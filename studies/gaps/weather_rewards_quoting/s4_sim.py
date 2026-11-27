"""Step 4: the simulated quoter (protocol 4.3-4.9). Reads build/min_*.parquet, build/mid_*.npy, meta.json,
routine_times.json. Writes out/*.json, out/*.csv and prints the tables.

usage: python3 s4_sim.py [last_day]     (default: all days; e.g. 2026-10-02 for the one-day slice check)
"""
import datetime as dt, glob, json, math, os, re, sys, collections
import numpy as np, pandas as pd
from pmlab.stats import mean_se, ratio_cluster, wilson

OUT = "/home/user/polymarket-lab/data/gaps_weather_rewards"
RES = "/home/user/polymarket-lab/studies/gaps/weather_rewards_quoting/out"
os.makedirs(RES, exist_ok=True)
LAST = sys.argv[1] if len(sys.argv) > 1 else "2026-10-11"
TAG = "" if LAST == "2026-10-11" else "_slice"
UTC = dt.timezone.utc
D0 = dt.datetime(2026, 10, 2, tzinfo=UTC)
M0 = int(D0.timestamp()) // 60                       # global minute id of 2026-10-02 00:00
SPLIT = M0 + 5 * 1440                                # first minute of the reporting period (2026-10-07)
BUDGET = 200.0

meta = json.load(open(OUT + "/meta.json"))
CONDS = sorted(meta)
routine = json.load(open(OUT + "/routine_times.json"))
last_ts = json.load(open(OUT + "/build/last_ts.json")) if os.path.exists(OUT + "/build/last_ts.json") else {}

# ---------------------------------------------------------------- load
files = [f for f in sorted(glob.glob(OUT + "/build/min_*.parquet")) if f[-18:-8] <= LAST]
D = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True).sort_values(["ci", "minute"]).reset_index(drop=True)
mid_days = sorted(glob.glob(OUT + "/build/mid_*.npy"))
MID = np.concatenate([np.load(f) for f in mid_days], axis=1)          # [market, minute since M0]
NMIN = MID.shape[1]
print("in-universe market-minutes", len(D), "markets", D.ci.nunique(), "mid minutes", NMIN, flush=True)


def epoch(s):
    s = s.replace(" ", "T").replace("+00", "+00:00") if s.endswith("+00") else s.replace(" ", "T")
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def bucket_key(item):
    m = re.search(r"-?\d+", item)
    return float(m.group(0)) if m else float("nan")


M = {}
for ci, c in enumerate(CONDS):
    v = meta[c]
    est = epoch(v["est"])
    M[ci] = dict(event=v["event"], city=v["city"], station=v["station"], est=est, end=est + 86400,
                 closed=epoch(v["closed"]) if v["closed"] else est + 86400 + 3 * 3600,
                 final=float(v["final_yes"]), key=bucket_key(v["item"]), step=2.0 if "F" in v["item"] else 1.0,
                 last=last_ts.get(c, 0) / 1000.0)
D["event"] = D.ci.map(lambda i: M[i]["event"])
D["city"] = D.ci.map(lambda i: M[i]["city"])
t_sec = D.minute.values * 60.0
D["date"] = pd.to_datetime(D.minute.values * 60, unit="s").strftime("%Y-%m-%d")
hrs = (D.ci.map(lambda i: M[i]["end"]).values - t_sec) / 3600.0
D["hclass"] = np.select([hrs > 24, hrs > 12, hrs > 6, hrs > 3, hrs > 0], ["a >24h", "b 24-12h", "c 12-6h", "d 6-3h", "e 3-0h"], "f after end")
D["mclass"] = D.msz.astype(int).astype(str)
D["moh"] = (D.minute.values % 60) // 10 * 10
# routine-report blocks and proximity
blk = np.zeros(len(D), bool); near = np.zeros(len(D), bool)
for ci, idx in D.groupby("ci").indices.items():
    st = M[ci]["station"]
    T = np.array(routine.get(st) or [], float)
    t = t_sec[idx]
    if len(T) == 0:
        blk[idx] = True
        continue
    j = np.searchsorted(T, t)
    dn = np.minimum(np.abs(T[np.clip(j, 0, len(T) - 1)] - t), np.abs(T[np.clip(j - 1, 0, len(T) - 1)] - t))
    near[idx] = dn <= 600
    nxt = T[np.clip(j, 0, len(T) - 1)]; prv = T[np.clip(j - 1, 0, len(T) - 1)]
    # (t, t+60] touches [T-600, T+600]  <=>  T-660 <= t < T+600
    blk[idx] = ((nxt - 660 <= t) & (t < nxt + 600)) | ((prv - 660 <= t) & (t < prv + 600))
D["near_report"] = near
D["blk_report"] = blk
D["blk_eod"] = hrs <= 3
D["no_station"] = D.ci.map(lambda i: M[i]["station"] is None).values
# distance from the leading bucket at t_m
ev_members = collections.defaultdict(list)
for ci in M:
    ev_members[M[ci]["event"]].append(ci)
lead = np.full(len(D), "alone", dtype=object)
mi = (D.minute.values - M0).astype(int)
for ev, idx in D.groupby("event").indices.items():
    mem = ev_members[ev]
    sub = MID[np.array(mem)][:, mi[idx]]                      # [members, rows]
    keys = np.array([M[c]["key"] for c in mem])
    anyv = ~np.isnan(sub)
    other = anyv.sum(axis=0)
    filled = np.where(anyv, sub, -1.0)
    lk = keys[filled.argmax(axis=0)]
    own = np.array([M[c]["key"] for c in D.ci.values[idx]])
    dist = np.abs(own - lk) / M[mem[0]]["step"]
    own_valid = ~np.isnan(MID[D.ci.values[idx], mi[idx]])
    cls = np.where(dist == 0, "0 leader", np.where(dist <= 1, "1 step", "2+ steps")).astype(object)
    cls[(other < 2) | ~own_valid] = "alone"
    lead[idx] = cls
D["lclass"] = lead
print(D.hclass.value_counts().to_dict(), D.lclass.value_counts().to_dict(), "blocked by report", round(float(D.blk_report.mean()), 3),
      "eod", round(float(D.blk_eod.mean()), 3), flush=True)

GROUPS = {ci: idx for ci, idx in D.groupby("ci").indices.items()}
COLS = {c: D[c].values for c in D.columns if D[c].dtype != object}


# ---------------------------------------------------------------- one-minute transition
def step(state, r, model_o, size, qb, qa, in_both, in_bid, in_ask, sh_both, sh_bid, sh_ask, mb0, mb1, ma0, ma1, R, shS=None):
    """state = [yes, no, unp_side, unp_sh, unp_cost, pairs, case]. Returns (income, capital, fills[(side, price, size, half)]).
    state[6] is set to the liveness case at the reward sample: 0 none, 1 both, 2 bid only, 3 ask only."""
    net = state[0] - state[1]
    if net == 0:
        if not in_both:
            return 0.0, 0.0, ()
        bl = al = True
    elif net > 0:
        if not in_ask:
            return 0.0, 0.0, ()
        bl, al = False, True
    else:
        if not in_bid:
            return 0.0, 0.0, ()
        bl, al = True, False
    pb = qb / 1000.0; pn = (1000.0 - qa) / 1000.0
    cap = size * ((pb if bl else 0.0) + (pn if al else 0.0)) + state[4]
    if model_o:
        fb0 = bl and mb0 <= qb; fa0 = al and ma0 >= qa
    else:
        fb0 = bl and mb0 < qb; fa0 = al and ma0 > qa
    lb = bl and not fb0; la = al and not fa0
    sh = sh_both if (lb and la) else sh_bid if lb else sh_ask if la else 0.0
    state[6] = 1 if (lb and la) else 2 if lb else 3 if la else 0
    inc = R / 1440.0 * sh
    if model_o:
        fb1 = lb and mb1 <= qb; fa1 = la and ma1 >= qa
    else:
        fb1 = lb and mb1 < qb; fa1 = la and ma1 > qa
    fills = []
    if fb0: fills.append((0, pb, size, 0))
    if fa0: fills.append((1, pn, size, 0))
    if fb1: fills.append((0, pb, size, 1))
    if fa1: fills.append((1, pn, size, 1))
    for side, p, z, _ in fills:
        state[side] += z
        if state[3] == 0 or state[2] == side:
            state[2] = side; state[3] += z; state[4] += z * p
        else:
            m = min(z, state[3]); state[5] += m
            state[4] -= state[4] * m / state[3]; state[3] -= m
            if z > m:
                state[2] = side; state[3] = z - m; state[4] = (z - m) * p
            elif state[3] <= 1e-9:
                state[3] = 0.0; state[4] = 0.0
    return inc, cap, fills


def run_variant(k, model_o, protect):
    inc = np.zeros(len(D)); cap = np.zeros(len(D)); quoted = np.zeros(len(D), bool); incS = np.zeros(len(D))
    fills = []
    pairs_total = 0.0
    c = COLS
    qb_, qa_ = c[f"qb{k}"], c[f"qa{k}"]
    ib, ibd, ia = c[f"in_both{k}"], c[f"in_bid{k}"], c[f"in_ask{k}"]
    s2, sb, sa = c[f"sh_both{k}"], c[f"sh_bid{k}"], c[f"sh_ask{k}"]
    t2, tb, ta = c[f"sh1_both{k}"], c[f"sh1_bid{k}"], c[f"sh1_ask{k}"]
    ok = c["valid_q"].copy()
    if protect:
        ok &= ~(c["blk_report"] | c["blk_eod"] | c["no_station"])
    for ci, idx in GROUPS.items():
        st = [0.0, 0.0, 0, 0.0, 0.0, 0.0, 0]
        for i in idx:
            if not ok[i]:
                continue
            a, cp, fl = step(st, i, model_o, c["msz"][i], qb_[i], qa_[i], ib[i], ibd[i], ia[i], s2[i], sb[i], sa[i],
                             c["minbid0"][i], c["minbid1"][i], c["maxask0"][i], c["maxask1"][i], c["R"][i])
            if cp > 0:
                quoted[i] = True; cap[i] = cp; inc[i] = a
                # sensitivity: same liveness, competitors as one maker
                if st[6]:
                    incS[i] = c["R"][i] / 1440.0 * (t2[i] if st[6] == 1 else tb[i] if st[6] == 2 else ta[i])
                for side, p, z, half in fl:
                    fills.append((ci, int(c["minute"][i]), side, p, z, half, i))
        pairs_total += st[5]
    F = pd.DataFrame(fills, columns=["ci", "minute", "side", "price", "size", "half", "row"])
    return inc, incS, cap, quoted, F, pairs_total


def mark_fills(F):
    """settlement PnL and markouts per share (protocol 4.5)."""
    if len(F) == 0:
        for col in ["pnl", "ps", "m5", "m30", "m120", "date", "event", "yes_won"]:
            F[col] = []
        return F
    fin = F.ci.map(lambda i: M[i]["final"]).values
    val = np.where(F.side.values == 0, fin, 1.0 - fin)
    F["ps"] = val - F.price.values
    F["pnl"] = F.ps * F["size"]
    F["yes_won"] = fin
    F["event"] = F.ci.map(lambda i: M[i]["event"])
    F["date"] = pd.to_datetime(F.minute.values * 60, unit="s").strftime("%Y-%m-%d")
    for X in (5, 30, 120):
        out = np.full(len(F), np.nan)
        for n, (ci, mnt, side, p) in enumerate(zip(F.ci.values, F.minute.values, F.side.values, F.price.values)):
            j = int(mnt - M0) + 1 + X
            mk = np.nan
            if j < NMIN:
                seg = MID[ci, max(j - 10, 0):j + 1]
                okk = np.flatnonzero(~np.isnan(seg))
                if len(okk):
                    mk = float(seg[okk[-1]])
            if np.isnan(mk) and (M0 + j) * 60 > M[ci]["last"] > 0:
                mk = M[ci]["final"]
            if not np.isnan(mk):
                out[n] = (mk - p) if side == 0 else ((1.0 - mk) - p)
        F[f"m{X}"] = out
    return F


def market_days(inc, quoted, cap, F, mask=None):
    """per market-day table: reward (after the 1-dollar rule), settlement PnL, net, capital-days."""
    d = pd.DataFrame({"ci": D.ci.values, "date": D.date.values, "event": D.event.values, "city": D.city.values,
                      "inc": inc, "q": quoted, "cap": cap})
    if mask is not None:
        d = d[mask]
    g = d.groupby(["ci", "date"]).agg(event=("event", "first"), city=("city", "first"), raw=("inc", "sum"), qmin=("q", "sum"),
                                      capmin=("cap", "sum")).reset_index()
    g["reward"] = np.where(g.raw >= 1.0, g.raw, 0.0)
    if len(F):
        pf = F.groupby(["ci", "date"]).agg(pnl=("pnl", "sum"), fills=("pnl", "size")).reset_index()
        g = g.merge(pf, on=["ci", "date"], how="outer")
        g["event"] = g.event.fillna(g.ci.map(lambda i: M[i]["event"])); g["city"] = g.city.fillna(g.ci.map(lambda i: M[i]["city"]))
    else:
        g["pnl"] = 0.0; g["fills"] = 0
    g = g.fillna({"raw": 0.0, "reward": 0.0, "pnl": 0.0, "fills": 0, "qmin": 0, "capmin": 0.0})
    g["net"] = g.reward + g.pnl
    g["capday"] = g.capmin / 1440.0
    return g[(g.qmin > 0) | (g.fills > 0)]


def cl_mean(g, col, den=None):
    """mean of `col` per market-day (or ratio to `den`) with errors clustered by event."""
    e = g.groupby("event").agg(num=(col, "sum"), n=(col, "size"), den=(den or col, "sum"))
    return ratio_cluster(e.num.tolist(), (e.den if den else e.n).tolist())


def summarize(name, inc, incS, cap, quoted, F, pairs, lo=None, hi=None):
    g = market_days(inc, quoted, cap, F)
    if lo:
        g = g[(g.date >= lo) & (g.date <= hi)]
        Fx = F[(F.date >= lo) & (F.date <= hi)]
        msk = (D.date.values >= lo) & (D.date.values <= hi)
    else:
        Fx = F; msk = np.ones(len(D), bool)
    mean, se, t = cl_mean(g, "net")
    rw, _, _ = cl_mean(g, "reward"); pl, pse, pt = cl_mean(g, "pnl")
    rcap, rcse, rct = cl_mean(g, "net", "capday")
    out = dict(variant=name, market_days=int(len(g)), markets=int(g.ci.nunique()), events=int(g.event.nunique()),
               reward_per_md=rw, pnl_per_md=pl, net_per_md=mean, se=se, t=t,
               reward_total=float(g.reward.sum()), reward_raw_total=float(g.raw.sum()), pnl_total=float(g.pnl.sum()), net_total=float(g.net.sum()),
               reward_one_maker_total=float(incS[msk].sum()),
               capital_days=float(g.capday.sum()), net_per_capday=rcap, t_capday=rct, reward_per_capday=float(g.reward.sum() / max(g.capday.sum(), 1e-9)),
               mean_cap_quoted=float(cap[msk & quoted].mean()) if (msk & quoted).any() else float("nan"),
               quoted_minutes=int((msk & quoted).sum()), fills=int(len(Fx)), fill_shares=float(Fx["size"].sum()) if len(Fx) else 0.0,
               n_days=int(g.date.nunique()))
    if len(Fx):
        e = Fx.groupby("event").agg(pnl=("pnl", "sum"), sh=("size", "sum"))
        r, se_, t_ = ratio_cluster(e.pnl.tolist(), e.sh.tolist())
        out.update(settle_ps=r, settle_ps_t=t_)
        for X in (5, 30, 120):
            ok = Fx[~Fx[f"m{X}"].isna()]
            ee = ok.assign(v=ok[f"m{X}"] * ok["size"]).groupby("event").agg(v=("v", "sum"), sh=("size", "sum"))
            r, se_, t_ = ratio_cluster(ee.v.tolist(), ee.sh.tolist())
            out[f"m{X}_ps"] = r; out[f"m{X}_t"] = t_; out[f"m{X}_missing"] = int(len(Fx) - len(ok))
    return out, g


# ---------------------------------------------------------------- the six base variants
VAR = {}
for k in (0, 1, 2):
    for mo in (False, True):
        name = f"k{k}{'O' if mo else 'P'}"
        inc, incS, cap, quoted, F, pairs = run_variant(k, mo, False)
        F = mark_fills(F)
        VAR[name] = dict(k=k, mo=mo, protect=False, inc=inc, incS=incS, cap=cap, quoted=quoted, F=F, pairs=pairs)
        print(name, "fills", len(F), "pairs(shares)", pairs, flush=True)

DAYS = sorted(D.date.unique())
A_LO, A_HI = DAYS[0], min("2026-10-06", DAYS[-1])
B_LO, B_HI = "2026-10-07", DAYS[-1]
first5 = {}
for name, v in VAR.items():
    s, _ = summarize(name, v["inc"], v["incS"], v["cap"], v["quoted"], v["F"], v["pairs"], A_LO, A_HI)
    first5[name] = s["net_per_md"]
best6 = max(first5, key=first5.get)
print("first-5-day net per market-day:", {k: round(x, 3) for k, x in first5.items()}, "-> best of six:", best6, flush=True)
b = VAR[best6]
name7 = best6 + "+prot"
inc, incS, cap, quoted, F, pairs = run_variant(b["k"], b["mo"], True)
VAR[name7] = dict(k=b["k"], mo=b["mo"], protect=True, inc=inc, incS=incS, cap=cap, quoted=quoted, F=mark_fills(F), pairs=pairs)

rows = []
MD = {}
for name, v in VAR.items():
    for lab, lo, hi in (("all", None, None), ("first5", A_LO, A_HI), ("last5", B_LO, B_HI)):
        if lab == "last5" and B_LO > DAYS[-1]:
            continue
        s, g = summarize(name, v["inc"], v["incS"], v["cap"], v["quoted"], v["F"], v["pairs"], lo, hi)
        s["period"] = lab; s["pairs_shares_all_period"] = v["pairs"]
        rows.append(s)
        if lab == "all":
            MD[name] = g
S = pd.DataFrame(rows)
S.to_csv(f"{RES}/variants{TAG}.csv", index=False)
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 60); pd.set_option("display.float_format", lambda x: f"{x:,.4f}")
show = ["variant", "period", "market_days", "markets", "events", "reward_per_md", "pnl_per_md", "net_per_md", "t", "reward_total", "pnl_total",
        "net_total", "capital_days", "net_per_capday", "fills", "settle_ps", "settle_ps_t", "m5_ps", "m30_ps", "m120_ps"]
print(S[[c for c in show if c in S]].to_string(index=False), flush=True)

# ---------------------------------------------------------------- sanity checks (protocol 4.11)
chk = {}
allF = VAR["k0O"]["F"]
if len(allF):
    yb = allF[(allF.side == 0) & (allF.price >= 0.40) & (allF.price <= 0.60)]
    ev_ = yb.groupby("event").yes_won.first()
    chk["yes_fills_040_060"] = dict(n=int(len(yb)), events=int(len(ev_)), yes_win_rate_by_fill=float(yb.yes_won.mean()) if len(yb) else None,
                                    mean_price=float(yb.price.mean()) if len(yb) else None,
                                    yes_win_rate_by_event=float(ev_.mean()) if len(ev_) else None,
                                    wilson_by_event=wilson(int(ev_.sum()), int(len(ev_))) if len(ev_) else None)
    nb = allF[(allF.side == 1) & (allF.price >= 0.40) & (allF.price <= 0.60)]
    chk["no_fills_040_060"] = dict(n=int(len(nb)), no_win_rate_by_fill=float((1 - nb.yes_won).mean()) if len(nb) else None,
                                   mean_price=float(nb.price.mean()) if len(nb) else None)
g0 = MD["k0O"]
rate_md = D.groupby(["ci", "date"]).R.max().reset_index()
mm = g0.merge(rate_md, on=["ci", "date"], how="left")
chk["max_reward_over_rate"] = float((mm.raw / mm.R).max())
chk["share_range"] = [float(min(D[f"sh_both{k}"].min() for k in (0, 1, 2))), float(max(D[f"sh_both{k}"].max() for k in (0, 1, 2)))]
chk["minute_range_utc"] = [str(pd.to_datetime(D.minute.min() * 60, unit="s")), str(pd.to_datetime(D.minute.max() * 60, unit="s"))]
chk["valid_quote_instants_pct"] = float(D.valid_q.mean() * 100)
chk["maker_fee"] = 0.0
print("CHECKS", json.dumps(chk, indent=1, default=str), flush=True)
json.dump(chk, open(f"{RES}/checks{TAG}.json", "w"), indent=1, default=str)


# ---------------------------------------------------------------- breakdowns (R3) for every variant, full period and halves
def breakdown(v, col, lo=None, hi=None):
    msk = np.ones(len(D), bool) if lo is None else (D.date.values >= lo) & (D.date.values <= hi)
    d = pd.DataFrame({"cls": D[col].values[msk], "event": D.event.values[msk], "inc": v["inc"][msk], "cap": v["cap"][msk], "q": v["quoted"][msk]})
    a = d.groupby("cls").agg(reward=("inc", "sum"), quoted_min=("q", "sum"), capmin=("cap", "sum"))
    F = v["F"]
    if len(F):
        Fx = F if lo is None else F[(F.date >= lo) & (F.date <= hi)]
        fc = pd.Series(D[col].values[Fx.row.values], index=Fx.index)
        pf = Fx.assign(cls=fc).groupby("cls").agg(pnl=("pnl", "sum"), fills=("pnl", "size"))
        a = a.join(pf, how="outer")
        # t by event for the net of the class
        de = d.groupby(["cls", "event"]).inc.sum().rename("inc").reset_index()
        fe = Fx.assign(cls=fc).groupby(["cls", "event"]).pnl.sum().reset_index()
        ne = de.merge(fe, on=["cls", "event"], how="outer").fillna(0.0)
        ne["net"] = ne.inc + ne.pnl
        tt = ne.groupby("cls").net.apply(lambda s: mean_se(s.tolist())[2]).rename("t_event")
        a = a.join(tt)
    a = a.fillna(0.0)
    a["net"] = a.reward + a.get("pnl", 0.0)
    a["net_per_capday"] = a.net / (a.capmin / 1440.0).replace(0, np.nan)
    a["capdays"] = a.capmin / 1440.0
    return a.drop(columns=["capmin"])


BR = {}
for name, v in VAR.items():
    for col in ("hclass", "lclass", "moh", "near_report", "mclass", "city"):
        for lab, lo, hi in (("all", None, None), ("first5", A_LO, A_HI), ("last5", B_LO, B_HI)):
            if lab == "last5" and B_LO > DAYS[-1]:
                continue
            x = breakdown(v, col, lo, hi).reset_index()
            x.insert(0, "period", lab); x.insert(0, "dim", col); x.insert(0, "variant", name)
            BR[(name, col, lab)] = x
BRD = pd.concat(BR.values(), ignore_index=True)
BRD.to_csv(f"{RES}/breakdowns{TAG}.csv", index=False)
for col in ("hclass", "lclass", "moh", "near_report", "mclass"):
    for nm in (best6, name7):
        print(f"\n== {nm} by {col} (all 10 days)"); print(BR[(nm, col, "all")].drop(columns=["variant", "dim", "period"]).to_string(index=False))
print(f"\n== {best6} by city (all 10 days)"); print(BR[(best6, "city", "all")].drop(columns=["variant", "dim", "period"]).sort_values("net").to_string(index=False), flush=True)

# ---------------------------------------------------------------- the 200-dollar account (protocol 4.9)
f5 = {}
for name, v in VAR.items():
    s, _ = summarize(name, v["inc"], v["incS"], v["cap"], v["quoted"], v["F"], v["pairs"], A_LO, A_HI)
    f5[name] = s["net_per_md"]
best7 = max(f5, key=f5.get)
ak, aprot = VAR[best7]["k"], VAR[best7]["protect"]
fname = f"k{ak}O" + ("+prot" if aprot else "")
aux = False
if fname not in VAR:                                 # filter needs (k*, O, protection*): auxiliary run, counted in the results
    inc, incS, cap, quoted, F, pairs = run_variant(ak, True, aprot)
    VAR[fname] = dict(k=ak, mo=True, protect=aprot, inc=inc, incS=incS, cap=cap, quoted=quoted, F=mark_fills(F), pairs=pairs)
    aux = True
keep = {}
for col in ("hclass", "lclass", "mclass"):
    x = breakdown(VAR[fname], col, A_LO, A_HI)
    keep[col] = sorted(str(c) for c in x.index[x.net >= 0])
    print("class filter", col, {str(c): round(float(n), 2) for c, n in x.net.items()}, "-> keep", keep[col])
elig_cls = D.hclass.isin(keep["hclass"]).values & D.lclass.isin(keep["lclass"]).values & D.mclass.isin(keep["mclass"]).values
if aprot:
    elig_cls &= ~(D.blk_eod.values | D.no_station.values)
by_minute = collections.defaultdict(list)
for i, m in enumerate(D.minute.values):
    by_minute[int(m)].append(i)


STASH = {}


class _Held(dict):
    """dict of held markets that stashes the state of a dropped market holding unpaired inventory."""
    def pop(self, ci, *a):
        st = super().pop(ci, *a)
        if st is not None and st[3] > 0:
            STASH[ci] = st
        return st


def account_report(model_o, lo, hi, label):
    global STASH
    STASH = {}
    m_lo = M0 + DAYS.index(lo) * 1440; m_hi = M0 + (DAYS.index(hi) + 1) * 1440
    inc_rows, F, quoted_md, pairs, cap_used = _run_account_impl(model_o, m_lo, m_hi)
    rw = pd.DataFrame([(ci, d, x) for (ci, d), x in inc_rows.items()], columns=["ci", "date", "raw"])
    rw["reward"] = np.where(rw.raw >= 1.0, rw.raw, 0.0)
    rw["event"] = rw.ci.map(lambda i: M[i]["event"])
    days = [d for d in DAYS if lo <= d <= hi]
    daily = pd.DataFrame({"date": days}).set_index("date")
    daily["reward"] = rw.groupby("date").reward.sum().reindex(days).fillna(0.0)
    daily["reward_if_1usd_rule_per_account"] = rw.groupby("date").raw.sum().reindex(days).fillna(0.0)
    daily["pnl"] = (F.groupby("date").pnl.sum() if len(F) else pd.Series(dtype=float)).reindex(days).fillna(0.0)
    daily["fills"] = (F.groupby("date").size() if len(F) else pd.Series(dtype=float)).reindex(days).fillna(0).astype(int)
    daily["net"] = daily.reward + daily.pnl
    ev = rw.groupby("event").reward.sum().rename("reward").to_frame()
    if len(F):
        ev = ev.join(F.groupby("event").pnl.sum(), how="outer")
    else:
        ev["pnl"] = 0.0
    ev = ev.fillna(0.0); ev["net"] = ev.reward + ev.pnl
    me, se, t_ev = mean_se(ev.net.tolist())
    md_, sd_, t_day = mean_se(daily.net.tolist())
    res = dict(label=label, fill_model="O" if model_o else "P", k=ak, protection=aprot, days=len(days),
               usd_per_day=float(daily.net.mean()), pct_per_day=float(daily.net.mean() / BUDGET * 100),
               reward_per_day=float(daily.reward.mean()), pnl_per_day=float(daily.pnl.mean()),
               markets=len({ci for ci, _ in quoted_md}), market_days=len(quoted_md), events=int(len(ev)),
               fills=int(len(F)), pairs_completed_shares=float(pairs), worst_day=float(daily.net.min()), best_day=float(daily.net.max()),
               t_events=t_ev, t_days=t_day, mean_capital_reserved=float(np.mean(cap_used)),
               reward_removed_by_1usd_rule=float((rw.raw - rw.reward).sum()), total_net=float(daily.net.sum()),
               settle_ps=float(F.pnl.sum() / F["size"].sum()) if len(F) else None, daily=daily.reset_index().to_dict("records"))
    return res, rw, F


def _run_account_impl(model_o, m_lo, m_hi):
    c = COLS; k = ak
    held = _Held(); locked = {}
    inc_rows = collections.defaultdict(float); fills = []; quoted_md = set(); pairs = 0.0; cap_used = []
    for m in range(m_lo, m_hi):
        now = m * 60.0
        rows = {int(c["ci"][i]): i for i in by_minute.get(m, ())}
        for ci in [x for x, (cost, rel) in locked.items() if rel <= now]:
            del locked[ci]; STASH.pop(ci, None)
        for ci in list(held):
            i = rows.get(ci)
            if i is None or not elig_cls[i]:
                st = held.pop(ci)
                if st[3] > 0:
                    locked[ci] = (st[4], M[ci]["closed"])
                else:
                    pairs += st[5]
        used = sum(c["msz"][rows[ci]] * 1.0 + held[ci][4] for ci in held) + sum(x[0] for x in locked.values())
        for ci in sorted(held, key=lambda x: -(c["msz"][rows[x]])):
            if used > BUDGET + 1e-9:
                st = held.pop(ci)
                used -= c["msz"][rows[ci]] * 1.0 + st[4]
                if st[3] > 0:
                    locked[ci] = (st[4], M[ci]["closed"]); used += st[4]
                else:
                    pairs += st[5]
        free = BUDGET - used
        cand = []
        for ci, i in rows.items():
            if ci in held or not elig_cls[i]:
                continue
            if ci in locked:
                cand.append((1e18, ci, i))
            elif c["valid_q"][i] and c[f"in_both{k}"][i] and not (aprot and c["blk_report"][i]):
                cand.append((c["R"][i] * c[f"sh0_{k}"][i] / max(c["msz"][i], 1.0), ci, i))
        for score, ci, i in sorted(cand, reverse=True):
            need = c["msz"][i] * 1.0
            if ci in locked:
                if need <= free + 1e-9:
                    locked.pop(ci)
                    held[ci] = STASH.pop(ci)
                    free -= need
            elif score > 0 and need <= free + 1e-9:
                held[ci] = [0.0, 0.0, 0, 0.0, 0.0, 0.0, 0]
                free -= need
        cap_used.append(BUDGET - free)
        for ci, st in held.items():
            i = rows[ci]
            if not c["valid_q"][i] or (aprot and c["blk_report"][i]):
                continue
            a, cp, fl = step(st, i, model_o, c["msz"][i], c[f"qb{k}"][i], c[f"qa{k}"][i], c[f"in_both{k}"][i], c[f"in_bid{k}"][i],
                             c[f"in_ask{k}"][i], c[f"sh_both{k}"][i], c[f"sh_bid{k}"][i], c[f"sh_ask{k}"][i],
                             c["minbid0"][i], c["minbid1"][i], c["maxask0"][i], c["maxask1"][i], c["R"][i])
            if cp > 0:
                d = D.date.values[i]
                inc_rows[(ci, d)] += a
                quoted_md.add((ci, d))
                for side, p, z, half in fl:
                    fills.append((ci, m, side, p, z, half, i))
    pairs += sum(st[5] for st in held.values()) + sum(st[5] for st in STASH.values())
    F = mark_fills(pd.DataFrame(fills, columns=["ci", "minute", "side", "price", "size", "half", "row"]))
    return inc_rows, F, quoted_md, pairs, cap_used


ACC = []
periods = [("first5 (choice period, reference only)", A_LO, A_HI)]
if B_LO <= DAYS[-1]:
    periods.append(("last5 (reporting period)", B_LO, B_HI))
for label, lo, hi in periods:
    for mo in (False, True):
        r, rw, F = account_report(mo, lo, hi, label)
        ACC.append(r)
        print("\nACCOUNT", {k_: (round(v_, 4) if isinstance(v_, float) else v_) for k_, v_ in r.items() if k_ != "daily"})
        print(pd.DataFrame(r["daily"]).to_string(index=False), flush=True)
json.dump(dict(best_of_six=best6, variant7=name7, first5_net_per_md=f5, account_variant=best7, account_k=ak, account_protection=aprot,
               filter_from=fname, auxiliary_filter_run=aux, class_filter=keep, accounts=ACC,
               october_median_rate_quoted=float(np.median(D.R.values[VAR[best7]["quoted"]])) if VAR[best7]["quoted"].any() else None),
          open(f"{RES}/account{TAG}.json", "w"), indent=1, default=str)
np.save(f"{RES}/inc_{best7}{TAG}.npy", VAR[best7]["inc"])
for name, v in VAR.items():
    v["F"].to_csv(f"{RES}/fills_{name}{TAG}.csv", index=False)
    MD.get(name, market_days(v["inc"], v["quoted"], v["cap"], v["F"])).to_csv(f"{RES}/marketdays_{name}{TAG}.csv", index=False)
D[["ci", "minute", "date", "event", "city", "R", "msz", "hclass", "lclass", "mclass", "moh", "near_report", "blk_report", "blk_eod", "no_station",
   "valid_q"]].assign(**{f"inc_{n}": v["inc"] for n, v in VAR.items()}, **{f"q_{n}": v["quoted"] for n, v in VAR.items()},
                      **{f"cap_{n}": v["cap"] for n, v in VAR.items()}).to_parquet(f"{RES}/minutes{TAG}.parquet", index=False)
print("done")

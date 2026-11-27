"""Audit step 3: own re-implementation of the pre-registered 200-dollar account (protocol 4.9) on the author's
per-minute build (build/min_*.parquet, validated against the audit replay in a2) and the author's mid arrays.
Class filter recomputed here from meta (hours to end), mids (leader distance) and minimum size.
usage: python3 -I a3_account.py [scale] [budget]    scale = reward multiplier (1 = October rates)
"""
import collections, datetime as dt, glob, json, os, re, sys
import numpy as np, pandas as pd

G = "/home/user/polymarket-lab/data/gaps_weather_rewards"
HERE = os.path.dirname(os.path.abspath(__file__))
SCALE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
BUDGET = float(sys.argv[2]) if len(sys.argv) > 2 else 200.0
meta = json.load(open(G + "/meta.json"))
CONDS = sorted(meta)
M0 = int(dt.datetime(2026, 10, 2, tzinfo=dt.timezone.utc).timestamp()) // 60


def ep(s):
    return dt.datetime.fromisoformat(s.replace(" ", "T").replace("+00", "+00:00") if s.endswith("+00") else s.replace("Z", "+00:00")).timestamp()


EST = np.array([ep(meta[c]["est"]) for c in CONDS])
CLOSE = np.array([ep(meta[c]["closed"]) if meta[c]["closed"] else ep(meta[c]["est"]) + 86400 + 3 * 3600 for c in CONDS])
FIN = np.array([float(meta[c]["final_yes"]) for c in CONDS])
EVENT = [meta[c]["event"] for c in CONDS]
KEY = np.array([float(re.search(r"-?\d+", meta[c]["item"]).group(0)) for c in CONDS])
STEP = np.array([2.0 if "F" in meta[c]["item"] else 1.0 for c in CONDS])
MID = np.concatenate([np.load(f) for f in sorted(glob.glob(G + "/build/mid_*.npy"))], axis=1)
members = collections.defaultdict(list)
for i, e in enumerate(EVENT):
    members[e].append(i)

cols = ["ci", "minute", "R", "msz", "valid_q", "bb", "ba", "in_both0", "in_bid0", "in_ask0", "sh_both0", "sh_bid0", "sh_ask0", "sh0_0",
        "minbid0", "minbid1", "maxask0", "maxask1"]
D = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(G + "/build/min_*.parquet"))], ignore_index=True)
D = D[(D.minute >= M0) & (D.minute < M0 + 10 * 1440)].reset_index(drop=True)
hrs = (EST[D.ci.values] + 86400 - D.minute.values * 60.0) / 3600
hcl = np.select([hrs > 24, hrs > 12, hrs > 6, hrs > 3, hrs > 0], [0, 1, 2, 3, 4], 5)
# leader distance at t_m
mi = D.minute.values - M0
lcl = np.full(len(D), 3)                       # 0 leader, 1 one step, 2 two+, 3 alone
for i in range(len(D)):
    pass
ci_ = D.ci.values
evs = collections.defaultdict(list)
for i, c in enumerate(ci_):
    evs[EVENT[c]].append(i)
for e, idx in evs.items():
    idx = np.array(idx); mem = np.array(members[e])
    sub = MID[mem][:, mi[idx]]
    nval = (~np.isnan(sub)).sum(0)
    lead = mem[np.nanargmax(np.where(np.isnan(sub), -1, sub), axis=0)]
    dist = np.abs(KEY[ci_[idx]] - KEY[lead]) / STEP[ci_[idx]]
    own = ~np.isnan(MID[ci_[idx], mi[idx]])
    c_ = np.where(dist == 0, 0, np.where(dist <= 1, 1, 2))
    c_[(nval < 2) | ~own] = 3
    lcl[idx] = c_
D["hcl"] = hcl; D["lcl"] = lcl


def step(st, r, O):
    """st: [yes, no, cost_unpaired]; returns (income, fills)."""
    net = st[0] - st[1]
    if net == 0:
        if not r["in_both0"]:
            return 0.0, [], False
        lb = la = True
    elif net > 0:
        if not r["in_ask0"]:
            return 0.0, [], False
        lb, la = False, True
    else:
        if not r["in_bid0"]:
            return 0.0, [], False
        lb, la = True, False
    qb, qa = r["bb"], r["ba"]
    hb0 = lb and (r["minbid0"] <= qb if O else r["minbid0"] < qb)
    ha0 = la and (r["maxask0"] >= qa if O else r["maxask0"] > qa)
    lb2, la2 = lb and not hb0, la and not ha0
    sh = r["sh_both0"] if (lb2 and la2) else r["sh_bid0"] if lb2 else r["sh_ask0"] if la2 else 0.0
    hb1 = lb2 and (r["minbid1"] <= qb if O else r["minbid1"] < qb)
    ha1 = la2 and (r["maxask1"] >= qa if O else r["maxask1"] > qa)
    fl = []
    if hb0 or hb1:
        fl.append((0, qb / 1000, r["msz"]))
    if ha0 or ha1:
        fl.append((1, (1000 - qa) / 1000, r["msz"]))
    for side, p, z in fl:
        st[side] += z
    # cost of unpaired inventory: recompute from the fill ledger
    for side, p, z in fl:
        st[3].append((side, p, z))
    net = st[0] - st[1]
    if net == 0:
        st[2] = 0.0; st[3].clear()
    else:
        hold = 0 if net > 0 else 1
        lots = [(p, z) for s, p, z in st[3] if s == hold]
        # FIFO pairing: the most recent |net| shares of the held side are unpaired
        need, cost = abs(net), 0.0
        for p, z in reversed(lots):
            t = min(z, need); cost += t * p; need -= t
            if need <= 0:
                break
        st[2] = cost
    return SCALE * r["R"] / 1440 * sh, fl, True


def account(O, lo_day, keep_h, keep_l, keep_m):
    lo = M0 + lo_day * 1440; hi = lo + 5 * 1440
    sub = D[(D.minute >= lo) & (D.minute < hi)]
    elig = sub.hcl.isin(keep_h).values & sub.lcl.isin(keep_l).values & sub.msz.isin(keep_m).values
    recs = sub.to_dict("records")
    bym = collections.defaultdict(dict)
    for r, e in zip(recs, elig):
        r["elig"] = e
        bym[r["minute"]][r["ci"]] = r
    held, locked, stash = {}, {}, {}
    inc = collections.defaultdict(float); fills = []; capu = []
    for m in range(lo, hi):
        now = m * 60.0; rows = bym.get(m, {})
        for c in [c for c, (cost, rel) in locked.items() if rel <= now]:
            del locked[c]; stash.pop(c, None)
        for c in list(held):
            r = rows.get(c)
            if r is None or not r["elig"]:
                st = held.pop(c)
                if st[2] > 0:
                    locked[c] = (st[2], CLOSE[c]); stash[c] = st
        used = sum(rows[c]["msz"] + held[c][2] for c in held) + sum(v[0] for v in locked.values())
        for c in sorted(held, key=lambda x: -rows[x]["msz"]):
            if used > BUDGET + 1e-9:
                st = held.pop(c); used -= rows[c]["msz"] + st[2]
                if st[2] > 0:
                    locked[c] = (st[2], CLOSE[c]); stash[c] = st; used += st[2]
        free = BUDGET - used
        cand = []
        for c, r in rows.items():
            if c in held or not r["elig"]:
                continue
            if c in locked:
                cand.append((1e18, c))
            elif r["valid_q"] and r["in_both0"]:
                cand.append((r["R"] * r["sh0_0"] / max(r["msz"], 1), c))
        for sc, c in sorted(cand, reverse=True):
            need = rows[c]["msz"]
            if need > free + 1e-9 or sc <= 0:
                continue
            if c in locked:
                locked.pop(c); held[c] = stash.pop(c)
            else:
                held[c] = [0.0, 0.0, 0.0, []]
            free -= need
        capu.append(BUDGET - free)
        for c, st in held.items():
            r = rows[c]
            if not r["valid_q"]:
                continue
            a, fl, q = step(st, r, O)
            if q:
                day = (m - M0) // 1440
                inc[(c, day)] += a
                for side, p, z in fl:
                    fills.append((c, m, day, side, p, z, ((FIN[c] if side == 0 else 1 - FIN[c]) - p) * z))
    rw = pd.DataFrame([(c, d_, x) for (c, d_), x in inc.items()], columns=["ci", "day", "raw"])
    rw["reward"] = np.where(rw.raw >= 1, rw.raw, 0.0)
    F = pd.DataFrame(fills, columns=["ci", "m", "day", "side", "p", "z", "pnl"])
    days = range(lo_day, lo_day + 5)
    daily = pd.DataFrame({"reward": rw.groupby("day").reward.sum(), "raw": rw.groupby("day").raw.sum(),
                          "pnl": F.groupby("day").pnl.sum() if len(F) else 0.0}).reindex(days).fillna(0.0)
    daily["net"] = daily.reward + daily.pnl
    ev = pd.concat([rw.assign(e=rw.ci.map(lambda c: EVENT[c])).groupby("e").reward.sum(),
                    F.assign(e=F.ci.map(lambda c: EVENT[c])).groupby("e").pnl.sum() if len(F) else pd.Series(dtype=float)], axis=1).fillna(0).sum(1)
    k = len(ev); se_e = ev.std(ddof=1) / np.sqrt(k)
    tot_per_day = ev.sum() / 5
    # t by event on the period total: se of the total = sqrt(k) * sd(events)
    t_ev = ev.sum() / (np.sqrt(k) * ev.std(ddof=1))
    t_day = daily.net.mean() / (daily.net.std(ddof=1) / np.sqrt(5))
    return dict(usd_day=float(daily.net.mean()), ci95_by_event=[float(tot_per_day - 1.96 * np.sqrt(k) * ev.std(ddof=1) / 5), float(tot_per_day + 1.96 * np.sqrt(k) * ev.std(ddof=1) / 5)],
                t_events=float(t_ev), t_days=float(t_day), reward_day=float(daily.reward.mean()), raw_reward_day=float(daily.raw.mean()),
                pnl_day=float(daily.pnl.mean()), markets=int(rw.ci.nunique()), market_days=int(len(rw)), events=int(k), fills=int(len(F)),
                share_md_under_1usd=float((rw.raw < 1).mean()), daily_net=[round(x, 2) for x in daily.net], mean_cap=float(np.mean(capu)),
                settle_c_share=float(100 * F.pnl.sum() / F.z.sum()) if len(F) else None), rw, F


if __name__ == "__main__":
    keep_h = [0, 1, 3, 4, 5]; keep_l = [0, 1, 2]; keep_m = [20.0, 100.0]       # the author's filter, verified in a4
    if len(sys.argv) > 3 and sys.argv[3] == "nofilter":
        keep_h = [0, 1, 2, 3, 4, 5]; keep_l = [0, 1, 2, 3]
    out = {}
    for lab, d0 in (("first5", 0), ("last5", 5)):
        for O in (False, True):
            r, rw, F = account(O, d0, keep_h, keep_l, keep_m)
            out[f"{lab}_{'O' if O else 'P'}"] = r
            print(lab, "O" if O else "P", json.dumps(r), flush=True)
    tag = f"s{SCALE}_b{int(BUDGET)}" + ("_nofilter" if len(sys.argv) > 3 else "")
    json.dump(out, open(f"{HERE}/out/a3_{tag}.json", "w"), indent=1)

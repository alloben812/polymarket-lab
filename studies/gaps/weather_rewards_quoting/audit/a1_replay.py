"""Audit step 1: independent book replay from the raw filtered PendulumFlow files for a 1/4 sample of markets
(int(condition_id, 16) % 4 == SEL), reporting period 2026-10-07..10-11, k = 0.

Writes audit/out/min_<SEL>.parquet: per in-universe market-minute: R, msz, v, bb, ba, valid, in_both/bid/ask,
reward shares (both / bid only / ask only) at t_m + 30 s, and the first qualifying print time under P and O for
the YES bid and the NO bid for latency 0 and 2 s / 5 s (window (t_m + L, t_m + 60 + L]).
Own code: does not import any of the author's modules.
usage: python3 -I a1_replay.py [SEL]
"""
import datetime as dt, glob, json, os, sys
import numpy as np, pandas as pd, pyarrow.parquet as pq, pyarrow.dataset as ds

PF = "/home/user/polymarket-lab/data/datasets/pflow_weather"
HX = "/home/user/polymarket-lab/data/datasets/houroux_weather"
META = "/home/user/polymarket-lab/data/gaps_weather_rewards/meta.json"
OUTD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUTD, exist_ok=True)
SEL = int(sys.argv[1]) if len(sys.argv) > 1 else 0
DAYS = ["2026-10-%02d" % d for d in range(7, 12)]
WARM = ["2026-10-06T%02d" % h for h in range(20, 24)]           # warm-up hours (book state before 10-07)
LAT = (0, 2000, 5000)

meta = json.load(open(META))
# ---- reward universe as of each minute, straight from the Houroux discovery files
u = pd.concat([pq.read_table(f, columns=["discovery_sequence", "received_at_ns", "condition_id", "market_slug", "daily_reward",
                                         "rewards_max_spread_cents", "rewards_min_size"]).to_pandas()
               for f in sorted(glob.glob(HX + "/marketsfull_*.parquet"))])
snap_t = u.groupby("discovery_sequence").received_at_ns.max()
u = u[u.market_slug.str.startswith("highest-temperature-in-")].drop_duplicates(["discovery_sequence", "condition_id"])
u["st"] = u.discovery_sequence.map(snap_t) // 1_000_000                 # ms
ST = np.sort(snap_t.values // 1_000_000)
conds = sorted(c for c in u.condition_id.unique() if int(c, 16) % 4 == SEL)
U = {c: g.set_index("st") for c, g in u[u.condition_id.isin(conds)].groupby("condition_id")}
print("sample markets", len(conds), flush=True)


def load(tag):
    f, b = f"{PF}/flat_{tag}.parquet", f"{PF}/book_{tag}.parquet"
    if not os.path.exists(f):
        return None, None
    t = ds.dataset(f).to_table(columns=["event_type", "ts", "market", "asset_id", "price", "size", "side", "row_ordinal"],
                               filter=ds.field("event_type").isin(["price_change", "last_trade_price"])).to_pandas()
    t = t[t.market.isin(CSET)]
    t["mi"] = t.market.astype(str).map(CI).astype(np.int32)
    t["isno"] = t.asset_id.astype(str).isin(NOS)
    t["buy"] = t.side.values == "BUY"
    t["et"] = (t.event_type.astype(str) == "last_trade_price").astype(np.int8)
    t = t[["et", "ts", "mi", "isno", "buy", "price", "size", "row_ordinal"]]
    bk = pq.read_table(b).to_pandas()
    bk = bk[bk.market.isin(CSET)]
    bk["mi"] = bk.market.map(CI).astype(np.int32); bk["isno"] = bk.asset_id.isin(NOS)
    bk = bk.drop(columns=["market", "asset_id"])
    t["hr"] = HR[tag]; bk["hr"] = HR[tag]
    return t, bk


CSET = set(conds); CI = {c: i for i, c in enumerate(conds)}; NOS = {meta[c]["no"] for c in conds}
tags = WARM + [f"{d}T{h:02d}" for d in DAYS for h in range(24)] + ["2026-10-12T00"]
HR = {t: i for i, t in enumerate(tags)}
FL, BK = [], []
for tg in tags:
    a, b = load(tg)
    if a is not None:
        FL.append(a); BK.append(b)
F = pd.concat(FL, ignore_index=True); B = pd.concat(BK, ignore_index=True)
del FL, BK
print("rows", len(F), "books", len(B), flush=True)
day0 = int(dt.datetime(2026, 10, 7, tzinfo=dt.timezone.utc).timestamp() * 1000)
NMIN = 5 * 1440
INST = day0 + 30_000 * np.arange(2 * NMIN + 1)                    # instants: even = t_m, odd = t_m + 30 s
out = []
Fg = dict(tuple(F.groupby("mi")))
Bg = dict(tuple(B.groupby("mi")))
for n, c in enumerate(conds):
    f = Fg.get(n); b = Bg.get(n)
    if f is None or b is None:
        continue
    # merged event list: kind 0 = book snapshot (index into b), 1 = level change; prints kept apart
    pc = f[f.et == 0]
    tr = f[f.et == 1]
    isno = pc.isno.values
    px = np.rint(pc.price.values * 1000).astype(int)
    lvl = np.where(isno, 1000 - px, px)
    side = np.where(isno, pc.buy.values, ~pc.buy.values).astype(int)   # 0 YES bid, 1 YES ask
    ev = pd.DataFrame({"ts": np.concatenate([b.ts.values, pc.ts.values]), "hr": np.concatenate([b.hr.values, pc.hr.values]),
                       "ro": np.concatenate([b.row_ordinal.values, pc.row_ordinal.values]),
                       "kind": np.r_[np.zeros(len(b), int), np.ones(len(pc), int)],
                       "i": np.r_[np.arange(len(b)), np.arange(len(pc))]}).sort_values(["ts", "hr", "ro"], kind="stable")
    bid = np.zeros(1001); ask = np.zeros(1001); known = False
    SB = np.zeros((len(INST), 1001), np.float32); SA = np.zeros((len(INST), 1001), np.float32); KN = np.zeros(len(INST), bool)
    j = 0
    bts = b.ts.values; bno = b.isno.values
    bpx, bsz, apx, asz = b.bid_px.values, b.bid_sz.values, b.ask_px.values, b.ask_sz.values
    pl, ps, psz = lvl, side, pc["size"].values
    for ts, kind, i in zip(ev.ts.values, ev.kind.values, ev.i.values):
        while j < len(INST) and INST[j] < ts:
            SB[j] = bid; SA[j] = ask; KN[j] = known; j += 1
        if kind == 0:
            bid[:] = 0; ask[:] = 0; known = True
            p1 = np.rint(np.asarray(bpx[i]) * 1000).astype(int); s1 = np.asarray(bsz[i], float)
            p2 = np.rint(np.asarray(apx[i]) * 1000).astype(int); s2 = np.asarray(asz[i], float)
            if bno[i]:
                ask[1000 - p1] = s1; bid[1000 - p2] = s2
            else:
                bid[p1] = s1; ask[p2] = s2
        else:
            L = pl[i]
            if 0 <= L <= 1000:
                (bid if ps[i] == 0 else ask)[L] = psz[i]
    while j < len(INST):
        SB[j] = bid; SA[j] = ask; KN[j] = known; j += 1
    # ---- prints in YES terms
    tno = tr.isno.values
    tpx = np.rint(tr.price.values * 1000)
    ypx = np.where(tno, 1000 - tpx, tpx)
    bside = np.where(tno, tr.buy.values, ~tr.buy.values)
    tts = tr.ts.values.astype(np.int64)
    o = np.argsort(tts, kind="stable"); tts, ypx, bside = tts[o], ypx[o], bside[o]
    # ---- per minute
    g = U[c]
    for m in range(NMIN):
        tm = int(INST[2 * m])
        k = np.searchsorted(ST, tm, side="right") - 1
        if k < 0 or tm - ST[k] > 45 * 60_000 or ST[k] not in g.index:
            continue
        row = g.loc[ST[k]]
        R, msz, v = float(row.daily_reward), float(row.rewards_min_size), float(row.rewards_max_spread_cents) * 10
        Bq, Aq = SB[2 * m], SA[2 * m]
        nzb = np.flatnonzero(Bq > 0); nza = np.flatnonzero(Aq > 0)
        bb = nzb[-1] if len(nzb) else -1; ba = nza[0] if len(nza) else 1001
        valid = bool(KN[2 * m]) and bb >= 1 and ba <= 999 and bb < ba
        rec = dict(cond=c, m=m, R=R, msz=msz, v=v, bb=bb, ba=ba, valid=valid)
        if valid:
            qb, qa = bb, ba
            qz = np.flatnonzero(Bq >= msz); az = np.flatnonzero(Aq >= msz)
            abb = qz[-1] if len(qz) else -1; aba = az[0] if len(az) else 1001
            mid2 = (max(abb, qb) + min(aba, qa)) / 2
            rec["in_both"] = (mid2 - qb < v) and (qa - mid2 < v)
            mb = (max(abb, qb) + aba) / 2
            rec["in_bid"] = aba <= 1000 and 0 <= mb - qb < v
            ma = (abb + min(aba, qa)) / 2
            rec["in_ask"] = abb >= 0 and 0 <= qa - ma < v
            # reward shares at t_m + 30 s
            Bs, As = SB[2 * m + 1], SA[2 * m + 1]
            nzb2 = np.flatnonzero(Bs > 0); nza2 = np.flatnonzero(As > 0)
            vs = bool(KN[2 * m + 1]) and len(nzb2) and len(nza2) and nzb2[-1] < nza2[0] and nzb2[-1] >= 1 and nza2[0] <= 999
            qz2 = np.flatnonzero(Bs >= msz); az2 = np.flatnonzero(As >= msz)
            abb2 = qz2[-1] if len(qz2) else -1; aba2 = az2[0] if len(az2) else 1001
            for nm, lb, la in (("both", 1, 1), ("bid", 1, 0), ("ask", 0, 1)):
                sh = 0.0
                if vs:
                    amb = max(abb2, qb) if lb else abb2; ama = min(aba2, qa) if la else aba2
                    if amb >= 0 and ama <= 1000:
                        mid = (amb + ama) / 2
                        L = np.arange(1001)
                        sbid = mid - L; sask = L - mid
                        okb = (Bs >= msz) & (sbid >= 0) & (sbid < v); oka = (As >= msz) & (sask >= 0) & (sask < v)
                        q1c = float((Bs[okb] * ((v - sbid[okb]) / v) ** 2).sum()); q2c = float((As[oka] * ((v - sask[oka]) / v) ** 2).sum())
                        s_b = mid - qb; s_a = qa - mid
                        q1u = msz * ((v - s_b) / v) ** 2 if (lb and 0 <= s_b < v and qb < ama) else 0.0
                        q2u = msz * ((v - s_a) / v) ** 2 if (la and 0 <= s_a < v and qa > amb) else 0.0
                        inner = 100 <= mid <= 900
                        qu = max(min(q1u, q2u), max(q1u, q2u) / 3) if inner else min(q1u, q2u)
                        cc = min(q1c, q2c) + abs(q1c - q2c) / 3 if inner else min(q1c, q2c)
                        sh = qu / (qu + cc) if qu > 0 else 0.0
                rec["sh_" + nm] = sh
            # first qualifying prints (ms after t_m) for each latency
            for L_ in LAT:
                a0, a1 = np.searchsorted(tts, tm + L_, side="right"), np.searchsorted(tts, tm + 60_000 + L_, side="right")
                P, S_ = ypx[a0:a1], bside[a0:a1]; T = tts[a0:a1] - tm
                for nm, cond_ in (("bP", S_ & (P < qb)), ("bO", S_ & (P <= qb)), ("aP", ~S_ & (P > qa)), ("aO", ~S_ & (P >= qa))):
                    w = np.flatnonzero(cond_)
                    rec[f"{nm}{L_}"] = int(T[w[0]]) if len(w) else -1
        out.append(rec)
    if n % 20 == 0:
        print(n, c[:10], flush=True)
pd.DataFrame(out).to_parquet(f"{OUTD}/min_{SEL}.parquet", index=False)
print("done", len(out))

"""Step 3: rebuild the YES-token book of every reward-universe market on a 30-second grid and derive, per minute,
everything the quoter needs (protocol 4.2-4.5): quote prices for k = 0, 1, 2, band checks, reward shares at the
t_m + 30 s sample for the three liveness cases, and the extreme print prices of each half minute.

usage: python3 -I s3_build.py [first_day last_day]      (default 2026-10-02 2026-10-12; state is carried day to day)
Outputs under data/gaps_weather_rewards/build/: min_<date>.parquet (in-universe market-minutes), mid_<date>.npy
(YES mid at every minute boundary for every market, NaN when the book is not valid), qc_<date>.json.
"""
import datetime as dt, glob, json, os, sys, time
import numpy as np, pandas as pd, pyarrow.parquet as pq

PF = "/home/user/polymarket-lab/data/datasets/pflow_weather"
OUT = "/home/user/polymarket-lab/data/gaps_weather_rewards"
BLD = OUT + "/build"
os.makedirs(BLD, exist_ok=True)
NL = 1001                      # price levels 0.000 .. 1.000 in steps of 0.001
NS = 2880                      # 30-second instants per day; even = minute boundary t_m, odd = t_m + 30 s
KS = (0, 1, 2)

meta = json.load(open(OUT + "/meta.json"))
CONDS = sorted(meta)
CIDX = {c: i for i, c in enumerate(CONDS)}
NO_TOKENS = {v["no"] for v in meta.values()}
uni = pd.read_parquet(OUT + "/universe.parquet")
SNAP_T = np.sort(uni.snap_ns.unique())
uni["si"] = np.searchsorted(SNAP_T, uni.snap_ns.values)
UNI = {c: g.sort_values("si") for c, g in uni.groupby("condition_id")}


def universe_arrays(cond, day0_ms):
    """per minute of the day: in-universe flag, daily rate, minimum size, band (cents) as of t_m."""
    tm_ns = (day0_ms + 60_000 * np.arange(1440, dtype=np.int64)) * 1_000_000
    si = np.searchsorted(SNAP_T, tm_ns, side="right") - 1          # latest snapshot received at or before t_m
    ok = si >= 0
    age_ok = np.zeros(1440, bool)
    age_ok[ok] = (tm_ns[ok] - SNAP_T[si[ok]]) <= 45 * 60 * 1_000_000_000
    R = np.zeros(1440); ms = np.zeros(1440); v = np.zeros(1440); inu = np.zeros(1440, bool)
    g = UNI.get(cond)
    if g is None:
        return inu, R, ms, v
    pos = np.searchsorted(g.si.values, si)
    pos_ok = (pos < len(g)) & age_ok
    hit = np.zeros(1440, bool)
    hit[pos_ok] = g.si.values[pos[pos_ok]] == si[pos_ok]
    inu = hit
    R[hit] = g.daily_reward.values[pos[hit]]
    ms[hit] = g.rewards_min_size.values[pos[hit]]
    v[hit] = g.rewards_max_spread_cents.values[pos[hit]]
    return inu, R, ms, v


def ffill0(M):
    """forward-fill NaN down axis 0 (row 0 is the carry-in)."""
    n = M.shape[0]
    idx = np.where(~np.isnan(M), np.arange(n, dtype=np.int32)[:, None], 0)
    np.maximum.accumulate(idx, axis=0, out=idx)
    return np.take_along_axis(M, idx, axis=0)


def best_bid_idx(mask):   # last True along axis 1, -1 if none
    r = mask[:, ::-1]
    a = r.argmax(axis=1)
    return np.where(r.any(axis=1), NL - 1 - a, -1)


def best_ask_idx(mask):   # first True along axis 1, NL if none
    a = mask.argmax(axis=1)
    return np.where(mask.any(axis=1), a, NL)


OFF = np.arange(0, 47)


def side_score(M, mid, v_idx, msz, bid):
    """sum over qualifying levels strictly inside the band of size * ((v - s)/v)^2; M rows aligned with mid."""
    n = len(mid)
    if bid:
        base = np.floor(mid).astype(np.int64)
        lv = base[:, None] - OFF[None, :]
        s = mid[:, None] - lv
    else:
        base = np.ceil(mid).astype(np.int64)
        lv = base[:, None] + OFF[None, :]
        s = lv - mid[:, None]
    okl = (lv >= 0) & (lv < NL) & (s >= 0) & (s < v_idx[:, None])
    sz = np.take_along_axis(M, np.clip(lv, 0, NL - 1), axis=1)
    okl &= sz >= msz[:, None]
    w = ((v_idx[:, None] - s) / v_idx[:, None]) ** 2
    return np.where(okl, sz * w, 0.0).sum(axis=1)


def shares(B, A, abb, aba, qb, qa, live_b, live_a, v_idx, msz, valid):
    """reward share of our quotes against the book (B, A) for one liveness case; returns (share, share_one_maker, mid)."""
    n = len(qb)
    amb = np.where(live_b, np.maximum(abb, qb), abb).astype(float)
    ama = np.where(live_a, np.minimum(aba, qa), aba).astype(float)
    have = (amb >= 0) & (ama <= NL - 1) & valid & (v_idx > 0)
    mid = np.where(have, (amb + ama) / 2.0, np.nan)
    midz = np.where(have, mid, 500.0)
    vz = np.where(v_idx > 0, v_idx, 1.0)
    q1c = side_score(B, midz, vz, msz, True)
    q2c = side_score(A, midz, vz, msz, False)
    sb = midz - qb; sa = qa - midz
    q1u = np.where(live_b & (sb >= 0) & (sb < vz) & (qb < ama), msz * ((vz - sb) / vz) ** 2, 0.0)
    q2u = np.where(live_a & (sa >= 0) & (sa < vz) & (qa > amb), msz * ((vz - sa) / vz) ** 2, 0.0)
    inner = (midz >= 100.0) & (midz <= 900.0)
    lo_u, hi_u = np.minimum(q1u, q2u), np.maximum(q1u, q2u)
    qu = np.where(inner, np.maximum(lo_u, hi_u / 3.0), lo_u)
    lo_c, hi_c = np.minimum(q1c, q2c), np.maximum(q1c, q2c)
    c_cons = np.where(inner, lo_c + (hi_c - lo_c) / 3.0, lo_c)
    c_one = np.where(inner, np.maximum(lo_c, hi_c / 3.0), lo_c)
    with np.errstate(invalid="ignore", divide="ignore"):
        sh = np.where(have & (qu > 0), qu / (qu + c_cons), 0.0)
        sh1 = np.where(have & (qu > 0), qu / (qu + c_one), 0.0)
    return sh, sh1, mid, c_cons


def process_day(date, state):
    d0 = dt.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    day0 = int(d0.timestamp() * 1000)
    S = day0 + 30_000 * np.arange(NS, dtype=np.int64)
    flats, books = [], []
    ET = {"price_change": 0, "last_trade_price": 1, "tick_size_change": 2}
    for h in range(24):
        f = f"{PF}/flat_{date}T{h:02d}.parquet"
        if os.path.exists(f):
            t = pq.read_table(f, columns=["event_type", "ts", "market", "asset_id", "best_bid", "best_ask", "price", "size", "side",
                                          "new_tick_size", "row_ordinal"]).to_pandas()
            t = t[t.event_type.isin(list(ET))]
            mk = t["market"].astype("category"); ak = t["asset_id"].astype("category")
            mmap = np.array([CIDX.get(c, -1) for c in mk.cat.categories], np.int32)
            amap = np.array([a in NO_TOKENS for a in ak.cat.categories], bool)
            acode = ak.cat.codes.values
            flats.append(pd.DataFrame({
                "et": t.event_type.map(ET).values.astype(np.int8), "ts": t.ts.values.astype(np.int64),
                "ci": mmap[mk.cat.codes.values], "isno": np.where(acode >= 0, amap[np.clip(acode, 0, None)], False),
                "best_bid": t.best_bid.values.astype(np.float32), "best_ask": t.best_ask.values.astype(np.float32),
                "price": t.price.values.astype(np.float32), "size": t["size"].values.astype(np.float32),
                "buy": (t.side.values == "BUY"), "new_tick_size": t.new_tick_size.values.astype(np.float32),
                "row_ordinal": t.row_ordinal.values.astype(np.int64), "hour": np.int8(h)}))
            del t
            b = pq.read_table(f"{PF}/book_{date}T{h:02d}.parquet").to_pandas()
            b["hour"] = h
            b["ci"] = b.market.map(CIDX).fillna(-1).astype(np.int32)
            b["isno"] = b.asset_id.isin(NO_TOKENS)
            books.append(b.drop(columns=["market", "asset_id"]))
    qc = {"date": date, "hours": len(flats), "markets_with_rows": 0, "rows": 0}
    mids = np.full((len(CONDS), 1440), np.nan, np.float32)
    out_rows = []
    if not flats:
        return mids, None, qc
    F = pd.concat(flats, ignore_index=True); del flats
    Bk = pd.concat(books, ignore_index=True); del books
    qc["rows"] = len(F)
    qc["ts_outside_day_pct"] = float(((F.ts < day0 - 3_600_000) | (F.ts >= day0 + 86_400_000 + 3_600_000)).mean() * 100)
    F = F.sort_values("ci", kind="stable")
    cuts = np.flatnonzero(np.diff(F.ci.values)) + 1
    starts = np.concatenate([[0], cuts]); ends = np.concatenate([cuts, [len(F)]])
    fg = {int(F.ci.values[a]): (a, z) for a, z in zip(starts, ends)}
    bg = {int(k): g for k, g in Bk.groupby("ci", sort=False)}
    n_inst = n_valid = n_qc_bad = n_unknown = 0
    live = set(fg) | set(bg) | {CIDX[c] for c, st in state.items() if st["known"]}
    for cond in CONDS:
        inu, R, msz_m, v_m = universe_arrays(cond, day0)
        if CIDX[cond] not in live and not inu.any():
            continue
        st = state.setdefault(cond, {"bid": np.full(NL, np.nan, np.float32), "ask": np.full(NL, np.nan, np.float32), "known": False,
                                     "tick1": False, "rep": None, "last_ts": 0})
        yes, no = meta[cond]["yes"], meta[cond]["no"]
        g = F.iloc[slice(*fg[CIDX[cond]])] if CIDX[cond] in fg else None
        b = bg.get(CIDX[cond])
        MB = np.full((NS + 2, NL), np.nan, np.float32); MA = np.full((NS + 2, NL), np.nan, np.float32)
        MB[0] = st["bid"]; MA[0] = st["ask"]
        # ---- assemble level events in venue order: (ts, book before price_change, hour, row_ordinal)
        ev_ts, ev_cls, ev_hr, ev_ro, ev_side, ev_lvl, ev_sz = [], [], [], [], [], [], []
        first_snap_ts = None
        last_snap_ts = None
        if b is not None and len(b):
            for r in b.itertuples(index=False):
                isno = bool(r.isno)
                bp = np.rint(np.asarray(r.bid_px, float) * 1000).astype(np.int64); bs = np.asarray(r.bid_sz, np.float32)
                ap = np.rint(np.asarray(r.ask_px, float) * 1000).astype(np.int64); az = np.asarray(r.ask_sz, np.float32)
                vb = np.zeros(NL, np.float32); va = np.zeros(NL, np.float32)
                if isno:        # NO bids at q are YES asks at 1 - q; NO asks at q are YES bids at 1 - q
                    va[1000 - bp] = bs; vb[1000 - ap] = az
                else:
                    vb[bp] = bs; va[ap] = az
                for sd, vec in ((0, vb), (1, va)):
                    ev_ts.append(np.full(NL, r.ts, np.int64)); ev_cls.append(np.zeros(NL, np.int8)); ev_hr.append(np.full(NL, r.hour, np.int8))
                    ev_ro.append(np.full(NL, r.row_ordinal, np.int64)); ev_side.append(np.full(NL, sd, np.int8))
                    ev_lvl.append(np.arange(NL, dtype=np.int64)); ev_sz.append(vec)
            first_snap_ts = int(b.ts.min()); last_snap_ts = int(b.ts.max())
        pc = tr = tk = None
        if g is not None:
            qc["markets_with_rows"] += 1
            pc = g[g.et.values == 0]
            tr = g[g.et.values == 1]
            tk = g[g.et.values == 2]
            if len(pc):
                isno = pc.isno.values
                px = np.rint(pc.price.values.astype(np.float64) * 1000).astype(np.int64)
                buy = pc.buy.values
                lvl = np.where(isno, 1000 - px, px)
                sd = np.where(isno, buy, ~buy).astype(np.int8)       # 0 = YES bid side, 1 = YES ask side
                ev_ts.append(pc.ts.values.astype(np.int64)); ev_cls.append(np.ones(len(pc), np.int8)); ev_hr.append(pc.hour.values.astype(np.int8))
                ev_ro.append(pc.row_ordinal.values.astype(np.int64)); ev_side.append(sd); ev_lvl.append(lvl); ev_sz.append(pc["size"].values.astype(np.float32))
        if ev_ts:
            e_ts = np.concatenate(ev_ts); e_cls = np.concatenate(ev_cls); e_hr = np.concatenate(ev_hr); e_ro = np.concatenate(ev_ro)
            e_side = np.concatenate(ev_side); e_lvl = np.concatenate(ev_lvl); e_sz = np.concatenate(ev_sz)
            o = np.lexsort((e_ro, e_hr, e_cls, e_ts))
            e_ts, e_side, e_lvl, e_sz = e_ts[o], e_side[o], e_lvl[o], e_sz[o]
            okl = (e_lvl >= 0) & (e_lvl < NL)
            pos = np.searchsorted(S, e_ts, side="left") + 1          # first instant at or after the row; NS + 1 = end of day
            mb = okl & (e_side == 0); ma = okl & (e_side == 1)
            MB[pos[mb], e_lvl[mb]] = e_sz[mb]
            MA[pos[ma], e_lvl[ma]] = e_sz[ma]
            st["last_ts"] = max(st["last_ts"], int(e_ts.max()))
        MB = ffill0(MB); MA = ffill0(MA)
        known = np.full(NS, st["known"])
        if first_snap_ts is not None:
            known |= S >= first_snap_ts
        Bm = MB[1:NS + 1]; Am = MA[1:NS + 1]
        Bz = np.nan_to_num(Bm, nan=0.0); Az = np.nan_to_num(Am, nan=0.0)
        bb = best_bid_idx(Bz > 0); ba = best_ask_idx(Az > 0)
        # ---- feed-reported best bid / ask (YES terms) from the last price_change row at or before the instant
        rep_ok = np.ones(NS, bool)
        if pc is not None and len(pc):
            isno = pc.isno.values
            pbb = np.rint(pc.best_bid.values.astype(np.float64) * 1000); pba = np.rint(pc.best_ask.values.astype(np.float64) * 1000)
            rb = np.where(isno, 1000 - pba, pbb)
            ra = np.where(isno, 1000 - pbb, pba)
            o2 = np.lexsort((pc.row_ordinal.values, pc.hour.values, pc.ts.values))
            pts = pc.ts.values[o2].astype(np.int64); rb = rb[o2]; ra = ra[o2]
            j = np.searchsorted(pts, S, side="right") - 1
            has = j >= 0
            rbs = np.where(has, rb[np.clip(j, 0, None)], np.nan); ras = np.where(has, ra[np.clip(j, 0, None)], np.nan)
            lts = np.where(has, pts[np.clip(j, 0, None)], -1)
            if st["rep"] is not None:        # carry-in from the previous day
                rbs = np.where(has, rbs, st["rep"][0]); ras = np.where(has, ras, st["rep"][1]); lts = np.where(has, lts, st["rep"][2])
            st["rep"] = (float(rb[-1]), float(ra[-1]), int(pts[-1]))
        elif st["rep"] is not None:
            rbs = np.full(NS, st["rep"][0]); ras = np.full(NS, st["rep"][1]); lts = np.full(NS, st["rep"][2])
        else:
            rbs = np.full(NS, np.nan); ras = np.full(NS, np.nan); lts = np.full(NS, -1)
        # compare only where the last price_change is newer than the last book snapshot at that instant
        if b is not None and len(b):
            bts = np.sort(b.ts.values.astype(np.int64))
            jb = np.searchsorted(bts, S, side="right") - 1
            lsnap = np.where(jb >= 0, bts[np.clip(jb, 0, None)], st.get("snap_ts", -1))
            st["snap_ts"] = int(bts[-1])
        else:
            lsnap = np.full(NS, st.get("snap_ts", -1))
        cmp_ = (lts > lsnap) & ~np.isnan(rbs)
        bbz = np.where(bb < 0, 0, bb); baz = np.where(ba > 1000, 1000, ba)
        rep_ok = ~cmp_ | ((np.nan_to_num(rbs) == bbz) & (np.nan_to_num(ras) == baz))
        valid = known & (bb >= 1) & (ba <= 999) & (bb < ba) & rep_ok
        n_inst += NS; n_valid += int(valid.sum()); n_qc_bad += int((known & ~rep_ok).sum()); n_unknown += int((~known).sum())
        # ---- tick (index units): 1 once a change to 0.001 or an off-grid level has been seen, else 10
        offgrid = ((Bz[:, np.arange(NL) % 10 != 0] > 0).any(axis=1)) | ((Az[:, np.arange(NL) % 10 != 0] > 0).any(axis=1))
        t1 = np.maximum.accumulate(offgrid | st["tick1"])
        if tk is not None and len(tk):
            for r in tk.sort_values("ts").itertuples(index=False):
                if r.new_tick_size == r.new_tick_size and r.new_tick_size < 0.005:
                    t1 |= S >= r.ts
        tick = np.where(t1, 1, 10)
        # ---- carry-out
        st["bid"] = MB[NS + 1].copy(); st["ask"] = MA[NS + 1].copy(); st["known"] = bool(known[-1] or (last_snap_ts is not None))
        st["tick1"] = bool(t1[-1])
        # ---- mids at minute boundaries
        ci = CIDX[cond]
        ev = np.arange(0, NS, 2); od = ev + 1
        mids[ci] = np.where(valid[ev], (bb[ev] + ba[ev]) / 2000.0, np.nan)
        if not inu.any():
            continue
        # ---- prints: extreme prices per half minute (YES terms, index units)
        minbid = np.full(NS, np.inf); maxask = np.full(NS, -np.inf); nprint = np.zeros(NS, np.int32)
        if tr is not None and len(tr):
            isno = tr.isno.values
            px = np.rint(tr.price.values.astype(np.float64) * 1000)
            ypx = np.where(isno, 1000 - px, px)
            buy = tr.buy.values
            bidside = np.where(isno, buy, ~buy)                      # taker sold YES or bought NO
            j = np.ceil((tr.ts.values.astype(np.int64) - day0) / 30_000.0).astype(np.int64) - 1
            okj = (j >= 0) & (j < NS)
            np.minimum.at(minbid, j[okj & bidside], ypx[okj & bidside])
            np.maximum.at(maxask, j[okj & ~bidside], ypx[okj & ~bidside])
            np.add.at(nprint, j[okj], 1)
        # ---- per-minute quantities
        msz = msz_m; v_idx = v_m * 10.0
        mszq = np.where(msz > 0, msz, 1e18)
        abb_q = best_bid_idx(Bz[ev] >= mszq[:, None]); aba_q = best_ask_idx(Az[ev] >= mszq[:, None])
        abb_s = best_bid_idx(Bz[od] >= mszq[:, None]); aba_s = best_ask_idx(Az[od] >= mszq[:, None])
        rec = {"ci": np.full(1440, ci, np.int32), "minute": (day0 // 60_000 + np.arange(1440)).astype(np.int64), "R": R, "msz": msz, "v": v_m,
               "bb": bb[ev], "ba": ba[ev], "tick": tick[ev], "valid_q": valid[ev], "valid_s": valid[od],
               "minbid0": minbid[ev], "minbid1": minbid[od], "maxask0": maxask[ev], "maxask1": maxask[od],
               "nprint": nprint[ev] + nprint[od]}
        T = np.ones(1440, bool); Fz = np.zeros(1440, bool)
        for k in KS:
            qb = (bb[ev] - k * tick[ev]).astype(float); qa = (ba[ev] + k * tick[ev]).astype(float)
            price_ok = valid[ev] & (qb >= tick[ev]) & (qa <= 1000 - tick[ev])
            # band checks at t_m, adjusted midpoint with our live quotes included
            mid2 = (np.maximum(abb_q, qb) + np.minimum(aba_q, qa)) / 2.0
            in_both = price_ok & (mid2 - qb < v_idx) & (qa - mid2 < v_idx) & (v_idx > 0)
            mid_b = (np.maximum(abb_q, qb) + aba_q) / 2.0
            in_bid = price_ok & (aba_q <= NL - 1) & (mid_b - qb < v_idx) & (mid_b - qb >= 0) & (v_idx > 0)
            mid_a = (abb_q + np.minimum(aba_q, qa)) / 2.0
            in_ask = price_ok & (abb_q >= 0) & (qa - mid_a < v_idx) & (qa - mid_a >= 0) & (v_idx > 0)
            vs = valid[od]
            sh_both, sh1_both, _, c_s = shares(Bz[od], Az[od], abb_s, aba_s, qb, qa, T, T, v_idx, msz, vs)
            sh_bid, sh1_bid, _, _ = shares(Bz[od], Az[od], abb_s, aba_s, qb, qa, T, Fz, v_idx, msz, vs)
            sh_ask, sh1_ask, _, _ = shares(Bz[od], Az[od], abb_s, aba_s, qb, qa, Fz, T, v_idx, msz, vs)
            sh0, _, _, c_q = shares(Bz[ev], Az[ev], abb_q, aba_q, qb, qa, T, T, v_idx, msz, valid[ev])
            rec.update({f"qb{k}": qb, f"qa{k}": qa, f"in_both{k}": in_both, f"in_bid{k}": in_bid, f"in_ask{k}": in_ask,
                        f"sh_both{k}": sh_both, f"sh_bid{k}": sh_bid, f"sh_ask{k}": sh_ask,
                        f"sh1_both{k}": sh1_both, f"sh1_bid{k}": sh1_bid, f"sh1_ask{k}": sh1_ask, f"sh0_{k}": sh0, f"comp{k}": c_s})
        df = pd.DataFrame(rec)[inu]
        out_rows.append(df)
    qc.update(instants=n_inst, valid_pct=round(100 * n_valid / max(n_inst, 1), 2), qc_mismatch_pct=round(100 * n_qc_bad / max(n_inst, 1), 2),
              unknown_pct=round(100 * n_unknown / max(n_inst, 1), 2))
    return mids, (pd.concat(out_rows, ignore_index=True) if out_rows else None), qc


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "2026-10-02"
    z = sys.argv[2] if len(sys.argv) > 2 else "2026-10-12"
    d = dt.datetime.strptime(a, "%Y-%m-%d"); end = dt.datetime.strptime(z, "%Y-%m-%d")
    state = {}
    last_ts = {}
    while d <= end:
        date = d.strftime("%Y-%m-%d")
        t0 = time.time()
        mids, rows, qc = process_day(date, state)
        np.save(f"{BLD}/mid_{date}.npy", mids)
        if rows is not None:
            rows.to_parquet(f"{BLD}/min_{date}.parquet", index=False)
            qc["in_universe_minutes"] = len(rows); qc["valid_q_pct_in_universe"] = round(100 * float(rows.valid_q.mean()), 2)
        qc["seconds"] = round(time.time() - t0)
        json.dump(qc, open(f"{BLD}/qc_{date}.json", "w"))
        print(qc, flush=True)
        d += dt.timedelta(days=1)
    json.dump({c: st["last_ts"] for c, st in state.items()}, open(f"{BLD}/last_ts.json", "w"))

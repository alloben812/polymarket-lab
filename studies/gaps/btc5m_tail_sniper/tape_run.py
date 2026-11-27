"""Tape fill rule (protocol 3.5) on FORMATION, OOS-TAPE and OTHER FAMILIES. Writes one ticket table per dataset.

Usage: python3 tape_run.py formation|oos_tape|others
"""
import glob
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUDGET, CAPS, DATA, MIN_SHARES, TAPE_DELAYS, TAPE_WIN, signals  # noqa: E402
from pmlab import px, updown  # noqa: E402
from pmlab.fees import FEE_CHANGE_TS  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
CUR_RATE = {"btc": 0.05, "eth": 0.01, "sol": 0.01, "xrp": 0.01}


def tickets_for_market(t0, dur, sig, mt, side, p, z):
    """sig: [(T, tail, dist, mv, s)], prints arrays (match time, side 'Up'/'Down', price, size) in tape order.
    Returns list of dicts (cap, d, T, tail, shares, stake, attempts, n_sig)."""
    out = []
    ss = [(T, tail) for T, tail, _, _, s in sig if s]
    for cap_name, Z in CAPS.items():
        for d in TAPE_DELAYS:
            att = 0
            for T, tail in ss:
                att += 1
                lo, hi = T + 1 + d, T + 1 + d + TAPE_WIN
                sel = np.where((mt >= lo) & (mt < hi) & (side == tail) & (p <= Z + 1e-9))[0]
                if len(sel) == 0:
                    continue
                rem, sh, st = BUDGET, 0.0, 0.0
                for i in sel:
                    take = min(z[i], rem / p[i])
                    sh += take
                    st += take * p[i]
                    rem -= take * p[i]
                    if rem <= 1e-9:
                        break
                if sh >= MIN_SHARES:
                    out.append({"t0": t0, "cap": cap_name, "d": d, "T": T, "tail": tail, "shares": sh, "stake": st,
                                "attempts": att, "first_mt": int(mt[sel[0]])})
                    break
    return out, len(ss)


def run(markets, asset_of, dur_of, pxs, prints_of, up_won_of, name):
    recs, nsig = [], {}
    t_start = time.time()
    for i, t0 in enumerate(markets):
        dur = dur_of(t0)
        sig = signals(pxs[asset_of(t0)], int(t0), dur)
        pr = prints_of(t0)
        if pr is None:
            continue
        mt, side, p, z = pr
        tk, ns = tickets_for_market(t0, dur, sig, mt, side, p, z)
        nsig[t0] = ns
        uw = up_won_of(t0)
        for r in tk:
            r["hit"] = (r["tail"] == "Up") == uw
            r["asset"], r["dur"] = asset_of(t0), dur
            recs.append(r)
        if i % 1000 == 0:
            print(name, i, len(markets), f"{time.time() - t_start:.0f}s", flush=True)
    t = pd.DataFrame(recs)
    ms = pd.DataFrame({"t0": list(nsig.keys()), "n_sig": list(nsig.values())})
    return t, ms


def formation():
    src = ROOT / "data" / "gaps_btc5m_tails"
    mk = pd.read_parquet(src / "markets_full.parquet")
    empty = mk.rows == 0
    short = mk.volume.notna() & (mk.volume > 0) & (mk.tape_shares / mk.volume.where(mk.volume > 0) < 0.9)
    mk = mk[~empty & ~short & mk.up_won.notna()]
    df = pd.read_parquet(src / "prints_full.parquet", columns=["t0", "bt", "e", "side", "p", "z"])
    df = df[(df.e >= 220) & (df.e < 300) & (df.p <= 0.05 + 1e-9)]
    g = {k: v for k, v in df.groupby("t0")}
    npz = np.load(src / "px_dense.npz")
    dense = npz["p"]
    okm = ~np.isnan(dense)
    P = px.Px(int(npz["t_min"]) + np.nonzero(okm)[0], dense[okm])
    uw = dict(zip(mk.t0, mk.up_won))

    def prints_of(t0):
        v = g.get(t0)
        if v is None:
            return (np.array([]), np.array([]), np.array([]), np.array([]))
        return ((v.bt - 3).to_numpy(), np.where(v.side.to_numpy() == 1, "Up", "Down"), v.p.to_numpy(), v.z.to_numpy())

    t, ms = run(list(mk.t0), lambda t0: "btc", lambda t0: 300, {"btc": P}, prints_of, lambda t0: bool(uw[t0]), "formation")
    if len(t):
        t["rate_cur"] = 0.05
        t["rate_hist"] = np.where(t["T"] >= FEE_CHANGE_TS, 0.05, 0.07)
    return t, ms


def tape_prints(cond):
    rows = updown.tape(cond)
    b = [(mt, o, pp, zz) for mt, o, pp, zz in updown.buyable(rows) if pp <= 0.05 + 1e-9]
    if not b:
        return (np.array([]), np.array([]), np.array([]), np.array([]))
    a = list(zip(*b))
    return (np.array(a[0]), np.array(a[1]), np.array(a[2], dtype=float), np.array(a[3], dtype=float))


def oos_tape():
    st = {}
    for line in (DATA / "fetch_tape_status.jsonl").read_text().splitlines():
        r = json.loads(line)
        st[r["t0"]] = r
    grids = {}
    for t0, r in st.items():
        grids.setdefault((t0 // 300) % 4, []).append(r)
    all_wins = updown.windows("5m", 1787356800, 1788220800)
    complete = []
    for k in (0, 2, 1, 3):
        need = [t for t in all_wins if (t // 300) % 4 == k]
        if all(t in st for t in need):
            complete.append(k)
    print("complete sub-grids", complete, flush=True)
    if not complete:
        complete = [0]
    use = [t for t in all_wins if (t // 300) % 4 in complete and st.get(t, {}).get("ok")]
    meta = {t: updown.load_market("btc", "5m", t) for t in use}
    P = px.Px.load("BTCUSDT", [f"2026-08-{d}" for d in range(21, 32)] + ["2026-09-01"])
    t, ms = run(use, lambda t0: "btc", lambda t0: 300, {"btc": P}, lambda t0: tape_prints(meta[t0]["condition"]),
                lambda t0: bool(meta[t0]["up_won"]), "oos_tape")
    if len(t):
        t["rate_cur"] = 0.05
        t["rate_hist"] = 0.07
    ms["n_markets_used"] = len(use)
    ms.attrs["complete"] = complete
    (DATA / "oos_tape_grids.json").write_text(json.dumps({"complete": complete, "used": len(use), "windows": len(all_wins),
                                                         "status_rows": len(st), "ok": sum(1 for r in st.values() if r.get("ok"))}))
    return t, ms


def others():
    lo, hi = 1795219200, 1795737600  # 2026-11-21 00:00 .. 11-27 00:00
    days = [f"2026-11-{d}" for d in range(20, 27)]
    pxs = {a: px.Px.load(f"{a.upper()}USDT", days, fetch=False) for a in ("btc", "eth", "sol", "xrp")}
    allt, allm = [], []
    for asset, dur in (("btc", "15m"), ("eth", "5m"), ("eth", "15m"), ("sol", "5m"), ("sol", "15m"), ("xrp", "5m"), ("xrp", "15m")):
        meta = {}
        for f in glob.glob(str(ROOT / "data" / "updown_meta" / asset / dur / "*.json")):
            t0 = int(os.path.basename(f)[:-5])
            if lo <= t0 < hi:
                m = json.loads(Path(f).read_text())
                if m.get("up_won") is not None and m.get("condition") and (ROOT / "data" / "tape" / f"{m['condition']}.jsonl.gz").exists():
                    meta[t0] = m
        D = 300 if dur == "5m" else 900
        t, ms = run(sorted(meta), lambda t0, a=asset: a, lambda t0, D=D: D, pxs, lambda t0, meta=meta: tape_prints(meta[t0]["condition"]),
                    lambda t0, meta=meta: bool(meta[t0]["up_won"]), f"{asset}{dur}")
        if len(t):
            t["family"] = f"{asset}{dur}"
            t["rate_cur"] = CUR_RATE[asset]
            t["rate_hist"] = CUR_RATE[asset]
        ms["family"] = f"{asset}{dur}"
        allt.append(t)
        allm.append(ms)
    return pd.concat(allt, ignore_index=True), pd.concat(allm, ignore_index=True)


if __name__ == "__main__":
    which = sys.argv[1]
    t, ms = {"formation": formation, "oos_tape": oos_tape, "others": others}[which]()
    t.to_parquet(DATA / f"tickets_{which}.parquet")
    ms.to_parquet(DATA / f"sigmarkets_{which}.parquet")
    print(which, "tickets", len(t), "markets", len(ms), flush=True)

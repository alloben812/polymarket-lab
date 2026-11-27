"""Audit stage 1: independent rebuild from raw files (gamma meta json, tape jsonl.gz, Binance 1s zips).
No pmlab, no analyst code. Usage: python3 -I a1_build.py <scratch_dir>"""
import gzip, io, json, sys, zipfile
import numpy as np, pandas as pd

ROOT = "/home/user/polymarket-lab"
OUT = sys.argv[1]
BASE = 1795132800            # 2026-11-20 00:00:00 UTC
T_START, T_LAST, T_REPORT = 1795219200, 1795736700, 1795564800
DAYS = ["2026-11-%02d" % d for d in range(20, 27)]
SER = {"eth-5m": ("eth", "5m", 300, "ETHUSDT"), "eth-15m": ("eth", "15m", 900, "ETHUSDT"), "sol-15m": ("sol", "15m", 900, "SOLUSDT"),
       "xrp-15m": ("xrp", "15m", 900, "XRPUSDT"), "btc-15m": ("btc", "15m", 900, "BTCUSDT"), "btc-5m": ("btc", "5m", 300, "BTCUSDT")}


def closes(sym):
    dense = np.full(7 * 86400, np.nan)
    for d in DAYS:
        z = zipfile.ZipFile(f"{ROOT}/data/binance_1s/{sym}-1s-{d}.zip")
        a = np.loadtxt(io.BytesIO(z.read(z.namelist()[0])), delimiter=",", usecols=(0, 4, 6))
        t = a[:, 0]
        assert (t > 1e14).all(), "expected microseconds"
        assert ((a[:, 2] - a[:, 0]) == 999999).all(), "kline is not 1 s open->close"
        sec = (t // 1_000_000).astype(np.int64) - BASE
        assert len(np.unique(sec)) == len(sec)
        dense[sec] = a[:, 1]
    return dense


def grid(c, t0, dur):
    """My own fair value: G[i] for kline-open second s = t0 + i (uses closes up to kline s, i.e. time s + 1)."""
    lc = np.log(c)
    r2 = np.zeros(len(c)); r2[1:] = (lc[1:] - lc[:-1]) ** 2
    Q = np.concatenate([[0.0], np.cumsum(r2)])
    C = np.concatenate([[0.0], np.cumsum(c)])
    i0 = t0 - BASE
    k = (C[i0 + 1] - C[i0 - 59]) / 60.0
    s = np.arange(i0, i0 + dur)
    S = c[s]
    sig = 1.3 * np.sqrt(np.maximum((Q[s + 1] - Q[s - 899]) / 900.0, 1e-18))
    a0 = i0 + dur - 60                       # averaging window = klines a0+1 .. a0+60
    e = s - a0
    r = dur + i0 - s
    pre = s <= a0
    with np.errstate(divide="ignore", invalid="ignore"):
        sofar = (C[s + 1] - C[a0 + 1]) / np.where(e > 0, e, 1)
    mean = np.where(pre, S, (e / 60.0) * sofar + (r / 60.0) * S)
    var = np.where(pre, (sig * S) ** 2 * ((a0 - s) + 20.0), ((r / 60.0) * sig * S) ** 2 * (r / 3.0))
    zscore = (mean - k) / np.sqrt(np.maximum(var, 1e-12))
    from math import erf, sqrt
    G = np.array([0.5 * (1 + erf(x / sqrt(2))) for x in zscore])
    dev = np.abs(mean - k) / k
    twap1 = (C[i0 + dur + 1] - C[i0 + dur - 59]) / 60.0 if i0 + dur + 1 < len(C) else np.nan
    return G, dev, k, twap1


def windows(name):
    asset, d, dur, sym = SER[name]
    g = list(range(T_START, T_LAST + 1, dur))
    if name == "btc-5m":
        n = len(g)
        g = sorted({g[round(i * (n - 1) / 299)] for i in range(300)})
    return g


for name, (asset, d, dur, sym) in SER.items():
    c = closes(sym)
    print(name, "binance seconds", len(c), "missing", int(np.isnan(c).sum()), flush=True)
    mrows, frames, Gs, Ds = [], [], [], []
    for t0 in windows(name):
        try:
            m = json.load(open(f"{ROOT}/data/updown_meta/{asset}/{d}/{t0}.json"))
        except FileNotFoundError:
            mrows.append({"t0": t0, "found": False}); continue
        G, dev, k, tw1 = grid(c, t0, dur)
        rows = [json.loads(l) for l in gzip.open(f"{ROOT}/data/tape/{m['condition']}.jsonl.gz", "rt")]
        df = pd.DataFrame(rows)
        mrows.append({"t0": t0, "found": True, "cond": m["condition"], "up_won": m["up_won"], "ptb": m["price_to_beat"], "final": m["final_price"],
                      "rate": m["fee_rate"], "fee_type": m.get("fee_type"), "lookback": m["twap_lookback"], "volume": m["volume"], "closed": m["closed"],
                      "slug_ok": m["slug"] == f"{asset}-updown-{d}-{t0}", "t1_ok": m["t1"] == t0 + dur,
                      "k_bin": k, "twap1_bin": tw1, "n_rows": len(df), "shares": float(df.z.sum()) if len(df) else 0.0,
                      "sorted": bool((np.diff(df.t.to_numpy()) >= 0).all()) if len(df) > 1 else True,
                      "t_min": int(df.t.min()) if len(df) else -1, "t_max": int(df.t.max()) if len(df) else -1,
                      "dups": int(df.duplicated().sum()) if len(df) else 0})
        if len(df):
            df["t0"] = t0
            frames.append(df)
        Gs.append(G); Ds.append(dev)
    mk = pd.DataFrame(mrows)
    f = pd.concat(frames, ignore_index=True)
    mk.to_parquet(f"{OUT}/{name}_mk.parquet"); f.to_parquet(f"{OUT}/{name}_tape.parquet")
    np.savez_compressed(f"{OUT}/{name}_G.npz", t0=mk[mk.found].t0.to_numpy(), G=np.array(Gs), dev=np.array(Ds))
    print(name, "windows", len(mk), "found", int(mk.found.sum()), "rows", len(f), flush=True)

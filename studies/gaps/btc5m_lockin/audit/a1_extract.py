"""Sceptic's independent extract (does NOT import pmlab or the analyst's code).
Reads raw Binance zips, cached gamma metadata JSON and raw tape .jsonl.gz; writes a pickle in the scratch dir.
"""
import gzip, io, json, math, pickle, sys, zipfile
import numpy as np

ROOT = "/home/user/polymarket-lab"
OUT = sys.argv[1]
START = 1795219200
END = START + 6 * 86400
DAYS = ["2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26"]

# ---------------- Binance 1s klines: col0 open time, col4 close, col6 close time
ot, cl, ct = [], [], []
for d in DAYS:
    z = zipfile.ZipFile(f"{ROOT}/data/binance_1s/BTCUSDT-1s-{d}.zip")
    a = np.loadtxt(io.BytesIO(z.read(z.namelist()[0])), delimiter=",", usecols=(0, 4, 6))
    ot.append(a[:, 0]); cl.append(a[:, 1]); ct.append(a[:, 2])
ot, cl, ct = np.concatenate(ot), np.concatenate(cl), np.concatenate(ct)
unit = 1e6 if ot[0] > 1e14 else 1e3
sec = np.round(ot / unit).astype(np.int64)
print("binance rows", len(sec), "first", sec[0], "last", sec[-1], "unit", unit)
print("  open time on whole seconds:", bool(np.all(ot % unit == 0)), " close-open (s) min/max:", ((ct - ot) / unit).min(), ((ct - ot) / unit).max())
dif = np.diff(sec)
print("  gaps (diff != 1):", int((dif != 1).sum()), "max diff", int(dif.max()), " duplicates:", int((dif == 0).sum()), " expected rows", 7 * 86400)
TMIN = int(sec[0])
P = np.full(int(sec[-1]) - TMIN + 1, np.nan)
P[sec - TMIN] = cl
assert not np.isnan(P).any()
CS = np.concatenate([[0.0], np.cumsum(P)])              # CS[i] = sum P[0..i-1]
LR2 = np.concatenate([[0.0], np.diff(np.log(P)) ** 2])  # LR2[i] = (ln P[i] - ln P[i-1])^2
CQ = np.concatenate([[0.0], np.cumsum(LR2)])            # CQ[i] = sum LR2[0..i-1]


def msum(a, b):  # mean of closes with open time a..b inclusive
    return (CS[b - TMIN + 1] - CS[a - TMIN]) / (b - a + 1)


def model(t, t0):
    """Own implementation of the lock-in model: (P(Up), expected average, K). Uses closes with open time <= t only."""
    t1 = t0 + 300
    K = msum(t0 - 59, t0)
    S = P[t - TMIN]
    sig = 1.3 * math.sqrt((CQ[t - TMIN + 1] - CQ[t - TMIN - 899]) / 900.0)
    ta = t1 - 60
    if t <= ta:
        ea = S
        var = (sig * S) ** 2 * ((ta - t) + 20.0)
    else:
        e, r = t - ta, t1 - t
        ea = e / 60.0 * msum(ta + 1, t) + r / 60.0 * S
        var = (r / 60.0 * sig * S) ** 2 * (r / 3.0)
    x = (ea - K) / math.sqrt(max(var, 1e-12))
    return 0.5 * (1 + math.erf(x / math.sqrt(2))), ea, K


markets, prints, models = [], [], {}
tot_rows = dup_rows = 0
for t0 in range(START, END, 300):
    t1 = t0 + 300
    m = json.load(open(f"{ROOT}/data/updown_meta/btc/5m/{t0}.json"))
    assert m["t0"] == t0 and m["asset"] == "btc" and m["dur"] == "5m" and m["slug"] == f"btc-updown-5m-{t0}"
    rows = [json.loads(l) for l in gzip.open(f"{ROOT}/data/tape/{m['condition']}.jsonl.gz", "rt")]
    keys = [(r["t"], r["s"], r["o"], r["z"], r["p"], r["w"]) for r in rows]
    nd = len(keys) - len(set(keys))
    ts = [r["t"] for r in rows]
    a_bin = msum(t1 - 59, t1) if t1 - TMIN < len(P) else float("nan")
    markets.append(dict(t0=t0, cond=m["condition"], up_won=m["up_won"], ptb=m["price_to_beat"], final=m["final_price"], fee_rate=m["fee_rate"],
                        fee_type=m["fee_type"], volume=m["volume"], closed=m["closed"], n=len(rows), dups=nd, tmin=min(ts), tmax=max(ts),
                        sorted=ts == sorted(ts), shares=sum(r["z"] for r in rows), k_bin=msum(t0 - 59, t0), a_bin=a_bin,
                        sides=len({r["s"] for r in rows} - {"BUY", "SELL"}), outs=len({r["o"] for r in rows} - {"Up", "Down"})))
    tot_rows += len(rows); dup_rows += nd
    for seq, r in enumerate(rows):
        if t1 - 75 <= r["t"] <= t1 + 8:
            prints.append((t0, seq, r["t"], r["s"] == "BUY", r["o"] == "Up", r["p"], r["z"], r["w"]))
    for t in range(t1 - 80, min(t1 + 3, TMIN + len(P))):
        models[(t0, t)] = model(t, t0)
print("markets", len(markets), "tape rows", tot_rows, "exact duplicate rows", dup_rows, "prints kept", len(prints))
pickle.dump(dict(markets=markets, prints=prints, models=models), open(OUT, "wb"))

"""Audit stage 6: (1) do takers who arrive after a quiet spell and trade WITH a recent Binance-driven move earn anything?
(the tape's only window on quotes that sat unhit); (2) one M4 trade recomputed by hand from the raw files.
Usage: python3 -I a6_quiet.py <scratch_dir>"""
import importlib.util, io, json, gzip, math, sys, zipfile
import numpy as np, pandas as pd

S = sys.argv[1]
ROOT = "/home/user/polymarket-lab"
spec = importlib.util.spec_from_file_location("a4", f"{ROOT}/studies/gaps/crypto_lowfee/audit/a4_lib.py"); a4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(a4)
NAMES = ["eth-5m", "eth-15m", "sol-15m", "xrp-15m", "btc-15m", "btc-5m"]
pd.set_option("display.width", 250)

print("== (1) real takers' fills (full size, equivalent-buy form), prints in [t0+15, t1-5] by match = block - 3; f up to m;")
print("   'with' = the bought side's fair value rose >= 0.03 over the previous 10 s, 'against' = fell >= 0.03; quiet = no print in that market for >= 15 s before")
rows = []
for name in NAMES:
    d, G, dev, dur = a4.prints(name, 3)
    f = pd.read_parquet(f"{S}/{name}_tape.parquet")
    d["t"] = f.t.to_numpy()
    prev = d.groupby("t0").t.shift(1)
    # gap to the previous DIFFERENT block second of the same market
    last_other = d.t.where(d.t != prev).groupby(d.t0).ffill()
    sec_prev = d.groupby("t0").t.transform(lambda s: s.where(s != s.shift(1)).ffill())  # first row index time of the current second
    uniq = d.drop_duplicates(["t0", "t"])[["t0", "t"]].copy(); uniq["gap"] = uniq.groupby("t0").t.diff()
    d = d.merge(uniq, on=["t0", "t"], how="left")
    b = d[(d.m >= d.t0 + 15) & (d.m <= d.t0 + dur - 5)].copy()
    now = a4.look(G, b.r.to_numpy(), (b.m - 1 - b.t0).to_numpy(), dur); old = a4.look(G, b.r.to_numpy(), (b.m - 11 - b.t0).to_numpy(), dur)
    b["jump"] = np.where(b.eq_up, now - old, old - now)
    b["net"] = b.z * (b.won - b.q) - b.z * b.rate * b.q * (1 - b.q); b["gross"] = b.z * (b.won - b.q)
    for lab, sel in (("all prints, with", b.jump >= 0.03), ("all prints, against", b.jump <= -0.03), ("quiet>=15s, with", (b.gap >= 15) & (b.jump >= 0.03)),
                     ("quiet>=15s, against", (b.gap >= 15) & (b.jump <= -0.03)), ("quiet>=15s, any", b.gap >= 15), ("quiet>=30s, with", (b.gap >= 30) & (b.jump >= 0.03))):
        x = b[sel]
        if x.t0.nunique() < 5:
            continue
        a = x.groupby("t0")[["net", "gross", "z"]].sum(); r, se, t = a4.rc(a.net, a.z)
        rows.append({"series": name, "cell": lab, "fills": len(x), "mkts": len(a), "shares": round(a.z.sum()), "avg_q": round((x.q * x.z).sum() / x.z.sum(), 3),
                     "gross_c": round(100 * a.gross.sum() / a.z.sum(), 2), "net_c": round(100 * r, 2), "se": round(100 * se, 2), "t": round(t, 2), "net_usd_day": round(a.net.sum() / 6 * (1726 / 300 if name == "btc-5m" else 1))})
print(pd.DataFrame(rows).to_string(index=False))

print("\n== (2) one selected M4 trade by hand (sol-15m D0_thr0.02, reporting period), straight from the raw files")
name = "sol-15m"
d, G, dev, dur = a4.prints(name, 3)
x = a4.capped(a4.m4_sel(d, G, dur, 0, 0.02)); x = x[x.per == "report"]
tr = x.iloc[len(x) // 3]
t0, m = int(tr.t0), int(tr.m)
meta = json.load(open(f"{ROOT}/data/updown_meta/sol/15m/{t0}.json"))
raw = [json.loads(l) for l in gzip.open(f"{ROOT}/data/tape/{meta['condition']}.jsonl.gz", "rt")]
cand = [r for r in raw if r["t"] == m + 3 and abs(r["z"] - tr.z) < 1e-9]
print("tape row(s) at block time", m + 3, ":", cand[:2], "| official:", meta["price_to_beat"], "->", meta["final_price"], "up_won", meta["up_won"], "fee", meta["fee_rate"])
day = pd.Timestamp(t0, unit="s").strftime("%Y-%m-%d")
c = {}
for dd in sorted({pd.Timestamp(t0 - 1000, unit="s").strftime("%Y-%m-%d"), day}):
    z = zipfile.ZipFile(f"{ROOT}/data/binance_1s/SOLUSDT-1s-{dd}.zip")
    for line in z.read(z.namelist()[0]).decode().splitlines():
        p = line.split(","); c[int(p[0]) // 1_000_000] = float(p[4])
s = m - 0 - 1                                 # kline whose close is the last information: closes at s + 1 = m
K = sum(c[i] for i in range(t0 - 59, t0 + 1)) / 60
sig = 1.3 * math.sqrt(sum(math.log(c[i] / c[i - 1]) ** 2 for i in range(s - 899, s + 1)) / 900)
t1 = t0 + 900
if s <= t1 - 60:
    mean, var = c[s], (sig * c[s]) ** 2 * ((t1 - 60 - s) + 20)
else:
    e, r = s - (t1 - 60), t1 - s
    mean = e / 60 * (sum(c[i] for i in range(t1 - 59, s + 1)) / e) + r / 60 * c[s]; var = (r / 60 * sig * c[s]) ** 2 * r / 3
fup = 0.5 * (1 + math.erf((mean - K) / math.sqrt(var) / math.sqrt(2)))
f_side = fup if tr.eq_up else 1 - fup
fee = tr.rate * tr.q * (1 - tr.q)
print("m - t0 = %d s | Binance close at m %.4f, strike (Binance 60 s mean at t0) %.4f, sigma/s %.2e -> P(Up) %.4f | side %s f %.4f, q %.4f, fee/sh %.5f, edge %.4f >= 0.02 | shares %.2f of print %.2f | won %d -> net $ %.4f (script %.4f)" % (
    m - t0, c[s], K, sig, fup, "Up" if tr.eq_up else "Down", f_side, tr.q, fee, f_side - tr.q - fee, tr.sh, tr.z, tr.won, tr.sh * (tr.won - tr.q - fee), tr.net))

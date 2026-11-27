"""Sceptic's data checks + independent reproduction of the descriptive table, basis and headline variants."""
import math, pickle, sys
import numpy as np, pandas as pd

X = pickle.load(open(sys.argv[1], "rb"))
mk = pd.DataFrame(X["markets"]); pr = pd.DataFrame(X["prints"], columns=["t0", "seq", "bt", "is_buy", "o_up", "p", "z", "w"]); MOD = X["models"]
SPLIT = 1795564800; START = 1795219200; RATE = 0.05
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)

print("== DATA ==")
print("markets", len(mk), "closed", int(mk.closed.sum()), "up_won True/False/None", int((mk.up_won == True).sum()), int((mk.up_won == False).sum()), int(mk.up_won.isna().sum()))
print("fee_rate", mk.fee_rate.value_counts(dropna=False).to_dict(), "fee_type", mk.fee_type.value_counts(dropna=False).to_dict())
print("unique conditions", mk.cond.nunique(), " tapes sorted", int(mk.sorted.sum()), " odd sides/outcomes", int(mk.sides.sum()), int(mk.outs.sum()))
print("rows per tape min/median/max", mk.n.min(), mk.n.median(), mk.n.max(), " tapes with n %% 1000 == 0:", int((mk.n % 1000 == 0).sum()))
print("last tape row minus t1 (s): pct 0/1/50/99/100", np.percentile(mk.tmax - (mk.t0 + 300), [0, 1, 50, 99, 100]).tolist(), " first row minus t0: pct 0/50/100", np.percentile(mk.tmin - mk.t0, [0, 50, 100]).tolist())
v = mk.dropna(subset=["volume"])
rel = (v.shares - v.volume).abs() / v.volume
print("gamma volume present", len(v), " |tape shares - volume|/volume < 1e-6:", int((rel < 1e-6).sum()), " mismatches:", v[rel >= 1e-6][["t0", "shares", "volume", "n", "dups"]].to_dict("records"))
print("exact duplicate rows", int(mk.dups.sum()), "of", int(mk.n.sum()), " -> tape share totals match gamma WITH duplicates kept, so they are real repeated fills")
both = mk.dropna(subset=["ptb", "final"])
print("official prices present", len(both), " (final >= ptb) == up_won:", int(((both.final >= both.ptb) == both.up_won.astype(bool)).sum()), " exact ties final == ptb:", int((both.final == both.ptb).sum()),
      " min |final-ptb|:", float((both.final - both.ptb).abs().min()))
print("up share: all %.3f tune %.3f report %.3f" % (mk.up_won.mean(), mk[mk.t0 < SPLIT].up_won.mean(), mk[mk.t0 >= SPLIT].up_won.mean()))

mk["up"] = mk.up_won.astype(bool)
up = dict(zip(mk.t0, mk.up))
pr["t1"] = pr.t0 + 300; pr["up_won"] = pr.t0.map(up)


def rc(num, den):
    n = len(num); D = den.sum(); r = num.sum() / D
    if n < 2: return r, float("nan"), float("nan")
    e = num - r * den; se = math.sqrt(n / (n - 1) * (e ** 2).sum()) / D
    return r, se, r / se if se > 0 else float("nan")


print("\n== DESCRIPTIVE (own extract; taker BUY rows, block-3 in [t1-60, t1)) ==")
d = pr[pr.is_buy & (pr.bt - 3 >= pr.t1 - 60) & (pr.bt - 3 < pr.t1)].copy()
d["win"] = (d.o_up == d.up_won).astype(float); d["fee"] = RATE * d.p * (1 - d.p); d["net"] = d.z * (d.win - d.p - d.fee)
for lo, hi, nm in [(0.5, 0.8, "0.50-0.80"), (0.8, 0.9, "0.80-0.90"), (0.9, 0.95, "0.90-0.95"), (0.95, 0.98, "0.95-0.98"), (0.98, 1.01, "0.98-1.00"), (0.9, 1.01, "0.90-1.00")]:
    out = [nm]
    for a, b in [(0, 10**12), (0, SPLIT), (SPLIT, 10**12)]:
        s = d[(d.p >= lo - 1e-12) & (d.p < hi - 1e-12) & (d.t0 >= a) & (d.t0 < b)]
        g = s.groupby("t0").agg(net=("net", "sum"), z=("z", "sum"))
        r, se, t = rc(g.net.values, g.z.values)
        out.append(f"sh {s.z.sum():,.0f} win {(s.z*s.win).sum()/s.z.sum():.3f} fee {100*(s.z*s.fee).sum()/s.z.sum():.3f}c net {100*r:+.2f}c t {t:+.1f}")
    print("  ", " | ".join(out))
# dedup sensitivity
dd = d.drop_duplicates(subset=["t0", "bt", "o_up", "p", "z", "w"])
s = dd[dd.p >= 0.9 - 1e-12]; g = s.groupby("t0").agg(net=("net", "sum"), z=("z", "sum")); r, se, t = rc(g.net.values, g.z.values)
print(f"   0.90-1.00 with exact duplicate rows removed: sh {s.z.sum():,.0f} net {100*r:+.2f}c t {t:+.1f}")
# by day
s = d[d.p >= 0.9 - 1e-12].assign(day=(d.t0 - START) // 86400 + 21)
for day, x in s.groupby("day"):
    g = x.groupby("t0").agg(net=("net", "sum"), z=("z", "sum")); r, se, t = rc(g.net.values, g.z.values)
    print(f"   0.90-1.00 Nov {day}: markets {len(g)} sh {x.z.sum():,.0f} net {100*r:+.2f}c t {t:+.1f}  net$ {x.net.sum():+,.0f}  worst market $ {g.net.min():+,.0f}")

print("\n== BASIS (own TWAPs; last window lacks the 27 Nov 00:00:00 kline) ==")
bz = mk.dropna(subset=["ptb", "final", "a_bin"]).copy()
bz["err"] = (bz.a_bin - bz.final) - (bz.k_bin - bz.ptb); ab = bz.err.abs()
print("n", len(bz), "mean %.3f sd %.3f" % (bz.err.mean(), bz.err.std()), "abs p50/p95/p99/max", np.round(np.percentile(ab, [50, 95, 99, 100]), 2).tolist(),
      " proxy wrong: %d = %.4f" % (((bz.a_bin >= bz.k_bin) != bz.up).sum(), ((bz.a_bin >= bz.k_bin) != bz.up).mean()))
print("E99 tune-only %.2f report-only %.2f ; windows with |err| > 18.63: tune %d report %d ; > 25: %d ; > 30: %d ; > 40: %d" % (
    np.percentile(ab[bz.t0 < SPLIT], 99), np.percentile(ab[bz.t0 >= SPLIT], 99), (ab[bz.t0 < SPLIT] > 18.63).sum(), (ab[bz.t0 >= SPLIT] > 18.63).sum(), (ab > 25).sum(), (ab > 30).sum(), (ab > 40).sum()))
print("by day sd / p99:", {int(k): (round(v.std(), 2), round(float(np.percentile(v.abs(), 99)), 2)) for k, v in bz.groupby((bz.t0 - START) // 86400 + 21).err})
pickle.dump(dict(mk=mk, pr=pr), open(sys.argv[1] + ".df", "wb"))

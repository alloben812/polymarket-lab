"""T3: what does Vega7 select? Protocol 2.5. Usage: python3 t3.py [full|slice]

Vega7 units: all its BTC 5m BUY fills in the period (grid and off-grid windows). Baseline units: all grid markets with a
buyable tail print in the same price band x seconds band. Descriptive only: no thresholds, no rule.
"""
import json
import math
import sys

import numpy as np
import pandas as pd

from common import DATA, END, MONTHS, OUT, START, TAIL_BANDS, TIME_BANDS, add_money, cell_stats, month_of, tail_band, time_band
from pmlab import fair, px, stats

tag = sys.argv[1] if len(sys.argv) > 1 else "full"
out = OUT / tag
out.mkdir(parents=True, exist_ok=True)
lines = []


def say(s=""):
    print(s)
    lines.append(s)


# ---------- data
df = pd.read_parquet(DATA / f"prints_{tag}.parquet")
mk = pd.read_parquet(DATA / f"markets_{tag}.parquet")
empty = mk.rows == 0
short = mk.volume.notna() & (mk.volume > 0) & (mk.tape_shares / mk.volume.where(mk.volume > 0) < 0.9)
valid = mk[~empty & ~short]
df = df[df.t0.isin(set(valid.t0))]

npz = np.load(DATA / "px_dense.npz")
dense = npz["p"]
okm = ~np.isnan(dense)
P = px.Px(int(npz["t_min"]) + np.nonzero(okm)[0], dense[okm])

fills = json.loads((DATA / "vega7_fills.json").read_text())
meta = {int(r.t0): bool(r.up_won) for r in mk.itertuples()}
mpath = DATA / "vega7_meta.json"
if mpath.exists():
    meta.update({int(k): bool(v["up_won"]) for k, v in json.loads(mpath.read_text()).items()})
rows, no_meta, other = [], 0, 0
for f in fills:
    slug = f.get("slug") or ""
    if not slug.startswith("btc-updown-5m-") or f.get("side") != "BUY":
        other += 1
        continue
    t0 = int(slug.rsplit("-", 1)[1])
    if not (START <= t0 < END):
        other += 1
        continue
    if t0 not in meta:
        no_meta += 1
        continue
    side = 1 if f["outcome"] == "Up" else 0
    rows.append({"t0": t0, "bt": int(f["timestamp"]), "e": int(f["timestamp"]) - 3 - t0, "side": side, "p": round(float(f["price"]), 6),
                 "z": float(f["size"]), "hit": (side == 1) == meta[t0], "role": f.get("role"), "grid": t0 % 1200 == 0})
v = add_money(pd.DataFrame(rows))
v["tb"] = time_band(v.e.to_numpy())
v["band"] = tail_band(v.p.to_numpy())
v.loc[v.p > 0.10, "band"] = ">0.10"
v["month"] = month_of(v.t0.to_numpy())
say("## T3. Vega7 (0x6ba25c9f...) against all tail prints\n")
say(f"Vega7 fills in the period: {len(fills)}; BTC 5m BUY fills with official outcome: {len(v)} (taker {int((v.role == 'T').sum())}, maker {int((v.role == 'M').sum())}); "
    f"not BTC 5m / not BUY / outside period: {other}; no resolved metadata: {no_meta}; markets {v.t0.nunique()}, on the grid {v[v.grid].t0.nunique()}.")
tot = cell_stats(v)
say(f"All its fills: stake ${tot['dollars']:,.0f}, avg price {tot['avg_price']:.4f}, net ${tot['net_dollars']:,.0f}, net {100 * tot['net_ps']:+.3f} c/share (t {tot['t']:+.1f}), "
    f"hit markets {tot['hits']}/{tot['units']}.")
for m in MONTHS:
    c = cell_stats(v[v.month == m])
    if c["prints"]:
        say(f"- {m}: fills {c['prints']}, markets {c['markets']}, stake ${c['dollars']:,.0f}, avg price {c['avg_price']:.4f}, hit markets {c['hits']}/{c['units']}, "
            f"net ${c['net_dollars']:,.0f}, net {100 * c['net_ps']:+.3f} c/share (t {c['t']:+.1f}), return on stake {100 * c['ros']:+.0f}%")

# tape completeness: Vega7's grid fills must be in the tapes
vg = v[v.grid & v.t0.isin(set(valid.t0))]
tp = df[df.v7 & (df.src == 1)]
key_v = set(zip(vg.t0, vg.bt, vg.side, vg.p.round(4), vg.z.round(2)))
key_t = set(zip(tp.t0, tp.bt, tp.side, tp.p.round(4), tp.z.round(2)))
say(f"\nTape check: Vega7 fills in used grid markets {len(vg)} ({vg.z.sum():,.0f} shares); tape rows with Vega7 as taker buyer {len(tp)} ({tp.z.sum():,.0f} shares); "
    f"fills found in the tape by (market, block time, outcome, price, size): {len(key_v & key_t)} of {len(key_v)} distinct.")

say("\n### Vega7's own fills by cell (all its markets)\n")
say("| price | s left | fills | mkts | shares | dollars | hit mkts | avg price | net c/share | t | net $ |")
say("|---|---|---|---|---|---|---|---|---|---|---|")
own = []
for b in [x[0] for x in TAIL_BANDS] + [">0.10"]:
    for tb in ["pre"] + TIME_BANDS:
        c = cell_stats(v[(v.band == b) & (v.tb == tb)])
        if not c["prints"]:
            continue
        own.append({"price": b, "left": tb, **c})
        say(f"| {b} | {tb} | {c['prints']} | {c['markets']} | {c['shares']:,.0f} | {c['dollars']:,.0f} | {c['hits']}/{c['units']} | {c['avg_price']:.4f} | "
            f"{100 * c['net_ps']:+.3f} | {c['t']:+.1f} | {c['net_dollars']:+,.0f} |")
pd.DataFrame(own).to_csv(out / "t3_vega7_cells.csv", index=False)

# ---------- features
def features(pairs: pd.DataFrame) -> pd.DataFrame:
    """pairs: distinct (t0, e). Up-direction features at match time t0 + e."""
    recs = []
    for t0, e in zip(pairs.t0.to_numpy(), pairs.e.to_numpy()):
        t0, e = int(t0), int(e)
        t = t0 + e
        g = fair.gap_in_sigmas(P, t, t0, 300, 60)
        g5 = fair.gap_in_sigmas(P, t, t0 - 5, 300, 60)
        s = P.sigma(t, 300)
        a, b = P.price(t), P.price(t - 30)
        recs.append((t0, e, g, g5, s * math.sqrt(300) * 1e4, (a / b - 1) * 1e4 if a == a and b == b and b > 0 else float("nan")))
    return pd.DataFrame(recs, columns=["t0", "e", "g", "g5", "vol5", "mv_up"])


def with_features(d: pd.DataFrame) -> pd.DataFrame:
    f = features(d[["t0", "e"]].drop_duplicates())
    d = d.merge(f, on=["t0", "e"], how="left")
    sgn = np.where(d.side == 1, 1.0, -1.0)
    d["dist"] = -sgn * d.g      # positive = the tail is behind by that many model sd
    d["dist5"] = -sgn * d.g5
    d["mv30"] = sgn * d.mv_up   # positive = Binance moved the tail's way over the last 30 s
    d["amv30"] = d.mv_up.abs()
    d["hour"] = (d.t0 % 86400) // 3600
    return d


CELL_E = (225, 285)
base = df[(df.p <= 0.05) & (df.e >= CELL_E[0]) & (df.e < CELL_E[1])].copy()
base["band"] = tail_band(base.p.to_numpy())
base["tb"] = time_band(base.e.to_numpy())
base = with_features(add_money(base))
vc = v[(v.p <= 0.05) & (v.e >= CELL_E[0]) & (v.e < CELL_E[1])].copy()
vc = with_features(vc)
say(f"\nBaseline prints in 'price <= 0.05, seconds 225-285': {len(base):,} in {base.t0.nunique():,} grid markets; Vega7 fills there: {len(vc):,} in {vc.t0.nunique():,} markets "
    f"({100 * vc.stake.sum() / v.stake.sum():.0f}% of its dollars).")
FEATS = ["dist", "dist5", "vol5", "mv30", "amv30", "p", "e"]
LABEL = {"dist": "dist (model sd behind)", "dist5": "dist, window shifted 5 s", "vol5": "vol5 (bp per 5 min)", "mv30": "mv30 toward tail (bp)",
         "amv30": "abs mv30 (bp)", "p": "price paid", "e": "second in window"}


def units(d: pd.DataFrame) -> pd.DataFrame:
    agg = {f: (f, "mean") for f in FEATS}
    u = d.groupby(["t0", "side"]).agg(hit=("hit", "first"), n=("z", "size"), z=("z", "sum"), stake=("stake", "sum"), net=("net", "sum"), hour=("hour", "first"), **agg)
    return u.reset_index()


def ranksum_z(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return float("nan")
    x = np.concatenate([a, b])
    r = pd.Series(x).rank().to_numpy()
    u = r[:n1].sum() - n1 * (n1 + 1) / 2
    _, cnt = np.unique(x, return_counts=True)
    n = n1 + n2
    sig = math.sqrt(n1 * n2 / 12 * ((n + 1) - float((cnt.astype(float) ** 3 - cnt).sum()) / (n * (n - 1))))
    return (u - n1 * n2 / 2) / sig if sig > 0 else float("nan")


def two_prop_z(k1, n1, k2, n2) -> float:
    if not n1 or not n2:
        return float("nan")
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (k1 / n1 - k2 / n2) / se if se > 0 else float("nan")


def rate(k, n) -> str:
    if not n:
        return "n/a"
    lo, hi = stats.wilson(int(k), int(n))
    return f"{int(k)}/{int(n)} = {100 * k / n:.2f}% [{100 * lo:.2f}, {100 * hi:.2f}]"


cells = [("<=0.05 x 225-285 (pooled)", lambda d: d)]
for b, _, _ in TAIL_BANDS[:3]:
    for tb in ("75-45", "45-15"):
        cells.append((f"{b} x {tb}", lambda d, b=b, tb=tb: d[(d.band == b) & (d.tb == tb)]))

say("\n### Hit rate: Vega7's markets vs all markets with a tail print in the same cell\n")
say("| cell | Vega7, all its markets | Vega7, grid markets only | baseline: all grid markets with a print | z (Vega7 all vs baseline) | Vega7 net c/share (t) | baseline net c/share (t) | Vega7 avg price | baseline avg price |")
say("|---|---|---|---|---|---|---|---|---|")
hit_rows = []
unit_store = {}
for name, sel in cells:
    dv, db = sel(vc), sel(base)
    uv, ub = units(dv), units(db)
    unit_store[name] = (uv, ub)
    uvg = uv[uv.t0 % 1200 == 0]
    cv, cb = cell_stats(dv), cell_stats(db)
    z = two_prop_z(uv.hit.sum(), len(uv), ub.hit.sum(), len(ub))
    small = " (under 30 Vega7 markets: too small to read)" if len(uv) < 30 else ""
    say(f"| {name}{small} | {rate(uv.hit.sum(), len(uv))} | {rate(uvg.hit.sum(), len(uvg))} | {rate(ub.hit.sum(), len(ub))} | {z:+.2f} | "
        + (f"{100 * cv['net_ps']:+.3f} ({cv['t']:+.1f})" if cv["prints"] else "n/a") + " | "
        + (f"{100 * cb['net_ps']:+.3f} ({cb['t']:+.1f})" if cb["prints"] else "n/a") + " | "
        + (f"{cv['avg_price']:.4f}" if cv["prints"] else "n/a") + " | " + (f"{cb['avg_price']:.4f}" if cb["prints"] else "n/a") + " |")
    hit_rows.append({"cell": name, "v_k": int(uv.hit.sum()), "v_n": len(uv), "vg_k": int(uvg.hit.sum()), "vg_n": len(uvg), "b_k": int(ub.hit.sum()), "b_n": len(ub), "z": z})
pd.DataFrame(hit_rows).to_csv(out / "t3_hit.csv", index=False)

say("\nVega7 in the pooled cell by month: " + "; ".join(
    (lambda c, m: f"{m}: hit markets {c['hits']}/{c['units']}, stake ${c['dollars']:,.0f}, net ${c['net_dollars']:+,.0f}, {100 * c['net_ps']:+.3f} c/share (t {c['t']:+.1f})")(cell_stats(vc[vc.month == m]), m)
    for m in MONTHS if len(vc[vc.month == m])))
say("Baseline in the pooled cell by month (hit markets): " + "; ".join(
    f"{m}: {rate(u.hit.sum(), len(u))}" for m in MONTHS for u in [unit_store[cells[0][0]][1]] for u in [u[month_of(u.t0.to_numpy()) == m]] if len(u)))

sep_rows = []
for name, _ in cells:
    uv, ub = unit_store[name]
    if len(uv) < 30:
        continue
    say(f"\n### Separation in cell {name}: Vega7 units {len(uv)}, baseline units {len(ub)}\n")
    say("| variable | Vega7 mean | Vega7 median | baseline mean | baseline median | std. mean diff | rank-sum z | baseline hit rate by tercile (low / mid / high) | Vega7 hits in the same terciles |")
    say("|---|---|---|---|---|---|---|---|---|")
    for f in FEATS:
        a, b = uv[f].to_numpy(float), ub[f].to_numpy(float)
        a, b = a[~np.isnan(a)], b[~np.isnan(b)]
        smd = (a.mean() - b.mean()) / b.std(ddof=1) if len(a) and len(b) > 1 and b.std(ddof=1) > 0 else float("nan")
        z = ranksum_z(a, b)
        q1, q2 = np.nanquantile(ub[f], [1 / 3, 2 / 3])
        tb_, tv_ = [], []
        for lo, hi in ((-np.inf, q1), (q1, q2), (q2, np.inf)):
            sb = ub[(ub[f] > lo) & (ub[f] <= hi)]
            sv = uv[(uv[f] > lo) & (uv[f] <= hi)]
            tb_.append(f"{int(sb.hit.sum())}/{len(sb)} ({100 * sb.hit.mean():.1f}%)" if len(sb) else "n/a")
            tv_.append(f"{int(sv.hit.sum())}/{len(sv)} ({100 * sv.hit.mean():.1f}%)" if len(sv) else "0/0")
        say(f"| {LABEL[f]} | {a.mean():.3f} | {np.median(a):.3f} | {b.mean():.3f} | {np.median(b):.3f} | {smd:+.2f} | {z:+.1f} | "
            f"{' / '.join(tb_)} (cuts {q1:.3g}, {q2:.3g}) | {' / '.join(tv_)} |")
        sep_rows.append({"cell": name, "feature": f, "v_mean": a.mean(), "v_med": np.median(a), "b_mean": b.mean(), "b_med": np.median(b), "smd": smd, "ranksum_z": z,
                         "v_nan": int(uv[f].isna().sum()), "b_nan": int(ub[f].isna().sum())})
    hb = []
    for lo in (0, 6, 12, 18):
        sb, sv = ub[(ub.hour >= lo) & (ub.hour < lo + 6)], uv[(uv.hour >= lo) & (uv.hour < lo + 6)]
        hb.append(f"{lo:02d}-{lo + 6:02d} UTC: Vega7 {100 * len(sv) / len(uv):.0f}% of units, hits {int(sv.hit.sum())}/{len(sv)}; baseline {100 * len(sb) / len(ub):.0f}%, hits {int(sb.hit.sum())}/{len(sb)}"
                  + (f" ({100 * sb.hit.mean():.1f}%)" if len(sb) else ""))
    say("\nHour of day: " + "; ".join(hb) + ".")
pd.DataFrame(sep_rows).to_csv(out / "t3_separation.csv", index=False)
for name, (uv, ub) in unit_store.items():
    if name.startswith("<=0.05"):
        uv.to_parquet(DATA / f"t3_units_vega7_{tag}.parquet", index=False)
        ub.to_parquet(DATA / f"t3_units_base_{tag}.parquet", index=False)
(out / "t3.md").write_text("\n".join(lines) + "\n")

"""Step 3: descriptive table, basis risk, the rule family. Everything is fixed in protocol.md."""
import itertools
import json

import numpy as np
import pandas as pd

from common import EXTRACT, OUT, RATE, SPLIT
from pmlab import stats

OUT.mkdir(parents=True, exist_ok=True)
lines: list[str] = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    lines.append(s)


mk = pd.read_parquet(EXTRACT / "markets.parquet")
pr = pd.read_parquet(EXTRACT / "prints.parquet")
md = pd.read_parquet(EXTRACT / "model.parquet")
use = mk[mk.usable].copy()
use["up_won"] = use.up_won.astype(bool)
say(f"windows {len(mk)}, usable {len(use)}, unusable: {mk[~mk.usable].why.value_counts().to_dict()}")
say(f"tuning windows usable {int((use.t0 < SPLIT).sum())}, reporting {int((use.t0 >= SPLIT).sum())}")
say(f"fee_rate on metadata: {use.fee_rate.value_counts(dropna=False).to_dict()}")
pr = pr[pr.t0.isin(use.t0)].copy()
pr["t1"] = pr.t0 + 300
pr["up_won"] = pr.t0.map(dict(zip(use.t0, use.up_won))).astype(bool)
PERIODS = {"all": (0, 10**12, 6), "tune": (0, SPLIT, 4), "report": (SPLIT, 10**12, 2)}

# ---------------------------------------------------------------- descriptive table
BUCKETS = [(0.0, 0.50, "<0.50"), (0.50, 0.80, "0.50-0.80"), (0.80, 0.90, "0.80-0.90"), (0.90, 0.95, "0.90-0.95"),
           (0.95, 0.98, "0.95-0.98"), (0.98, 1.0001, "0.98-1.00")]


def describe(df: pd.DataFrame, label: str) -> list[dict]:
    out = []
    df = df.copy()
    df["win"] = (df.o_up == df.up_won).astype(float)
    df["fee"] = RATE * df.p * (1 - df.p)
    df["net"] = df.z * (df.win - df.p - df.fee)
    for lo, hi, name in BUCKETS + [(0.90, 1.0001, "0.90-1.00 (pooled)"), (0.50, 1.0001, "0.50-1.00 (pooled)")]:
        b = df[(df.p >= lo - 1e-12) & (df.p < hi - 1e-12)] if hi < 1 else df[df.p >= lo - 1e-12]
        if b.empty:
            continue
        g = b.groupby("t0").agg(net=("net", "sum"), z=("z", "sum"))
        r, se, t = stats.ratio_cluster(list(g.net), list(g.z))
        sh = b.z.sum()
        out.append({"sample": label, "bucket": name, "prints": len(b), "markets": len(g), "shares": sh,
                    "avg_price": (b.z * b.p).sum() / sh, "win_share_w": (b.z * b.win).sum() / sh, "win_print_w": b.win.mean(),
                    "fee_c": 100 * (b.z * b.fee).sum() / sh, "gross_c": 100 * (b.z * (b.win - b.p)).sum() / sh,
                    "net_c": 100 * r, "se_c": 100 * se, "t": t, "net_usd": b.net.sum()})
    return out


buys = pr[pr.is_buy]
desc = []
for pname, (a, b, _) in PERIODS.items():
    d = buys[(buys.t0 >= a) & (buys.t0 < b)]
    desc += describe(d, f"{pname}, m<t1")
    desc += describe(d[d.m <= d.t1 - 2], f"{pname}, m<=t1-2")
desc = pd.DataFrame(desc)
desc.to_csv(OUT / "descriptive.csv", index=False)
say("\n== Descriptive: taker BUY prints, match time in the last 60 s ==")
with pd.option_context("display.width", 250, "display.max_rows", 200, "display.float_format", "{:.3f}".format):
    say(desc.to_string(index=False))

# ---------------------------------------------------------------- basis risk
bz = mk.dropna(subset=["ptb", "final", "k_bin", "a_bin"]).copy()
bz["err"] = (bz.a_bin - bz.final) - (bz.k_bin - bz.ptb)
bz["abs"] = bz.err.abs()
bz["err_bp"] = bz.err / bz.ptb * 1e4
bz["proxy_up"] = bz.a_bin >= bz.k_bin
bz["off_up"] = bz.final >= bz.ptb
E99 = float(np.percentile(bz["abs"], 99))
_p99 = lambda x: float(np.percentile(x, 99)) if len(x) else float("nan")  # noqa: E731 (empty only in slice mode)
E99_tune = _p99(bz[bz.t0 < SPLIT]["abs"])
E99_rep = _p99(bz[bz.t0 >= SPLIT]["abs"])
say("\n== Basis risk: (Binance end TWAP - final_price) - (Binance start TWAP - price_to_beat), dollars ==")
say(f"n {len(bz)}  mean {bz.err.mean():.3f}  sd {bz.err.std():.3f}  mean BTC price {bz.ptb.mean():.0f}")
say("signed percentiles 1/5/25/50/75/95/99:", np.round(np.percentile(bz.err, [1, 5, 25, 50, 75, 95, 99]), 2).tolist())
say("abs percentiles 50/90/95/99/max:", np.round(np.percentile(bz["abs"], [50, 90, 95, 99, 100]), 2).tolist())
say("abs in bp 50/90/95/99/max:", np.round(np.percentile(bz.err_bp.abs(), [50, 90, 95, 99, 100]), 3).tolist())
say(f"E99 (all windows) = {E99:.2f} USD;  tuning only {E99_tune:.2f};  reporting only {E99_rep:.2f}")
res = bz.dropna(subset=["up_won"])
res_up = res.up_won.astype(bool)
say(f"proxy outcome != official outcome: {int((res.proxy_up != res_up).sum())}/{len(res)} = {(res.proxy_up != res_up).mean():.4f}")
say(f"official prices (final >= ptb) != up_won: {int((res.off_up != res_up).sum())}")
miss = res[res.proxy_up != res_up]
say("|Binance end - start TWAP| in the proxy misses, USD: percentiles 50/90/max",
    np.round(np.percentile((miss.a_bin - miss.k_bin).abs(), [50, 90, 100]), 2).tolist() if len(miss) else None)
say(f"share of windows with |official final - ptb| < E99: {((bz.final - bz.ptb).abs() < E99).mean():.3f}")
bz[["t0", "ptb", "final", "k_bin", "a_bin", "err"]].to_csv(OUT / "basis.csv", index=False)

# ---------------------------------------------------------------- model calibration (diagnostic, addendum)
say("\n== Model calibration per market (diagnostic; favoured side at a fixed model time) ==")
mm = md.merge(use[["t0", "up_won"]], on="t0")
mm["t1"] = mm.t0 + 300
mm["fav_up"] = mm.f_up >= 0.5
mm["f"] = np.where(mm.fav_up, mm.f_up, 1 - mm.f_up)
mm["win"] = mm.fav_up == mm.up_won
mm["far"] = (mm.ea - mm.k).abs() >= E99
cal = []
for back in (45, 30, 15, 5):
    s = mm[mm.t == mm.t1 - back]
    for pname in ("tune", "report"):
        a, b, _ = PERIODS[pname]
        sp = s[(s.t0 >= a) & (s.t0 < b)]
        for floor in (0.97, 0.99):
            for ex in (False, True):
                q = sp[(sp.f >= floor) & (sp.far | (not ex))]
                n, k = len(q), int(q.win.sum())
                lo, hi = stats.wilson(k, n)
                cal.append({"model_time": f"t1-{back}", "period": pname, "floor": floor, "excl": ex, "markets": n,
                            "share_of_markets": n / max(len(sp), 1), "mean_f": q.f.mean(), "win": k / n if n else np.nan,
                            "wilson_lo": lo, "wilson_hi": hi, "losses": n - k})
cal = pd.DataFrame(cal)
cal.to_csv(OUT / "calibration.csv", index=False)
with pd.option_context("display.width", 250, "display.max_rows", 200, "display.float_format", "{:.4f}".format):
    say(cal.to_string(index=False))

# ---------------------------------------------------------------- rule family
proxy_up = dict(zip(mk.t0, mk.a_bin >= mk.k_bin))
merged: dict[int, pd.DataFrame] = {}


def with_model(D: int) -> pd.DataFrame:
    if D not in merged:
        df = pr.copy()
        df["t"] = df.m - D - 1
        df = df.merge(md, on=["t0", "t"], how="left").sort_values(["t0", "seq"]).reset_index(drop=True)
        df["fav_up"] = df.f_up >= 0.5
        df["f"] = np.where(df.fav_up, df.f_up, 1 - df.f_up)
        df["dist"] = (df.ea - df.k).abs()
        merged[D] = df
    return merged[D]


def run(L: int, floor: float, margin: float, D: int, excl: bool) -> pd.DataFrame:
    df = with_model(D)
    ok = (df.m >= df.t1 - L) & (df.m <= df.t1 - 2) & df.f_up.notna() & (df.b_up == df.fav_up) & (df.f >= floor) \
        & (df.bq <= df.f - margin + 1e-9) & (df.bq >= 0.50) & (df.z >= 5)
    if excl:
        ok &= df.dist >= E99
    e = df[ok].copy()
    size = np.zeros(len(e))
    t0s, z = e.t0.values, e.z.values
    cur, rem = None, 0.0
    for i in range(len(e)):
        if t0s[i] != cur:
            cur, rem = t0s[i], 500.0
        if rem < 5:
            continue
        s = min(z[i], 100.0, rem)
        size[i] = s
        rem -= s
    e["size"] = size
    e = e[e["size"] > 0].copy()
    e["win"] = (e.b_up == e.up_won).astype(float)
    e["fee"] = RATE * e.bq * (1 - e.bq)
    e["net"] = e["size"] * (e.win - e.bq - e.fee)
    e["proxy_miss"] = e.t0.map(proxy_up) != e.up_won
    return e


def summarise(e: pd.DataFrame, days: int) -> dict:
    if e.empty:
        return {"trades": 0, "markets": 0, "shares": 0.0}
    e = e.assign(wsz=e.win * e["size"])
    g = e.groupby("t0").agg(net=("net", "sum"), sh=("size", "sum"), wsh=("wsz", "sum"))
    r, se, t = stats.ratio_cluster(list(g.net), list(g.sh))
    n, k = len(e), int(e.win.sum())
    lo, hi = stats.wilson(k, n)
    mw = int((g.wsh >= 0.5 * g.sh).sum())
    mlo, mhi = stats.wilson(mw, len(g))
    sh = e["size"].sum()
    lost = e[e.win == 0]
    return {"trades": n, "markets": len(g), "shares": sh, "avg_price": (e["size"] * e.bq).sum() / sh, "avg_f": (e["size"] * e.f).sum() / sh,
            "win": k / n, "wil_lo": lo, "wil_hi": hi, "mkt_win": mw / len(g), "mkt_lo": mlo, "mkt_hi": mhi,
            "lost_mkts": len(g) - mw, "lost_mkts_proxy_miss": int(lost.groupby("t0").proxy_miss.first().sum()) if len(lost) else 0,
            "fee_c": 100 * (e["size"] * e.fee).sum() / sh, "net_c": 100 * r, "se_c": 100 * se, "t": t,
            "net_usd": e.net.sum(), "usd_day": e.net.sum() / days, "cost_usd": (e["size"] * (e.bq + e.fee)).sum()}


rows, trades = [], []


def do(L, floor, margin, D, excl):
    e = run(L, floor, margin, D, excl)
    name = f"L{L}_f{floor}_m{margin}_D{D}_{'excl' if excl else 'all'}"
    e2 = e[["t0", "seq", "m", "b_up", "bq", "z", "size", "f", "dist", "win", "net", "proxy_miss"]].copy()
    e2["variant"] = name
    trades.append(e2)
    for pname in ("tune", "report"):
        a, b, days = PERIODS[pname]
        rows.append({"variant": name, "L": L, "floor": floor, "margin": margin, "D": D, "excl": excl, "period": pname,
                     **summarise(e[(e.t0 >= a) & (e.t0 < b)], days)})


_w = with_model(1)
nan_prints = int((_w.f_up.isna() & (_w.m <= _w.t1 - 2)).sum())
say(f"\nprints in the last 60 s (m < t1): {len(pr)}; of them m <= t1-2: {int((_w.m <= _w.t1 - 2).sum())}; with model NaN at D=1: {nan_prints}")
TRIPLES = list(itertools.product((60, 30, 15), (0.97, 0.99), (0.02, 0.04, 0.08)))
for L, floor, margin in TRIPLES:
    for excl in (True, False):
        do(L, floor, margin, 1, excl)
res1 = pd.DataFrame(rows)
# ranking on tuning rows only, exclusion ON (protocol item 13)
tune_on = res1[(res1.period == "tune") & res1.excl].copy()
q = tune_on[tune_on.markets >= 30].sort_values("net_c", ascending=False)
rest = tune_on[tune_on.markets < 30].sort_values("markets", ascending=False)
ranked = pd.concat([q, rest])
top3 = [(int(r.L), float(r.floor), float(r.margin)) for r in ranked.head(3).itertuples()]
say("\nranking on the tuning period (exclusion ON, >= 30 traded markets), top 3:", top3)
say(f"triples with >= 30 traded tuning markets: {len(q)} of 18")
for L, floor, margin in top3:
    for excl in (True, False):
        do(L, floor, margin, 2, excl)
res = pd.DataFrame(rows)
res.to_csv(OUT / "variants.csv", index=False)
pd.concat(trades).to_parquet(EXTRACT / "trades_all_variants.parquet")
say(f"\ntotal runs: {res.variant.nunique()}")
cols = ["variant", "trades", "markets", "shares", "avg_price", "win", "wil_lo", "wil_hi", "mkt_win", "mkt_lo", "mkt_hi",
        "lost_mkts", "lost_mkts_proxy_miss", "net_c", "se_c", "t", "net_usd", "usd_day"]
for pname in ("tune", "report"):
    say(f"\n== Rule family, {pname} period ==")
    with pd.option_context("display.width", 300, "display.max_rows", 200, "display.float_format", "{:.3f}".format):
        say(res[res.period == pname][cols].to_string(index=False))
json.dump({"E99": E99, "E99_tune": E99_tune, "E99_report": E99_rep, "top3": top3, "judged": f"L{top3[0][0]}_f{top3[0][1]}_m{top3[0][2]}_D1_excl",
           "runs": int(res.variant.nunique())}, open(OUT / "summary.json", "w"), indent=1)
(OUT / "report.txt").write_text("\n".join(lines) + "\n")

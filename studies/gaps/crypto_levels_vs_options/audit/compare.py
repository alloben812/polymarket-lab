import numpy as np, pandas as pd, math
from pathlib import Path
D = Path("/home/user/polymarket-lab/data/gaps_levels")
E = pd.read_parquet("my_entries.parquet")
A = pd.read_parquet(D / "entries_euro_pa.parquet"); L = pd.read_parquet(D / "l4_euro_pa_all.parquet")
print("analyst entries", len(A), "mine", len(E))
m = E.merge(A, on=["cond", "g", "band", "t", "side"], how="outer", suffixes=("", "_a"), indicator=True)
print(m._merge.value_counts().to_dict())
b = m[m._merge == "both"]
print("max abs diff pe %.2e pnl %.2e gap %.2e model %.2e" % ((b.pe - b.pe_a).abs().max(), (b.pnl - b.pnl_a).abs().max(), (b.gap - b.gap_a).abs().max(), (b.pf - b.model).abs().max()))
k = E.merge(L[["cond", "t", "side", "conf", "size_ok"]].drop_duplicates(), on=["cond", "t", "side"], how="left")
print("confirm agreement (w0 vs analyst):", (k.conf_w0 == k.conf).mean(), "size_ok agreement:", ((k.size_w0 >= k.shares - 1e-9) == k.size_ok).mean())

def rc(num, den):
    n = len(num); den_s = den.sum(); r = num.sum() / den_s
    if n < 2: return r, float("nan"), float("nan")
    resid = num - r * den; se = math.sqrt(n / (n - 1) * (resid ** 2).sum()) / den_s
    return r, se, r / se
def line(e, label, by="cluster"):
    if len(e) == 0: print(f"{label}: 0 entries"); return
    c = e.groupby(by).agg(pnl=("pnl", "sum"), st=("stake", "sum"))
    r, se, t = rc(c.pnl.values, c.st.values)
    print(f"{label}: n {len(e)} mkts {e.cond.nunique()} clus {len(c)} stake {e.stake.sum():.0f} pnl {e.pnl.sum():+.1f} ret {r:+.3f} t {t:+.2f} win {e.won.mean():.2f} pe {e.pe.mean():.2f}")
E["stake"] = 20.0
print("\n== reproduction of the 18 confirmed cells (my code, analyst window (t, t+600]) ==")
for per in ("tune", "report"):
    for g in (0.05, 0.08, 0.12):
        for bn in ("2-12h", "12-48h", "48h-7d"):
            e = E[(E.period == per) & (E.g == g) & (E.band == bn)]
            line(e, f"paper {per} {g} {bn}"); line(e[e.conf_w0], f"  conf {per} {g} {bn}")
E.to_parquet("my_entries.parquet")

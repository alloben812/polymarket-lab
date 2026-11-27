"""Audit diagnostics (post hoc, descriptive, NOT a rule): every signal second with a >=5-share fill at <= cap on the real
book at tau+2 s, hit rate and net by dist / mv bucket; and an 'oracle-free' alternative: best-dist second per market."""
import sys
sys.argv = ["x"]
exec(open("/home/user/polymarket-lab/studies/gaps/btc5m_tail_sniper/audit/a3_tickets.py").read().split("DELAYS = ")[0])
d = 2.0
rows = []
for t0, g in sig.groupby("t0"):
    t0 = int(t0)
    if t0 not in up_won or t0 not in EV: continue
    Ts = list(zip(g["T"], g["tail"], g["dist"], g["mv"]))
    rp = Replay(EV[t0]); st = {}
    for q in sorted({T + 1 + dd for T, *_ in Ts for dd in (0.0, d)}):
        A, B, s = rp.at(q); st[q] = (dict(A), dict(B), s)
    for T, tail, dist, mv in Ts:
        A, B, s = st[T + 1 + d]
        if not s: continue
        for capn, Z in (("1.5c", 0.015), ("5c", 0.05)):
            sh, stk, fee = fill(tail_levels(A, B, tail), Z)
            if sh >= 5:
                rows.append(dict(t0=t0, T=T, cap=capn, tail=tail, dist=dist, mv=mv, shares=sh, stake=stk, fee=fee, hit=(tail == "Up") == up_won[t0]))
x = pd.DataFrame(rows)
x["net"] = x.shares * x.hit - x.stake - x.fee
def line(s, name):
    if len(s) == 0: print(name, "empty"); return
    m = s.groupby("t0").agg(net=("net", "sum"), stake=("stake", "sum"), hit=("hit", "max"))
    print(f"{name:34s} secs={len(s):5d} mkts={len(m):4d} mkts_hit={int(m.hit.sum()):2d} stake={s.stake.sum():8.0f} net={s.net.sum():+8.0f} ret={100*s.net.sum()/s.stake.sum():+6.1f}%")
for capn in ("1.5c", "5c"):
    y = x[x.cap == capn]
    print("==", capn, "all signal seconds with a fill (d=2 s)")
    line(y, "all")
    for lo, hi in ((0, 1), (1, 1.5), (1.5, 2), (2, 2.61)):
        line(y[(y.dist >= lo) & (y.dist < hi)], f"dist [{lo},{hi})")
    for lo, hi in ((0, 1), (1, 2), (2, 4), (4, 99)):
        line(y[(y.mv >= lo) & (y.mv < hi)], f"mv30 [{lo},{hi}) bp toward tail")
    line(y[(y.dist < 1.5) & (y.mv >= 1)], "dist<1.5 & mv>=1bp")
    line(y[(y.dist < 2.0) & (y.mv >= 2)], "dist<2 & mv>=2bp")
print("dist distribution of signal secs with fill, 5c:", x[x.cap == "5c"].dist.describe().round(2).to_dict())
# first-ticket dist
tk = pd.read_parquet(SP + "my_tickets.parquet")
for capn in ("1.5c", "5c"):
    q = tk[(tk.cap == capn) & (tk.d == 2.0)]
    print(capn, "first-ticket dist quantiles", q.dist.quantile([.1, .5, .9]).round(2).tolist(), "mv quantiles", q.mv.quantile([.1, .5, .9]).round(2).tolist())

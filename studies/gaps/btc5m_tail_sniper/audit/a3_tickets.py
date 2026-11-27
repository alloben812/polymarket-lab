"""Independent audit step 3: replay + tickets + stats from the raw L2 events (own code)."""
import pickle, glob, math, bisect
import numpy as np, pandas as pd
R = "/home/user/polymarket-lab/"
SP = "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/"
sig = pd.read_parquet(SP + "my_signals.parquet")
mk = pd.read_parquet(R + "data/gaps_btc5m_tail_sniper/mw/markets.parquet")
mk["t0"] = mk.market_slug.str.rsplit("-", n=1).str[1].astype(int)
mk = mk[(mk.t0 >= 1786665600) & (mk.t0 < 1787356800)]
up_won = {int(a): (b == "yes") for a, b in zip(mk.t0, mk.winning_outcome) if b in ("yes", "no")}
EV, BEST = {}, {}
for f in sorted(glob.glob(SP + "ev_08*.pkl")):
    e, b = pickle.load(open(f, "rb"))
    for k, v in e.items(): EV.setdefault(k, []).extend(v)
    for k, v in b.items(): BEST.setdefault(k, []).append(v)
for k in EV: EV[k].sort(key=lambda x: x[0])
BEST = {k: np.concatenate(v) for k, v in BEST.items()}
BEST = {k: v[np.argsort(v[:, 0], kind="stable")] for k, v in BEST.items()}

class Replay:
    def __init__(self, ev):
        self.ev, self.i, self.A, self.B, self.seen = ev, 0, {}, {}, False
    def at(self, q):   # queries must be non-decreasing
        ev = self.ev
        while self.i < len(ev) and ev[self.i][0] <= q:
            e = ev[self.i]
            if e[1] == "book":
                self.A = {round(p, 4): z for p, z in e[2]}; self.B = {round(p, 4): z for p, z in e[3]}; self.seen = True
            else:
                d = self.A if e[4] == "SELL" else self.B
                if e[3] > 0: d[round(e[2], 4)] = e[3]
                else: d.pop(round(e[2], 4), None)
            self.i += 1
        return self.A, self.B, self.seen

def tail_levels(A, B, tail):
    if tail == "Up": return sorted(A.items())
    return sorted((round(1 - p, 4), z) for p, z in B.items())

def fill(levels, Z, budget=5.0):
    rem, sh, st, fee = budget, 0.0, 0.0, 0.0
    for p, z in levels:
        if p > Z + 1e-9: break
        take = min(z, rem / p)
        sh += take; st += take * p; fee += take * 0.05 * p * (1 - p); rem -= take * p
        if rem <= 1e-9: break
    return sh, st, fee

DELAYS = [0.0, 0.15, 0.5, 1.0, 2.0, 5.0]
tix = []
nobook = 0
for t0, g in sig.groupby("t0"):
    t0 = int(t0)
    if t0 not in up_won or t0 not in EV: continue
    Ts = list(zip(g["T"], g["tail"], g["dist"], g["mv"]))
    qs = sorted({T + 1 + d for T, *_ in Ts for d in DELAYS})
    rp = Replay(EV[t0]); state = {}
    for q in qs:
        A, B, seen = rp.at(q); state[q] = (dict(A), dict(B), seen)
    for capn, Z in (("1.5c", 0.015), ("5c", 0.05)):
        for d in DELAYS:
            for T, tail, dist, mv in Ts:
                A, B, seen = state[T + 1]
                if not seen: nobook += 1; continue
                lv0 = tail_levels(A, B, tail)
                if not any(p <= Z + 1e-9 and z > 0 for p, z in lv0): continue
                A2, B2, seen2 = state[T + 1 + d]
                sh, st, fee = fill(tail_levels(A2, B2, tail), Z)
                if sh >= 5:
                    tix.append(dict(t0=t0, cap=capn, d=d, T=T, tail=tail, dist=dist, mv=mv, shares=sh, stake=st, fee=fee,
                                    hit=(tail == "Up") == up_won[t0]))
                    break
t = pd.DataFrame(tix)
t.to_parquet(SP + "my_tickets.parquet")
print("queries without book:", nobook)
def summ(s):
    n = len(s); k = int(s.hit.sum()); net = s.shares * s.hit - s.stake - s.fee
    be = ((s.stake + s.fee) / s.shares).mean()
    return f"n={n:4d} hits={k:2d} ({100*k/n:.2f}% vs be {100*be:.2f}%) stake={s.stake.sum():8.0f} net={net.sum():+8.0f} ret={100*net.sum()/s.stake.sum():+.0f}%"
for capn in ("1.5c", "5c"):
    for d in DELAYS:
        print(capn, d, summ(t[(t.cap == capn) & (t.d == d)]))
old = pd.read_parquet(R + "data/gaps_btc5m_tail_sniper/tickets_oos_book.parquet")
print(old.columns.tolist())
for capn, cn in (("1.5c", "Z1"), ("5c", "Z2")):
    o = old[(old.cap == cn) & (old.d == 2.0) & (old["shift"] == 0.0)]
    m = t[(t.cap == capn) & (t.d == 2.0)]
    print(capn, "author tickets", len(o), "mine", len(m), "same market+T", len(set(zip(o.t0, o["T"])) & set(zip(m.t0, m["T"]))),
          "share diff max", float(np.abs(o.merge(m, on=["t0", "T"]).eval("shares_x - shares_y")).max()) if len(o) else None)

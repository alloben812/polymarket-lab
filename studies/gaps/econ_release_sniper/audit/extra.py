"""Extra checks: day-clustered bootstrap, de-duplicated tapes, US-only small tickets (the live micro-test scope)."""
import sys, io, contextlib, collections, random, math, time
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/econ_release_sniper/audit")
with contextlib.redirect_stdout(io.StringIO()):
    import recompute as R

def by_day(perT, Ts, days):
    d = collections.defaultdict(float)
    for t in Ts:
        d[time.strftime("%Y-%m-%d", time.gmtime(t))] += perT.get(t, 0.0)
    v = list(d.values()); n = len(v); mu = sum(v) / n
    se = math.sqrt(sum((x - mu) ** 2 for x in v) / (n - 1) / n)
    rnd = random.Random(1)
    bs = sorted(sum(v[rnd.randrange(n)] for _ in range(n)) for _ in range(10000))
    k = 30.4 / days
    return dict(days=n, month=round(sum(v) * k), ci=(round(bs[250] * k), round(bs[9749] * k)), t=round(mu / se, 2))

P = R.cell(R.mech, 1, 50, "S")[0]
print("primary clustered by DAY: all", by_day(P, R.CL, 87), "late", by_day(P, R.LATE, 43))

# de-duplicate exact repeated rows and rerun primary
orig = dict(R.TAPE)
for c, rows in orig.items():
    seen = set(); out = []
    for r in rows:
        if r in seen: continue
        seen.add(r); out.append(r)
    R.TAPE[c] = out
Pd = R.cell(R.mech, 1, 50, "S")[0]
print("primary on de-duplicated tapes: all", round(sum(Pd.values()), 1), "late", round(sum(Pd.get(t, 0) for t in R.LATE), 1))
R.TAPE.update(orig)

US = [m for m in R.mech if m["type"] in R.US and m["type"] not in ("ISM", "UMich")]  # micro-test scope: BLS/BEA + FOMC
UST = sorted({m["T"] for m in US})
for B in (10, 20, 50):
    for a in (1, 3):
        perT, perM, nf, _ = R.cell(US, a, B, "S")
        tot = sum(perT.values())
        late = sum(perT.get(t, 0) for t in UST if t >= R.SPLIT)
        rel_f = sum(1 for t in UST if perT.get(t, 0) > 1e-9)
        print(f"micro-test scope (BLS/BEA+FOMC), a=+{a}s B={B} S: releases {len(UST)}, with fills {rel_f}, filled orders {nf}, "
              f"net all {tot:.1f} (= {tot/87*30.4:.1f}/mo), late {late:.1f} (= {late/43*30.4:.1f}/mo), per release {tot/len(UST):.2f}")
        perT2 = R.cell(US, a, B, "S", skip_first_block=True)[0]
        print(f"      same, behind incumbent: net all {sum(perT2.values()):.1f} (= {sum(perT2.values())/87*30.4:.1f}/mo)")

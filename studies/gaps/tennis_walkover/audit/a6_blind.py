"""Audit step 6: blind version of the causal rule (no signal: buy <= 0.46 for 30 min starting 60 min before the
scheduled start, same cap), outcome-name drops, and the causal follower with the pre-Nov-20 sports rate 0.04."""
import sys, json, gzip, os, math, statistics
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/tennis_walkover/audit")
import a3_rule as R
A = sorted(R.U["A"], key=lambda r: r["closed"]); S = R.U["S"]; K = R.U["k"]
cut = A[int(0.67 * len(A))]["closed"]
def blind(recs, off):
    out = []
    for r in recs:
        res = R.get(r)
        if not res or not res[0] or r["start"] is None: out.append((r["closed"], 0.0, 0.0, False)); continue
        n, c, sh, f = R.rule([(res[0], r["fin"])], [r["start"] - off])
        out.append((r["closed"], n, c, sh > 0))
    return out
for off in (3600, 600):
    ra, rc = blind(A, off), blind(S, off)
    f, l = R.combine(ra, rc), R.combine(ra, rc, cut)
    cost = sum(x[2] for x in ra) + K * sum(x[2] for x in rc)
    print(f"blind start-{off//60}min: ALL net {f[0]:.0f} t {f[1]:.2f} on ${cost:,.0f} spent ({f[0]/cost*100:.1f}%) | REPORT net {l[0]:.0f} t {l[1]:.2f}")
drop = tot = 0
for r in A + S:
    p = R.TD + r["cid"] + ".jsonl.gz"
    if not os.path.exists(p): continue
    for line in gzip.open(p, "rt"):
        tot += 1; drop += json.loads(line)["o"] not in r["out"]
print("tape rows with an outcome name not in the market's outcomes:", drop, "of", tot)
R.FEE = 0.04
for d in (10, 60):
    ra, rc = R.causal_rows(A, d), R.causal_rows(S, d)
    f, l = R.combine(ra, rc), R.combine(ra, rc, cut)
    print(f"causal at fee rate 0.04 d={d}: ALL {f[0]:.0f} t {f[1]:.2f} | REPORT {l[0]:.0f} t {l[1]:.2f}")

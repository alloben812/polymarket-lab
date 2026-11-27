"""Per release: tier, tape move offset (confirm.json), primary net (a=+1,$50,S) and a=+3 $20 S, earliest stale block.
Imports recompute.py (the auditor's own code)."""
import json, sys
sys.argv = ["x"]; sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/econ_release_sniper/audit")
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import recompute as R
conf = json.load(open(R.D + "/confirm.json"))
p1 = R.cell(R.mech, 1, 50, "S")[0]; p3 = R.cell(R.mech, 3, 20, "S")[0]
rows = []
for T in R.CL:
    ms = [m for m in R.kept if m["T"] == T]
    rel = sorted({m["release"] for m in ms})
    st = [r for m in ms if m["flag"] == "" for r in R.stale(m)]
    b0 = min((r[0] for r in st), default=None)
    # winner-buyable vs loser-buyable $ at b 0..6 in mechanical markets (informed direction check)
    wb = sum(r[2] * r[1] for m in ms if m["flag"] == "" for r in R.TAPE[m["cond"]] if 0 <= r[0] <= 6 and r[4] and r[1] < .95)
    lb = sum(r[2] * (1 - r[1]) for m in ms if m["flag"] == "" for r in R.TAPE[m["cond"]] if 0 <= r[0] <= 6 and not r[4] and r[1] > .05)
    rows.append((ms[0]["when"], ",".join(rel), conf[rel[0]]["tier"], conf[rel[0]]["move_off"], b0, round(p1.get(T, 0), 1), round(p3.get(T, 0), 1), round(wb), round(lb)))
print("when | release | tier | tape move offset | first stale block (mech) | primary A1 $50 S | A3 $20 S | winner-buy $ b0-6 | loser-buy $ b0-6")
for r in rows:
    if r[5] or r[6]:
        print(" | ".join(map(str, r)))
tb = sum(r[5] for r in rows if r[2] == "B"); ta = sum(r[5] for r in rows if r[2] == "A")
print("primary by tier: A", round(ta, 1), "B", round(tb, 1))
print("A3 $20 S by tier: A", round(sum(r[6] for r in rows if r[2]=='A'),1), "B", round(sum(r[6] for r in rows if r[2]=='B'),1))

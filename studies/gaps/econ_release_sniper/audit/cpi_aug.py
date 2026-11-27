"""Tape around T for the releases that carry the primary: winner-side prints b in [-40, 8] for mechanical markets."""
import sys, io, contextlib
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/econ_release_sniper/audit")
with contextlib.redirect_stdout(io.StringIO()):
    import recompute as R
for rel in sys.argv[1:]:
    print("==", rel)
    for m in R.mech:
        if m["release"] != rel: continue
        rows = [r for r in R.TAPE[m["cond"]] if -40 <= r[0] <= 8]
        if not rows: continue
        print("  ", m["title"][:30], "winner", m["winner"], " ".join(f"{b:+d}:{wp:.2f}{'W' if tw else 'L'}{z:.0f}" for b, wp, z, w, tw in rows))

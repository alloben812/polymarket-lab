"""POST-HOC, exploratory (not a protocol cell): levels the published claim C2 actually names (pair cost 0.946-0.98,
i.e. 0.47-0.49 per leg) and in-between levels, same rules as recompute.py. 7 extra levels x 2 scenarios."""
import importlib.util, os, sys
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rc", os.path.join(here, "recompute.py")); rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)
rc.LV = [0.49, 0.48, 0.47, 0.46, 0.35, 0.20, 0.10]
out = []
for tag, kw in (("conservative (strictly through), skip on", {}), ("touch (<=), skip on", {"strict": False}),
                ("conservative, NO skip (placed even if ask already <= L: fills as taker at L is NOT modelled; see note)", {"skip": False})):
    res, legs, nm = rc.run(**kw)
    out.append(f"## {tag}")
    for L in rc.LV:
        allv = [x for (s, l), v in res.items() if l == L for x in v]
        m, se, t = rc.cl(allv)
        fl, wl, pps = legs[L]
        by = {}
        for dur in ("5m", "15m", "1h"):
            v = [x for (s, l), vv in res.items() if l == L and s.endswith(dur) for x in vv]
            mm, ss, tt = rc.cl(v); by[dur] = f"{mm:+.2f} (t {tt:+.1f})"
        out.append(f"L={L}: pooled {m:+.3f} (t {t:+.1f}) | 5m {by['5m']} | 15m {by['15m']} | 1h {by['1h']} | legs filled {fl}, win {wl/max(fl,1):.3f}, net/share {pps/max(fl,1):+.4f}")
    print("\n".join(out[-8:]), flush=True)
open(os.path.join(here, "extend_out.txt"), "w").write("\n".join(out) + "\n")

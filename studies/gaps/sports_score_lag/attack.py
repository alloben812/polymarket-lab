"""POST-HOC attack on the soccer trigger-T markout (written after seeing out/report.txt and out/diag.txt).

The protocol's trigger T knows from ESPN that a goal happened (and that it stood: ESPN lists only goals that
counted). A live follower watching only the Polymarket tape does not. Here the trigger is the tape alone, with the
same numbers as trigger T (a print >= 3 c above the median of [t-120, t-10]), in either direction, in-play only
(kickoff to kickoff + 2 h), at most one trigger per market per 300 s. Fill: first buyable print in [t+4, t+34]
(d = 3 plus the 1 s delay), <= 20 USD. Exits: (1) sell at the first sellable print in [t_a+300, t_a+360], two fees;
(2) hold to resolution. Triggers are labelled 'goal' if an ESPN goal wallclock lies in [t-30, t+60], else 'other'."""
from __future__ import annotations

import bisect
import json
import statistics as st
from collections import defaultdict

import analyze as A
from pmlab.fees import fee_per_share
from pmlab.stats import ratio_cluster

games = json.loads((A.DATA / "games.json").read_text())
rows = []
for g in games:
    if g["sport"] != "soccer":
        continue
    period = "early" if g["t0"] < A.SPLIT else "late"
    goals = [e["t"] for e in g["events"]]
    for k, m in g["markets"].items():
        tape = A.load_tape(m["cid"])
        for x in ("Yes", "No"):
            conv = A.convert(tape, x)
            times = [c[0] for c in conv]
            fin = (m.get("final") or {}).get(x)
            last = -10**12
            i0 = bisect.bisect_left(times, g["t0"])
            i1 = bisect.bisect_right(times, g["t0"] + 7200)
            for c in conv[i0:i1]:
                t = c[0]
                if t - last < 300:
                    continue
                pre = A.window(conv, times, t - 120, t - 10)
                if not pre:
                    continue
                pp = st.median(z[1] for z in pre)
                if not (0.05 <= pp <= 0.95) or c[1] < pp + 0.03:
                    continue
                last = t
                ta = t + 3 + int(m.get("delay") or 0)
                fill = next((z for z in A.window(conv, times, ta, ta + 30) if z[2]), None)
                if fill is None:
                    continue
                p = fill[1]
                sh = min(fill[3], A.STAKE / p)
                ex = next((z for z in A.window(conv, times, ta + 300, ta + 360) if not z[2]), None)
                lab = "goal" if any(t - 30 <= gt <= t + 60 for gt in goals) else "other"
                rows.append({"game": g["event"], "period": period, "lab": lab, "sh": sh, "p": p,
                             "rt": None if ex is None else ex[1] - p - fee_per_share(p, A.RATE) - fee_per_share(ex[1], A.RATE),
                             "hold": None if fin is None else fin - p - fee_per_share(p, A.RATE)})

out = []
for lab in ("goal", "other", "all"):
    for per in ("early", "late", "all"):
        tt = [r for r in rows if (lab == "all" or r["lab"] == lab) and (per == "all" or r["period"] == per)]
        line = f"{lab:5s} {per:5s} triggers filled {len(tt):4d} games {len({r['game'] for r in tt}):3d}"
        for meas in ("rt", "hold"):
            num, den = defaultdict(float), defaultdict(float)
            for r in tt:
                if r[meas] is None:
                    continue
                num[r["game"]] += r[meas] * r["sh"]
                den[r["game"]] += r["sh"]
            ks = list(num)
            rr, se, t = ratio_cluster([num[q] for q in ks], [den[q] for q in ks])
            n = sum(1 for r in tt if r[meas] is not None)
            usd = sum(num.values()) / n if n else float("nan")
            line += f" | {meas} {100*rr:.2f} c/sh se {100*se:.2f} t {t:.2f} n {n} (${usd:.3f}/trade)"
        out.append(line)
games_n = len({r["game"] for r in rows})
days = 6
out.append(f"triggers per day (filled): {len(rows)/days:.1f}; goal-labelled {sum(r['lab']=='goal' for r in rows)}, other {sum(r['lab']=='other' for r in rows)}; games {games_n}")
(A.OUT / "attack.txt").write_text("\n".join(out) + "\n")
print("\n".join(out))

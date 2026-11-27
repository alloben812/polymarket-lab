"""Audit extension (POST-HOC, exploratory, not a verdict by itself): does a tape-only follower do better if it only
follows jumps that look like goals (large jump, and a second market of the same match moves at the same time)?
Same fill/exit rules as recompute.py (d=3, taker delay 1 s, first buyable print in 30 s, sell at first bid print
300-360 s later, two fees). Labels 'goal' = an ESPN goal wallclock within [t-30, t+60] (diagnostic only)."""
import bisect, statistics, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from recompute import games, tape, conv, sl, fee, cluster_ratio, SPLIT
from collections import defaultdict

def collect(thr, need_coh, cohthr=0.03, d=3):
    rows = []
    for g in games:
        if g["sport"] != "soccer": continue
        per = "early" if g["t0"] < SPLIT else "late"
        goals = [e["t"] for e in g["events"]]
        tp = {k: tape(m["cid"]) for k, m in g["markets"].items()}
        cy = {k: (conv(tp[k], "Yes")) for k in tp}
        ty = {k: [x[0] for x in cy[k]] for k in tp}
        for k, m in g["markets"].items():
            for tok in ("Yes", "No"):
                c = conv(tp[k], tok); ts = [x[0] for x in c]
                last = -10**12
                for x in c[bisect.bisect_left(ts, g["t0"]):bisect.bisect_right(ts, g["t0"] + 7200)]:
                    t = x[0]
                    if t - last < 300: continue
                    pre = sl(c, ts, t - 120, t - 10)
                    if not pre: continue
                    pp = statistics.median(z[1] for z in pre)
                    if not .05 <= pp <= .95 or x[1] < pp + thr: continue
                    last = t
                    if need_coh:
                        ok = 0
                        for k2 in tp:
                            if k2 == k: continue
                            pr2 = sl(cy[k2], ty[k2], t - 120, t - 10)
                            if not pr2: continue
                            q = statistics.median(z[1] for z in pr2)
                            if any(abs(z[1] - q) >= cohthr for z in sl(cy[k2], ty[k2], t - 10, t + 15)): ok += 1
                        if ok < need_coh: continue
                    ta = t + d + 1
                    fl = next((z for z in sl(c, ts, ta, ta + 30) if z[2]), None)
                    if fl is None: continue
                    p = fl[1]; sh = min(fl[4], 20 / p)
                    ex = next((z for z in sl(c, ts, ta + 300, ta + 360) if z[3]), None)
                    if ex is None: continue
                    lab = "goal" if any(t - 30 <= gt <= t + 60 for gt in goals) else "other"
                    rows.append(dict(g=g["event"], per=per, lab=lab, sh=sh, p=p, rt=ex[1] - p - fee(p) - fee(ex[1])))
    return rows

def rep(label, rows):
    for lab in ("all", "goal", "other"):
        for per in ("early", "late", "all"):
            tt = [r for r in rows if (lab == "all" or r["lab"] == lab) and (per == "all" or r["per"] == per)]
            num, den = defaultdict(float), defaultdict(float)
            for r in tt: num[r["g"]] += r["rt"] * r["sh"]; den[r["g"]] += r["sh"]
            ks = list(num)
            if len(ks) < 3: print(f"{label:28s} {lab:5s} {per:5s} n={len(tt)} (too few games)"); continue
            r, se, t = cluster_ratio([num[k] for k in ks], [den[k] for k in ks])
            print(f"{label:28s} {lab:5s} {per:5s} n={len(tt):4d} games={len(ks):3d} rt {100*r:6.2f} c/sh se {100*se:5.2f} t {t:5.2f}")

if __name__ == "__main__":
    for thr, coh in ((0.03, 0), (0.03, 1), (0.08, 0), (0.08, 1), (0.05, 1)):
        rep(f"tape-only thr {thr} coh>={coh}", collect(thr, coh))

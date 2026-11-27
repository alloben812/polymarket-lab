"""Step 6: descriptive tables for results.md (pooled calibration by family x horizon; weekend split)."""
import collections
import json
import pickle

from pmlab.stats import ratio_cluster
from common import BNAMES, DATA, OUT


def rc(rows, key, side, by="ev"):
    d = collections.defaultdict(lambda: [0.0, 0])
    for r in rows:
        a = d[r[by]]
        a[0] += r[key] if side is None else r[side]
        a[1] += 1
    if len(d) < 2:
        return float("nan"), float("nan"), len(d)
    m, se, t = ratio_cluster([v[0] for v in d.values()], [v[1] for v in d.values()])
    return m, t, len(d)


def fmt(m, t):
    return f"{100*m:+.2f} ({t:+.1f})" if m == m else "-"


def main():
    obs = pickle.load(open(DATA / "obs.pkl", "rb"))
    lines = ["| family | horizon | part | markets | events | mean fav price | fav win rate | gross fav c/sh (t) | net fav c/sh (t) | net long c/sh (t) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    g = collections.defaultdict(list)
    for r in obs:
        g[(r["fam"], r["h"], r["late"])].append(r)
    hord = {"24h": 0, "6h": 1, "1h": 2, "10m": 3}
    for (fam, h, late) in sorted(g, key=lambda k: (k[0], hord[k[1]], k[2])):
        rows = g[(fam, h, late)]
        mg, tg, nev = rc(rows, "gross", None)
        mf, tf, _ = rc(rows, None, "nf")
        ml, tl, _ = rc(rows, None, "nl")
        lines.append(f"| {fam} | {h} | {'late' if late else 'early'} | {len(rows)} | {nev} | {sum(r['pf'] for r in rows)/len(rows):.3f} | "
                     f"{sum(r['wf'] for r in rows)/len(rows):.3f} | {fmt(mg,tg)} | {fmt(mf,tf)} | {fmt(ml,tl)} |")
    open(OUT / "pooled.md", "w").write("\n".join(lines) + "\n")
    # weekend: pooled per family, all horizons, both parts, net fav and net long
    wl = ["| family | weekend obs | weekday obs | net fav weekend (t) | net fav weekday (t) | net long weekend (t) | net long weekday (t) |", "|---|---|---|---|---|---|---|"]
    f2 = collections.defaultdict(list)
    for r in obs:
        f2[r["fam"]].append(r)
    for fam in sorted(f2):
        we = [r for r in f2[fam] if r["wkend"]]
        wd = [r for r in f2[fam] if not r["wkend"]]
        a = rc(we, None, "nf"); b = rc(wd, None, "nf"); c = rc(we, None, "nl"); d = rc(wd, None, "nl")
        wl.append(f"| {fam} | {len(we)} | {len(wd)} | {fmt(a[0],a[1])} | {fmt(b[0],b[1])} | {fmt(c[0],c[1])} | {fmt(d[0],d[1])} |")
    open(OUT / "weekend.md", "w").write("\n".join(wl) + "\n")
    # bucket x horizon gross edge (fav) pooled over families, early/late, for the bias shape
    bl = ["| bucket | horizon | early markets | early gross fav c (t) | late markets | late gross fav c (t) |", "|---|---|---|---|---|---|"]
    g3 = collections.defaultdict(list)
    for r in obs:
        g3[(r["b"], r["h"], r["late"])].append(r)
    for b in range(len(BNAMES)):
        for h in ("24h", "6h", "1h", "10m"):
            e = g3.get((b, h, False), []); l = g3.get((b, h, True), [])
            me = rc(e, "gross", None); ml = rc(l, "gross", None)
            bl.append(f"| {BNAMES[b]} | {h} | {len(e)} | {fmt(me[0],me[1])} | {len(l)} | {fmt(ml[0],ml[1])} |")
    open(OUT / "shape.md", "w").write("\n".join(bl) + "\n")
    print("ok")


if __name__ == "__main__":
    main()

"""Step 7 (descriptive): per-family table pooled over horizons and buckets, early vs late."""
import collections, json, pickle
from pmlab.stats import ratio_cluster
from common import DATA, OUT

obs = pickle.load(open(DATA / "obs.pkl", "rb"))
uni = json.load(open(OUT / "universe.json"))["families"]


def rc(rows, k):
    d = collections.defaultdict(lambda: [0.0, 0])
    for r in rows:
        d[r["ev"]][0] += r[k]; d[r["ev"]][1] += 1
    if len(d) < 2:
        return "-"
    m, se, t = ratio_cluster([v[0] for v in d.values()], [v[1] for v in d.values()])
    return f"{100*m:+.2f} ({t:+.1f})"


g = collections.defaultdict(list)
for r in obs:
    g[r["fam"]].append(r)
L = ["| family | universe/day | weekend share | obs early / late | events early / late | gross fav c early | gross fav c late | net fav c early | net fav c late | net long c early | net long c late |",
     "|---|---|---|---|---|---|---|---|---|---|---|"]
for fam in sorted(g):
    e = [r for r in g[fam] if not r["late"]]; l = [r for r in g[fam] if r["late"]]
    ne = len({r["ev"] for r in e}); nl = len({r["ev"] for r in l})
    L.append(f"| {fam} | {uni[fam]['per_day']} | {uni[fam]['weekend_share']:.2f} | {len(e)} / {len(l)} | {ne} / {nl} | {rc(e,'gross')} | {rc(l,'gross')} | {rc(e,'nf')} | {rc(l,'nf')} | {rc(e,'nl')} | {rc(l,'nl')} |")
open(OUT / "family.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))

"""Step 9: seeded draw of 40 news clusters from the unscheduled main sample (protocol section 8)."""
import csv, json, random
from common import *

def main():
    jumps = json.load(open(OUT / "jumps.json"))
    lab = {(r["c"], int(r["t0"])): r["label"] for r in csv.DictReader(open(OUT / "labels.csv"))}
    um = [j for j in jumps if j["status"] == "main" and lab.get((j["c"], j["t0"])) == "unscheduled"]
    first = {}
    for j in sorted(um, key=lambda j: j["t0"]):
        first.setdefault(j["cluster"], j)
    pool = [first[k] for k in sorted(first)]
    rng = random.Random(20261127)
    pick = pool if len(pool) <= 40 else rng.sample(pool, 40)
    order = {j["cluster"]: k for k, j in enumerate(pick)}   # Amendment 2: draw order kept in a column
    pick.sort(key=lambda j: j["t0"])
    with open(OUT / "news_sample.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["draw", "cluster", "t0", "t0_iso", "dir", "pf_pre", "p10", "slug", "question"])
        for j in pick:
            w.writerow([order[j["cluster"]], j["cluster"], j["t0"], j["t0_iso"], "YES" if j["dir"] > 0 else "NO", j["pf_pre"], j["p10"], j["slug"], j["question"]])
            print(j["cluster"], j["t0_iso"], "YES" if j["dir"] > 0 else "NO", j["pf_pre"], "->", j["p10"], "|", j["question"])
    print("pool", len(pool), "picked", len(pick))

if __name__ == "__main__":
    main()

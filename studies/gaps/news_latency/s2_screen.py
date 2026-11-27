"""Step 2b: screen cached prices-history for candidate jumps (protocol section 2)."""
import gzip, json, bisect
from common import *


def detect(points, max_gap, thr):
    """points sorted (ts, price). Yields (i, j) of the first pair in each run with |dp| >= thr and gap <= max_gap."""
    out = []
    n = len(points)
    j0 = 0
    for i in range(n):
        ti, pi = points[i]
        j = i + 1
        while j < n and points[j][0] - ti <= max_gap:
            if abs(points[j][1] - pi) >= thr:
                out.append((i, j))
                break
            j += 1
    return out


def main():
    u = universe()
    cands = []
    nfile = 0
    for m in u:
        path = PH / f"{m['conditionId']}.json.gz"
        if not path.exists():
            continue
        nfile += 1
        d = json.load(gzip.open(path, "rt"))
        p300 = [tuple(x) for x in d["p300"]]
        p60 = [tuple(x) for x in d["p60"]]
        first300 = p300[0][0] if p300 else 10**12
        p1800 = [tuple(x) for x in d["p1800"] if x[0] < first300]
        det = []
        for (i, j) in detect(p1800, 3600, 0.35):
            det.append((p1800[i][0], p1800[i][1], p1800[j][0], p1800[j][1], 1800))
        for (i, j) in detect(p300, 600, 0.40):
            det.append((p300[i][0], p300[i][1], p300[j][0], p300[j][1], 300))
        for (i, j) in detect(p60, 600, 0.40):
            det.append((p60[i][0], p60[i][1], p60[j][0], p60[j][1], 60))
        det.sort()
        merged = []
        for x in det:
            if merged and x[0] - merged[-1][0] < 7200:   # same episode: keep the earliest start
                merged[-1] = merged[-1][:5] + (max(merged[-1][5], x[0]),)
                # chain: extend the episode end so a long burst stays one candidate
                continue
            merged.append(x + (x[0],))
        # single-linkage on the last detection of the episode
        final = []
        for x in det:
            if final and x[0] - final[-1]["last"] < 7200:
                final[-1]["last"] = x[0]
                continue
            final.append({"c": m["conditionId"], "slug": m["slug"], "T_pre": x[0], "p_pre": x[1], "T_post": x[2], "p_post": x[3],
                          "bucket": x[4], "last": x[0]})
        for f in final:
            if W0 <= f["T_pre"] < W1:
                cands.append(f)
    cands.sort(key=lambda f: f["T_pre"])
    json.dump(cands, open(OUT / "candidates.json", "w"), indent=0)
    import collections
    print("markets with history", nfile, "of", len(u))
    print("candidates", len(cands), "markets", len({c["c"] for c in cands}))
    print("by bucket", collections.Counter(c["bucket"] for c in cands))
    print("by month", collections.Counter(iso(c["T_pre"])[:7] for c in cands))
    print("up/down", collections.Counter("up" if c["p_post"] > c["p_pre"] else "down" for c in cands))


if __name__ == "__main__":
    main()

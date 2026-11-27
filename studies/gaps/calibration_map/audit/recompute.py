"""Independent recomputation of the headline (pooled net buy-favourite, early/late) from raw cached data.
Own parsing of ph.jsonl + sample.jsonl.gz; does not import the study's code (only re-reads the protocol rules)."""
import gzip, json, math, collections, sys
from datetime import datetime, timezone

D = "/home/user/polymarket-lab/data/gaps_calibration_map/"
def T(s):
    if not s: return None
    s = s.strip().replace(" ", "T")
    if s.endswith("Z"): s = s[:-1] + "+00:00"
    if s.endswith("+00"): s += ":00"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()

sample = {}
for l in gzip.open(D + "sample.jsonl.gz", "rt"):
    m = json.loads(l); sample[m["cid"]] = m
ph = {}
for l in open(D + "ph.jsonl"):
    r = json.loads(l); ph[r["cid"]] = r

SPLIT = datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp()
HZ = [86400, 21600, 3600, 600]
def bucket(p):
    edges = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.995000001]
    for i in range(7):
        if edges[i] <= p < edges[i+1]: return i
    return None

def run(stale_extra=0, lag_mode="study"):
    rows = []
    for cid, r in ph.items():
        m = sample.get(cid)
        if not m or "err" in r or not r["pts"]: continue
        b = r["b"]; pts = sorted(r["pts"])
        closed = T(m["closedTime"]) or 9e12; start = T(m["startDate"]) or 0
        for H in HZ:
            if H == 600 and b != 300: continue
            o = m["anchor"] - H
            if not (start <= o < closed): continue
            lag = b if lag_mode == "study" else 0
            cand = [(t, p) for t, p in pts if t <= o - lag]
            if not cand: continue
            t, p0 = cand[-1]
            if t < o - 3 * b: continue
            pf = max(p0, 1 - p0)
            fav = 0 if p0 >= 0.5 else 1
            if pf > 0.995: continue
            w = m["win"][fav]
            s = 0.01 if 0.10 <= pf <= 0.90 else 0.005
            e = pf + s
            net = w - e - m["rate"] * e * (1 - e)
            rows.append(dict(fam=m["fam"], H=H, ev=m.get("event") or cid, late=m["anchor"] >= SPLIT, pf=pf, w=w,
                             net=net, gross=w - pf, tdiff=o - t, b=b, cid=cid, anchor=m["anchor"]))
    return rows

def ratio(rows, key):
    d = collections.defaultdict(lambda: [0.0, 0])
    for r in rows:
        d[r["ev"]][0] += r[key]; d[r["ev"]][1] += 1
    n = len(d); den = sum(v[1] for v in d.values()); num = sum(v[0] for v in d.values())
    mu = num / den
    var = n / (n - 1) * sum((v[0] - mu * v[1]) ** 2 for v in d.values()) / den ** 2
    se = math.sqrt(var)
    return mu * 100, se * 100, mu / se, len(rows), n

if __name__ == "__main__":
    rows = run()
    for late in (False, True):
        part = [r for r in rows if r["late"] == late]
        for k in ("gross", "net"):
            mu, se, t, n, ne = ratio(part, k)
            print("late" if late else "early", k, f"{mu:+.3f}c se {se:.3f} CI [{mu-1.96*se:+.2f},{mu+1.96*se:+.2f}] t {t:+.2f} obs {n} events {ne}")

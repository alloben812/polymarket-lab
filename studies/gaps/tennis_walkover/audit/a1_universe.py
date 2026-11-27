"""Audit step 1: rebuild class A and the control population from raw gamma metadata, independently of s2."""
import gzip, json, datetime as dt, collections, hashlib, math, sys
D = "/home/user/polymarket-lab/data/gaps_tennis_wo/"
P0 = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc).timestamp()
P1 = dt.datetime(2026, 11, 25, 23, 59, 59, tzinfo=dt.timezone.utc).timestamp()

def t(s):
    if not s: return None
    s = str(s).replace(" ", "T").replace("Z", "+00:00")
    if s.endswith("+00"): s += ":00"
    try:
        x = dt.datetime.fromisoformat(s)
    except ValueError:
        try: x = dt.datetime.fromisoformat(s[:19])
        except ValueError: return None
    if x.tzinfo is None: x = x.replace(tzinfo=dt.timezone.utc)
    return x.timestamp()

A, C = [], []
seen_cid = collections.Counter()
nev = 0
for line in gzip.open(D + "events.jsonl.gz", "rt"):
    e = json.loads(line); nev += 1
    ml = [m for m in e["markets"] if m.get("sportsMarketType") == "moneyline"]
    for m in e["markets"]: seen_cid[m["conditionId"]] += 1
    if not ml: continue
    m = ml[0]
    try: pr = [float(x) for x in json.loads(m["outcomePrices"])]
    except Exception: continue
    ct = t(m.get("closedTime"))
    if not ct or not (P0 <= ct <= P1): continue
    st = t(m.get("gameStartTime")) or t(e.get("startTime"))
    rec = dict(slug=e["slug"], cid=m["conditionId"], out=json.loads(m["outcomes"]), fin=pr, closed=ct, start=st,
               vol=m.get("volumeNum"), nml=len(ml))
    if pr == [0.5, 0.5]: A.append(rec)
    elif sorted(pr) == [0.0, 1.0] and m.get("volumeNum") is not None: C.append(rec)
print("events", nev, "classA", len(A), "control pop", len(C), "dup cids", sum(1 for v in seen_cid.values() if v > 1),
      "events with >1 moneyline among A", sum(1 for r in A if r["nml"] > 1))
k = math.ceil(len(C) / 3000)
S = [c for c in C if int(hashlib.sha1(c["cid"].encode()).hexdigest(), 16) % k == 0]
print("k", k, "sample", len(S))
json.dump({"A": A, "C": C, "S": S, "k": k}, open("/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/aud_universe.json", "w"))
U = json.load(open(D + "universe.json"))
a1 = {r["slug"] for r in A}; a2 = {r["slug"] for r in U["A"]}
s1 = {c["cid"] for c in S}; s2 = {c["cid"] for c in U["control"]}
print("A mine-author", len(a1 - a2), "author-mine", len(a2 - a1), "| sample mine-author", len(s1 - s2), "author-mine", len(s2 - s1))

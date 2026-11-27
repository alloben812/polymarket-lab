"""Assign families and pick the fixed sample (protocol.md). No trade or outcome statistic here."""
import gzip, json, glob, hashlib, re, collections, sys
D = "/home/user/polymarket-lab/data/gaps_maker_edge"
K = int(sys.argv[1]) if len(sys.argv) > 1 else 25
FAMS = ["btc-5m", "btc-15m", "alt-updown-5m15m", "crypto-updown-long", "crypto-other", "mentions", "post-counts",
        "sports", "weather", "economics", "finance", "politics", "tech", "culture", "other"]
def fam(r):
    s = r["slug"] or ""; tags = [t or "" for t in r["tags"]]; f0 = r["family0"]
    if s.startswith("btc-updown-5m-"): return "btc-5m"
    if s.startswith("btc-updown-15m-"): return "btc-15m"
    if re.match(r"^[a-z0-9]+-updown-(5m|15m)-\d+$", s): return "alt-updown-5m15m"
    if re.search(r"-updown-", f0) or ("up-or-down" in s and (f0 == "crypto" or any(t in ("crypto", "crypto-prices") for t in tags))): return "crypto-updown-long"
    if f0 == "crypto": return "crypto-other"
    if any("mention" in t for t in tags): return "mentions"
    if "tweet" in s or any("tweet" in t for t in tags) or "-posts-" in s: return "post-counts"
    return f0 if f0 in FAMS else "other"
def resolved(r):
    try: pr = [float(x) for x in json.loads(r["outcomePrices"])]
    except Exception: return None
    if sorted(pr) in ([0.0, 1.0], [0.5, 0.5]): return pr
    return None
rows = []
for p in sorted(glob.glob(f"{D}/universe_2*.jsonl.gz")):
    rows += [json.loads(l) for l in gzip.open(p, "rt")]
seen = set(); uni = []
for r in rows:
    if r["conditionId"] in seen: continue
    seen.add(r["conditionId"]); uni.append(r)
cnt = collections.Counter(); unres = collections.Counter(); sel = []
by = collections.defaultdict(list)
for r in uni:
    f = fam(r); r["family"] = f
    half = "early" if r["endDate"] < "2026-11-24" else "late"
    cnt[(f, half)] += 1
    pr = resolved(r)
    if pr is None: unres[f] += 1; continue
    r["payout"] = pr; r["half"] = half
    by[(f, half)].append(r)
for k in by: by[k].sort(key=lambda r: hashlib.sha1(r["conditionId"].encode()).hexdigest())
for f in FAMS:
    for h in ("early", "late"):
        sel += by[(f, h)][:K]
OUTN = sys.argv[2] if len(sys.argv) > 2 else "sample.json"
json.dump(sel, open(f"{D}/{OUTN}", "w"))
# family market counts (all resolved, for scaling per-day numbers)
famcount = {f"{f}|{h}": len(by[(f, h)]) for f in FAMS for h in ("early", "late")}
json.dump({"universe_rows": len(uni), "counts_all": {f"{a}|{b}": c for (a, b), c in cnt.items()}, "resolved": famcount, "unresolved": dict(unres)}, open(f"{D}/universe_counts.json", "w"), indent=1)
print("universe", len(uni), "sample", len(sel))
for f in FAMS: print(f"{f:20s} early {len(by[(f,'early')]):6d} late {len(by[(f,'late')]):6d} unresolved {unres[f]}")

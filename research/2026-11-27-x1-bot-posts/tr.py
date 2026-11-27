import json, sys, time, urllib.request, collections, re, datetime as dt
DATA="https://data-api.polymarket.com/v2"
def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}), timeout=60) as r: return json.loads(r.read())
        except Exception as e: err=e; time.sleep(1.5*(i+1))
    return {"_err":str(err)}
first=True
for arg in sys.argv[1:]:
    label,w=arg.split("=")
    full=get(f"{DATA}/trades?user={w}&limit=1000&taker_only=false")
    tak=get(f"{DATA}/trades?user={w}&limit=1000")
    rows=full.get("data") or full.get("trades") or (full if isinstance(full,list) else [])
    trows=tak.get("data") or tak.get("trades") or (tak if isinstance(tak,list) else [])
    if first and rows:
        print("KEYS", sorted(rows[0].keys())); print("SAMPLE", json.dumps(rows[0])[:700]); first=False
    if not rows: print(label, "no rows", str(full)[:200]); continue
    def slugfam(r):
        s=r.get("slug") or r.get("market_slug") or r.get("event_slug") or r.get("title") or "?"
        s=re.sub(r"\d{9,}","#",s); s=re.sub(r"20\d\d-\d\d-\d\d","DATE",s); s=re.sub(r"\d+","N",s)
        return s[:38]
    fam=collections.Counter(slugfam(r) for r in rows)
    side=collections.Counter((r.get("side") or "?") for r in rows)
    px=[float(r.get("price") or 0) for r in rows]; sz=[float(r.get("size") or 0) for r in rows]
    usd=[p*s for p,s in zip(px,sz)]
    b=collections.Counter()
    for p,u in zip(px,usd):
        k="<=0.03" if p<=0.03 else "0.03-0.2" if p<0.2 else "0.2-0.8" if p<0.8 else "0.8-0.97" if p<0.97 else ">=0.97"
        b[k]+=u
    tot=sum(usd) or 1
    ts=[r.get("timestamp") or 0 for r in rows]
    span=(max(ts)-min(ts))/3600 if ts else 0
    # maker share: rows in full not in taker within overlapping time span
    tmin=max(min(ts), min([r.get("timestamp") or 0 for r in trows]) if trows else 0)
    nf=sum(1 for r in rows if (r.get("timestamp") or 0)>=tmin); nt=sum(1 for r in trows if (r.get("timestamp") or 0)>=tmin)
    print(f"\n## {label}: {len(rows)} fills over {span:.1f}h (latest {dt.datetime.fromtimestamp(max(ts), dt.timezone.utc):%m-%d %H:%M}); side {dict(side)}; avg fill ${tot/len(rows):.1f}; taker-share of fills in overlap ~{nt/nf*100 if nf else 0:.0f}% ({nt}/{nf})")
    print("   usd by price: " + ", ".join(f"{k} {v/tot*100:.0f}%" for k,v in sorted(b.items())))
    print("   top markets: " + "; ".join(f"{k} x{v}" for k,v in fam.most_common(6)))
    time.sleep(0.3)

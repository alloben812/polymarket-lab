import json, sys, time, urllib.request, urllib.parse
def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}), timeout=40) as r: return json.loads(r.read())
        except Exception as e: time.sleep(1.5*(i+1))
    return {}
for ref in sys.argv[1:]:
    if ref.lower().startswith("0x") and len(ref)>=42:
        print(f"{ref[:10]}={ref[:42].lower()}"); continue
    d=get("https://gamma-api.polymarket.com/public-search?"+urllib.parse.urlencode({"q":ref,"search_profiles":"true","limit_per_type":10}))
    profs=[p for p in (d.get("profiles") or []) if p]
    exact=[p for p in profs if (p.get("name") or "").lower()==ref.lower()]
    if exact: print(f"{exact[0]['name']}={exact[0]['proxyWallet']}")
    else: sys.stderr.write(f"UNRESOLVED {ref}: candidates {[p.get('name') for p in profs][:5]}\n")
    time.sleep(0.2)

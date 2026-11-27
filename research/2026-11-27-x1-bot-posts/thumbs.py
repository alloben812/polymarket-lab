import json, sys, re, subprocess, os
path, outdir = sys.argv[1], sys.argv[2]
rows = [json.loads(l) for l in open(path)]
rows.sort(key=lambda s: s.get("created_timestamp") or 0)
for s in rows:
    text = s.get("text") or ""
    if not re.search(r"polymarket|up/down|up or down|“up or down”", text.lower()): continue
    for i, m in enumerate(((s.get("media") or {}).get("all") or [])):
        u = m.get("thumbnail_url") or (m.get("url") if m.get("type")=="photo" else None)
        if not u: continue
        fn = os.path.join(outdir, f"{s['created_at'][4:10].replace(' ','')}_{s['id']}_{i}.jpg")
        if os.path.exists(fn) and os.path.getsize(fn)>1000: continue
        subprocess.run(["curl","-sS","-L","--max-time","40","-o",fn,u])
        print(fn, os.path.getsize(fn) if os.path.exists(fn) else None)

import json,glob,sys
seen={}
for f in glob.glob(sys.argv[1]):
    try: d=json.load(open(f))
    except Exception as e: continue
    items = (d.get('results') or d.get('posts') or []) if isinstance(d, dict) else d
    if not isinstance(items, list): continue
    for p in items:
        if not isinstance(p, dict): continue
        u=p.get('canonical_url'); 
        if u in seen: continue
        seen[u]=(p.get('post_date','')[:10], p.get('wordcount'), p.get('audience'), (p.get('publishedBylines') or [{}])[0].get('name'), p.get('title','')[:100], (p.get('reactions') or {}).get('❤'))
for u,v in sorted(seen.items(), key=lambda x:x[1][0], reverse=True): print(*v, u, sep=' | ')

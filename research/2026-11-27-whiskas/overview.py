import json,sys,collections,re,datetime as dt
rows=[json.loads(l) for l in open(sys.argv[1])]
print("rows",len(rows), "from", dt.datetime.utcfromtimestamp(min(r['timestamp'] for r in rows)), "to", dt.datetime.utcfromtimestamp(max(r['timestamp'] for r in rows)))
def fam(slug):
    m=re.match(r'([a-z0-9]+)-updown-(\d+[mh])-(\d+)$',slug or '')
    return (m.group(1)+'-'+m.group(2)) if m else re.sub(r'-\d{6,}.*$','',slug or '?')[:40]
agg=collections.defaultdict(lambda: collections.defaultdict(float))
for r in rows:
    k=(fam(r['slug']), r['role'], r['side'])
    a=agg[k]; a['n']+=1; a['sh']+=r['size']; a['usd']+=r['size']*r['price']; a['w']+=r['size']*r['price']*(1-r['price'])
tot_usd=sum(a['usd'] for a in agg.values())
print(f"{'family':14s} role side {'fills':>7s} {'shares':>10s} {'usdc':>10s} {'%usdc':>6s} {'avg_px':>6s} {'avg_fill_sh':>10s} {'wV=sh*p*(1-p)':>13s}")
for k in sorted(agg, key=lambda k:-agg[k]['usd']):
    a=agg[k]
    print(f"{k[0]:14s} {k[1]:4s} {k[2]:4s} {a['n']:7.0f} {a['sh']:10.0f} {a['usd']:10.0f} {a['usd']/tot_usd*100:5.1f}% {a['usd']/a['sh']:6.3f} {a['sh']/a['n']:10.1f} {a['w']:13.0f}")
mk=sum(a['usd'] for k,a in agg.items() if k[1]=='M'); tk=sum(a['usd'] for k,a in agg.items() if k[1]=='T')
print(f"\nTOTAL usdc {tot_usd:.0f}: maker {mk:.0f} ({mk/tot_usd*100:.1f}%)  taker {tk:.0f} ({tk/tot_usd*100:.1f}%)")
print("distinct markets:", len(set(r['condition_id'] for r in rows)))

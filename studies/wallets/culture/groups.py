"""Group each account's markets (from the pmlab.wallet JSON) by slug stem to see what it actually trades."""
import json, re, sys, collections
def stem(s):
    s = s or 'none'
    s = re.sub(r'\d+', '#', s)
    return s[:58]
for n in sys.argv[1:]:
    d = json.load(open(n + '.json'))
    g = collections.defaultdict(lambda: dict(m=0, res=0, inc=0, turn=0.0, net=0.0, fam=''))
    for m in d['_markets']:
        k = stem(m['slug'])
        x = g[k]; x['m'] += 1; x['turn'] += m.get('turnover') or 0; x['fam'] = m['family']
        if m.get('resolved') and not m.get('incomplete'):
            x['res'] += 1; x['net'] += m.get('net') or 0
        if m.get('incomplete'): x['inc'] += 1
    print(f'\n== {n}: {len(d["_markets"])} markets, {len(g)} stems')
    for k, x in sorted(g.items(), key=lambda kv: -kv[1]['turn'])[:int(18)]:
        print(f"  {x['fam'][:8]:8} mk {x['m']:4} res {x['res']:4} inc {x['inc']:4} turn {x['turn']:9.0f} net {x['net']:9.0f}  {k}")

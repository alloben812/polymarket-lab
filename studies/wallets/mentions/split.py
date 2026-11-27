"""Variant 1: which share of each candidate's 14-day activity is in mentions markets (tag or slug), and its PnL there."""
import json, re, sys, glob, os
sys.path.insert(0, '/home/user/polymarket-lab')
from pmlab import gamma
D = os.path.dirname(os.path.abspath(__file__))
PAT = re.compile(r"(^|-)(say|says|said|mention|mentions|mentioned)(-|$)")
def is_mention(md, slug):
    tags = set(gamma.tag_slugs(md or {}))
    return any('mention' in t for t in tags) or bool(PAT.search(slug or ''))
out = {}
alltags = {}
for f in sorted(glob.glob(D + '/*.json')):
    n = os.path.basename(f)[:-5]
    if n in ('leaders',) or n.startswith('_'): continue
    d = json.load(open(f))
    if '_markets' not in d: continue
    ms = d['_markets']
    meta = gamma.markets_by_condition([m['condition'] for m in ms])
    a = dict(mk=0, res=0, inc=0, to=0.0, net=0.0, wins=0, taker=0.0, fills=0)
    o = dict(mk=0, to=0.0, net=0.0)
    for m in ms:
        md = meta.get(m['condition'])
        if m['n_fills'] == 0: continue
        if is_mention(md, m['slug']):
            for t in gamma.tag_slugs(md or {}): alltags[t] = alltags.get(t, 0) + 1
            a['mk'] += 1; a['to'] += m['turnover']; a['fills'] += m['n_fills']; a['taker'] += m['taker_usd']
            if m['incomplete']: a['inc'] += 1
            elif m['resolved']:
                a['res'] += 1; a['net'] += m['net']; a['wins'] += m['net'] > 0
        else:
            o['mk'] += 1; o['to'] += m['turnover']; o['net'] += (m['net'] if m['resolved'] and not m['incomplete'] else 0)
    s = d['summary']; ap = d.get('api_window') or {}
    out[n] = dict(mentions=a, other=o)
    print(f"{n:20s} trunc={d['account']['truncated']} fills={s['fills']:5d} | MENTIONS mk={a['mk']:4d} res={a['res']:4d} inc={a['inc']:3d} fills={a['fills']:5d} to=${a['to']:9.0f} taker={a['taker']/max(a['to'],1):.2f} net=${a['net']:8.0f} win={a['wins']/max(a['res'],1):.2f} | OTHER mk={o['mk']:4d} to=${o['to']:9.0f} net=${o['net']:8.0f} | tool net {s['net']:.0f} vs API kept {ap.get('economic_pnl')}")
json.dump(out, open(D + '/_split.json', 'w'), indent=1)
print(sorted(alltags.items(), key=lambda x: -x[1])[:25])

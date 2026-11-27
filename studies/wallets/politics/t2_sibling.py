"""T2 of protocol.md: are Cb94C437's politics buys preceded by a >= 2 c move in a sibling market (120 s)? Placebo = 1 h earlier."""
import bisect, collections, json, os
base = '/home/user/polymarket-lab/data/politics_wallets/'; acc = json.load(open('Cb94C437.json')); meta = {m['condition']: m for m in acc['_markets']}
fills = json.load(open(base + 'Cb94C437.fills.json')); ev = collections.defaultdict(set); f2e = {}
for f in fills:
    if (meta.get(f['condition_id']) or {}).get('family') == 'politics' and os.path.exists(base + 'tapes/' + f['condition_id'] + '.json'): ev[f['event_slug']].add(f['condition_id'])
tp = {}
for cs in ev.values():
    for c in cs:
        rows = json.load(open(base + 'tapes/' + c + '.json')); tp[c] = ([r[0] for r in rows], [(r[3] if r[2] == 0 else 1 - r[3]) for r in rows])
def moved(c, t):
    ts, ps = tp[c]; i = bisect.bisect_left(ts, t - 123) - 1; j = bisect.bisect_right(ts, t - 3) - 1
    return i >= 0 and j > i and abs(ps[j] - ps[i]) >= 0.02
def own(c, t):
    return moved(c, t)
n = hit = pl = ownhit = ownpl = 0; evs = set()
for f in fills:
    if f['side'] != 'BUY' or f['event_slug'] not in ev or f['condition_id'] not in ev[f['event_slug']]: continue
    sib = [c for c in ev[f['event_slug']] if c != f['condition_id']]
    if not sib: continue
    t = f['timestamp']; n += 1; evs.add(f['event_slug'])
    hit += any(moved(c, t) for c in sib); pl += any(moved(c, t - 3600) for c in sib)
    ownhit += own(f['condition_id'], t); ownpl += own(f['condition_id'], t - 3600)
print(f"Cb94C437 politics buys with a sibling tape: {n} in {len(evs)} events")
print(f"  sibling moved >= 2 c in the 120 s before: {hit} ({hit / max(1, n):.1%});  placebo one hour earlier: {pl} ({pl / max(1, n):.1%});  ratio {hit / max(1, pl):.2f}")
print(f"  OWN market moved >= 2 c in the 120 s before: {ownhit} ({ownhit / max(1, n):.1%});  placebo: {ownpl} ({ownpl / max(1, n):.1%})")

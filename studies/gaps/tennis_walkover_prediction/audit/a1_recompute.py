"""Independent recompute of the key number: walkover rate and premium vs fee among underdogs buyable T-6h..T-1h.
Own code: reads only universe.json and raw tapes. Does not import s1/s2."""
import json, gzip, os, sys, math, collections
U = json.load(open('/home/user/polymarket-lab/data/gaps_tennis_wo/universe.json'))
TAPE = '/home/user/polymarket-lab/data/tape/'
H = 3600
def load(cid):
    p = TAPE + cid + '.jsonl.gz'
    if not os.path.exists(p): return None
    return [json.loads(l) for l in gzip.open(p, 'rt')]
def buyables(tape, outs):
    """list of (match_time, outcome_index, price_buyable, size) for each print: BUY o@p -> o buyable at p; SELL o@p -> other buyable at 1-p"""
    out = []
    for r in tape:
        if r['o'] not in outs: continue
        i = outs.index(r['o']); p = float(r['p']); z = float(r['z']); t = r['t'] - 3
        if r['s'] == 'BUY': out.append((t, i, p, z))
        else: out.append((t, 1 - i, 1 - p, z))
    out.sort(); return out
def run(lo_h, hi_h, pmin=0.05, pmax=0.45, rate=0.05, firstonly=True):
    rows = []
    for cls, recs, w in (('A', U['A'], 1), ('C', U['control'], 8)):
        for r in recs:
            if cls == 'A':
                m = [x for x in r['markets'] if x['type'] == 'moneyline'][0]
                cid, outs, fin, start = m['cid'], m['outcomes'], m.get('api_final') or m['final'], m['start'] or r['startTime']
            else:
                cid, outs, fin, start = r['cid'], r['outcomes'], r.get('api_final') or r['final'], r['start']
            if start is None: continue
            tp = load(cid)
            if tp is None: continue
            bs = buyables(tp, outs)
            for t, i, p, z in bs:
                if start - lo_h*H <= t <= start - hi_h*H and pmin-1e-9 <= p <= pmax+1e-9:
                    rows.append((cls, w, p, fin[i], z, start - t)); break
    return rows
def stats(rows, rate=0.05, label=''):
    W = sum(r[1] for r in rows)
    wo = sum(1 for r in rows if r[0]=='A')
    q = sum(r[1] for r in rows if r[0]=='A')/W
    prem = sum(r[1]*(0.5-r[2]) for r in rows if r[0]=='A')/W
    fee = sum(r[1]*rate*r[2]*(1-r[2]) for r in rows)/W
    gross = sum(r[1]*(r[3]-r[2]) for r in rows)/W
    print(f"{label:34s} n={len(rows):5d} wo={wo:4d} W={W:7.0f} q={q*100:.2f}% premium={prem*100:+.3f}c fee={fee*100:.3f}c prem-fee={100*(prem-fee):+.3f}c gross(pay-p)={gross*100:+.2f}c net={100*(gross-fee):+.2f}c")
if __name__ == '__main__':
    stats(run(6,1), label='protocol window T-6h..T-1h')

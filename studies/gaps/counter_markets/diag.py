"""POST-HOC diagnostic (not a strategy variant, written after the protocol results were seen):
is the simple counter model a better probability than the price? For every (event, h, token) the FIRST print in the
30-minute window, regardless of edge: Brier score of model q vs the print price c against the outcome.
python3 -I diag.py > out/diag.txt"""
import contextlib, io, os
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analyze.py')).read().split('ALL = {}; rows = []')[0]
with contextlib.redirect_stdout(io.StringIO()): exec(src)
for model in ('M1', 'M2'):
    for part in ('EARLY', 'LATE'):
        acc = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0]); ev_bs = []
        for ev in EV:
            if ev['part'] != part: continue
            eb = [0.0, 0.0, 0]
            for h, t in dec_times(ev):
                k = KFIT[(model, h)]; seen = set()
                for (lo, hi), m, yes in ev['mk']:
                    yi = m['outcomes'].index('Yes'); ytok, ntok = m['toks'][yi], m['toks'][1 - yi]
                    rows = tape(m['cid']); i = bisect.bisect_left([r['t'] for r in rows], t + LAG)
                    for r in rows[i:]:
                        mt = r['t'] - LAG
                        if mt > t + WIN: break
                        tk, c = (r['tok'], r['p']) if r['side'] == 'BUY' else ((ntok if r['tok'] == ytok else ytok), 1 - r['p'])
                        if tk in seen or not (0.02 <= c <= 0.97): continue
                        seen.add(tk); N = ncount(ev, mt); q = qbucket(mu_of(model, ev, mt, N), k, N, lo, hi)
                        y = yes
                        if tk != ytok: q, y = 1 - q, 1 - yes
                        a = acc[h]; a[0] += 1; a[1] += (q - y) ** 2; a[2] += (c - y) ** 2; a[3] += (q - c)
                        eb[0] += (q - y) ** 2; eb[1] += (c - y) ** 2; eb[2] += 1
            if eb[2]: ev_bs.append((eb[0] - eb[1]) / eb[2])
        tot = [sum(a[i] for a in acc.values()) for i in range(4)]
        m_, se, tt = stats.mean_se(ev_bs)
        print(f'{model} {part}: first prints {tot[0]}, Brier model {tot[1] / tot[0]:.4f} vs price {tot[2] / tot[0]:.4f}; '
              f'mean per-event (model - price) {m_:+.4f} (se {se:.4f}, t {tt:+.2f}, {len(ev_bs)} events)')
        for h in sorted(acc, reverse=True):
            a = acc[h]; print(f'    h={h:2}: n {a[0]:4} Brier model {a[1] / a[0]:.4f} price {a[2] / a[0]:.4f}')

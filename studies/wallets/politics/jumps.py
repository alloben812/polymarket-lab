"""News jumps on the cached tapes and what the account did around them.   python3 jumps.py <tag> [min_jump_c=8] [window_s=120]

A jump = the YES-equivalent last-print price (all wallets) moves by >= min_jump within window_s, measured from the last
print before the window; t0 = time of the first print that is >= 2 c away from the pre-level (start of the move).
For each jump: pre level, level 5 min after t0, number of taker wallets in the first 60 s, and the account's fills:
  before  = its net YES-equivalent shares traded in the 30 min before t0 in the jump direction (+) or against (-)
  first   = lag in seconds from t0 to its first fill, role, signed direction, price captured relative to the 5-min level.
Block timestamps are 2-3 s after the match, same for everyone, so lags between wallets are comparable.
"""
import bisect, collections, json, os, sys, time
tag = sys.argv[1]; mj = float(sys.argv[2]) / 100 if len(sys.argv) > 2 else 0.08; ws = int(sys.argv[3]) if len(sys.argv) > 3 else 120
base = '/home/user/polymarket-lab/data/politics_wallets/'
acc = json.load(open(tag + '.json')); wal = acc['account']['wallet'].lower(); meta = {m['condition']: m for m in acc['_markets']}
out = []
for c, m in meta.items():
    p = base + 'tapes/' + c + '.json'
    if not os.path.exists(p): continue
    tp = json.load(open(p))
    if len(tp) < 50: continue
    ser = [(t, (px if oi == 0 else 1 - px), sz, (1 if (sd == 'BUY') == (oi == 0) else -1), w) for t, sd, oi, px, sz, w in tp]
    ts = [x[0] for x in ser]; i = 1; last_jump = 0
    while i < len(ser):
        t = ser[i][0]; pre = ser[i - 1][1]
        if abs(ser[i][1] - pre) >= 0.02 and t - last_jump > 1800:
            j = bisect.bisect_right(ts, t + ws) - 1
            seg = [x[1] for x in ser[i:j + 1]]
            ext = max(seg, key=lambda v: abs(v - pre))
            k5 = bisect.bisect_right(ts, t + 300) - 1; lvl5 = ser[k5][1]
            if abs(ext - pre) >= mj and abs(lvl5 - pre) >= mj * 0.6 and (lvl5 - pre) * (ext - pre) > 0:
                d = 1 if lvl5 > pre else -1
                k60 = bisect.bisect_right(ts, t + 60)
                wl = {x[4] for x in ser[i:k60]}
                b0 = bisect.bisect_left(ts, t - 1800)
                before = sum(x[2] * x[3] * d for x in ser[b0:i] if x[4] == wal)
                mine = [x for x in ser[i:bisect.bisect_right(ts, t + 1800)] if x[4] == wal]
                first = None
                if mine:
                    x = mine[0]; first = dict(lag=x[0] - t, dir=x[3] * d, px=x[1], edge=d * (lvl5 - x[1]) * (x[3] * d), sh=sum(y[2] for y in mine if y[0] - t <= 300))
                # taker-side only tape: maker fills of the account are not in it; get them from own fills later
                out.append(dict(c=c, slug=m['slug'], t=t, pre=pre, ext=ext, lvl5=lvl5, d=d, n_wal60=len(wl), before=before, first=first, sh60=sum(x[2] for x in ser[i:k60])))
                last_jump = t
        i += 1
out.sort(key=lambda r: r['t'])
# the tape has taker rows only: add the account's own fills (both roles) from its fill cache
fills = json.load(open(base + tag + '.fills.json')); byc = collections.defaultdict(list)
for f in fills:
    oi = 0 if f['outcome'] == 'Yes' else 1; px = float(f['price']); py = px if oi == 0 else 1 - px; d = 1 if (f['side'] == 'BUY') == (oi == 0) else -1
    byc[f['condition_id']].append((f['timestamp'], py, float(f['size']), d, f['role']))
n = part10 = part60 = part300 = withdir = antic = 0; maker_hit = 0; rows = []
for r in out:
    own = sorted(byc.get(r['c'], [])); n += 1
    aft = [x for x in own if 0 <= x[0] - r['t'] <= 1800]; bef = [x for x in own if -1800 <= x[0] - r['t'] < 0]
    b = sum(x[2] * x[3] * r['d'] for x in bef)
    f300 = [x for x in aft if x[0] - r['t'] <= 300]
    net300 = sum(x[2] * x[3] * r['d'] for x in f300); mk_against = sum(x[2] for x in f300 if x[4] == 'M' and x[3] * r['d'] < 0); tk_with = sum(x[2] for x in f300 if x[4] == 'T' and x[3] * r['d'] > 0)
    lag = aft[0][0] - r['t'] if aft else None
    cap = (sum(x[2] * r['d'] * (r['lvl5'] - x[1]) * (x[3] * r['d']) for x in f300)) if f300 else 0.0
    part10 += lag is not None and lag <= 10; part60 += lag is not None and lag <= 60; part300 += lag is not None and lag <= 300
    withdir += net300 > 0; antic += b > 0; maker_hit += mk_against > 0
    rows.append((r, lag, b, net300, tk_with, mk_against, cap))
print(f"{tag}: {n} jumps (>= {mj * 100:.0f} c within {ws} s) on {len({r['c'] for r in out})} of its markets with cached tapes")
print(f"  account's first fill within 10 s: {part10}, 60 s: {part60}, 300 s: {part300};  net WITH the jump in first 300 s: {withdir};  run over as maker (maker fills against the jump): {maker_hit};  net position added in jump direction in the 30 min BEFORE: {antic}")
tot = sum(x[6] for x in rows); print(f"  5-minute value captured by its fills in the first 300 s (shares * (level at +5 min - fill price), signed): ${tot:,.0f}")
for r, lag, b, net300, tk, mk, cap in sorted(rows, key=lambda x: -abs(x[6]))[:22]:
    print(f"  {time.strftime('%m-%d %H:%M:%S', time.gmtime(r['t']))} {r['slug'][:52]:52} {r['pre']:.2f}->{r['lvl5']:.2f} wallets60 {r['n_wal60']:3} | before {b:+8.0f} sh | first fill lag {str(lag):>5} s | net 300 s {net300:+8.0f} sh (taker with {tk:7.0f}, maker against {mk:7.0f}) | captured ${cap:+7.0f}")
json.dump([dict(r, lag=lag, before_own=b, net300=net300, cap=cap) for r, lag, b, net300, tk, mk, cap in rows], open(tag + '.jumps.json', 'w'))

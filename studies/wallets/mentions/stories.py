"""Variant 2b: print sampled market stories from deep_<label>.json (top 5 by |pnl| + 9 seeded-random, max 2 per event for the random part)."""
import json, sys, random, datetime as dt, os
D = os.path.dirname(os.path.abspath(__file__))
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%m-%d %H:%M:%S') if t else '-'
def rel(x):
    if x is None: return '   n/a'
    s = '-' if x < 0 else '+'; x = abs(x)
    return f"{s}{x//3600}h{(x%3600)//60:02d}m{x%60:02d}s"
label = sys.argv[1]
d = json.load(open(f"{D}/deep_{label}.json"))
S = d['stories']
top = sorted(S, key=lambda s: -abs(s['pnl']))[:5]
rest = [s for s in S if s not in top]
random.Random(7).shuffle(rest)
seen, pick = {}, []
for s in rest:
    if seen.get(s['event'], 0) >= 2: continue
    seen[s['event']] = seen.get(s['event'], 0) + 1; pick.append(s)
    if len(pick) >= 9: break
for s in top + pick:
    print(f"\n# {s['q']}  [{(s['event'] or '')[:60]}]  vol ${s['vol'] or 0:.0f} tape {s['n_tape']} rows")
    print(f"  sched start {iso(s['start'])} | last print<0.60 {iso(s['tpre'])} | first print>=0.60 {iso(s['first_move'])} | determined(tape) {iso(s['tdet'])} | resolved {iso(s['closed'])} | outcome {'YES' if s['final_yes']>=0.5 else 'NO'} | account pnl ${s['pnl']} on ${s['usd']}")
    fl = s['fills']
    for f in fl[:7] + ([dict(skip=len(fl) - 9)] if len(fl) > 9 else []) + (fl[-2:] if len(fl) > 9 else fl[7:9]):
        if 'skip' in f: print(f"    ... {f['skip']} more fills ..."); continue
        print(f"    {iso(f['t'])} start{rel(f['rel_start'])} det{rel(f['rel_det'])} {f['ph']:7s} {f['role']} {f['side']:4s} {f['o']:3s} @{f['p']:.3f} x{f['s']:7.1f} pnl {f['pnl']:8.2f}")

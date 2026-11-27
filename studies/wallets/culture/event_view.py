"""Timeline of one event (all markets whose slug matches) for one account: its fills (grouped per 30 min) next to
the independent tape (other wallets) and the tape's biggest 30-minute repricings.
  python3 event_view.py <tag> '<slug regex>' [min_jump_cents]"""
import bisect, collections, datetime as dt, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pmlab import dataapi
tag, rx = sys.argv[1], re.compile(sys.argv[2]); J = float(sys.argv[3]) / 100 if len(sys.argv) > 3 else 0.12
d = json.load(open(tag + '.story.json')); wal = d['wallet'].lower()
iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%a %m-%d %H:%M')
ev = []
for m in d['markets']:
    if not rx.search(m['slug'] or ''): continue
    raw = list(dataapi.iter_trades(condition=m['cond'], max_rows=40000))
    if raw and not ev: print('tape row keys:', sorted(raw[0].keys()))
    tp = sorted((int(r['timestamp']), float(r['price']) if r.get('outcome') == m['first'] else 1 - float(r['price']), float(r['size']),
                 (r.get('proxy_wallet') or r.get('user') or '').lower() == wal) for r in raw)
    oth = [(t, p) for t, p, s, own in tp if not own]; ts = [t for t, _ in oth]
    short = re.sub(r'^will-|opening-weekend-box-office-be-|-2026.*$', '', m['slug'])[:44]
    print(f"\n## {m['slug']}\n   final {m['final']} vol {m['vol']} end {iso(m['end']) if m['end'] else '-'} closed {iso(m['closed']) if m['closed'] else '-'} T90 {iso(m['t90']) if m['t90'] else '-'} tape rows {len(tp)} (own taker rows {sum(1 for x in tp if x[3])}) pnl {m['pnl']:.0f}")
    def px(t):
        i = bisect.bisect_right(ts, t) - 1
        return oth[i][1] if i >= 0 else float('nan')
    g = collections.OrderedDict()
    for r in m['fills']:
        k = (r['t'] // 1800, r['role'], r['sign'])
        x = g.setdefault(k, [0.0, 0.0, r['t'], r['t']]); x[0] += r['size']; x[1] += r['size'] * r['py']; x[3] = r['t']
    for (b, role, sign), (sh, cost, t0, t1) in g.items():
        ev.append((t0, f"  FILL {iso(t0)} {short:44} {role} {'LONG ' if sign > 0 else 'SHORT'}yes {sh:6.0f} @ {cost / sh:.3f} | others: before {px(t0 - 1):.2f} +10m {px(t1 + 600):.2f} +1h {px(t1 + 3600):.2f} +6h {px(t1 + 21600):.2f} +24h {px(t1 + 86400):.2f}"))
    if oth:
        t = (oth[0][0] // 1800) * 1800
        while t < oth[-1][0]:
            a, b = px(t), px(t + 1800)
            if a == a and abs(b - a) >= J:
                n = bisect.bisect_right(ts, t + 1800) - bisect.bisect_right(ts, t)
                ev.append((t, f"  jump {iso(t)} {short:44} {a:.2f} -> {b:.2f} ({n} trades)"))
            t += 1800
print()
for _, line in sorted(ev): print(line)

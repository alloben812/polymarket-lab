"""Threshold accounts: Polymarket-price markouts from whole-market tapes + market stories (top markets by the account's turnover)."""
import sys, json, collections, bisect, datetime as dt
import numpy as np
import ud
from pmlab import updown, stats
name = sys.argv[1]; NM = int(sys.argv[2]) if len(sys.argv) > 2 else 12
rows = json.load(open(ud.HERE / "out" / f"thr_{name}.json"))
turn = collections.Counter()
for r in rows:
    if r["final"] is not None: turn[r["cond"]] += r["size"] * r["price"]
# half by turnover, half spread through the list, so the sample is not only the biggest markets
order = [c for c, _ in turn.most_common()]
pick = order[:NM // 2] + order[NM // 2::max(1, (len(order) - NM // 2) // (NM - NM // 2))][:NM - NM // 2]
H = (10, 60, 600, 3600)
agg = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0]))
fmt = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
print(f"== {name}: {len(pick)} markets (of {len(order)} resolved above/hit markets with fills in 2026-11-21..26)")
for c in pick:
    tape = updown.tape(c); mine = sorted([r for r in rows if r["cond"] == c], key=lambda r: r["tm"])
    tt = np.array([x["t"] - 3 for x in tape]); py = np.array([x["p"] if x["o"] == "Yes" else 1 - x["p"] for x in tape])
    def px_at(t, win):
        i, j = bisect.bisect_left(tt, t), bisect.bisect_right(tt, t + win)
        return float(np.median(py[i:j])) if j > i else float("nan")
    for r in mine:
        yes_dir = (1 if r["outcome"] == "Yes" else -1) * (1 if r["side"] == "BUY" else -1)
        p_yes = r["price"] if r["outcome"] == "Yes" else 1 - r["price"]
        for h in H:
            p2 = px_at(r["tm"] + h, max(h, 30))
            if p2 == p2:
                a = agg[(r["role"], h)][c]; a[0] += (p2 - p_yes) * yes_dir * r["size"]; a[1] += r["size"]
    m0 = mine[0]; hit = m0["hit_t"]
    net_yes = sum(r["size"] * (1 if r["outcome"] == "Yes" else -1) * (1 if r["side"] == "BUY" else -1) for r in mine)
    pnl = sum(r["size"] * (r["final"] - r["price"]) * (1 if r["side"] == "BUY" else -1) - r["fee"] for r in mine)
    print(f"\n{m0['slug']}  K={m0['K']:g} window {fmt(m0['t_start'])}..{fmt(m0['t_end'])}  first 1s close through K: {fmt(hit) if hit else 'none'}  tape fills {len(tape)}")
    print(f"   account: {len(mine)} fills in window, taker {sum(r['role']=='T' for r in mine)}, usd {sum(r['size']*r['price'] for r in mine):,.0f}, net Yes-equivalent shares {net_yes:,.0f}, final(Yes)={m0['final'] if m0['outcome']=='Yes' else 1-m0['final']:.0f}, pnl in window {pnl:,.0f}")
    # clusters separated by 30 min
    cl = [[mine[0]]]
    for r in mine[1:]:
        (cl.append([r]) if r["tm"] - cl[-1][-1]["tm"] > 1800 else cl[-1].append(r))
    show = cl if len(cl) <= 6 else cl[:3] + cl[-3:]
    for g in show:
        ny = sum(r["size"] * (1 if r["outcome"] == "Yes" else -1) * (1 if r["side"] == "BUY" else -1) for r in g)
        sh = sum(r["size"] for r in g); pyv = sum((r["price"] if r["outcome"] == "Yes" else 1 - r["price"]) * r["size"] for r in g) / sh
        print(f"     {fmt(g[0]['tm'])} +{(g[-1]['tm']-g[0]['tm'])//60:4}min  fills {len(g):4} (T {sum(r['role']=='T' for r in g):3})  net Yes-eq {ny:9,.0f}  avg Yes px {pyv:.3f}  spot {g[0]['S']:.6g}->{g[-1]['S']:.6g}  dist to K {g[0]['dist_pct']:+.2f}%  model(rv/iv) Yes {(g[0]['m_rv'] if g[0]['outcome']=='Yes' else 1-g[0]['m_rv']):.2f}/{(g[0]['m_iv'] if g[0]['outcome']=='Yes' else 1-g[0]['m_iv']):.2f}  tape Yes px +10min {px_at(g[-1]['tm']+600, 600):.3f}")
    if len(cl) > 6: print(f"     ... {len(cl)-6} more clusters")
print(f"\nMARKOUTS on these {len(pick)} markets (Polymarket tape median Yes price at t+h minus fill price, signed for the account, cents per share; clusters = markets)")
for role in "TM":
    line = f"  {role}: "
    for h in H:
        a = agg[(role, h)]
        if not a: continue
        e, se, _ = stats.ratio_cluster([v[0] for v in a.values()], [v[1] for v in a.values()])
        line += f" +{h}s {100*e:6.2f} (se {100*se:.2f}, sh {sum(v[1] for v in a.values()):,.0f}) |"
    print(line)

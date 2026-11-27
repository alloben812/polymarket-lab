"""Where do each account's fills sit relative to the appearance of the model on the deciding leaderboard (race.py
definition) and to the settling of the market's own tape (T90)?  usage: phases.py [account ...] -> phases_<acc>.txt"""
import sys, bisect, collections
from common import *
from race import INFO, JUMP, appearance, pw_rows, check_time, tape
def px_at(c, t):
    rows = pw_rows(c); i = bisect.bisect_right([r[0] for r in rows], t) - 1
    if i < 0: return float("nan")
    return rows[i][1] if INFO[c]["winner"] == "Yes" else 1 - rows[i][1]
def phase(c, t, m):
    kind = "debut" if "debut" in (m["event"] or "") else "monthend"
    t9 = JUMP[c][0]; ta = appearance(c)
    if kind == "debut":
        if ta is None: return kind, "0 no appearance found" + (" (after T90)" if t9 and t >= t9 else "")
        x = t - ta
        if x < -5: return kind, "1 before appearance" + (" >7d" if x < -7 * 86400 else (" 1-7d" if x < -86400 else " <24h"))
        if x <= 60: return kind, "2a 0-60 s after"
        if x <= 600: return kind, "2b 1-10 min after"
        if x <= 6 * 3600: return kind, "2c 10 min-6 h after"
        return kind, "2d 6 h+ after"
    hrs = (check_time(m["closed_at"]) - t) / 3600
    if t9 is not None and t >= t9: return kind, "m4 after T90"
    return kind, "m1 >7d before check" if hrs > 168 else ("m2 1-7d before check" if hrs > 24 else "m3 last 24h, before T90")
def run(name, out):
    d = load(name); bym = {m["condition"]: m for m in d["_markets"]}
    P = lambda *a: print(*a, file=out)
    agg = collections.defaultdict(lambda: collections.defaultdict(float)); mk = collections.defaultdict(set); stories = collections.defaultdict(list)
    for r in d["_fills"]:
        c = r["condition_id"]
        if c not in JUMP: continue
        m = bym[c]; kind, ph = phase(c, r["timestamp"], m); w = INFO[c]["winner"]
        size, price = float(r["size"]), float(r["price"]); val = 1.0 if r["outcome"] == w else 0.0
        edge = (val - price) * size if r["side"] == "BUY" else (price - val) * size
        fee = size * 0.05 * price * (1 - price) if r["role"] == "T" else 0.0
        right = (r["outcome"] == w) == (r["side"] == "BUY")
        k = (kind, ph, r["side"], r["role"]); a = agg[k]; mk[k].add(c)
        a["n"] += 1; a["usd"] += size * price; a["sh"] += size; a["edge"] += edge; a["fee"] += fee; a["ok"] += size * price * right
        stories[c].append((r["timestamp"], r["side"], r["role"], r["outcome"], size, price, ph))
    P(f"##### {name}: fills in {len(stories)} cached resolved arena/hle markets (edge = settlement value minus price; fee at 0.05*p*(1-p) on taker fills)")
    P(f"{'kind':8} {'phase':30} {'side':4} {'role':4} {'fills':>5} {'mkts':>4} {'usd':>8} {'avg_px':>6} {'right$%':>7} {'edge_c/sh':>9} {'fee_c/sh':>8} {'net_usd':>8}")
    tot = collections.defaultdict(float)
    for k in sorted(agg):
        a = agg[k]; tot[k[0] + " " + k[1][:2]] += a["edge"] - a["fee"]
        P(f"{k[0]:8} {k[1]:30} {k[2]:4} {k[3]:4} {int(a['n']):5d} {len(mk[k]):4d} {a['usd']:8.0f} {a['usd']/a['sh']:6.3f} {100*a['ok']/a['usd']:7.0f} {100*a['edge']/a['sh']:9.2f} {100*a['fee']/a['sh']:8.2f} {a['edge']-a['fee']:8.0f}")
    P("net by phase group: " + " | ".join(f"{k}: {v:.0f}" for k, v in sorted(tot.items())))
    # falsification counts per market: first buy relative to appearance
    first = collections.Counter(); 
    for c, xs in stories.items():
        if appearance(c) is None: continue
        b = [x for x in xs if x[1] == "BUY" and x[2] == "T"]
        if b: first[min(b)[6][:2]] += 1
    P(f"debut markets with a found appearance: first taker buy falls in phase -> {dict(sorted(first.items()))}")
    top = sorted(stories, key=lambda c: -sum(x[4] * x[5] for x in stories[c]))[:14]
    for c in top:
        m = bym[c]; ta = appearance(c); t9 = JUMP[c][0]; tc = m["closed_at"]
        P(f"\n- {INFO[c]['q']}  [{(m['event'] or '')[:60]}]\n    winner={INFO[c]['winner']} check={f(check_time(tc))} closed={f(tc)} appearance={fs(ta)} T90={fs(t9)} market vol={m['vol']:.0f}; account net={(m.get('net') or 0):.0f}{' (incomplete)' if m['incomplete'] else ''}")
        ref = ta or (check_time(tc) - 20 * 3600)
        pts = [("-7d", ref - 7*86400), ("-48h", ref - 48*3600), ("-1h", ref - 3600), ("-10s", ref - 10), ("+60s", ref + 60), ("+10m", ref + 600), ("+2h", ref + 7200), ("check-1h", check_time(tc) - 3600)]
        P("    pYes around " + ("appearance" if ta else "check-20h") + ": " + " ".join(f"{k}:{px_at(c,t):.2f}" for k, t in pts))
        g = collections.OrderedDict()
        for t, sd, role, o, size, price, ph in sorted(stories[c]):
            k = (t // 3600, sd, role, o, ph); a = g.setdefault(k, [0, 0.0, 0.0, t, t]); a[0] += 1; a[1] += size; a[2] += size * price; a[4] = t
        items = list(g.items())
        for k, a in (items if len(items) <= 7 else items[:4] + items[-3:]):
            rel = f"{(a[3]-ta):+.0f}s vs appearance" if ta and abs(a[3] - ta) < 3600 else (f"{(a[3]-ta)/3600:+.1f}h vs appearance" if ta else f"{(check_time(tc)-a[3])/3600:.1f}h before check")
            P(f"    {fs(a[3])} {k[1]:4} {k[2]} {k[3]:3} n={a[0]:3d} sh={a[1]:7.0f} px={a[2]/a[1]:.3f} usd={a[2]:6.0f}  [{k[4]}; {rel}]")
        if len(items) > 7: P(f"    ... {len(items)-7} more hour-groups")
if __name__ == "__main__":
    for name in (sys.argv[1:] or list(ACC)):
        with open(f"phases_{name}.txt", "w") as out: run(name, out)

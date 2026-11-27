"""Market stories: for sampled markets per account, the deciding time (Yahoo proxy), the account's fills against it,
the model fair at the fills, the Polymarket price afterwards and the outcome. Also the 'bought after it was decided?' count."""
import sys, json, collections, statistics, datetime as dt, math
import fin, yh, ladder, model
from pmlab import dataapi
def hm(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M")
def decide_time(m, ty, title, T, P):
    """(time, label) when the outcome became known per the Yahoo proxy; None if it never was before T."""
    kind, K = ladder.strike(title)
    s = yh.session((T // 86400) * 86400); Tc = min(T, s[1]) if s else T
    if ty.startswith("hit") and K and P.ok:
        a = fin.ts(m.get("startDate")) or T - 7 * 86400
        if ty == "hit-week": a = max(a, (T // 86400) * 86400 - dt.datetime.fromtimestamp(T, dt.timezone.utc).weekday() * 86400)
        tt = P.first_touch(a, Tc, K, kind == "hitHIGH")
        return (tt, "touch") if tt else (Tc, "period end, never touched")
    return (Tc, "session close")
def run(name, k=14, bond=False):
    d = fin.load(name); meta = d["meta"]; res = d["res"]; rows = model.rows_for(name); G = collections.defaultdict(list)
    for r in rows: G[r["cond"]].append(r)
    cand = []
    for c, rs in G.items():
        if any(r["final"] is None for r in rs): continue
        pnl = sum(r["sgn"] * (r["final"] - r["px"]) * r["sz"] - r["fee"] * r["sz"] for r in rs); cand.append((pnl, c))
    cand.sort(); n = len(cand)
    # sample: evenly spaced through the PnL ranking (worst .. best), so the stories are not cherry-picked
    pick = [cand[int(i * (n - 1) / (k - 1))] for i in range(k)] if n >= k else cand
    print(f"\n################ {name}: {n} resolved equity price markets; {len(pick)} stories evenly spaced through the PnL ranking")
    aft = bef = 0; aft_usd = bef_usd = 0.0
    for c, rs in G.items():
        m = meta.get(c) or {}; P = model.px(rs[0]["tk"]); tdec, lab = decide_time(m, rs[0]["ty"], rs[0]["title"], fin.ts(m.get("endDate")), P)
        for r in rs:
            if r["side"] != "BUY": continue
            if r["t"] >= tdec: aft += 1; aft_usd += r["px"] * r["sz"]
            else: bef += 1; bef_usd += r["px"] * r["sz"]
    print(f"  ORDER TEST (all {len(G)} markets with a model value): buy fills at/after the deciding time {aft} (${aft_usd:.0f}) vs before {bef} (${bef_usd:.0f})")
    for pnl, c in pick:
        rs = sorted(G[c], key=lambda r: r["t"]); m = meta.get(c) or {}; r0 = rs[0]; P = model.px(r0["tk"]); T = fin.ts(m.get("endDate"))
        tdec, lab = decide_time(m, r0["ty"], r0["title"], T, P); closed = fin.ts(m.get("closedTime"))
        tok = ((res.get(c) or {}).get("tokens") or {})
        print(f"  * {r0['title']}  [{r0['ty']}, Pyth 1-min candles]  outcome: {[o for o, v in ((res.get(c) or {}).get('final') or {}).items() if v == 1.0]}  decided {hm(tdec)} ({lab}); resolved on-chain {hm(closed) if closed else '?'} (+{(closed - tdec) / 60:.0f} min)" if closed else f"  * {r0['title']}")
        byo = collections.defaultdict(list)
        for r in rs: byo[(r["side"], r["out"])].append(r)
        for (sd, o), xs in byo.items():
            sh = sum(x["sz"] for x in xs); px_ = sum(x["px"] * x["sz"] for x in xs) / sh; fv = sum(x["fair"] * x["sz"] for x in xs) / sh
            lead = [(tdec - x["t"]) / 3600 for x in xs]
            after = ""
            try:
                t_last = xs[-1]["t"]; ph = dataapi.prices_history(tok.get(o), t_last, min(t_last + 7200, T), 300) if tok.get(o) else []
                if ph: after = f"; PM price 1-2 h after the last fill {float(ph[-1].get('price') or ph[-1].get('p') or 0):.2f}"
            except Exception as e: after = ""
            print(f"      {sd} {o}: {len(xs)} fills {sh:.0f} sh @ {px_:.3f} ({sum(x['role'] == 'M' for x in xs)} maker) between {hm(xs[0]['t'])} and {hm(xs[-1]['t'])} UTC, {statistics.median(lead):.1f} h before decision (median); ref {xs[0]['S']:.2f}..{xs[-1]['S']:.2f} vs strike {xs[0]['K']:.2f}; model fair {fv:.2f}{after}")
        print(f"      result ${pnl:+.0f}")
def bond(name, k=14):
    d = fin.load(name); meta = d["meta"]; res = d["res"]; rows = [r for r in model.rows_for(name) if r["side"] == "BUY" and r["px"] >= 0.90]
    aft = bef = 0; au = bu = 0.0; delays = []; pre = []
    for r in rows:
        m = meta.get(r["cond"]) or {}; P = model.px(r["tk"]); tdec, lab = decide_time(m, r["ty"], r["title"], fin.ts(m.get("endDate")), P)
        won = r["final"]; r["tdec"] = tdec; r["lab"] = lab; r["closed"] = fin.ts(m.get("closedTime"))
        if r["t"] >= tdec: aft += 1; au += r["px"] * r["sz"]; delays.append(r["t"] - tdec)
        else: bef += 1; bu += r["px"] * r["sz"]; pre.append(r)
    print(f"\n################ {name} (buys at >= 0.90, equity price markets with a Yahoo proxy): at/after the deciding time {aft} fills ${au:.0f}; before {bef} fills ${bu:.0f}")
    if delays:
        ds = sorted(delays); print(f"  delay decision -> fill: p10 {ds[len(ds) // 10]} s, median {ds[len(ds) // 2]} s, p90 {ds[9 * len(ds) // 10]} s; fill -> on-chain resolution median {statistics.median([(r['closed'] - r['t']) / 60 for r in rows if r.get('closed') and r['t'] >= r['tdec']]):.0f} min")
    if pre:
        z = [abs(math.log(r["S"] / r["K"])) / (r["sig"] * math.sqrt(max(yh.var_left(r["t"], r["T"]), 1e-6))) for r in pre if r["K"]]
        print(f"  the 'before' fills: median price {statistics.median(r['px'] for r in pre):.3f}, median model fair {statistics.median(r['fair'] for r in pre):.3f}, distance to strike in sigmas of time left: median {statistics.median(z):.1f}, min {min(z):.1f}; lost: {sum(1 for r in pre if r['final'] == 0)} of {sum(1 for r in pre if r['final'] is not None)} resolved")
    rows.sort(key=lambda r: -r["px"] * r["sz"]); seen = set(); n = 0
    for r in rows:
        if r["cond"] in seen: continue
        seen.add(r["cond"]); n += 1
        if n > k: break
        print(f"  * {r['title']} [{r['ty']}] {r['side']} {r['out']} {r['sz']:.0f} @ {r['px']:.4f} ({'maker' if r['role'] == 'M' else 'taker'}) at {hm(r['t'])}; decided {hm(r['tdec'])} ({r['lab']}) -> fill {(r['t'] - r['tdec']) / 60:+.0f} min; resolved {hm(r['closed']) if r['closed'] else '?'}; ref {r['S']:.2f} vs strike {r['K']:.2f}; final {r['final']}")
if __name__ == "__main__":
    for a in sys.argv[1:]:
        if a.startswith("bond:"): bond(a[5:])
        else: run(a)

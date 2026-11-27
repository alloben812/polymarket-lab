"""Dota 2: align Polymarket 'Game N Winner' tapes with OpenDota match clocks (start_time, duration, kills).
A  end of game vs the tape     B  event study around won fights (>= 3 net kills in a cluster)
C  when in the game each account trades     D  lag of taker buys after a won fight, account vs crowd, with a placebo
E  markouts of account taker fills on ALL mapped markets + a momentum control     F  episodes of the taker bot."""
import json, os, collections, statistics as st, bisect, sys
import lib
from pmlab import stats
ACC = ["RITALINEWITHSNUS", "BLASTSLAM9WINNER", "DamwonChampions2027", "calculate10"]
mp = json.load(open(f"{lib.HERE}/out/od_map.json"))
def P(*a): print(*a, flush=True)
det = {}
for c, v in mp.items():
    p = f"{lib.HERE}/out/od_matches/{v['match_id']}.json"
    if os.path.exists(p): det[c] = json.load(open(p))
M = lib.meta(list(mp)); R = lib.resol(list(mp))
AF = {n: collections.defaultdict(list) for n in ACC}
for n in ACC:
    for f in lib.fills(n): AF[n][f["condition_id"]].append(f)
WL = {lib.WALLETS[n].lower(): n for n in ACC}
usd = lambda r: r["size"] * r["price"]
endlag = []; ev_curves = collections.defaultdict(list); OFFS = list(range(-60, 305, 5))
flow = {k: collections.Counter() for k in ["crowd_same", "crowd_opp"] + [n + s for n in ACC for s in ("_same", "_opp")]}
gclock = {n: collections.Counter() for n in ACC}
mo = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0]))
episodes = []; nev = 0; nmk = 0
for c, v in mp.items():
    if c not in det or not os.path.exists(f"{lib.HERE}/fills/tape_{c[:14]}.json.gz"): continue
    d = det[c]; m = M[c]; toks = lib.gamma.jfield(m["clobTokenIds"]); tok0 = toks[0]; T = lib.tape(c)
    if len(T) < 50 or not d.get("kills"): continue
    nmk += 1
    path = lib.Path(T, tok0); o0r = v["out0_is_radiant"]; start = d["start_time"]; dur = d["duration"]
    rad = lambda t: (lambda q: None if q is None else (q if o0r else 1 - q))(path.at(t))
    rw = d["radiant_win"]
    # A
    wp = [(t, (p if o0r else 1 - p) if rw else 1 - (p if o0r else 1 - p)) for t, p in zip(path.t, path.p)]
    t99 = None; tl90 = None
    for t, p in reversed(wp):
        if p < 0.90: tl90 = t; break
        if p >= 0.99: t99 = t
    draft = sum((x.get("total_time_taken") or 0) for x in (d.get("draft_timings") or []))
    if t99: endlag.append((t99 - start - dur, (tl90 or 0) - start - dur if tl90 else None, draft, v["slug"]))
    # B fight events
    ks = d["kills"]; cl = []; cur = []
    for t, isr in ks:
        if cur and t - cur[-1][0] > 12: cl.append(cur); cur = []
        cur.append((t, isr))
    if cur: cl.append(cur)
    events = []
    for g in cl:
        r = sum(1 for _, x in g if x); dd = len(g) - r
        if abs(r - dd) >= 3 and 600 <= g[0][0] and g[-1][0] <= dur - 240:
            w = start + g[-1][0]; base = rad(w - 60)
            if base is None or not (0.12 <= base <= 0.88): continue
            sign = 1 if r > dd else -1; events.append((w, sign, start + g[0][0]))
            for o in OFFS:
                q = rad(w + o)
                if q is not None: ev_curves[o].append((sign * (q - base) * 100, c))
    nev += len(events); ew = [e[0] for e in events]
    def last_event(t):
        i = bisect.bisect_right(ew, t) - 1
        return events[i] if i >= 0 else None
    def raddir(r):
        is0 = r["token_id"] == tok0; buy = r["side"] == "BUY"; d0 = 1 if is0 == buy else -1
        return d0 if o0r else -d0
    def lagbin(x): return "none/>=300" if x is None or x >= 300 else f"{int(x // 30) * 30:03d}-{int(x // 30) * 30 + 30:03d}"
    # D taker flow after fights (crowd = every taker that is not one of the four accounts)
    for r in T:
        w = (r.get("proxy_wallet") or "").lower(); e = last_event(r["timestamp"]); rd = raddir(r)
        who = WL.get(w, "crowd"); lag = (r["timestamp"] - e[0]) if e else None
        if who != "crowd": continue
        k = "crowd_same" if (e and rd == e[1]) else "crowd_opp"
        flow[k][lagbin(lag)] += usd(r)
    for n in ACC:
        for r in AF[n].get(c, []):
            t = r["timestamp"]
            b = "a before game start" if t < start else "g after end" if t > start + dur + 150 else f"{chr(98 + min(4, int((t - start) // 600)))} min {min(4, int((t - start) // 600)) * 10}+"
            gclock[n][(r["role"], b)] += usd(r)
            if r["role"] != "T": continue
            e = last_event(t); rd = raddir(r); lag = (t - e[0]) if e else None
            flow[n + ("_same" if (e and rd == e[1]) else "_opp")][lagbin(lag)] += usd(r)
    # E markouts (outcome-0 terms)
    fin0 = float(R[c]["final"].get(lib.gamma.jfield(m["outcomes"])[0]) or 0)
    def marks(r, key):
        is0 = r["token_id"] == tok0; buy = r["side"] == "BUY"; d0 = 1 if is0 == buy else -1; p0 = r["price"] if is0 else 1 - r["price"]; t = r["timestamp"]
        q30 = path.at(t - 30); pre = d0 * (p0 - q30) * 100 if q30 is not None else None
        keys = [key]
        if key == "crowd" and pre is not None and 1 <= pre <= 6: keys.append("crowd_pre30_1to6c")
        if key == "crowd" and pre is not None and 1 <= pre <= 6 and r["size"] * r["price"] >= 500: keys.append("crowd_pre30_1to6c_ge500usd")
        for k in keys:
            for h in (5, 10, 30, 60, 300):
                q = path.at(t + h)
                if q is not None: a = mo[(k, f"mo{h:03d}")][c]; a[0] += d0 * (q - p0) * 100 * r["size"]; a[1] += r["size"]
            a = mo[(k, "final")][c]; a[0] += d0 * (fin0 - p0) * 100 * r["size"]; a[1] += r["size"]
            a = mo[(k, "fee_c")][c]; a[0] += 5 * r["price"] * (1 - r["price"]) * r["size"]; a[1] += r["size"]
            if pre is not None: a = mo[(k, "pre30")][c]; a[0] += pre * r["size"]; a[1] += r["size"]
        return d0, p0
    for r in T:
        if (r.get("proxy_wallet") or "").lower() not in WL: marks(r, "crowd")
    for n in ACC:
        tk = [r for r in AF[n].get(c, []) if r["role"] == "T"]
        for r in tk:
            marks(r, n + "_T"); marks(r, n + ("_T_wk1" if r["timestamp"] < lib.END - 7 * 86400 else "_T_wk2"))
        for r in AF[n].get(c, []):
            if r["role"] == "M": marks(r, n + "_M")
        if n == "RITALINEWITHSNUS":   # F episodes
            cur = []
            def flush(cur):
                if not cur: return
                is0 = cur[0]["token_id"] == tok0; d0 = 1 if is0 else -1; sh = sum(x["size"] for x in cur); u = sum(usd(x) for x in cur); t0 = cur[0]["timestamp"]
                vw = sum((x["price"] if is0 else 1 - x["price"]) * x["size"] for x in cur) / sh
                q5 = path.at(t0 - 5); q60 = path.at(cur[-1]["timestamp"] + 60); q10 = path.at(cur[-1]["timestamp"] + 10)
                ob = sum(usd(x) for x in T if t0 - 12 <= x["timestamp"] < t0 - 1 and (x.get("proxy_wallet") or "").lower() not in WL and ((x["token_id"] == tok0) == (x["side"] == "BUY")) == is0)
                oa = sum(usd(x) for x in T if t0 - 1 <= x["timestamp"] <= t0 + 12 and (x.get("proxy_wallet") or "").lower() not in WL and ((x["token_id"] == tok0) == (x["side"] == "BUY")) == is0)
                e = last_event(t0); rd = d0 if o0r else -d0
                episodes.append(dict(c=c, slug=v["slug"], t0=t0, gmin=round((t0 - start) / 60, 1), usd=u, sh=sh, px=cur[0]["price"], pxavg=u / sh, pre5=d0 * (vw - q5) * 100 if q5 is not None else None,
                    mo10=d0 * (q10 - vw) * 100 if q10 is not None else None, mo60=d0 * (q60 - vw) * 100 if q60 is not None else None, fin=d0 * (fin0 - vw) * 100, others_before=ob, others_after=oa,
                    ev_lag=(t0 - e[0]) if (e and rd == e[1]) else None, n=len(cur), span=cur[-1]["timestamp"] - t0))
            for r in sorted(tk, key=lambda x: (x["token_id"], x["timestamp"])):
                if cur and (r["token_id"] != cur[-1]["token_id"] or r["timestamp"] - cur[-1]["timestamp"] > 20): flush(cur); cur = []
                cur.append(r)
            flush(cur)
P(f"mapped markets with tape + kills: {nmk}; fight events (>=3 net kills, minute 10+, price 0.12-0.88): {nev}")
x = sorted(e[0] for e in endlag); y = sorted(e[1] for e in endlag if e[1] is not None)
q = lambda v, p: v[min(len(v) - 1, int(len(v) * p))]
P(f"A  t99 - (start+duration): n {len(x)} p10 {q(x,.1)} p25 {q(x,.25)} median {q(x,.5)} p75 {q(x,.75)} p90 {q(x,.9)} s;   last print of winner < 0.90 - (start+duration): p10 {q(y,.1)} median {q(y,.5)} p90 {q(y,.9)}")
dr = [e[2] for e in endlag if e[2]]; 
if len(dr) > 5:
    xs = [e[2] for e in endlag if e[2]]; ys = [e[0] for e in endlag if e[2]]; mx, my = st.mean(xs), st.mean(ys)
    P(f"   draft length median {st.median(xs)} s; corr(draft length, t99 lag) = {sum((a-mx)*(b-my) for a,b in zip(xs,ys))/ (sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))**.5:.2f}")
P("B  event study: price of the team that won the fight, cents vs 60 s before the LAST kill (raw OpenDota clock = start_time + game time):")
P("   " + "  ".join(f"{o:+d}:{st.mean(a for a,_ in ev_curves[o]):.1f}" for o in (-30, -15, 0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 180, 210, 240, 300)))
P("D  taker buy $ by lag after the last won-fight event (same = buying the fight winner; opp = buying the fight loser), share of that group's $:")
bins = sorted({b for f in flow.values() for b in f})
P("   " + " ".join(f"{b:>11s}" for b in ["group"] + bins + ["total$"]))
for k, f in flow.items():
    tot = sum(flow[k.rsplit("_", 1)[0] + "_same"].values()) + sum(flow[k.rsplit("_", 1)[0] + "_opp"].values())
    if tot: P("   " + " ".join([f"{k[:11]:>11s}"] + [f"{f[b] / tot * 100:10.1f}%" for b in bins] + [f"{sum(f.values()):11,.0f}"]))
P("C  account $ by game clock (raw: minutes since OpenDota start_time):")
for n in ACC:
    tot = sum(gclock[n].values())
    if tot: P(f"   {n[:12]:12s} " + "  ".join(f"{k[0]}/{k[1]}: {v / tot * 100:.0f}%" for k, v in sorted(gclock[n].items())))
P("E  markouts on all mapped markets, c/share, clustered by market (ratio se t n shares):")
for key in sorted(mo):
    dd = mo[key]; num = [a[0] for a in dd.values()]; den = [a[1] for a in dd.values()]
    if len(num) < 5 or (key[0].startswith(("calc", "Damwon", "BLAST")) and key[1] not in ("mo010", "mo060", "final", "pre30", "fee_c")) or "wk" in key[0] and key[1] not in ("mo010", "final", "fee_c"): continue
    r, se, t = stats.ratio_cluster(num, den); P(f"   {key[0]:28s} {key[1]:6s} {r:7.2f} {se:6.2f} {t:6.2f}  n {len(num):3d}  {sum(den):12,.0f}")
E = episodes; json.dump(E, open(f"{lib.HERE}/out/ritaline_episodes.json", "w"))
if E:
    P(f"F  RITALINE taker episodes (fills within 20 s, one outcome): {len(E)} in {len({e['c'] for e in E})} markets; $ per episode median {st.median(e['usd'] for e in E):,.0f} p90 {q(sorted(e['usd'] for e in E), .9):,.0f} max {max(e['usd'] for e in E):,.0f}; fills/episode median {st.median(e['n'] for e in E)}")
    g = [e for e in E if e["mo60"] is not None]
    P(f"   mo60 > 1.2 c (fee) in {sum(1 for e in g if e['mo60'] > 1.2)}/{len(g)}; mo60 < -1.2 c in {sum(1 for e in g if e['mo60'] < -1.2)}; mean pre5 {st.mean(e['pre5'] for e in g if e['pre5'] is not None):.2f} c; won at settlement {sum(1 for e in E if e['fin'] > 0)}/{len(E)}")
    P(f"   others' same-direction taker $ in the 12 s before the episode: median {st.median(e['others_before'] for e in E):,.0f}; zero in {sum(1 for e in E if e['others_before'] == 0)}/{len(E)}; in the 12 s after: median {st.median(e['others_after'] for e in E):,.0f}")
    a = [e for e in E if e["ev_lag"] is not None and e["ev_lag"] < 300]
    P(f"   episodes within 300 s after a won fight of the bought team: {len(a)}/{len(E)}; lag median {st.median(e['ev_lag'] for e in a) if a else None} p25 {q(sorted(e['ev_lag'] for e in a), .25) if a else None} p75 {q(sorted(e['ev_lag'] for e in a), .75) if a else None}")
    P("   by entry price: " + "  ".join(f"{lo:.2f}-{hi:.2f}: n {len(s)} mo10 {st.mean(e['mo10'] for e in s if e['mo10'] is not None):.1f} fin {sum(e['fin']*e['sh'] for e in s)/sum(e['sh'] for e in s):.1f}" for lo, hi in ((0, .3), (.3, .5), (.5, .7), (.7, 1)) for s in [[e for e in E if lo <= e['pxavg'] < hi]] if len(s) > 3))
    P("   by game minute: " + "  ".join(f"{lo}-{hi}: n {len(s)} ${sum(e['usd'] for e in s):,.0f}" for lo, hi in ((-999, 0), (0, 10), (10, 20), (20, 30), (30, 40), (40, 999)) for s in [[e for e in E if lo <= e['gmin'] < hi]]))

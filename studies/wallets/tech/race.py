"""Who takes the stale prices when a model first appears on the deciding leaderboard?
Appearance of an event = earliest 'decisive jump' among its sibling markets on the rule-implied day (the ET calendar day
before the 12:00 ET check): the first trade of the run that stays >= 0.90 on the eventual winner, where the trade before
it was <= 0.80. Then every taker buy of the eventual winner below 0.97 after that moment is 'gap money'."""
import sys, os, bisect, collections, pickle, datetime as dt
from zoneinfo import ZoneInfo
from common import *
from tapes import tape, TD
ET = ZoneInfo("America/New_York")
have = {fn[:-4] for fn in os.listdir(TD)}
INFO = {}
for name in ACC:
    for m in load(name)["_markets"]:
        if m["condition"] in have and m["condition"] not in INFO:
            fin = m.get("final") or {}; w = [o for o, v in fin.items() if float(v or 0) > 0.5]
            INFO[m["condition"]] = dict(event=m["event"], closed=m["closed_at"], q=m["question"], winner=w[0] if w else None, vol=m["vol"])
def check_time(tclose):
    return int(dt.datetime.fromtimestamp(tclose, ET).replace(hour=12, minute=0, second=0, microsecond=0).timestamp())
def pw_rows(c):
    """tape as (t, price of the eventual winner implied by the trade, usd, taker wallet, taker bought winner?)"""
    w = INFO[c]["winner"]; out = []
    for t, p, s, o, sd, wal in tape(c):
        pw = p if o == w else 1 - p
        bought_w = (o == w) == (sd == "BUY")
        out.append((t, pw, s * p, wal, bought_w, s))
    return out
def jump(c):
    rows = pw_rows(c); last = None
    for i, r in enumerate(rows):
        if r[1] < 0.90: last = i
    if last is None: return (rows[0][0] if rows else None), None
    if last + 1 >= len(rows): return None, rows[last][1]
    return rows[last + 1][0], rows[last][1]
JUMP = {c: jump(c) for c in INFO if INFO[c]["winner"]}
def ekey(c): return (INFO[c]["event"], check_time(INFO[c]["closed"]))
APP = {}
groups = collections.defaultdict(list)
for c in JUMP:
    if "debut" in (INFO[c]["event"] or ""): groups[ekey(c)].append(c)
for k, cs in groups.items():
    chk = k[1]; APP[k] = None
    for back in range(0, 8):
        lo, hi = chk - 36 * 3600 - back * 86400, chk - 12 * 3600 - back * 86400
        cand = sorted((JUMP[c][0], JUMP[c][1]) for c in cs if JUMP[c][0] and JUMP[c][1] is not None and lo <= JUMP[c][0] <= hi)
        ts = [t for t, _ in cand]
        clus = [t for i, t in enumerate(ts) if bisect.bisect_right(ts, t + 900) - i >= 2]   # two siblings settle within 15 min
        big = [t for t, p in cand if p <= 0.80]                                              # or one jump of >= 10 cents
        pick = clus[:1] + big[:1]
        if pick: APP[k] = min(pick); break
def appearance(c): return APP.get(ekey(c)) if "debut" in (INFO[c]["event"] or "") else None
NAMES = {v: k for k, v in ACC.items()}
if __name__ == "__main__":
    league = collections.defaultdict(lambda: collections.defaultdict(float)); out = open("race.txt", "w")
    P = lambda *a: print(*a, file=out)
    tot_ev = 0
    for k in sorted(APP, key=lambda k: k[1]):
        t0 = APP[k]; cs = groups[k]
        if not t0: P(f"\n== {k[0][:70]} check {f(k[1])}: no qualifying jump among {len(cs)} cached siblings"); continue
        tot_ev += 1
        rows = []
        for c in cs:
            pre = [r for r in pw_rows(c) if r[0] < t0 - 5]
            p0 = pre[-1][1] if pre else None
            for t, pw, usd, wal, bw, sh in pw_rows(c):
                if t0 - 5 <= t <= k[1] and bw and pw < 0.97: rows.append((t, wal, pw, sh, c, p0))
        rows.sort()
        by = collections.OrderedDict()
        for t, wal, pw, sh, c, p0 in rows:
            a = by.setdefault(wal, dict(first=t, sh=0.0, cost=0.0, n=0, mk=set(), sh60=0.0, cost60=0.0)); a["sh"] += sh; a["cost"] += sh * pw; a["n"] += 1; a["mk"].add(c)
            if t <= t0 + 60: a["sh60"] += sh; a["cost60"] += sh * pw
        edge = sum(a["sh"] - a["cost"] for a in by.values()); e60 = sum(a["sh60"] - a["cost60"] for a in by.values()); e600 = sum(sh * (1 - pw) for t, wal, pw, sh, c, p0 in rows if t <= t0 + 600)
        P(f"\n== {k[0][:70]}  appearance {fs(t0)} UTC ({dt.datetime.fromtimestamp(t0, ET).strftime('%a %H:%M ET')}), check {f(k[1])}, {len(cs)} cached siblings; winner bought <0.97 until the check: ${sum(a['cost'] for a in by.values()):.0f}, edge ${edge:.0f} (first 60 s ${e60:.0f}, first 10 min ${e600:.0f})")
        for i, (wal, a) in enumerate(by.items()):
            L = league[wal]; L["events"] += 1; L["edge"] += a["sh"] - a["cost"]; L["cost"] += a["cost"]; L["edge60"] += a["sh60"] - a["cost60"]; L["rank_sum"] += i + 1; L["first" if i == 0 else "notfirst"] += 1
            L["fee"] += sum(sh * 0.05 * pw * (1 - pw) for t, w2, pw, sh, c, p0 in rows if w2 == wal)
            if a["first"] <= t0 + 600: L["in10m"] += 1
            if i < 6: P(f"   #{i+1} {NAMES.get(wal, wal[:10]):14} +{a['first']-t0:6.0f}s  fills {a['n']:3d} mkts {len(a['mk']):2d} cost {a['cost']:7.0f} avg_px {a['cost']/a['sh']:.3f} edge {a['sh']-a['cost']:7.0f}")
    P(f"\n===== league over {tot_ev} debut events with a jump (taker buys of the eventual winner below 0.97, from the appearance to the check)")
    P(f"{'wallet':16} {'events':>6} {'first':>5} {'in10m':>5} {'cost':>8} {'edge':>8} {'fee':>6} {'edge60s':>8} {'avg_rank':>8}")
    for wal, L in sorted(league.items(), key=lambda x: -x[1]["edge"])[:25]:
        P(f"{NAMES.get(wal, wal[:14]):16} {int(L['events']):6d} {int(L['first']):5d} {int(L['in10m']):5d} {L['cost']:8.0f} {L['edge']:8.0f} {L['fee']:6.0f} {L['edge60']:8.0f} {L['rank_sum']/L['events']:8.1f}")
    P(f"all wallets: edge {sum(L['edge'] for L in league.values()):.0f}, of which first 60 s {sum(L['edge60'] for L in league.values()):.0f}; distinct wallets {len(league)}")
    out.close()

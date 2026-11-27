"""How fast does the Fed-December decision market reprice after US data releases (jobs 11-06, CPI 11-10, PPI 11-13, PCE 11-25)?
Tape = taker fills; block time ~2-3 s after match."""
import json, sys, os, calendar, time, collections, datetime as dt
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import gamma, dataapi
OUT = "/home/user/polymarket-lab/data/econ_tapes"
ts = lambda s: calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M"))
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
e = gamma.event_by_slug("fed-decision-in-december-20260729232808632")
ms = sorted(e["markets"], key=lambda m: -float(m.get("volumeNum") or 0))[:2]
REL = [("jobs Oct", ts("2026-11-06 13:30")), ("CPI Oct", ts("2026-11-10 13:30")), ("PPI Oct", ts("2026-11-13 13:30")), ("PCE Oct", ts("2026-11-25 13:30")), ("ISM mfg", ts("2026-11-02 15:00")), ("ISM svc", ts("2026-11-04 15:00"))]
floor = ts("2026-11-01 00:00")
names = {}
for m in ms:
    p = f"{OUT}/fedDec_{m['conditionId']}.json"
    if os.path.exists(p): rows = json.load(open(p))
    else:
        rows = []
        for r in dataapi.iter_trades(condition=m["conditionId"], max_rows=400000):
            if r["timestamp"] < floor: break
            rows.append([r["timestamp"], r["proxy_wallet"], r["side"], r.get("outcome_index"), float(r["price"]), float(r["size"]), r.get("name") or ""])
        json.dump(rows, open(p, "w"))
    rows.sort()
    print(f"\n### {m['slug'][:70]} vol={float(m['volumeNum']):.0f} rows since 11-01: {len(rows)}")
    yes = [(t, (px if oi == 0 else 1 - px), sz, (side == "BUY") == (oi == 0), w, n) for t, w, side, oi, px, sz, n in rows]   # Yes-equivalent price; taker long Yes?
    def px_at(t):
        last = None
        for r in yes:
            if r[0] > t: break
            last = r[1]
        return last
    for name, T in REL:
        p0 = px_at(T - 1); p5 = px_at(T + 8); p30 = px_at(T + 33); p5m = px_at(T + 300); p1h = px_at(T + 3600); p6h = px_at(T + 21600)
        if p0 is None: continue
        win = [r for r in yes if T <= r[0] < T + 3600]
        first = win[0][0] - T if win else None
        # taker P&L marked at the +1h price, by lag bucket
        bk = collections.OrderedDict((k, [0, 0.0, 0.0]) for k in ("0-8s", "8-33s", "33s-5m", "5m-1h"))
        tk = collections.defaultdict(float)
        for t, p, sz, lw, w, n in win:
            lag = t - T; k = "0-8s" if lag < 8 else "8-33s" if lag < 33 else "33s-5m" if lag < 300 else "5m-1h"
            pnl = (p1h - p) * sz * (1 if lw else -1) - 0.01 * p * (1 - p) * sz
            b = bk[k]; b[0] += 1; b[1] += p * sz if lw else (1 - p) * sz; b[2] += pnl
            if lag < 33: tk[(w, n)] += pnl
        print(f"  {name:8} T={f(T)} yes: pre={p0:.3f} +5s={p5:.3f} +30s={p30:.3f} +5m={p5m:.3f} +1h={p1h:.3f} +6h={p6h:.3f} first fill lag={first}s | " + " ".join(f"{k}: n={v[0]} usd={v[1]:.0f} pnl@1h={v[2]:.0f}" for k, v in bk.items()))
        top = sorted(tk.items(), key=lambda kv: -abs(kv[1]))[:4]
        print("           first-33s takers: " + "; ".join(f"{n[:14] or w[:8]} {v:+.0f}" for (w, n), v in top))

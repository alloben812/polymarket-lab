"""Sceptic (lighter, fourth account, tied on confidence 3): Ahpo. FIFO round trips in economics-keyword markets in two
windows (Jun-Aug fetched fresh, Sep-Nov from the analyst's cached raw fills), by event with the three best removed;
taker fills in the first 60 s after 12:30/13:30/18:00/19:00 UTC; the 11-06 story against the raw December tape."""
import pickle, os, re, collections, math, json, datetime as dt, glob
from pmlab import wallet as W
A = "0xcdb1f1ef8213c06911e4ba6a884176c5571e276c"
ECON = re.compile(r"(fed|fomc|interest-rate|rate-cut|rate-hike|bps|cpi|inflation|jobs|payroll|unemployment|gdp|recession|ecb|bank-of-|pce|ppi|treasury|overheating|ism-)", re.I)
f_ = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
tstat = lambda v: (sum(v) / len(v)) / math.sqrt(sum((x - sum(v) / len(v)) ** 2 for x in v) / (len(v) - 1) / len(v)) if len(v) > 2 else float("nan")
cp = "/home/user/polymarket-lab/data/econ_tapes/sceptic_ahpo_jun_aug.pkl"
if os.path.exists(cp): F1 = pickle.load(open(cp, "rb"))
else:
    F1, tr = W.fetch_fills(A, 1780272000, 1788134400, 200000); pickle.dump(F1, open(cp, "wb"))
F2 = pickle.load(open("/home/user/polymarket-lab/data/econ_tapes/fills_Ahpo.pkl", "rb"))
for lab, F in (("Jun-Aug", F1), ("Sep-Nov", F2)):
    E = sorted([f for f in F if ECON.search((f.get("event_slug") or "") + " " + (f.get("slug") or ""))], key=lambda f: f["timestamp"])
    usd = sum(f["size"] * f["price"] for f in E)
    lots = collections.defaultdict(list); ev = collections.defaultdict(float); real = cost = 0.0; holds = []; old = 0.0; unsold = 0.0
    for f in E:
        k = f["token_id"]; e = f.get("event_slug") or f["slug"]
        if f["side"] == "BUY": lots[k].append([f["size"], f["price"], f["timestamp"], e])
        else:
            s = f["size"]
            while s > 1e-9 and lots[k]:
                L = lots[k][0]; q = min(s, L[0]); p = q * (f["price"] - L[1]); real += p; cost += q * L[1]; ev[e] += p; holds.append((q * L[1], f["timestamp"] - L[2]))
                L[0] -= q; s -= q
                if L[0] <= 1e-9: lots[k].pop(0)
            old += s * f["price"]
    unsold = sum(L[0] * L[1] for v in lots.values() for L in v)
    holds.sort(key=lambda x: x[1]); half = sum(h[0] for h in holds) / 2; acc = 0; med = None
    for c_, h in holds:
        acc += c_
        if acc >= half: med = h; break
    xs = sorted(ev.items(), key=lambda kv: -kv[1]); v = [x[1] for x in xs]
    tk = [f for f in E if f["role"] == "T" and (f["timestamp"] % 86400) in range(45000, 45061) or f["role"] == "T" and (f["timestamp"] % 86400) in range(48600, 48661) or f["role"] == "T" and (f["timestamp"] % 86400) in range(64800, 64861) or f["role"] == "T" and (f["timestamp"] % 86400) in range(68400, 68461)]
    print(f"{lab}: fills {len(F)}, economics fills {len(E)} ${usd:.0f}, maker share of econ $ {100*sum(f['size']*f['price'] for f in E if f['role']=='M')/usd:.0f}%")
    print(f"   FIFO round trips: cost {cost:.0f}, realised {real:.0f} ({100*real/cost if cost else 0:.2f}% of cost); sells of older inventory ${old:.0f}; unsold cost {unsold:.0f}; dollar-weighted median hold {med/3600 if med else 0:.1f} h")
    print(f"   by event: {len(v)} events, positive {sum(1 for x in v if x>0)}, t {tstat(v):.2f}; top3 {sum(v[:3]):.0f}; rest {sum(v[3:]):.0f} (t {tstat(v[3:]):.2f})")
    print("      best:", [(k[:36], round(x)) for k, x in xs[:4]], "worst:", [(k[:36], round(x)) for k, x in xs[-3:]])
    print(f"   taker fills in the first 60 s after 12:30/13:30/18:00/19:00 UTC: {len(tk)}, ${sum(f['size']*f['price'] for f in tk):.0f}")
    for f in sorted(tk, key=lambda f: -f["size"] * f["price"])[:5]: print(f"      {f_(f['timestamp'])} {f['side']} {f['outcome']} {f['size']:.0f} @ {f['price']:.3f} ${f['size']*f['price']:.0f} {f['slug'][:55]}")
# 11-06 story against the raw tape
T = 1794058200  # 2026-11-06 13:30:00 UTC
for p in glob.glob("/home/user/polymarket-lab/data/econ_tapes/fedDec_*.json"):
    rows = sorted(json.load(open(p)))
    w = [r for r in rows if T - 30 <= r[0] <= T + 60]
    mine = [r for r in w if r[1].lower() == A]
    if not mine: continue
    pre = [r for r in rows if r[0] < T][-1]
    print(f"\nDecember market tape {os.path.basename(p)[:20]}: last print before 13:30:00 {pre[4]:.3f} (outcome {pre[3]}); fills 13:30:00-13:31:00: {len([r for r in w if r[0]>=T])}")
    agg = collections.OrderedDict()
    for r in w:
        if r[0] < T: continue
        k = r[0] - T; a = agg.setdefault(k, [0.0, 0.0, 0.0]); y = r[4] if r[3] == 0 else 1 - r[4]; a[0] += r[5] * y; a[1] += r[5]; a[2] += (r[5] * y if r[1].lower() == A else 0)
    print("   second: yes-equivalent VWAP, $ traded, of which Ahpo:", "; ".join(f"+{k}s {v[0]/v[1]:.3f} ${v[0]:.0f} ({v[2]:.0f})" for k, v in list(agg.items())[:16]))
    for h in (300, 3600, 86400):
        later = [r for r in rows if r[0] >= T + h][:1]
        if later: print(f"   price {h//60} min later: {(later[0][4] if later[0][3]==0 else 1-later[0][4]):.3f}")

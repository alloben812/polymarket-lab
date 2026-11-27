"""Sceptic: perfectnostalgia economics P&L (pmlab.wallet resolved complete markets) split by the price it paid
(dollar-weighted buy price per market) and by kind of event, three quarters. Plus the last fills in the August CPI 3.4% market."""
import json, pickle, collections, re, datetime as dt, math
F = pickle.load(open("/home/user/polymarket-lab/data/econ_tapes/sceptic_perfect_fills.pkl", "rb"))
f_ = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
by = collections.defaultdict(list)
for f in F: by[f["condition_id"]].append(f)
CB = re.compile(r"fed|ecb|bank-of|boe|rba|reserve-bank|interest-rate|rate-(hike|cut)|bps|decision", re.I)
tstat = lambda v: (sum(v) / len(v)) / math.sqrt(sum((x - sum(v) / len(v)) ** 2 for x in v) / (len(v) - 1) / len(v)) if len(v) > 2 else float("nan")
W = {"Mar-May": (1772323200, 1780185600), "Jun-Aug": (1780185600, 1788134400), "Sep-Nov": (1788190740, 1795793940)}
for lab, path in (("Mar-May", "perfectnosta_mar_may.json"), ("Jun-Aug", "perfectnosta_jun_aug.json"), ("Sep-Nov", "../perfectnosta_88d.json")):
    lo, hi = W[lab]
    ms = [m for m in json.load(open(path))["_markets"] if m.get("resolved") and not m.get("incomplete") and m.get("turnover", 0) > 0 and m["family"] == "economics"]
    cell = collections.defaultdict(lambda: [0, 0.0, 0.0, []])
    for m in ms:
        b = [f for f in by.get(m["condition"], []) if f["side"] == "BUY" and lo <= f["timestamp"] <= hi]
        usd = sum(f["size"] * f["price"] for f in b); sh = sum(f["size"] for f in b)
        vw = usd / sh if sh else None
        band = "no buys" if vw is None else "<0.30" if vw < 0.3 else "0.30-0.70" if vw < 0.7 else ">=0.70"
        kind = "central bank" if CB.search(m["slug"]) else "data release"
        for k in ((kind, band), (kind, "all"), ("all", band)):
            c = cell[k]; c[0] += 1; c[1] += m["turnover"]; c[2] += m["net"]; c[3].append(m["net"])
    print(f"{lab}: economics net {sum(m['net'] for m in ms):.0f}")
    for k in sorted(cell): c = cell[k]; print(f"    {k[0]:13} {k[1]:9} markets {c[0]:3d} turnover {c[1]:8.0f} net {c[2]:8.0f} ({100*c[2]/c[1] if c[1] else 0:6.1f}%) positive {sum(1 for x in c[3] if x>0):3d} t {tstat(c[3]):.2f}")
c = next(c for c, fs in by.items() if "inflation-be-3pt4-in-august" in fs[0]["slug"])
fs = sorted(by[c], key=lambda f: f["timestamp"])
print("\nAugust CPI 3.4%: last six fills (CPI release 09-11 12:30 UTC; PPI release 09-10 12:30 UTC):")
for f in fs[-6:]: print(f"    {f_(f['timestamp'])} {f['role']} {f['side']} {f['outcome']} {f['size']:.0f} @ {f['price']:.3f}")

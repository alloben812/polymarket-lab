"""Sceptic checks for perfectnostalgia: (a) monthly record, (b) per-event clustering in three quarters, (c) six markets
re-derived from raw fills and raw tapes, (d) selection versus a blind buyer of same-priced outcomes in the same event at
the same moment (88-day window, release-event markets with cached tapes)."""
import json, pickle, os, re, math, collections, calendar, time, datetime as dt, bisect, sys
from pmlab import wallet as W, dataapi
A = "0x0ffcad4963e25dc150774363f4061ebe840c8236"
f_ = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M")
def tstat(v):
    n = len(v); mu = sum(v) / n; s = sum((x - mu) ** 2 for x in v) / (n - 1); return mu / math.sqrt(s / n) if s > 0 else float("nan")
# (a) monthly
mon = []
for line in open("../perfectnosta.monthly.txt"):
    p = line.split()
    if len(p) == 9 and re.match(r"20\d\d-\d\d", p[0]): mon.append((p[0], float(p[5].replace(",", "")), float(p[7].replace(",", ""))))
k = [m[1] for m in mon]
print(f"(a) months {len(k)}, positive {sum(1 for x in k if x > 0)}, sum {sum(k):.0f}, t of monthly kept {tstat(k):.2f}; without the 3 best months sum {sum(sorted(k)[:-3]):.0f}, t {tstat(sorted(k)[:-3]):.2f}; kept/volume by year: " +
      ", ".join(f"{y}: {sum(m[1] for m in mon if m[0][:4]==y):.0f}/{sum(m[2] for m in mon if m[0][:4]==y):.0f}={100*sum(m[1] for m in mon if m[0][:4]==y)/sum(m[2] for m in mon if m[0][:4]==y):.1f}%" for y in ("2024", "2025", "2026")))
last12 = k[-12:]; print(f"    last 12 months: positive {sum(1 for x in last12 if x>0)}, t {tstat(last12):.2f}; worst month {min(k):.0f}, best {max(k):.0f} ({100*max(k)/sum(k):.0f}% of all)")
# fills for three quarters
cp = "/home/user/polymarket-lab/data/econ_tapes/sceptic_perfect_fills.pkl"
if os.path.exists(cp): F = pickle.load(open(cp, "rb"))
else:
    F, _ = W.fetch_fills(A, 1772323200, 1795824000, 200000); pickle.dump(F, open(cp, "wb"))
print("fills Mar-Nov:", len(F))
ev_of = {f["condition_id"]: (f.get("event_slug") or f["slug"]) for f in F}
# (b) per event
for lab, path in (("Mar-May", "perfectnosta_mar_may.json"), ("Jun-Aug", "perfectnosta_jun_aug.json"), ("Sep-Nov", "../perfectnosta_88d.json")):
    ms = [m for m in json.load(open(path))["_markets"] if m.get("resolved") and not m.get("incomplete") and m.get("turnover", 0) > 0 and m["family"] == "economics"]
    by = collections.defaultdict(float)
    for m in ms: by[ev_of.get(m["condition"], m["slug"])] += m["net"]
    xs = sorted(by.items(), key=lambda kv: -kv[1]); v = [x[1] for x in xs]
    print(f"(b) {lab}: economics markets {len(ms)} net {sum(v):.0f}; events {len(v)}, positive {sum(1 for x in v if x>0)}, t by event {tstat(v):.2f}; top3 events {sum(v[:3]):.0f}; rest {sum(v[3:]):.0f} (t {tstat(v[3:]):.2f})")
    print("      best:", [(k_[:34], round(x)) for k_, x in xs[:3]], "worst:", [(k_[:34], round(x)) for k_, x in xs[-3:]])
# (c) raw re-derivation
src = open("../release_analysis_v2.py").read(); ns = {}
exec("import calendar, time\ndef ts(s): return calendar.timegm(time.strptime(s, '%Y-%m-%d %H:%M'))\n" + src[src.index("SCHED = ["):src.index("OVERRIDE = {")], ns)
EV = json.load(open("../release_events.json")); TAPES = "/home/user/polymarket-lab/data/econ_tapes"
info = {}
for e in EV:
    T = ns["sched_T"](e["slug"])
    for m in e["markets"]:
        pr = [float(x) for x in json.loads(m["prices"])] if m.get("prices") else None
        info[m["cond"]] = {"ev": e["slug"], "T": T, "win": (None if not pr or max(pr) < 0.99 else pr.index(max(pr))), "slug": m["slug"]}
tape_cache = {}
def tape(c):
    if c not in tape_cache:
        p = f"{TAPES}/{c}.json"
        rows = sorted(json.load(open(p))) if os.path.exists(p) else []
        tape_cache[c] = ([r[0] for r in rows], [(r[4] if r[3] == 0 else 1 - r[4]) for r in rows], rows)
    return tape_cache[c]
def yes_px(c, t):
    ts_, px, _ = tape(c); i = bisect.bisect_left(ts_, t) - 1
    return px[i] if i >= 0 else None
want = ["ecb-announce-no-change-at-the-october", "inflation-be-3pt4-in-august", "inflation-be-3pt7-in-september", "inflation-be-3pt6-in-september", "core-cpi-mom-be-0pt2-in-september", "bank-of-england.*25.*november|boe.*november", "no-change-in-fed-interest-rates-after-the-october"]
print("\n(c) raw fills + raw tape per market (prices are for the outcome it bought)")
for w in want:
    cs = collections.Counter(f["condition_id"] for f in F if re.search(w, f["slug"]) and f["condition_id"] in info)
    if not cs: print("   not found in release events:", w); continue
    c = cs.most_common(1)[0][0]; I = info[c]; T = I["T"]
    fs = sorted([f for f in F if f["condition_id"] == c], key=lambda f: f["timestamp"])
    b = [f for f in fs if f["side"] == "BUY"]; s = [f for f in fs if f["side"] == "SELL"]
    out = collections.Counter(f["outcome"] for f in b).most_common(1)[0][0]; oi = 0 if out == "Yes" else 1
    bo = [f for f in b if f["outcome"] == out]
    usd = sum(f["size"] * f["price"] for f in bo); sh = sum(f["size"] for f in bo)
    ts_, px, rows = tape(c); conv = lambda p: p if oi == 0 else 1 - p
    span = [(r[5], conv(r[4] if r[3] == 0 else 1 - r[4])) for r in rows if bo[0]["timestamp"] <= r[0] <= bo[-1]["timestamp"] and r[1] != A]
    mv = sum(a * p for a, p in span) / sum(a for a, p in span) if span else float("nan")
    fin = 1.0 if I["win"] == oi else 0.0
    after = [f for f in fs if T and f["timestamp"] >= T]
    pts = {lab: (conv(yes_px(c, T - d)) if yes_px(c, T - d) is not None else None) for lab, d in (("30d", 30 * 86400), ("7d", 7 * 86400), ("1d", 86400), ("1h", 3600), ("1min", 60))}
    sold = sum(f["size"] for f in s if f["outcome"] == out); sold_usd = sum(f["size"] * f["price"] for f in s if f["outcome"] == out)
    pnl = sum(((fin - f["price"]) if f["side"] == "BUY" else (f["price"] - fin)) * f["size"] * (1 if f["outcome"] == out else 0) for f in fs) + sum(((1 - fin) - f["price"]) * f["size"] * (1 if f["side"] == "BUY" else -1) for f in fs if f["outcome"] != out)
    print(f"  {I['slug'][:70]} [{out}] release {f_(T)} final {fin:.0f}")
    print(f"     buys {len(bo)} ({sum(1 for f in bo if f['role']=='T')} taker, ${sum(f['size']*f['price'] for f in bo if f['role']=='T'):.0f}) {f_(bo[0]['timestamp'])} .. {f_(bo[-1]['timestamp'])}: {sh:.0f} sh, ${usd:.0f}, VWAP {usd/sh:.3f}; everyone else in the same span VWAP {mv:.3f} ({len(span)} tape fills)")
    print(f"     tape price before release: " + ", ".join(f"{k_} {v:.3f}" if v is not None else f"{k_} n/a" for k_, v in pts.items()) + f"; first buy {(T-bo[0]['timestamp'])/86400:.1f} d before, last buy {(T-bo[-1]['timestamp'])/3600:.1f} h before")
    print(f"     sold {sold:.0f} sh for ${sold_usd:.0f} (avg {sold_usd/sold if sold else 0:.3f}); fills at or after the release: {len(after)} ({sum(1 for f in after if f['role']=='T')} taker); P&L before fees {pnl:.0f}")
# (d) selection vs blind
print("\n(d) its pre-release buys in release-event markets vs a blind buyer of every same-priced token (+-0.10) in the same event at the same moment")
START = 1795793940 - 88 * 86400
by_ev = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0])
band = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
ev_m = collections.defaultdict(list)
for c, I in info.items(): ev_m[I["ev"]].append(c)
skipped = 0
for f in F:
    c = f["condition_id"]
    if f["timestamp"] < START or f["side"] != "BUY" or c not in info: continue
    I = info[c]
    if I["win"] is None or not I["T"] or f["timestamp"] >= I["T"]: continue
    oi = 0 if f["outcome"] == "Yes" else 1; fin = 1.0 if I["win"] == oi else 0.0
    comp = []
    for c2 in ev_m[I["ev"]]:
        J = info[c2]
        if J["win"] is None: continue
        y = yes_px(c2, f["timestamp"])
        if y is None: continue
        for o2, p2 in ((0, y), (1, 1 - y)):
            if abs(p2 - f["price"]) <= 0.10: comp.append((1.0 if J["win"] == o2 else 0.0) - p2)
    if len(comp) < 2: skipped += 1; continue
    usd = f["size"] * f["price"]; mine = (fin - f["price"]) * f["size"]; blind = f["size"] * sum(comp) / len(comp)
    x = by_ev[I["ev"]]; x[0] += usd; x[1] += mine; x[2] += blind; x[3] += 1
    kb = "<0.30" if f["price"] < 0.3 else "0.30-0.55" if f["price"] < 0.55 else "0.55-0.80" if f["price"] < 0.8 else ">=0.80"
    y_ = band[kb]; y_[0] += usd; y_[1] += mine; y_[2] += blind
tot = [sum(v[i] for v in by_ev.values()) for i in range(3)]
diff = [v[1] - v[2] for v in by_ev.values()]
print(f"   events {len(by_ev)}, fills {sum(v[3] for v in by_ev.values())} (skipped {skipped} with no same-priced comparator): bought ${tot[0]:.0f}; its edge {tot[1]:.0f}; blind same-price edge {tot[2]:.0f}; difference {tot[1]-tot[2]:.0f}, t by event {tstat(diff):.2f}, positive in {sum(1 for d in diff if d>0)}/{len(diff)} events; its own edge t by event {tstat([v[1] for v in by_ev.values()]):.2f}")
for kb, v in sorted(band.items()): print(f"     price {kb:10} bought ${v[0]:7.0f} its edge {v[1]:7.0f} blind {v[2]:7.0f}")
srt = sorted(by_ev.items(), key=lambda kv: -(kv[1][1] - kv[1][2]))
print("   largest differences:", [(k_[:30], round(v[1]), round(v[2])) for k_, v in srt[:4]], "smallest:", [(k_[:30], round(v[1]), round(v[2])) for k_, v in srt[-3:]])
d3 = sorted(diff, reverse=True)[3:]; print(f"   difference without its three best events: {sum(d3):.0f}, t {tstat(d3):.2f}")

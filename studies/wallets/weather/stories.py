"""Event stories for one account: python3 -I stories.py <acct> [n_events].  Times are hours relative to the station's local midnight (h<0 = before the day)."""
import json, sys, collections, math, random, datetime as dt
acct = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 14
F = json.load(open("out/fills.json"))[acct]; MK = json.load(open("out/mk.json")); OBS = json.load(open("out/obs2.json"))
FEE_SWITCH = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc).timestamp()
def whole(t, unit):
    v = t / 10.0 if unit == "C" else t / 10.0 * 9 / 5 + 32
    return math.floor(v + 0.5 + 1e-9)
ev = collections.defaultdict(list)
for r in F:
    d = MK.get(r["condition_id"])
    if d and d["ok"] and d["kind"] == "hi" and d["final"] is not None: ev[d["event"]].append((r, d))
# account-level timing facts
hb = collections.Counter(); uh = collections.Counter(); off = {"LY": collections.Counter(), "LN": collections.Counter()}; net = collections.Counter(); usd = collections.Counter()
for e, lst in ev.items():
    r0, d0 = lst[0]
    obs = [whole(v, d0["unit"]) for t, v, _ in OBS.get(d0["station"], []) if v is not None and d0["est"] <= t < d0["est"] + 86400]
    fin = max(obs) if obs else None
    for r, d in lst:
        h = (r["timestamp"] - d["est"]) / 3600
        b = "<-36" if h < -36 else "-36..-24" if h < -24 else "-24..-12" if h < -12 else "-12..-6" if h < -6 else "-6..0" if h < 0 else "0..9" if h < 9 else "9..12" if h < 12 else "12..15" if h < 15 else "15..24" if h < 24 else ">24"
        p, sh = float(r["price"]), float(r["size"]); v = float(d["final"][r["outcome"]])
        pn = (sh * (v - p) if r["side"] == "BUY" else sh * (p - v)) - ((0.05 if r["timestamp"] < FEE_SWITCH else 0.01) * sh * p * (1 - p) if r["role"] == "T" else 0)
        hb[b] += 1; net[b] += pn; usd[b] += sh * p
        uh[dt.datetime.fromtimestamp(r["timestamp"], dt.timezone.utc).hour] += 1
        ly = (r["side"] == "BUY") == (r["outcome"] == "Yes")
        if fin is not None and -900 < d["lo"] and d["hi"] < 900:
            w = d["hi"] - d["lo"] + 1; o = 0 if d["lo"] <= fin <= d["hi"] else (math.ceil((fin - d["hi"]) / w) if fin > d["hi"] else -math.ceil((d["lo"] - fin) / w))
            off["LY" if ly else "LN"][max(-3, min(3, o))] += sh * p
print(f"## {acct}: {len(ev)} resolved highest-temperature events")
print("fills by hours from local midnight: " + "  ".join(f"[{b}] n={hb[b]} ${usd[b]:.0f} net${net[b]:.0f}" for b in ["<-36", "-36..-24", "-24..-12", "-12..-6", "-6..0", "0..9", "9..12", "12..15", "15..24", ">24"] if hb[b]))
print("fills by UTC hour: " + " ".join(f"{h}:{uh[h]}" for h in range(24)))
for k in ("LY", "LN"):
    tot = sum(off[k].values()) or 1
    print(f"{k} dollars by (final max - bucket) in bucket widths: " + " ".join(f"{o:+d}:{100*off[k][o]/tot:.0f}%" for o in range(-3, 4)))
random.seed(11); names = sorted(ev); random.shuffle(names)
for e in names[:N]:
    lst = sorted(ev[e], key=lambda x: x[0]["timestamp"]); d0 = lst[0][1]
    obs = [(t, whole(v, d0["unit"])) for t, v, _ in OBS.get(d0["station"], []) if v is not None and d0["est"] <= t < d0["est"] + 86400]
    fin = max(w for _, w in obs) if obs else None; tpk = next((t for t, w in obs if w == fin), None)
    print(f"\n{e[23:]} [{d0['station']}] final max {fin}{d0['unit']} first reached at local h={((tpk - d0['est'])/3600 if tpk else float('nan')):.1f}")
    byb = collections.defaultdict(list)
    for r, d in lst: byb[(d["lo"], d["hi"])].append((r, d))
    tot = 0.0
    for (lo, hi), fl in sorted(byb.items()):
        d = fl[0][1]; parts = []; pn = 0.0
        agg = collections.OrderedDict()
        for r, _ in fl:
            k = (r["role"], r["side"], r["outcome"]); a = agg.setdefault(k, [0.0, 0.0, [], 0])
            a[0] += float(r["size"]); a[1] += float(r["size"]) * float(r["price"]); a[2].append((r["timestamp"] - d["est"]) / 3600); a[3] += 1
            p, sh = float(r["price"]), float(r["size"]); v = float(d["final"][r["outcome"]])
            pn += (sh * (v - p) if r["side"] == "BUY" else sh * (p - v)) - ((0.05 if r["timestamp"] < FEE_SWITCH else 0.01) * sh * p * (1 - p) if r["role"] == "T" else 0)
        for k, a in agg.items(): parts.append(f"{k[0]} {k[1]} {k[2]} {a[0]:.0f}@{a[1]/a[0]:.3f} x{a[3]} h={min(a[2]):+.1f}..{max(a[2]):+.1f}")
        tot += pn
        name = (f"<= {hi}" if lo < -900 else f">= {lo}" if hi > 900 else (f"{lo}" if lo == hi else f"{lo}-{hi}"))
        print(f"   bucket {name:>7s} {'WON ' if d['final']['Yes'] == 1 else 'lost'} | " + "; ".join(parts) + f" | net ${pn:+.1f}")
    print(f"   event net ${tot:+.1f}")

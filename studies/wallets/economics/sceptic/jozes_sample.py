"""Sceptic: same spread / market-move split as jozes_tapes.py on a RANDOM sample of its markets (seed fixed before looking),
so the split is not biased by picking winners. Markets with at least 10 of its fills; 30 drawn; tape cap 30,000 rows."""
import pickle, collections, os, random, bisect, json, math
from pmlab import dataapi
A = "0xd0bf186c69a936395c84d6b45bbd39eadfcf9f9f"
fills = pickle.load(open("/home/user/polymarket-lab/data/econ_tapes/sceptic_jozeslemsek.pkl", "rb"))["fills"]
bym = collections.defaultdict(list)
for f in fills: bym[f["condition_id"]].append(f)
elig = sorted(c for c, fs in bym.items() if len(fs) >= 10)
random.seed(20261127); pick = random.sample(elig, 30)
print(f"markets {len(bym)}, with >= 10 fills {len(elig)} (they hold {sum(len(bym[c]) for c in elig)} of {len(fills)} fills); sampled 30")
res = dataapi.resolutions(pick)
rows = []
for c in pick:
    fs = sorted(bym[c], key=lambda f: f["timestamp"])
    cp = f"/home/user/polymarket-lab/data/econ_tapes/sceptic_tape_{c}.pkl"
    if os.path.exists(cp): tape = pickle.load(open(cp, "rb"))
    else:
        tape = [{k: r.get(k) for k in ("timestamp", "proxy_wallet", "side", "outcome", "price", "size")} for r in dataapi.iter_trades(condition=c, max_rows=30000)]
        pickle.dump(tape, open(cp, "wb"))
    if not tape: continue
    tape.sort(key=lambda r: r["timestamp"]); t0 = tape[0]["timestamp"]
    tot = {"spread": 0.0, "real": 0.0, "left_cost": 0.0, "left_val": 0.0, "buy": 0.0}
    for out in {f["outcome"] for f in fs}:
        oth = [(r["timestamp"], (r["price"] if r["outcome"] == out else 1 - r["price"]), r["size"]) for r in tape if r["proxy_wallet"] != A]
        ts_ = [x[0] for x in oth]
        def ref(t, w=7200):
            i, j = bisect.bisect_left(ts_, t - w), bisect.bisect_right(ts_, t + w)
            v = sum(x[2] for x in oth[i:j]); return sum(x[1] * x[2] for x in oth[i:j]) / v if v > 0 else None
        bsh = bus = ssh = sus = 0.0
        for f in fs:
            if f["outcome"] != out or f["timestamp"] < t0: continue
            r = ref(f["timestamp"]); s = f["size"]
            if f["side"] == "BUY": bsh += s; bus += s * f["price"]
            else: ssh += s; sus += s * f["price"]
            if r is not None: tot["spread"] += ((r - f["price"]) if f["side"] == "BUY" else (f["price"] - r)) * s
        m = min(bsh, ssh)
        if m > 0: tot["real"] += m * (sus / ssh - bus / bsh)
        left = bsh - ssh
        if left > 0:
            tot["left_cost"] += left * bus / bsh
            R = res.get(c) or {}
            fin = float(R["final"].get(out) or 0) if R.get("resolved") else (oth[-1][1] if oth else 0)
            tot["left_val"] += left * fin
        tot["buy"] += bus
    tot["slug"] = fs[0]["slug"]; tot["resolved"] = bool((res.get(c) or {}).get("resolved")); rows.append(tot)
S = lambda k: sum(r[k] for r in rows)
print(f"sample of {len(rows)}: bought ${S('buy'):.0f}; realised on matched shares {S('real'):.0f}; spread part {S('spread'):.0f}; market-move part {S('real')-S('spread'):.0f}; unsold cost {S('left_cost'):.0f} worth {S('left_val'):.0f} (final price if resolved, last print if open)")
print(f"   total P&L of the sample {S('real')+S('left_val')-S('left_cost'):.0f}; markets with positive total {sum(1 for r in rows if r['real']+r['left_val']-r['left_cost']>0)}/{len(rows)}; resolved {sum(1 for r in rows if r['resolved'])}")
sp = [r["spread"] for r in rows]; mv = [r["real"] - r["spread"] for r in rows]
t_ = lambda v: (sum(v) / len(v)) / math.sqrt(sum((x - sum(v) / len(v)) ** 2 for x in v) / (len(v) - 1) / len(v))
print(f"   spread part: positive in {sum(1 for x in sp if x>0)} markets, t {t_(sp):.2f}; move part: positive in {sum(1 for x in mv if x>0)}, t {t_(mv):.2f}")
for r in sorted(rows, key=lambda r: -(r["real"])): print(f"   {r['slug'][:58]:58} real {r['real']:6.1f} spread {r['spread']:6.1f} move {r['real']-r['spread']:6.1f} left cost {r['left_cost']:5.1f} val {r['left_val']:5.1f} {'R' if r['resolved'] else 'open'}")

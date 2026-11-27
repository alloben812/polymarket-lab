"""Sceptic check 3 for jozeslemsek: is the profit a dealer's spread or a price move it happened to be long for?
Raw whole-market tapes (fresh from the Data API) for its most profitable markets. For each of its fills the reference is
the volume-weighted price of everybody else's fills within +-2 h (converted to the token it traded).
spread part = sum over buys (ref - price) * size + over sells (price - ref) * size; move part = realised P&L - spread part."""
import pickle, collections, json, os, datetime as dt, bisect, sys
from pmlab import dataapi
A = "0xd0bf186c69a936395c84d6b45bbd39eadfcf9f9f"
d = pickle.load(open("/home/user/polymarket-lab/data/econ_tapes/sceptic_jozeslemsek.pkl", "rb")); fills = d["fills"]
f_ = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M")
bym = collections.defaultdict(list)
for f in fills: bym[f["condition_id"]].append(f)
def cashpnl(fs): return sum((-1 if f["side"] == "BUY" else 1) * f["size"] * f["price"] for f in fs)
top = sorted(bym.items(), key=lambda kv: -cashpnl(kv[1]))[:7]
TOT = collections.defaultdict(float)
for c, fs in top:
    fs.sort(key=lambda f: f["timestamp"]); slug = fs[0]["slug"]
    cp = f"/home/user/polymarket-lab/data/econ_tapes/sceptic_tape_{c}.pkl"
    if os.path.exists(cp): tape = pickle.load(open(cp, "rb"))
    else:
        tape = [{k: r.get(k) for k in ("timestamp", "proxy_wallet", "side", "outcome", "price", "size")} for r in dataapi.iter_trades(condition=c, max_rows=80000)]
        pickle.dump(tape, open(cp, "wb"))
    tape.sort(key=lambda r: r["timestamp"]); t0 = tape[0]["timestamp"]
    out = collections.Counter(f["outcome"] for f in fs).most_common(1)[0][0]
    oth = [(r["timestamp"], (r["price"] if r["outcome"] == out else 1 - r["price"]), r["size"]) for r in tape if r["proxy_wallet"] != A]
    ts_ = [x[0] for x in oth]
    def ref(t, w=7200):
        i, j = bisect.bisect_left(ts_, t - w), bisect.bisect_right(ts_, t + w)
        v = sum(x[2] for x in oth[i:j]); return sum(x[1] * x[2] for x in oth[i:j]) / v if v > 0 else None
    cov = [f for f in fs if f["timestamp"] >= t0 and f["outcome"] == out]
    spread = 0.0; nref = 0; bsh = bus = ssh = sus = 0.0; rb = rs = 0.0; rbw = rsw = 0.0; inv = 0.0; maxinv = 0.0; mk = collections.Counter()
    for f in cov:
        r = ref(f["timestamp"]); s = f["size"]
        if f["side"] == "BUY": bsh += s; bus += s * f["price"]; inv += s
        else: ssh += s; sus += s * f["price"]; inv -= s
        maxinv = max(maxinv, inv); mk[f["role"] + f["side"][0]] += s * f["price"]
        if r is None: continue
        nref += 1
        if f["side"] == "BUY": spread += (r - f["price"]) * s; rb += r * s; rbw += s
        else: spread += (f["price"] - r) * s; rs += r * s; rsw += s
    matched = min(bsh, ssh); realised = matched * ((sus / ssh if ssh else 0) - (bus / bsh if bsh else 0))
    print(f"\n{slug[:78]} [{out}] tape rows {len(tape)} from {f_(t0)}; its fills {len(fs)} ({len(cov)} inside the tape span), whole-life cash {cashpnl(fs):.0f}")
    print(f"   inside the span: bought {bsh:.0f} sh at {bus/bsh if bsh else 0:.4f}, sold {ssh:.0f} sh at {sus/ssh if ssh else 0:.4f}; realised on matched shares {realised:.0f}; left {bsh-ssh:.0f} sh; peak inventory {maxinv:.0f} sh; $ by role/side {dict((k, round(v)) for k, v in mk.items())}")
    print(f"   everyone else's price around its buys {rb/rbw if rbw else float('nan'):.4f}, around its sells {rs/rsw if rsw else float('nan'):.4f}  ->  spread part {spread:.0f}, market-move part {realised-spread:.0f} ({nref} fills with a reference)")
    # weekly path of the market and of its inventory
    wk = collections.OrderedDict()
    for t, p, s in oth:
        k = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d")[:5]
        w = wk.setdefault(dt.datetime.fromtimestamp(t - (t % (7 * 86400)), dt.timezone.utc).strftime("%m-%d"), [0.0, 0.0]); w[0] += p * s; w[1] += s
    print("   market weekly VWAP:", ", ".join(f"{k} {v[0]/v[1]:.4f}" for k, v in list(wk.items())[-9:]))
    TOT["realised"] += realised; TOT["spread"] += spread
print(f"\nTOTAL over these markets: realised {TOT['realised']:.0f}, spread part {TOT['spread']:.0f}, market-move part {TOT['realised']-TOT['spread']:.0f}")

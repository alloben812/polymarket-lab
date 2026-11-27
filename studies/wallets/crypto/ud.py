"""Shared helpers for the crypto wallet study: cached fills, Binance fair values for up/down fills."""
import gzip, json, math, re, collections
from pathlib import Path
from pmlab import wallet as W, fair, fees
from pmlab.px import Px
HERE = Path(__file__).resolve().parent
T0, T1 = 1795219200, 1795737600          # 2026-11-21 00:00 .. 2026-11-27 00:00 UTC (days with Binance 1 s dumps)
DAYS = ["2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26"]
SYM = {"btc": "BTCUSDT", "eth": "ETHUSDT", "sol": "SOLUSDT", "xrp": "XRPUSDT"}
DUR = {"5m": 300, "15m": 900}
_UD = re.compile(r"^([a-z0-9]+)-updown-(\d+[mh])-(\d{9,})$")
_px = {}

def px(asset):
    if asset not in _px:
        _px[asset] = Px.load(SYM[asset], DAYS, fetch=False)
    return _px[asset]

def fills(name, wallet, start=T0, end=T1, cap=60000):
    p = HERE / "fills" / f"{name}_{start}_{end}.json.gz"
    if p.exists():
        return json.load(gzip.open(p, "rt"))
    f, trunc = W.fetch_fills(wallet, start, end, cap)
    d = {"truncated": trunc, "fills": f}
    json.dump(d, gzip.open(p, "wt"))
    return d

def finals(name):
    """condition -> {outcome: final price} from the pmlab.wallet JSON of this account."""
    d = json.load(open(HERE / f"{name}.json"))
    return {m["condition"]: m.get("final") for m in d["_markets"] if m.get("resolved")}

def rate(asset, dur, ts):
    if asset == "btc" and dur in ("5m", "15m"):
        return fees.btc_updown_rate(ts) if dur == "5m" else 0.05
    return 0.01

def enrich(rows, fin):
    """Add up/down fields to fills of btc/eth/sol/xrp 5m/15m markets. Returns the list of enriched rows."""
    out = []
    for r in rows:
        m = _UD.match(r.get("slug") or "")
        if not m or m.group(1) not in SYM or m.group(2) not in DUR:
            continue
        a, d, t0 = m.group(1), m.group(2), int(m.group(3))
        dur = DUR[d]; P = px(a)
        tm = r["timestamp"] - 3
        k = P.twap(t0, 60)
        if k != k:
            continue
        up = r["outcome"] == "Up"
        def f(t):
            v = fair.fair_up(P, t, t0, dur, 60, k)
            return v if up else 1 - v
        s = P.price(min(tm, t0 + dur))
        sig = P.sigma(min(tm, t0 + dur))
        fnl = (fin.get(r["condition_id"]) or {}).get(r["outcome"])
        proxy = None
        a_end = P.twap(t0 + dur, 60)
        if a_end == a_end:
            proxy = 1.0 if ((a_end >= k) == up) else 0.0
        e = dict(r); e.update(asset=a, d=d, t0=t0, t1=t0 + dur, tm=tm, rel=tm - t0, left=t0 + dur - tm, k=k, spot=s,
                         gap_bp=(s / k - 1) * 1e4 * (1 if up else -1), sig=sig, fair=f(tm), fair_m2=f(tm - 2), fair_m5=f(tm - 5), fair_m10=f(tm - 10),
                         fair_p10=f(tm + 10), fair_p30=f(tm + 30), final=fnl if fnl is not None else proxy, final_official=fnl is not None, proxy=proxy,
                         size=float(r["size"]), price=float(r["price"]), fam=f"{a}-{d}")
        e["fee"] = e["size"] * fees.fee_per_share(e["price"], rate(a, d, r["timestamp"])) if r["role"] == "T" else 0.0
        out.append(e)
    return out

def tab(rows, keyfn, valfn=None, title=""):
    """Edge table clustered by market: key -> fills, shares, usd, avg px, realised edge c/sh (se), fair-edge c/sh at fill, at -5 s, +30 s."""
    from pmlab import stats
    g = collections.defaultdict(list)
    for r in rows:
        k = keyfn(r)
        if k is not None:
            g[k].append(r)
    print(f"\n{title}")
    print(f"{'key':28} {'fills':>6} {'mkts':>5} {'shares':>9} {'usd':>9} {'avg_px':>6} {'real_c':>7} {'se':>5} {'fairEdge':>8} {'fair-5s':>7} {'fair+30':>7} {'net$':>9}")
    for k in sorted(g):
        rr = [r for r in g[k] if r["final"] is not None and r["side"] == "BUY"]
        if not rr:
            continue
        bym = collections.defaultdict(lambda: [0.0, 0.0])
        for r in rr:
            bym[r["condition_id"]][0] += r["size"] * (r["final"] - r["price"]) - r["fee"]
            bym[r["condition_id"]][1] += r["size"]
        num = [v[0] for v in bym.values()]; den = [v[1] for v in bym.values()]
        e, se, _ = stats.ratio_cluster(num, den)
        sh = sum(den); usd = sum(r["size"] * r["price"] for r in rr)
        def w(field):
            xs = [(r[field] - r["price"]) * r["size"] for r in rr if r[field] == r[field]]
            ws = sum(r["size"] for r in rr if r[field] == r[field])
            return 100 * sum(xs) / ws if ws else float("nan")
        print(f"{str(k)[:28]:28} {len(rr):6} {len(bym):5} {sh:9.0f} {usd:9.0f} {usd/sh:6.3f} {100*e:7.2f} {100*se if se==se else float('nan'):5.2f} {w('fair'):8.2f} {w('fair_m5'):7.2f} {w('fair_p30'):7.2f} {sum(num):9.0f}")

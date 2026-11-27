"""Threshold (above / hit-price) accounts: speed vs model vs already-decided. Fills of 2026-11-21..26 on BTC/ETH/SOL/XRP."""
import sys, re, json, math, collections, bisect
import numpy as np
import ud
from pmlab import gamma, stats, fees
from pmlab.http import get_json
from pmlab.wallet import _ts
from subfam import subfam, asset_of
ACCTS = {"Eager47259": "0xab155a20ff29debee4128e9dd1ea6ab8541c46e5", "0xDB5": "0xdb5ad26b68d77ae966d29e7180147272ab7a3965",
         "x6916Cc": "0x6916cc00aa1c3e75ecf4081df7cae7d2f3592fd4"}
name = sys.argv[1]
d = ud.fills(name, ACCTS[name]); fin = ud.finals(name); raw = d["fills"]
meta = gamma.markets_by_condition(sorted({r["condition_id"] for r in raw}))
N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
def strike(slug):
    m = re.search(r"-(?:above|reach|dip-to)-(\d+)(?:pt(\d+))?(k?)-", slug)
    if not m: return None
    v = float(m.group(1) + ("." + m.group(2) if m.group(2) else ""))
    return v * 1000 if m.group(3) else v
dvol = {}
for cur in ("BTC", "ETH"):
    r = get_json("https://www.deribit.com/api/v2/public/get_volatility_index_data", {"currency": cur, "start_timestamp": (ud.T0 - 86400) * 1000, "end_timestamp": ud.T1 * 1000, "resolution": 3600}, cache=True)
    dvol[cur.lower()] = sorted((x[0] // 1000, x[4] / 100) for x in r["result"]["data"])
def iv(asset, t):
    s = dvol.get(asset)
    if not s: return float("nan")
    i = bisect.bisect_right(s, (t, 9)) - 1
    return s[max(i, 0)][1]
YEAR = 365 * 86400
_ext = {}
def run_ext(asset, t_from, kind):
    """prefix running max/min of 1 s closes from t_from (cached per asset/start)."""
    key = (asset, t_from, kind)
    if key not in _ext:
        P = ud.px(asset); i = max(t_from - P.t_min, 0)
        a = P.p[i:]
        a = np.where(np.isnan(a), -np.inf if kind == "max" else np.inf, a)
        _ext[key] = (i, np.maximum.accumulate(a) if kind == "max" else np.minimum.accumulate(a))
    return _ext[key]
def rv(asset, t, look=86400):
    """annualised realised vol from 60 s returns over the previous `look` seconds."""
    P = ud.px(asset); j = t - P.t_min; i = max(j - look, 0)
    a = P.p[i:j:60]; a = a[~np.isnan(a)]
    if len(a) < 100: return float("nan")
    lr = np.diff(np.log(a)); return float(np.sqrt(np.mean(lr * lr) / 60 * YEAR))
rows = []
for r in raw:
    md = meta.get(r["condition_id"]) or {}; slug = r.get("slug") or ""
    sf = subfam(slug, r.get("title") or ""); a, kind = sf.split("-", 1) if "-" in sf else (sf, "")
    if a not in ud.SYM or kind not in ("above", "hit"): continue
    K = strike(slug); t_end = _ts(md.get("endDate")); t_start = _ts(md.get("startDate"))
    if not K or not t_end or not t_start: continue
    P = ud.px(a); tm = r["timestamp"] - 3; S = P.price(tm)
    if S != S: continue
    dirn = -1 if "dip-to" in slug else 1
    yes = r["outcome"] == "Yes"; buy = r["side"] == "BUY"
    sign = dirn * (1 if yes else -1) * (1 if buy else -1)      # +1: the trade gains when spot rises
    sig_r, sig_i = rv(a, tm), iv(a, tm)
    T = max(t_end - tm, 1) / YEAR
    def model(sig, S=S, t=tm):
        if sig != sig: return float("nan")
        T = max(t_end - t, 1) / YEAR
        if kind == "above":
            return N(math.log(S / K) / (sig * math.sqrt(T)))
        return min(1.0, 2 * N(-abs(math.log(K / S)) / (sig * math.sqrt(T))))
    hit_t = None
    if kind == "hit":
        i0, ext = run_ext(a, t_start, "max" if dirn > 0 else "min")
        j = tm - P.t_min - i0
        cond = (ext >= K) if dirn > 0 else (ext <= K)
        if cond.any():
            hit_t = int(np.argmax(cond)) + i0 + P.t_min
        hit_before = hit_t is not None and hit_t <= tm
    else:
        hit_before = False
    pm_r, pm_i = (1.0 if hit_before else model(sig_r)), (1.0 if hit_before else model(sig_i))
    size, price = float(r["size"]), float(r["price"])
    def val(p):   # value of the traded outcome under a Yes-probability p
        return p if yes else 1 - p
    f = (fin.get(r["condition_id"]) or {}).get(r["outcome"])
    ret = lambda dt_: (S / P.price(tm - dt_) - 1) * 1e4 * sign if P.price(tm - dt_) == P.price(tm - dt_) else float("nan")
    fwd = lambda dt_: (P.price(tm + dt_) / S - 1) * 1e4 * sign if P.price(tm + dt_) == P.price(tm + dt_) else float("nan")
    e = dict(slug=slug, cond=r["condition_id"], asset=a, kind=kind, K=K, dirn=dirn, tm=tm, t_start=t_start, t_end=t_end, left=t_end - tm, S=S, dist_pct=(K / S - 1) * 100,
             outcome=r["outcome"], side=r["side"], role=r["role"], size=size, price=price, sign=sign, hit_before=hit_before, hit_t=hit_t,
             since_hit=(tm - hit_t) if hit_t is not None else None, m_rv=val(pm_r), m_iv=val(pm_i), final=f,
             pre5=ret(5), pre30=ret(30), pre300=ret(300), fwd60=fwd(60), fwd600=fwd(600),
             fee=size * fees.fee_per_share(price, 0.01) if r["role"] == "T" else 0.0)
    rows.append(e)
print(f"== {name}: fills {len(raw)} (truncated={d['truncated']}), above/hit fills on BTC/ETH/SOL/XRP with price data: {len(rows)}")
def table(rs, keyfn, title):
    g = collections.defaultdict(list)
    for r in rs:
        k = keyfn(r)
        if k is not None: g[k].append(r)
    print(f"\n{title}\n{'key':40} {'fills':>6} {'mkts':>5} {'usd':>9} {'avg_px':>6} {'pre5bp':>7} {'pre30':>6} {'pre300':>7} {'fwd60':>6} {'fwd600':>7} {'mdl_rv_c':>8} {'mdl_iv_c':>8} {'real_c':>7} {'se':>5} {'net$':>8}")
    for k in sorted(g):
        rr = g[k]; w = np.array([x["size"] for x in rr]); usd = sum(x["size"] * x["price"] for x in rr)
        def wm(f, scale=1.0):
            v = np.array([x[f] for x in rr], float); ok = ~np.isnan(v)
            return float((v[ok] * w[ok]).sum() / w[ok].sum()) * scale if ok.any() else float("nan")
        sg = lambda x: 1 if x["side"] == "BUY" else -1
        def edge(f):
            v = np.array([(x[f] - x["price"]) * sg(x) for x in rr], float); ok = ~np.isnan(v)
            return float((v[ok] * w[ok]).sum() / w[ok].sum()) * 100 if ok.any() else float("nan")
        bym = collections.defaultdict(lambda: [0.0, 0.0])
        for x in rr:
            if x["final"] is None: continue
            bym[x["cond"]][0] += x["size"] * (x["final"] - x["price"]) * sg(x) - x["fee"]; bym[x["cond"]][1] += x["size"]
        e, se, _ = stats.ratio_cluster([v[0] for v in bym.values()], [v[1] for v in bym.values()]) if bym else (float("nan"),) * 3
        print(f"{str(k)[:40]:40} {len(rr):6} {len({x['cond'] for x in rr}):5} {usd:9.0f} {usd/w.sum():6.3f} {wm('pre5'):7.2f} {wm('pre30'):6.2f} {wm('pre300'):7.2f} {wm('fwd60'):6.2f} {wm('fwd600'):7.2f} {edge('m_rv'):8.2f} {edge('m_iv'):8.2f} {100*e:7.2f} {100*se if se==se else float('nan'):5.2f} {sum(v[0] for v in bym.values()):8.0f}")
table(rows, lambda r: (r["kind"], r["role"], r["side"], r["outcome"]), "by type, role, side, outcome   (pre/fwd = spot move in bp signed in the trade's favour; mdl = model value - price, c/share, signed for the side)")
def pb(p): return "0.00-0.05" if p < .05 else "0.05-0.30" if p < .3 else "0.30-0.70" if p < .7 else "0.70-0.95" if p < .95 else "0.95-1.00"
table([r for r in rows if r["side"] == "BUY"], lambda r: (r["kind"], r["role"], pb(r["price"])), "BUYS by type, role, price")
def lb(l): return "a >3d" if l > 3 * 86400 else "b 1-3d" if l > 86400 else "c 6-24h" if l > 6 * 3600 else "d 1-6h" if l > 3600 else "e 10-60m" if l > 600 else "f <10m" if l > 0 else "g after end"
table([r for r in rows if r["side"] == "BUY"], lambda r: (r["kind"], r["role"], lb(r["left"])), "BUYS by type, role, time left")
hit = [r for r in rows if r["kind"] == "hit"]
def hb(r):
    if r["hit_t"] is None: return "never hit in data"
    s = r["since_hit"]
    return "before hit >1h" if s < -3600 else "before hit 10-60m" if s < -600 else "before hit 1-10m" if s < -60 else "before hit 0-60s" if s < 0 else "after hit 0-10s" if s < 10 else "after hit 10-60s" if s < 60 else "after hit 1-10m" if s < 600 else "after hit >10m"
table(hit, lambda r: (r["role"], r["side"], r["outcome"], hb(r)), "HIT markets: timing relative to the first 1 s Binance close through the barrier")
json.dump(rows, open(ud.HERE / "out" / f"thr_{name}.json", "w"))

"""Polymarket crypto threshold prices vs risk-neutral digitals implied by Deribit option marks (protocol.md Q2)."""
import json, time, urllib.request, gzip, math, sys, datetime as dt, collections, bisect
G = "https://gamma-api.polymarket.com"; C = "https://clob.polymarket.com"; D = "https://www.deribit.com/api/v2/public"
def get(url, data=None):
    last = None
    for i in range(4):
        try:
            h = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Accept-Encoding": "gzip"}; body = None
            if data is not None: body = json.dumps(data).encode(); h["Content-Type"] = "application/json"
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=60) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
                return json.loads(b)
        except Exception as e: last = e; time.sleep(1.5 * (i + 1))
    raise SystemExit(f"{url}: {last}")
N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
def call(F, K, w):  # undiscounted Black-76 call, w = total variance
    if w <= 0: return max(F - K, 0.0)
    s = math.sqrt(w); d1 = (math.log(F / K) + 0.5 * w) / s; return F * N(d1) - K * N(d1 - s)
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
def surface(cur):
    rows = get(f"{D}/get_book_summary_by_currency?currency={cur}&kind=option")["result"]; exp = collections.defaultdict(dict)
    for x in rows:
        _, e, k, cp = x["instrument_name"].split("-"); k = float(k)
        day = int(e[:-5]); t = dt.datetime(2000 + int(e[-2:]), MON[e[-5:-2]], day, 8, tzinfo=dt.timezone.utc).timestamp()
        F = x["underlying_price"]; otm = (cp == "P" and k <= F) or (cp == "C" and k > F)
        d = exp[t].setdefault(k, {}); d["F"] = F
        if otm or "iv" not in d: d["iv"] = x["mark_iv"] / 100.0; d["bid"] = x.get("bid_price"); d["ask"] = x.get("ask_price"); d["cp"] = cp
    return exp
def iv_at(sm, K):
    ks = sorted(sm); i = bisect.bisect_left(ks, K)
    if i == 0: return sm[ks[0]]["iv"]
    if i >= len(ks): return sm[ks[-1]]["iv"]
    a, b = ks[i - 1], ks[i]; return sm[a]["iv"] + (sm[b]["iv"] - sm[a]["iv"]) * (K - a) / (b - a)
def digital(exp, T, K, now, basis, h):
    ts = sorted(t for t in exp if t > now + 600)
    def w_at(k):
        lo = [t for t in ts if t <= T]; hi = [t for t in ts if t > T]
        if not lo:  # before the first listed expiry: flat-vol scaling of the first expiry
            t1 = hi[0]; return iv_at(exp[t1], k) ** 2 * (T - now) / 31557600
        if not hi: t1 = lo[-1]; return iv_at(exp[t1], k) ** 2 * (T - now) / 31557600
        t1, t2 = lo[-1], hi[0]; w1 = iv_at(exp[t1], k) ** 2 * (t1 - now) / 31557600; w2 = iv_at(exp[t2], k) ** 2 * (t2 - now) / 31557600
        return w1 + (w2 - w1) * (T - t1) / (t2 - t1)
    lo = [t for t in ts if t <= T]; hi = [t for t in ts if t > T]
    F1 = next(iter(exp[(lo or hi)[-1 if lo else 0]].values()))["F"]; F2 = next(iter(exp[(hi or lo)[0 if hi else -1]].values()))["F"]
    t1 = (lo or hi)[-1 if lo else 0]; t2 = (hi or lo)[0 if hi else -1]
    F = F1 if t1 == t2 else F1 + (F2 - F1) * (T - t1) / (t2 - t1)
    F += basis
    dg = (call(F, K - h, w_at(K - h)) - call(F, K + h, w_at(K + h))) / (2 * h)
    return dg, F, math.sqrt(w_at(K) / ((T - now) / 31557600))
def pbooks(tokens):
    out = {}
    for i in range(0, len(tokens), 40):
        for b in get(f"{C}/books", [{"token_id": t} for t in tokens[i:i+40]]):
            bids = [float(x["price"]) for x in b.get("bids") or []]; asks = [float(x["price"]) for x in b.get("asks") or []]
            out[b["asset_id"]] = (max(bids) if bids else 0.0, min(asks) if asks else 1.0)
    return out
res = []
for cur, sym, slugs, h in (("BTC", "BTCUSDT", sys.argv[1].split(","), 250.0), ("ETH", "ETHUSDT", sys.argv[2].split(","), 10.0)):
    exp = surface(cur); now = time.time()
    idx = get(f"{D}/get_index_price?index_name={cur.lower()}_usd")["result"]["index_price"]
    bn = float(get(f"https://data-api.binance.vision/api/v3/ticker/price?symbol={sym}")["price"]); basis = bn - idx
    print(f"\n{cur}: Deribit index {idx:.2f} Binance {bn:.2f} basis {basis:+.2f}; expiries (h from now): {[round((t-now)/3600,1) for t in sorted(exp) if t>now][:8]}")
    for slug in slugs:
        ev = get(f"{G}/events?slug={slug}")
        if not ev: print("missing", slug); continue
        ev = ev[0]; T = dt.datetime.fromisoformat(ev["endDate"].replace("Z", "+00:00")).timestamp()
        ms = [m for m in ev["markets"] if not m.get("closed")]; bk = pbooks([json.loads(m["clobTokenIds"])[0] for m in ms])
        print(f"== {slug}  resolves in {(T-now)/3600:.1f} h   v24=${float(ev.get('volume24hr') or 0):.0f}")
        for m in sorted(ms, key=lambda m: float(m["groupItemTitle"].replace(",", "").replace("$", ""))):
            K = float(m["groupItemTitle"].replace(",", "").replace("$", "")); bid, ask = bk[json.loads(m["clobTokenIds"])[0]]
            dg, F, vol = digital(exp, T, K, now, basis, h); mid = (bid + ask) / 2; fee = 0.01 * mid * (1 - mid)
            flag = "PM>opt: sell/NO" if bid - fee > dg else ("PM<opt: buy YES" if ask + fee < dg else "")
            edge = (bid - fee - dg) if bid - fee > dg else ((dg - ask - fee) if ask + fee < dg else 0.0)
            res.append(dict(cur=cur, slug=slug, K=K, hrs=(T - now) / 3600, bid=bid, ask=ask, dg=dg, vol=vol, F=F, edge=edge, v24=float(m.get("volume24hr") or 0)))
            print(f"   K={K:>8.0f} PM {bid:.3f}/{ask:.3f}  Deribit digital {dg:.3f} (F={F:.0f}, iv={vol:.2f})  mid-opt {mid-dg:+.3f}  {flag} {('edge %.3f' % edge) if edge else ''}  v24=${float(m.get('volume24hr') or 0):.0f}")
json.dump(res, open(f"/home/user/polymarket-lab/data/r4/deribit_vs_pm_{int(time.time())}.json", "w"))
core = [r for r in res if 0.05 <= r["dg"] <= 0.95]
import statistics as st
print("\nALL n", len(res), "| core (digital 5-95%) n", len(core), "mean(mid-opt)", round(st.mean((r["bid"]+r["ask"])/2 - r["dg"] for r in core), 4), "median |mid-opt|", round(st.median(abs((r["bid"]+r["ask"])/2 - r["dg"]) for r in core), 4), "n flagged", sum(1 for r in core if r["edge"] > 0), "median PM spread", round(st.median(r["ask"]-r["bid"] for r in core), 3))

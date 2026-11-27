"""One-shot Kalshi vs Polymarket top-of-book comparison for hand-matched events (protocol.md). Read-only."""
import json, sys, time, urllib.request, gzip, re, unicodedata
K = "https://api.elections.kalshi.com/trade-api/v2"; G = "https://gamma-api.polymarket.com"; C = "https://clob.polymarket.com"
def get(url, data=None):
    last = None
    for i in range(5):
        try:
            h = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Accept-Encoding": "gzip"}
            body = None
            if data is not None: body = json.dumps(data).encode(); h["Content-Type"] = "application/json"
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=60) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
                return json.loads(b)
        except Exception as e:
            last = e; time.sleep(1.5 * (i + 1))
    raise SystemExit(f"{url}: {last}")
def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", "", s.replace("j.d.", "jd")).strip()
KFEE = 0.07
def kfee(p): return KFEE * p * (1 - p)
def pfee(p, rate): return rate * p * (1 - p)
def kbook(t):
    ob = get(f"{K}/markets/{t}/orderbook?depth=5").get("orderbook_fp") or {}
    yb = [(float(p), float(s)) for p, s in ob.get("yes_dollars") or []]; nb = [(float(p), float(s)) for p, s in ob.get("no_dollars") or []]
    ybid = max(yb) if yb else (0.0, 0.0); nbid = max(nb) if nb else (0.0, 0.0)
    return {"bid": ybid[0], "bid_sz": ybid[1], "ask": round(1 - nbid[0], 4), "ask_sz": nbid[1]}
def pbooks(tokens):
    out = {}
    for i in range(0, len(tokens), 40):
        for b in get(f"{C}/books", [{"token_id": t} for t in tokens[i:i+40]]):
            bids = [(float(x["price"]), float(x["size"])) for x in b.get("bids") or []]; asks = [(float(x["price"]), float(x["size"])) for x in b.get("asks") or []]
            bb = max(bids) if bids else (0.0, 0.0); ba = min(asks) if asks else (1.0, 0.0)
            out[b["asset_id"]] = {"bid": bb[0], "bid_sz": bb[1], "ask": ba[0], "ask_sz": ba[1]}
    return out
# (label, category, pm_event_slug, kalshi_event, mode, mapping)
PAIRS = [
 ("NFL DEN@PIT 11-27", "sports", "nfl-den-pit-2026-11-27", "KXNFLGAME-26NOV27DENPIT", "game", ["DEN", "PIT"]),
 ("NFL SEA@SF 11-29", "sports", "nfl-sea-sf-2026-11-29", "KXNFLGAME-26NOV29SEASF", "game", ["SEA", "SF"]),
 ("NFL TEN@JAX 11-29", "sports", "nfl-ten-jax-2026-11-29", "KXNFLGAME-26NOV29TENJAC", "game", ["TEN", "JAC"]),
 ("NBA LAL@SAS 11-27", "sports", "nba-lal-sas-2026-11-27", "KXNBAGAME-26NOV27LALSAS", "game", ["LAL", "SAS"]),
 ("NBA MIA@NYK 11-27", "sports", "nba-mia-nyk-2026-11-27", "KXNBAGAME-26NOV27MIANYK", "game", ["MIA", "NYK"]),
 ("NBA PHI@IND 11-27", "sports", "nba-phi-ind-2026-11-27", "KXNBAGAME-26NOV27PHIIND", "game", ["PHI", "IND"]),
 ("CFB TEX@TXAM 11-27", "sports", "cfb-tx-txam-2026-11-27", "KXNCAAFGAME-26NOV27TEXTXAM", "game", ["TEX", "TXAM"]),
 ("EPL NFO-CHE 11-27", "sports", "epl-not-che-2026-11-27", "KXEPLGAME-26NOV27NFOCFC", "explicit", {"-not": "NFO", "-che": "CFC", "-draw": "TIE"}),
 ("Super Bowl 2027", "sports-futures", "pro-football-2027-champion-20260729185915366", "KXSB-27", "name", None),
 ("NBA champion 2027", "sports-futures", "nba-2027-champion", "KXNBA-27", "name", None),
 ("NFL MVP", "sports-futures", "pro-football-2026-mvp-winner", "KXNFLMVP-27", "name", None),
 ("Fed decision Dec", "economics", "fed-decision-in-december-20260729232808632", "KXFEDDECISION-26DEC", "title", {"25 bps increase": "H25", "No change": "H0", "50+ bps increase": "H26", "25 bps decrease": "C25", "50+ bps decrease": "C26"}),
 ("US recession 2026", "economics", "us-recession-by-end-of-2026", "KXRECSSNBER-26", "single", None),
 ("Dem nominee 2028", "politics", "democratic-presidential-nominee-2028", "KXPRESNOMD-28", "name", None),
 ("Rep nominee 2028", "politics", "republican-presidential-nominee-2028", "KXPRESNOMR-28", "name", None),
 ("President 2028", "politics", "presidential-election-winner-2028", "KXPRESPERSON-28", "name", None),
 ("Taipei mayor 11-28", "politics", "taipei-mayor-election-winner-20260813125857100", "KXTAIPEIMAYOR-26NOV28", "name", None),
 ("TIME POY 2026", "culture", "time-person-of-the-year-2026", "KXTIME-26", "name", None),
 ("Game Awards GOTY", "culture", "the-game-awards-game-of-the-year-20260804145650", "KXGAMEAWARDS-2026", "name", None),
 ("BTC low in 2026", "crypto", "what-price-will-bitcoin-hit-before-2027", "KXBTCMINY-27JAN01", "title", {"↓ 55,000": "55000.00", "↓ 50,000": "50000.00", "↓ 45,000": "45000.00", "↓ 40,000": "40000.00"}),
]
rows = []; raw = {"ts": time.time(), "pairs": []}
for label, cat, slug, kev, mode, mp in PAIRS:
    pe = get(f"{G}/events?slug={slug}"); ke = get(f"{K}/events/{kev}?with_nested_markets=true")
    if not pe: print("PM missing", slug); continue
    pe = pe[0]; kms = {m["ticker"]: m for m in (ke.get("event", {}).get("markets") or ke.get("markets") or [])}
    pms = [m for m in pe["markets"] if not m.get("closed")]
    legs = []  # (name, pm_market, yes_token, no_token, [kalshi tickers same side], [kalshi tickers opposite side])
    if mode == "game":
        m = next(x for x in pms if x["slug"] == slug); toks = json.loads(m["clobTokenIds"]); outs = json.loads(m["outcomes"])
        legs.append((outs[0], m, toks[0], toks[1], f"{kev}-{mp[0]}", f"{kev}-{mp[1]}"))
    elif mode == "single":
        m = pms[0]; toks = json.loads(m["clobTokenIds"]); legs.append((m["question"][:30], m, toks[0], toks[1], list(kms)[0], None))
    else:
        for m in pms:
            toks = json.loads(m["clobTokenIds"]); title = m.get("groupItemTitle") or ""
            kt = None
            if mode == "explicit":
                for suf, ks in mp.items():
                    if m["slug"].endswith(suf): kt = f"{kev}-{ks}"
            elif mode == "title":
                if title in mp: kt = f"{kev}-{mp[title]}"
            else:
                n = norm(title)
                cands = [t for t, km in kms.items() if norm(km.get("yes_sub_title")) and (norm(km.get("yes_sub_title")) == n or n.startswith(norm(km.get("yes_sub_title")) + " "))]
                if len(cands) == 1: kt = cands[0]
            if kt and kt in kms:
                km = kms[kt]
                if mode == "name" and max(float(km.get("yes_bid_dollars") or 0), float(m.get("bestBid") or 0)) < 0.03: continue
                legs.append((title, m, toks[0], toks[1], kt, None))
    books = pbooks([t for l in legs for t in (l[2], l[3])])
    for name, m, ty, tn, kt, kopp in legs:
        py, pn = books.get(ty), books.get(tn)
        if not py or not pn: continue
        kb = kbook(kt)
        k_yes_ask, k_yes_bid = kb["ask"], kb["bid"]; k_ask_sz, k_bid_sz = kb["ask_sz"], kb["bid_sz"]
        if kopp:  # the other team's market gives an alternative price for the same exposure
            ko = kbook(kopp)
            if 1 - ko["bid"] < k_yes_ask: k_yes_ask, k_ask_sz = round(1 - ko["bid"], 4), ko["bid_sz"]
            if 1 - ko["ask"] > k_yes_bid: k_yes_bid, k_bid_sz = round(1 - ko["ask"], 4), ko["ask_sz"]
        rate = float((m.get("feeSchedule") or {}).get("rate") or 0)
        p_yes_ask = min(py["ask"], round(1 - pn["bid"], 4)); p_yes_bid = max(py["bid"], round(1 - pn["ask"], 4))
        k_no_ask = round(1 - k_yes_bid, 4); p_no_ask = round(1 - p_yes_bid, 4)
        A = p_yes_ask + pfee(p_yes_ask, rate) + k_no_ask + kfee(k_no_ask)      # buy YES on PM, NO on Kalshi
        B = k_yes_ask + kfee(k_yes_ask) + p_no_ask + pfee(p_no_ask, rate)      # buy YES on Kalshi, NO on PM
        Araw = p_yes_ask + k_no_ask; Braw = k_yes_ask + p_no_ask
        pmid = (p_yes_ask + p_yes_bid) / 2; kmid = (k_yes_ask + k_yes_bid) / 2
        thr = (p_yes_ask - p_yes_bid) / 2 + pfee(pmid, rate)
        r = dict(label=label, cat=cat, name=name, pm_slug=m["slug"], k_ticker=kt, rate=rate, pm_bid=p_yes_bid, pm_ask=p_yes_ask, pm_bid_sz=py["bid_sz"], pm_ask_sz=py["ask_sz"],
                 k_bid=k_yes_bid, k_ask=k_yes_ask, k_bid_sz=k_bid_sz, k_ask_sz=k_ask_sz, A=round(A, 4), B=round(B, 4), Araw=round(Araw, 4), Braw=round(Braw, 4),
                 mid_diff=round(pmid - kmid, 4), thr=round(thr, 4), pm_v24=float(m.get("volume24hr") or 0), k_v24=float(kms.get(kt, {}).get("volume_24h_fp") or 0), t=time.time())
        rows.append(r)
    raw["pairs"].append({"label": label, "pm_desc": (pms[0].get("description") or "")[:1500], "k_rules": [(km.get("rules_primary"), km.get("rules_secondary")) for km in list(kms.values())[:1]]})
    time.sleep(0.2)
raw["rows"] = rows
out = f"/home/user/polymarket-lab/data/r4/snapshot_{int(time.time())}.json"; json.dump(raw, open(out, "w"), indent=0)
print("saved", out, "rows", len(rows))
print(f"{'event':<20}{'outcome':<26}{'PM bid/ask':<14}{'K bid/ask':<14}{'mid PM-K':>9}{'thr':>7}{'rawmin':>8}{'netmin':>8}  fee  PMv24/Kv24")
for r in rows:
    print(f"{r['label']:<20}{r['name'][:25]:<26}{r['pm_bid']:.3f}/{r['pm_ask']:.3f}  {r['k_bid']:.3f}/{r['k_ask']:.3f} {r['mid_diff']:>+9.4f}{r['thr']:>7.4f}{min(r['Araw'], r['Braw']):>8.4f}{min(r['A'], r['B']):>8.4f}  {r['rate']:.2f} {r['pm_v24']:.0f}/{r['k_v24']:.0f}")

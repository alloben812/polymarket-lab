"""Minute-bar lead-lag Kalshi vs Polymarket on settled games (protocol.md Q4). Read-only."""
import json, urllib.request, urllib.error, time, math, statistics as st, datetime as dt, gzip
import pmlab.dataapi as da
K = "https://api.elections.kalshi.com/trade-api/v2"; G = "https://gamma-api.polymarket.com"
def get(u, tries=7):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}), timeout=40) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503): time.sleep(3 + 3 * i); continue
            return {"_err": e.code}
        except Exception: time.sleep(2)
    return {"_err": "retries"}
GAMES = [("KXNFLGAME", "26NOV26", "KC", "BUF", "nfl-kc-buf-2026-11-26"), ("KXNFLGAME", "26NOV26", "PHI", "DAL", "nfl-phi-dal-2026-11-26"), ("KXNFLGAME", "26NOV26", "CHI", "DET", "nfl-chi-det-2026-11-26"),
         ("KXNFLGAME", "26NOV25", "GB", "LAR", "nfl-gb-la-2026-11-25"), ("KXNFLGAME", "26NOV25", "GB", "LAR", "nfl-gb-lar-2026-11-25"),
         ("KXNBAGAME", "26NOV25", "SAS", "POR", "nba-sas-por-2026-11-25"), ("KXNBAGAME", "26NOV25", "SAC", "GSW", "nba-sac-gsw-2026-11-25"), ("KXNBAGAME", "26NOV25", "PHX", "HOU", "nba-phx-hou-2026-11-25"),
         ("KXNBAGAME", "26NOV25", "LAC", "MEM", "nba-lac-mem-2026-11-25"), ("KXNBAGAME", "26NOV25", "BKN", "MIL", "nba-bkn-mil-2026-11-25"), ("KXNBAGAME", "26NOV25", "MIN", "OKC", "nba-min-okc-2026-11-25"),
         ("KXNBAGAME", "26NOV25", "CLE", "NYK", "nba-cle-nyk-2026-11-25"), ("KXNBAGAME", "26NOV25", "CHI", "CHA", "nba-chi-cha-2026-11-25"), ("KXNBAGAME", "26NOV25", "MIA", "PHI", "nba-mia-phi-2026-11-25")]
LAGS = range(-3, 4); per_game = []; note = []
for series, d, a, h, slug in GAMES:
    ev = get(f"{G}/events?slug={slug}")
    if not isinstance(ev, list) or not ev: note.append(f"PM slug missing {slug}"); continue
    m = next((x for x in ev[0]["markets"] if x["slug"] == slug), None)
    if not m: note.append(f"no moneyline {slug}"); continue
    tok = json.loads(m["clobTokenIds"])[0]
    gs = m.get("gameStartTime") or ev[0].get("startTime") or m.get("endDate")
    t_start = int(dt.datetime.fromisoformat(gs.replace("Z", "+00:00").replace(" ", "T").replace("+00", "+00:00") if gs.endswith("+00") else gs.replace("Z", "+00:00")).timestamp())
    s0, s1 = t_start - 1800, t_start + 5 * 3600
    tick = f"{series}-{d}{a}{h}-{a}"
    c = get(f"{K}/series/{series}/markets/{tick}/candlesticks?start_ts={s0}&end_ts={s1}&period_interval=1")
    if "_err" in c: c = get(f"{K}/historical/markets/{tick}/candlesticks?start_ts={s0}&end_ts={s1}&period_interval=1")
    cs = c.get("candlesticks") or []
    if not cs: note.append(f"no Kalshi candles {tick} {c.get('_err')}"); continue
    def f(x, k):
        v = x.get(k) or {}; z = v.get("close_dollars", v.get("close")); 
        if z is None: return None
        z = float(z); return z / 100 if z > 1.0001 else z
    kser = {}
    for x in cs:
        b, a_ = f(x, "yes_bid"), f(x, "yes_ask")
        if b is not None and a_ is not None: kser[int(x["end_period_ts"]) // 60 * 60] = (b + a_) / 2
    ph = da.prices_history(tok, s0, s1, 60)
    if not ph: note.append(f"no PM history {slug}"); continue
    if not per_game: print("sample PM history row:", ph[0], "| sample Kalshi candle:", json.dumps(cs[len(cs)//2])[:400])
    tk = "t" if "t" in ph[0] else ("timestamp" if "timestamp" in ph[0] else list(ph[0])[0]); pk = "p" if "p" in ph[0] else ("price" if "price" in ph[0] else list(ph[0])[1])
    pser = {int(r[tk]) // 60 * 60: float(r[pk]) for r in ph}
    ts = sorted(set(kser) & set(pser)); ts = [t for t in ts if 0.03 < kser[t] < 0.97 and 0.03 < pser[t] < 0.97]
    # keep only runs of consecutive minutes
    rows = [(t, pser[t], kser[t]) for t in ts]
    dP = {}; dK = {}; gap = {}
    for i in range(1, len(rows)):
        if rows[i][0] - rows[i-1][0] == 60: dP[rows[i][0]] = rows[i][1] - rows[i-1][1]; dK[rows[i][0]] = rows[i][2] - rows[i-1][2]
        gap[rows[i][0]] = rows[i][2] - rows[i][1]
    def corr(xs, ys):
        if len(xs) < 20: return float("nan")
        mx, my = st.mean(xs), st.mean(ys); sx = math.sqrt(sum((x-mx)**2 for x in xs)); sy = math.sqrt(sum((y-my)**2 for y in ys))
        return sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / (sx * sy) if sx > 0 and sy > 0 else float("nan")
    cc = {}
    for L in LAGS:
        pairs = [(dP[t], dK[t + 60 * L]) for t in dP if t + 60 * L in dK]; cc[L] = corr([p for p, _ in pairs], [k for _, k in pairs])
    def slope(pairs):
        if len(pairs) < 20: return float("nan")
        mx = st.mean(x for x, _ in pairs); my = st.mean(y for _, y in pairs); sxx = sum((x-mx)**2 for x, _ in pairs)
        return sum((x-mx)*(y-my) for x, y in pairs) / sxx if sxx > 0 else float("nan")
    bP = slope([(gap[t], dP[t + 60]) for t in gap if t + 60 in dP]); bK = slope([(gap[t], dK[t + 60]) for t in gap if t + 60 in dK])
    absgap = [abs(g) for g in gap.values()]
    per_game.append(dict(slug=slug, n=len(dP), cc=cc, bP=bP, bK=bK, med_gap=st.median(absgap) if absgap else None, p90_gap=sorted(absgap)[int(0.9*len(absgap))] if absgap else None))
    print(f"{slug:<26} n={len(dP):>4} " + " ".join(f"L{L:+d}:{cc[L]:+.2f}" for L in LAGS) + f" | gap-closure next min: PM {bP:+.2f}  K {-bK:+.2f} | |gap| med {st.median(absgap):.3f} p90 {sorted(absgap)[int(0.9*len(absgap))]:.3f}")
    time.sleep(1.5)
print("notes:", note)
ok = [g for g in per_game if g["n"] >= 60]
if ok:
    print("games used", len(ok))
    for L in LAGS:
        v = [g["cc"][L] for g in ok if g["cc"][L] == g["cc"][L]]; print(f"  lag {L:+d} min: mean corr {st.mean(v):+.3f} se {st.pstdev(v)/math.sqrt(len(v)):.3f} (n games {len(v)})")
    vp = [g["bP"] for g in ok if g["bP"] == g["bP"]]; vk = [-g["bK"] for g in ok if g["bK"] == g["bK"]]
    print(f"  gap closed in next minute: by PM {st.mean(vp):+.3f} (se {st.pstdev(vp)/math.sqrt(len(vp)):.3f}), by Kalshi {st.mean(vk):+.3f} (se {st.pstdev(vk)/math.sqrt(len(vk)):.3f})")
json.dump(per_game, open("/home/user/polymarket-lab/data/r4/leadlag_minute.json", "w"))

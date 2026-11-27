"""For each scheduled-release event: when did the price move, how much traded at stale prices after the release, who took it.
Tape rows are taker-side fills; timestamps are block times (~2-3 s after the match)."""
import json, sys, collections, datetime as dt, calendar, time, os
TAPES = "/home/user/polymarket-lab/data/econ_tapes"
ev = json.load(open("release_events.json"))
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
def ts(s): return calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M"))

SCHED = [  # (slug regex, release time UTC). US data 08:30 ET (12:30 UTC until Nov 1, 13:30 after), ISM 10:00 ET, FOMC 14:00 ET.
 (r"^ism-manufacturing-pmi-august", "2026-09-01 14:00"), (r"^bank-of-canada-decision-in-september", "2026-09-02 13:45"), (r"^ism-services-pmi-august", "2026-09-03 14:00"),
 (r"^(august-unemployment-rate|how-many-jobs-added-in-august)", "2026-09-04 12:30"), (r"^ecb-interest-rates-september", "2026-09-10 12:15"), (r"^ppi-yoy-august", "2026-09-10 12:30"),
 (r"^(august-inflation-us|core-cpi-(mom|yoy)-august)", "2026-09-11 12:30"), (r"^fed-decision-in-september", "2026-09-16 18:00"), (r"^bank-of-england-decision-in-september", "2026-09-17 11:00"),
 (r"^bank-of-mexico-decision-in-september", "2026-09-24 19:00"), (r"^canada-gdp-july", "2026-09-29 12:30"), (r"^reserve-bank-of-australia-decision-in-sept", "2026-09-29 04:30"),
 (r"^core-pce-(yoy|mom)-august", "2026-09-30 12:30"), (r"^ism-manufacturing-pmi-september", "2026-10-01 14:00"), (r"^(september-unemployment-rate|how-many-jobs-added-in-september)", "2026-10-02 12:30"),
 (r"^ism-services-pmi-september", "2026-10-05 14:00"), (r"^(september-inflation-us|core-cpi-(mom|yoy)-september)", "2026-10-14 12:30"), (r"^ppi-yoy-september", "2026-10-15 12:30"),
 (r"^inflation-uk-annual", "2026-10-21 06:00"), (r"^bank-of-canada-decision-in-october", "2026-10-28 13:45"), (r"^fed-decision-in-october", "2026-10-28 18:00"),
 (r"^(core-pce-(yoy|mom)-september|us-gdp-growth-in-q3)", "2026-10-29 12:30"), (r"^ecb-interest-rates-october", "2026-10-29 13:15"), (r"^eurozone-gdp", "2026-10-30 10:00"), (r"^germany-gdp", "2026-10-30 09:00"),
 (r"^canada-gdp-august", "2026-10-30 12:30"), (r"^ism-manufacturing-pmi-october", "2026-11-02 15:00"), (r"^reserve-bank-of-australia-decision-in-nov", "2026-11-03 03:30"), (r"^ism-services-pmi-october", "2026-11-04 15:00"),
 (r"^bank-of-england-decision-in-november", "2026-11-05 12:00"), (r"^bank-of-mexico-decision-in-november", "2026-11-05 19:00"), (r"^(october-unemployment-rate|how-many-jobs-added-in-october)", "2026-11-06 13:30"),
 (r"^(october-inflation-us|core-cpi-(mom|yoy)-october)", "2026-11-10 13:30"), (r"^uk-gdp", "2026-11-12 07:00"), (r"^ppi-yoy-october", "2026-11-13 13:30"), (r"^october-inflation-uk", "2026-11-18 07:00"),
 (r"^core-pce-(yoy|mom)-october", "2026-11-25 13:30"),
]
import re as _re
def sched_T(slug):
    for pat, t in SCHED:
        if _re.search(pat, slug): return ts(t)
    return None
OVERRIDE = {"fed-decision-in-september-762": ts("2026-09-16 18:00"), "fed-decision-in-october-20260617190323537": ts("2026-10-28 18:00")}
BUCKETS = [(-1e9, 6, "a <6s"), (6, 15, "b 6-15s"), (15, 60, "c 15-60s"), (60, 300, "d 1-5min"), (300, 1800, "e 5-30min"), (1800, 21600, "f 30min-6h"), (21600, 1e12, "g >6h")]
STALE = 0.95
snip = collections.defaultdict(lambda: {"name": "", "events": set(), "p60": 0.0, "p30m": 0.0, "plate": 0.0, "usd": 0.0, "n": 0})
out_rows = []
tot = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0])
for e in sorted(ev, key=lambda e: e["end"]):
    fills = []; mk = []
    for m in e["markets"]:
        p = f"{TAPES}/{m['cond']}.json"
        if not os.path.exists(p) or not m.get("prices"): continue
        pr = [float(x) for x in json.loads(m["prices"])]
        if max(pr) < 0.99: continue
        win = pr.index(max(pr))
        rows = json.load(open(p))
        for t, w, side, oi, px, sz, name in rows:
            pw = px if oi == win else 1 - px                     # winner-equivalent price
            long_w = (side == "BUY") == (oi == win)              # taker ends up long the winning outcome
            fills.append((t, m["cond"], pw, sz, long_w, w, name))
        mk.append(m)
    if len(fills) < 30: continue
    fills.sort()
    endts = calendar.timegm(time.strptime(e["end"][:19], "%Y-%m-%dT%H:%M:%S"))
    # burst minute inside [end-12 d, end+12 d]
    cnt = collections.Counter(t // 60 for t, *_ in fills if endts - 12 * 86400 < t < endts + 12 * 86400)
    if not cnt: continue
    bm, bn = max(cnt.items(), key=lambda kv: kv[1])
    first_in_burst = min(t for t, *_ in fills if t // 60 in (bm - 1, bm) and cnt.get(t // 60, 0) >= max(3, bn // 4)) if bn >= 3 else bm * 60
    T = sched_T(e["slug"])
    if T is None: continue
    n_before = sum(1 for t, *_ in fills if T - 600 <= t < T); n_after = sum(1 for t, *_ in fills if T <= t < T + 600)
    snapped = n_after >= 3 * max(1, n_before) / 2
    # pre-release price per market, uncertainty
    pre = {}
    for t, c, pw, sz, lw, w, name in fills:
        if t < T: pre[c] = pw
    unc = [c for c, p in pre.items() if p < 0.90]
    bk = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0])   # n, shares, usd, profit after fee
    wrong = [0, 0.0]
    last_stale = None; first95 = {}
    for t, c, pw, sz, lw, w, name in fills:
        if t < T: continue
        lag = t - T
        if pw >= 0.95 and c in unc and c not in first95: first95[c] = lag
        if lw and pw < STALE:
            prof = (1 - pw) * sz - 0.01 * pw * (1 - pw) * sz
            b = next(n for lo, hi, n in BUCKETS if lo <= lag < hi)
            for d_ in (bk[b], tot[b]):
                d_[0] += 1; d_[1] += sz; d_[2] += pw * sz; d_[3] += prof
            if pw < 0.90: last_stale = lag
            s = snip[w]; s["name"] = name; s["events"].add(e["slug"]); s["usd"] += pw * sz; s["n"] += 1
            if lag < 60: s["p60"] += prof
            elif lag < 1800: s["p30m"] += prof
            else: s["plate"] += prof
        elif (not lw) and pw < STALE:
            wrong[0] += 1; wrong[1] += (1 - pw) * sz              # taker's loss = maker's gain
    row = {"slug": e["slug"], "T": T, "snapped": snapped, "burst_first": first_in_burst, "burst_n": bn, "n_markets": len(mk), "uncertain": len(unc),
           "min_pre": min(pre.values()) if pre else None, "first95": sorted(first95.values()), "last_stale_lag": last_stale,
           "buckets": {k: v for k, v in sorted(bk.items())}, "wrong_way": wrong, "volume": e["volume"]}
    out_rows.append(row)
    b = row["buckets"]
    g = lambda k: f"{b[k][2]:7.0f}/{b[k][3]:6.0f}" if k in b else "      -/     -"
    print(f"{e['slug'][:42]:42} T={f(T)}{'' if snapped else '?'} burst@{f(first_in_burst)[6:]} n10before={n_before:3d} n10after={n_after:4d} unc={len(unc):2d}/{len(mk):2d} minpre={row['min_pre'] if row['min_pre'] is None else round(row['min_pre'],2)} "
          f"t95={[round(x) for x in sorted(first95.values())[:3]]} lastStale={last_stale if last_stale is None else round(last_stale)}s | " + " ".join(f"{k[:1]}:{g(k)}" for _, _, k in BUCKETS) + f" | wrong {wrong[1]:.0f}")
json.dump(out_rows, open("release_results_v2.json", "w"), default=list)
print("\nTOTAL stale taker-long-winner fills after release (pw<0.95), usd / profit after 1% fee:")
for _, _, k in BUCKETS:
    v = tot[k]; print(f"  {k:12} fills={v[0]:6d} shares={v[1]:10.0f} usd={v[2]:10.0f} profit={v[3]:9.0f}")
print("\nTop wallets by post-release profit on stale fills (first 60 s / 1-30 min / later):")
top = sorted(snip.items(), key=lambda kv: -(kv[1]["p60"] + kv[1]["p30m"]))[:25]
for w, s in top:
    print(f"  {w} {s['name'][:22]:22} events={len(s['events']):2d} fills={s['n']:4d} usd={s['usd']:9.0f} p<60s={s['p60']:8.0f} p1-30m={s['p30m']:8.0f} later={s['plate']:8.0f}")
json.dump({w: {**s, "events": sorted(s["events"])} for w, s in snip.items()}, open("release_snipers_v2.json", "w"))

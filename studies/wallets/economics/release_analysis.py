"""For each scheduled-release event: when did the price move, how much traded at stale prices after the release, who took it.
Tape rows are taker-side fills; timestamps are block times (~2-3 s after the match)."""
import json, sys, collections, datetime as dt, calendar, time, os
TAPES = "/home/user/polymarket-lab/data/econ_tapes"
ev = json.load(open("release_events.json"))
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
def ts(s): return calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M"))
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
    T = OVERRIDE.get(e["slug"]) or ((first_in_burst - 3) // 900 * 900 if (first_in_burst - 3) % 900 < 240 else (first_in_burst - 3) // 60 * 60)
    snapped = OVERRIDE.get(e["slug"]) is not None or (first_in_burst - 3) % 900 < 240
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
    print(f"{e['slug'][:42]:42} T={f(T)}{'' if snapped else '?'} burst@{f(first_in_burst)[6:]} n={bn:3d} unc={len(unc):2d}/{len(mk):2d} minpre={row['min_pre'] if row['min_pre'] is None else round(row['min_pre'],2)} "
          f"t95={[round(x) for x in sorted(first95.values())[:3]]} lastStale={last_stale if last_stale is None else round(last_stale)}s | " + " ".join(f"{k[:1]}:{g(k)}" for _, _, k in BUCKETS) + f" | wrong {wrong[1]:.0f}")
json.dump(out_rows, open("release_results.json", "w"), default=list)
print("\nTOTAL stale taker-long-winner fills after release (pw<0.95), usd / profit after 1% fee:")
for _, _, k in BUCKETS:
    v = tot[k]; print(f"  {k:12} fills={v[0]:6d} shares={v[1]:10.0f} usd={v[2]:10.0f} profit={v[3]:9.0f}")
print("\nTop wallets by post-release profit on stale fills (first 60 s / 1-30 min / later):")
top = sorted(snip.items(), key=lambda kv: -(kv[1]["p60"] + kv[1]["p30m"]))[:25]
for w, s in top:
    print(f"  {w} {s['name'][:22]:22} events={len(s['events']):2d} fills={s['n']:4d} usd={s['usd']:9.0f} p<60s={s['p60']:8.0f} p1-30m={s['p30m']:8.0f} later={s['plate']:8.0f}")
json.dump({w: {**s, "events": sorted(s["events"])} for w, s in snip.items()}, open("release_snipers.json", "w"))

"""Step 5: current state (2026-11-27): live reward fields of open weather markets (gamma), a few live books (CLOB),
and the daily reward_income of known rewards farmers (Data API). Read-only. Writes out/live.json."""
import json, random, statistics as st, time, collections
import numpy as np
from pmlab import gamma, dataapi
from pmlab.http import get_json

RES = "/home/user/polymarket-lab/studies/gaps/weather_rewards_quoting/out"
out = {"pulled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
mk = []
for e in gamma.iter_events(limit=50, closed="false", tag_slug="weather"):
    for m in e.get("markets") or []:
        if m.get("closed"):
            continue
        rate = sum(float(c.get("rewardsDailyRate") or 0) for c in (m.get("clobRewards") or []))
        mk.append(dict(slug=m.get("slug"), event=e.get("slug"), rate=rate, msz=m.get("rewardsMinSize"), band=m.get("rewardsMaxSpread"),
                       bid=m.get("bestBid"), ask=m.get("bestAsk"), liq=float(m.get("liquidityNum") or 0), vol24=float(m.get("volume24hr") or 0),
                       tokens=gamma.jfield(m.get("clobTokenIds")), fee=(m.get("feeSchedule") or {}).get("rate"),
                       est=m.get("eventStartTime") or m.get("gameStartTime"), tick=m.get("orderPriceMinTickSize")))
ht = [m for m in mk if (m["slug"] or "").startswith("highest-temperature-in-")]
rw = [m for m in ht if m["rate"] > 0]
q = lambda xs, p: float(np.quantile(xs, p)) if xs else None
out["open_weather_markets"] = len(mk)
out["open_highest_temperature_markets"] = len(ht)
out["rewarded_highest_temperature"] = len(rw)
out["rate_sum_per_day"] = sum(m["rate"] for m in rw)
out["rate_quantiles"] = {p: q([m["rate"] for m in rw], p) for p in (0.1, 0.25, 0.5, 0.75, 0.9, 1.0)}
out["rate_ge_50"] = sum(1 for m in rw if m["rate"] >= 50)
out["min_size_counts"] = dict(collections.Counter(m["msz"] for m in rw))
out["band_counts"] = dict(collections.Counter(m["band"] for m in rw))
out["fee_counts"] = dict(collections.Counter(str(m["fee"]) for m in rw))
out["all_weather_rewarded"] = sum(1 for m in mk if m["rate"] > 0)
out["all_weather_rate_sum"] = sum(m["rate"] for m in mk if m["rate"] > 0)
print({k: v for k, v in out.items()})


def score_book(book, msz, v_c, k=0, tick=0.01):
    """conservative competitor score and our two-sided share for a minimum quote k ticks behind the best prices."""
    bids = sorted(((float(x["price"]), float(x["size"])) for x in book.get("bids") or []), reverse=True)
    asks = sorted(((float(x["price"]), float(x["size"])) for x in book.get("asks") or []))
    if not bids or not asks:
        return None
    qb, qa = bids[0][0] - k * tick, asks[0][0] + k * tick
    abb = max([p for p, s in bids if s >= msz] + [qb]); aba = min([p for p, s in asks if s >= msz] + [qa])
    mid = (abb + aba) / 2; v = v_c / 100.0
    S = lambda s: ((v - s) / v) ** 2 if 0 <= s < v else 0.0
    q1c = sum(s * S(mid - p) for p, s in bids if s >= msz); q2c = sum(s * S(p - mid) for p, s in asks if s >= msz)
    inner = 0.10 <= mid <= 0.90
    C = min(q1c, q2c) + (abs(q1c - q2c) / 3 if inner else 0)
    q1u, q2u = msz * S(mid - qb), msz * S(qa - mid)
    qu = max(min(q1u, q2u), max(q1u, q2u) / 3) if inner else min(q1u, q2u)
    depth = sum(p * s for p, s in bids if mid - p < v) + sum((1 - p) * s for p, s in asks if p - mid < v)
    return dict(best_bid=bids[0][0], best_ask=asks[0][0], mid=mid, comp=C, q_us=qu, share=qu / (qu + C) if qu > 0 else 0.0, inband_usd=depth)


random.seed(7)
pick = sorted(rw, key=lambda m: -m["rate"])[:6] + random.sample(rw, min(18, len(rw)))
books = []
for m in pick:
    try:
        b = get_json("https://clob.polymarket.com/book", {"token_id": m["tokens"][0]})
    except Exception as ex:
        print("book error", m["slug"], ex); continue
    for k in (0, 1):
        s = score_book(b, float(m["msz"] or 20), float(m["band"] or 4.5), k, float(m["tick"] or 0.01))
        if s:
            s.update(slug=m["slug"], rate=m["rate"], msz=m["msz"], k=k, est_reward_per_day=m["rate"] * s["share"])
            books.append(s)
    time.sleep(0.3)
out["live_books"] = books
b0 = [b for b in books if b["k"] == 0 and b["share"] > 0]
out["live_books_summary_k0"] = dict(n=len(b0), median_comp=st.median([b["comp"] for b in b0]) if b0 else None,
                                    median_share=st.median([b["share"] for b in b0]) if b0 else None,
                                    median_est_reward_per_day=st.median([b["est_reward_per_day"] for b in b0]) if b0 else None,
                                    median_rate=st.median([b["rate"] for b in b0]) if b0 else None,
                                    median_inband_usd=st.median([b["inband_usd"] for b in b0]) if b0 else None)
print(out["live_books_summary_k0"])

# reward farmers: daily reward_income (Data API user-pnl, fidelity 1d)
farm = {}
for name in ["xtxpleasecallme", "pootytherewardfarmer", "ArmageddonRewardsBilly"]:
    try:
        nm, w = gamma.resolve_profile(name)
        pts = dataapi.user_pnl(w, "all", "1d")
        keys = sorted(pts[-1].keys()) if pts else []
        rk = next((k for k in keys if "reward" in k), None)
        days = [(p["timestamp"], float(p.get(rk) or 0)) for p in pts] if rk else []
        # the series may be cumulative: report both the raw last values and day-over-day differences
        vals = [v for _, v in days]
        diffs = [b - a for a, b in zip(vals, vals[1:])]
        oct_ = [(t, v) for t, v in days if 1791158400 <= (t if t < 1e12 else t / 1000) < 1792022400]   # 2026-10-02 .. 2026-10-11 UTC approx
        farm[name] = dict(wallet=w, exact_name=nm, fields=keys, reward_field=rk, n_points=len(pts), last5_raw=vals[-5:], last5_diff=diffs[-5:],
                          oct_window_raw=[v for _, v in oct_], oct_window_diff=[b - a for (_, a), (_, b) in zip(oct_, oct_[1:])])
    except Exception as ex:
        farm[name] = dict(error=str(ex))
    time.sleep(0.5)
out["farmers"] = farm
print(json.dumps(farm, indent=1)[:3000])
json.dump(out, open(RES + "/live.json", "w"), indent=1)

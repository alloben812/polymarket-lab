"""Step 2: select the universe from metadata, download Binance 1m, DVOL and Polymarket price histories (cached)."""
import gzip, json, re, sys, time
import numpy as np
from pmlab.http import get_json
from pmlab import gamma, dataapi
from common import *

def select():
    evs = json.load(gzip.open(DATA / "events_raw.json.gz"))
    uni, drop = [], {}
    def d(k): drop[k] = drop.get(k, 0) + 1
    for e in evs:
        s = e.get("seriesSlug") or ((e.get("series") or [{}])[0].get("slug"))
        if s in EURO_SERIES: grp, (asset, freq) = "euro", EURO_SERIES[s]
        elif s in OT_SERIES: grp, (asset, freq) = "ot", OT_SERIES[s]
        else: continue
        for m in e["markets"]:
            end = m.get("endDate")
            if not end or not (WIN0 <= end <= WIN1): d((grp, freq, "out_of_window")); continue
            if not m.get("closed"): d((grp, freq, "not_closed")); continue
            op = gamma.jfield(m.get("outcomePrices")) or []
            outs = gamma.jfield(m.get("outcomes")) or []
            if outs != ["Yes", "No"] or sorted(op) != ["0", "1"]: d((grp, freq, "bad_outcome")); continue
            if (m.get("volumeNum") or 0) < 5000: d((grp, freq, "low_volume")); continue
            git = m.get("groupItemTitle") or ""
            num = re.sub(r"[^\d.]", "", git)
            if not num: d((grp, freq, "no_strike")); continue
            K = float(num)
            q = m["question"]
            qn = [float(x.replace(",", "")) for x in re.findall(r"\$?([\d,]{3,}(?:\.\d+)?)", q)]
            if K not in qn: d((grp, freq, "strike_mismatch")); continue
            up = None
            if grp == "ot":
                up = ("reach" in q.lower()) or ("↑" in git)
                if (("dip" in q.lower()) or ("↓" in git)) == up: d((grp, freq, "dir_unclear")); continue
            toks = gamma.jfield(m["clobTokenIds"])
            uni.append({"grp": grp, "asset": asset, "freq": freq, "series": s, "event": e["slug"], "slug": m["slug"], "cond": m["conditionId"],
                        "yes": toks[0], "no": toks[1], "K": K, "up": up, "start": ts(m["startDate"]), "T": ts(end),
                        "ev_start": ts(e["startDate"]), "closed_t": ts(m["closedTime"]) if m.get("closedTime") else None,
                        "vol": m["volumeNum"], "yes_won": op[0] == "1", "fee_rate": (m.get("feeSchedule") or {}).get("rate"),
                        "date": end[:10], "q": q})
    json.dump(uni, open(DATA / "universe.json", "w"))
    import collections
    c = collections.Counter((u["grp"], u["asset"], u["freq"]) for u in uni)
    print("kept", len(uni), dict(c)); print("dropped", drop)

def binance(sym, t0, t1):
    out = []; cur = t0
    while cur < t1:
        rows = get_json("https://data-api.binance.vision/api/v3/klines", {"symbol": sym, "interval": "1m", "startTime": cur * 1000, "limit": 1000}, cache=cur + 1000 * 60 < time.time() - 3600)
        if not rows: break
        for r in rows: out.append((int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4])))
        cur = out[-1][0] + 60
    a = np.array([r for r in out if r[0] < t1]); np.save(DATA / f"{sym}_1m.npy", a); print(sym, a.shape, iso(a[0, 0]), iso(a[-1, 0]))

def dvol(cur, t0, t1):
    out = {}; end = t1
    while end > t0:
        r = get_json("https://www.deribit.com/api/v2/public/get_volatility_index_data", {"currency": cur, "start_timestamp": t0 * 1000, "end_timestamp": end * 1000, "resolution": 3600}, cache=True)["result"]
        rows = r["data"]
        if not rows: break
        for x in rows: out[int(x[0]) // 1000] = x[4]
        cont = r.get("continuation")
        if not cont: break
        end = int(cont) // 1000
    a = np.array(sorted(out.items()), dtype=float); np.save(DATA / f"dvol_{cur}.npy", a); print("dvol", cur, a.shape, iso(a[0, 0]), iso(a[-1, 0]), a[:, 1].min(), a[:, 1].max())

def histories(grp):
    uni = [u for u in load_universe() if u["grp"] == grp]
    (DATA / "ph").mkdir(exist_ok=True)
    n = 0
    for u in uni:
        p = DATA / "ph" / f"{u['cond']}.json"
        if p.exists(): continue
        rows = []; a = u["start"] - 600  # the API refuses spans above 15 days: walk in 14-day chunks
        while a < u["T"] + 600:
            b = min(a + 14 * 86400, u["T"] + 600)
            rows += dataapi.prices_history(u["yes"], a, b, 300); a = b
        rows = list({(r["timestamp"], r["resolution_seconds"]): r for r in rows}.values()); rows.sort(key=lambda r: r["timestamp"])
        json.dump([(r["timestamp"], r["price"], r["resolution_seconds"]) for r in rows], open(p, "w"))
        n += 1
        if n % 100 == 0: print("ph", grp, n, file=sys.stderr)
    print("histories", grp, len(uni), "new", n)

if __name__ == "__main__":
    what = sys.argv[1]
    if what == "select": select()
    elif what == "px":
        t0, t1 = ts("2026-09-28T00:00:00Z"), ts("2026-11-27T12:00:00Z")
        for s in ("BTCUSDT", "ETHUSDT"): binance(s, t0, t1)
        for c in ("BTC", "ETH"): dvol(c, t0, t1)
    elif what == "ph": histories(sys.argv[2])

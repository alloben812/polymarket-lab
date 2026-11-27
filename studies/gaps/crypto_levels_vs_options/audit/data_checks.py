import json, gzip, re, collections, time
import numpy as np, pandas as pd
from pathlib import Path
D = Path("/home/user/polymarket-lab/data/gaps_levels")
iso = lambda t: time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))
uni = json.load(open(D / "universe.json")); eu = [u for u in uni if u["grp"] == "euro"]
print("universe", len(uni), "euro", len(eu), "dup cond", len(uni) - len({u["cond"] for u in uni}), "dup yes token", len(uni) - len({u["yes"] for u in uni}))
# 1. my own pass over the raw gamma dump for the daily 'above' ladders
evs = json.load(gzip.open(D / "events_raw.json.gz"))
ser = collections.Counter(); seen = collections.Counter(); allm = []
for e in evs:
    s = e.get("seriesSlug") or ((e.get("series") or [{}])[0].get("slug")); ser[s] += 1
    title = (e.get("title") or "").lower()
    for m in e.get("markets", []):
        q = (m.get("question") or "").lower()
        if ("bitcoin" in q or "ethereum" in q) and " above " in q:
            allm.append((s, m.get("endDate"), m.get("closed"), m.get("volumeNum") or 0, m.get("conditionId"), m.get("outcomePrices"), m.get("slug")))
print("series counts in dump:", dict(ser))
a = pd.DataFrame(allm, columns=["series", "end", "closed", "vol", "cond", "op", "slug"]).drop_duplicates("cond")
w = a[(a.end >= "2026-10-27T00:00:00Z") & (a.end <= "2026-11-26T23:59:59Z")]
print("'above' markets in window by series:\n", w.groupby("series").agg(n=("cond", "size"), ge5k=("vol", lambda x: (x >= 5000).sum()), lt5k=("vol", lambda x: (x < 5000).sum()), not_closed=("closed", lambda x: (~x.astype(bool)).sum())).to_string())
inuni = {u["cond"] for u in eu}
print("in window, vol>=5000, in my scan but NOT in analyst universe:", len(w[(w.vol >= 5000) & ~w.cond.isin(inuni)]), w[(w.vol >= 5000) & ~w.cond.isin(inuni)].series.value_counts().to_dict())
print("analyst euro markets not found by my scan:", len(inuni - set(w.cond)))
d = w[w.series.isin(["btc-multi-strikes-weekly", "ethereum-multi-strikes-weekly"])]
print("daily ladders: dates", d.end.str[:10].nunique(), "markets", len(d), "kept", (d.vol >= 5000).sum(), "dropped low volume", (d.vol < 5000).sum())
# 2. T hours, start->T span, outcome from Binance candle (my own lookup)
kl = {s: np.load(D / f"{s}USDT_1m.npy") for s in ("BTC", "ETH")}
cl = {s: dict(zip(kl[s][:, 0].astype("int64").tolist(), kl[s][:, 4].tolist())) for s in kl}
ok59 = ok00 = n = 0; span = []
for u in eu:
    if u["freq"] != "daily": continue
    n += 1; ok59 += (cl[u["asset"]][u["T"] - 60] > u["K"]) == u["yes_won"]; ok00 += (cl[u["asset"]][u["T"]] > u["K"]) == u["yes_won"]; span.append((u["T"] - u["start"]) / 3600)
    assert time.gmtime(u["T"]).tm_hour == (16 if u["date"] <= "2026-10-31" else 17) and u["T"] % 3600 == 0
print(f"daily ladders {n}: outcome reproduced by 11:59 candle {ok59}, by 12:00 candle {ok00}; life hours min/med/max {min(span):.1f}/{np.median(span):.1f}/{max(span):.1f}")
# 3. price histories: coverage and gaps
rows = []
for u in eu:
    r = json.load(open(D / "ph" / f"{u['cond']}.json"))
    t = sorted({x[0] for x in r if x[2] == 300 and x[0] < u["T"]})
    non300 = sum(1 for x in r if x[2] != 300); exp = (u["T"] - u["start"]) // 300
    rows.append((u["slug"], u["freq"], len(t), exp, non300, (t[0] - u["start"]) if t else None, (u["T"] - t[-1]) if t else None, int(np.max(np.diff(t))) if len(t) > 1 else None, sum(1 for x in t if x % 300)))
ph = pd.DataFrame(rows, columns=["slug", "freq", "n", "exp", "non300", "first_lag", "last_gap", "max_step", "offgrid"])
dd = ph[ph.freq == "daily"]
print("price histories (daily): markets", len(dd), "empty", (dd.n == 0).sum(), "coverage n/expected: min %.3f median %.3f" % ((dd.n / dd.exp).min(), (dd.n / dd.exp).median()), "| points with resolution != 300:", int(ph.non300.sum()), "| off-grid stamps", int(ph.offgrid.sum()), "| max step s: max", dd.max_step.max(), "markets with a hole > 300 s:", (dd.max_step > 300).sum(), "| first point lag after start median s", dd.first_lag.median(), "| last point before T median s", dd.last_gap.median())
# 4. tapes: completeness vs volumeNum, dollars vs shares
rows = []
for u in eu:
    p = D / "tape" / f"{u['cond']}.json.gz"
    if not p.exists(): rows.append((u["slug"], u["vol"], None, None, None, None, None, u["date"])); continue
    tp = json.load(gzip.open(p, "rt"))
    sh = sum(x[3] for x in tp); usd = sum(x[3] * x[4] for x in tp)
    rows.append((u["slug"], u["vol"], len(tp), sh, usd, tp[0][0] - u["start"] if tp else None, tp[-1][0] - u["T"] if tp else None, u["date"]))
tp = pd.DataFrame(rows, columns=["slug", "vol", "rows", "shares", "usd", "first_after_start", "last_after_T", "date"])
h = tp.dropna(subset=["rows"])
print("tapes cached for", len(h), "of", len(tp), "euro markets; dup rows within tapes: n/a (aggregated rows)")
print("tape shares / volumeNum: min %.4f median %.4f max %.4f; tapes with ratio < 0.99: %d" % ((h.shares / h.vol).min(), (h.shares / h.vol).median(), (h.shares / h.vol).max(), ((h.shares / h.vol) < 0.99).sum()))
print("tape DOLLARS / volumeNum: median %.3f; markets whose dollar turnover is below $5,000: %d of %d (below $2,000: %d)" % ((h.usd / h.vol).median(), (h.usd < 5000).sum(), len(h), (h.usd < 2000).sum()))
print("rows per tape: median", h.rows.median(), "max", h.rows.max(), "| tapes with rows multiple of 1000:", (h.rows % 1000 == 0).sum(), "| trades before start:", (h.first_after_start < 0).sum(), "| share of tape rows after T: n/a")
tp.to_parquet("tape_stats.parquet")

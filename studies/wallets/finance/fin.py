"""Shared loader for the finance wallet study: fills + inventory events + gamma metadata + resolutions, cached."""
import json, os, re, time, collections, datetime as dt
from pmlab import gamma, dataapi, wallet as W

HERE = os.path.dirname(os.path.abspath(__file__))
END = 1795795200          # 2026-11-27 16:00 UTC (fixed so reruns are comparable)
WALLETS = {
 "grasstoucher69": "0x982a77e75498fa134607f598c861b8de9d0c6851",
 "thanksforplayin": "0x38d812aff0b79f3bf5da2a477f780bcc163eea7c",
 "superstonksbro": "0x969fae0a3a93778adc42178f72c612ed8c4e4d55",
 "C03B": "0x40604cb1f958c03bea0b18aa43e4cb0d62f33ec3",
 "CoinTrick": "0x731a241767938bb23d1b2fac4c9cd2f3cea9033f",
 "Hauchn": "0xf0ca28d5b0141f0a8e7b251dea80fd881cb166ed",
 "PippiTrader": "0x403f2471f8aaa1e8a224f1338b073bfa3fdb94f1",
}

def load(name, days=21):
    p = f"{HERE}/cache/{name}_{days}.json"
    if os.path.exists(p):
        return json.load(open(p))
    w = WALLETS[name]; start = END - days * 86400
    fills, trunc = W.fetch_fills(w, start, END, 80000)
    inv = W.fetch_inventory_events(w, start, END)
    conds = sorted({f["condition_id"] for f in fills} | {e.get("condition_id") for e in inv if e.get("condition_id")})
    meta = gamma.markets_by_condition(conds)
    res = dataapi.resolutions(conds)
    keep = ("question", "slug", "endDate", "startDate", "closedTime", "description", "resolutionSource", "feeType", "feeSchedule",
            "volumeNum", "negRisk", "outcomes", "clobTokenIds", "umaResolutionStatus", "clobRewards", "rewardsMinSize", "rewardsMaxSpread", "orderPriceMinTickSize")
    meta = {c: {k: m.get(k) for k in keep} | {"tags": gamma.tag_slugs(m), "event_slug": (m.get("events") or [{}])[0].get("slug") if isinstance(m.get("events"), list) else None}
            for c, m in meta.items()}
    out = dict(name=name, wallet=w, start=start, end=END, truncated=trunc, fills=fills, inv=inv, meta=meta, res=res)
    json.dump(out, open(p, "w"))
    return out

TICK = r"\(([A-Z0-9.\-]{1,8})\)"
def mtype(title, slug=""):
    """(type, ticker) for finance price markets; type None for anything else."""
    t = title or ""; s = slug or ""
    tk = re.search(TICK.replace("(HIGH|LOW)", ""), re.sub(r"\((HIGH|LOW)\)", "", t)); tk = tk.group(1) if tk else None
    if re.search(r"Up or Down", t):
        if re.search(r"\d{1,2}(:\d\d)?(AM|PM)", t): return ("updown-intraday", tk)
        return ("updown-day", tk)
    if re.search(r"hit \((HIGH|LOW)\).*Week of", t) or re.search(r"the week of", t): return ("hit-week", tk)
    if re.search(r"hit \((HIGH|LOW)\)", t): return ("hit-month", tk)
    if re.search(r"finish week of .* above", t): return ("close-week", tk)
    if re.search(r"close above .* end of", t): return ("close-month", tk)
    if re.search(r"closes? (above|below|at|between)", t) and re.search(r" on (January|February|March|April|May|June|July|August|September|October|November|December) \d", t): return ("close-day", tk)
    if re.search(r"market cap", t, re.I): return ("mcap", tk)
    if re.search(r"earnings", t, re.I): return ("earnings", tk)
    if re.search(r"\bIPO\b", t): return ("ipo", tk)
    return (None, tk)

def ts(v):
    return W._ts(v)

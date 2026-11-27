"""Independent recomputation for the news_latency audit (auditor's own code; imports nothing from the study).
Reads only raw caches: data/gaps_news/markets_all.jsonl.gz, ph/, tapes/, and the cached Data API settlement answer
out/resolutions.json, plus the frozen hand labels out/labels.csv (a human input, not an analysis output).
Writes audit/recomputed.json. Usage: python3 -I recompute.py"""
import bisect, csv, datetime as dt, gzip, json, math, random, re, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
DATA = STUDY.parents[2] / "data" / "gaps_news"


def T(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())


W0, W1, SPLIT = T("2026-09-01"), T("2026-11-26"), T("2026-10-14")
INC = {"politics", "geopolitics", "world", "world-affairs", "elections", "global-elections", "world-elections",
       "breaking-news", "middle-east"}
EXC = {"tweets-markets", "elon-tweets", "mention-markets", "sports", "games", "esports", "crypto-prices", "up-or-down",
       "hit-price", "multi-strikes", "weather"}
ELECT = {"elections", "global-elections", "world-elections", "midterms", "primaries"}
WORD = re.compile(r"(^|-)(say|said|mention|mentions|tweet|tweets|post|posts)(-|$)")


def ptime(s):
    if not s:
        return None
    s = s.replace(" ", "T").replace("Z", "+00:00")
    if re.search(r"[+-]\d\d$", s):
        s += ":00"
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return int((d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).timestamp())


def jl(x):
    return json.loads(x) if isinstance(x, str) else x


def load_markets():
    mk = {}
    with gzip.open(DATA / "markets_all.jsonl.gz", "rt") as f:
        for line in f:
            m = json.loads(line)
            mk[m["conditionId"]] = m
    return mk


def universe_ok(m):
    tags = set(m.get("tags") or [])
    try:
        o, t = jl(m["outcomes"]), jl(m["clobTokenIds"])
    except Exception:
        return False
    if not o or len(o) != 2 or not t or len(t) != 2:
        return False
    if not tags & INC or tags & EXC or WORD.search(m.get("slug") or ""):
        return False
    st = ptime(m.get("startDate") or m.get("createdAt"))
    if st is None or st >= W1:
        return False
    if m.get("closed"):
        ct = ptime(m.get("closedTime"))
        if ct is None or ct < W0:
            return False
    return True


def cat_of(m):
    tags = set(m.get("tags") or [])
    if m.get("feeType") == "politics_elections_fees" or tags & ELECT:
        return "elections"
    if "geopolitics" in tags or (m.get("feeType") == "zero_fees" and tags & {"world", "middle-east", "world-affairs"}):
        return "geopolitics"
    return "other politics"


def rate_of(m):
    fs = m.get("feeSchedule") or {}
    if fs.get("rate") is not None:
        return float(fs["rate"])
    return {"geopolitics": 0.0, "elections": 0.05, "other politics": 0.01}[cat_of(m)]


# ---------- independent screen ----------
def pairs(pts, gap, thr):
    out = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if pts[j][0] - pts[i][0] > gap:
                break
            if abs(pts[j][1] - pts[i][1]) >= thr:
                out.append((pts[i][0], pts[i][1], pts[j][0], pts[j][1]))
                break
    return out


def screen(mk):
    cands = []
    for cid, m in mk.items():
        if not universe_ok(m):
            continue
        p = DATA / "ph" / f"{cid}.json.gz"
        if not p.exists():
            continue
        d = json.load(gzip.open(p, "rt"))
        p300 = [x for x in d["p300"] if x[0] and True]
        p60 = d["p60"]
        f300 = p300[0][0] if p300 else 10**12
        p1800 = [x for x in d["p1800"] if x[0] < f300]
        det = [(a, b, c, e, 1800) for a, b, c, e in pairs(p1800, 3600, 0.35)]
        det += [(a, b, c, e, 300) for a, b, c, e in pairs(p300, 600, 0.40)]
        det += [(a, b, c, e, 60) for a, b, c, e in pairs(p60, 600, 0.40)]
        det.sort()
        epi = []
        for x in det:
            if epi and x[0] - epi[-1]["last"] < 7200:
                epi[-1]["last"] = x[0]
                continue
            epi.append({"c": cid, "T_pre": x[0], "p_pre": x[1], "T_post": x[2], "p_post": x[3], "bucket": x[4], "last": x[0]})
        cands += [e for e in epi if W0 <= e["T_pre"] < W1]
    return sorted(cands, key=lambda e: (e["T_pre"], e["c"]))


# ---------- tape timing ----------
_tape_cache = {}


def tape(cid):
    if cid not in _tape_cache:
        p = DATA / "tapes" / f"{cid}.jsonl.gz"
        _tape_cache[cid] = [json.loads(l) for l in gzip.open(p, "rt")] if p.exists() else None
    return _tape_cache[cid]


def yes_price(r):
    return r["p"] if r["i"] == 0 else 1 - r["p"]


def offer_F(r, fidx):
    """F was on offer at this price at match time (taker BUY of F, or taker SELL of the other token = its bid = F ask)."""
    if r["s"] == "BUY" and r["i"] == fidx:
        return r["p"]
    if r["s"] == "SELL" and r["i"] != fidx:
        return 1 - r["p"]
    return None


def ph_at(cid, t):
    d = json.load(gzip.open(DATA / "ph" / f"{cid}.json.gz", "rt"))
    for key, b in (("p60", 60), ("p300", 300), ("p1800", 1800)):
        pts = d[key]
        ts = [x[0] for x in pts]
        k = bisect.bisect_left(ts, t)
        if k < len(pts) and pts[k][0] <= t + 2 * b:
            return pts[k][1]
    return None


def time_jump(c, m, res):
    tp = tape(c["c"])
    if tp is None:
        return {"status": "notape"}
    up = c["p_post"] > c["p_pre"]
    fidx = 0 if up else 1
    fp = (lambda r: yes_price(r)) if up else (lambda r: 1 - yes_price(r))
    pre = c["p_pre"] if up else 1 - c["p_pre"]
    lo, hi = c["T_pre"] - 5 + 3, c["T_post"] + c["bucket"] + 3     # match-time window -> block time (+3 s)
    k0 = None
    for k, r in enumerate(tp):
        if r["t"] > hi:
            break
        if r["t"] >= lo and fp(r) >= pre + 0.10:
            k0 = k
            break
    if k0 is None:
        return {"status": "nojump"}
    tb = tp[k0]["t"]
    k10 = k0
    while k10 + 1 < len(tp) and tp[k10 + 1]["t"] <= tb + 600:
        k10 += 1
    p10 = fp(tp[k10])
    j = {"c": c["c"], "fidx": fidx, "up": up, "pre": pre, "tb": tb, "t0": tb - 3, "p_first": fp(tp[k0]), "p10": p10,
         "event": ((m.get("events") or [{}])[0] or {}).get("slug") or c["c"], "cat": cat_of(m), "rate": rate_of(m),
         "q": m["question"]}
    prev = None
    for r in reversed(tp[:k0]):
        if r["t"] < tb - 86400:
            break
        prev = r
        break
    r_ = res.get(c["c"]) or {}
    o = jl(m["outcomes"])
    fin = r_.get("final") or {}
    sy = float(fin[o[0]]) if r_.get("resolved") and fin.get(o[0]) is not None else None
    try:
        my = float(jl(m["outcomePrices"])[0])
    except Exception:
        my = None
    j["resolved"] = sy is not None
    py = sy if sy is not None else my
    j["payoff"] = None if py is None else (py if up else 1 - py)
    if p10 - pre < 0.40:
        j["status"] = "unconf"
        return j
    if prev is not None and p10 - fp(prev) < 0.25:
        j["status"] = "artef"
        return j
    y2 = ph_at(c["c"], tb - 3 + 7200)
    if y2 is None:
        ct = ptime(m.get("closedTime")) if m.get("closed") else None
        if sy is not None and ct is not None and ct <= tb + 7200 + 3600:
            y2 = sy
        else:
            last = tp[k0]
            for r in tp[k0:]:
                if r["t"] > tb + 7200:
                    break
                last = r
            y2 = yes_price(last)
    p2h = y2 if up else 1 - y2
    j["p2h"] = p2h
    j["status"] = "main" if p2h - pre >= 0.5 * (p10 - pre) else "R"
    return j


def rule(j, d, budget=200.0, pmax=0.90, window=600, mode="prints"):
    """mode prints: every offer print <= pmax in window (study's rule).  mode first: only the first offer print at or
    after t0+d, within 5 s, size <= that print (one-shot, no cherry-picking later prints)."""
    tp = tape(j["c"])
    a, b = j["tb"] + d, j["tb"] + d + window
    spent = sh = fee = 0.0
    nf = 0
    for r in tp:
        if r["t"] < a:
            continue
        if r["t"] > b or spent >= budget - 1e-9:
            break
        p = offer_F(r, j["fidx"])
        if mode == "first":
            if r["t"] > a + 5:
                break
            if p is None:
                continue
            if p > pmax:
                break
        if p is None or p > pmax or p <= 0:
            continue
        q = min(r["z"], (budget - spent) / p)
        spent += q * p
        sh += q
        fee += j["rate"] * p * (1 - p) * q
        nf += 1
        if mode == "first":
            break
    net = sh * j["payoff"] - spent - fee if sh else 0.0
    return {"spent": spent, "sh": sh, "fee": fee, "net": net, "nf": nf}


def clusters(js):
    js = sorted(js, key=lambda j: j["t0"])
    last = {}
    n = 0
    for j in js:
        k = j["event"]
        if k in last and j["t0"] - last[k][0] <= 1800:
            j["cl"] = last[k][1]
        else:
            n += 1
            j["cl"] = n
        last[k] = (j["t0"], j["cl"])


def tstat(vals_by_unit):
    v = list(vals_by_unit.values())
    if len(v) < 2:
        return float("nan")
    s = statistics.stdev(v)
    return sum(v) / (s * math.sqrt(len(v))) if s > 0 else float("nan")


def summarize(js, d, key="cl", **kw):
    by = defaultdict(float)
    byday = defaultdict(float)
    tot = spent = fee = 0.0
    nfill = 0
    for j in js:
        r = rule(j, d, **kw)
        j.setdefault("net", {})[(d, kw.get("budget", 200), kw.get("mode", "prints"))] = r["net"]
        by[j[key]] += r["net"]
        byday[dt.datetime.utcfromtimestamp(j["t0"]).date()] += r["net"]
        tot += r["net"]
        spent += r["spent"]
        fee += r["fee"]
        nfill += r["sh"] > 0
    return {"n": len(js), "mk": len({j["c"] for j in js}), "units": len(by), "fill": nfill, "spent": round(spent),
            "fee": round(fee, 2), "net": round(tot), "t_cl": round(tstat(by), 2), "t_day": round(tstat(byday), 2)}


def boot(js, d, n=2000, seed=1, **kw):
    by = defaultdict(float)
    for j in js:
        by[j["cl"]] += rule(j, d, **kw)["net"]
    v = list(by.values())
    rng = random.Random(seed)
    s = sorted(sum(rng.choice(v) for _ in v) for _ in range(n))
    return round(s[int(0.025 * n)]), round(s[int(0.975 * n)])


def main():
    mk = load_markets()
    res = json.load(open(STUDY / "out" / "resolutions.json"))
    cands = screen(mk)
    auth = json.load(open(STUDY / "out" / "candidates.json"))
    ak = {(c["c"], c["T_pre"]) for c in auth}
    mykeys = {(c["c"], c["T_pre"]) for c in cands}
    print("screen: mine", len(cands), "author", len(auth), "both", len(ak & mykeys), "only mine", len(mykeys - ak),
          "only author", len(ak - mykeys))
    js = [time_jump(c, mk[c["c"]], res) for c in cands]
    print("status", Counter(j["status"] for j in js))
    js = [j for j in js if j["status"] in ("main", "R", "unconf", "artef")]
    labels = {}
    for row in csv.DictReader(open(STUDY / "out" / "labels.csv")):
        labels[(row["c"], int(row["t0"]))] = row
    conf = [j for j in js if j["status"] in ("main", "R")]
    clusters(conf)
    miss = 0
    for j in conf:
        L = labels.get((j["c"], j["t0"]))
        if L is None:
            miss += 1
            j["label"] = "?"
        else:
            j["label"] = L["label"]
            j["doubt"] = L["doubt"]
    print("confirmed", len(conf), "label not found", miss)
    out = {}
    U = lambda j: j["label"] == "unscheduled"
    for half, f in (("first", lambda j: j["t0"] < SPLIT), ("second", lambda j: j["t0"] >= SPLIT)):
        main_ = [j for j in conf if j["status"] == "main" and U(j) and f(j)]
        for d in (10, 30, 120, 600):
            s = summarize(main_, d)
            s["ci"] = boot(main_, d)
            out[f"main_unsched_{half}_{d}"] = s
            print("main unsched", half, d, s)
    json.dump(out, open(HERE / "recomputed.json", "w"), indent=1, default=str)
    return mk, res, js, conf


if __name__ == "__main__":
    main()

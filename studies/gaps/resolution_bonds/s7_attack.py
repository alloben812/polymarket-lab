"""Step 7 (added after s1-s6 had run): attack checks and descriptive splits. None of these changes the verdict rule;
each check is counted as a variant in results.md.

A1  C-tape restricted to taker BUY rows with block time >= entry time t (the favourite token is known at t; rows
    before t use the later knowledge that this token becomes the favourite).
A2  Same as A1 with block time >= t + 300 (a slow program reacting to the 5-minute mid).
A3  Time profile of A1 prints: seconds after t of each qualifying print, share of dollars more than 60 s / 10 min
    after the first qualifying print (what reaction time is needed).
A4  Size check: markets where at least $20 / $100 of qualifying taker BUYs printed after t.
D1  Weekday vs weekend (closedTime, UTC) for claim entries (C-mid, all categories) and C-tape A1 (crypto+politics).
D2  Crypto sub-types (slug pattern) in the claim, C-mid and C-tape A1.
D3  Exploratory pooled row: all families except sports and weather, C-mid / C-cons, by period (post hoc, not
    part of the verdict).
"""
import gzip
import json
import pickle
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone

from pmlab.fees import fee_per_share
from pmlab.stats import ratio_cluster, wilson
from common import DATA, EPS, OUT

LO, HI = 0.95, 0.98
panel = {r["cid"]: r for r in pickle.load(open(DATA / "panel.pkl", "rb"))}
sel = json.loads((DATA / "tape_sample.json").read_text())
L = []


def P(s=""):
    L.append(s)


def crypto_type(slug):
    if "up-or-down" in slug:
        return "up/down hourly" if re.search(r"-\d{1,2}(am|pm)-et$", slug) else "up/down daily"
    if "-dip-to-" in slug or "-reach-" in slug:
        return "hit-price (dip/reach)"
    if "-between-" in slug:
        return "range"
    if "-above-" in slug:
        return "above-X"
    return "other"


def weekend(t):
    return datetime.fromtimestamp(t, tz=timezone.utc).weekday() >= 5


def cl_stats(items):
    """items: (event, profit, shares) -> mean c/share, se, t clustered by event; and n markets."""
    num, den = defaultdict(float), defaultdict(float)
    for ev, pr, sh in items:
        num[ev] += pr
        den[ev] += sh
    ev = list(num)
    if not ev:
        return None
    m, se, t = ratio_cluster([num[e] for e in ev], [den[e] for e in ev])
    return m, se, t, len(ev)


# ---------------- A1-A4 on the tape sample
rows = []
for fam, cids in sel["chosen"].items():
    for cid in cids:
        r = panel[cid]
        d = json.load(gzip.open(DATA / "tapes" / f"{cid}.json.gz", "rt"))
        c = r["claim"]
        tok = r["tokens"][c["k"]]
        prints = []
        for t, side, tk, price, size, wallet in d["rows"]:
            if side != "BUY" or tk != tok or not (LO - EPS <= price < HI - EPS):
                continue
            if not (r["end"] - 3600 <= t <= r["closed"]):
                continue
            prints.append((t, price, size, wallet))
        prints.sort()
        rows.append({"cid": cid, "fam": fam, "slug": r["slug"], "event": r["event"], "late": r["late"], "t": c["t"], "pay": c["pay"],
                     "rate": r["rate"], "prints": prints, "closed": r["closed"], "end": r["end"],
                     "ctype": crypto_type(r["slug"]) if fam == "crypto" else fam})


def ctape(rs, delay):
    out = []
    for r in rs:
        pr = sh = cost = 0.0
        for t, price, size, w in r["prints"]:
            if delay is not None and t < r["t"] + delay:
                continue
            fee = fee_per_share(price, r["rate"])
            pr += size * (r["pay"] - price - fee)
            sh += size
            cost += size * (price + fee)
        if sh > 0:
            out.append((r, pr, sh, cost))
    return out


P("# Attack checks and descriptive splits (s7_attack.py)")
P()
P("## A1/A2 C-tape with the favourite known before the print")
P()
P("variant | category | period | markets | events | losing markets | shares | $ cost | net c/share | SE c (event) | t (event) | net % of cost")
P("|".join(["---"] * 12))
res_a = {}
for name, delay in [("C-tape (s6, all rows)", None), ("A1 rows >= t", 0), ("A2 rows >= t+300 s", 300)]:
    for fam in sel["best"] + ["ALL"]:
        for per in ["early", "late", "both"]:
            rs = [r for r in rows if (fam == "ALL" or r["fam"] == fam) and (per == "both" or r["late"] == (per == "late"))]
            got = ctape(rs, delay)
            s = cl_stats([(r["event"], pr, sh) for r, pr, sh, _ in got])
            if not s:
                continue
            m, se, t, nev = s
            cost = sum(x[3] for x in got)
            res_a[(name, fam, per)] = {"n": len(got), "net": m, "t": t}
            P(f"{name} | {fam} | {per} | {len(got)} | {nev} | {sum(1 for r, *_ in got if r['pay'] < 1)} | {sum(x[2] for x in got):,.0f} | "
              f"{cost:,.0f} | {100*m:+.2f} | {100*se:.2f} | {t:+.1f} | {100*sum(x[1] for x in got)/cost:+.2f}")
P()

# A3 timing
P("## A3 When the qualifying prints happen (A1 rows, after entry time t)")
P()
P("category | markets with prints | median s from t to first print | median s from t to last print | "
  "share of $ > 60 s after the market's first print | share of $ > 10 min after first print | median print $ | distinct taker wallets per market (median)")
P("|".join(["---"] * 8))
for fam in sel["best"] + ["ALL"]:
    rs = [r for r in rows if (fam == "ALL" or r["fam"] == fam)]
    first, last, usd, usd60, usd600, psz, nw = [], [], 0.0, 0.0, 0.0, [], []
    nm = 0
    for r in rs:
        pp = [p for p in r["prints"] if p[0] >= r["t"]]
        if not pp:
            continue
        nm += 1
        f0 = pp[0][0]
        first.append(f0 - r["t"])
        last.append(pp[-1][0] - r["t"])
        nw.append(len({p[3] for p in pp}))
        for t, price, size, w in pp:
            u = price * size
            usd += u
            psz.append(u)
            if t > f0 + 60:
                usd60 += u
            if t > f0 + 600:
                usd600 += u
    if nm:
        P(f"{fam} | {nm} | {statistics.median(first):,.0f} | {statistics.median(last):,.0f} | {100*usd60/usd:.0f}% | {100*usd600/usd:.0f}% | "
          f"{statistics.median(psz):,.1f} | {statistics.median(nw):.0f}")
P()

# A4 size
P("## A4 Was there room for a 5-100 USD order? (qualifying taker BUY dollars after t, per market)")
P()
P("category | period | markets in tape sample | with >= $5 | >= $20 | >= $100 | median $ after t")
P("|".join(["---"] * 7))
for fam in sel["best"] + ["ALL"]:
    for per in ["early", "late"]:
        rs = [r for r in rows if (fam == "ALL" or r["fam"] == fam) and r["late"] == (per == "late")]
        dol = [sum(p[1] * p[2] for p in r["prints"] if p[0] >= r["t"]) for r in rs]
        if dol:
            P(f"{fam} | {per} | {len(rs)} | {sum(d >= 5 for d in dol)} | {sum(d >= 20 for d in dol)} | {sum(d >= 100 for d in dol)} | {statistics.median(dol):,.0f}")
P()

# ---------------- D1 weekday / weekend
ok = [r for r in panel.values() if not r["drop"]]
ent = [r for r in ok if r["claim"]]
P("## D1 Weekday vs weekend (by closedTime, UTC). Descriptive.")
P()
P("Claim entries, C-mid (mid at the entry bucket, fee included):")
P()
P("category | days | markets | entries per day (sample) | entries per day (universe est.) | not-win | net c/share | t (event)")
P("|".join(["---"] * 8))
# days in [Oct 20, Nov 25): 36 days, of which weekend days:
from datetime import timedelta
d0 = datetime(2026, 10, 20, tzinfo=timezone.utc)
ndays = Counter("weekend" if (d0 + timedelta(days=i)).weekday() >= 5 else "weekday" for i in range(36))
SCALE = 36604 / 5000
for fam in ["crypto", "politics", "sports", "weather", "ALL"]:
    for wk in ["weekday", "weekend"]:
        rs = [r for r in ent if (fam == "ALL" or r["fam"] == fam) and ("weekend" if weekend(r["closed"]) else "weekday") == wk]
        if not rs:
            continue
        items = [(r["event"], r["claim"]["pay"] - r["claim"]["p"] - fee_per_share(r["claim"]["p"], r["rate"]), 1.0) for r in rs]
        m, se, t, nev = cl_stats(items)
        P(f"{fam} | {wk} ({ndays[wk]} d) | {len(rs)} | {len(rs)/ndays[wk]:.1f} | {len(rs)/ndays[wk]*SCALE:.0f} | {sum(1 for r in rs if r['claim']['pay'] < 1)} | {100*m:+.2f} | {t:+.1f}")
P()
P("C-tape A1 (crypto + politics tape sample):")
P()
P("category | days | markets with prints | losing | net c/share | t (event) | qualifying taker-BUY $ per day (universe est.)")
P("|".join(["---"] * 7))
for fam in sel["best"] + ["ALL"]:
    for wk in ["weekday", "weekend"]:
        rs = [r for r in rows if (fam == "ALL" or r["fam"] == fam) and ("weekend" if weekend(r["closed"]) else "weekday") == wk]
        got = ctape(rs, 0)
        s = cl_stats([(r["event"], pr, sh) for r, pr, sh, _ in got])
        if not s:
            continue
        m, se, t, nev = s
        usd = sum(sum(p[1] * p[2] for p in r["prints"] if p[0] >= r["t"]) for r in rs)
        scale = (sel["pool"][fam] / len(sel["chosen"][fam]) * SCALE) if fam != "ALL" else SCALE
        P(f"{fam} | {wk} ({ndays[wk]} d) | {len(got)} | {sum(1 for r, *_ in got if r['pay'] < 1)} | {100*m:+.2f} | {t:+.1f} | {usd*scale/ndays[wk]:,.0f}")
P()

# ---------------- D2 crypto sub-types
P("## D2 Crypto sub-types")
P()
P("type | claim markets | not-win | C-mid net c/share | t (event) | mean lock-up h | C-tape A1 markets | A1 net c/share | A1 t (event)")
P("|".join(["---"] * 9))
types = sorted({crypto_type(r["slug"]) for r in ent if r["fam"] == "crypto"})
for ty in types:
    rs = [r for r in ent if r["fam"] == "crypto" and crypto_type(r["slug"]) == ty]
    items = [(r["event"], r["claim"]["pay"] - r["claim"]["p"] - fee_per_share(r["claim"]["p"], r["rate"]), 1.0) for r in rs]
    m, se, t, nev = cl_stats(items)
    got = ctape([r for r in rows if r["fam"] == "crypto" and r["ctype"] == ty], 0)
    s2 = cl_stats([(r["event"], pr, sh) for r, pr, sh, _ in got])
    a = f"{len(got)} | {100*s2[0]:+.2f} | {s2[2]:+.1f}" if s2 else "0 | - | -"
    P(f"{ty} | {len(rs)} | {sum(1 for r in rs if r['claim']['pay'] < 1)} | {100*m:+.2f} | {t:+.1f} | {sum(r['claim']['lock_h'] for r in rs)/len(rs):.1f} | {a}")
P()

# ---------------- D3 pooled exploratory
P("## D3 Exploratory pooled row (post hoc): all families except sports and weather")
P()
P("variant | period | markets | events | not-win | win % | Wilson 95% | mean price | net c/share | t (event) | break-even win % at mean price+fee")
P("|".join(["---"] * 11))
for var in ["C-mid", "C-cons"]:
    for per in ["early", "late", "both"]:
        rs = [r for r in ent if r["fam"] not in ("sports", "weather") and (per == "both" or r["late"] == (per == "late"))]
        items, prices = [], []
        for r in rs:
            c = r["claim"]
            if var == "C-mid":
                p = c["p"]
            else:
                if c["p_next"] is None:
                    continue
                p = min(c["p_next"] + 0.005, 0.999)
            f = fee_per_share(p, r["rate"])
            items.append((r["event"], c["pay"] - p - f, 1.0, c["pay"]))
            prices.append(p + f)
        m, se, t, nev = cl_stats([(a, b, c) for a, b, c, _ in items])
        w = sum(1 for x in items if x[3] >= 1)
        lo, hi = wilson(w, len(items))
        P(f"{var} | {per} | {len(items)} | {nev} | {len(items)-w} | {100*w/len(items):.2f} | {100*lo:.1f}-{100*hi:.1f} | "
          f"{sum(prices)/len(prices):.4f} | {100*m:+.2f} | {t:+.1f} | {100*sum(prices)/len(prices):.2f}")
P()
(OUT / "attack_tables.md").write_text("\n".join(L) + "\n")
pickle.dump(res_a, open(DATA / "attack.pkl", "wb"))
print("\n".join(L))

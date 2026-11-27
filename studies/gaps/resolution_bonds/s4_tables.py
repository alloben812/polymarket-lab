"""Step 4: tables for B-a, B-b, the claim (C-mid, C-cons) and B-d from the panel. Writes out/tables.md etc.

Usage: python3 s4_tables.py [slice]
"""
import csv
import json
import pickle
import statistics
import sys
from collections import Counter, defaultdict

from pmlab.fees import fee_per_share
from pmlab.stats import ratio_cluster, wilson
from common import BUCKET_NAMES, BUCKETS, DATA, EPS, OUT, bucket_of, iso

SLICE = len(sys.argv) > 1
panel = pickle.load(open(DATA / ("panel_slice.pkl" if SLICE else "panel.pkl"), "rb"))
lines = []
CELLS = Counter()


def P(s=""):
    lines.append(s)


def cats_of(r):
    out = [r["fam"], "ALL"]
    if r["sub"]:
        out.append(r["sub"])
    return out


FAMS = sorted({r["fam"] for r in panel})
CAT_ROWS = []
for f in FAMS:
    CAT_ROWS.append(f)
    if f == "sports":
        CAT_ROWS += ["sports/start", "sports/other"]
CAT_ROWS.append("ALL")


def stats(items):
    """items: list of (event, pay, price, rate, lock_h). Returns dict of cell statistics."""
    n = len(items)
    if n == 0:
        return None
    wins = sum(1 for it in items if it[1] >= 1)
    lo, hi = wilson(wins, n)
    num, den = defaultdict(float), defaultdict(float)
    nets, cost = [], []
    for ev, pay, p, rate, lock in items:
        fee = fee_per_share(p, rate)
        net = pay - p - fee
        nets.append(net)
        cost.append(p + fee)
        num[ev] += net
        den[ev] += 1
    evs = list(num)
    mean, se, t = ratio_cluster([num[e] for e in evs], [den[e] for e in evs])
    lock = [it[4] for it in items]
    mlock = sum(lock) / n
    mcost = sum(cost) / n
    return {"n": n, "ev": len(evs), "wins": wins, "wr": wins / n, "lo": lo, "hi": hi, "p": sum(it[2] for it in items) / n,
            "fee": sum(fee_per_share(it[2], it[3]) for it in items) / n, "net": mean, "se": se, "t": t, "lock": mlock,
            "lock_med": statistics.median(lock), "ret_day": (mean / mcost) / (mlock / 24) if mlock > 0 else float("nan"),
            "sum_net": sum(nets)}


def fmt(s, extra=""):
    if s is None:
        return None
    return (f"{s['n']} | {s['ev']} | {s['n']-s['wins']} | {100*s['wr']:.2f} | {100*s['lo']:.1f}-{100*s['hi']:.1f} | {s['p']:.4f} | "
            f"{100*s['fee']:.3f} | {100*s['net']:+.2f} | {100*s['se']:.2f} | {s['t']:+.1f} | {s['lock']:.1f} | {s['lock_med']:.1f} | {100*s['ret_day']:+.2f}")


HEAD = "markets | events | not-win | win % | Wilson 95% | mean price | fee c | net c/share | SE c | t (event) | lock-up h mean | median | ret %/day"
SEP = "|".join(["---"] * (HEAD.count("|") + 1))

ok = [r for r in panel if not r["drop"]]
P(f"# Tables ({'SLICE' if SLICE else 'full sample'})")
P()
P(f"Sample markets: {len(panel)}; dropped: {dict(Counter(r['drop'] for r in panel if r['drop']))}; analysed: {len(ok)}.")
P(f"By family (analysed): {dict(Counter(r['fam'] for r in ok))}; sports sub-rows: {dict(Counter(r['sub'] for r in ok if r['sub']))}.")
P(f"By period (analysed): early {sum(1 for r in ok if not r['late'])}, late {sum(1 for r in ok if r['late'])}.")
P(f"Fee-rate source: {dict(Counter(r['rate_src'] for r in ok))}; rates: {dict(Counter((r['fam'], r['rate']) for r in ok))}.")
P(f"Events (analysed): {len({r['event'] for r in ok})}. Observations with one token imputed as 1 - other: {sum(r['imputed'] for r in ok)}.")
P()

# ---- timing: closedTime - endDate by category (all sample rows)
P("## closedTime - endDate (hours), all sampled markets")
P()
P("category | markets | closed >24 h before endDate | closed before endDate | gap >= 30 min | p10 | p25 | median | p75 | p90")
P("|".join(["---"] * 10))
for c in CAT_ROWS:
    g = [r["gap"] / 3600 for r in panel if c in cats_of(r)]
    if not g:
        continue
    g.sort()
    q = lambda f: g[min(len(g) - 1, int(f * len(g)))]
    P(f"{c} | {len(g)} | {sum(1 for x in g if x <= -24.25)} | {sum(1 for x in g if x < 0)} | {sum(1 for x in g if x >= 0.5)} | {q(.1):.1f} | {q(.25):.1f} | {q(.5):.1f} | {q(.75):.1f} | {q(.9):.1f}")
P()

# ---- sanity calibration
P("## Sanity: calibration of favourites below 0.80 (all categories, all five B-a observation times pooled per time)")
P()
P("obs | bucket | " + HEAD)
P("---|---|" + SEP)
for name in ["T-24h", "T-6h", "T-1h", "T-10m", "T"]:
    for lo, hi in [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8)]:
        items = [(r["event"], o["pay"], o["p"], r["rate"], o["lock_h"]) for r in ok if (o := r["obs"].get(name)) and lo - EPS <= o["p"] < hi - EPS]
        s = stats(items)
        if s:
            P(f"{name} | {lo:.2f}-{hi:.2f} | {fmt(s)}")
P()

# ---- B-a
P("## B-a Calibration near the end (purchase at the mid; fee from feeSchedule)")
P()
for name in ["T-24h", "T-6h", "T-1h", "T-10m", "T"]:
    P(f"### Observation {name}")
    P()
    nvalid = sum(1 for r in ok if name in r["obs"])
    nb = sum(1 for r in ok if name in r["obs"] and r["obs"][name]["p"] >= 0.8 - EPS)
    P(f"Markets with a valid observation: {nvalid}; favourite >= 0.80: {nb}.")
    P()
    P("category | bucket | " + HEAD)
    P("---|---|" + SEP)
    for c in CAT_ROWS:
        for bi, bn in enumerate(BUCKET_NAMES):
            items = [(r["event"], o["pay"], o["p"], r["rate"], o["lock_h"]) for r in ok
                     if c in cats_of(r) and (o := r["obs"].get(name)) and bucket_of(o["p"]) == bi]
            CELLS["B-a"] += 1
            s = stats(items)
            if s:
                P(f"{c} | {bn} | {fmt(s)}")
    P()

# ---- B-b
P("## B-b The post-endDate window (markets with closedTime - endDate >= 30 min)")
P()
post = [r for r in ok if r["gap"] >= 1800]
P(f"Markets: {len(post)} of {len(ok)} analysed.")
P()
P("category | obs | with favourite price | fav < 0.99 % | fav < 0.98 % | fav < 0.95 % | fav < 0.80 %")
P("|".join(["---"] * 7))
for c in CAT_ROWS:
    for name in ["T", "T+10m", "T+1h"]:
        ps = [r["obs"][name]["p"] for r in post if c in cats_of(r) and name in r["obs"]]
        CELLS["B-b share"] += 1
        if not ps:
            continue
        sh = lambda x: 100 * sum(1 for p in ps if p < x - EPS) / len(ps)
        P(f"{c} | {name} | {len(ps)} | {sh(.99):.1f} | {sh(.98):.1f} | {sh(.95):.1f} | {sh(.80):.1f}")
P()
P("What those favourites went on to do (same markets; purchase at the mid at that time):")
P()
P("category | obs | fav price band | " + HEAD)
P("---|---|---|" + SEP)
BANDS = [("0.50-0.80", 0.5, 0.8), ("0.80-0.95", 0.8, 0.95), ("0.95-0.98", 0.95, 0.98), ("0.98-0.99", 0.98, 0.99), (">=0.99", 0.99, 1.01)]
for c in CAT_ROWS:
    for name in ["T", "T+10m", "T+1h"]:
        for bn, lo, hi in BANDS:
            items = [(r["event"], o["pay"], o["p"], r["rate"], o["lock_h"]) for r in post
                     if c in cats_of(r) and (o := r["obs"].get(name)) and lo - EPS <= o["p"] < hi - EPS]
            CELLS["B-b outcome"] += 1
            s = stats(items)
            if s:
                P(f"{c} | {name} | {bn} | {fmt(s)}")
P()

# ---- claim
P("## Pre-registered claim: first time the favourite's mid is in [0.95, 0.98) from endDate - 1 h to closedTime")
P()
ent = [r for r in ok if r["claim"]]
P(f"Markets with an entry: {len(ent)} of {len(ok)} (early {sum(1 for r in ent if not r['late'])}, late {sum(1 for r in ent if r['late'])}). "
  f"Entry before endDate: {sum(1 for r in ent if r['claim']['rel_end_h'] < 0)}, at/after: {sum(1 for r in ent if r['claim']['rel_end_h'] >= 0)}. "
  f"No usable next bucket (dropped from C-cons): {sum(1 for r in ent if r['claim']['p_next'] is None)}.")
P()
claim_out = {}
for var in ["C-mid", "C-cons"]:
    P(f"### {var}")
    P()
    P("category | period | " + HEAD)
    P("---|---|" + SEP)
    for c in CAT_ROWS:
        for per in ["early", "late", "both"]:
            items = []
            for r in ent:
                if c not in cats_of(r):
                    continue
                if per != "both" and r["late"] != (per == "late"):
                    continue
                cl = r["claim"]
                if var == "C-mid":
                    price = cl["p"]
                else:
                    if cl["p_next"] is None:
                        continue
                    price = min(cl["p_next"] + 0.005, 0.999)
                items.append((r["event"], cl["pay"], price, r["rate"], cl["lock_h"]))
            if per != "both":
                CELLS[var] += 1
            s = stats(items)
            claim_out[(var, c, per)] = s
            if s:
                P(f"{c} | {per} | {fmt(s)}")
    P()
pickle.dump(claim_out, open(DATA / ("claim_slice.pkl" if SLICE else "claim.pkl"), "wb"))

# ---- B-d
P("## B-d Losers: an outcome with mid >= 0.95 at some bucket in [endDate - 24 h, closedTime) that did not pay 1")
P()
los = [r for r in ok if r["loser"]]
los.sort(key=lambda r: -r["loser"]["pmax"])
P(f"Markets: {len(los)} of {len(ok)} analysed ({100*len(los)/max(1,len(ok)):.2f}%). By family: {dict(Counter(r['fam'] for r in los))}. "
  f"50-50 resolutions among them: {sum(1 for r in los if r['loser']['pay'] == 0.5)}.")
everhi = Counter()
for r in ok:
    everhi[r["fam"]] += 1
P()
P("slug | category | outcome | payoff | max mid | buckets >= 0.95 | first seen (h rel. endDate) | last seen (h before closedTime) | endDate | closedTime")
P("|".join(["---"] * 10))
with open(OUT / ("losers_slice.csv" if SLICE else "losers.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["slug", "family", "sub", "event", "outcome", "payoff", "pmax", "n_buckets", "first_rel_end_h", "last_before_close_h", "endDate", "closedTime", "volume", "cid"])
    for r in los:
        L = r["loser"]
        w.writerow([r["slug"], r["fam"], r["sub"], r["event"], L["outcome"], L["pay"], L["pmax"], L["n_buckets"], round((L["t_first"] - r["end"]) / 3600, 2),
                    round((r["closed"] - L["t_last"]) / 3600, 2), iso(r["end"]), iso(r["closed"]), round(r["vol"]), r["cid"]])
        P(f"{r['slug']} | {r['sub'] or r['fam']} | {L['outcome']} | {L['pay']} | {L['pmax']:.4f} | {L['n_buckets']} | {(L['t_first']-r['end'])/3600:+.1f} | "
          f"{(r['closed']-L['t_last'])/3600:.1f} | {iso(r['end'])} | {iso(r['closed'])}")
P()
P(f"Cells counted: {dict(CELLS)} (total {sum(CELLS.values())}).")
(OUT / ("tables_slice.md" if SLICE else "tables.md")).write_text("\n".join(lines) + "\n")
print("\n".join(lines[:12]))
print("cells", dict(CELLS))

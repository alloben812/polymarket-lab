"""Independent recomputation for audit.md (does not import the author's measure.py / diag.py).
Reads data/gaps_econ directly. Prints all numbers used in audit.md and writes audit/recompute.json.
Usage: python3 -I recompute.py"""
import gzip, json, collections, random, calendar, time, math

D = "/home/user/polymarket-lab/data/gaps_econ"
OUTF = "/home/user/polymarket-lab/studies/gaps/econ_release_sniper/audit/recompute.json"
SPLIT = calendar.timegm((2026, 10, 15, 0, 0, 0))
DAYS = {"all": 87.0, "early": 44.0, "late": 43.0}
BLSBEA = {"Employment", "CPI", "PPI", "PCE", "GDP", "JOLTS"}
US = BLSBEA | {"FOMC", "ISM", "UMich"}

status = json.load(open(D + "/release_status.json"))
allm = json.load(open(D + "/markets.json"))["markets"]
kept = [m for m in allm if "DROPPED" not in status[m["release"]]]
mech = [m for m in kept if m["flag"] == ""]

# ---------- tapes -> winner-side view
def view(m):
    raw = json.load(gzip.open(D + "/tapes/" + m["cond"] + ".json.gz"))["rows"]
    seen = collections.Counter(tuple(r) for r in raw)
    dup = sum(c - 1 for c in seen.values() if c > 1)
    out = []
    for ts, side, oi, oname, p, sz, wal in raw:
        name = oname if oname in ("Yes", "No") else ("Yes" if oi == 0 else "No")
        win_tok = name == m["winner"]
        # price at which the WINNER token changed hands from the maker's side
        wpx = p if win_tok else 1 - p
        # taker obtained the winner (bought winner or sold loser)
        took_winner = (side == "BUY") == win_tok
        out.append((ts - m["T"], wpx, sz, wal or "?", took_winner))
    return out, dup

TAPE, DUPS = {}, 0
for m in kept:
    TAPE[m["cond"]], d = view(m)
    DUPS += d
CL = sorted({m["T"] for m in kept})
EARLY = [t for t in CL if t < SPLIT]
LATE = [t for t in CL if t >= SPLIT]
print("markets kept", len(kept), "mech", len(mech), "release seconds", len(CL), "early", len(EARLY), "late", len(LATE),
      "exact duplicate rows", DUPS)

def fee(p, q, rate=0.01):
    return rate * p * (1 - p) * q

def stale(m, lo=0, hi=10**9, cap=0.95):
    return [r for r in TAPE[m["cond"]] if lo <= r[0] <= hi and r[4] and r[1] < cap - 1e-9]

# ---------- pool
def pool(ms, hi):
    usd = prof = 0.0
    wal = collections.Counter()
    rel = set()
    for m in ms:
        for b, wp, z, w, _ in stale(m, 0, hi):
            g = z * (1 - wp) - fee(wp, z)
            usd += z * wp; prof += g; wal[w] += g; rel.add(m["T"])
    top = sum(v for _, v in wal.most_common(3))
    return dict(usd=round(usd), profit=round(prof), wallets=len(wal), top3=round(top / prof, 3) if prof else None,
                releases=len(rel))

POOL = {k: pool(kept, h) for k, h in (("b<=5", 5), ("b<=8", 8), ("b<=13", 13), ("all", 10**9))}
# first block per release second
fb_usd = fb_prof = 0.0; fbw = collections.Counter(); fbn = 0
byT = collections.defaultdict(list)
for m in kept:
    byT[m["T"]].append(m)
for T, ms in byT.items():
    rows = [r for m in ms for r in stale(m)]
    if not rows:
        continue
    fbn += 1
    b0 = min(r[0] for r in rows)
    for b, wp, z, w, _ in rows:
        if b == b0:
            g = z * (1 - wp) - fee(wp, z); fb_usd += z * wp; fb_prof += g; fbw[w] += g
POOL["first block"] = dict(usd=round(fb_usd), profit=round(fb_prof), wallets=len(fbw),
                           top3=round(sum(v for _, v in fbw.most_common(3)) / fb_prof, 3), releases=fbn)
print("POOL", json.dumps(POOL))

# ---------- one prepared order per market
def order(m, a, B, scen, lag=3.0, rate=0.01, lo_extra=0, skip_first_block=False, worst_first=False):
    lo, hi = a + lag + lo_extra, a + lag + 2
    rows = [r for r in TAPE[m["cond"]] if lo <= r[0] <= hi and r[4] and r[1] <= 0.95 + 1e-9]
    if skip_first_block:
        allst = [r for r in TAPE[m["cond"]] if r[0] >= 0 and r[4] and r[1] <= 0.95 + 1e-9]
        if allst:
            b0 = min(r[0] for r in allst)
            rows = [r for r in rows if r[0] > b0]
    if not rows:
        return 0.0, 0.0
    k = len({r[3] for r in rows})
    rows.sort(key=lambda r: -r[1] if worst_first else r[1])
    left = B; net = spent = 0.0
    for b, wp, z, w, _ in rows:
        avail = z if scen == "U" else z / (k + 1)
        q = min(avail, left / wp)
        if q <= 0:
            break
        net += q * (1 - wp) - fee(wp, q, rate); spent += q * wp; left -= q * wp
        if left <= 1e-9:
            break
    return net, spent

def cell(ms, a, B, scen, **kw):
    perT = collections.defaultdict(float); perM = {}; nfill = 0; spentT = collections.defaultdict(float)
    for m in ms:
        n, s = order(m, a, B, scen, **kw)
        perT[m["T"]] += n; perM[m["cond"]] = n; nfill += s > 0; spentT[m["T"]] += s
    return perT, perM, nfill, spentT

def stats(perT, Ts, days, seed=1):
    v = [perT.get(t, 0.0) for t in Ts]
    n = len(v); tot = sum(v); mu = tot / n
    se = math.sqrt(sum((x - mu) ** 2 for x in v) / (n - 1) / n)
    rnd = random.Random(seed)
    bs = sorted(sum(v[rnd.randrange(n)] for _ in range(n)) for _ in range(10000))
    k = 30.4 / days
    return dict(n=n, fills=sum(x > 1e-9 for x in v), total=round(tot, 1), month=round(tot * k, 1),
                ci=(round(bs[250] * k), round(bs[9749] * k)), t=round(mu / se, 2) if se else None)

def report(label, perT, nfill=None):
    r = {p: stats(perT, Ts, DAYS[p]) for p, Ts in (("all", CL), ("early", EARLY), ("late", LATE))}
    print(f"{label:58s} fills={nfill} all {r['all']['total']:8.1f} ({r['all']['month']}/mo CI {r['all']['ci']}) "
          f"early {r['early']['total']:7.1f} late {r['late']['total']:7.1f} ({r['late']['month']}/mo CI {r['late']['ci']} t {r['late']['t']})")
    return r

RES = {"pool": POOL, "cells": {}, "attacks": {}}
print("\n--- 12 protocol cells (recomputed)")
for a in (1, 3):
    for B in (20, 50, 200):
        for sc in ("U", "S"):
            perT, perM, nf, _ = cell(mech, a, B, sc)
            RES["cells"][f"A{a}_B{B}_{sc}"] = report(f"a=+{a}s B={B} {sc}", perT, nf)

print("\n--- attacks on the primary (a=+1 s, $50, S)")
P, PM, PN, PS = cell(mech, 1, 50, "S")
A = RES["attacks"]
# 1. by calendar day instead of release second (same as release second here? check)
days_of = {t: time.strftime("%Y-%m-%d", time.gmtime(t)) for t in CL}
print("release seconds", len(CL), "distinct days", len(set(days_of.values())))
# 2. timing: only prints that were matched after our arrival even at the longest lag 3.33 s (block >= a+3.33 -> b>=5)
A["strict_after_arrival"] = report("strict: only blocks b>=5 (matched after T+1 at any lag)", cell(mech, 1, 50, "S", lo_extra=1)[0])
# 3. second in line: the first stale block of each market goes to the incumbent
A["second_in_line"] = report("behind incumbent: skip each market's first stale block", cell(mech, 1, 50, "S", skip_first_block=True)[0])
A["second_in_line_U"] = report("behind incumbent, U", cell(mech, 1, 50, "U", skip_first_block=True)[0])
# 4. historical fee 0.04
A["fee_0.04"] = report("fee rate 0.04 (pre-Nov-21 economics level)", cell(mech, 1, 50, "S", rate=0.04)[0])
# 5. subsets
for name, sel in (("US only", lambda m: m["type"] in US), ("BLS/BEA only", lambda m: m["type"] in BLSBEA),
                  ("non-US only", lambda m: m["type"] not in US)):
    A[name] = report(f"primary, {name}", cell([m for m in mech if sel(m)], 1, 50, "S")[0])
# 6. leave out best release and best ten markets
best = max(CL, key=lambda t: P.get(t, 0))
A["minus_best_release"] = report(f"minus best release ({[m['release'] for m in mech if m['T']==best][0]})",
                                 {t: v for t, v in P.items() if t != best})
top10 = set(sorted(PM, key=PM.get, reverse=True)[:10])
A["minus_top10_markets"] = report("minus best 10 markets", cell([m for m in mech if m["cond"] not in top10], 1, 50, "S")[0])
# 7. concentration: share of total from top 3 releases
srt = sorted(P.values(), reverse=True)
print("primary: total", round(sum(srt), 1), "top-3 releases", [round(x, 1) for x in srt[:3]], "share",
      round(sum(srt[:3]) / sum(srt), 2), "releases with fills", sum(x > 1e-9 for x in srt), "filled orders", PN)
A["top3_release_share"] = round(sum(srt[:3]) / sum(srt), 3)
# 8. owner's set-up: a home Mac, matched at T+3..T+6 (sensitivity, auditor-run, not protocol cells)
for a in (2, 3, 4, 5, 6):
    A[f"arrival_{a}_S_B20"] = report(f"arrival +{a}s, $20, S (auditor sensitivity)", cell(mech, a, 20, "S")[0])
for a in (3, 4, 5):
    A[f"arrival_{a}_S_B20_BLSBEA"] = report(f"arrival +{a}s, $20, S, BLS/BEA only", cell([m for m in mech if m['type'] in BLSBEA], a, 20, "S")[0])
# 9. home Mac, behind incumbents, $20
for a in (1, 3, 5):
    A[f"arrival_{a}_S_B20_second"] = report(f"arrival +{a}s, $20, S, behind incumbent", cell(mech, a, 20, "S", skip_first_block=True)[0])
# 10. break-even wrong-mapping rate per filled order (a wrong order loses about its cost)
net_per = sum(P.values()) / PN; cost_per = sum(PS.values()) / PN
A["breakeven_error_rate"] = round(net_per / (net_per + cost_per), 3)
print("net per filled order", round(net_per, 2), "cost per filled order", round(cost_per, 2),
      "break-even share of wrong orders", A["breakeven_error_rate"])
# 11. price distribution of the primary's fills (how cheap)
fills = []
for m in mech:
    rows = [r for r in TAPE[m["cond"]] if 4 <= r[0] <= 6 and r[4] and r[1] <= 0.95 + 1e-9]
    fills += [r[1] for r in rows]
fills.sort()
print("stale print prices in primary window: n", len(fills), "median", fills[len(fills)//2], "share >=0.90",
      round(sum(x >= 0.90 for x in fills) / len(fills), 2))
# 12. who takes the primary window prints
wal = collections.Counter(); usd = 0
for m in mech:
    for b, wp, z, w, _ in stale(m, 4, 6, 0.9500001):
        wal[w] += z * (1 - wp); usd += z * (1 - wp)
print("primary-window gap $", round(usd), "wallets", len(wal), "top3 share", round(sum(v for _, v in wal.most_common(3)) / usd, 2),
      [(w[:8], round(v)) for w, v in wal.most_common(5)])
json.dump(RES, open(OUTF, "w"), indent=1)

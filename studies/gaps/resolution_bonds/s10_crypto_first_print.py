"""Step 10 (post hoc, not part of the verdict): what a few-seconds program would have got in crypto, one trade per
market. Crypto claim-entry markets of the 5,000 sample and of the s8 extension. Entry = the FIRST taker BUY print on
the entry-time favourite at [0.95, 0.98) with block time >= t + D (t = the 5-minute bucket that triggered the claim;
D = 10 s and 60 s), bought at that print's price; equal weight per market; fee 0.01 x p x (1-p) from the market rate.
Reports the per-market loss rate with Wilson interval, net per 10 USD, t clustered by event, by period and type."""
import gzip, json, pickle
from collections import defaultdict
from pmlab.fees import fee_per_share
from pmlab.stats import ratio_cluster, wilson
from common import DATA, EPS, OUT, iso
from s7_attack import crypto_type  # noqa: E402  (also re-writes out/attack_tables.md, same content)

LO, HI = 0.95, 0.98
rows = [dict(r, src="sample") for r in pickle.load(open(DATA / "panel.pkl", "rb")) if not r["drop"] and r["claim"] and r["fam"] == "crypto"]
rows += [dict(r, src="extension") for r in pickle.load(open(DATA / "ext" / "panel.pkl", "rb")) if not r["drop"] and r["claim"] and r["fam"] == "crypto"]
L = ["# Crypto, one trade per market at the first print after a delay (s10, post hoc)", "",
     f"Markets: {len(rows)} (sample {sum(r['src']=='sample' for r in rows)}, extension {sum(r['src']=='extension' for r in rows)}).", "",
     "delay | type | period | markets with a print | lost | loss % (Wilson 95%) | mean price | net per 10 USD | SE | t (event) | break-even loss %",
     "|".join(["---"] * 11)]
detail = []
for D in (10, 60):
    got = []
    for r in rows:
        p = DATA / "tapes" / f"{r['cid']}.json.gz"
        if not p.exists():
            continue
        d = json.load(gzip.open(p, "rt"))
        tok = r["tokens"][r["claim"]["k"]]
        cand = sorted((t, price) for t, side, tk, price, size, w in d["rows"]
                      if side == "BUY" and tk == tok and LO - EPS <= price < HI - EPS and r["claim"]["t"] + D <= t <= r["closed"])
        if not cand:
            continue
        t0, price = cand[0]
        cost = price + fee_per_share(price, r["rate"])
        got.append((r, price, cost, 10 * (r["claim"]["pay"] - cost) / cost))
        if D == 10 and r["claim"]["pay"] < 1:
            detail.append(f"{r['slug']} ({r['src']}, bought {price:.3f} at {iso(t0)}, {(r['closed']-t0)/60:.0f} min before settlement)")
    for ty in ("all", "up/down hourly", "other types"):
        for per in ("early", "late", "both"):
            g = [x for x in got if (per == "both" or x[0]["late"] == (per == "late"))
                 and (ty == "all" or (crypto_type(x[0]["slug"]) == "up/down hourly") == (ty == "up/down hourly"))]
            if not g:
                continue
            num, den = defaultdict(float), defaultdict(float)
            for r, price, cost, pr in g:
                num[r["event"]] += pr
                den[r["event"]] += 1
            ev = list(num)
            m, se, t = ratio_cluster([num[e] for e in ev], [den[e] for e in ev])
            k = sum(1 for x in g if x[0]["claim"]["pay"] < 1)
            lo, hi = wilson(k, len(g))
            mc = sum(x[2] for x in g) / len(g)
            L.append(f"{D} s | {ty} | {per} | {len(g)} | {k} | {100*k/len(g):.2f} ({100*lo:.1f}-{100*hi:.1f}) | {sum(x[1] for x in g)/len(g):.4f} | "
                     f"{m:+.3f} | {se:.3f} | {t:+.1f} | {100*(1-mc):.2f}")
L += ["", "Losing markets (10 s delay): " + "; ".join(detail)]
(OUT / "crypto_first_print.md").write_text("\n".join(L) + "\n")
print("\n".join(L))

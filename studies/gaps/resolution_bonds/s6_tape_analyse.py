"""Step 6: B-c capacity and C-tape from the tape sample (rules 18, 20, 21)."""
import gzip
import json
import pickle
import statistics
from collections import Counter, defaultdict

from pmlab.fees import fee_per_share
from pmlab.stats import ratio_cluster
from common import DATA, EPS, OUT

LO, HI = 0.95, 0.98
panel = {r["cid"]: r for r in pickle.load(open(DATA / "panel.pkl", "rb"))}
sel = json.loads((DATA / "tape_sample.json").read_text())
N_UNIVERSE = 36604
N_SAMPLE = len(panel)
DAYS = 36.0
L = []


def P(s=""):
    L.append(s)

P("# B-c capacity and C-tape")
P()
P(f"Best-looking categories ({sel['rule']}): {sel['best']}. Claim-entry markets in them: {sel['pool']}; tapes pulled: "
  f"{ {f: len(v) for f, v in sel['chosen'].items()} }.")
P()
rows = []
for fam, cids in sel["chosen"].items():
    for cid in cids:
        r = panel[cid]
        d = json.load(gzip.open(DATA / "tapes" / f"{cid}.json.gz", "rt"))
        t0, t1 = r["end"] - 3600, r["closed"]
        tape = d["rows"]
        oldest = min((x[0] for x in tape), default=None)
        trunc = bool(d["capped"] and oldest is not None and oldest > t0)
        kwin = next((k for k in (0, 1) if r["pay"][k] >= 1), None)
        kfav = r["claim"]["k"]
        o = {"cid": cid, "fam": fam, "event": r["event"], "late": r["late"], "trunc": trunc, "n_rows": len(tape), "slug": r["slug"],
             "win_buy_usd": 0.0, "win_sell_usd": 0.0, "win_buy_sh": 0.0, "win_sell_sh": 0.0,
             "fav_buy_sh": 0.0, "fav_buy_cost": 0.0, "fav_buy_profit": 0.0, "fav_pay": r["claim"]["pay"], "n_fav_buy": 0,
             "wallets": set(), "in_window_rows": 0, "lock_h": r["claim"]["lock_h"], "rate": r["rate"],
             "fav_buy_first_t": None}
        for t, side, tok, price, size, wallet in tape:
            if not (t0 <= t <= t1):
                continue
            o["in_window_rows"] += 1
            if not (LO - EPS <= price < HI - EPS):
                continue
            if kwin is not None and tok == r["tokens"][kwin]:
                if side == "BUY":
                    o["win_buy_usd"] += price * size
                    o["win_buy_sh"] += size
                else:
                    o["win_sell_usd"] += price * size
                    o["win_sell_sh"] += size
            if tok == r["tokens"][kfav] and side == "BUY":
                fee = fee_per_share(price, r["rate"])
                o["fav_buy_sh"] += size
                o["fav_buy_cost"] += size * (price + fee)
                o["fav_buy_profit"] += size * (r["claim"]["pay"] - price - fee)
                o["n_fav_buy"] += 1
                o["wallets"].add(wallet)
        o["n_wallets"] = len(o.pop("wallets"))
        rows.append(o)
pickle.dump(rows, open(DATA / "tape_rows.pkl", "wb"))

P(f"Tapes: {len(rows)}; truncated at the 60,000-row cap before the window start: {sum(r['trunc'] for r in rows)}; "
  f"tapes with no row inside the window: {sum(1 for r in rows if r['in_window_rows'] == 0)}.")
P()
P("## Capacity: dollars traded on the eventual WINNER at 0.95-0.98 in [endDate - 1 h, closedTime]")
P()
P("category | period | markets | with taker-BUY $ | median $ (all) | mean $ | total taker-BUY $ | total taker-SELL $ (bids hit) | universe est. taker-BUY $/day | universe est. taker-SELL $/day")
P("|".join(["---"] * 10))
for fam in sel["best"] + ["ALL"]:
    for per in ["early", "late", "both"]:
        rs = [r for r in rows if (fam == "ALL" or r["fam"] == fam) and (per == "both" or r["late"] == (per == "late"))]
        if not rs:
            continue
        b = [r["win_buy_usd"] for r in rs]
        s = [r["win_sell_usd"] for r in rs]
        # scale: tape sample -> claim-entry pool of the 5,000 sample -> universe; per day of the period part
        if fam == "ALL":
            scale = None
        else:
            scale = sel["pool"][fam] / len(sel["chosen"][fam]) * N_UNIVERSE / N_SAMPLE
        days = DAYS if per == "both" else (24.0 if per == "early" else 12.0)
        est_b = f"{sum(b)*scale/days:,.0f}" if scale else "-"
        est_s = f"{sum(s)*scale/days:,.0f}" if scale else "-"
        P(f"{fam} | {per} | {len(rs)} | {sum(1 for x in b if x > 0)} | {statistics.median(b):,.0f} | {sum(b)/len(b):,.0f} | {sum(b):,.0f} | {sum(s):,.0f} | {est_b} | {est_s}")
P()
P("## C-tape: taker BUY rows on the entry-time favourite at 0.95-0.98 in the window (price demonstrably available)")
P()
P("category | period | markets with such buys | events | losing markets | shares | $ cost | net c/share | SE (market) | t (market) | t (event) | net % of cost")
P("|".join(["---"] * 12))
ctape = {}
for fam in sel["best"] + ["ALL"]:
    for per in ["early", "late", "both"]:
        rs = [r for r in rows if (fam == "ALL" or r["fam"] == fam) and (per == "both" or r["late"] == (per == "late")) and r["fav_buy_sh"] > 0]
        if not rs:
            continue
        m, se, t = ratio_cluster([r["fav_buy_profit"] for r in rs], [r["fav_buy_sh"] for r in rs])
        num, den = defaultdict(float), defaultdict(float)
        for r in rs:
            num[r["event"]] += r["fav_buy_profit"]
            den[r["event"]] += r["fav_buy_sh"]
        ev = list(num)
        m2, se2, t2 = ratio_cluster([num[e] for e in ev], [den[e] for e in ev])
        cost = sum(r["fav_buy_cost"] for r in rs)
        ctape[(fam, per)] = {"n": len(rs), "ev": len(ev), "net": m, "t_m": t, "t_e": t2}
        P(f"{fam} | {per} | {len(rs)} | {len(ev)} | {sum(1 for r in rs if r['fav_pay'] < 1)} | {sum(r['fav_buy_sh'] for r in rs):,.0f} | {cost:,.0f} | "
          f"{100*m:+.2f} | {100*se:.2f} | {t:+.1f} | {t2:+.1f} | {100*sum(r['fav_buy_profit'] for r in rs)/cost:+.2f}")
P()
P("## Equal-size version: $100 per market (capped by the taker-BUY dollars on the tape), entry-time favourite")
P()
P("category | period | markets | events | losing | $ deployed | $ profit | profit per market $ | SE | t (event) | mean lock-up h")
P("|".join(["---"] * 11))
eq = {}
for fam in sel["best"] + ["ALL"]:
    for per in ["early", "late", "both"]:
        rs = [r for r in rows if (fam == "ALL" or r["fam"] == fam) and (per == "both" or r["late"] == (per == "late")) and r["fav_buy_sh"] > 0]
        if not rs:
            continue
        num, den, dep = defaultdict(float), defaultdict(float), 0.0
        for r in rs:
            size = min(100.0, r["fav_buy_cost"])
            pr = size * r["fav_buy_profit"] / r["fav_buy_cost"]
            num[r["event"]] += pr
            den[r["event"]] += 1
            dep += size
        ev = list(num)
        m, se, t = ratio_cluster([num[e] for e in ev], [den[e] for e in ev])
        eq[(fam, per)] = {"n": len(rs), "profit": sum(num.values()), "per_mkt": m, "t": t, "dep": dep}
        P(f"{fam} | {per} | {len(rs)} | {len(ev)} | {sum(1 for r in rs if r['fav_pay'] < 1)} | {dep:,.0f} | {sum(num.values()):+,.2f} | {m:+.3f} | {se:.3f} | {t:+.1f} | "
          f"{sum(r['lock_h'] for r in rs)/len(rs):.1f}")
P()
P("Losing markets in the tape sample (entry-time favourite did not pay 1): " + ", ".join(f"{r['slug']} ({r['fam']}, payoff {r['fav_pay']}, ${r['fav_buy_cost']:,.0f} bought at 0.95-0.98)" for r in rows if r["fav_pay"] < 1))
P()
pickle.dump({"ctape": ctape, "eq": eq}, open(DATA / "ctape.pkl", "wb"))
(OUT / "tape_tables.md").write_text("\n".join(L) + "\n")
print("\n".join(L))

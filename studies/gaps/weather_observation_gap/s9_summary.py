"""Post-hoc summary of out_full.json (written after the protocol; no new rule, no new variant).
Re-expresses the protocol fills of the 12 variants as: return on stake with a city-day-clustered 95% interval,
net per trade at a 10 USD stake, entries per calendar day, weekday vs weekend, and the timing of entries.
Also: the O1(b) stale pie per calendar day split weekday/weekend, and the O2 lock tables pooled by period."""
import collections, datetime as dt, json, statistics as st, sys
sys.path.insert(0, "/home/user/polymarket-lab")
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_observation_gap")
from pmlab import stats
from common import *

D = json.load(open(DATA + "/out_full.json"))
E = D["entries"]; O1 = D["o1"]; O2 = D["o2"]; ND = D["ndays"]
VARS = [f"A d={d}" for d in (5, 15, 60)] + [f"B h={h} cap={c:.2f}" for h in (19, 21, 23) for c in (0.80, 0.90, 0.95)]


def wkend(date):
    return dt.date.fromisoformat(date).weekday() >= 5


M = load_markets()
days = collections.defaultdict(set)
for e in M:
    per = "Oct" if e["date"] < "2026-11-01" else "Nov"
    days[(per, wkend(e["date"]))].add(e["date"])


def line(rows, ndays, fee=0.01):
    if not rows:
        return None
    byk = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for x in rows:
        net = x["pay"] - x["p"] - fee * x["p"] * (1 - x["p"])
        byk[x["key"]][0] += net * x["sh"]; byk[x["key"]][1] += x["p"] * x["sh"]; byk[x["key"]][2] += 1
    r, se, t = stats.ratio_cluster([v[0] for v in byk.values()], [v[1] for v in byk.values()])
    # equal 10 USD stake per entry: net = 10 * (pay - p - fee) / p
    n10 = [10 * (x["pay"] - x["p"] - fee * x["p"] * (1 - x["p"])) / x["p"] for x in rows]
    k10 = collections.defaultdict(float)
    for x, v in zip(rows, n10):
        k10[x["key"]] += v
    m10, se10, t10 = stats.mean_se(n10)
    lo10, hi10 = stats.bootstrap_sum_ci(list(k10.values()))
    losers = sum(1 for x in rows if x["pay"] == 0)
    return {"n": len(rows), "cd": len(byk), "per_day": len(rows) / ndays, "ret": 100 * r, "lo": 100 * (r - 1.96 * se) if se == se else float("nan"),
            "hi": 100 * (r + 1.96 * se) if se == se else float("nan"), "t": t, "n10": sum(n10) / len(n10), "sum10": sum(n10), "sum10_lo": lo10, "sum10_hi": hi10,
            "usd10_day": sum(n10) / ndays, "losers": losers, "stake": sum(v[1] for v in byk.values()), "net": sum(v[0] for v in byk.values()),
            "avgp": sum(x["p"] * x["sh"] for x in rows) / sum(x["sh"] for x in rows), "med_usd": st.median([x["p"] * x["sh"] for x in rows])}


print("Return on stake (net of fee 0.01, city-day clustered 95% interval) and the same fills at a fixed 10 USD stake per entry")
print("variant            per  entries cdays ent/day  avg px  med $/entry  return % [95%]          t     losers  net $ (actual size)  net/entry @$10  sum @$10 [bootstrap 95%]  $/day @$10")
for v in VARS:
    for per in ("Oct", "Nov"):
        s = line([x for x in E if x["var"] == v and x["per"] == per], ND[per])
        if not s:
            print(f"{v:18s} {per}  0"); continue
        print(f"{v:18s} {per}  {s['n']:6d} {s['cd']:5d} {s['per_day']:6.2f}  {s['avgp']:.3f}  {s['med_usd']:8.2f}   {s['ret']:+6.2f} [{s['lo']:+6.2f},{s['hi']:+6.2f}] {s['t']:+6.2f}  {s['losers']:4d}   {s['net']:+9.2f}           {s['n10']:+6.3f}      {s['sum10']:+8.2f} [{s['sum10_lo']:+.1f},{s['sum10_hi']:+.1f}]  {s['usd10_day']:+6.2f}")

print("\nWeekend (Sat/Sun observation dates) vs weekdays, both periods pooled, fee 0.01")
for v in VARS:
    for wk in (False, True):
        nd = len(days[("Oct", wk)]) + len(days[("Nov", wk)])
        s = line([x for x in E if x["var"] == v and wkend(x["date"]) == wk], nd)
        if s:
            print(f"{v:18s} {'weekend' if wk else 'weekday'} days={nd:3d} entries={s['n']:5d} ent/day={s['per_day']:5.2f} return {s['ret']:+6.2f}% [{s['lo']:+.2f},{s['hi']:+.2f}] t {s['t']:+.2f} net/entry@$10 {s['n10']:+.3f}")

print("\nEntry timing: seconds from the public time (obs + 300 s) to the entry print (rule A) / from the decision time (rule B)")
for v in VARS:
    xs = [x["mt"] - x["T"] for x in E if x["var"] == v]
    if xs:
        q = sorted(xs)
        print(f"{v:18s} n={len(q):5d} delay after T: median {st.median(q):.0f} s p10 {q[len(q)//10]:.0f} p90 {q[int(.9*len(q))]:.0f}")

print("\nO1(b) stale dead-bucket profit locked by all takers, per calendar day, weekday vs weekend (USD before fee)")
for per in ("Oct", "Nov"):
    for wk in (False, True):
        rr = [r for r in O1 if r["per"] == per and wkend(r["date"]) == wk]
        nd = len(days[(per, wk)]) or 1
        tot = {bn: sum(r["stale"].get(bn, [0, 0, 0])[1] for r in rr) for bn in ("pre", "0-5", "5-15", "15-60", "60+")}
        print(f"{per} {'weekend' if wk else 'weekday'} days={nd:2d} kills={len(rr):5d}  " + "  ".join(f"{k}: ${v/nd:,.1f}/day" for k, v in tot.items()))

print("\nO2 pooled: share of city-days where the lock bucket wins and its mean YES price, by hour and period")
for h in (17, 19, 21, 23):
    for per in ("Oct", "Nov"):
        rr = [r for r in O2 if r["h"] == h and r["per"] == per]
        n = len(rr); w = sum(r["lock_won"] for r in rr); lo, hi = stats.wilson(w, n)
        px = [r["lock_px"] for r in rr if r["lock_px"] is not None]
        print(f"{h:02d}h {per}: n={n} lock wins {100*w/n:.1f}% [{100*lo:.1f}-{100*hi:.1f}]  mean lock YES {sum(px)/len(px):.3f} (n px {len(px)})  "
              f"lock YES <= 0.95: {sum(p <= 0.95 for p in px)} of which won {sum(r['lock_won'] for r in rr if r['lock_px'] is not None and r['lock_px'] <= 0.95)}")

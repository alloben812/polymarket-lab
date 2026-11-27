"""Post-hoc summary of the protocol's own trades (no new signals; added when the study was resumed, see results.md).
Reads data/gaps_weather_fc/entries.csv written by s09_analyse.py and prints:
 S1 95% intervals (city-day clustered, normal approx.) for the selected cell and the 6 pooled rows, both periods,
    plus a cluster bootstrap interval for net dollars;
 S2 size-capped sensitivity: shares = min(10/p, size of the entry print) (AGENTS.md rule 4: no more than shown);
 S3 the 6 h decision entries one by one (small cells with large returns);
 S4 model probability vs realised win rate of the bought buckets.
Run with python3 -I."""
import csv, collections, math, sys
sys.path.insert(0, "/home/user/polymarket-lab")
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_forecast_gap")
import common as C
from pmlab.stats import ratio_cluster, bootstrap_sum_ci, wilson

E = []
for r in csv.DictReader(open(f"{C.DATA}/entries.csv")):
    for k in ("p", "y", "sh", "gap", "pm", "net", "net_actual", "fee", "size"):
        r[k] = float(r[k])
    r["slot"] = int(r["slot"]); r["g"] = float(r["g"])
    E.append(r)


def summ(L, capped=False):
    cd = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for e in L:
        sh = min(e["sh"], e["size"]) if capped else e["sh"]
        net = sh * (e["y"] - e["p"] - 0.01 * e["p"] * (1 - e["p"]))
        a = cd[(e["city"], e["date"])]; a[0] += net; a[1] += sh; a[2] += sh * e["p"]
    nums = [a[0] for a in cd.values()]
    ret, se, t = ratio_cluster(nums, [a[2] for a in cd.values()])
    cps, se2, _ = ratio_cluster(nums, [a[1] for a in cd.values()])
    lo, hi = bootstrap_sum_ci(nums)
    return dict(n=len(L), cd=len(cd), staked=sum(a[2] for a in cd.values()), net=sum(nums), ret=ret, se=se, t=t, cps=cps, se2=se2, lo=lo, hi=hi)


def row(s):
    return (f"| {s['n']} | {s['cd']} | {s['staked']:.0f} | {s['net']:+.1f} [{s['lo']:+.0f}, {s['hi']:+.0f}] | "
            f"{100*s['ret']:+.1f}% [{100*(s['ret']-1.96*s['se']):+.1f}, {100*(s['ret']+1.96*s['se']):+.1f}] | "
            f"{100*s['cps']:+.2f} [{100*(s['cps']-1.96*s['se2']):+.2f}, {100*(s['cps']+1.96*s['se2']):+.2f}] | {s['t']:.2f} |")


H = ("| entries | city-days | staked $ | net $ [95% bootstrap by city-day] | return on stake [95%] | net c/share [95%] | t (city-day) |\n"
     "|---|---|---|---|---|---|---|")
print("## S1. Intervals, fee 0.01, $10 per entry (protocol sizing)\n")
cells = [("AVG", 0.15, 60, "selected cell")] + [(v, g, None, "pooled") for v in ("BEST", "AVG") for g in (0.08, 0.15, 0.25)]
print("| version | g | decision | period " + H.split("\n")[0][1:]); print("|---|---|---|---" + H.split("\n")[1][0:])
for v, g, slot, lab in cells:
    for pd_ in ("tune", "report"):
        L = [e for e in E if e["v"] == v and e["g"] == g and e["period"] == pd_ and (slot is None or e["slot"] == slot)]
        print(f"| {v} | {g} | {lab if slot is None else f'{slot}h (selected)'} | {pd_} " + row(summ(L)))
print("\n## S2. Size-capped sensitivity: shares = min(10/p, shares of the entry print)\n")
print(f"entries whose print covered $10: {sum(1 for e in E if e['size'] >= e['sh'] - 1e-9)} of {len(E)}\n")
print("| version | g | decision | period " + H.split("\n")[0][1:]); print("|---|---|---|---" + H.split("\n")[1][0:])
for v, g, slot, lab in cells:
    for pd_ in ("tune", "report"):
        L = [e for e in E if e["v"] == v and e["g"] == g and e["period"] == pd_ and (slot is None or e["slot"] == slot)]
        print(f"| {v} | {g} | {lab if slot is None else f'{slot}h (selected)'} | {pd_} " + row(summ(L, capped=True)))
print("\n## S3. Entries at the 6 h decision (unique bucket x city-day; each may appear in several variants)\n")
seen = {}
for e in E:
    if e["slot"] == 6:
        k = (e["city"], e["date"], e["bucket"])
        seen.setdefault(k, [e, set()])[1].add(f"{e['v']}/{e['g']}")
print("| city | date | bucket | entry price | print shares | print $ | minutes after decision | model prob | won | variants |")
print("|---|---|---|---|---|---|---|---|---|---|")
for k, (e, vs) in sorted(seen.items()):
    print(f"| {k[0]} | {k[1]} | {k[2]} | {e['p']:.3f} | {e['size']:.1f} | {e['size']*e['p']:.2f} | {int(e['lag'])//60} | {e['pm']:.3f} | {int(e['y'])} | {', '.join(sorted(vs))} |")
print("\n## S4. Model probability of the bought bucket vs realised win rate (all 4,857 entries, all cells, both periods)\n")
print("| model prob | entries | mean model prob | mean price | win rate [Wilson 95%] |")
print("|---|---|---|---|---|")
for lo, hi in ((0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5), (0.5, 0.7), (0.7, 1.01)):
    L = [e for e in E if lo <= e["pm"] < hi]
    if not L: continue
    k = sum(int(e["y"]) for e in L); a, b = wilson(k, len(L))
    print(f"| {lo:.1f}-{min(hi,1):.1f} | {len(L)} | {sum(e['pm'] for e in L)/len(L):.3f} | {sum(e['p'] for e in L)/len(L):.3f} | {k/len(L):.3f} [{a:.3f}, {b:.3f}] |")

import json, collections, sys
import fin, ladder
from pmlab import stats
def d_of(r):
    kind, _ = ladder.strike(r["title"]); yes = r["out"] in ("Yes", "Up")
    up_if_yes = kind in ("hitHIGH", "above", "updown")
    return "bull" if (yes == up_if_yes) else "bear"
for n in sys.argv[1:]:
    rows = [r for r in json.load(open(f"cache/{n}_model.json")) if r["final"] is not None and r["side"] == "BUY"]
    print(f"\n#### {n}: resolved buy fills {len(rows)} (equity/ETF/index price markets)")
    def tab(keyfn, label, top=None):
        G = collections.defaultdict(list)
        for r in rows: G[keyfn(r)].append(r)
        items = sorted(G.items(), key=lambda kv: -sum((r["final"] - r["px"] - r["fee"]) * r["sz"] for r in kv[1])) if top else sorted(G.items())
        if top: items = items[:top] + items[-2:]
        print(f"  {label}")
        for k, rs in items:
            byc = collections.defaultdict(lambda: [0.0, 0.0])
            for r in rs: byc[r["cond"]][0] += (r["final"] - r["px"] - r["fee"]) * r["sz"]; byc[r["cond"]][1] += r["sz"]
            est, se, t = stats.ratio_cluster([v[0] for v in byc.values()], [v[1] for v in byc.values()]) if len(byc) > 2 else (float("nan"),) * 3
            usd = sum(r["px"] * r["sz"] for r in rs); net = sum(v[0] for v in byc.values())
            print(f"    {str(k):22} mkts {len(byc):4} usd {usd:8.0f} avg px {usd / sum(r['sz'] for r in rs):.2f} net ${net:8.0f} ({net / usd:6.1%})  c/sh {100 * est:6.2f} t {t:5.1f}")
    tab(d_of, "by direction")
    tab(lambda r: "wk" + str(1 + (r["t"] - 1793980800) // (7 * 86400)), "by week of the fill (wk1 = Nov 6-13, wk2 = Nov 13-20, wk3 = Nov 20-27)")
    tab(lambda r: (d_of(r), "px<0.45" if r["px"] < .45 else "px>=0.45"), "direction x price")
    tab(lambda r: r["tk"], "by ticker (top 5 and bottom 2 by net $)", top=5)

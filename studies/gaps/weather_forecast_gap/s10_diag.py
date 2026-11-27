"""Post-hoc DESCRIPTIVE diagnostics (not rule variants, added after the slice run; see results.md "Deviations"):
 D1 market-implied expected maximum vs the forecast: MAE in F at each decision time;
 D2 top bucket hit rate: market favourite vs model's most likely bucket;
 D3 encompassing regression per bucket: won ~ a + b1*market_prob + b2*model_prob (OLS, errors clustered by city-day).
Run with python3 -I."""
import bisect, csv, gzip, json, sys, collections, statistics
import numpy as np
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_forecast_gap")
import common as C

markets = collections.defaultdict(list); M = {}
for r in csv.DictReader(open(f"{C.DATA}/markets.csv")):
    r["lo"], r["hi"], r["t_end"] = int(r["lo"]), int(r["hi"]), int(r["t_end"]); markets[(r["city"], r["date"])].append(r); M[r["condition"]] = r
win = {r["condition"]: float(r["yes_final"]) for r in csv.DictReader(open(f"{C.DATA}/winners.csv")) if r["yes_final"] != ""}
obs = {(r["station"], r["date"]): int(r["max_f"]) for r in csv.DictReader(open(f"{C.DATA}/obs_max.csv")) if int(r["n_reports"]) >= 20}
prob = collections.defaultdict(dict)
for r in csv.DictReader(open(f"{C.DATA}/model_probs.csv")):
    prob[(r["city"], r["date"], int(r["slot"]), r["version"])][r["condition"]] = float(r["prob"])
meta = {(r["city"], r["date"], int(r["slot"]), r["version"]): r for r in csv.DictReader(open(f"{C.DATA}/model_meta.csv"))}
PX = {}
with gzip.open(f"{C.DATA}/prices.jsonl.gz", "rt") as f:
    for line in f:
        try: o = json.loads(line)
        except ValueError: continue
        PX[o["c"]] = ([p[0] for p in o["pts"]], [p[1] for p in o["pts"]])


def px_at(c, t):
    if c not in PX: return None
    ts, ps = PX[c]; i = bisect.bisect_right(ts, t) - 1
    return ps[i] if i >= 0 and t - ts[i] <= 6 * 3600 else None


def mid(m):
    if m["lo"] < -1000: return m["hi"] - 0.5
    if m["hi"] > 1000: return m["lo"] + 0.5
    return (m["lo"] + m["hi"]) / 2


def ols_cluster(X, y, groups):
    X = np.asarray(X, float); y = np.asarray(y, float)
    XtX = np.linalg.inv(X.T @ X); b = XtX @ X.T @ y; u = y - X @ b
    meat = np.zeros((X.shape[1], X.shape[1]))
    idx = collections.defaultdict(list)
    for i, g in enumerate(groups): idx[g].append(i)
    for ii in idx.values():
        s = X[ii].T @ u[ii]; meat += np.outer(s, s)
    G = len(idx); V = XtX @ meat @ XtX * G / (G - 1)
    return b, np.sqrt(np.diag(V)), G


print("| period | decision | city-days | MAE market-implied mean | MAE forecast BEST | MAE forecast AVG | market favourite wins | model BEST top bucket wins | model AVG top bucket wins |")
print("|---|---|---|---|---|---|---|---|---|")
reg = collections.defaultdict(lambda: ([], [], []))
for pd_ in ("tune", "report"):
    for slot in C.SLOTS:
        mm, mb, ma, fw, bw, aw = [], [], [], [], [], []
        for (city, d), mk in markets.items():
            if (pd_ == "report") != (d >= C.SPLIT.isoformat()): continue
            if any(m["condition"] not in win for m in mk): continue
            st = mk[0]["station"]
            if (st, d) not in obs: continue
            t = mk[0]["t_end"] - slot * 3600
            pp = [px_at(m["condition"], t) for m in mk]
            if any(p is None for p in pp) or sum(pp) <= 0: continue
            kb, ka = (city, d, slot, "BEST"), (city, d, slot, "AVG")
            if kb not in prob or ka not in prob: continue
            s = sum(pp); q = [p / s for p in pp]
            mm.append(abs(sum(qi * mid(m) for qi, m in zip(q, mk)) - obs[(st, d)]))
            mb.append(abs(float(meta[kb]["f"]) + float(meta[kb]["bias_train"]) - obs[(st, d)])); ma.append(abs(float(meta[ka]["f"]) + float(meta[ka]["bias_train"]) - obs[(st, d)]))
            y = [win[m["condition"]] for m in mk]
            fw.append(y[max(range(len(mk)), key=lambda i: q[i])]); bw.append(y[max(range(len(mk)), key=lambda i: prob[kb][mk[i]["condition"]])]); aw.append(y[max(range(len(mk)), key=lambda i: prob[ka][mk[i]["condition"]])])
            for v, k in (("BEST", kb), ("AVG", ka)):
                X, Y, Gp = reg[(pd_, slot, v)]
                for qi, m, yi in zip(q, mk, y):
                    X.append([1.0, qi, prob[k][m["condition"]]]); Y.append(yi); Gp.append((city, d))
        if mm:
            print(f"| {pd_} | {slot}h | {len(mm)} | {statistics.mean(mm):.2f} | {statistics.mean(mb):.2f} | {statistics.mean(ma):.2f} | {statistics.mean(fw):.3f} | {statistics.mean(bw):.3f} | {statistics.mean(aw):.3f} |")
print("\n(forecast MAE here is after removing the trailing mean error, so it is comparable with the market-implied mean)\n")
print("| period | decision | version | buckets | city-days | coef market prob (se) | coef model prob (se) | t model |")
print("|---|---|---|---|---|---|---|---|")
for (pd_, slot, v), (X, Y, Gp) in sorted(reg.items(), key=lambda kv: (kv[0][0], -kv[0][1], kv[0][2]), reverse=False):
    if len(Y) < 100: continue
    b, se, G = ols_cluster(X, Y, Gp)
    print(f"| {pd_} | {slot}h | {v} | {len(Y)} | {G} | {b[1]:.3f} ({se[1]:.3f}) | {b[2]:+.3f} ({se[2]:.3f}) | {b[2]/se[2]:.2f} |")

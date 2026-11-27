"""Audit step 2: own quoter state machine on the audit replay (a1), k = 0, no capital limit, reporting period.
Compares market-day reward / settlement PnL with the author's marketdays_k0P / k0O for the same markets.
usage: python3 -I a2_quoter.py [SEL]
"""
import json, os, sys
import numpy as np, pandas as pd

SEL = int(sys.argv[1]) if len(sys.argv) > 1 else 0
HERE = os.path.dirname(os.path.abspath(__file__))
G = "/home/user/polymarket-lab/data/gaps_weather_rewards"
meta = json.load(open(G + "/meta.json"))
CONDS = sorted(meta)
CI = {c: i for i, c in enumerate(CONDS)}
d = pd.read_parquet(f"{HERE}/out/min_{SEL}.parquet").sort_values(["cond", "m"])
DATES = ["2026-10-%02d" % x for x in range(7, 12)]


def run(model, lat):
    inc_md, pnl_md, fills = {}, {}, []
    for c, g in d.groupby("cond"):
        fin = float(meta[c]["final_yes"])
        y = n_ = 0.0                                          # YES and NO shares held
        for r in g.itertuples(index=False):
            if not r.valid:
                continue
            net = y - n_
            if net == 0:
                if not r.in_both:
                    continue
                lb, la = True, True
            elif net > 0:
                if not r.in_ask:
                    continue
                lb, la = False, True
            else:
                if not r.in_bid:
                    continue
                lb, la = True, False
            tb = getattr(r, f"b{model}{lat}") if lb else -1
            ta = getattr(r, f"a{model}{lat}") if la else -1
            # alive at the sample (t_m + 30 s) unless filled before it
            bl = lb and not (0 <= tb <= 30_000)
            al = la and not (0 <= ta <= 30_000)
            sh = r.sh_both if (bl and al) else r.sh_bid if bl else r.sh_ask if al else 0.0
            day = DATES[r.m // 1440]
            inc_md[(c, day)] = inc_md.get((c, day), 0.0) + r.R / 1440 * sh
            if tb >= 0:
                p = r.bb / 1000; y += r.msz
                pnl_md[(c, day)] = pnl_md.get((c, day), 0.0) + (fin - p) * r.msz
                fills.append((c, r.m, 0, p, r.msz, fin))
            if ta >= 0:
                p = (1000 - r.ba) / 1000; n_ += r.msz
                pnl_md[(c, day)] = pnl_md.get((c, day), 0.0) + ((1 - fin) - p) * r.msz
                fills.append((c, r.m, 1, p, r.msz, fin))
    keys = sorted(set(inc_md) | set(pnl_md))
    md = pd.DataFrame([(c, dd, inc_md.get((c, dd), 0.0), pnl_md.get((c, dd), 0.0)) for c, dd in keys], columns=["cond", "date", "raw", "pnl"])
    md["reward"] = np.where(md.raw >= 1, md.raw, 0.0)
    md["net"] = md.reward + md.pnl
    md["event"] = md.cond.map(lambda c: meta[c]["event"])
    return md, pd.DataFrame(fills, columns=["cond", "m", "side", "price", "size", "fin"])


def clus(md, col="net"):
    e = md.groupby("event").agg(s=(col, "sum"), n=(col, "size"))
    N = e.n.sum(); mean = e.s.sum() / N
    resid = e.s - mean * e.n
    k = len(e)
    se = np.sqrt(k / (k - 1) * (resid ** 2).sum()) / N
    return mean, se, mean / se


res = {}
for model in ("P", "O"):
    a = pd.read_csv(f"{G}/marketdays_k0{model}.csv")
    a["cond"] = a.ci.map(lambda i: CONDS[i])
    a = a[a.cond.isin(set(d.cond)) & (a.date >= "2026-10-07")]
    for lat in (0, 2000, 5000):
        md, F = run(model, lat)
        m, se, t = clus(md)
        r = dict(market_days=len(md), markets=md.cond.nunique(), events=md.event.nunique(), reward_md=md.reward.mean(), raw_total=md.raw.sum(),
                 pnl_md=md.pnl.mean(), net_md=m, t=t, fills=len(F),
                 settle_c_per_share=100 * float(((np.where(F.side == 0, F.fin, 1 - F.fin) - F.price) * F["size"]).sum() / F["size"].sum()) if len(F) else None)
        if lat == 0:
            j = md.merge(a[["cond", "date", "raw", "pnl", "fills"]], on=["cond", "date"], how="outer", suffixes=("", "_a")).fillna(0)
            r["author_same_markets"] = dict(market_days=int(len(a)), raw_total=float(a.raw.sum()), pnl_total=float(a.pnl.sum()),
                                            fills=int(a.fills.sum()), net_md=float(a.net.mean()), t=float(clus(a.assign(net=a.net))[2]))
            r["mine_totals"] = dict(raw_total=float(md.raw.sum()), pnl_total=float(md.pnl.sum()))
            r["corr_raw_md"] = float(np.corrcoef(j.raw, j.raw_a)[0, 1]); r["corr_pnl_md"] = float(np.corrcoef(j.pnl, j.pnl_a)[0, 1])
            r["abs_raw_diff_gt_0.5"] = int((abs(j.raw - j.raw_a) > 0.5).sum())
            md.to_csv(f"{HERE}/out/md_{model}_{SEL}.csv", index=False); F.to_csv(f"{HERE}/out/fills_{model}_{SEL}.csv", index=False)
        res[f"k0{model}_lat{lat}"] = r
        print(model, lat, json.dumps(r, default=float), flush=True)
json.dump(res, open(f"{HERE}/out/a2_{SEL}.json", "w"), indent=1, default=float)

"""Audit step 6: queue-position fill models on the audit replay (a4), k = 0, no capital limit, reporting period.
Q1: a fresh order every minute joins behind the whole level shown at t_m; it fills when a print goes through the
    price (as P) or when prints AT our price add up to (queue ahead + our size). Cancellations ahead are ignored.
Q2: as Q1, but an unfilled order whose price is unchanged keeps its place: ahead = min(previous ahead - traded at
    the level, level size at t_m) (cancellations ahead of us allowed to shrink the queue).
Also re-runs P and O from the same file for a like-for-like comparison.
usage: python3 -I a6_queue.py SEL [SEL ...]
"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
G = "/home/user/polymarket-lab/data/gaps_weather_rewards"
meta = json.load(open(G + "/meta.json"))
DATES = ["2026-10-%02d" % x for x in range(7, 12)]
d = pd.concat([pd.read_parquet(f"{HERE}/out/minq_{s}.parquet") for s in sys.argv[1:]]).sort_values(["cond", "m"])


def first_fill(model, sweep, lt, lz, ahead, msz):
    """ms after t_m of the fill (-1 none) and the volume traded at our level during the minute."""
    vol = float(np.sum(lz)) if len(lz) else 0.0
    if model == "P":
        return sweep, vol
    if model == "O":
        c = ([sweep] if sweep >= 0 else []) + ([int(lt[0])] if len(lt) else [])
        return (min(c) if c else -1), vol
    t_q = -1
    if len(lz):
        cum = np.cumsum(lz)
        w = np.flatnonzero(cum >= ahead + msz)
        if len(w):
            t_q = int(lt[w[0]])
    c = [x for x in (sweep, t_q) if x >= 0]
    return (min(c) if c else -1), vol


def run(model):
    inc_md, pnl_md, fills = {}, {}, []
    for c, g in d.groupby("cond"):
        fin = float(meta[c]["final_yes"])
        y = n_ = 0.0
        prev = {0: None, 1: None}          # (minute, price, remaining ahead) of a live unfilled order per side
        for r in g.itertuples(index=False):
            if not r.valid:
                prev = {0: None, 1: None}; continue
            net = y - n_
            if net == 0:
                if not r.in_both:
                    prev = {0: None, 1: None}; continue
                lb, la = True, True
            elif net > 0:
                if not r.in_ask:
                    prev = {0: None, 1: None}; continue
                lb, la = False, True
            else:
                if not r.in_bid:
                    prev = {0: None, 1: None}; continue
                lb, la = True, False
            tt = {}
            for side, live, px, sz, sw, lt, lz in ((0, lb, r.bb, r.qb_sz, r.bP0, r.lb_t, r.lb_z), (1, la, r.ba, r.qa_sz, r.aP0, r.la_t, r.la_z)):
                if not live:
                    prev[side] = None; tt[side] = -1; continue
                ahead = sz
                if model == "Q2" and prev[side] is not None and prev[side][0] == r.m - 1 and prev[side][1] == px:
                    ahead = min(prev[side][2], sz)
                t, vol = first_fill(model, sw, np.asarray(lt), np.asarray(lz), ahead, r.msz)
                tt[side] = t
                prev[side] = None if t >= 0 else (r.m, px, max(ahead - vol, 0.0))
            bl = lb and not (0 <= tt[0] <= 30_000)
            al = la and not (0 <= tt[1] <= 30_000)
            sh = r.sh_both if (bl and al) else r.sh_bid if bl else r.sh_ask if al else 0.0
            day = DATES[r.m // 1440]
            inc_md[(c, day)] = inc_md.get((c, day), 0.0) + r.R / 1440 * sh
            if tt[0] >= 0:
                p = r.bb / 1000; y += r.msz
                pnl_md[(c, day)] = pnl_md.get((c, day), 0.0) + (fin - p) * r.msz; fills.append((c, r.m, 0, p, r.msz, fin))
            if tt[1] >= 0:
                p = (1000 - r.ba) / 1000; n_ += r.msz
                pnl_md[(c, day)] = pnl_md.get((c, day), 0.0) + ((1 - fin) - p) * r.msz; fills.append((c, r.m, 1, p, r.msz, fin))
    keys = sorted(set(inc_md) | set(pnl_md))
    md = pd.DataFrame([(c, dd, inc_md.get((c, dd), 0.0), pnl_md.get((c, dd), 0.0)) for c, dd in keys], columns=["cond", "date", "raw", "pnl"])
    md["reward"] = np.where(md.raw >= 1, md.raw, 0.0); md["net"] = md.reward + md.pnl
    md["event"] = md.cond.map(lambda c: meta[c]["event"])
    return md, pd.DataFrame(fills, columns=["cond", "m", "side", "price", "size", "fin"])


def clus(md, col="net"):
    e = md.groupby("event").agg(s=(col, "sum"), n=(col, "size"))
    N = e.n.sum(); mean = e.s.sum() / N; k = len(e)
    se = np.sqrt(k / (k - 1) * ((e.s - mean * e.n) ** 2).sum()) / N
    return float(mean), float(se), float(mean / se)


res = {}
for model in ("P", "Q1", "Q2", "O"):
    md, F = run(model)
    m, se, t = clus(md)
    ps = (np.where(F.side == 0, F.fin, 1 - F.fin) - F.price) * F["size"]
    # drop the 10 best markets (by net over the period)
    best = md.groupby("cond").net.sum().nlargest(10).index
    m10, _, t10 = clus(md[~md.cond.isin(best)])
    res[model] = dict(market_days=len(md), markets=int(md.cond.nunique()), events=int(md.event.nunique()), reward_md=float(md.reward.mean()),
                      pnl_md=float(md.pnl.mean()), net_md=m, ci95=[m - 1.96 * se, m + 1.96 * se], t=t, fills=len(F),
                      settle_c_share=float(100 * ps.sum() / F["size"].sum()) if len(F) else None,
                      net_md_without_10_best_markets=m10, t_without_10_best=t10)
    print(model, json.dumps(res[model]), flush=True)
json.dump(res, open(f"{HERE}/out/a6_{'_'.join(sys.argv[1:])}.json", "w"), indent=1)

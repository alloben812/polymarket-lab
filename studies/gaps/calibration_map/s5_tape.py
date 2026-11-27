"""Step 5: tape stage for confirmed cells (protocol: Decision rule, tape stage)."""
import json
import pickle
import random
from concurrent.futures import ThreadPoolExecutor

from pmlab import dataapi
from pmlab.stats import ratio_cluster
from common import BNAMES, DATA, HORIZONS, OUT, SEED, read_jsonl

LAG = 3
HSEC = dict(HORIZONS)


def tape_rows(cid, t_min):
    out = []
    for i, r in enumerate(dataapi.iter_trades(condition=cid, max_rows=40000)):
        if int(r["timestamp"]) < t_min:
            break
        out.append(r)
    return out


def fill(m, o, side, obs, rows):
    H = HSEC[obs["h"]]
    W = min(1800, H / 6)
    names = m["outcomes"]
    me = names[obs["fav"]] if side == "fav" else names[1 - obs["fav"]]
    other = names[1 - names.index(me)]
    e = obs["ef"] if side == "fav" else obs["el"]
    pr = []
    for r in rows:
        mt = int(r["timestamp"]) - LAG
        if not (o <= mt <= o + W):
            continue
        p, z = float(r["price"]), float(r["size"])
        if r["side"] == "BUY" and r["outcome"] == me:
            x = p
        elif r["side"] == "SELL" and r["outcome"] == other:
            x = 1 - p
        else:
            continue
        if x <= e + 1e-9:
            pr.append((mt, x, z))
    pr.sort()
    usd = sh = 0.0
    for mt, x, z in pr:
        take = min(z, (20 - usd) / x)
        usd += take * x
        sh += take
        if usd >= 20 - 1e-9:
            break
    return usd, sh


def main():
    dec = json.load(open(OUT / "decision.json"))
    conf = dec["confirmed"]
    if not conf:
        print("no confirmed cell: no tape stage")
        json.dump({"tape_stage": "not run (no confirmed cell)"}, open(OUT / "tape.json", "w"))
        return
    sample = {m["cid"]: m for m in read_jsonl(DATA / "sample.jsonl.gz")}
    obs = pickle.load(open(DATA / "obs.pkl", "rb"))
    rng = random.Random(SEED)
    res = []
    for c in conf:
        b = BNAMES.index(c["bucket"])
        rows = [r for r in obs if r["fam"] == c["fam"] and r["h"] == c["h"] and r["b"] == b and r["late"]]
        rows.sort(key=lambda r: r["cid"])
        rng.shuffle(rows)
        rows = rows[:150]

        def work(ob):
            m = sample[ob["cid"]]
            try:
                tr = tape_rows(ob["cid"], int(ob["o"]) - 600)
            except Exception as e:  # noqa
                return ob, None, str(e)
            return ob, fill(m, ob["o"], c["side"], ob, tr), None

        with ThreadPoolExecutor(3) as ex:
            got = list(ex.map(work, rows))
        filled = []
        for ob, f, err in got:
            if f is None:
                continue
            usd, sh = f
            if usd >= 5:
                vwap = usd / sh
                rate = sample[ob["cid"]]["rate"]
                wv = ob["wf"] if c["side"] == "fav" else 1 - ob["wf"]
                net = wv - vwap - rate * vwap * (1 - vwap)
                filled.append((ob["ev"], net, usd, vwap))
        by = {}
        for ev, net, usd, vw in filled:
            a = by.setdefault(ev, [0.0, 0])
            a[0] += net
            a[1] += 1
        m_, se, t = ratio_cluster([v[0] for v in by.values()], [v[1] for v in by.values()]) if by else (None, None, None)
        r = {"cell": [c["fam"], c["h"], c["bucket"], c["side"]], "tried": len(rows), "errors": sum(1 for g in got if g[1] is None),
             "filled": len(filled), "fill_rate": len(filled) / max(1, len(rows)), "net_per_share": m_, "t": t,
             "mean_usd": sum(f[2] for f in filled) / max(1, len(filled)), "mean_vwap": sum(f[3] for f in filled) / max(1, len(filled))}
        r["tape_confirmed"] = bool(r["fill_rate"] >= 0.5 and m_ is not None and m_ > 0 and (t or 0) >= 2.0)
        print(r, flush=True)
        res.append(r)
    json.dump(res, open(OUT / "tape.json", "w"), indent=1)


if __name__ == "__main__":
    main()

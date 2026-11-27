"""Step 4: observations at fixed horizons, cell table, decision rule (protocol: Observation .. Decision rule)."""
import collections
import csv
import json
import math
from datetime import datetime, timezone

from pmlab.stats import ratio_cluster, wilson
from common import BNAMES, DATA, HORIZONS, OUT, T_SPLIT, bucket_of, read_jsonl, slip, ts


def fee(e, r):
    return r * e * (1 - e)


def build():
    sample = {m["cid"]: m for m in read_jsonl(DATA / "sample.jsonl.gz")}
    ph = {}
    for line in open(DATA / "ph.jsonl"):
        r = json.loads(line)
        ph[r["cid"]] = r
    obs = []
    cnt = collections.Counter()
    fetched = collections.Counter()
    for cid, r in ph.items():
        m = sample.get(cid)
        if m is None:
            continue
        if "err" in r:
            cnt["fetch_err"] += 1
            continue
        fetched[m["fam"]] += 1
        pts = sorted(r["pts"])
        if not pts:
            cnt["no_points"] += 1
            continue
        b = r["b"]
        closed = ts(m.get("closedTime")) or 9e12
        start = ts(m.get("startDate")) or 0
        for hn, H in HORIZONS:
            if H == 600 and b != 300:
                continue
            o = m["anchor"] - H
            if not (start <= o < closed):
                cnt[f"not_trading_{hn}"] += 1
                continue
            last = None
            for t, p in pts:
                if t <= o - b:
                    last = (t, p)
                else:
                    break
            if last is None or last[0] < o - 3 * b:
                cnt[f"stale_{hn}"] += 1
                continue
            p0 = last[1]
            fav = 0 if p0 >= 0.5 else 1
            pf = p0 if fav == 0 else 1 - p0
            if pf > 0.995:
                cnt[f"gt995_{hn}"] += 1
                continue
            bi = bucket_of(pf)
            if bi is None:
                continue
            wf, wl = m["win"][fav], m["win"][1 - fav]
            ef = pf + slip(pf)
            pl = 1 - pf
            el = pl + slip(pl)
            rate = m["rate"]
            day = int(m["anchor"] // 86400)
            obs.append({"cid": cid, "fam": m["fam"], "h": hn, "b": bi, "ev": m.get("event") or cid, "day": day,
                        "late": m["anchor"] >= T_SPLIT, "pf": pf, "wf": wf, "gross": wf - pf,
                        "nf": wf - ef - fee(ef, rate), "nl": wl - el - fee(el, rate), "ef": ef, "el": el,
                        "wkend": datetime.fromtimestamp(m["anchor"], timezone.utc).weekday() >= 5, "o": o,
                        "tok_fav": m["tokens"][fav], "tok_other": m["tokens"][1 - fav], "fav": fav})
    return obs, cnt, fetched


def cell_stats(rows, key):
    by = collections.defaultdict(lambda: [0.0, 0])
    for r in rows:
        a = by[r[key]]
        a[0] += r["_v"]
        a[1] += 1
    num = [v[0] for v in by.values()]
    den = [v[1] for v in by.values()]
    return ratio_cluster(num, den), len(by)


def summarize(rows, side):
    if not rows:
        return None
    for r in rows:
        r["_v"] = r["nf"] if side == "fav" else r["nl"]
    (m, se, t), nev = cell_stats(rows, "ev")
    (_, _, tday), nday = cell_stats(rows, "day")
    return {"n": len(rows), "events": nev, "days": nday, "net": m, "se": se, "t": t, "t_day": tday}


def main():
    obs, cnt, fetched = build()
    json.dump({"drops": cnt, "fetched_ok_by_family": fetched, "observations": len(obs)}, open(OUT / "obs_counts.json", "w"), indent=1)
    cells = collections.defaultdict(list)
    for r in obs:
        cells[(r["fam"], r["h"], r["b"])].append(r)
    out = []
    for (fam, h, b), rows in sorted(cells.items()):
        early = [r for r in rows if not r["late"]]
        late = [r for r in rows if r["late"]]
        n = len(rows)
        k = sum(r["wf"] for r in rows)
        base = {"fam": fam, "h": h, "bucket": BNAMES[b], "n_all": n, "mean_p": sum(r["pf"] for r in rows) / n,
                "win_fav": k / n, "gross_fav_c": 100 * sum(r["gross"] for r in rows) / n}
        for side in ("fav", "long"):
            row = dict(base, side=side)
            for nm, part in (("E", early), ("L", late)):
                s = summarize(part, side)
                for kk in ("n", "events", "net", "t", "t_day"):
                    row[f"{nm}_{kk}"] = None if s is None else s[kk]
            out.append(row)
    keys = list(out[0].keys())
    with open(OUT / "cells.csv", "w", newline="") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        for r in out:
            w.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()})
    # decision rule
    cand = [r for r in out if (r["E_events"] or 0) >= 100 and (r["E_net"] or -1) > 0 and (r["E_t"] or 0) >= 2.0]
    conf = [r for r in cand if (r["L_events"] or 0) >= 200 and (r["L_net"] or -1) > 0 and (r["L_t"] or 0) >= 3.0
            and (r["L_t_day"] or 0) >= 2.0]
    conf.sort(key=lambda r: -r["L_t"])
    res = {"n_cells_computed": len(out), "n_family_horizon_bucket": len(cells), "candidates": cand,
           "confirmed": conf[:5], "n_confirmed": len(conf)}
    json.dump(res, open(OUT / "decision.json", "w"), indent=1, default=str)
    print("cells", len(out), "candidates", len(cand), "confirmed", len(conf))
    for r in cand:
        print("CAND", r["fam"], r["h"], r["bucket"], r["side"], "E", r["E_events"], round(100 * r["E_net"], 2), round(r["E_t"], 2),
              "L", r["L_events"], None if r["L_net"] is None else round(100 * r["L_net"], 2), None if r["L_t"] is None else round(r["L_t"], 2), r["L_t_day"])
    # save observations (small) for the tape stage
    import pickle
    pickle.dump(obs, open(DATA / "obs.pkl", "wb"))


if __name__ == "__main__":
    main()

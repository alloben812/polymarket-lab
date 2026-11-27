"""Step 3: per-market panel (observations, claim entry, loser scan) from sample + resolutions + price histories.

Usage: python3 s3_build.py [max_markets]   (max_markets: sanity slice in file order of hist.jsonl.gz)
"""
import bisect
import gzip
import json
import pickle
import sys

from pmlab.fees import fee_per_share
from common import DATA, EPS, T_SPLIT, bucket_of, read_jsonl, ts

OFFS = {"T-24h": -86400, "T-6h": -21600, "T-1h": -3600, "T-10m": -600, "T": 0, "T+10m": 600, "T+1h": 3600}
STALE = 900


def fee_rate(m):
    if m.get("feesEnabled") is False:
        return 0.0, "disabled"
    r = (m.get("feeSchedule") or {}).get("rate")
    if r is None:
        return 0.05, "missing->0.05"
    return float(r), "schedule"


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    sample = {m["conditionId"]: m for m in read_jsonl(DATA / "sample.jsonl.gz")}
    res = json.loads((DATA / "resolutions.json").read_text())
    panel, drops = [], {}
    n = 0
    with gzip.open(DATA / "hist.jsonl.gz", "rt") as f:
        for line in f:
            h = json.loads(line)
            n += 1
            if limit and n > limit:
                break
            m = sample.get(h["cid"])
            if m is None:
                continue
            end, closed = ts(m["endDate"]), ts(m["closedTime"])
            gs = ts(m.get("gameStartTime"))
            fam = m["family"]
            sub = None
            if fam == "sports":
                sub = "sports/start" if (gs is not None and abs(gs - end) <= 60) else "sports/other"
            rate, rate_src = fee_rate(m)
            row = {"cid": h["cid"], "slug": m["slug"], "fam": fam, "sub": sub, "event": m.get("event_slug") or m["slug"],
                   "end": end, "closed": closed, "late": closed >= T_SPLIT, "rate": rate, "rate_src": rate_src,
                   "feeType": m.get("feeType"), "vol": m["volumeNum"], "outcomes": m["outcomes"], "tokens": m["clobTokenIds"],
                   "gap": closed - end, "negRisk": m.get("negRisk"), "smt": m.get("sportsMarketType"), "drop": None,
                   "obs": {}, "claim": None, "loser": None, "imputed": 0}
            r = res.get(h["cid"])
            pay = None
            if r and r.get("resolved"):
                pay = [r["final"].get(o) for o in m["outcomes"]]
                if any(p is None for p in pay):
                    pay = None
            if pay is None:
                row["drop"] = "unresolved_or_no_final"
            elif h.get("err"):
                row["drop"] = "download_error"
            elif h.get("skip"):
                row["drop"] = h["skip"]
            row["pay"] = pay
            if row["drop"]:
                drops[row["drop"]] = drops.get(row["drop"], 0) + 1
                panel.append(row)
                continue
            # usable buckets
            T, P = [], []
            n_settle = 0
            for k in (0, 1):
                tt, pp = [], []
                for t, p, rs in h["h"][k]:
                    if rs != 300:
                        n_settle += 1
                        continue
                    if t >= closed:
                        continue
                    tt.append(t)
                    pp.append(p)
                T.append(tt)
                P.append(pp)
            row["n_pts"] = (len(T[0]), len(T[1]))
            if not T[0] and not T[1]:
                row["drop"] = "no_usable_prices"
                drops[row["drop"]] = drops.get(row["drop"], 0) + 1
                panel.append(row)
                continue

            def price_at(x, k, stale):
                i = bisect.bisect_right(T[k], x) - 1
                if i >= 0 and T[k][i] > x - stale:
                    return P[k][i]
                return None

            def both_at(x, stale):
                p0, p1 = price_at(x, 0, stale), price_at(x, 1, stale)
                imp = False
                if p0 is None and p1 is None:
                    return None
                if p0 is None:
                    p0, imp = 1 - p1, True
                elif p1 is None:
                    p1, imp = 1 - p0, True
                return p0, p1, imp

            for name, off in OFFS.items():
                x = end + off
                if not x < closed:
                    continue
                b = both_at(x, STALE)
                if b is None:
                    continue
                p0, p1, imp = b
                if abs(p0 - p1) < EPS:
                    continue
                k = 0 if p0 > p1 else 1
                pf = (p0, p1)[k]
                row["obs"][name] = {"k": k, "p": pf, "other": (p0, p1)[1 - k], "pay": pay[k], "lock_h": (closed - x) / 3600, "imp": imp}
                row["imputed"] += imp
            # claim entry (rule 16)
            times = sorted(set(t for t in T[0] + T[1] if t >= end - 3600))
            for t in times:
                b = both_at(t, 1)  # stale=1 -> only a bucket at exactly t
                if b is None:
                    continue
                p0, p1, imp = b
                if abs(p0 - p1) < EPS:
                    continue
                k = 0 if p0 > p1 else 1
                pf = (p0, p1)[k]
                if 0.95 - EPS <= pf < 0.98 - EPS:
                    c = {"t": t, "k": k, "p": pf, "pay": pay[k], "lock_h": (closed - t) / 3600, "rel_end_h": (t - end) / 3600}
                    b2 = both_at(t + 300, 1) if t + 300 < closed else None
                    c["p_next"] = None if b2 is None else (b2[0], b2[1])[k]
                    row["claim"] = c
                    break
            # loser scan (rule 22)
            worst = None
            for k in (0, 1):
                if pay[k] >= 1:
                    continue
                # own buckets and the mirror of the other token
                cand = [(p, t) for t, p in zip(T[k], P[k]) if t >= end - 86400] + [(1 - p, t) for t, p in zip(T[1 - k], P[1 - k]) if t >= end - 86400]
                cand = [c for c in cand if c[0] >= 0.95 - EPS]
                if cand:
                    pmax, tmax = max(cand)
                    tfirst = min(t for _, t in cand)
                    tlast = max(t for _, t in cand)
                    w = {"k": k, "outcome": m["outcomes"][k], "pmax": pmax, "t_max": tmax, "t_first": tfirst, "t_last": tlast,
                         "n_buckets": len(set(t for _, t in cand)), "pay": pay[k]}
                    if worst is None or pmax > worst["pmax"]:
                        worst = w
            row["loser"] = worst
            row["n_settle_pts"] = n_settle
            panel.append(row)
    out = DATA / ("panel_slice.pkl" if limit else "panel.pkl")
    with open(out, "wb") as f:
        pickle.dump(panel, f)
    print("panel", len(panel), "drops", drops, "->", out)


if __name__ == "__main__":
    main()

"""Step 1 (protocol 3-4): one candidate trade per eligible moneyline + the seven public-fact features.

Output: data/gaps_tennis_wo_pred/trades.json (one row per moneyline in the universe, eligible or not)."""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import gzip
import json
import os
import unicodedata
from pathlib import Path

DATA = Path("/home/user/polymarket-lab/data/gaps_tennis_wo")
OUTD = Path("/home/user/polymarket-lab/data/gaps_tennis_wo_pred")
OUTD.mkdir(parents=True, exist_ok=True)
TAPE = Path("/home/user/polymarket-lab/data/tape")
LAG = 3
FEE = 0.05
H = 3600.0


def ts(s):
    if not s:
        return None
    s = str(s).strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if s.endswith("+00"):
        s += ":00"
    if "." in s:
        head, rest = s.split(".", 1)
        i = 0
        while i < len(rest) and rest[i].isdigit():
            i += 1
        s = head + "." + rest[:i][:6].ljust(6, "0") + rest[i:]
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()


def jf(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().replace("-", " ").split())


def fprices(m):
    p = jf(m.get("outcomePrices"))
    try:
        return tuple(float(x) for x in p) if p and len(p) == 2 else None
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ event index
def build_index():
    evs = []
    with gzip.open(DATA / "events.jsonl.gz", "rt") as f:
        for line in f:
            ev = json.loads(line)
            ms = ev.get("markets") or []
            ml = [m for m in ms if m.get("sportsMarketType") == "moneyline"]
            if not ml:
                continue
            ml = ml[0]
            outs = jf(ml.get("outcomes")) or []
            if len(outs) != 2:
                continue
            series = ev.get("seriesSlug") or ""
            dbl = series.endswith("-doubles") or any("/" in o for o in outs)
            start = ts(ml.get("gameStartTime")) or ts(ev.get("startTime"))
            fin = fprices(ml)
            cm = [m for m in ms if m.get("sportsMarketType") == "tennis_completed_match"]
            ret = False
            if cm and fin and set(fin) == {0.0, 1.0}:
                o = jf(cm[0].get("outcomes")) or []
                cp = fprices(cm[0])
                if cp and "No" in o and cp[o.index("No")] == 1.0:
                    ret = True
            keys = [norm(o) for o in outs]
            if dbl:
                sur = [norm(x).split()[-1] for o in outs for x in o.split("/") if norm(x)]
            else:
                sur = [k.split()[-1] for k in keys if k]
            evs.append({"slug": ev["slug"], "series": series, "dbl": dbl, "start": start, "closed": ts(ml.get("closedTime")),
                        "created": ts(ev.get("createdAt")) or ts(ml.get("createdAt")), "keys": keys, "sur": sur,
                        "fin": fin, "wo": fin == (0.5, 0.5), "ret": ret})
    return evs


def main():
    evs = build_index()
    by_slug = {e["slug"]: e for e in evs}
    by_key = collections.defaultdict(list)     # exact player/pair key -> events
    sing_sur = collections.defaultdict(list)   # surname -> singles events
    dbl_sur = collections.defaultdict(list)    # surname -> doubles events
    for e in evs:
        for k in e["keys"]:
            by_key[k].append(e)
        for s in e["sur"]:
            (dbl_sur if e["dbl"] else sing_sur)[s].append(e)
    print("match events indexed", len(evs), "retirement-flag events", sum(e["ret"] for e in evs))

    u = json.load(open(DATA / "universe.json"))
    rows = []
    for cls, recs in (("A", u["A"]), ("C", u["control"])):
        for r in recs:
            if cls == "A":
                m = next(x for x in r["markets"] if x["cid"] == r["ml"])
                cid, outs, fin, closed, start, vol = m["cid"], m["outcomes"], m.get("api_final") or m["final"], m["closed"], m["start"] or r["startTime"], m.get("vol")
                w = 1
            else:
                cid, outs, fin, closed, start, vol = r["cid"], r["outcomes"], r.get("api_final") or r["final"], r["closed"], r["start"], r.get("vol")
                w = 8
            row = {"cls": cls, "w": w, "slug": r["slug"], "cid": cid, "series": r["series"], "start": start, "closed": closed,
                   "vol": vol, "fin": list(fin), "elig": False}
            rows.append(row)
            path = TAPE / f"{cid}.jsonl.gz"
            row["tape"] = path.exists()
            if not path.exists() or start is None:
                continue
            with gzip.open(path, "rt") as f:
                tape = [json.loads(x) for x in f]
            pr = []
            for t in tape:
                if t["o"] not in outs:
                    continue
                oi = outs.index(t["o"])
                p = float(t["p"])
                if t["s"] == "BUY":
                    pr.append((t["t"] - LAG, oi, p, float(t["z"]), 1 - oi, 1.0 - p))  # buyable oi at p; sellable other at 1-p
                else:
                    pr.append((t["t"] - LAG, 1 - oi, 1.0 - p, float(t["z"]), oi, p))  # buyable other at 1-p; sellable oi at p
            pr.sort(key=lambda x: x[0])
            lo, hi = start - 6 * H, start - 1 * H
            tr = None
            avail = 0.0
            for x in pr:
                if lo <= x[0] <= hi and 0.05 - 1e-9 <= x[2] <= 0.45 + 1e-9:
                    if tr is None:
                        tr = x
                    if x[1] == tr[1]:
                        avail += x[2] * x[3]
            row["n_prints_before_T"] = sum(1 for x in pr if x[0] < start)
            if tr is None:
                continue
            t0, X, p, z = tr[0], tr[1], tr[2], tr[3]
            row.update({"elig": True, "t": t0, "X": X, "p": p, "z": z, "avail_usd": avail, "pay": fin[X],
                        "lead_h": (start - t0) / H})
            # maker scenario: bid at p - 0.01 for X from t0 until T; sellable prints of X
            bid = round(p - 0.01, 4)
            mk_thr = mk_at = None
            for x in pr:
                if x[0] <= t0 or x[0] >= start:
                    continue
                if x[4] == X:
                    if mk_at is None and x[5] <= bid + 1e-9:
                        mk_at = (x[5], x[3])
                    if mk_thr is None and x[5] < bid - 1e-9:
                        mk_thr = (x[5], x[3])
                        break
            row["bid"] = bid
            row["mk_thr_z"] = mk_thr[1] if mk_thr else 0.0
            row["mk_at_z"] = mk_at[1] if mk_at else 0.0
            # ------------------------------------------------ features (information before t0)
            me = by_slug.get(r["slug"])
            keys = me["keys"] if me else [norm(o) for o in outs]
            dbl = me["dbl"] if me else str(r["series"]).endswith("-doubles")
            sur = me["sur"] if me else []
            F = {"itf": r["series"] == "itf", "doubles": dbl}
            short = longp = ret = wo = False
            for k in keys:
                for e in by_key.get(k, []):
                    if e is me or e["slug"] == r["slug"] or e["start"] is None or e["closed"] is None:
                        continue
                    if e["closed"] >= t0 or e["start"] >= start:
                        continue
                    if e["closed"] >= start - 16 * H:
                        short = True
                    if e["start"] >= start - 72 * H and e["closed"] - e["start"] >= 150 * 60:
                        longp = True
                    if e["ret"] and e["start"] >= start - 14 * 24 * H:
                        ret = True
                    if e["wo"]:
                        wo = True
            dd = False
            cands = []
            if not dbl:
                for k in keys:
                    cands += [e for e in by_key.get(k, [])]
                for s in sur:
                    cands += dbl_sur.get(s, [])
            else:
                for s in sur:
                    cands += sing_sur.get(s, []) + dbl_sur.get(s, [])
            for e in cands:
                if e["slug"] == r["slug"] or e["start"] is None:
                    continue
                if e["created"] is not None and e["created"] >= t0:
                    continue
                if abs(e["start"] - start) <= 12 * H:
                    dd = True
                    break
            F.update({"short_rest": short, "long_prev": longp, "recent_ret": ret, "double_duty": dd, "wo_history": wo})
            row["F"] = F
    json.dump(rows, open(OUTD / "trades.json", "w"))
    el = [r for r in rows if r["elig"]]
    print("rows", len(rows), "eligible", len(el), "A eligible", sum(r["cls"] == "A" for r in el))
    print("A with vol>0 but no tape", sum(1 for r in rows if r["cls"] == "A" and not r["tape"] and (r["vol"] or 0) > 0))
    print("A no tape", sum(1 for r in rows if r["cls"] == "A" and not r["tape"]))
    fc = collections.Counter(k for r in el for k, v in r["F"].items() if v)
    print("feature flags (unweighted, eligible)", dict(fc))


if __name__ == "__main__":
    main()

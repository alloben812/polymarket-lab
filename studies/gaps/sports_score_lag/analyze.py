"""Runs protocol.md exactly: stale-pool tables and the 12 follower variants. Writes out/*.csv and out/report.txt."""
from __future__ import annotations

import bisect
import csv
import gzip
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

from pmlab.fees import fee_per_share
from pmlab.stats import ratio_cluster, bootstrap_sum_ci

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "gaps_sports_lag"
OUT = Path(__file__).resolve().parent / "out"
LAG = 3
RATE = 0.05
SPLIT = 1795478400  # 2026-11-24 00:00 UTC
STAKE = 20.0


def load_tape(cid):
    with gzip.open(DATA / "tapes" / f"{cid}.jsonl.gz", "rt") as f:
        return [json.loads(l) for l in f]


def convert(rows, x):
    """-> sorted list of (match_time, price_of_x, buyable_x, shares, wallet, usd)."""
    out = []
    for r in rows:
        if r["o"] == x:
            p, b = r["p"], r["s"] == "BUY"
        else:
            p, b = 1.0 - r["p"], r["s"] == "SELL"
        out.append((r["t"] - LAG, p, b, r["z"], r["w"]))
    out.sort(key=lambda z: z[0])
    return out


def window(conv, times, a, b):
    i, j = bisect.bisect_left(times, a), bisect.bisect_right(times, b)
    return conv[i:j]


def favoured(g, key, ev):
    if g["sport"] == "nfl":
        return g["home_out"] if ev["team_id"] == g["home_id"] else g["away_out"]
    home_scored = ev["team_id"] == g["home_id"]
    if key == "home":
        return "Yes" if home_scored else "No"
    if key == "away":
        return "No" if home_scored else "Yes"
    bh, ba = ev["before"]
    ah, aa = ev["after"]
    return "Yes" if abs(ah - aa) < abs(bh - ba) else "No"


def main():
    OUT.mkdir(exist_ok=True)
    games = json.loads((DATA / "games.json").read_text())
    rep = []
    P = rep.append
    pool_rows, trade_rows, ev_rows = [], [], []
    n_ev_total = n_ev_kept = 0
    for g in games:
        if any(m.get("n_rows") is None for m in g["markets"].values()):
            continue
        period = "early" if g["t0"] < SPLIT else "late"
        tapes = {}
        for k, m in g["markets"].items():
            tapes[k] = load_tape(m["cid"])
        evs = g["events"]
        for i, ev in enumerate(evs):
            n_ev_total += 1
            if i > 0 and ev["t"] - evs[i - 1]["t"] < 180:
                continue
            n_ev_kept += 1
            te = ev["t"]
            for k, m in g["markets"].items():
                x = favoured(g, k, ev)
                fin = (m.get("final") or {}).get(x)
                conv = convert(tapes[k], x)
                times = [c[0] for c in conv]
                pre = window(conv, times, te - 120, te - 10)
                if not pre:
                    ev_rows.append({"game": g["event"], "sport": g["sport"], "period": period, "te": te, "mkt": k, "status": "no_pre"})
                    continue
                p_pre = st.median(c[1] for c in pre)
                if not (0.05 <= p_pre <= 0.95):
                    ev_rows.append({"game": g["event"], "sport": g["sport"], "period": period, "te": te, "mkt": k, "status": "pre_out", "p_pre": p_pre})
                    continue
                post = window(conv, times, te + 120, te + 300)
                p_post = st.median(c[1] for c in post) if post else None
                J = (p_post - p_pre) if p_post is not None else None
                row = {"game": g["event"], "sport": g["sport"], "period": period, "te": te, "mkt": k, "status": "ok",
                       "p_pre": round(p_pre, 4), "p_post": None if p_post is None else round(p_post, 4),
                       "J": None if J is None else round(J, 4), "final": fin, "text": ev.get("text")}
                # descriptive stale pool
                if J is not None and J >= 0.05:
                    half = p_pre + J / 2
                    rep_t = next((c[0] for c in window(conv, times, te - 60, te + 300) if c[1] >= half), None)
                    row["reprice_dt"] = None if rep_t is None else rep_t - te
                    first_move = next((c[0] for c in window(conv, times, te - 60, te + 300) if c[1] >= p_pre + 0.03), None)
                    row["move3_dt"] = None if first_move is None else first_move - te
                    for c in window(conv, times, te - 30, te + 300):
                        if c[2] and c[1] <= half:
                            pool_rows.append({"game": g["event"], "sport": g["sport"], "period": period, "te": te, "mkt": k,
                                              "dt": c[0] - te, "price": round(c[1], 4), "shares": c[3], "usd": c[3] * c[1],
                                              "locked": (p_post - c[1] - fee_per_share(c[1], RATE)) * c[3],
                                              "won": None if fin is None else (fin - c[1] - fee_per_share(c[1], RATE)) * c[3],
                                              "wallet": c[4]})
                ev_rows.append(row)
                # strategies
                trig_t = next((c[0] for c in window(conv, times, te - 30, te + 300) if c[1] >= p_pre + 0.03), None)
                for trig, t0 in (("E", te), ("T", trig_t)):
                    for d in (3, 10, 60):
                        if t0 is None:
                            continue
                        ta = t0 + d + int(m.get("delay") or 0)
                        fill = next((c for c in window(conv, times, ta, ta + 30) if c[2]), None)
                        if fill is None:
                            continue
                        p = fill[1]
                        sh = min(fill[3], STAKE / p)
                        fee = fee_per_share(p, RATE)
                        mk = window(conv, times, ta + 240, ta + 360)
                        ref = st.median(c[1] for c in mk) if mk else None
                        trade_rows.append({"sport": g["sport"], "period": period, "game": g["event"], "te": te, "mkt": k,
                                           "var": f"{g['sport']}-{trig}{d}", "trig": trig, "d": d, "t_fill_dt": fill[0] - te,
                                           "price": round(p, 4), "p_pre": round(p_pre, 4), "shares": sh, "fee": fee,
                                           "hold": None if fin is None else (fin - p - fee),
                                           "mark": None if ref is None else (ref - p - fee)})
    P(f"games {len(games)}; scoring events {n_ev_total}, kept after 180 s rule {n_ev_kept}")
    # ---------- event-market table
    ok = [r for r in ev_rows if r["status"] == "ok"]
    P(f"event-markets: {len(ev_rows)} total, ok {len(ok)}, no_pre {sum(r['status']=='no_pre' for r in ev_rows)}, "
      f"pre_out {sum(r['status']=='pre_out' for r in ev_rows)}")
    for sp in ("soccer", "nfl"):
        rows = [r for r in ok if r["sport"] == sp and r["J"] is not None]
        big = [r for r in rows if r["J"] >= 0.05]
        P(f"\n[{sp}] event-markets with P_post: {len(rows)}; J>=0.05: {len(big)}; median J (all) {st.median([r['J'] for r in rows]) if rows else None}")
        rp = sorted(r["reprice_dt"] for r in big if r.get("reprice_dt") is not None)
        m3 = sorted(r["move3_dt"] for r in big if r.get("move3_dt") is not None)
        if rp:
            q = lambda a, f: a[min(len(a) - 1, int(f * len(a)))]
            P(f"  reprice (first print >= halfway) dt vs ESPN wallclock: n {len(rp)} p10 {q(rp,.1)} p25 {q(rp,.25)} median {q(rp,.5)} p75 {q(rp,.75)} p90 {q(rp,.9)}; "
              f"before wallclock {sum(1 for v in rp if v < 0)}; none within 300 s {sum(1 for r in big if r.get('reprice_dt') is None)}")
            P(f"  first +3c print dt: n {len(m3)} p10 {q(m3,.1)} p25 {q(m3,.25)} median {q(m3,.5)} p75 {q(m3,.75)} p90 {q(m3,.9)}")
        for per in ("early", "late", "all"):
            pr = [r for r in pool_rows if r["sport"] == sp and (per == "all" or r["period"] == per)]
            nev = len({(r["game"], r["te"]) for r in big if per == "all" or r["period"] == per})
            ngames = len({r["game"] for r in big if per == "all" or r["period"] == per})
            if not pr:
                P(f"  pool {per}: no stale prints (events {nev})")
                continue
            usd = sum(r["usd"] for r in pr)
            locked = sum(r["locked"] for r in pr)
            after = [r for r in pr if r["dt"] >= 0]
            buckets = defaultdict(float)
            for r in pr:
                b = "<0" if r["dt"] < 0 else "0-2" if r["dt"] <= 2 else "3-5" if r["dt"] <= 5 else "6-10" if r["dt"] <= 10 else "11-30" if r["dt"] <= 30 else "31-60" if r["dt"] <= 60 else ">60"
                buckets[b] += r["usd"]
            by_game = defaultdict(float)
            for r in pr:
                by_game[r["game"]] += r["locked"]
            ci = bootstrap_sum_ci(list(by_game.values()) + [0.0] * (ngames - len(by_game)))
            P(f"  pool {per}: games {ngames}, events {nev}, stale prints {len(pr)}, ${usd:,.0f} bought at stale prices, "
              f"profit locked vs P_post ${locked:,.0f} (95% CI by game {ci[0]:,.0f}..{ci[1]:,.0f}), wallets {len({r['wallet'] for r in pr})}; "
              f"after wallclock ${sum(r['usd'] for r in after):,.0f}, locked ${sum(r['locked'] for r in after):,.0f}")
            P("    $ by seconds after wallclock: " + ", ".join(f"{b} ${buckets[b]:,.0f}" for b in ("<0", "0-2", "3-5", "6-10", "11-30", "31-60", ">60")))
    # ---------- variants
    P("\n# Variants (hold = hold to resolution, mark = 5-minute markout; c/share after fee; t by game)")
    vrows = []
    for sp in ("soccer", "nfl"):
        for trig in ("E", "T"):
            for d in (3, 10, 60):
                v = f"{sp}-{trig}{d}"
                for per in ("early", "late", "all"):
                    tr = [r for r in trade_rows if r["var"] == v and (per == "all" or r["period"] == per)]
                    out = {"variant": v, "period": per, "trades": len(tr), "games": len({r["game"] for r in tr})}
                    for meas in ("hold", "mark"):
                        tt = [r for r in tr if r[meas] is not None]
                        num, den = defaultdict(float), defaultdict(float)
                        for r in tt:
                            num[r["game"]] += r[meas] * r["shares"]
                            den[r["game"]] += r["shares"]
                        ks = list(num)
                        rr, se, t = ratio_cluster([num[k] for k in ks], [den[k] for k in ks])
                        usd = sum(r["shares"] * r["price"] for r in tt)
                        out[f"{meas}_c"] = round(100 * rr, 2) if rr == rr else None
                        out[f"{meas}_se"] = round(100 * se, 2) if se == se else None
                        out[f"{meas}_t"] = round(t, 2) if t == t else None
                        out[f"{meas}_usd_per_trade"] = round(sum(num.values()) / len(tt), 3) if tt else None
                        out[f"{meas}_n"] = len(tt)
                    out["avg_price"] = round(sum(r["price"] for r in tr) / len(tr), 3) if tr else None
                    out["avg_fee_c"] = round(100 * sum(r["fee"] for r in tr) / len(tr), 2) if tr else None
                    out["avg_stake"] = round(sum(r["shares"] * r["price"] for r in tr) / len(tr), 2) if tr else None
                    out["med_fill_dt"] = st.median([r["t_fill_dt"] for r in tr]) if tr else None
                    vrows.append(out)
                    P(f"{v:12s} {per:5s} trades {out['trades']:4d} games {out['games']:3d} avg p {out['avg_price']} fee {out['avg_fee_c']}c stake ${out['avg_stake']} "
                      f"fill dt med {out['med_fill_dt']} | hold {out['hold_c']}c se {out['hold_se']} t {out['hold_t']} (${out['hold_usd_per_trade']}/trade) | "
                      f"mark {out['mark_c']}c se {out['mark_se']} t {out['mark_t']} n {out['mark_n']}")
    with open(OUT / "variants.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(vrows[0]))
        w.writeheader()
        w.writerows(vrows)
    with open(OUT / "event_markets.csv", "w", newline="") as f:
        keys = sorted({k for r in ev_rows for k in r})
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(ev_rows)
    (DATA / "pool_rows.json").write_text(json.dumps(pool_rows))
    (DATA / "trade_rows.json").write_text(json.dumps(trade_rows))
    (OUT / "report.txt").write_text("\n".join(rep) + "\n")
    print("\n".join(rep))


if __name__ == "__main__":
    main()

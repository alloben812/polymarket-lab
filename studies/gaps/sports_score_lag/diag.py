"""POST-HOC diagnostics (written after seeing out/report.txt; they do not change the protocol verdict).

(a) concentration of the stale pool by game and wallet; (b) the stale pool measured from the tape's own first move
(first +3c print) instead of the ESPN wallclock; (c) mean price path after the first move; (d) a real round trip for
the soccer trigger-T variants: exit by selling at the first sellable print >= t_a + 300 s, second taker fee paid;
(e) markout reference computed from sell-side prints only."""
from __future__ import annotations

import json
import statistics as st
from collections import defaultdict, Counter
from pathlib import Path

import analyze as A
from pmlab.fees import fee_per_share
from pmlab.stats import ratio_cluster, bootstrap_sum_ci

games = json.loads((A.DATA / "games.json").read_text())
pool = json.loads((A.DATA / "pool_rows.json").read_text())
out = []
P = out.append

# (a)
for sp in ("soccer", "nfl"):
    pr = [r for r in pool if r["sport"] == sp]
    tot = sum(r["usd"] for r in pr)
    byg = Counter()
    byw = Counter()
    for r in pr:
        byg[r["game"]] += r["usd"]
        byw[r["wallet"]] += r["usd"]
    P(f"(a) {sp}: stale $ {tot:,.0f}; top games " + ", ".join(f"{g} ${v:,.0f}" for g, v in byg.most_common(4)))
    P(f"    top wallets " + ", ".join(f"{w[:10]} ${v:,.0f}" for w, v in byw.most_common(5)))
    big = [r for r in pr if r["usd"] > 20000]
    P(f"    prints above $20K: {len(big)}, ${sum(r['usd'] for r in big):,.0f}; " + "; ".join(f"{r['game']} {r['mkt']} dt {r['dt']} p {r['price']} ${r['usd']:,.0f}" for r in big[:8]))

# (b)-(e)
paths = defaultdict(lambda: defaultdict(list))
pool_b = []
rt = []
mark_sell = []
for g in games:
    period = "early" if g["t0"] < A.SPLIT else "late"
    tapes = {k: A.load_tape(m["cid"]) for k, m in g["markets"].items()}
    evs = g["events"]
    for i, ev in enumerate(evs):
        if i > 0 and ev["t"] - evs[i - 1]["t"] < 180:
            continue
        te = ev["t"]
        for k, m in g["markets"].items():
            x = A.favoured(g, k, ev)
            conv = A.convert(tapes[k], x)
            times = [c[0] for c in conv]
            pre = A.window(conv, times, te - 120, te - 10)
            if not pre:
                continue
            p_pre = st.median(c[1] for c in pre)
            if not (0.05 <= p_pre <= 0.95):
                continue
            tm = next((c[0] for c in A.window(conv, times, te - 30, te + 300) if c[1] >= p_pre + 0.03), None)
            if tm is None:
                continue
            post = A.window(conv, times, te + 120, te + 300)
            p_post = st.median(c[1] for c in post) if post else None
            if p_post is not None and p_post - p_pre >= 0.05:
                J = p_post - p_pre
                half = p_pre + J / 2
                for c in A.window(conv, times, tm, te + 300):
                    if c[2] and c[1] <= half:
                        pool_b.append({"sport": g["sport"], "period": period, "game": g["event"], "dt": c[0] - tm, "usd": c[3] * c[1],
                                       "locked": (p_post - c[1] - fee_per_share(c[1], A.RATE)) * c[3], "w": c[4], "key": (g["event"], te, k)})
                for h in (0, 5, 10, 30, 60, 120, 300, 600):
                    w = A.window(conv, times, tm + h - 2, tm + h + 2) or A.window(conv, times, tm + h - 15, tm + h + 15)
                    if w:
                        paths[g["sport"]][h].append((st.median(c[1] for c in w) - p_pre) / J)
            for d in (3, 10, 60):
                ta = tm + d + int(m.get("delay") or 0)
                fill = next((c for c in A.window(conv, times, ta, ta + 30) if c[2]), None)
                if fill is None:
                    continue
                p = fill[1]
                sh = min(fill[3], A.STAKE / p)
                ex = next((c for c in A.window(conv, times, ta + 300, ta + 360) if not c[2]), None)
                if ex is not None:
                    q = ex[1]
                    rt.append({"sport": g["sport"], "period": period, "game": g["event"], "d": d, "sh": sh,
                               "pnl": q - p - fee_per_share(p, A.RATE) - fee_per_share(q, A.RATE)})
                sw = [c[1] for c in A.window(conv, times, ta + 240, ta + 360) if not c[2]]
                if sw:
                    mark_sell.append({"sport": g["sport"], "period": period, "game": g["event"], "d": d, "sh": sh,
                                      "pnl": st.median(sw) - p - fee_per_share(p, A.RATE)})

for sp in ("soccer", "nfl"):
    for per in ("early", "late", "all"):
        pr = [r for r in pool_b if r["sport"] == sp and (per == "all" or r["period"] == per)]
        if not pr:
            continue
        b = defaultdict(float)
        lk = defaultdict(float)
        for r in pr:
            lab = "0-1" if r["dt"] <= 1 else "2-3" if r["dt"] <= 3 else "4-6" if r["dt"] <= 6 else "7-10" if r["dt"] <= 10 else "11-30" if r["dt"] <= 30 else "31-60" if r["dt"] <= 60 else ">60"
            b[lab] += r["usd"]
            lk[lab] += r["locked"]
        byg = defaultdict(float)
        for r in pr:
            byg[r["game"]] += r["locked"]
        ci = bootstrap_sum_ci(list(byg.values()))
        P(f"(b) {sp} {per}: pool from first +3c print: {len({r['key'] for r in pr})} event-markets in {len(byg)} games, "
          f"${sum(r['usd'] for r in pr):,.0f} bought, locked ${sum(r['locked'] for r in pr):,.0f} (CI by game {ci[0]:,.0f}..{ci[1]:,.0f}), "
          f"wallets {len({r['w'] for r in pr})}")
        P("     $ (locked) by s after first move: " + ", ".join(f"{k} ${b[k]:,.0f} (${lk[k]:,.0f})" for k in ("0-1", "2-3", "4-6", "7-10", "11-30", "31-60", ">60")))
        late_w = Counter(r["w"] for r in pr if r["dt"] >= 4)
        P(f"     wallets taking stale prints >= 4 s after the first move: {len(late_w)}; $ {sum(r['usd'] for r in pr if r['dt'] >= 4):,.0f}")
for sp in ("soccer", "nfl"):
    P(f"(c) {sp} mean share of the jump J reached at h s after first +3c print: " + ", ".join(
        f"+{h}s {st.mean(v):.2f} (n {len(v)})" for h, v in sorted(paths[sp].items())))


def summ(rows, label):
    for sp in ("soccer", "nfl"):
        for d in (3, 10, 60):
            for per in ("early", "late", "all"):
                tt = [r for r in rows if r["sport"] == sp and r["d"] == d and (per == "all" or r["period"] == per)]
                num, den = defaultdict(float), defaultdict(float)
                for r in tt:
                    num[r["game"]] += r["pnl"] * r["sh"]
                    den[r["game"]] += r["sh"]
                ks = list(num)
                rr, se, t = ratio_cluster([num[k] for k in ks], [den[k] for k in ks])
                P(f"{label} {sp}-T{d} {per}: n {len(tt)} games {len(ks)} {100*rr:.2f} c/share se {100*se:.2f} t {t:.2f}")


summ(rt, "(d) round trip, sell at bid >= +300 s, two fees:")
summ(mark_sell, "(e) markout vs sell-side prints only:")
(A.OUT / "diag.txt").write_text("\n".join(out) + "\n")
print("\n".join(out))

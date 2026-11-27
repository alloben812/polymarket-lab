"""Tickets and summary tables for every dataset and variant (protocol sections 2, 4, 5). Writes out/*.md, out/*.csv."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BOOK_DELAYS, BUDGET, CAPS, DATA, MIN_SHARES, OUT, summarise  # noqa: E402
from pmlab import updown  # noqa: E402

LINES = []


def say(s=""):
    print(s)
    LINES.append(s)


def book_tickets():
    q = pd.read_parquet(DATA / "book_queries.parquet")
    mk = pd.read_parquet(DATA / "mw" / "markets.parquet")
    mk["t0"] = mk.market_slug.str.rsplit("-", n=1).str[1].astype(int)
    mk = mk[(mk.t0 >= 1786665600) & (mk.t0 < 1787356800)]
    up = {}
    missing = 0
    for t0, w in zip(mk.t0, mk.winning_outcome):
        if w in ("yes", "no"):
            up[int(t0)] = w == "yes"
        else:
            m = updown.load_market("btc", "5m", int(t0))
            if m and m.get("up_won") is not None:
                up[int(t0)] = bool(m["up_won"])
            else:
                missing += 1
    say(f"OOS-BOOK: {len(mk)} windows, outcome from dataset {int(mk.winning_outcome.isin(['yes','no']).sum())}, "
        f"from gamma {len(up) - int(mk.winning_outcome.isin(['yes','no']).sum())}, unknown {missing} (dropped)")
    q = q[q.t0.isin(up.keys())]
    key = {(r.t0, r.T, r.off): (np.asarray(r.ask_p), np.asarray(r.ask_z), r.seen_book) for r in q.itertuples()}
    sigs = q[["t0", "T", "tail"]].drop_duplicates().sort_values(["t0", "T"])
    say(f"  signal seconds {len(sigs)} in {sigs.t0.nunique()} markets; queries without any book snapshot in the window: "
        f"{int((~q.seen_book).sum())} of {len(q)}")
    recs = []
    variants = [(d, 0.0) for d in BOOK_DELAYS] + [(0.0, 0.5), (2.0, 0.5)]
    for cap, Z in CAPS.items():
        for d, shift in variants:
            for t0, g in sigs.groupby("t0"):
                att = 0
                for T, tail in zip(g["T"], g["tail"]):
                    vp, vz, _ = key[(t0, T, shift)]
                    if not ((vp <= Z + 1e-9) & (vz > 0)).any():
                        continue
                    att += 1
                    fp, fz, _ = key[(t0, T, round(shift + d, 4))]
                    m = (fp <= Z + 1e-9) & (fz > 0)
                    rem, sh, st = BUDGET, 0.0, 0.0
                    avail = float((fp[m] * fz[m]).sum())
                    for pp, zz in zip(fp[m], fz[m]):
                        take = min(zz, rem / pp)
                        sh += take
                        st += take * pp
                        rem -= take * pp
                        if rem <= 1e-9:
                            break
                    if sh >= MIN_SHARES:
                        recs.append({"t0": t0, "cap": cap, "d": d, "shift": shift, "T": T, "tail": tail, "shares": sh, "stake": st,
                                     "attempts": att, "avail": avail, "hit": (tail == "Up") == up[t0]})
                        break
    t = pd.DataFrame(recs)
    t["rate_cur"] = 0.05
    t["rate_hist"] = 0.07
    t.to_parquet(DATA / "tickets_oos_book.parquet")
    # offer-visible signal markets per cap (attempt markets)
    vis = {}
    for cap, Z in CAPS.items():
        n = 0
        for t0, g in sigs.groupby("t0"):
            if any(((key[(t0, T, 0.0)][0] <= Z + 1e-9) & (key[(t0, T, 0.0)][1] > 0)).any() for T in g["T"]):
                n += 1
        vis[cap] = n
    return t, len(up), sigs.t0.nunique(), vis


def table(t, days_total, split, title, delays, rate="rate_cur", extra_cols=None):
    say(f"\n### {title}\n")
    say("| cap | delay s | part | tickets | per day | kept vs first delay | avg price | hits (rate) [Wilson 95%] | break-even | exact p | "
        "net $ | net/ticket $ [95%] | return on stake | day-boot 95% of net $ | net w/o best 3 |")
    say("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    rows = []
    for cap in CAPS:
        base_n = None
        for d in delays:
            sub = t[(t.cap == cap) & (t.d == d)] if len(t) else t
            for part, (lo, hi, nd) in split.items():
                s = sub[(sub.t0 >= lo) & (sub.t0 < hi)] if len(sub) else sub
                r = summarise(s.assign(day=s.t0 // 86400), nd, rate) if len(s) else {"tickets": 0}
                if part == "all" and base_n is None:
                    base_n = r["tickets"]
                r.update(cap=cap, d=d, part=part)
                rows.append(r)
                if r["tickets"] == 0:
                    say(f"| {cap} | {d} | {part} | 0 | 0 | | | | | | | | | | |")
                    continue
                kept = f"{100 * r['tickets'] / base_n:.0f}%" if part == "all" and base_n else ""
                say(f"| {cap} | {d} | {part} | {r['tickets']} | {r['tickets_per_day']:.1f} | {kept} | {r['avg_price']:.4f} | "
                    f"{r['hits']} ({100 * r['hit_rate']:.1f}%) [{100 * r['wil_lo']:.1f}, {100 * r['wil_hi']:.1f}] | {100 * r['breakeven']:.2f}% | "
                    f"{r['p_binom']:.3g} | {r['net']:+.2f} | {r['net_per_ticket']:+.3f} [{r['npt_lo']:+.3f}, {r['npt_hi']:+.3f}] | "
                    f"{100 * r['ros']:+.0f}% | [{r['boot_lo']:+.1f}, {r['boot_hi']:+.1f}] | {r['net_wo_best3']:+.2f} |")
    return pd.DataFrame(rows)


def main():
    allrows = []
    # ---------------- OOS-BOOK
    tb, n_mk, n_sig, vis = book_tickets()
    say(f"  markets with outcome {n_mk}; with a Binance signal {n_sig}; with a signal AND the tail offered at <= cap at tau: "
        f"Z1 {vis['Z1']}, Z2 {vis['Z2']}")
    D = 86400
    a0 = 1786665600
    sp = {"all": (a0, a0 + 8 * D, 8), "Aug14-17": (a0, a0 + 4 * D, 4), "Aug18-21": (a0 + 4 * D, a0 + 8 * D, 4)}
    main_b = tb[tb["shift"] == 0.0]
    r = table(main_b, 8, sp, "OOS-BOOK, BTC 5m, 2026-08-14..21, fee 0.05 (today)", BOOK_DELAYS)
    r["dataset"] = "oos_book"; allrows.append(r)
    r = table(main_b, 8, {"all": sp["all"]}, "OOS-BOOK, historical fee 0.07", BOOK_DELAYS, rate="rate_hist")
    r["dataset"] = "oos_book_fee07"; allrows.append(r)
    sh = tb[tb["shift"] == 0.5]
    r = table(sh, 8, {"all": sp["all"]}, "OOS-BOOK sensitivity: tau shifted +0.5 s (clock offset), fee 0.05", [0.0, 2.0])
    r["dataset"] = "oos_book_shift"; allrows.append(r)
    # $20 capacity at the fill moment
    say("\nShown size at <= cap at the fill moment (OOS-BOOK, all tickets): share of tickets whose $20 order would fill in full")
    for cap in CAPS:
        for d in BOOK_DELAYS:
            s = main_b[(main_b.cap == cap) & (main_b.d == d)]
            if len(s):
                say(f"- {cap} d={d}: {100 * (s.avail >= 20).mean():.0f}% (median shown ${s.avail.median():.1f}, n {len(s)})")
    # ---------------- OOS-TAPE
    p = DATA / "tickets_oos_tape.parquet"
    if p.exists():
        tt = pd.read_parquet(p)
        info = json.loads((DATA / "oos_tape_grids.json").read_text())
        say(f"\nOOS-TAPE: sub-grids complete {info['complete']}, markets used {info['used']} of {info['windows']} windows")
        b0 = 1787356800
        frac = info["used"] / info["windows"]
        spt = {"all": (b0, b0 + 10 * D, 10 * frac), "Aug22-26": (b0, b0 + 5 * D, 5 * frac), "Aug27-31": (b0 + 5 * D, b0 + 10 * D, 5 * frac)}
        r = table(tt, 10, spt, "OOS-TAPE, BTC 5m, 2026-08-22..31, tape fill rule, fee 0.05 (per-day figures scaled to all windows)", [1.0, 2.0, 5.0])
        r["dataset"] = "oos_tape"; allrows.append(r)
    # ---------------- FORMATION
    tf = pd.read_parquet(DATA / "tickets_formation.parquet")
    f0, nov1, end = 1788220800, 1793491200, 1795737600
    spf = {"all": (f0, end, 87 / 4), "Sep-Oct": (f0, nov1, 61 / 4), "Nov1-26": (nov1, end, 26 / 4)}
    r = table(tf, 87, spf, "FORMATION (in-sample), BTC 5m grid Sep 1 - Nov 26, tape fill rule, fee 0.05 (per day scaled x4)", [1.0, 2.0, 5.0])
    r["dataset"] = "formation"; allrows.append(r)
    r = table(tf, 87, {"all": spf["all"]}, "FORMATION, historical fee (0.07 before Nov 21)", [1.0, 2.0, 5.0], rate="rate_hist")
    r["dataset"] = "formation_fee_hist"; allrows.append(r)
    # ---------------- OTHERS
    to = pd.read_parquet(DATA / "tickets_others.parquet")
    o0 = 1795219200
    spo = {"all": (o0, o0 + 6 * D, 6), "Nov21-23": (o0, o0 + 3 * D, 3), "Nov24-26": (o0 + 3 * D, o0 + 6 * D, 3)}
    for fam, g in to.groupby("family"):
        r = table(g, 6, spo, f"OTHER FAMILY {fam}, 2026-11-21..26, tape fill rule, fee {g.rate_cur.iloc[0]}", [1.0, 2.0, 5.0])
        r["dataset"] = fam; allrows.append(r)
    pd.concat(allrows, ignore_index=True).to_csv(OUT / "summary.csv", index=False)
    (OUT / "tables.md").write_text("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()

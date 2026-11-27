"""Step 4: tables from data/gaps_copy/trades.json.gz -> out/report.txt, out/variants.csv."""
import collections
import csv
import gzip
import json
import math
from pathlib import Path

from pmlab.stats import ratio_cluster

ROOT = Path("/home/user/polymarket-lab")
OUT = ROOT / "studies/gaps/copy_trading/out"
CACHE = ROOT / "data/gaps_copy"
VARS = ["ref_wallet_price"] + [f"d{d}_{e}" for d in (10, 60, 300) for e in ("hold", "mirror")]
L = []


def say(s=""):
    print(s)
    L.append(s)


def agg(rows, key="c"):
    f = [r for r in rows if r.get("filled")]
    byc = collections.defaultdict(lambda: [0.0, 0.0])
    for r in f:
        byc[r[key]][0] += r["net"]
        byc[r[key]][1] += r["cost"]
    num = [v[0] for v in byc.values()]
    den = [v[1] for v in byc.values()]
    ret, se, t = ratio_cluster(num, den)
    # drop 5 best markets (by net)
    bym = collections.defaultdict(lambda: [0.0, 0.0])
    for r in f:
        bym[r["c"]][0] += r["net"]
        bym[r["c"]][1] += r["cost"]
    keep = sorted(bym.items(), key=lambda kv: -kv[1][0])[5:]
    d5 = (sum(v[0] for _, v in keep) / sum(v[1] for _, v in keep)) if keep and sum(v[1] for _, v in keep) > 0 else float("nan")
    return {"entries": len(rows), "filled": len(f), "fill_rate": len(f) / len(rows) if rows else float("nan"),
            "markets": len({r["c"] for r in f}), "wallets": len({r["wallet"] for r in f}),
            "cost": sum(r["cost"] for r in f), "net": sum(r["net"] for r in f), "ret": ret, "se": se, "t": t,
            "net_per_trade": (sum(r["net"] for r in f) / len(f)) if f else float("nan"), "drop5": d5}


def fmt(a):
    if a["filled"] == 0:
        return f"entries {a['entries']:4d} filled    0"
    lo, hi = a["ret"] - 1.96 * a["se"], a["ret"] + 1.96 * a["se"]
    return (f"entries {a['entries']:4d} filled {a['filled']:4d} ({a['fill_rate']*100:5.1f}%) mkts {a['markets']:4d} "
            f"wal {a['wallets']:2d} cost ${a['cost']:8.0f} net ${a['net']:8.1f} ret {a['ret']*100:+6.2f}% "
            f"[{lo*100:+6.2f},{hi*100:+6.2f}] t {a['t']:+5.2f} $/trade {a['net_per_trade']:+6.3f} drop5 {a['drop5']*100:+6.2f}%")


def main():
    T = json.load(gzip.open(CACHE / "trades.json.gz", "rt"))
    rows_csv = []
    for win in ("early", "late"):
        say(f"=== window {win} ===")
        for v in VARS:
            rs = [r for r in T if r["win"] == win and r["variant"] == v]
            a = agg(rs)
            aw = agg(rs, key="wallet")
            say(f"{v:17s} {fmt(a)}  t_by_wallet {aw['t']:+5.2f}")
            rows_csv.append({"window": win, "variant": v, "group": "all", **{k: a[k] for k in a}, "t_wallet": aw["t"]})
            rr = [r for r in rs if r["resolved"]]
            ar = agg(rr)
            say(f"{'  resolved only':17s} {fmt(ar)}")
            for gname in ("etype", "wtype", "cat"):
                groups = sorted({r[gname] for r in rs})
                for g in groups:
                    sub = [r for r in rs if r[gname] == g]
                    a2 = agg(sub)
                    aw2 = agg(sub, key="wallet")
                    say(f"  {gname}={g:14s} {fmt(a2)}  t_by_wallet {aw2['t']:+5.2f}")
                    rows_csv.append({"window": win, "variant": v, "group": f"{gname}={g}", **{k: a2[k] for k in a2}, "t_wallet": aw2["t"]})
            say()
    with open(OUT / "variants.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows_csv[0].keys()))
        wr.writeheader()
        for r in rows_csv:
            wr.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()})
    # slippage and lag diagnostics, late window
    say("=== late: price paid minus wallet price (c/share), by delay and entry type (filled) ===")
    for d in (10, 60, 300):
        for et in ("TAKER", "MAKER"):
            rs = [r for r in T if r["win"] == "late" and r["variant"] == f"d{d}_hold" and r["filled"] and r["etype"] == et]
            if rs:
                sl = sorted(r["slip"] for r in rs)
                say(f"d{d} {et}: n {len(rs)} median slip {sl[len(sl)//2]*100:+.2f}c mean {sum(sl)/len(sl)*100:+.2f}c, "
                    f"median fill lag {sorted(r['lag_s'] for r in rs)[len(rs)//2]} s")
    # per-wallet late table (d60 hold)
    say("\n=== late, per wallet: ref vs d10/d60/d300 hold (ret %, filled) ===")
    sel = json.load(open(OUT / "selected_typed.json"))
    for w, s in sel.items():
        parts = []
        for v in ("ref_wallet_price", "d10_hold", "d60_hold", "d300_hold"):
            a = agg([r for r in T if r["win"] == "late" and r["variant"] == v and r["wallet"] == w])
            parts.append(f"{v.split('_')[0]} {a['ret']*100 if a['filled'] else float('nan'):+7.1f}% n{a['filled']}")
        ts = s.get("taker_share_early")
        say(f"{str(s.get('name'))[:20]:20s} {s['source']:16s} taker_share {ts if ts is None else round(ts,2)!s:5s} | " + " | ".join(parts))
    # opportunities per day (all late entries of chosen wallets)
    summ = json.load(open(CACHE / "entry_summary.json"))
    say("\n=== late: entries (first buy per token) per UTC day, all chosen wallets ===")
    perday = collections.Counter()
    rate_total = 0.0
    capped = 0
    for s in summ:
        if s["win"] != "late":
            continue
        days = (s["span1"] - s["span0"]) / 86400
        if s["capped"]:
            capped += 1
        if days > 0:
            rate_total += s["entries"] / days
        for dd in s["entry_days"]:
            perday[dd] += 1
    import datetime as dt
    for dd in sorted(perday):
        say(f"{dt.datetime.fromtimestamp(dd*86400, dt.timezone.utc):%Y-%m-%d %a}: {perday[dd]} entries (capped wallets cover part only)")
    unc = collections.Counter()
    nunc = 0
    for s in summ:
        if s["win"] == "late" and not s["capped"]:
            nunc += 1
            for dd in s["entry_days"]:
                unc[dd] += 1
    say(f"uncapped wallets only ({nunc}): " + ", ".join(f"{dt.datetime.fromtimestamp(dd*86400, dt.timezone.utc):%a %d}: {unc[dd]}" for dd in sorted(unc)))
    for d in (10, 60, 300):
        for lab, days in (("weekend 21-22", {20778, 20779}), ("weekdays 23-25", {20780, 20781, 20782})):
            a = agg([r for r in T if r["win"] == "late" and r["variant"] == f"d{d}_hold" and r["day"] in days])
            say(f"d{d}_hold {lab}: {fmt(a)}")
    say(f"estimated entries/day over all chosen wallets (coverage-adjusted): {rate_total:.0f}; wallets capped at 4000 fills: {capped}")
    for d in (10, 60, 300):
        rs = [r for r in T if r["win"] == "late" and r["variant"] == f"d{d}_hold"]
        fr = sum(r["filled"] for r in rs) / len(rs) if rs else float("nan")
        say(f"d{d}: fill rate {fr*100:.1f}% -> about {rate_total*fr:.0f} copyable entries/day")
    hh = sorted(r["hold_h"] for r in T if r["win"] == "late" and r["variant"] == "d60_hold" and r.get("filled") and r.get("hold_h") is not None)
    if hh:
        say(f"hours from entry to market close/end (d60 filled, n {len(hh)}): median {hh[len(hh)//2]:.1f}, p25 {hh[len(hh)//4]:.1f}, p75 {hh[3*len(hh)//4]:.1f}")
    (OUT / "report.txt").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()

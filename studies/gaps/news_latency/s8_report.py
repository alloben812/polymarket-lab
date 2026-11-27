"""Step 8: tables for results.md (protocol sections 5-6). Reads out/jumps.json, labels.csv, measure.json, rule.json."""
import collections, csv, json, statistics as st, sys
from pmlab import stats
from common import *

DELAYS = [10, 30, 120, 600]


def q(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def fmt(x, n=2):
    if x is None or (isinstance(x, float) and x != x):
        return "-"
    return f"{x:.{n}f}"


def load():
    jumps = json.load(open(OUT / "jumps.json"))
    lab = {}
    if (OUT / "labels.csv").exists():
        for r in csv.DictReader(open(OUT / "labels.csv")):
            lab[(r["c"], int(r["t0"]))] = r
    ok = [j for j in jumps if j["status"] in ("main", "R")]
    for j in ok:
        l = lab.get((j["c"], j["t0"]))
        j["label"] = l["label"] if l else "unlabelled"
        j["doubt"] = bool(l and l.get("doubt"))
        j["half"] = 1 if j["t0"] < SPLIT else 2
        payoff = j["settle_f"] if j["resolved"] else j["mark_f"]
        j["payoff"] = payoff
        j["reversed"] = (payoff < 0.5) if j["resolved"] else (j["mark_f"] < j["pf_pre"] + 0.5 * (j["p10"] - j["pf_pre"]))
        j["day"] = iso(j["t0"])[:10]
    meas = {(m["c"], m["t0"]): m for m in json.load(open(OUT / "measure.json"))}
    rule = collections.defaultdict(dict)
    rp = OUT / "rule.json"
    if rp.exists():
        for r in json.load(open(rp)):
            rule[(r["c"], r["t0"])][r["d"]] = r
    return jumps, ok, meas, rule


def rule_row(js, rule, d):
    rows = [(j, rule[(j["c"], j["t0"])][d]) for j in js if d in rule.get((j["c"], j["t0"]), {})]
    n = len(rows)
    if n == 0:
        return None
    filled = [(j, r) for j, r in rows if r["shares"] > 0]
    spent = sum(r["spent"] for _, r in filled)
    shares = sum(r["shares"] for _, r in filled)
    fee = sum(r["fee"] for _, r in filled)
    net = sum(r["net"] for _, r in rows)
    by_cl, by_day, den_cl = collections.defaultdict(float), collections.defaultdict(float), collections.defaultdict(float)
    for j, r in rows:
        by_cl[j["cluster"]] += r["net"]
        den_cl[j["cluster"]] += r["spent"]
        by_day[j["day"]] += r["net"]
    m_cl, se_cl, t_cl = stats.mean_se(list(by_cl.values()))
    m_d, se_d, t_d = stats.mean_se(list(by_day.values()))
    keys = sorted(by_cl)
    roi, roi_se, roi_t = stats.ratio_cluster([by_cl[k] for k in keys], [den_cl[k] for k in keys])
    return {"n": n, "markets": len({j["c"] for j, _ in rows}), "clusters": len(by_cl), "days": len(by_day), "filled": len(filled),
            "spent": spent, "avg_p": spent / shares if shares else None, "fee": fee,
            "rev_all": sum(1 for j, _ in rows if j["reversed"]) / n, "rev_filled": (sum(1 for j, _ in filled if j["reversed"]) / len(filled)) if filled else None,
            "net": net, "net_per_event": net / n, "t_cluster": t_cl, "t_day": t_d, "roi": roi, "roi_t": roi_t,
            "unresolved_filled": sum(1 for j, r in filled if not j["resolved"]),
            "net_resolved_only": sum(r["net"] for j, r in rows if j["resolved"])}


def rule_table(title, js, rule, out):
    out.append(f"\n**{title}**\n")
    out.append("| category | delay | events | markets | clusters | with fill | $ spent | avg entry | reversed (all / filled) | fee $ | net $ total | net $/event | return on $ | t (cluster) | t (day) | unresolved fills |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for cat in ["geopolitics", "other politics", "elections", "ALL"]:
        sub = js if cat == "ALL" else [j for j in js if j["cat"] == cat]
        for d in DELAYS:
            r = rule_row(sub, rule, d)
            if r is None:
                continue
            out.append(f"| {cat} | {d} s | {r['n']} | {r['markets']} | {r['clusters']} | {r['filled']} | {r['spent']:.0f} | {fmt(r['avg_p'],3)} | "
                       f"{r['rev_all']*100:.0f}% / {fmt(None if r['rev_filled'] is None else r['rev_filled']*100,0)}% | {r['fee']:.2f} | {r['net']:+.0f} | {r['net_per_event']:+.1f} | "
                       f"{fmt(None if r['roi'] != r['roi'] else r['roi']*100,1)}% | {fmt(r['t_cluster'])} | {fmt(r['t_day'])} | {r['unresolved_filled']} |")


def main():
    jumps, ok, meas, rule = load()
    out = []
    cands = json.load(open(OUT / "candidates.json"))
    out.append("## Funnel\n")
    out.append(f"- universe markets: {len(universe())}; screen candidates: {len(cands)} in {len({c['c'] for c in cands})} markets")
    stc = collections.Counter(j["status"] for j in jumps)
    out.append(f"- on tape: no first print 0.10 beyond the pre-price: {len(cands) - len(jumps)}; not confirmed (p10 - pre < 0.40): {stc['unconfirmed']}; "
               f"pre-price artefact: {stc['artefact']}; confirmed and held 2 h (main): {stc['main']}; confirmed, reverted within 2 h (R): {stc['R']}")
    lc = collections.Counter((j["status"], j["label"]) for j in ok)
    out.append(f"- labels: {dict(sorted(lc.items()))}")
    out.append(f"- screen bucket of confirmed jumps: {dict(collections.Counter(j['bucket'] for j in ok))}")
    um = [j for j in ok if j["status"] == "main" and j["label"] == "unscheduled"]
    sm = [j for j in ok if j["status"] == "main" and j["label"] == "scheduled"]
    ur = [j for j in ok if j["status"] == "R" and j["label"] == "unscheduled"]
    sr = [j for j in ok if j["status"] == "R" and j["label"] == "scheduled"]
    weeks = (W1 - W0) / 604800
    out.append(f"- unscheduled main: {len(um)} jumps, {len({j['c'] for j in um})} markets, {len({j['cluster'] for j in um})} news clusters, "
               f"{len({j['day'] for j in um})} days -> {len(um)/weeks:.1f} jumps and {len({j['cluster'] for j in um})/weeks:.1f} clusters per week; "
               f"first half {sum(1 for j in um if j['half']==1)}, second half {sum(1 for j in um if j['half']==2)}")
    out.append(f"- scheduled main: {len(sm)} jumps, {len({j['cluster'] for j in sm})} clusters; R: unscheduled {len(ur)}, scheduled {len(sr)}")
    out.append(f"- categories (unscheduled main): {dict(collections.Counter(j['cat'] for j in um))}; direction: {dict(collections.Counter('YES' if j['dir']>0 else 'NO' for j in um))}")
    out.append(f"- unresolved today (unscheduled main): {sum(1 for j in um if not j['resolved'])}; reversed at settlement/mark: {sum(1 for j in um if j['reversed'])}")

    def speed(title, js):
        out.append(f"\n**{title}** (n = {len(js)})\n")
        if not js:
            return
        ms = [meas[(j["c"], j["t0"])] for j in js]
        out.append("| measure | p25 | median | p75 |")
        out.append("|---|---|---|---|")
        for name, xs in [("price before (F side)", [j["pf_pre"] for j in js]), ("first print", [j["p_first"] for j in js]),
                         ("price at +10 min", [j["p10"] for j in js]), ("price at +2 h", [j["p2h"] for j in js]),
                         ("seconds to 50% of move", [m["t50"] for m in ms]), ("seconds to 90% of move", [m["t90"] for m in ms]),
                         ("seconds to 0.95 (reached within 24 h)", [m["t95"] for m in ms])]:
            out.append(f"| {name} | {fmt(q(xs,.25))} | {fmt(q(xs,.5))} | {fmt(q(xs,.75))} |")
        n = len(js)
        for lim in (10, 30, 120, 600, 7200):
            out.append(f"- reached 0.95 within {lim} s: {sum(1 for m in ms if m['t95'] is not None and m['t95'] <= lim)} of {n}; "
                       f"90% of the move within {lim} s: {sum(1 for m in ms if m['t90'] is not None and m['t90'] <= lim)} of {n}")
        out.append(f"- never printed 0.95 within 24 h: {sum(1 for m in ms if m['t95'] is None)} of {n}")
        out.append("\n| seconds after t0 | prints | $ all prints | $ F on offer | VWAP of F on offer | $ F on offer <= 0.90 | VWAP <= 0.90 | jumps with any offer <= 0.90 | median $ <= 0.90 per jump | realised $ to buyers (payoff - price) |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for k in range(5):
            b = [m["buckets"][k] for m in ms]
            bu = sum(x["buy_usd"] for x in b)
            sh = sum(x["buy_usd"] / x["buy_vwap"] for x in b if x["buy_vwap"])
            b90 = sum(x["buy90_usd"] for x in b)
            sh90 = sum(x["buy90_usd"] / x["buy90_vwap"] for x in b if x["buy90_vwap"])
            real = sum((j["payoff"] - x["buy_vwap"]) * x["buy_usd"] / x["buy_vwap"] for j, x in zip(js, b) if x["buy_vwap"])
            out.append(f"| {b[0]['a']}-{b[0]['b']} | {sum(x['n'] for x in b)} | {sum(x['usd'] for x in b):,.0f} | {bu:,.0f} | {fmt(bu/sh if sh else None,3)} | {b90:,.0f} | "
                       f"{fmt(b90/sh90 if sh90 else None,3)} | {sum(1 for x in b if x['buy90_usd']>0)} | {fmt(q([x['buy90_usd'] for x in b],.5),0)} | {real:+,.0f} |")
        f10 = [m["first10"] for m in ms]
        out.append(f"\n- first 10 s, buy-F takers: median wallets {fmt(q([f['n_wallets'] for f in f10],.5),0)} (p25 {fmt(q([f['n_wallets'] for f in f10],.25),0)}, p75 {fmt(q([f['n_wallets'] for f in f10],.75),0)}); "
                   f"median $ {fmt(q([f['usd'] for f in f10],.5),0)}; median top-3 share {fmt(q([f['top3_share'] for f in f10],.5),2)}; jumps with no buy-F taker in 10 s: {sum(1 for f in f10 if f['n_wallets']==0)}")
        wc, wusd = collections.defaultdict(set), collections.Counter()
        for j, m in zip(js, ms):
            for w, v in m["first10"]["wallets"].items():
                wc[w].add(j["cluster"])
                wusd[w] += v
        ncl = len({j["cluster"] for j in js})
        rep = sorted(wc.items(), key=lambda kv: (-len(kv[1]), -wusd[kv[0]]))
        out.append(f"- distinct first-10-s wallets: {len(wc)}; in >= 2 clusters: {sum(1 for w, s in wc.items() if len(s)>=2)}; in >= 3: {sum(1 for w, s in wc.items() if len(s)>=3)}; in >= 5: {sum(1 for w, s in wc.items() if len(s)>=5)} (of {ncl} clusters)")
        tot = sum(wusd.values())
        out.append("- most frequent first-10-s wallets (clusters, $ in first 10 s, share of all first-10-s $): " +
                   "; ".join(f"{w[:10]} ({len(s)}, ${wusd[w]:,.0f}, {wusd[w]/tot*100:.0f}%)" for w, s in rep[:8]))
        covered = set()
        for w, s in rep[:5]:
            covered |= s
        out.append(f"- clusters in which at least one of the 5 most frequent wallets is among the first-10-s buyers: {len(covered)} of {ncl}")

    out.append("\n## Speed of absorption")
    speed("Unscheduled, main sample", um)
    speed("Scheduled, main sample", sm)
    speed("Unscheduled, reverted within 2 h (R)", ur)

    if rule:
        out.append("\n## Rule (buy F at prints <= 0.90 from t0 + d for 10 minutes, $200, hold to settlement)")
        rule_table("Unscheduled main, whole period", um, rule, out)
        rule_table("Unscheduled main, first half (1 Sep - 13 Oct)", [j for j in um if j["half"] == 1], rule, out)
        rule_table("Unscheduled main, second half = reporting period (14 Oct - 25 Nov)", [j for j in um if j["half"] == 2], rule, out)
        rule_table("Look-ahead check: unscheduled R only (reverted within 2 h), whole period", ur, rule, out)
        rule_table("Look-ahead check: unscheduled main + R, whole period", um + ur, rule, out)
        rule_table("Look-ahead check: unscheduled main + R, second half", [j for j in um + ur if j["half"] == 2], rule, out)
        rule_table("Scheduled main, whole period", sm, rule, out)
        rule_table("Scheduled main + R, whole period", sm + sr, rule, out)
        out.append("\n**Resolved-only totals (unscheduled main, whole period)**: " + "; ".join(
            f"{d} s: {rule_row(um, rule, d)['net_resolved_only']:+.0f}" for d in DELAYS if rule_row(um, rule, d)))
        b2 = [j for j in um if rule[(j['c'], j['t0'])][120]['shares'] > 0]
        b2s = [j for j in um if rule[(j['c'], j['t0'])][120]['spent'] >= 50]
        out.append(f"\n- still buyable at 2 minutes (a print <= 0.90 in t0+120 s .. +720 s): {len(b2)} of {len(um)} unscheduled main jumps "
                   f"({len({j['cluster'] for j in b2})} of {len({j['cluster'] for j in um})} clusters); with at least $50 fillable: {len(b2s)}")
        wk = collections.Counter((j["t0"] - W0) // 604800 for j in um)
        wk2 = collections.Counter((j["t0"] - W0) // 604800 for j in b2)
        out.append("- per week (week index from 1 Sep: jumps / buyable at 2 min): " + ", ".join(f"w{int(k)+1}: {wk[k]}/{wk2[k]}" for k in sorted(wk)))
    (OUT / "tables.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()

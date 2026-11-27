"""Per account x market type: how it trades (role, side, price, timing vs the deciding time) and per-market PnL
(cash-flow accounting with merges, fee in; resolved markets; unresolved marked at gamma's current price, shown apart)."""
import sys, json, collections, math, statistics
import fin
from pmlab import gamma, stats, fees

def rate(ts): return 0.05 if ts >= 1795219140 else 0.04   # finance 0.04 -> 0.05 at 2026-11-20 23:59 UTC (NOTES)
def tb(dt):
    if dt > 0: return "a after end"
    dt = -dt
    for lim, lab in ((600, "b 0-10m"), (3600, "c 10-60m"), (6.5*3600, "d 1-6.5h"), (86400, "e 6.5-24h"), (7*86400, "f 1-7d")):
        if dt <= lim: return lab
    return "g >7d"

def run(name):
    d = fin.load(name); meta = d["meta"]; res = d["res"]
    cur = gamma.markets_by_condition(list(meta), cache=False) if "--mark" in sys.argv else {}
    M = collections.defaultdict(lambda: dict(cash=0.0, sh=collections.Counter(), usd=0.0, fee=0.0, n=0, mk=0.0, neg=False, merges=0.0))
    T = collections.defaultdict(lambda: dict(n=0, usd=0.0, mk=0.0, buy=0.0, px=[], tb=collections.Counter(), mkts=set(), et=collections.Counter()))
    typ = {}
    for f in sorted(d["fills"], key=lambda r: r["timestamp"]):
        c = f["condition_id"]; m = meta.get(c) or {}
        ty, tk = fin.mtype(f["title"], f["slug"]); ty = ty or ("crypto" if "crypto" in (m.get("tags") or []) else "other"); typ[c] = ty
        sz, px, t = float(f["size"]), float(f["price"]), int(f["timestamp"]); usd = sz * px
        fee = fees.taker_fee(sz, px, rate(t)) if f["role"] == "T" and ty not in ("other",) else 0.0
        if ty == "crypto": fee = fees.taker_fee(sz, px, 0.01) if f["role"] == "T" else 0
        r = M[c]; sgn = 1 if f["side"] == "BUY" else -1
        r["cash"] -= sgn * usd + fee; r["sh"][f["outcome"]] += sgn * sz; r["usd"] += usd; r["fee"] += fee; r["n"] += 1; r["mk"] += usd if f["role"] == "M" else 0
        a = T[ty]; a["n"] += 1; a["usd"] += usd; a["mk"] += usd if f["role"] == "M" else 0; a["buy"] += usd if sgn > 0 else 0; a["px"].append(px); a["mkts"].add(c)
        end = fin.ts(m.get("endDate"))
        if end: a["tb"][tb(t - 3 - end)] += usd
        h = ((t - 3) % 86400) / 3600 - 5; h += 24 if h < 0 else 0
        a["et"]["RTH 9:30-16" if 9.5 <= h < 16 else "post 16-20" if 16 <= h < 20 else "pre 4-9:30" if 4 <= h < 9.5 else "night 20-4"] += usd
    for e in d["inv"]:
        c = e.get("condition_id"); 
        if c not in M: continue          # inventory events of markets without fills in the window are left out
        r = M[c]; sz = float(e.get("size") or 0)
        if e["type"] == "MERGE":
            r["cash"] += sz; r["merges"] += sz
            for o in list(r["sh"]) or []: pass
            r["merge_sh"] = r.get("merge_sh", 0) + sz
        elif e["type"] == "SPLIT":
            r["cash"] -= sz; r["merge_sh"] = r.get("merge_sh", 0) - sz
    print(f"\n######## {name}  fills {len(d['fills'])}  {d['start']}..{d['end']} (21 d)  inv {dict(collections.Counter(e['type'] for e in d['inv']))}")
    print(f"{'type':16}{'mkts':>5}{'fills':>6}{'usd':>9}{'mk%':>5}{'buy%':>5}{'medpx':>6} | {'res':>4}{'net$':>8}{'net%':>7}{'t':>6}{'win%':>5} | {'open':>4}{'mtm$':>8} | timing by usd (vs endDate) | ET session")
    tot = [0, 0, 0]
    for ty, a in sorted(T.items(), key=lambda kv: -kv[1]["usd"]):
        pn, un, den, mtm, nopen, ninc = [], [], [], 0.0, 0, 0
        for c in a["mkts"]:
            r = M[c]; ms = r.get("merge_sh", 0); rs = res.get(c) or {}
            sh = {o: v - ms for o, v in r["sh"].items()}
            if ms and len(sh) < 2: r["neg"] = True
            if any(v < -1e-3 for v in sh.values()) or r["neg"]: ninc += 1; continue
            fp = rs.get("final") if isinstance(rs.get("final"), dict) else None
            if fp is None and rs.get("resolved"):
                fp = {o.get("outcome"): float(o.get("final_price") or 0) for o in rs.get("outcomes", [])} if rs.get("outcomes") else None
            if rs.get("resolved") and fp:
                pn.append(r["cash"] + sum(v * fp.get(o, 0) for o, v in sh.items())); den.append(r["usd"])
            else:
                nopen += 1
                g = cur.get(c)
                if g:
                    outs = gamma.jfield(g.get("outcomes")); prs = [float(x) for x in gamma.jfield(g.get("outcomePrices")) or []]
                    mp = dict(zip(outs, prs)); mtm += r["cash"] + sum(v * mp.get(o, 0) for o, v in sh.items())
        net = sum(pn); t = stats.mean_se(pn)[2] if len(pn) > 2 else float("nan")
        win = sum(1 for x in pn if x > 0) / len(pn) if pn else float("nan")
        tbs = " ".join(f"{k[2:]}:{v / a['usd']:.0%}" for k, v in sorted(a["tb"].items()))
        ets = " ".join(f"{k.split()[0]}:{v / a['usd']:.0%}" for k, v in a["et"].most_common())
        print(f"{ty:16}{len(a['mkts']):5}{a['n']:6}{a['usd']:9.0f}{a['mk'] / a['usd']:5.0%}{a['buy'] / a['usd']:5.0%}{statistics.median(a['px']):6.2f} | {len(pn):4}{net:8.0f}{(net / sum(den) if den else float('nan')):7.1%}{t:6.1f}{win:5.0%} | {nopen:4}{mtm:8.0f} | {tbs} | {ets}  inc={ninc}")
        tot[0] += net; tot[1] += mtm; tot[2] += a["usd"]
    print(f"TOTAL resolved net {tot[0]:.0f}  open marked {tot[1]:.0f}  turnover {tot[2]:.0f}")
    json.dump({c: dict(type=typ.get(c), cash=r["cash"], usd=r["usd"], n=r["n"], sh=dict(r["sh"]), merge_sh=r.get("merge_sh", 0)) for c, r in M.items()}, open(f"{fin.HERE}/cache/{name}_mk.json", "w"))

if __name__ == "__main__":
    for n in [a for a in sys.argv[1:] if not a.startswith("--")]:
        run(n)

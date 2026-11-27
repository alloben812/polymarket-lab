"""Audit step 4: independent hindsight t_first (protocol 2.3) and the class A rule over all markets (2.5), plus
robustness cuts (best day, top events), first-2-seconds share of W4, and a fill-realism haircut."""
import gzip, json, math, statistics, collections, datetime as dt, sys
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/tennis_walkover/audit")
from a3_rule import tape, rule, U, E, D_, P1   # my own audit functions (a3), not the study's
A = sorted(U["A"], key=lambda r: r["closed"]); slugs = {r["slug"]: r for r in A}
cut = A[int(0.67 * len(A))]["closed"]
MK = {}
for line in gzip.open("/home/user/polymarket-lab/data/gaps_tennis_wo/events.jsonl.gz", "rt"):
    e = json.loads(line)
    if e["slug"] not in slugs: continue
    ms = []
    for m in e["markets"]:
        try: fin = [float(x) for x in json.loads(m["outcomePrices"])]; outs = json.loads(m["outcomes"])
        except Exception: continue
        if len(fin) != 2: continue
        ms.append(dict(cid=m["conditionId"], out=outs, fin=fin, type=m.get("sportsMarketType"), vol=m.get("volumeNum")))
    MK[e["slug"]] = ms

def tfirst(pr, ref):
    n = len(pr)
    for i, rf in enumerate(ref):
        if not (rf and rf[3]): continue
        und, r = rf[0], rf[1]; bad = 0
        for j in range(i + 1, n):
            xx = pr[j][1] if und == 0 else 1 - pr[j][1]
            if xx < r + 0.03 - E:
                bad += 1
                if bad > 2: break
        if bad <= 2: return pr[i][0]
    return None

TF = {}; S = {}
for r in A:
    st = {}
    for m in MK[r["slug"]]:
        res = tape(m["cid"], m["out"]) if m["vol"] else ([], [])
        st[m["cid"]] = (m, res[0] if res else [], res[1] if res else [])
    S[r["slug"]] = st
    _, pr, ref = st[r["cid"]]
    t0 = tfirst(pr, ref) if pr else None
    if t0 is None:
        c = [tfirst(p_, rf_) for cid, (m, p_, rf_) in st.items() if cid != r["cid"] and m["fin"] == [0.5, 0.5] and p_]
        c = [x for x in c if x is not None]
        t0 = min(c) if c else None
    TF[r["slug"]] = t0
print("t_first found", sum(1 for v in TF.values() if v is not None), "of", len(A))
ea = {o["slug"]: o.get("t_first") for o in json.load(open("/home/user/polymarket-lab/studies/gaps/tennis_walkover/out/events_A.json"))}
diff = [s for s in TF if (TF[s] is None) != (ea.get(s) is None) or (TF[s] is not None and abs(TF[s] - ea[s]) > 0.5)]
print("t_first disagreements with author:", len(diff), diff[:5])
known = {"2026-11-03": None}
for s, t in TF.items():
    if t and ("2026-11-03 09:3" in str(dt.datetime.fromtimestamp(t, dt.timezone.utc)) or "2026-11-18 11:15" in str(dt.datetime.fromtimestamp(t, dt.timezone.utc))):
        print("  sanity", s, dt.datetime.fromtimestamp(t, dt.timezone.utc))

def run(d, pmax=0.46, skip=0.0, lag_extra=0):
    rows = []
    for r in A:
        t0 = TF[r["slug"]]
        if t0 is None: rows.append((r, 0.0, 0.0, 0.0)); continue
        streams = [(pr, m["fin"]) for m, pr, ref in S[r["slug"]].values() if pr]
        n, c, sh, f = rule(streams, [t0 + d + lag_extra], pmax=pmax)
        rows.append((r, n, c, sh))
    return rows

def summ(rows, label):
    nets = [x[1] for x in rows]; n = len(nets); m = statistics.mean(nets); se = statistics.stdev(nets) / math.sqrt(n)
    fil = sum(1 for x in rows if x[3] > 0)
    days = collections.defaultdict(float)
    for x in rows: days[dt.datetime.fromtimestamp(x[0]["closed"], dt.timezone.utc).date()] += x[1]
    best_day = max(days.values()) if days else 0
    srt = sorted(nets, reverse=True)
    span = (P1 - rows[0][0]["closed"]) / 86400 if label.startswith("REPORT") else 86
    print(f"{label}: n {n} filled {fil} net {sum(nets):7.0f} per/ev {m:5.2f} CI [{m-1.96*se:5.2f},{m+1.96*se:5.2f}] t {m/se if se else 0:4.1f}"
          f" per day {sum(nets)/span:5.1f} | w/o best day {sum(nets)-best_day:6.0f} | w/o top3 {sum(srt[3:]):6.0f} | w/o top10 {sum(srt[10:]):6.0f}")
for d in D_:
    rows = run(d)
    summ(rows, f"ALL d={d}")
    summ([x for x in rows if x[0]["closed"] >= cut], f"REPORT d={d}")
# fill realism: the follower is one block later than the print it copies; require the copied liquidity to still be
# there one more block (3 s) later is not observable; proxy = start 3 s later and cap price at 0.45
for d in (10, 60):
    summ([x for x in run(d, lag_extra=3) if x[0]["closed"] >= cut], f"REPORT d={d}+3s")
    summ([x for x in run(d, pmax=0.45) if x[0]["closed"] >= cut], f"REPORT d={d} pmax0.45")

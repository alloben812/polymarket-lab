"""H5: whole-market tape around every bucket-killing report (see protocol.md addendum 3)."""
import json, sys, math, collections, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import dataapi
MK = json.load(open("out/mk.json")); OBS = json.load(open("out/obs2.json")); REC = json.load(open("out/receipt.json"))
T0 = dt.datetime(2026, 11, 22, tzinfo=dt.timezone.utc).timestamp()
def whole(t, unit):
    v = t / 10.0 if unit == "C" else t / 10.0 * 9 / 5 + 32
    return math.floor(v + 0.5 + 1e-9)
kills = []
for c, d in MK.items():
    if not d["ok"] or d["kind"] != "hi" or d["final"] is None or d["est"] < T0: continue
    k = next((t for t, v, _ in OBS.get(d["station"], []) if v is not None and d["est"] <= t < d["est"] + 86400 and whole(v, d["unit"]) > d["hi"]), None)
    if k is None or k == d["est"]: continue
    rc = REC.get(d["station"], {}).get(str(k))
    if rc: kills.append((c, d, k, rc))
print("kills", len(kills), flush=True)
def tape(x):
    c, d, k, rc = x
    for a in range(3):
        try: return x, list(dataapi.iter_trades(condition=c, taker_only=True, max_rows=20000))
        except Exception as e: time.sleep(2)
    return x, None
W = {"A": [0, 0.0, 0.0, set()], "B": [0, 0.0, 0.0, set()], "C": [0, 0.0, 0.0, set()]}
wal = collections.defaultdict(lambda: [0.0, 0.0, set(), []]); first_delay = []; fail = 0; grp = collections.Counter(); perkill = []
with ThreadPoolExecutor(4) as ex:
    for (c, d, k, rc), rows in ex.map(tape, kills):
        if rows is None: fail += 1; continue
        tot = 0.0; firsts = []
        for r in rows:
            longno = (r["side"] == "BUY") == (r["outcome"] == "No")
            if not longno: continue
            p = float(r["price"]); pno = p if r["outcome"] == "No" else 1 - p; sh = float(r["size"]); t = r["timestamp"] - 3
            if pno >= 0.985 or pno < 0.02 or not (k - 300 <= t < rc + 900): continue
            win = "A" if t < rc else "B" if t < rc + 60 else "C"
            prof = sh * (1 - pno) - 0.01 * sh * pno * (1 - pno)
            w = W[win]; w[0] += 1; w[1] += sh * pno; w[2] += prof; w[3].add(c)
            u = r.get("proxy_wallet") or r.get("user") or r.get("taker") or "?"
            a = wal[u]; a[0] += sh * pno; a[1] += prof; a[2].add(c); a[3].append(t - k)
            tot += prof; firsts.append(t - k)
            grp[("US" if d["station"].startswith("K") else "intl", win)] += prof
        perkill.append(tot)
        if firsts: first_delay.append(min(firsts))
json.dump({"W": {k: v[:3] + [len(v[3])] for k, v in W.items()}, "perkill": perkill}, open("out/niche.json", "w"))
print("tape failures", fail, "| sample row keys:", None)
for k, v in W.items(): print(f"window {k}: fills {v[0]}  $ {v[1]:.0f}  profit ${v[2]:.0f}  kills with a fill {len(v[3])}")
print("profit by region/window:", {f"{a}/{b}": round(v) for (a, b), v in sorted(grp.items())})
pk = sorted(perkill); n = len(pk)
print(f"kills analysed {n}; with any stale fill {sum(1 for x in pk if x > 0)}; profit per kill: median {pk[n//2]:.2f}, p90 {pk[int(.9*n)]:.2f}, max {pk[-1]:.0f}; total ${sum(pk):.0f} over days since Nov 22")
fd = sorted(first_delay); print("first stale fill minus report time (s): p10 %.0f median %.0f p90 %.0f" % (fd[len(fd)//10], fd[len(fd)//2], fd[9*len(fd)//10]) if fd else "none")
print("top wallets by profit (wallet, $, profit, kills, median s after report):")
for u, a in sorted(wal.items(), key=lambda kv: -kv[1][1])[:12]:
    s = sorted(a[3]); print(f"  {u}  ${a[0]:.0f}  profit ${a[1]:.0f}  kills {len(a[2])}  median {s[len(s)//2]:.0f}s")
print("wallets total", len(wal))

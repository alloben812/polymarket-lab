"""(1) size of the niche, (2) the post-decision 'bond' pool on the tapes, (3) finance taker fee implied by real charges."""
import json, os, collections, datetime as dt, statistics
import fin, yh, ladder, stories
from pmlab import dataapi, fees
exec(open("gap.py").read().split("def tape")[0])
vol = collections.Counter(); cnt = collections.Counter()
for c, m in U.items():
    T = fin.ts(m["endDate"])
    if T and fin.END - 21 * 86400 <= T <= fin.END: vol[m["ty"]] += m.get("volumeNum") or 0; cnt[m["ty"]] += 1
print("(1) resolved price markets ending in the 21-day window that at least one studied account touched (equity/ETF tickers):")
for k, v in vol.most_common(): print(f"    {k:12} markets {cnt[k]:5}  volume ${v:10,.0f}  per market ${v / cnt[k]:7,.0f}  median ${statistics.median([m.get('volumeNum') or 0 for m in U.values() if m['ty'] == k]):,.0f}")
print(f"    total ${sum(vol.values()):,.0f} in 21 days = ${sum(vol.values()) / 21:,.0f} per day")
PXc = {}
def px(tk):
    if tk not in PXc: PXc[tk] = yh.Px(tk)
    return PXc[tk]
pool = collections.Counter(); tk_w = collections.Counter(); nm = 0; gaps = []
for c, m in U.items():
    p = f"cache/tapes/{c}.json"
    if not os.path.exists(p): continue
    T = fin.ts(m["endDate"]); P = px(m["tk"])
    if not P.ok: continue
    tdec, lab = stories.decide_time(m, m["ty"], m["question"], T, P); closed = fin.ts(m.get("closedTime")); nm += 1
    if closed and lab != "period end, never touched": gaps.append(closed - tdec)
    for r in json.load(open(p)):
        t = int(r["timestamp"]) - 3; won = (m["final"] or {}).get(r["outcome"]) == 1.0; pr = float(r["price"]); sz = float(r["size"])
        if t < tdec + 60 or not won or pr < 0.90: continue          # +60 s: stay clear of the Yahoo/Pyth minute boundary
        b = "0.90-0.97" if pr < 0.97 else "0.97-0.99" if pr < 0.99 else "0.99-0.995" if pr < 0.995 else ">=0.995"
        pool[b + " usd"] += pr * sz; pool[b + " disc"] += (1 - pr) * sz; pool[b + " n"] += 1
        pool[b + (" takerbuy" if r["side"] == "BUY" else " takersell")] += (1 - pr) * sz
        tk_w[(r["proxy_wallet"], r["side"])] += (1 - pr) * sz
print(f"\n(2) post-decision trades of the WINNING outcome at >= 0.90 ({nm} markets with tapes: hit resolved Yes + close/updown), from decision + 60 s to resolution:")
for b in ("0.90-0.97", "0.97-0.99", "0.99-0.995", ">=0.995"):
    print(f"    px {b:10} trades {pool[b + ' n']:5.0f} usd {pool[b + ' usd']:10,.0f} discount to $1: ${pool[b + ' disc']:7,.0f}  (taker bought: ${pool[b + ' takerbuy']:6,.0f}; taker sold to a resting bid: ${pool[b + ' takersell']:6,.0f})")
tot = sum(v for k, v in pool.items() if k.endswith("disc")); print(f"    whole discount pool ${tot:,.0f} in 21 days over {nm} markets; median decision -> on-chain resolution {statistics.median(gaps) / 60:.0f} min (p10 {sorted(gaps)[len(gaps) // 10] / 60:.0f}, p90 {sorted(gaps)[9 * len(gaps) // 10] / 60:.0f})")
known = {v: k for k, v in fin.WALLETS.items()}
print("    top taker wallets by discount (side = what the taker did):", [(known.get(w, w[:10]), s, round(v)) for (w, s), v in tk_w.most_common(8)])
print("\n(3) finance taker fee implied by real charges (API daily fees / sum over taker fills of shares*p*(1-p)):")
for n in ("grasstoucher69", "thanksforplayin", "superstonksbro", "PippiTrader"):
    d = fin.load(n); base = collections.Counter()
    for f in d["fills"]:
        if f["role"] == "T": base[int(f["timestamp"]) // 86400] += float(f["size"]) * float(f["price"]) * (1 - float(f["price"]))
    pts = dataapi.user_pnl(d["wallet"], "all", "1d"); fee = {}; prev = None
    for q in pts:
        day = q["timestamp"] // 86400
        if prev is not None: fee[day] = -((q.get("fees") or 0) - (prev.get("fees") or 0))
        prev = q
    def imp(lo, hi):
        days = [x for x in base if lo <= x * 86400 < hi]; b = sum(base[x] for x in days); f = sum(fee.get(x, 0) + fee.get(x + 1, 0) * 0 for x in days)
        return (f / b if b else float("nan")), b, f
    a = imp(fin.END - 21 * 86400 + 86400, 1795132800); b = imp(1795305600, fin.END - 86400)
    print(f"    {n:16} Nov 7-19: rate {a[0]:.4f} (base {a[1]:,.0f}, fees {a[2]:,.0f})   Nov 22-26: rate {b[0]:.4f} (base {b[1]:,.0f}, fees {b[2]:,.0f})")
print("    sample of user_pnl point keys:", sorted(pts[-1].keys()))

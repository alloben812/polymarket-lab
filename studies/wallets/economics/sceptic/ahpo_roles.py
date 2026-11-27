"""Sceptic: Ahpo economics FIFO round trips split by how the lot was opened (taker / maker buy) and closed, and by
whether the opening buy came within 10 minutes after 12:30/13:30/18:00/19:00 UTC. Gross of fees; taker fee estimated
at 0.04 before 2026-11-21 (0 on 10-20..10-31), 0.01 after."""
import pickle, re, collections
ECON = re.compile(r"(fed|fomc|interest-rate|rate-cut|rate-hike|bps|cpi|inflation|jobs|payroll|unemployment|gdp|recession|ecb|bank-of-|pce|ppi|treasury|overheating|ism-)", re.I)
TP = "/home/user/polymarket-lab/data/econ_tapes"
def rate(t): return 0.0 if 1792454400 <= t < 1793491200 else (0.04 if t < 1795305600 else 0.01)
def fee(f): return rate(f["timestamp"]) * f["size"] * f["price"] * (1 - f["price"]) if f["role"] == "T" else 0.0
for lab, p in (("Jun-Aug", f"{TP}/sceptic_ahpo_jun_aug.pkl"), ("Sep-Nov", f"{TP}/fills_Ahpo.pkl")):
    E = sorted([f for f in pickle.load(open(p, "rb")) if ECON.search((f.get("event_slug") or "") + " " + f["slug"])], key=lambda f: f["timestamp"])
    lots = collections.defaultdict(list); cell = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for f in E:
        k = f["token_id"]
        if f["side"] == "BUY":
            news = any(0 <= (f["timestamp"] % 86400) - s <= 600 for s in (45000, 48600, 64800, 68400))
            lots[k].append([f["size"], f["price"], f["role"], news, fee(f) / f["size"]])
        else:
            s = f["size"]; fs = fee(f) / f["size"]
            while s > 1e-9 and lots[k]:
                L = lots[k][0]; q = min(s, L[0])
                for key in ((f"open {L[2]}", f"close {f['role']}"), (f"open {L[2]}", "all"), ("opened <=10 min after a release time" if L[3] else "opened at other times", "all")):
                    c = cell[key]; c[0] += q * L[1]; c[1] += q * (f["price"] - L[1]); c[2] += q * (L[4] + fs)
                L[0] -= q; s -= q
                if L[0] <= 1e-9: lots[k].pop(0)
    print(lab)
    for key in sorted(cell): c = cell[key]; print(f"   {key[0]:38} {key[1]:8} cost {c[0]:8.0f} gross {c[1]:7.0f} est. taker fee {c[2]:6.0f} net {c[1]-c[2]:7.0f} ({100*(c[1]-c[2])/c[0]:.2f}% of cost)")

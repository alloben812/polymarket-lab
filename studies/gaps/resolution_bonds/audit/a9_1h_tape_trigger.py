"""Audit a9: live-like rule without 5-minute snapshots, on the 430 btc/eth-updown-1h markets of 18-26 Nov:
trigger = first taker BUY print on either token at [0.95,0.98) in [endDate-1h, close); buy = first BUY print on the
same token at [0.95,0.98) at least 10 s later (block times). One 10 USD trade per market."""
import gzip, json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
D = Path("/home/user/polymarket-lab/data/gaps_resolution_bonds/audit_1h"); OUT = Path(__file__).resolve().parent
J = lambda v: json.loads(v) if isinstance(v, str) else v
def T(s):
    s = str(s).replace(" ", "T").replace("Z", "+00:00")
    if s.endswith("+00"): s += ":00"
    return datetime.fromisoformat(s).timestamp()
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h
def tstat(v):
    n = len(v); m = sum(v) / n; s = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1)); return m, m / (s / math.sqrt(n))
G = []
for m in json.load(open(D / "markets.json")):
    d = json.load(gzip.open(D / f"{m['conditionId']}.json.gz", "rt"))
    op = [float(x) for x in J(m["outcomePrices"])]; toks = J(m["clobTokenIds"])
    end, closed = T(m["endDate"]), T(m["closedTime"])
    rows = sorted(r for r in d["rows"] if r[1] == "BUY" and end - 3600 <= r[0] < closed and 0.95 - 1e-9 <= r[3] < 0.98 - 1e-9)
    if not rows: continue
    t0, tok = rows[0][0], rows[0][2]
    f = next((r for r in rows if r[2] == tok and r[0] >= t0 + 10), None)
    if not f: continue
    pay = op[toks.index(tok)]; c = f[3] + 0.01 * f[3] * (1 - f[3])
    G.append((m["slug"], pay, 10 * (pay - c) / c, c, datetime.fromtimestamp(end, tz=timezone.utc).weekday() >= 5))
k = sum(x[1] < 1 for x in G); lo, hi = wil(k, len(G)); mm, t = tstat([x[2] for x in G])
L = [f"tape-trigger rule, btc+eth 1h 18-26 Nov: {len(G)} trades, lost {k} ({100*k/len(G):.2f}%, Wilson {100*lo:.1f}-{100*hi:.1f}), "
     f"break-even {100*(1-sum(x[3] for x in G)/len(G)):.2f}%, net per 10 USD {mm:+.3f} (t {t:+.1f})"]
for nm, sel in (("weekend", [x for x in G if x[4]]), ("weekday", [x for x in G if not x[4]])):
    k = sum(x[1] < 1 for x in sel); mm, t = tstat([x[2] for x in sel])
    L.append(f"  {nm}: {len(sel)} trades, lost {k}, net per 10 USD {mm:+.3f} (t {t:+.1f})")
print("\n".join(L)); (OUT / "a9_out.txt").write_text("\n".join(L) + "\n")

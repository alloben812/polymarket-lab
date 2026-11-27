"""Audit a8: crypto markets with NO 5-minute entry whose eventual loser reached a mid >= 0.85 in the last hour
(a3 list). Did a taker buy the eventual LOSER at [0.95,0.98) in [endDate-1h, close)? Such a market would have been
bought by a live poller that watches the book, but not by the 5-minute-snapshot backtest."""
import gzip, json, pickle, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import dataapi
D = Path("/home/user/polymarket-lab/data/gaps_resolution_bonds"); OUT = Path(__file__).resolve().parent
uni = {m["conditionId"]: m for m in (json.loads(l) for l in gzip.open(D / "universe.jsonl.gz", "rt"))}
res = json.load(open(D / "resolutions.json")); res.update(json.load(open(D / "ext/resolutions.json")))
cand = pickle.load(open(OUT / "a3_noentry_losers.pkl", "rb"))
hit = 0; lines = []
for x in cand:
    m = uni[x["cid"]]
    p = D / "tapes" / f"{x['cid']}.json.gz"
    if not p.exists(): p = D / "audit_1h" / f"missed_{x['cid']}.json.gz"
    if p.exists():
        rows = json.load(gzip.open(p, "rt"))["rows"]
    else:
        rows = [[r["timestamp"], r["side"], r["token_id"], r["price"], r["size"], r["proxy_wallet"]] for r in dataapi.iter_trades(condition=x["cid"], max_rows=60000)]
        json.dump({"cid": x["cid"], "capped": len(rows) >= 60000, "rows": rows}, gzip.open(p, "wt"))
    fin = res[x["cid"]]["final"]
    k = [i for i, o in enumerate(m["outcomes"]) if fin.get(o) < 1][0]
    tok = m["clobTokenIds"][k]
    b = [(r[0], r[3], r[4]) for r in rows if r[1] == "BUY" and r[2] == tok and x["end"] - 3600 <= r[0] < x["closed"] and 0.95 - 1e-9 <= r[3] < 0.98 - 1e-9]
    if b:
        hit += 1
        lines.append(f"  {x['slug']}: {len(b)} buys of the loser at 0.95-0.98, {sum(p*s for _, p, s in b):.0f} USD, first at {min(b)[1]:.3f}")
print(f"no-entry crypto markets whose loser had mid >= 0.85: {len(cand)}; with a taker buy of the loser at 0.95-0.98: {hit}")
print("\n".join(lines))
(OUT / "a8_out.txt").write_text(f"{len(cand)} {hit}\n" + "\n".join(lines) + "\n")

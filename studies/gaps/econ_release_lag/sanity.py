"""Step 4: sanity slice on one release (default US CPI of 2026-09-11)."""
import sys, collections
from pmlab import fees
import lib
rel = sys.argv[1] if len(sys.argv) > 1 else "US-CPI-august"
ms = [m for m in lib.markets() if (rel == "ALL" or m["release"] == rel)]
print("markets", len(ms), "winner Yes:", sum(m["winner"] == "Yes" for m in ms))
print("fee check: 100 shares at 0.50, rate 0.01 ->", fees.taker_fee(100, 0.5, 0.01), "(expected 0.25); at 0.97 ->", fees.taker_fee(100, 0.97, 0.01), "(expected 0.0291)")
k = n = 0; usd_w = usd = 0.0
pre = post = 0; mn = 10**12; mx = -10**12; miss = 0
bymk = collections.Counter()
for m in ms:
    rows, d = lib.tape(m)
    if rows is None:
        miss += 1; continue
    for r in rows:
        mn = min(mn, r["off"]); mx = max(mx, r["off"])
        if r["off"] < -60:
            pre += 1
            # token the TAKER ended up long: BUY -> the printed token at p ; SELL -> the other token at 1-p
            price = r["p"] if r["side"] == "BUY" else 1 - r["p"]
            tok_wins = (r["o"] == m["winner"]) if r["side"] == "BUY" else (r["o"] != m["winner"])
            if 0.40 <= price <= 0.60:
                n += 1; k += tok_wins; usd += r["z"] * price; usd_w += r["z"] * price * tok_wins; bymk[m["cond"]] += 1
        elif r["off"] >= 0:
            post += 1
    if d["status"] == "cap": print("CAP", m["slug"])
print(f"tapes missing {miss}; prints before T-60s {pre}, after T {post}; offsets from {mn/3600:.1f} h to {mx/3600:.1f} h")
print(f"taker positions opened at 0.40-0.60 before the release: {n} prints in {len(bymk)} markets, won {k} = {k/max(n,1):.3f}; dollar-weighted {usd_w/max(usd,1e-9):.3f}")

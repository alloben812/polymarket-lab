"""Market stories for the up/down accounts: 10 markets each, evenly spaced through 2026-11-21..26 (not hand-picked)."""
import json, collections, sys, datetime as dt
import ud
fmt = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
for name in ("0x50f7", "tiredofwinning2much", "mo-money", "0x0dbd0e1d"):
    rows = json.load(open(ud.HERE / "out" / f"ud_{name}.json"))
    bym = collections.defaultdict(list)
    for r in rows: bym[r["slug"]].append(r)
    cand = sorted([s for s, v in bym.items() if sum(x["size"] * x["price"] for x in v) >= (200 if name == "0x50f7" else 20)], key=lambda s: int(s.rsplit("-", 1)[1]))
    pick = cand[5::max(1, len(cand) // 10)][:10]
    print(f"\n===== {name}: {len(pick)} of {len(cand)} markets")
    for s in pick:
        v = sorted(bym[s], key=lambda r: r["tm"]); t0 = int(s.rsplit("-", 1)[1]); dur = 300 if "-5m-" in s else 900
        won = next((("Up" if (r["final"] == 1) == (r["outcome"] == "Up") else "Down") for r in v if r["final"] is not None), "?")
        pnl = sum(r["size"] * ((r["final"] or 0) - r["price"]) * (1 if r["side"] == "BUY" else -1) - r["fee"] for r in v)
        print(f"{s}  window {fmt(t0)} +{dur}s  winner {won}  fills {len(v)}  pnl {pnl:+.2f}")
        for o in ("Up", "Down"):
            w = [r for r in v if r["outcome"] == o and r["side"] == "BUY"]
            if not w: continue
            sh = sum(r["size"] for r in w); avg = sum(r["size"] * r["price"] for r in w) / sh
            f0, f1 = w[0], w[-1]
            print(f"     BUY {o:4} {sh:8.0f} sh @ {avg:.3f}  ({sum(r['role']=='T' for r in w)} taker/{len(w)} fills)  first at {dur-f0['left']:4}s into window: px {f0['price']:.3f}, spot gap {f0['gap_bp']:+6.1f}bp, fair {f0['fair']:.2f} | last at {dur-f1['left']:4}s: px {f1['price']:.3f}, gap {f1['gap_bp']:+6.1f}bp, fair {f1['fair']:.2f}")
        sl = [r for r in v if r["side"] == "SELL"]
        if sl: print(f"     SELLS {len(sl)} fills, {sum(r['size'] for r in sl):.0f} sh @ {sum(r['size']*r['price'] for r in sl)/sum(r['size'] for r in sl):.3f}")

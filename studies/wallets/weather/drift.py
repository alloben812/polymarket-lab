"""Does the market move toward the account's side before the local day starts?  Mark each pre-day fill at the YES price at local midnight."""
import json, bisect, collections, sys
F = json.load(open("out/fills.json")); MK = json.load(open("out/mk.json")); PX = json.load(open("out/px.json"))
for acct in ["WrongBy1Degree", "OnlyLuckNoBrain"]:
    ev = collections.Counter(); ev_fin = collections.Counter(); cost = 0.0; n = 0
    for r in F[acct]:
        d = MK.get(r["condition_id"]); pts = PX.get(r["condition_id"])
        if not d or not pts or not d["ok"] or r["timestamp"] >= d["est"] - 3600 or r["side"] != "BUY": continue
        ts = [p[0] for p in pts]; i = bisect.bisect_right(ts, d["est"]) - 1
        if i < 0 or d["est"] - ts[i] > 6 * 3600: continue
        y0 = pts[i][1]; p = float(r["price"]); sh = float(r["size"])
        mark = y0 if r["outcome"] == "Yes" else 1 - y0
        ev[d["event"]] += sh * (mark - p); ev_fin[d["event"]] += sh * (float(d["final"][r["outcome"]]) - p); cost += sh * p; n += 1
    v = list(ev.values()); m = len(v); mu = sum(v) / m; se = (sum((x - mu) ** 2 for x in v) / (m - 1) / m) ** 0.5
    print(f"{acct}: {n} pre-day buys, cost ${cost:.0f}: marked at local midnight (mid, no fees) ${sum(v):+.0f} ({100*sum(v)/cost:+.1f}%, t by event {mu/se:.2f}); same fills at settlement ${sum(ev_fin.values()):+.0f} ({100*sum(ev_fin.values())/cost:+.1f}%)")

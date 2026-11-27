"""Step 6: E1-E4 per (release, market). Definitions in protocol.md section 5. Output: data/gaps_econ/measures.json"""
import json, collections
import lib

# Section 4 verdicts. Automatic result from confirm_times.py, then the written investigation (results.md):
# the four "move early" cases are single 5-10 share prints inside the last minute, the trading burst starts at 0..+6 s
# (AR-CPI-oct at +39 s, with a >= 0.10 move there) -> kept at the official/scheduled time.
conf = json.load(open(f"{lib.D}/confirm.json"))
INVESTIGATED_KEEP = {"US-EMP-august", "US-CPI-august", "US-PCE-august", "US-ISMM-october", "AR-CPI-oct"}
status = {}
for rel, c in conf.items():
    a = c["auto"]
    if a.startswith("confirmed"):
        status[rel] = a
    elif a.startswith("investigate") and rel in INVESTIGATED_KEEP:
        status[rel] = "kept after investigation (noise print before T)"
    elif c["tier"] == "A":
        status[rel] = "tier A unconfirmed (kept, flagged)"
    else:
        status[rel] = "DROPPED: tier B time not confirmed by the tape"
json.dump(status, open(f"{lib.D}/release_status.json", "w"), indent=1)

BUCKETS = [(0, 5, "0-5s"), (5, 30, "5-30s"), (30, 120, "30s-2m"), (120, 600, "2-10m"), (600, 10**9, "later")]
DELAYS = [5, 30, 120, 600]
out = []
for m in lib.markets():
    if status[m["release"]].startswith("DROPPED"):
        continue
    rows, d = lib.tape(m)
    rec = {k: m[k] for k in ("release", "type", "group", "tier", "T", "when", "event", "slug", "cond", "title", "vol", "winner", "flag", "closed_ts")}
    rec["status"] = status[m["release"]]
    pre = [r for r in rows if r["off"] < 0]
    post = [r for r in rows if r["off"] >= 0]
    rec["n_pre"], rec["n_post"] = len(pre), len(post)
    rec["e1"] = pre[-1]["wp"] if pre else None
    rec["e1_age"] = -pre[-1]["off"] if pre else None
    rec["e2"] = {}
    for lvl in (0.90, 0.95, 0.99):
        t = next((r["off"] for r in post if r["wp"] >= lvl - 1e-9), None)
        rec["e2"][str(lvl)] = t
    e3 = {"a": {b[2]: [0.0, 0.0] for b in BUCKETS}, "b": {b[2]: [0.0, 0.0] for b in BUCKETS}}
    wal = collections.defaultdict(float)
    for r in post:
        if r["wp"] < 0.95 - 1e-9:
            kind = "a" if r["buyable"] else "b"
            b = next(name for lo, hi, name in BUCKETS if lo <= r["off"] < hi)
            e3[kind][b][0] += r["z"] * r["p"]            # dollars that changed hands in the traded token
            e3[kind][b][1] += r["z"] * (1.0 - r["wp"])   # gap dollars
            if kind == "a":
                wal[r["w"]] += r["z"] * (1.0 - r["wp"])
    rec["e3"] = e3
    rec["e3_wallets"] = dict(wal)
    rec["e4"] = {}
    for dly in DELAYS:
        budget = 500.0; sh = cost = fee = 0.0; n = 0; first = last = None
        for r in post:
            if r["off"] < dly or not r["buyable"] or r["wp"] > 0.97 + 1e-9:
                continue
            q = min(r["z"], budget / r["wp"])
            if q <= 1e-9:
                break
            sh += q; cost += q * r["wp"]; fee += lib.FEE * r["wp"] * (1 - r["wp"]) * q; budget -= q * r["wp"]; n += 1
            first = r["off"] if first is None else first; last = r["off"]
        rec["e4"][str(dly)] = {"shares": sh, "cost": cost, "fee": fee, "net": sh - cost - fee, "n": n, "first": first, "last": last}
    out.append(rec)
json.dump(out, open(f"{lib.D}/measures.json", "w"))
import collections as c
print("markets measured", len(out), "releases", len({r['release'] for r in out}), "release seconds", len({r['T'] for r in out}))
print(c.Counter(status.values()))
for dly in DELAYS:
    print(dly, "net", round(sum(r["e4"][str(dly)]["net"] for r in out), 2), "cost", round(sum(r["e4"][str(dly)]["cost"] for r in out), 2),
          "markets with fills", sum(1 for r in out if r["e4"][str(dly)]["n"]))

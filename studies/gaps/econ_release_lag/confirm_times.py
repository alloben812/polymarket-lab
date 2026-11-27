"""Step 5: confirm each scheduled time against the tape (protocol section 4). Uses Yes-prices only, no winner information."""
import json, collections
import lib

ms = lib.markets()
by = collections.defaultdict(list)
for m in ms:
    by[m["release"]].append(m)
out = {}
print(f"{'release':<19}{'when (UTC)':<17}{'tier':<5}{'mk':>3} {'move_off':>9} {'in market':<28} {'busiest60s':>10} {'n±1h':>6}  verdict")
for rel, lst in sorted(by.items(), key=lambda kv: kv[1][0]["T"]):
    best = None; offs = []
    for m in lst:
        rows, d = lib.tape(m)
        if rows is None:
            continue
        ref = None
        for r in rows:
            if r["off"] < -60:
                ref = r["yes"]
            else:
                break
        if ref is not None:
            for r in rows:
                if r["off"] >= -60 and abs(r["yes"] - ref) >= 0.10:
                    if best is None or r["off"] < best[0]:
                        best = (r["off"], m["title"], ref, r["yes"])
                    break
        offs += [r["off"] for r in rows if -3600 <= r["off"] <= 3600]
    offs.sort()
    busy = None; j = 0; bestn = 0
    for i, o in enumerate(offs):  # busiest 60-second window starting at a print
        while j < len(offs) and offs[j] < o + 60:
            j += 1
        if j - i > bestn:
            bestn, busy = j - i, o
    mv = best[0] if best else None
    if mv is not None and -5 <= mv <= 60:
        v = "confirmed"
    elif mv is None:
        v = "confirmed (activity)" if busy is not None and -5 <= busy <= 60 else "unconfirmed: no move"
    else:
        v = "investigate: move early" if mv < -5 else "investigate: move late"
    m0 = lst[0]
    out[rel] = {"move_off": mv, "move_market": best[1] if best else None, "ref": best[2] if best else None, "to": best[3] if best else None,
                "busiest": busy, "busiest_n": bestn, "n_1h": len(offs), "auto": v, "tier": m0["tier"], "T": m0["T"], "when": m0["when"], "type": m0["type"]}
    print(f"{rel:<19}{m0['when']:<17}{m0['tier']:<5}{len(lst):>3} {str(mv):>9} {str(best[1] if best else '-')[:20]:<20}{(f'{best[2]:.2f}>{best[3]:.2f}' if best else ''):<9}{str(busy):>10} {len(offs):>6}  {v}")
json.dump(out, open(f"{lib.D}/confirm.json", "w"), indent=1)
import collections as c
print(c.Counter(v["auto"] for v in out.values()))

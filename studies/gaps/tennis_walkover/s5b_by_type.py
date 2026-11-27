"""Diagnostic after s5 (not a new rule): split the class A 'all markets' result of each delay by market type, using the
same fills (run_rule over all markets, then each fill attributed to its market's type). Also: the
'tennis_completed_match' market (Yes = match completed) resolves No = 1.0 on a walkover, so it is reported apart."""
import collections, json
from pmlab import updown
from common import *


def main():
    U = json.load(open(DATA / "universe.json"))
    EA = {o["slug"]: o for o in json.load(open(OUT / "events_A.json"))}
    for d in DELAYS:
        by = collections.defaultdict(lambda: [0.0, 0.0, 0.0, set()])  # cost+fee, payoff, shares, events
        for r in U["A"]:
            t0 = EA[r["slug"]].get("t_first")
            if t0 is None:
                continue
            ms = [m for m in r["markets"] if m.get("vol") and m.get("api_final")]
            streams = []
            for m in ms:
                pr = prints(updown.tape(m["cid"]), m["outcomes"])
                streams.append((pr, (float(m["api_final"][0]), float(m["api_final"][1]))))
            x = run_rule(streams, [t0 + d])
            for t, k, p, q, w in x["fills"]:
                m = ms[k]
                pr, fin = streams[k]
                # recover which outcome: the fill came from a print with this price; payoff via run_rule's bo is not kept,
                # so recompute from the matching print
                bo = next(y["bo"] for y in pr if y["t"] == t and abs(y["bp"] - p) < 1e-12)
                b = by[m["type"]]
                b[0] += q * (p + fee_ps(p))
                b[1] += q * fin[bo]
                b[2] += q
                b[3].add(r["slug"])
        print(f"d={d}s: type | events | shares | cost incl. fee | payoff | net")
        for ty, (c, pay, sh, ev) in sorted(by.items(), key=lambda kv: -kv[1][0]):
            print(f"   {ty} | {len(ev)} | {sh:,.0f} | {c:,.0f} | {pay:,.0f} | {pay - c:,.0f}")


if __name__ == "__main__":
    main()

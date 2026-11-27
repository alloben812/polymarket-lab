"""Step 3: download whole-market tapes (cached by pmlab.updown.tape in data/tape/).

Class A and B: every market of the event with a non-null, positive volumeNum (a null volumeNum means no trades;
checked on a sample by `--check-null`). Controls: the sampled moneylines."""
import json, sys, time
from pmlab import updown
from common import *


def main():
    U = json.load(open(DATA / "universe.json"))
    todo = []
    for cls in ("A", "B"):
        for r in U[cls]:
            for m in r["markets"]:
                if m["vol"]:
                    todo.append(m["cid"])
    if "--no-control" not in sys.argv:
        todo += [c["cid"] for c in U["control"]]
    todo = list(dict.fromkeys(todo))
    print("tapes to have:", len(todo), flush=True)
    t0 = time.time()
    rows = 0
    for i, cid in enumerate(todo):
        try:
            rows += len(updown.tape(cid))
        except Exception as e:  # noqa: BLE001
            print("FAILED", cid, e, flush=True)
        if i % 250 == 0:
            print(i, rows, round(time.time() - t0), flush=True)
    print("done", len(todo), rows, flush=True)
    if "--check-null" in sys.argv:
        nulls = [m["cid"] for r in U["A"] for m in r["markets"] if not m["vol"]][:40]
        print("null-volume markets checked:", len(nulls), "with any trade:", sum(1 for c in nulls if updown.tape(c, cache=False)))


if __name__ == "__main__":
    main()

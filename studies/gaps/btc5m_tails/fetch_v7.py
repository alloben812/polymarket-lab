"""Vega7 fills for the study period + official metadata of the off-grid windows it traded. Sequential. No statistics."""
import json
import time

from common import DATA, END, START, VEGA7
from pmlab import updown, wallet


def main() -> None:
    path = DATA / "vega7_fills.json"
    if path.exists():
        fills = json.loads(path.read_text())
    else:
        fills, truncated = wallet.fetch_fills(VEGA7, START, END)
        print("fills", len(fills), "truncated", truncated, flush=True)
        path.write_text(json.dumps(fills))
    t0s = sorted({int(f["slug"].rsplit("-", 1)[1]) for f in fills if (f.get("slug") or "").startswith("btc-updown-5m-")})
    t0s = [t for t in t0s if START <= t < END]
    print("btc 5m windows traded", len(t0s), "of which on the grid", sum(1 for t in t0s if t % 1200 == 0), flush=True)
    meta, bad = {}, 0
    t_start = time.time()
    for i, t0 in enumerate(t0s):
        try:
            m = updown.load_market("btc", "5m", t0)
        except Exception as e:  # noqa: BLE001
            m = None
            print("error", t0, repr(e)[:100], flush=True)
        if m is None or m.get("up_won") is None:
            bad += 1
            continue
        meta[t0] = {"up_won": bool(m["up_won"]), "ptb": m.get("price_to_beat"), "final": m.get("final_price"), "condition": m.get("condition")}
        if i % 300 == 0:
            print(i, len(t0s), f"{time.time() - t_start:.0f}s", flush=True)
    (DATA / "vega7_meta.json").write_text(json.dumps(meta))
    print("meta", len(meta), "unresolved or missing", bad, "done", flush=True)


if __name__ == "__main__":
    main()

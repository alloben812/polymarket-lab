"""Shared loaders for the release-lag study."""
import gzip, json, os

D = "/home/user/polymarket-lab/data/gaps_econ"
LAG = 3  # block time - match time, seconds (NOTES.md)
FEE = 0.01


def markets():
    return json.load(open(f"{D}/markets.json"))["markets"]


def tape(m):
    """Prints oldest first: dicts with off (match time - T), side, oi (outcome index), o (outcome name), p, z, w,
    wp (winner price of the print), buyable (winner could be BOUGHT at wp for z shares), kind 'a' taker-informed / 'b' maker-informed."""
    path = f"{D}/tapes/{m['cond']}.json.gz"
    if not os.path.exists(path):
        return None, None
    d = json.load(gzip.open(path))
    out = []
    for ts, side, oi, o, p, z, w in d["rows"]:
        if o not in ("Yes", "No"):
            o = "Yes" if oi == 0 else "No"
        is_w = (o == m["winner"])
        wp = p if is_w else 1.0 - p
        buyable = (side == "BUY" and is_w) or (side == "SELL" and not is_w)
        out.append({"off": ts - LAG - m["T"], "ts": ts, "side": side, "o": o, "p": p, "z": z, "w": w or "unknown", "wp": wp,
                    "yes": p if o == "Yes" else 1.0 - p, "buyable": buyable})
    out.sort(key=lambda r: r["ts"])
    return out, d

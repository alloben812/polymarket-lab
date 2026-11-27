"""Shared: family classification of the gamma universe (protocol, Data 2) and token maps."""
import json, re
from pmlab.fees import CURRENT

D = "/home/user/polymarket-lab/data/gaps_negrisk"
ABOVE = re.compile(r"above \$?([\d,]+(?:\.\d+)?)", re.I)


def jl(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return None
    return v


def rate_of(m, ev):
    fs = m.get("feeSchedule") or {}
    if isinstance(fs, dict) and fs.get("rate") is not None:
        return float(fs["rate"])
    ft = (m.get("feeType") or "")
    if ft == "zero_fees":
        return 0.0
    tags = set(ev.get("tags") or [])
    if "weather" in tags: return CURRENT["weather"]
    if "geopolitics" in tags: return CURRENT["geopolitics"]
    if "crypto" in tags: return CURRENT["crypto_other"]
    if "sports" in tags: return CURRENT["sports"]
    return CURRENT["other"]


def families():
    U = json.load(open(f"{D}/universe.json"))
    fam = {"B": [], "C1": [], "C2": []}
    for e in U:
        ms = [m for m in e["markets"] if m.get("conditionId") and jl(m.get("clobTokenIds"))]
        for m in ms:
            t = jl(m["clobTokenIds"]); m["yes"], m["no"] = str(t[0]), str(t[1]); m["rate"] = rate_of(m, e)
        e["markets"] = ms
        if e.get("negRisk") and len(ms) >= 2:
            fam["B"].append(e)
        elif "multi-strikes" in (e.get("tags") or []) and len(ms) >= 2:
            ks = []
            for m in ms:
                g = ABOVE.search(m.get("question") or "")
                ks.append(float(g.group(1).replace(",", "")) if g else None)
            if all(k is not None for k in ks) and len(set(ks)) == len(ks):
                for m, k in zip(ms, ks): m["K"] = k
                fam["C1"].append(e)
        elif not e.get("negRisk") and len(ms) >= 3 and all(" by " in (m.get("question") or "").lower() for m in ms):
            ds = [m.get("endDate") for m in ms]
            if all(ds) and len(set(ds)) == len(ds):
                fam["C2"].append(e)
    return fam

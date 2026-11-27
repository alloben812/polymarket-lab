"""Step 1: wallet pool and early-window selection (protocol.md, 'Wallet pool and selection rule')."""
import glob
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pmlab.http import get_json

D = "https://data-api.polymarket.com/v2"
ROOT = Path("/home/user/polymarket-lab")
OUT = ROOT / "studies/gaps/copy_trading/out"
CACHE = ROOT / "data/gaps_copy"
E0, E1 = 1794009600, 1795219200
CATS = ["crypto", "sports", "politics", "weather", "economics", "mentions", "culture", "tech", "finance", "esports"]
ADDR = re.compile(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
REB = ["maker_rebate", "taker_rebate", "reward_income", "sponsored_income", "referral_income"]


def boards():
    out = {}
    for c in CATS:
        d = get_json(f"{D}/leaderboard", {"category": c, "time_period": "month", "sort_by": "PNL", "limit": 25})
        out[c] = [(r["user_id"].lower(), r.get("user_name")) for r in d.get("data") or []]
    return out


def other_sources():
    s = set(a.lower() for a in ADDR.findall((ROOT / "catalog/raw/x1_wallets.md").read_text()))
    for f in glob.glob(str(ROOT / "studies/wallets/*/README.md")):
        s |= set(a.lower() for a in ADDR.findall(Path(f).read_text(errors="ignore")))
    # deviation 1 (results.md): only the SUBJECT wallet of each per-wallet json, not every address inside it
    for f in glob.glob(str(ROOT / "studies/wallets/*/*.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if isinstance(d, dict):
            for v in (d.get("wallet"), (d.get("account") or {}).get("wallet") if isinstance(d.get("account"), dict) else None):
                if isinstance(v, str) and ADDR.fullmatch(v):
                    s.add(v.lower())
    return s


def at(points, ts):
    best = None
    for p in points:
        if p["timestamp"] <= ts:
            best = p
    return best


def metric(w):
    try:
        d = get_json(f"{D}/user-pnl", {"user": w, "interval": "all", "fidelity": "1d"}, cache=False).get("data") or {}
    except Exception as e:
        return w, None
    pts = sorted(d.get("points") or [], key=lambda p: p["timestamp"])
    a, b = at(pts, E0), at(pts, E1)
    if not a or not b:
        return w, {"metric": None}

    def trading(p):
        return (p.get("economic_pnl") or 0) - sum((p.get(k) or 0) for k in REB)

    return w, {"metric": trading(b) - trading(a), "econ": (b.get("economic_pnl") or 0) - (a.get("economic_pnl") or 0),
               "trades": (b.get("trade_count") or 0) - (a.get("trade_count") or 0), "a_ts": a["timestamp"], "b_ts": b["timestamp"]}


def main():
    bd = boards()
    names = {w: n for c in bd for w, n in bd[c]}
    others = other_sources()
    pool = set(names) | others
    print("pool", len(pool), "boards", len(names), "others", len(others))
    with ThreadPoolExecutor(4) as ex:
        m = dict(ex.map(metric, sorted(pool)))
    json.dump({"boards": bd, "others": sorted(others), "metric": m}, open(CACHE / "pool.json", "w"))

    def ok(w):
        x = m.get(w)
        return bool(x) and x.get("metric") is not None and x["metric"] > 0 and x["trades"] >= 30

    chosen = []
    src = {}
    for c in CATS:
        cand = sorted([w for w, _ in bd[c] if ok(w) and w not in chosen], key=lambda w: -m[w]["metric"])[:3]
        for w in cand:
            chosen.append(w)
            src[w] = "board:" + c
    cand = sorted([w for w in others if ok(w) and w not in chosen], key=lambda w: -m[w]["metric"])[:6]
    for w in cand:
        chosen.append(w)
        src[w] = "x1/studies"
    sel = [{"wallet": w, "name": names.get(w), "source": src[w], **m[w]} for w in chosen]
    json.dump(sel, open(OUT / "selected.json", "w"), indent=1)
    elig = sum(1 for w in pool if ok(w))
    print("eligible", elig, "chosen", len(sel))
    for s in sel:
        print(f"{s['source']:18s} {str(s['name'])[:22]:22s} {s['wallet']} metric {s['metric']:12.0f} trades {s['trades']}")


if __name__ == "__main__":
    main()

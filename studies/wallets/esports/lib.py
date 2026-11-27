"""Helpers for the esports wallet study: cached fills, market metadata, whole-market tapes, OpenDota matches."""
import gzip, json, os, time, datetime as dt, collections, re, bisect
from pmlab import wallet as W, dataapi, gamma, http

HERE = os.path.dirname(os.path.abspath(__file__))
END = 1795796820      # 2026-11-27 16:27 UTC, the end of the pmlab.wallet window
DAYS = 14
WALLETS = {
    "RITALINEWITHSNUS": "0x9d910a16612ac0b6c2d54e7061ac8d4d0a9d6816",
    "DamwonChampions2027": "0x3471a897e56a8d3621ca79af87dae4325977f17e",
    "calculate10": "0xb35f674af4603c9602dfbf39564087e94897cf4c",
    "gojda": "0xd2bb94594762beda042e596598800d83f781bd8e",
    "iii252": "0xed446954680979932092e970b443e6ae61e34f76",
    "lonmi2511": "0x997cb45c25e94b4ee58c234ce1f211496a0d51f3",
    "BLASTSLAM9WINNER": "0x77d9009e5e22d8b7187530c862dd058949b906ed",
}
ts = W._ts
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S") if t else "-"

def fills(name, days=DAYS, max_fills=60000):
    p = f"{HERE}/fills/{name}_{days}d.json.gz"
    if os.path.exists(p): return json.load(gzip.open(p, "rt"))
    f, trunc = W.fetch_fills(WALLETS[name], END - int(days*86400), END, max_fills)
    for r in f: r["size"] = float(r["size"]); r["price"] = float(r["price"])
    f.sort(key=lambda r: r["timestamp"])
    json.dump(f, gzip.open(p, "wt")); print(name, "fills", len(f), "truncated", trunc)
    return f

def inv(name, days=DAYS):
    p = f"{HERE}/fills/{name}_{days}d_inv.json.gz"
    if os.path.exists(p): return json.load(gzip.open(p, "rt"))
    r = W.fetch_inventory_events(WALLETS[name], END - int(days*86400), END)
    json.dump(r, gzip.open(p, "wt")); return r

def meta(conds): return gamma.markets_by_condition(sorted(set(conds)), cache=True)
def resol(conds): return dataapi.resolutions(sorted(set(conds)), cache=True)

def tape(cond):
    p = f"{HERE}/fills/tape_{cond[:14]}.json.gz"
    if os.path.exists(p): return json.load(gzip.open(p, "rt"))
    keep = ("side", "token_id", "size", "price", "timestamp", "outcome", "proxy_wallet", "transaction_hash")
    rows = [{k: r.get(k) for k in keep} for r in dataapi.iter_trades(condition=cond)]
    for r in rows: r["size"] = float(r["size"]); r["price"] = float(r["price"])
    rows.sort(key=lambda r: r["timestamp"])
    json.dump(rows, gzip.open(p, "wt")); return rows

def mtype(m):
    """series (match winner) / map (game N winner) / other, from gamma fields."""
    t = (m.get("sportsMarketType") or "").lower(); q = (m.get("question") or "").lower()
    if t: return t
    if re.search(r"(game|map) \d", q): return "child_moneyline"
    return "moneyline"

def game(m):
    s = (m.get("slug") or "").split("-")[0]
    return s

class Path:
    """Price path of outcome 0 of a binary market built from the whole tape (taker rows)."""
    def __init__(self, rows, tok0):
        self.t = []; self.p = []
        for r in rows:
            p = r["price"] if r["token_id"] == tok0 else 1 - r["price"]
            self.t.append(r["timestamp"]); self.p.append(p)
    def at(self, t):
        """last print at or before t (None before the first)."""
        i = bisect.bisect_right(self.t, t) - 1
        return self.p[i] if i >= 0 else None
    def first_at_or_after(self, t):
        i = bisect.bisect_left(self.t, t)
        return (self.t[i], self.p[i]) if i < len(self.t) else None

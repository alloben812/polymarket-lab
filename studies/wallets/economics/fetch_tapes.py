"""Download whole-market tapes for scheduled-release events (Sep-Nov 2026). Compact rows -> data/econ_tapes/<cond>.json
Row: [ts, wallet, side, outcome_index, price, size, name]."""
import json, re, sys, os, calendar, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import dataapi
OUT = "/home/user/polymarket-lab/data/econ_tapes"
ev = json.load(open("events_sep_nov.json"))
PAT = re.compile(r"^(fed-decision-in-(september|october)|(august|september|october)-inflation-us-(annual|monthly)|core-cpi-(mom|yoy)-(august|september|october)|how-many-jobs-added|(august|september|october)-unemployment-rate|us-gdp-growth-in-q3|core-pce-(yoy|mom)|ppi-yoy|ism-(services|manufacturing)|ecb-interest-rates|bank-of-england-decision|bank-of-canada-decision|bank-of-japan-decision|reserve-bank-of-australia-decision|bank-of-mexico-decision|canada-gdp|uk-gdp|eurozone-gdp|germany-gdp|october-inflation-uk|inflation-uk)")
sel = [e for e in ev if PAT.search(e["slug"])]
jobs = [(e["slug"], m) for e in sel for m in e["markets"] if m.get("cond")]
print(len(sel), "events", len(jobs), "markets", file=sys.stderr)
def ts(s):
    return calendar.timegm(time.strptime(s[:19].replace(" ", "T"), "%Y-%m-%dT%H:%M:%S")) if s else None
def fetch(job):
    slug, m = job
    path = f"{OUT}/{m['cond']}.json"
    if os.path.exists(path):
        return 0
    big = slug.startswith("fed-decision")
    floor = None
    if big:  # huge tapes: keep from 3 days before the scheduled end of the meeting day only
        floor = ts(m["end"]) - 4 * 86400
    rows = []
    for r in dataapi.iter_trades(condition=m["cond"], max_rows=400000 if big else 60000):
        if floor and r["timestamp"] < floor:
            break
        rows.append([r["timestamp"], r["proxy_wallet"], r["side"], r.get("outcome_index"), float(r["price"]), float(r["size"]), r.get("name") or r.get("pseudonym") or ""])
    json.dump(rows, open(path, "w"))
    return len(rows)
t0 = time.time()
with ThreadPoolExecutor(8) as ex:
    ns = list(ex.map(fetch, jobs))
print("rows", sum(ns), "in", round(time.time() - t0), "s", file=sys.stderr)
json.dump([{"slug": e["slug"], "end": e["end"], "volume": e["volume"], "markets": e["markets"]} for e in sel], open("release_events.json", "w"))

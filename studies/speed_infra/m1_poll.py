"""m1: how fresh are free public endpoints when polled from this sandbox (US IP)?

For each source, poll at a fixed cadence for DURATION seconds and record per poll:
local send time, local receive time, the source's own event timestamp (if any), a content hash.
Output: studies/speed_infra/out/m1_<source>.jsonl. Analysis in m1_report.py.
Public endpoints only, no keys. Run: python3 -I m1_poll.py <source> <duration_s> <interval_s>
"""
import hashlib, json, os, sys, time, urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "pm-research/0.1 (public data study)"}


def get(url, timeout=10):
    t0 = time.time()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        hdr = dict(r.headers)
    t1 = time.time()
    return t0, t1, body, hdr


def ev_binance(body):  # /api/v3/trades?limit=1 -> last trade time ms
    return json.loads(body)[-1]["time"] / 1000


def ev_coinbase(body):  # /products/BTC-USD/ticker -> ISO time of last trade
    import datetime as dt
    s = json.loads(body)["time"]
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def ev_binance_time(body):
    return json.loads(body)["serverTime"] / 1000


def ev_pmbook(body):
    return int(json.loads(body)["timestamp"]) / 1000


def ev_none(body):
    return None


SOURCES = {
    "binance_trades": ("https://data-api.binance.vision/api/v3/trades?symbol=BTCUSDT&limit=1", ev_binance),
    "binance_time": ("https://data-api.binance.vision/api/v3/time", ev_binance_time),
    "coinbase_ticker": ("https://api.exchange.coinbase.com/products/BTC-USD/ticker", ev_coinbase),
    "espn_nba": ("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard", ev_none),
    "espn_ncaab": ("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard", ev_none),
    "espn_soccer": ("https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard", ev_none),
    "espn_nhl": ("https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard", ev_none),
    "espn_cfb": ("https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard", ev_none),
}


def main():
    src, dur, iv = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    url = sys.argv[4] if len(sys.argv) > 4 else SOURCES[src][0]
    ev = SOURCES[src][1] if src in SOURCES else ev_pmbook if src.startswith("pmbook") else ev_none
    path = os.path.join(OUT, f"m1_{src}.jsonl")
    end = time.time() + dur
    with open(path, "a") as f:
        while time.time() < end:
            nxt = time.time() + iv
            try:
                t0, t1, body, hdr = get(url)
                rec = {"t0": t0, "t1": t1, "ev": ev(body), "h": hashlib.sha1(body).hexdigest()[:12],
                       "len": len(body), "age": hdr.get("Age"), "cc": hdr.get("Cache-Control"),
                       "date": hdr.get("Date"), "xcache": hdr.get("X-Cache") or hdr.get("x-cache")}
                if src.startswith("espn"):
                    # keep a compact score signature for live games
                    d = json.loads(body)
                    sig = []
                    for e in d.get("events", []):
                        st = e.get("status", {}).get("type", {}).get("state")
                        if st == "in":
                            c = e["competitions"][0]
                            sig.append([e["id"], e["status"].get("displayClock"), e["status"].get("period"),
                                        [x.get("score") for x in c.get("competitors", [])]])
                    rec["live"] = sig
            except Exception as ex:  # record and continue
                rec = {"t0": time.time(), "err": repr(ex)[:200]}
            f.write(json.dumps(rec) + "\n")
            f.flush()
            time.sleep(max(0, nxt - time.time()))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step 6b: official WTA live-scoring API (api.wtatennis.com, public JSON). For every WTA tournament of the period
list the matches recorded as walkovers with the time the result was entered (MatchTimeStamp / LastUpdated).
Writes data/gaps_tennis_wo/wta_walkovers.json. Read-only; untrusted data, only names and timestamps are used."""
import json, time, urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
OUT = "/home/user/polymarket-lab/data/gaps_tennis_wo/wta_walkovers.json"


def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=40) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    print("failed", url, last)
    return None


def main():
    tours = []
    for page in range(0, 6):
        d = get(f"https://api.wtatennis.com/tennis/tournaments/?page={page}&pageSize=50&excludeLevels=ITF&from=2026-08-24&to=2026-11-25")
        if not d or not d.get("content"):
            break
        tours += d["content"]
        time.sleep(0.5)
    print("tournaments", len(tours))
    res = []
    n_matches = 0
    for t in tours:
        gid, year = t["tournamentGroup"]["id"], t["year"]
        d = get(f"https://api.wtatennis.com/tennis/tournaments/{gid}/{year}/matches")
        time.sleep(0.5)
        if not d:
            continue
        ms = d.get("matches") or []
        n_matches += len(ms)
        for m in ms:
            if "W/O" in (m.get("ScoreString") or "").upper() or "W/O" in (m.get("ResultString") or "").upper():
                res.append({"tournament": t["tournamentGroup"]["name"], "title": t.get("title"), "start": t["startDate"], "end": t["endDate"],
                            "type": m.get("DrawMatchType"), "level": m.get("DrawLevelType"), "round": m.get("RoundID"),
                            "A": [m.get("PlayerNameLastA"), m.get("PlayerNameLastA2")], "B": [m.get("PlayerNameLastB"), m.get("PlayerNameLastB2")],
                            "A_first": m.get("PlayerNameFirstA"), "B_first": m.get("PlayerNameFirstB"),
                            "result": m.get("ResultString"), "MatchTimeStamp": m.get("MatchTimeStamp"), "LastUpdated": m.get("LastUpdated")})
    print("matches", n_matches, "walkovers", len(res))
    json.dump(res, open(OUT, "w"), indent=1)
    for r in res:
        print(r["tournament"], r["type"], r["result"], r["MatchTimeStamp"], r["LastUpdated"])


if __name__ == "__main__":
    main()

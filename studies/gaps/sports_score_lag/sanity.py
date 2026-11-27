"""Data sanity (no strategy numbers): ESPN running score vs Polymarket resolution, delays, fee rates, tape coverage."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
games = json.loads((ROOT / "data" / "gaps_sports_lag" / "games.json").read_text())
bad = []
cnt = Counter()
for g in games:
    for m in g["markets"].values():
        cnt[("delay", m.get("delay"))] += 1
        cnt[("rate", m.get("rate"))] += 1
        cnt[("tape", m.get("n_rows") is not None)] += 1
    fin = {k: m.get("final") for k, m in g["markets"].items()}
    if g["sport"] == "soccer":
        h, a = g["events"][-1]["after"] if g["events"] else (0, 0)
        exp = {"home": "Yes" if h > a else "No", "away": "Yes" if a > h else "No", "draw": "Yes" if h == a else "No"}
        okk = all((fin[k] or {}).get(exp[k]) == 1.0 for k in exp)
    else:
        hs, as_ = (g["events"][-1]["after"] if g["events"] else (0, 0))
        w = g["home_out"] if (hs or 0) > (as_ or 0) else g["away_out"]
        okk = (fin["ml"] or {}).get(w) == 1.0
    cnt[(g["sport"], "score_matches_resolution", okk)] += 1
    if not okk:
        bad.append((g["event"], [(e.get("clock"), e["text"], e.get("after")) for e in g["events"]], fin))
for k, v in sorted(cnt.items(), key=str):
    print(k, v)
print("games", len(games), Counter(g["sport"] for g in games), Counter(g["league"] for g in games))
print("events", sum(len(g["events"]) for g in games))
for b in bad:
    print("MISMATCH", b)

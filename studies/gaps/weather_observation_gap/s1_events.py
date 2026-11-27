"""Step 1: enumerate closed weather events (gamma) and keep the daily highest-temperature ones.
Writes data/gaps_weather_obs/events_raw.jsonl.gz (all highest-temperature events with event date in the window)."""
import gzip, json, re, sys
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import gamma

OUT = "/home/user/polymarket-lab/data/gaps_weather_obs/events_raw.jsonl.gz"
SLUG = re.compile(r"^highest-temperature-in-(.+)-on-([a-z]+)-(\d{1,2})-(\d{4})$")
n = k = 0
seen = set()
with gzip.open(OUT, "wt") as f:
    for ev in gamma.iter_events(closed="true", tag_slug="weather", limit=50,
                                end_date_min="2026-09-29T00:00:00Z", end_date_max="2026-11-28T00:00:00Z"):
        n += 1
        s = ev.get("slug") or ""
        if not SLUG.match(s) or s in seen:
            continue
        seen.add(s)
        k += 1
        f.write(json.dumps(ev) + "\n")
        if k % 200 == 0:
            print(n, k, s, flush=True)
print("events seen", n, "highest-temperature kept", k)

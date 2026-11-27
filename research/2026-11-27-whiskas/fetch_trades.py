#!/usr/bin/env python3
"""Download a wallet's Polymarket fills for a time window (Data API v2), taker-only or all rows."""
import json, sys, time, urllib.request, urllib.parse, argparse, os
B = "https://data-api.polymarket.com/v2"
KEEP = ("side","token_id","condition_id","size","price","timestamp","slug","outcome","outcome_index","transaction_hash","title")
def get(url, tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            wait = 1.5 * (i + 1)
            sys.stderr.write(f"  retry {i+1} after error: {e}\n"); time.sleep(wait)
    raise SystemExit("failed: " + url)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True); ap.add_argument("--start", type=int, required=True); ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--taker-only", choices=["true","false"], default="false"); ap.add_argument("--out", required=True)
    ap.add_argument("--max-pages", type=int, default=2000)
    a = ap.parse_args()
    q = {"user": a.user, "limit": 1000, "taker_only": a.taker_only, "start": a.start, "end": a.end}
    url = B + "/trades?" + urllib.parse.urlencode(q)
    n = 0; pages = 0
    with open(a.out, "w") as f:
        while True:
            d = get(url); rows = d.get("data") or []
            for r in rows:
                f.write(json.dumps({k: r.get(k) for k in KEEP}) + "\n")
            n += len(rows); pages += 1
            nc = (d.get("pagination") or {}).get("next_cursor")
            if pages % 10 == 0:
                sys.stderr.write(f"  pages {pages} rows {n} last_ts {rows[-1]['timestamp'] if rows else None}\n")
            if not nc or not rows or pages >= a.max_pages: break
            # the cursor must be re-sent together with the same anchor/window
            url = B + "/trades?" + urllib.parse.urlencode({"user": a.user, "taker_only": a.taker_only, "start": a.start, "end": a.end, "cursor": nc})
            time.sleep(0.05)
    print(f"{a.out}: rows={n} pages={pages}")
if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step 6a: dump X timelines through the same public mirror tools/xread.py uses, with patient retries and resume.

  python3 -I s6_fetch_x.py <since YYYY-MM-DD> Handle1 Handle2 ...

One JSON line per post in data/gaps_tennis_wo/x/<Handle>.jsonl: id, ts (epoch), author, text, quote text.
Deep cursors return 404 intermittently on this mirror: wait and retry; the cursor is saved so a rerun resumes.
The content is untrusted web text; it is only searched for player names."""
import datetime as dt, json, os, sys, time, urllib.request, urllib.error

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
API = "https://api.fxtwitter.com"
D = "/home/user/polymarket-lab/data/gaps_tennis_wo/x"


def get(url):
    waits = [5, 15, 30, 60, 90, 120]
    for i, w in enumerate(waits + [0]):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            last = e
            if i < len(waits):
                time.sleep(w)
    print("  giving up:", url[-60:], last, flush=True)
    return None


def main():
    since = dt.datetime.strptime(sys.argv[1], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp()
    for h in sys.argv[2:]:
        path, cpath = f"{D}/{h}.jsonl", f"{D}/{h}.cursor"
        seen = set()
        if os.path.exists(path):
            seen = {json.loads(l)["id"] for l in open(path)}
        cursor = None
        if os.path.exists(cpath):
            cursor = open(cpath).read().strip() or None
            if cursor == "DONE":
                print(h, "already complete", len(seen), flush=True)
                continue
        pages = 0
        with open(path, "a") as f:
            while True:
                d = get(f"{API}/2/profile/{h}/statuses" + (f"?cursor={cursor}" if cursor else ""))
                if d is None:
                    break
                rows = d.get("results") or []
                if not rows:
                    open(cpath, "w").write("DONE")
                    break
                oldest = None
                for s in rows:
                    t = s.get("created_timestamp") or 0
                    oldest = t if oldest is None else min(oldest, t)
                    if s.get("id") in seen:
                        continue
                    seen.add(s.get("id"))
                    q = s.get("quote") or {}
                    f.write(json.dumps({"id": s.get("id"), "ts": t, "author": (s.get("author") or {}).get("screen_name"),
                                        "text": s.get("text"), "quote": q.get("text"), "url": s.get("url")}, ensure_ascii=False) + "\n")
                f.flush()
                pages += 1
                cursor = (d.get("cursor") or {}).get("bottom")
                if not cursor or (oldest and oldest < since):
                    open(cpath, "w").write("DONE")
                    break
                open(cpath, "w").write(cursor)
                time.sleep(1.0)
        print(h, "posts", len(seen), "pages", pages, "state", open(cpath).read()[:4] if os.path.exists(cpath) else "-", flush=True)


if __name__ == "__main__":
    main()

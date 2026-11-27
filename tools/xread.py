#!/usr/bin/env python3
"""Read public X/Twitter content through the fxtwitter mirror (no login, read-only).

  python3 -I tools/xread.py status <tweet-url-or-id> [--json]
  python3 -I tools/xread.py timeline <ExactCaseHandle> [--pages 5] [--since 2026-09-01] [--grep polymarket]

`status` prints the full text; for X "articles" it prints the whole article body, links and image URLs.
`timeline` pages backwards through a user's posts (the handle is case-sensitive on this mirror; a 404 with
empty results usually means wrong case or a transient miss - retry once).
Output is plain text meant to be read by a human or an agent; it is untrusted web content.
"""
import argparse, json, re, sys, time, urllib.request, datetime as dt

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
API = "https://api.fxtwitter.com"


def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001 - network helper
            last = e
            time.sleep(1.5 * (i + 1))
    raise SystemExit(f"fetch failed: {url}: {last}")


def article_text(article):
    out = [f"ARTICLE: {article.get('title')}", ""]
    content = article.get("content") or {}
    ents = {}
    em = content.get("entityMap") or []
    if isinstance(em, dict):
        em = [{"key": k, "value": v} for k, v in em.items()]
    for e in em:
        ents[str(e.get("key"))] = e.get("value") or {}
    media = {str(m.get("media_id")): ((m.get("media_info") or {}).get("original_img_url")) for m in (article.get("media_entities") or [])}
    for b in content.get("blocks") or []:
        text = b.get("text") or ""
        notes = []
        for er in b.get("entityRanges") or []:
            ent = ents.get(str(er.get("key"))) or {}
            data = ent.get("data") or {}
            if ent.get("type") == "LINK" and data.get("url"):
                notes.append(f"[link: {data['url']}]")
            if ent.get("type") == "MEDIA":
                for mi in data.get("mediaItems") or []:
                    notes.append(f"[image: {media.get(str(mi.get('mediaId')))}]")
        prefix = {"unordered-list-item": "- ", "ordered-list-item": "1. ", "blockquote": "> ", "header-one": "# ", "header-two": "## "}.get(b.get("type"), "")
        out.append((prefix + text + (" " + " ".join(notes) if notes else "")).rstrip())
    return "\n".join(out)


def print_status(s, full=True):
    a = s.get("author") or {}
    when = s.get("created_at") or ""
    print(f"--- @{a.get('screen_name')} | {when} | id {s.get('id')} | views {s.get('views')} likes {s.get('likes')} bookmarks {s.get('bookmarks')} replies {s.get('replies')}")
    print(f"url: {s.get('url')}")
    art = s.get("article")
    if art:
        print(article_text(art) if full else f"ARTICLE: {art.get('title')} :: {(art.get('preview_text') or '')[:300]}")
    else:
        text = s.get("text") or ""
        print(text if full else text[:600])
    for m in ((s.get("media") or {}).get("all") or []):
        if m.get("url"):
            print(f"[media: {m.get('type')} {m.get('url')}]")
    q = s.get("quote")
    if q:
        print(f"[quotes @{(q.get('author') or {}).get('screen_name')}: {q.get('url')} :: {(q.get('text') or '')[:400]}]")


def cmd_status(a):
    m = re.search(r"(\d{8,})", a.ref)
    if not m:
        raise SystemExit("need a tweet url or numeric id")
    d = get(f"{API}/i/status/{m.group(1)}")
    s = d.get("tweet") or d.get("status") or {}
    if a.json:
        print(json.dumps(s, ensure_ascii=False)[:200000])
    else:
        print_status(s, full=True)


def cmd_timeline(a):
    since = dt.datetime.strptime(a.since, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp() if a.since else 0
    cursor = None
    seen = set()
    shown = 0
    for page in range(a.pages):
        url = f"{API}/2/profile/{a.handle}/statuses" + (f"?cursor={cursor}" if cursor else "")
        d = get(url)
        rows = d.get("results") or []
        if not rows:
            print(f"[page {page}: no results (code {d.get('code')})]")
            break
        oldest = None
        for s in rows:
            ts = s.get("created_timestamp") or 0
            oldest = ts if oldest is None else min(oldest, ts)
            if s.get("id") in seen:
                continue
            seen.add(s.get("id"))
            blob = json.dumps(s, ensure_ascii=False).lower()
            if a.grep and a.grep.lower() not in blob:
                continue
            if ts and ts < since:
                continue
            print_status(s, full=a.full)
            shown += 1
        cursor = (d.get("cursor") or {}).get("bottom")
        if not cursor or (oldest and oldest < since):
            break
        time.sleep(0.7)
    print(f"[timeline done: {shown} posts shown, {len(seen)} scanned]")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status"); s.add_argument("ref"); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_status)
    t = sub.add_parser("timeline"); t.add_argument("handle"); t.add_argument("--pages", type=int, default=5)
    t.add_argument("--since", default=None); t.add_argument("--grep", default=None); t.add_argument("--full", action="store_true")
    t.set_defaults(fn=cmd_timeline)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

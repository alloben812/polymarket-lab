#!/usr/bin/env python3
"""Step 7 (protocol 2.7): public notice time t_public for class A events, from the sources that were reachable.

Sources (all fetched before by s6_fetch_x.py / s6_wta.py / tools/xread.py; untrusted text, only names and times used):
  - WTA live-scoring API (data/gaps_tennis_wo/wta_walkovers.json): MatchTimeStamp and LastUpdated of matches whose
    result is W/O, second precision. LastUpdated is the latest edit of the record, so the W/O was visible no later
    than that: it is used as t_public (an upper bound on the first public moment); MatchTimeStamp is shown alongside.
  - X timelines dumped under data/gaps_tennis_wo/x/ (*.jsonl from s6_fetch_x.py, *.txt from tools/xread.py):
    posts that name a player of the event together with a withdrawal word, posted between scheduled start - 4 days
    and the moneyline close. Second precision. Every match is printed for a manual check; rejected ones are listed
    in REJECT below with the reason.
Order of work (2.7): class A events sorted by moneyline volume; every class A event is "attempted" against every
source; hit rate reported. Writes out/public_times.json and prints the table (out/s6_public.txt)."""
import datetime as dt, glob, json, re, unicodedata
from common import *

X = DATA / "x"
KEY = re.compile(r"withdr|walkover|walk-over|\bw/o\b|\bOUT:|pulls? out|pulled out|will not play|won't play|scratch", re.I)
REJECT = {  # slug -> reason, filled after manual review of the printed matches (2026-11-27)
    "atp-doubles-luzmato-berrcob-2026-11-03": "generic 'barring withdrawals' post, not this match",
    "atp-doubles-michtie-krawpue-2026-11-03": "post is about the singles withdrawals of Tsitsipas/Davidovich Fokina; Tien matched by name only",
    "atp-doubles-basefar-coutpag-2026-11-03": "post is about singles withdrawals at Basel, not this doubles match",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z /-]", "", s)


def surnames(side):
    """'Carlos Alcaraz' -> {'alcaraz'}; 'Jiang/Zhang' -> {'jiang','zhang'}; multi-word surnames keep the last two words too."""
    out = set()
    for p in re.split(r"/", norm(side)):
        w = [x for x in re.split(r"[ -]", p.strip()) if x]
        if not w:
            continue
        out.add(w[-1])
        if len(w) >= 3:
            out.add(" ".join(w[-2:]))
    return out


def sides(title):
    t = title.split(":", 1)[-1]
    parts = re.split(r"\s+vs\.?\s+", t)
    return parts if len(parts) == 2 else None


def load_x():
    posts = []
    for f in glob.glob(str(X / "*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            if r.get("ts"):
                posts.append({"ts": float(r["ts"]), "author": r.get("author"), "text": (r.get("text") or "") + " " + (r.get("quote") or ""), "url": r.get("url")})
    for f in glob.glob(str(X / "*.txt")):
        cur = None
        for l in open(f, errors="ignore"):
            m = re.match(r"--- @(\S+) \| (.+?) \| id (\d+)", l)
            if m:
                if cur:
                    posts.append(cur)
                t = dt.datetime.strptime(m.group(2), "%a %b %d %H:%M:%S %z %Y").timestamp()
                cur = {"ts": t, "author": m.group(1), "text": "", "url": f"https://x.com/{m.group(1)}/status/{m.group(3)}"}
            elif cur is not None:
                cur["text"] += l
        if cur:
            posts.append(cur)
    seen, out = set(), []
    for p in posts:
        k = p["url"] or (p["author"], p["ts"])
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def main():
    U = json.load(open(DATA / "universe.json"))
    EA = {o["slug"]: o for o in json.load(open(OUT / "events_A.json"))}
    wta = json.load(open(DATA / "wta_walkovers.json")) if (DATA / "wta_walkovers.json").exists() else []
    posts = load_x()
    print(f"sources: WTA API walkover records {len(wta)}; X posts loaded {len(posts)} from {sorted({p['author'] for p in posts})}")
    recs = sorted(U["A"], key=lambda r: -(next(m for m in r["markets"] if m["cid"] == r["ml"])["vol"] or 0))
    res = []
    for r in recs:
        o = EA[r["slug"]]
        sd = sides(r["title"])
        row = {"slug": r["slug"], "series": r["series"], "title": r["title"], "t_first": o.get("t_first"), "start": o.get("start"),
               "closed": o.get("closed"), "t_public": None, "precision": None, "source": None, "candidates": []}
        if not sd:
            res.append(row)
            continue
        sa, sb = surnames(sd[0]), surnames(sd[1])
        lo = (o.get("start") or o["closed"]) - 4 * 86400
        hi = o["closed"] or (o.get("start") or 0) + 86400
        for w in wta:
            wa = {norm(x) for x in w["A"] if x}
            wb = {norm(x) for x in w["B"] if x}
            t_lu = ts(w["LastUpdated"])
            t_mt = ts(w["MatchTimeStamp"])
            if not t_lu or not (lo <= t_lu <= hi + 86400):
                continue
            if (wa & sa and wb & sb) or (wa & sb and wb & sa):
                row["candidates"].append({"src": "WTA API LastUpdated", "t": t_lu, "t_matchstamp": t_mt, "text": f"{w['tournament']} {w['result']}"})
        for p in posts:
            if not (lo <= p["ts"] <= hi) or not KEY.search(p["text"]):
                continue
            tx = norm(p["text"])
            hit = [s for s in sa | sb if len(s) >= 4 and re.search(r"\b" + re.escape(s) + r"\b", tx)]
            if hit:
                row["candidates"].append({"src": f"X @{p['author']}", "t": p["ts"], "text": p["text"][:160].replace("\n", " "), "url": p["url"], "names": hit})
        ok = [] if r["slug"] in REJECT else row["candidates"]
        row["rejected"] = REJECT.get(r["slug"])
        if ok:
            c = min(ok, key=lambda c: c["t"])
            row.update({"t_public": c["t"], "precision": "second", "source": c["src"]})
        res.append(row)
    json.dump(res, open(OUT / "public_times.json", "w"))
    att = len(res)
    found = [x for x in res if x["t_public"]]
    print(f"attempted {att} class A events (all, by volume); with a second-precision notice {len(found)}; of them with t_first {sum(1 for x in found if x['t_first'])}")
    print("slug | series | t_first | t_public | lag t_first - t_public | source | MatchTimeStamp lag | text")
    lags = []
    for x in found:
        lag = (x["t_first"] - x["t_public"]) if x["t_first"] else None
        c = min(x["candidates"], key=lambda c: c["t"])
        mt = c.get("t_matchstamp")
        if lag is not None:
            lags.append(lag)
        lag_s = "n/a" if lag is None else f"{lag:+.0f} s"
        mt_s = "" if (not mt or not x["t_first"]) else f"{x['t_first'] - mt:+.0f} s"
        print(f"{x['slug']} | {x['series']} | {iso(x['t_first'])} | {iso(x['t_public'])} | {lag_s} | {x['source']} | {mt_s} | {c['text'][:110]}")
        for c2 in x["candidates"]:
            if c2 is not c:
                print(f"      other: {c2['src']} {iso(c2['t'])} {c2['text'][:100]}")
    if lags:
        lags.sort()
        print(f"lag t_first - t_public (n={len(lags)}): median {lags[len(lags) // 2]:+.0f} s, min {lags[0]:+.0f} s, max {lags[-1]:+.0f} s; "
              f"book moved before the notice in {sum(1 for v in lags if v < 0)}, within 60 s after in {sum(1 for v in lags if 0 <= v <= 60)}, later in {sum(1 for v in lags if v > 60)}")


if __name__ == "__main__":
    main()

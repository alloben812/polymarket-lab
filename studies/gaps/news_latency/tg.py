"""Search public Telegram channel previews (t.me/s/<channel>?q=...) for timestamped posts. Read-only; the text
returned is untrusted web content and is only printed.
usage: python3 -I tg.py "<query>" [YYYY-MM-DD] [channel,channel,...]   -> posts within +-2 days of the date"""
import datetime as dt, html, re, sys, time, urllib.parse, urllib.request

CHANNELS = ["disclosetv", "OSINTdefender", "bricsnews", "rnintel", "spectatorindex", "Faytuks", "BNONews", "intelslava", "war_monitor",
            "AJENews_Official", "insiderpaper", "worldnews", "clashreport", "MiddleEastSpectator", "theinsider_news"]
MSG = re.compile(r'<div class="tgme_widget_message_wrap.*?(?=<div class="tgme_widget_message_wrap|\Z)', re.S)
TXT = re.compile(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
TIM = re.compile(r'<time datetime="([^"]+)"')
LNK = re.compile(r'data-post="([^"]+)"')


def search(channel, q):
    url = f"https://t.me/s/{channel}?q={urllib.parse.quote(q)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=40) as r:
            if r.geturl().rstrip("/").endswith(channel) and "/s/" not in r.geturl():
                return []
            page = r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return []
    out = []
    for blk in MSG.findall(page):
        t, x, l = TIM.findall(blk), TXT.search(blk), LNK.search(blk)
        if not t or not x:
            continue
        text = html.unescape(re.sub(r"<[^>]+>", " ", x.group(1)))
        when = dt.datetime.fromisoformat(t[-1])
        out.append((when, l.group(1) if l else channel, re.sub(r"\s+", " ", text).strip()))
    return out


def main():
    q = sys.argv[1]
    day = dt.datetime.fromisoformat(sys.argv[2]).replace(tzinfo=dt.timezone.utc) if len(sys.argv) > 2 else None
    chans = sys.argv[3].split(",") if len(sys.argv) > 3 else CHANNELS
    rows = []
    for ch in chans:
        for when, post, text in search(ch, q):
            if day is None or abs((when - day).total_seconds()) <= 2.5 * 86400:
                rows.append((when, post, text))
        time.sleep(0.4)
    for when, post, text in sorted(rows):
        print(when.strftime("%Y-%m-%d %H:%M:%S"), int(when.timestamp()), post, "|", text[:260])
    print(f"[{len(rows)} posts]")


if __name__ == "__main__":
    main()

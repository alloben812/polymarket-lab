"""Public-only readiness probe for the Mac. Never print the geolocation payload."""

import asyncio
import json
import re
import subprocess
import time
from urllib.request import Request, urlopen

from websockets.asyncio.client import connect

WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def public(url):
    with urlopen(
        Request(url, headers={"User-Agent": "pmlab-public/1"}), timeout=12
    ) as response:
        return json.load(response)


def ntp(host):
    reply = subprocess.run(
        ["/usr/bin/sntp", "-t", "3", host], capture_output=True, text=True, timeout=8
    )
    fields = re.search(
        r"([+-][0-9]+\.[0-9]+)\s+\+/-\s*([0-9.]+)", reply.stdout + reply.stderr
    )
    if reply.returncode or not fields:
        raise RuntimeError("NTP probe unavailable")
    return {
        "offset_ms": round(float(fields[1]) * 1000, 2),
        "uncertainty_ms": round(float(fields[2]) * 1000, 2),
    }


async def run():
    geo = public("https://polymarket.com/api/geoblock")
    if not isinstance(geo.get("blocked"), bool):
        raise RuntimeError("geoblock field missing")
    result = {"country": geo.get("country"), "blocked": geo["blocked"]}
    start = int(time.time()) // 300 * 300
    event = public(
        f"https://gamma-api.polymarket.com/events/slug/btc-updown-5m-{start}"
    )
    market = event["markets"][0]
    ids = json.loads(market["clobTokenIds"])
    book = public("https://clob.polymarket.com/book?token_id=" + ids[0])
    if book["asset_id"] != ids[0]:
        raise RuntimeError("unexpected REST book")
    result["rest_slug"] = market["slug"]
    counts = {}
    async with asyncio.timeout(22):
        async with connect(WS, open_timeout=10) as ws:
            await ws.send(
                json.dumps(
                    {
                        "type": "market",
                        "assets_ids": ids,
                        "custom_feature_enabled": True,
                    }
                )
            )
            while counts.get("book", 0) == 0 or not (set(counts) - {"book"}):
                frame = await ws.recv()
                if frame in ("PONG", "PING"):
                    continue
                packet = json.loads(frame)
                for item in packet if isinstance(packet, list) else [packet]:
                    name = item.get("event_type", "other")
                    counts[name] = counts.get(name, 0) + 1
    result["websocket_events"] = counts
    result["ntp"] = {
        host: ntp(host) for host in ("time.apple.com", "time.cloudflare.com")
    }
    print(json.dumps(result, sort_keys=True))
    if result["blocked"] or any(
        abs(x["offset_ms"]) + x["uncertainty_ms"] > 250 for x in result["ntp"].values()
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(run())

"""Record only public, closed Binance one-second candles and official resolutions."""

import asyncio
import json
import time
from urllib.request import Request, urlopen

from websockets.asyncio.client import connect


def get_json(url, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"User-Agent": "pmlab-public/1", "Content-Type": "application/json"}
    with urlopen(Request(url, data=body, headers=headers), timeout=7) as response:
        return json.load(response)


async def reference_btc(journal):
    newest = 0

    def ingest(source, bars):
        nonlocal newest
        fresh = [(sec, price) for sec, price in bars if sec > newest]
        if not fresh:
            return
        if newest and fresh[0][0] > newest + 1:
            # REST will fetch the missing interval on its next scheduled poll.
            if source == "binance_ws":
                return
            journal.put(
                "reference_gap",
                reason="missing_seconds",
                since_s=newest,
                to_s=fresh[0][0],
            )
        journal.put("reference", symbol="BTCUSDT", source=source, bars=fresh)
        newest = fresh[-1][0]

    async def mirror():
        while True:
            try:
                now = int(time.time())
                limit = 1000 if not newest else max(4, min(1000, now - newest + 3))
                url = (
                    "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1s&limit="
                    + str(limit)
                )
                if newest:
                    # The latest-N window moves while a request is in flight.
                    # Page from the last accepted second, including delayed recovery.
                    url += f"&startTime={(newest + 1) * 1000}"
                rows = await asyncio.to_thread(get_json, url)
                # Ignore the candle which was open when the request was sent.
                bars = [
                    (int(r[0]) // 1000, str(r[4]))
                    for r in rows
                    if int(r[0]) // 1000 < now
                ]
                if any(b[0] != a[0] + 1 for a, b in zip(bars, bars[1:])):
                    raise ValueError("non-contiguous mirror response")
                ingest("binance_rest", bars)
            except Exception as err:
                journal.put(
                    "reference_error", source="binance_rest", reason=type(err).__name__
                )
            await asyncio.sleep(1)

    async def stream():
        while True:
            try:
                async with connect(
                    "wss://data-stream.binance.vision/ws/btcusdt@kline_1s",
                    open_timeout=8,
                ) as ws:
                    while True:
                        k = json.loads(await asyncio.wait_for(ws.recv(), timeout=7))[
                            "k"
                        ]
                        if newest and k["x"] and k["s"] == "BTCUSDT" and k["i"] == "1s":
                            ingest("binance_ws", [(int(k["t"]) // 1000, str(k["c"]))])
            except Exception as err:
                journal.put(
                    "reference_error", source="binance_ws", reason=type(err).__name__
                )
                await asyncio.sleep(2)

    async with asyncio.TaskGroup() as group:
        group.create_task(mirror())
        group.create_task(stream())


async def resolutions(journal, seen, pending):
    while True:
        await asyncio.sleep(10)
        for slug, market in list(pending.items()):
            end = market.get("end_ts")
            if not end or int(time.time()) < end + 12 or slug in seen:
                continue
            try:
                m = await asyncio.to_thread(
                    get_json, "https://gamma-api.polymarket.com/markets/slug/" + slug
                )
                if (
                    m.get("conditionId") != market["condition_id"]
                    or not m.get("closed")
                    or m.get("umaResolutionStatus") != "resolved"
                ):
                    continue
                outcomes, prices = (
                    json.loads(m["outcomes"]),
                    json.loads(m["outcomePrices"]),
                )
                if len(outcomes) != len(prices) or set(outcomes) != set(
                    market["tokens"]
                ):
                    raise ValueError("invalid official outcomes")
                payouts = {k: float(v) for k, v in zip(outcomes, prices)}
                if (
                    not all(0 <= v <= 1 for v in payouts.values())
                    or abs(sum(payouts.values()) - 1) > 1e-6
                ):
                    raise ValueError("invalid payouts")
                journal.put(
                    "resolution",
                    slug=slug,
                    condition_id=m["conditionId"],
                    payouts=payouts,
                    source="gamma",
                )
                seen.add(slug)
                pending.pop(slug, None)
            except (ValueError, KeyError, OSError) as err:
                journal.put("resolution_error", slug=slug, reason=type(err).__name__)

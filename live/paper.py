"""Run the same event-driven paper strategy on a live public feed or sealed tape."""

import argparse
import asyncio
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path
import signal

from .book import BookReplay, iter_records
from .journal import Journal, atomic_json
from .record import DEFAULT_ROOT, HERE, Recorder

DAY_NS = 86_400_000_000_000
BASELINE_CENTS = Decimal("3.58")


def utc_day(recv_ns):
    return (date(1970, 1, 1) + timedelta(days=recv_ns // DAY_NS)).isoformat()


class Daily:
    """Realized cash flows use the UTC day of sale or official settlement."""

    def __init__(self):
        self.days = {}
        self.positions = {}
        self.markets = {}
        self.tainted_since = None
        self.fills = []

    def day(self, now):
        key = utc_day(now)
        if key not in self.days:
            self.days[key] = Counter()
        return self.days[key]

    def fill(self, f):
        size, price, fee = (Decimal(f[k]) for k in ("size", "price", "fee"))
        token = f["token"]
        pos = self.positions.setdefault(
            token,
            {
                "slug": f["slug"],
                "outcome": f["outcome"],
                "size": Decimal(0),
                "cost": Decimal(0),
            },
        )
        day = self.day(f["recv_ns"])
        day["fills"] += 1
        day["fees"] += fee
        if f["side"] == "BUY":
            pos["size"] += size
            pos["cost"] += size * price + fee
        else:
            if pos["size"] < size:
                raise ValueError("paper sell exceeds recorded holdings")
            cost = pos["cost"] * size / pos["size"]
            pos["size"] -= size
            pos["cost"] -= cost
            day["realized"] += size * price - fee - cost
            day["closed_shares"] += size
        self.fills.append(f)

    def resolve(self, row):
        slug = row["slug"]
        m = self.markets.get(slug)
        if (
            not m
            or m["condition_id"] != row["condition_id"]
            or row.get("source") != "gamma"
        ):
            return []
        payouts = {k: Decimal(str(v)) for k, v in row["payouts"].items()}
        if (
            set(payouts) != set(m["tokens"])
            or sum(payouts.values()) != 1
            or min(payouts.values()) < 0
        ):
            raise ValueError("invalid official resolution in paper tape")
        results = []
        for outcome, token in sorted(m["tokens"].items()):
            pos = self.positions.get(token)
            if not pos or pos["size"] == 0:
                continue
            proceeds = pos["size"] * payouts[outcome]
            result = proceeds - pos["cost"]
            day = self.day(row["recv_ns"])
            day["realized"] += result
            day["closed_shares"] += pos["size"]
            day["settled_lots"] += 1
            results.append(
                dict(
                    kind="realized",
                    slug=slug,
                    token=token,
                    outcome=outcome,
                    size=str(pos["size"]),
                    cost_including_fees=str(pos["cost"]),
                    payout=str(proceeds),
                    net=str(result),
                )
            )
            pos["size"] = pos["cost"] = Decimal(0)
        return results

    def gap(self, row):
        # Later REST reconciliation can invalidate a quote already used online.
        # An affected fill also changes subsequent cash and risk availability.
        affected = set(row.get("tokens", []))
        result = []
        for f in self.fills:
            if f.get("book_session") != row["session"] or (
                affected and f["token"] not in affected
            ):
                continue
            evidence = (f["recv_ns"], f.get("signal_recv_ns"), f.get("book_recv_ns"))
            if any(
                stamp is not None and row["since_ns"] < stamp <= row["recv_ns"]
                for stamp in evidence
            ):
                self.tainted_since = min(
                    self.tainted_since or f["recv_ns"], f["recv_ns"]
                )
                result.append(
                    dict(
                        kind="invalidated_fill",
                        fill_id=f.get("fill_id"),
                        slug=f["slug"],
                        reason=row["reason"],
                        since_ns=row["since_ns"],
                    )
                )
        return result

    def summary(self):
        rows = {}
        for name, day in sorted(self.days.items()):
            closed = day["closed_shares"]
            valid = self.tainted_since is None or name < utc_day(self.tainted_since)
            cents = (
                Decimal(100) * day["realized"] / closed if closed and valid else None
            )
            rows[name] = dict(
                decisions=day["decisions"],
                intents=day["intents"],
                fills=day["fills"],
                fees=str(day["fees"]),
                settled_lots=day["settled_lots"],
                closed_shares=str(closed),
                realized_net=str(day["realized"]) if valid else None,
                net_cents_per_closed_share=str(round(cents, 5))
                if cents is not None
                else None,
                difference_from_study_cents=str(round(cents - BASELINE_CENTS, 5))
                if cents is not None
                else None,
                accounting="verified" if valid else "withheld_after_invalidated_fill",
            )
        open_positions = {
            k: {**v, "size": str(v["size"]), "cost": str(v["cost"])}
            for k, v in self.positions.items()
            if v["size"]
        }
        return dict(
            utc_days=rows,
            open_positions=open_positions,
            historical_holdout_cents_per_share=str(BASELINE_CENTS),
            historical_holdout_markets=5,
        )


class Paper:
    def __init__(self, output, latency_ms, cash):
        from .execution import PaperExecution
        from .lockin import Lockin

        output.mkdir(parents=True, exist_ok=False)
        self.output = output
        self.file = (output / "decisions.jsonl").open("x", encoding="utf8")
        self.book = BookReplay()
        self.strategy = Lockin()
        self.execution = PaperExecution(initial_cash=cash, latency_ms=latency_ms)
        self.daily = Daily()
        self.last_summary = 0
        self.last_day = -1
        self.reasons = Counter()
        self.write(
            dict(
                kind="settings",
                strategy="btc5m_lockin",
                model_delay_seconds=1,
                order_latency_ms=latency_ms,
                initial_paper_cash=str(cash),
            )
        )

    def write(self, value):
        self.file.write(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        )
        self.file.flush()

    def entry(self, row, value):
        self.write(
            {
                "recv_ns": row["recv_ns"],
                "ordinal": row["ordinal"],
                "session": row["session"],
                **value,
            }
        )

    def lifecycle(self, row, records):
        for item in records:
            self.entry(row, item)
            if item["kind"] == "fill":
                self.daily.fill(item)

    def observe(self, row):
        now = row["recv_ns"]
        if now // DAY_NS != self.last_day:
            self.daily.day(now)
            self.last_day = now // DAY_NS
        self.book.apply(row)
        if row["kind"] == "market":
            market = row["market"]
            self.daily.markets[market["slug"]] = market
        self.lifecycle(row, self.execution.observe(row, self.book))
        if row["kind"] == "gap":
            for item in self.daily.gap(row):
                self.entry(row, item)
        if row["kind"] == "resolution":
            for item in self.daily.resolve(row):
                self.entry(row, item)
        for decision in self.strategy.observe(row, self.book):
            self.entry(row, {"kind": "decision", **decision})
            day = self.daily.day(now)
            day["decisions"] += 1
            self.reasons[decision["reason"]] += 1
            if decision["action"] == "intent":
                day["intents"] += 1
                self.lifecycle(row, self.execution.submit(decision, row, self.book))
        if now - self.last_summary >= 60_000_000_000 or row["kind"] == "stop":
            self.save()
            self.last_summary = now

    def save(self):
        atomic_json(
            self.output / "daily.json",
            dict(
                **self.daily.summary(),
                decision_reasons=dict(sorted(self.reasons.items())),
            ),
        )

    def close(self):
        self.save()
        self.file.close()


async def live(args):
    journal = Journal(args.root)
    recorder = Recorder(journal, json.loads(args.config.read_text()))
    engine = Paper(journal.run / "paper", args.latency_ms, args.cash)
    journal.listener = engine.observe
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, recorder.stop.set)
    print(journal.run, flush=True)
    try:
        await recorder.run(args.seconds)
    finally:
        engine.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    stream = sub.add_parser("live")
    stream.add_argument("--config", type=Path, default=HERE / "markets.json")
    stream.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    stream.add_argument("--seconds", type=int, default=86400)
    replay = sub.add_parser("replay")
    replay.add_argument("run", type=Path)
    replay.add_argument("--output", type=Path, required=True)
    for cmd in (stream, replay):
        cmd.add_argument("--latency-ms", type=int, default=1000)
        cmd.add_argument("--cash", type=Decimal, default=Decimal(200))
    args = p.parse_args()
    if args.latency_ms <= 0 or not args.cash.is_finite() or args.cash <= 0:
        p.error("latency and simulated cash must be positive")
    if args.cmd == "live":
        if args.seconds <= 0:
            p.error("duration must be positive")
        asyncio.run(live(args))
        return
    files = sorted(args.run.glob("*.jsonl.gz"))
    if not files or list(args.run.glob("*.jsonl.gz.open")):
        p.error("replay requires a sealed run")
    engine = Paper(args.output, args.latency_ms, args.cash)
    last = None
    try:
        for row in iter_records(files):
            if last is None and row["ordinal"] != 1:
                raise ValueError("tape starts mid-run")
            if last == "stop":
                raise ValueError("records after stop")
            engine.observe(row)
            last = row["kind"]
        if last != "stop":
            raise ValueError("tape lacks final stop")
    finally:
        engine.close()
    print(args.output / "daily.json")


if __name__ == "__main__":
    main()

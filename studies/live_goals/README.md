# live_goals: the first measurement on live data

**Question.** A goal is scored. Which free source shows it first, and how many seconds after the Polymarket price
has already moved? What can a trader who reacts 1 s or 3 s after that confirmation still buy in the real order
book, and is it profitable after two 0.05 sports fees? The earlier tape study (`studies/gaps/sports_score_lag`)
could answer this only after the fact. Here every book change and every score update is recorded live on one
local clock.

**No orders are sent anywhere.** The trades are hypothetical (paper). Only public data is used: no accounts, no
keys, no wallets.

## Files (code and text only; data lives in `data/live_goals/`, which is not in git)

| file | what it does |
|---|---|
| `recorder.py` | Records everything. `--part ws`: gamma discovery every 10 min, the Polymarket market WebSocket (all book changes and trades of today's and tomorrow's soccer matches, from 20 min before kickoff to 3 h after), clock checks, compression. `--part scores`: the Polymarket sports WebSocket and the score pollers (ESPN scoreboard + summary, LiveScore, 365Scores, BBC, every 2 s). |
| `wsclient.py` | Minimal WebSocket client (standard library), works through the sandbox proxy. |
| `paper.py` | Paper trader: replays the recorded files in receive-time order and applies the frozen rules of `protocol.md`. With `--follow` it keeps up with the live files (4 s behind). |
| `report.py` | Prints the report: coverage, clocks, sources, lag per source, stale dollars, paper trades with CI. |
| `run.sh` | Detached restart loops (nohup + setsid): `start --with-paper`, `status`, `stop`. |
| `protocol.md` | The rules, frozen before any result (hash and time in `data/live_goals/protocol_frozen.txt`). |

## How to run, check and stop

```
bash studies/live_goals/run.sh start --with-paper   # recorder (ws), scores, paper: three restart loops
bash studies/live_goals/run.sh status               # are they alive, lines written, shards
python3 studies/live_goals/report.py                # the report (also written to data/live_goals/report.txt)
python3 studies/live_goals/report.py --replay       # rebuild the paper outputs from raw files first
bash studies/live_goals/run.sh stop                 # stops all three (writes *.stop files, kills the sessions)
```

Logs: `data/live_goals/recorder.log`, `scores.log`, `paper.log`. The heartbeat is `data/live_goals/status.json`,
rewritten every minute.

## Data layout (`data/live_goals/`)

- `YYYY-MM-DD/ws_market-HH.g<start>.jsonl.gz` is the market WebSocket, gzip written on the fly (one file per
  process and hour). Each line is `{"r": local receive ms, "k": shard, "d": raw message}`.
- `pm_sports-HH.jsonl` (sports WebSocket), `scores-HH.jsonl` (one line per change of a game's score or state per
  source), `polls2-HH.jsonl` (every poll: status, latency, Date/Age/Cache-Control), `meta-HH.jsonl` /
  `meta2-HH.jsonl` (connections, errors, discovery), `clock-HH.jsonl`, `matches-HH.jsonl` (discovered matches).
  Plain files are gzipped after two hours.
- `paper/`: `triggers.jsonl`, `fills.jsonl` (with the book snapshot used), `goals.jsonl`, `links.jsonl`,
  `resolved.jsonl`.

## Guards

- Polite polling: one request per source every 2 s. ESPN summaries are capped at 2 requests/s in total. On an error
  the source backs off (403/429 start at 30 s and double up to 10 min). The user agent is generic and no personal
  identifier is sent.
- Disk: below 6 GB free only moneyline tokens are subscribed, below 3 GB nothing (logged as `disk_guard`).
  Measured on Friday evening: about 1.3 MB/s of raw WebSocket text, about 0.2 MB/s after gzip.
- The two recorder processes never append to the same file (`meta`/`polls` vs `meta2`/`polls2`), so the
  pollers' JSON work cannot delay the receive timestamps of the market stream.

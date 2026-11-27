#!/usr/bin/env python3
"""Operator: the bridge between the lab's coordinator and the trading programs on the owner's Mac.

Start it through the launcher: `python3 -I pilot/operator.py run` (this file holds the code; the launcher's
name matches the standard-library module `operator`, see the launcher's docstring).

The coordinator (a cloud session that cannot send orders: Polymarket blocks order placement from its US
IP) decides what runs and commits that decision to the branch `live-control` of the repository's origin,
as one JSON file `control/desired.json` (a sequence number and a list of actions). This program runs on
the owner's Mac, next to smoke.py / exp_bids.py / exp_fav.py, and:

  * every 60 s runs `git fetch origin live-control` and reads the JSON file from the fetched ref with
    `git cat-file blob` (never a checkout, merge or pull; no code from that branch is ever run: the
    programs it starts are the files already on disk, which only the owner updates by hand);
  * processes each new sequence number exactly once (state: ~/.polymarket-pilot/operator-state.json);
  * executes only actions from a fixed table (program + subcommand + parameters checked against explicit
    ranges); no shell, no free-form arguments, no paths from the control file;
  * runs a live action only while the owner's file ~/.polymarket-pilot/ARMED exists; ARMED states the
    maximum total loss and the maximum daily loss in USD; at a limit the operator creates the STOP file
    the programs honour, interrupts the running live program and reports; removing ARMED disarms at once;
    the control file can lower these limits, never raise them;
  * after every action and at least every 30 minutes commits a small JSON and Markdown report to the
    branch `live-reports` and pushes it. The commit is built with git plumbing in the object store
    (hash-object, mktree, commit-tree, hooks off): nothing from that branch is ever checked out or
    written to disk, and the working copy with the code is never touched. Reports are scrubbed: no key,
    no secret, no wallet address, no user name, no host name, no home path, no repository path, no URL.
  * one failing cycle never ends supervision; on any exit a running program is interrupted.

Subcommands
  run       the loop (start it with `caffeinate -i` so the Mac stays awake)
  check F   validate a control file and print what each action would run (no state, no network)
  status    print the local state, ARMED and limits (no network)
  selftest  throwaway git repositories and fake programs: whitelist, ranges, replay, ARMED, limits,
            stale actions, sleep, STOP, report scrubbing, report branch, untouched working copy, and the
            attacks of the security review (REVIEW-operator.md: M1-M3, S1-S6, S8, S9)

Exit codes: 0 ok, 2 refused (bad control file, second instance), 1 error.
Only the Python standard library is used; git must be installed.
"""
from __future__ import annotations

import argparse
import fcntl
import getpass
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path

VERSION = "1.1.0"

# ----------------------------------------------------------------------------- fixed settings
CONTROL_BRANCH = "live-control"
CONTROL_FILE = "control/desired.json"
REPORT_BRANCH = "live-reports"
POLL_S = 60                       # fetch the control branch this often
HEARTBEAT_S = 30 * 60             # a report at least this often
BALANCE_PROBE_S = 30 * 60         # during a live run: read the balance this often (smoke.py auth --live)
DEFAULT_MAX_AGE_S = 20 * 60       # an action not started this long after `issued_utc` is skipped as stale
HARD_MAX_AGE_S = 6 * 3600         # `max_age_min` may stretch that to at most 6 h
FUTURE_SKEW_S = 5 * 60            # `issued_utc` more than this in the future: refused (clock problem)
SLEEP_GAP_S = 5 * 60              # loop paused longer than interval + this (sleep): queued actions dropped
STOP_GRACE_S = 15 * 60            # STOP present this long and the program still runs: interrupt it
INT_GRACE_S = 120                 # after SIGINT: wait this long, then SIGTERM ...
TERM_GRACE_S = 60                 # ... then SIGKILL
QUICK_TIMEOUT_S = 180             # status / auth / cancel / report
SELFTEST_TIMEOUT_S = 900
GIT_TIMEOUT_S = 30                # one git call; a network blackhole must not stall supervision for long
PUBLISH_BACKOFF_S = 5 * 60        # after a failed report push: the next try at most this often
GIT_NO_HOOKS = ("-c", "core.hooksPath=/dev/null")   # every git call: no hook from any tree ever runs
CONTROL_MAX_BYTES = 64 * 1024
ARMED_MAX_BYTES = 4096
MAX_ACTIONS = 10
MAX_SEQ = 10**9
MAX_SEQ_JUMP = 100_000            # a seq further ahead of the last one is refused without being consumed
BALANCE_JUMP_TOLERANCE = Decimal("1.00")   # balance rise beyond the records' change: flagged (deposit?)
DAY_OPEN_CARRY_S = 3600           # a reading this recent from the previous UTC day opens the new day
MAX_EVENTS = 200
REPORT_EVENTS = 30
TAIL_LINES = 60
REPORT_TAIL_LINES = 150
HARD_MAX_TOTAL_LOSS = Decimal("300")      # ARMED above this is treated as a typo: not armed
DEFAULT_MILESTONE_STEP = Decimal("100")
EXP_BIDS_CONFIGS = ("tails", "pairs", "late-tail")    # the shipped files pilot/experiments/<name>.json
EXP_BIDS_MAX_WINDOWS = 36                             # 3 hours of 5-minute windows
EXP_BIDS_STEP_WORST = Decimal("5.00")                 # exp_bids.MAX_WINDOW_NOTIONAL: worst loss of one window
EXP_FAV_TICKETS = (5, 10)
EXP_FAV_MAX_HOURS = 12
GIT_IDENT = ["-c", "user.name=pm-operator", "-c", "user.email=pm-operator@localhost.invalid",
             "-c", "commit.gpgsign=false"]
PROGRAM_FILES = {"smoke": "smoke.py", "exp_bids": "exp_bids.py", "exp_fav": "exp_fav.py"}
PY_FLAGS = ("-I", "-B", "-u")    # isolated (no folder on the path, no PYTHON* variables), no .pyc files, unbuffered
BALANCE_SOURCE = ("smoke", "auth")   # the only output trusted as the CURRENT balance (read right then)
BALANCE_RES = [re.compile(r"collateral \(pUSD\) balance:\s*([0-9]+(?:\.[0-9]+)?)"),   # smoke.py auth
               re.compile(r"pUSD balance\s+([0-9]+(?:\.[0-9]+)?)"),                    # exp_bids.py run
               re.compile(r"\bBALANCE_USD[=:]\s*([0-9]+(?:\.[0-9]+)?)")]               # any program


class Bad(Exception):
    """An action, a control file or a gate refused. The text goes into the report (scrubbed)."""


def utc(ts: float | None) -> str | None:
    return None if ts is None else datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_of(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def parse_utc(s) -> float:
    if not isinstance(s, str):
        raise Bad("issued_utc must be a string like 2026-11-28T09:00:00Z")
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        raise Bad("issued_utc must look like 2026-11-28T09:00:00Z (UTC)") from None


def money(x) -> str:
    return f"{Decimal(x):.2f}"


def short(x) -> str:
    try:
        s = repr(x)
    except (RecursionError, ValueError, MemoryError):    # deeply nested or a huge integer from the control file
        return f"<{type(x).__name__}>"
    return s if len(s) <= 40 else s[:37] + "..."


# ----------------------------------------------------------------------------- whitelist
@dataclass(frozen=True)
class Param:
    kind: str                     # bool | int | enum | money
    required: bool = False
    default: object = None
    lo: object = None
    hi: object = None
    choices: tuple = ()


@dataclass(frozen=True)
class Spec:
    kind: str                     # offline | read | reduce | run | op
    params: dict
    argv: object                  # (pilot_dir, params) -> list[str] after the program path
    timeout: object               # params -> seconds
    step_worst: object = None     # params -> Decimal: worst loss of one step of a live run
    help_tokens: tuple = ()       # a run's `--help` must show these, or the program is not what we expect


def _bids_run_argv(pilot: Path, p: dict) -> list[str]:
    a = ["run", "--config", str(pilot / "experiments" / f"{p['config']}.json"), "--max-windows", str(p["windows"])]
    return a + (["--live"] if p["live"] else [])


def _fav_run_argv(pilot: Path, p: dict) -> list[str]:
    a = ["run", "--ticket", str(p["ticket"]), "--hours", str(p["hours"])]
    return a + (["--live"] if p["live"] else [])


SPECS: dict[tuple[str, str], Spec] = {
    ("smoke", "status"): Spec("read", {}, lambda d, p: ["status", "--live"], lambda p: QUICK_TIMEOUT_S),
    ("smoke", "auth"): Spec("read", {}, lambda d, p: ["auth", "--live"], lambda p: QUICK_TIMEOUT_S),
    ("smoke", "cancel"): Spec("reduce", {}, lambda d, p: ["cancel", "--live"], lambda p: QUICK_TIMEOUT_S),
    ("smoke", "selftest"): Spec("offline", {}, lambda d, p: ["selftest"], lambda p: SELFTEST_TIMEOUT_S),
    ("exp_bids", "run"): Spec(
        "run",
        {"config": Param("enum", required=True, choices=EXP_BIDS_CONFIGS),
         "windows": Param("int", required=True, lo=1, hi=EXP_BIDS_MAX_WINDOWS),
         "live": Param("bool", default=False)},
        _bids_run_argv, lambda p: p["windows"] * 300 + 1800,
        step_worst=lambda p: EXP_BIDS_STEP_WORST, help_tokens=("--config", "--max-windows", "--live")),
    ("exp_bids", "report"): Spec(
        "offline", {"dry_run": Param("bool", default=False)},
        lambda d, p: ["report"] + (["--dry-run"] if p["dry_run"] else []), lambda p: QUICK_TIMEOUT_S),
    ("exp_bids", "selftest"): Spec("offline", {}, lambda d, p: ["selftest"], lambda p: SELFTEST_TIMEOUT_S),
    ("exp_fav", "run"): Spec(
        "run",
        {"ticket": Param("enum", required=True, choices=EXP_FAV_TICKETS),
         "hours": Param("int", required=True, lo=1, hi=EXP_FAV_MAX_HOURS),
         "live": Param("bool", default=False)},
        _fav_run_argv, lambda p: p["hours"] * 3600 + 1800,
        step_worst=lambda p: Decimal(p["ticket"]), help_tokens=("--ticket", "--hours", "--live")),
    ("exp_fav", "report"): Spec("offline", {}, lambda d, p: ["report"], lambda p: QUICK_TIMEOUT_S),
    ("exp_fav", "selftest"): Spec("offline", {}, lambda d, p: ["selftest"], lambda p: SELFTEST_TIMEOUT_S),
    ("operator", "stop_all"): Spec("op", {}, None, None),
    ("operator", "disarm"): Spec("op", {}, None, None),
    ("operator", "set_limits"): Spec(
        "op", {"max_total_loss_usd": Param("money", lo=Decimal("0.01"), hi=HARD_MAX_TOTAL_LOSS),
               "max_daily_loss_usd": Param("money", lo=Decimal("0.01"), hi=HARD_MAX_TOTAL_LOSS)}, None, None),
    ("operator", "report"): Spec("op", {}, None, None),
}
# risk-reducing built-ins: they run even when stale, future-dated or next to an invalid action
ALWAYS_OPS = {("operator", "stop_all"), ("operator", "disarm"), ("operator", "set_limits")}
# from a file whose seq is invalid or jumps too far: only these two run (set_limits needs a valid seq)
SALVAGE_OPS = {("operator", "stop_all"), ("operator", "disarm")}
ACTION_KEYS = {"id", "program", "cmd", "params", "max_age_min"}
CONTROL_KEYS = {"seq", "issued_utc", "note", "actions"}
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}")


def check_param(name: str, p: Param, v):
    if p.kind == "bool":
        if type(v) is not bool:
            raise Bad(f"{name} must be true or false, got {short(v)}")
        return v
    if p.kind == "int":
        if type(v) is not int:
            raise Bad(f"{name} must be a whole number, got {short(v)}")
        if not p.lo <= v <= p.hi:
            raise Bad(f"{name} must be {p.lo}-{p.hi}, got {v}")
        return v
    if p.kind == "enum":
        if type(v) not in (str, int) or type(v) is bool or v not in p.choices:
            raise Bad(f"{name} must be one of {list(p.choices)}, got {short(v)}")
        if type(v) is not type(p.choices[0]):
            raise Bad(f"{name} must be one of {list(p.choices)}, got {short(v)}")
        return v
    if p.kind == "money":
        if type(v) not in (int, float, str) or type(v) is bool:
            raise Bad(f"{name} must be a number of USD, got {short(v)}")
        try:
            d = Decimal(str(v))
        except InvalidOperation:
            raise Bad(f"{name} must be a number of USD, got {short(v)}") from None
        if not d.is_finite() or not p.lo <= d <= p.hi:
            raise Bad(f"{name} must be {p.lo}-{p.hi} USD, got {short(v)}")
        return str(d.quantize(Decimal("0.01"), rounding=ROUND_FLOOR))
    raise Bad("internal: unknown parameter kind")


def validate_action(raw, idx: int, seq: int) -> dict:
    if not isinstance(raw, dict):
        raise Bad(f"action {idx + 1} is not an object")
    extra = set(raw) - ACTION_KEYS
    if extra:
        raise Bad(f"action {idx + 1}: keys not allowed: {sorted(map(short, extra))}")
    prog, cmd = raw.get("program"), raw.get("cmd")
    if not isinstance(prog, str) or not isinstance(cmd, str) or (prog, cmd) not in SPECS:
        raise Bad(f"action {idx + 1}: {short(prog)} {short(cmd)} is not on the whitelist")
    spec = SPECS[(prog, cmd)]
    params = raw.get("params", {})
    if not isinstance(params, dict):
        raise Bad(f"action {idx + 1}: params must be an object")
    extra = set(params) - set(spec.params)
    if extra:
        raise Bad(f"action {idx + 1}: parameters not allowed for {prog} {cmd}: {sorted(map(short, extra))}")
    vals = {}
    for name, p in spec.params.items():
        if name in params:
            try:
                vals[name] = check_param(name, p, params[name])
            except Bad as e:
                raise Bad(f"action {idx + 1}: {e}") from None
        elif p.required:
            raise Bad(f"action {idx + 1}: {prog} {cmd} needs {name}")
        else:
            vals[name] = p.default
    if (prog, cmd) == ("operator", "set_limits") and all(v is None for v in vals.values()):
        raise Bad(f"action {idx + 1}: set_limits needs max_total_loss_usd and/or max_daily_loss_usd")
    aid = raw.get("id", f"{seq}.{idx + 1}")
    if not isinstance(aid, str) or not ID_RE.fullmatch(aid):
        raise Bad(f"action {idx + 1}: id must be 1-40 characters of letters, digits, '_', '.', '-'")
    age = DEFAULT_MAX_AGE_S
    if "max_age_min" in raw:
        m = raw["max_age_min"]
        if type(m) is not int or not 1 <= m <= HARD_MAX_AGE_S // 60:
            raise Bad(f"action {idx + 1}: max_age_min must be a whole number 1-{HARD_MAX_AGE_S // 60}")
        age = m * 60
    return {"id": aid, "program": prog, "cmd": cmd, "params": vals, "max_age_s": age}


def parse_control(blob: bytes, any_seq: bool = False) -> dict:
    """Structure of the control file. With any_seq=True an invalid seq is returned as None instead of refused
    (used only to salvage stop_all / disarm from a file whose only fault is its seq)."""
    if len(blob) > CONTROL_MAX_BYTES:
        raise Bad(f"control file is {len(blob)} bytes, more than {CONTROL_MAX_BYTES}")
    try:
        obj = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as e:   # JSONDecodeError is a ValueError; so is
        raise Bad(f"control file is not valid JSON ({type(e).__name__})") from None  # a 5000-digit integer
    if not isinstance(obj, dict):
        raise Bad("control file must be a JSON object")
    extra = set(obj) - CONTROL_KEYS
    if extra:
        raise Bad(f"control file: keys not allowed: {sorted(map(short, extra))}")
    seq = obj.get("seq")
    if type(seq) is not int or not 1 <= seq <= MAX_SEQ:
        if not any_seq:
            raise Bad(f"seq must be a whole number 1-{MAX_SEQ}, got {short(seq)}")
        seq = None
    issued = parse_utc(obj.get("issued_utc"))
    note = obj.get("note", "")
    if not isinstance(note, str) or len(note) > 500:
        raise Bad("note must be a string of at most 500 characters")
    acts = obj.get("actions")
    if not isinstance(acts, list) or not 1 <= len(acts) <= MAX_ACTIONS:
        raise Bad(f"actions must be a list of 1-{MAX_ACTIONS} actions")
    return {"seq": seq, "issued_ts": issued, "note": note, "actions": acts}


def validate_control(blob: bytes) -> tuple[dict, list[dict]]:
    ctl = parse_control(blob)
    acts = [validate_action(a, i, ctl["seq"]) for i, a in enumerate(ctl["actions"])]
    ids = [a["id"] for a in acts]
    if len(set(ids)) != len(ids):
        raise Bad("action ids must be unique within one control file")
    for a in acts:
        a["seq"], a["issued_ts"] = ctl["seq"], ctl["issued_ts"]
    return ctl, acts


def is_live(act: dict) -> bool:
    return SPECS[(act["program"], act["cmd"])].kind == "run" and act["params"].get("live") is True


def describe(act: dict) -> str:
    ps = " ".join(f"{k}={'yes' if v is True else 'no' if v is False else v}"
                  for k, v in act["params"].items() if v is not None)
    return f"{act['program']} {act['cmd']}" + (f" {ps}" if ps else "")


def build_argv(python: str, pilot: Path, act: dict) -> list[str]:
    spec = SPECS[(act["program"], act["cmd"])]
    return [python, *PY_FLAGS, str(pilot / PROGRAM_FILES[act["program"]])] + spec.argv(pilot, act["params"])


# ----------------------------------------------------------------------------- scrubbing
URL_RE = re.compile(r"(?i)\b(?:https?|ssh|git|file)://[^\s'\"<>]+|\b[\w.-]+@[\w.-]+:[\w./~-]+")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
HOMEPATH_RE = re.compile(r"/(?:Users|home|root)(?:/[^/\s'\"]+)?")
ADDRESS_RE = re.compile(r"(?i)(?<![0-9a-z])0x[0-9a-f]{40}(?![0-9a-z])")
LONGHEX_RE = re.compile(r"(?i)(?<![0-9a-z])(?:0x)?[0-9a-f]{32,}(?![0-9a-z])")
TOKEN_RE = re.compile(r"(?<![A-Za-z0-9+/=_-])(?=[A-Za-z0-9+/=_-]*[A-Za-z])(?=[A-Za-z0-9+/=_-]*[0-9])"
                      r"[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-])")
PLACEHOLDERS = ("<user>", "<host>", "<address>", "<hex>", "<token>", "<url>", "<email>", "<repo>")
SCRUB_MAX_PASSES = 8


class Scrubber:
    """Everything bound for a report passes through this: identity, paths, addresses, secrets-like strings."""

    def __init__(self, repo: Path | None = None) -> None:
        lits: list[tuple[str, str]] = []
        home = str(Path.home())
        if len(home) > 1:
            lits.append((home, "~"))
        try:
            lits.append((os.path.realpath(home), "~"))
        except OSError:
            pass
        names = {getpass.getuser(), Path.home().name}
        for n in names:
            if n and len(n) >= 3:
                lits.append((n, "<user>"))
        host = socket.gethostname()
        for h in {host, host.split(".")[0]}:
            if h and len(h) >= 3:
                lits.append((h, "<host>"))
        w = os.environ.get("PM_WALLET", "").strip()
        if len(w) >= 8:
            lits.append((w, "<address>"))
        if repo is not None:
            # the checkout may live outside the home folder (/Volumes/<name>/...): its path is scrubbed too
            for r in {str(repo), os.path.realpath(str(repo)), str(Path(repo).resolve())}:
                if len(r) >= 5:
                    lits.append((r, "<repo>"))
            for k in ("user.name", "user.email"):
                try:
                    v = subprocess.run(["git", "-C", str(repo), "config", "--get", k], capture_output=True,
                                       text=True, timeout=10).stdout.strip()
                except (OSError, subprocess.SubprocessError):
                    v = ""
                if len(v) >= 3:
                    lits.append((v, "<user>"))
        lits.sort(key=lambda t: -len(t[0]))
        self.literals = [(re.compile(r"(?<![A-Za-z0-9])" + re.escape(s) + r"(?![A-Za-z0-9])", re.I), r)
                         for s, r in lits]

    def _once(self, t: str) -> str:
        t = URL_RE.sub("<url>", t)
        t = EMAIL_RE.sub("<email>", t)
        for rx, rep in self.literals:
            t = rx.sub(rep, t)
        t = HOMEPATH_RE.sub("~", t)
        t = ADDRESS_RE.sub("<address>", t)
        t = LONGHEX_RE.sub("<hex>", t)
        t = TOKEN_RE.sub("<token>", t)
        return t

    def __call__(self, text) -> str:
        # one pass can create a new match ("/homehttps://x" -> "~https://x"): repeat until nothing changes
        t = str(text)
        for _ in range(SCRUB_MAX_PASSES):
            n = self._once(t)
            if n == t:
                break
            t = n
        return t

    def leaks(self, text) -> list[str]:
        t = str(text)
        for ph in PLACEHOLDERS:                  # a user called "user" or a host called "host" is not a leak
            t = t.replace(ph, " ")
        found = []
        for name, rx in (("url", URL_RE), ("email", EMAIL_RE), ("home path", HOMEPATH_RE),
                         ("address", ADDRESS_RE), ("long hex", LONGHEX_RE), ("token", TOKEN_RE)):
            if rx.search(t):
                found.append(name)
        for rx, rep in self.literals:
            if rx.search(t):
                found.append(rep)
        return found

    def obj(self, o):
        if isinstance(o, str):
            return self(o)
        if isinstance(o, list):
            return [self.obj(x) for x in o]
        if isinstance(o, dict):
            return {k: self.obj(v) for k, v in o.items()}
        return o

    def obj_leaks(self, o) -> list[str]:
        if isinstance(o, str):
            return self.leaks(o)
        if isinstance(o, list):
            return [x for v in o for x in self.obj_leaks(v)]
        if isinstance(o, dict):
            return [x for k, v in o.items() for x in self.leaks(k) + self.obj_leaks(v)]
        return []


# ----------------------------------------------------------------------------- small helpers
def acquire_lock(path: Path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    f = open(path, "a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    return f


def lock_is_held(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with open(path, "a") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(f, fcntl.LOCK_UN)
    except OSError:
        return False
    return False


def tail(path: Path, n: int) -> list[str]:
    try:
        data = path.read_bytes()[-200_000:]
    except OSError:
        return []
    lines = data.decode("utf-8", "replace").splitlines()
    return [ln[:300] for ln in lines[-n:]]


def last_balance(lines: list[str]) -> Decimal | None:
    found = None
    for ln in lines:
        for rx in BALANCE_RES:
            for m in rx.finditer(ln):
                found = Decimal(m.group(1))
    return found


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class GitError(Exception):
    pass


def fav_trades(rows: list[dict], since: float | None) -> list[tuple[str | None, str, Decimal]]:
    """exp_fav.py records -> (day, "realised" | "at_risk", USD), mirroring exp_fav's own build_ledger.

    A trade is a `decision` with sent != false, its first `order` (a later `late-check` order row replaces the
    fill), and its first `result`. Filled: cost includes the fee; won pays 1 per share. Fill unknown: lost
    costs the whole ticket, won counts 0 (cannot be worse), unresolved counts the whole ticket at risk.
    """
    by: dict = defaultdict(dict)
    for r in rows:
        typ, k = r.get("type"), r.get("key")
        if typ not in ("decision", "order", "result") or not k:
            continue
        if typ == "decision" and r.get("sent") is False:
            continue
        if typ == "order" and r.get("post") == "late-check" and "order" in by[k]:
            by[k]["order"] = {**by[k]["order"], **{x: r.get(x) for x in ("fill_state", "filled_shares", "cost")}}
            continue
        by[k].setdefault(typ, r)
    out = []
    for k, g in by.items():
        dec = g.get("decision")
        if dec is None:
            continue
        t = dec.get("t")
        if since is not None and isinstance(t, (int, float)) and t < since - 60:
            continue
        ticket = Decimal(str(dec.get("ticket") or "10"))
        o = g.get("order")
        state = (o or {}).get("fill_state", "unknown") if o is not None else "unknown"
        if state not in ("filled", "unknown"):
            continue                                        # unfilled, rejected, dry-run: no money moved
        cost = Decimal(str(o["cost"])) if state == "filled" and o.get("cost") is not None else ticket
        shares = Decimal(str(o["filled_shares"])) if state == "filled" and o.get("filled_shares") is not None else None
        res = g.get("result")
        day = dec.get("day")
        if res is None or res.get("winner") is None:
            out.append((day, "at_risk", cost))
        elif res.get("winner_is_split"):
            out.append((day, "realised", (shares * Decimal("0.5") - cost) if shares is not None else -ticket))
        elif res["winner"] == dec.get("outcome"):
            out.append((day, "realised", (shares - cost) if shares is not None else Decimal(0)))
        else:
            out.append((day, "realised", -cost))
    return out


# ----------------------------------------------------------------------------- the operator
class Operator:
    def __init__(self, pilot: Path, repo: Path, state_dir: Path, now=time.time, interval: int = POLL_S,
                 say=print) -> None:
        self.pilot, self.repo, self.sd = Path(pilot), Path(repo), Path(state_dir)
        self.now, self.interval, self.say = now, interval, say
        self.sd.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.stop_file = self.sd / "STOP"
        self.armed_file = self.sd / "ARMED"
        self.state_path = self.sd / "operator-state.json"
        self.lock_path = self.sd / "operator.lock"
        self.logs = self.sd / "operator-logs"
        self.bids_lock = self.sd / "exp_bids.live.lock"
        self.fav_lock = self.sd / "exp_fav.lock"
        venv = self.pilot / ".venv" / "bin" / "python"
        self.python = str(venv) if venv.exists() else sys.executable
        self.scrub = Scrubber(self.repo)
        self.child: dict | None = None
        self.quit = False
        self.st = self.load_state()

    # ------------------------------------------------------------------ state
    def default_state(self) -> dict:
        return {"version": 1, "last_seq": 0, "last_seq_issued_utc": None, "last_blob": None, "queue": [],
                "running": None, "events": [], "baseline": None, "balance": None, "day_open": None,
                "lowered": None, "limit_hit": None, "last_cycle": None, "last_publish": 0, "dirty": True,
                "help_cache": {}, "last_balance_probe": 0, "report_error": None, "control_error": None,
                "milestones_reached": 0, "control_note": "", "publish_failed_at": None, "cycle_error": None}

    def load_state(self) -> dict:
        st = self.default_state()
        if self.state_path.exists():
            try:
                st.update(json.loads(self.state_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as e:
                # a broken state file must not let an old sequence number run again: refuse to start
                raise SystemExit(f"operator: state file {self.state_path} unreadable ({type(e).__name__}); "
                                 f"fix or move it by hand. Not starting.") from None
        return st

    def save_state(self) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.st, f, indent=1, sort_keys=True, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.state_path)

    def event(self, outcome: str, what: str, **kw) -> None:
        e = {"utc": utc(self.now()), "outcome": outcome, "what": what}
        e.update({k: v for k, v in kw.items() if v is not None})
        self.st["events"].append(e)
        self.st["events"] = self.st["events"][-MAX_EVENTS:]
        self.st["dirty"] = True
        self.say(f"[{e['utc']}] {outcome}: {what}" + (f" ({kw['reason']})" if kw.get("reason") else ""))

    # ------------------------------------------------------------------ ARMED and limits
    def read_armed(self) -> dict:
        res = {"ok": False, "reason": "", "fp": None, "total": None, "daily": None, "baseline": None,
               "milestone": DEFAULT_MILESTONE_STEP}
        p = self.armed_file
        if not p.exists():
            res["reason"] = "no ARMED file"
            return res
        try:
            st = os.lstat(p)
        except OSError as e:
            res["reason"] = f"ARMED unreadable ({type(e).__name__})"
            return res
        import stat as _stat
        if not _stat.S_ISREG(st.st_mode):
            res["reason"] = "ARMED is not a regular file"
            return res
        if st.st_mode & 0o022:
            res["reason"] = "ARMED is writable by group or others (chmod 600 it)"
            return res
        if hasattr(os, "getuid") and st.st_uid != os.getuid():
            res["reason"] = "ARMED is not owned by the current user"
            return res
        if st.st_size > ARMED_MAX_BYTES:
            res["reason"] = "ARMED is too large"
            return res
        raw = p.read_bytes()
        res["fp"] = hashlib.sha256(raw).hexdigest()
        vals = {}
        allowed = {"max_total_loss_usd", "max_daily_loss_usd", "baseline_balance_usd", "milestone_step_usd"}
        for ln in raw.decode("utf-8", "replace").splitlines():
            ln = ln.split("#", 1)[0].strip()
            if not ln:
                continue
            m = re.fullmatch(r"([a-z_]+)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)", ln)
            if not m or m.group(1) not in allowed or m.group(1) in vals:
                res["reason"] = f"ARMED line not understood: {ln[:60]!r}"
                return res
            vals[m.group(1)] = Decimal(m.group(2))
        if "max_total_loss_usd" not in vals or "max_daily_loss_usd" not in vals:
            res["reason"] = "ARMED needs max_total_loss_usd and max_daily_loss_usd"
            return res
        t, d = vals["max_total_loss_usd"], vals["max_daily_loss_usd"]
        if not Decimal("1") <= t <= HARD_MAX_TOTAL_LOSS:
            res["reason"] = f"max_total_loss_usd must be 1-{HARD_MAX_TOTAL_LOSS}"
            return res
        if not Decimal("1") <= d <= t:
            res["reason"] = "max_daily_loss_usd must be at least 1 and not above max_total_loss_usd"
            return res
        if "milestone_step_usd" in vals and vals["milestone_step_usd"] < 1:
            res["reason"] = "milestone_step_usd must be at least 1"
            return res
        res.update(ok=True, total=t, daily=d, baseline=vals.get("baseline_balance_usd"),
                   milestone=vals.get("milestone_step_usd", DEFAULT_MILESTONE_STEP))
        return res

    def limits(self, a: dict) -> dict:
        if not a["ok"]:
            return {}
        tot, daily = a["total"], a["daily"]
        lw = self.st.get("lowered")
        if lw and lw.get("fp") == a["fp"]:
            if lw.get("total") is not None:
                tot = min(tot, Decimal(lw["total"]))
            if lw.get("daily") is not None:
                daily = min(daily, Decimal(lw["daily"]))
        daily = min(daily, tot)
        p = self.pnl()
        return {"armed_total_usd": a["total"], "armed_daily_usd": a["daily"], "total_usd": tot,
                "daily_usd": daily, "left_total_usd": tot - p["loss_total_usd"],
                "left_today_usd": daily - p["loss_today_usd"]}

    # ------------------------------------------------------------------ profit and loss
    def ledger(self) -> dict:
        """Live record files of the programs (exp_bids schema; exp_fav is read the same way if it follows it).

        realised = sum of `pnl` of resolved orders; at risk = cost of filled but unresolved orders plus the
        full notional of orders sent without a final record (interrupted session): the worst case.
        """
        since = (self.st.get("baseline") or {}).get("ts")
        today = day_of(self.now())
        placed: dict = {}
        final: dict = {}
        bad = 0
        fav_rows: list[dict] = []
        for f in sorted((self.pilot / "out").glob("*.jsonl")):
            if f.name.endswith(".dryrun.jsonl"):
                continue
            if f.name.startswith("exp-fav-"):                # exp_fav.py has its own schema: read below
                try:
                    for ln in f.read_text(encoding="utf-8").splitlines():
                        if ln.strip():
                            try:
                                r = json.loads(ln)
                            except json.JSONDecodeError:
                                bad += 1
                                continue
                            if isinstance(r, dict) and r.get("mode") in (None, "live"):
                                fav_rows.append(r)
                except OSError:
                    pass
                continue
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for ln in lines:
                if not ln.strip():
                    continue
                try:
                    r = json.loads(ln)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                if not isinstance(r, dict) or r.get("mode") not in (None, "live"):
                    continue
                ws = r.get("window_start")
                if since is not None and isinstance(ws, (int, float)) and ws < since - 60:
                    continue
                k = (f.name.split("-")[0], r.get("exp"), r.get("key"))
                if r.get("type") == "placed":
                    placed[k] = r
                elif r.get("type") == "order":
                    final[k] = r
        out = {"realised_total": Decimal(0), "at_risk_total": Decimal(0), "realised_today": Decimal(0),
               "at_risk_today": Decimal(0), "unreadable": bad}

        def add(kind, r, amount):
            out[f"{kind}_total"] += amount
            if r.get("day") in (None, today):
                out[f"{kind}_today"] += amount

        for k, r in final.items():
            try:
                if r.get("pnl") is not None:
                    add("realised", r, Decimal(str(r["pnl"])))
                elif r.get("cost") is not None:
                    if Decimal(str(r["cost"])) > 0:
                        add("at_risk", r, Decimal(str(r["cost"])))
                else:                        # cost unknown (e.g. exp_bids post-error): the full order counts
                    n = r.get("notional") or (placed.get(k) or {}).get("notional") or "0"
                    add("at_risk", r, Decimal(str(n)))
            except InvalidOperation:
                bad += 1
        for k, r in placed.items():
            if k not in final:
                try:
                    add("at_risk", r, Decimal(str(r.get("notional", "0"))))
                except InvalidOperation:
                    bad += 1
        for day, kind, amount in fav_trades(fav_rows, since):
            add(kind, {"day": day}, amount)
        out["unreadable"] = bad
        return out

    def pnl(self) -> dict:
        lg = self.ledger()
        bal = self.st.get("balance") or {}
        base = self.st.get("baseline") or {}
        dop = self.st.get("day_open") or {}
        cur = Decimal(bal["usd"]) if bal.get("usd") is not None else None
        cash_tot = cur - Decimal(base["usd"]) if cur is not None and base.get("usd") is not None else None
        today = day_of(self.now())
        cash_day = (cur - Decimal(dop["usd"]) if cur is not None and dop.get("day") == today
                    and dop.get("usd") is not None else None)
        ledger_loss_tot = max(Decimal(0), -lg["realised_total"] + lg["at_risk_total"])
        ledger_loss_day = max(Decimal(0), -lg["realised_today"] + lg["at_risk_today"])
        loss_tot = max(ledger_loss_tot, -cash_tot if cash_tot is not None else Decimal(0), Decimal(0))
        loss_day = max(ledger_loss_day, -cash_day if cash_day is not None else Decimal(0), Decimal(0))
        return {"balance_usd": None if cur is None else cur, "balance_utc": bal.get("utc"),
                "baseline_usd": base.get("usd"), "baseline_utc": utc(base.get("ts")),
                "day_open_usd": dop.get("usd") if dop.get("day") == today else None,
                "cash_change_total_usd": cash_tot, "cash_change_today_usd": cash_day,
                "ledger_realised_total_usd": lg["realised_total"], "ledger_at_risk_total_usd": lg["at_risk_total"],
                "ledger_realised_today_usd": lg["realised_today"], "ledger_at_risk_today_usd": lg["at_risk_today"],
                "ledger_unreadable_lines": lg["unreadable"], "loss_total_usd": loss_tot, "loss_today_usd": loss_day}

    def note_balance(self, bal: Decimal) -> None:
        now = self.now()
        prev = self.st.get("balance") or {}
        lg = self.ledger()
        net = lg["realised_total"] - lg["at_risk_total"]       # what the records say cash should have moved by
        if prev.get("usd") is not None and prev.get("ledger_net") is not None:
            d_bal = bal - Decimal(prev["usd"])
            d_led = net - Decimal(prev["ledger_net"])
            if d_bal > BALANCE_JUMP_TOLERANCE and d_bal - d_led > BALANCE_JUMP_TOLERANCE:
                # a deposit raises the balance-based measure and would hide losses and post a false milestone
                self.event("warning", "balance rose more than the programs' records explain",
                           reason=f"balance +{money(d_bal)}, records {money(d_led)} USD: a deposit or redeemed "
                                  f"winnings; after a deposit the owner writes baseline_balance_usd in ARMED")
        self.st["balance"] = {"usd": str(bal), "utc": utc(now), "ts": now, "ledger_net": str(net)}
        today = day_of(now)
        if (self.st.get("day_open") or {}).get("day") != today:
            # the day opens at the last reading before midnight when it is recent (a live run crossing midnight),
            # so losses between midnight and the first reading of the day still count toward the new day
            carry = (prev.get("usd") is not None and isinstance(prev.get("ts"), (int, float))
                     and day_of(prev["ts"]) != today and now - prev["ts"] <= DAY_OPEN_CARRY_S)
            self.st["day_open"] = {"day": today, "usd": prev["usd"] if carry else str(bal)}
        a = self.read_armed()
        if a["ok"]:
            base = self.st.get("baseline")
            if a["baseline"] is not None and (not base or Decimal(base["usd"]) != a["baseline"]):
                self.st["baseline"] = {"usd": str(a["baseline"]), "ts": (base or {}).get("ts", now),
                                       "source": "ARMED"}
            elif not base:
                self.st["baseline"] = {"usd": str(bal), "ts": now, "source": "first balance after arming"}
        self.st["dirty"] = True

    def balance_probe(self, why: str) -> Decimal | None:
        self.st["last_balance_probe"] = self.now()
        if not (self.pilot / PROGRAM_FILES["smoke"]).exists():
            return None
        act = {"id": "balance", "program": "smoke", "cmd": "auth", "params": {}}
        rc, lines, bal, _ = self.run_quick(act)
        if rc != 0 or bal is None:
            self.event("failed", f"balance check ({why})", exit=rc, reason="no balance in the output",
                       tail=[self.scrub(x) for x in lines[-10:]])
            return None
        self.note_balance(bal)
        return bal

    # ------------------------------------------------------------------ programs
    def child_env(self) -> dict:
        env = dict(os.environ)
        return env

    def run_quick(self, act: dict, timeout: int | None = None):
        argv = build_argv(self.python, self.pilot, act)
        timeout = timeout or SPECS[(act["program"], act["cmd"])].timeout(act["params"])
        self.logs.mkdir(mode=0o700, parents=True, exist_ok=True)
        log = self.logs / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{act['id']}.log"
        with open(log, "wb") as f:
            p = subprocess.Popen(argv, cwd=self.pilot, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                                 env=self.child_env(), start_new_session=True)
            try:
                rc = p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._signal(p.pid, signal.SIGINT)
                try:
                    rc = p.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self._signal(p.pid, signal.SIGKILL)
                    rc = p.wait()
                f.write(f"\n[operator] timeout after {timeout} s: interrupted\n".encode())
        lines = tail(log, REPORT_TAIL_LINES)
        return rc, lines, last_balance(lines), log

    def _signal(self, pid: int, sig) -> None:
        try:
            os.killpg(pid, sig)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass

    def help_ok(self, act: dict) -> None:
        spec = SPECS[(act["program"], act["cmd"])]
        prog = self.pilot / PROGRAM_FILES[act["program"]]
        if not prog.exists():
            raise Bad(f"{prog.name} is not installed on this Mac")
        if not spec.help_tokens:
            return
        digest = hashlib.sha256(prog.read_bytes()).hexdigest()
        key = f"{act['program']}.{act['cmd']}.{digest}"
        cached = self.st["help_cache"].get(key)
        if cached is None:
            try:
                r = subprocess.run([self.python, *PY_FLAGS, str(prog), act["cmd"], "--help"], cwd=self.pilot,
                                   capture_output=True, text=True, timeout=60, env=self.child_env())
                text = r.stdout + r.stderr
            except (OSError, subprocess.SubprocessError) as e:
                text = f"{type(e).__name__}"
            missing = [t for t in spec.help_tokens if t not in text]
            cached = missing
            hc = {k: v for k, v in self.st["help_cache"].items() if k.split(".")[:2] != key.split(".")[:2]}
            hc[key] = missing
            self.st["help_cache"] = hc
        if cached:
            raise Bad(f"{prog.name} {act['cmd']} --help does not show {cached}: its command line differs from "
                      f"the operator's table; the owner must update operator.py")

    def start_action(self, act: dict) -> None:
        spec = SPECS[(act["program"], act["cmd"])]
        what = describe(act)
        now = self.now()
        age = now - act["issued_ts"]
        if age > act["max_age_s"] and (act["program"], act["cmd"]) not in ALWAYS_OPS:
            self.event("skipped", what, seq=act["seq"], id=act["id"],
                       reason=f"stale: {age / 60:.0f} min after issued_utc, limit {act['max_age_s'] // 60} min")
            return
        if spec.kind == "op":
            return self.run_op(act)
        try:
            if spec.kind == "run" and self.stop_file.exists():
                raise Bad("STOP file present: no program runs are started")
            if act["cmd"] == "selftest" and self.child is not None and self.child["live"]:
                raise Bad("a live program is running: a selftest (up to 15 min) would delay its supervision")
            self.help_ok(act)
            if act["program"] == "exp_bids" and act["cmd"] == "run":
                cfg = self.pilot / "experiments" / f"{act['params']['config']}.json"
                if not cfg.exists():
                    raise Bad(f"config {cfg.name} not found on this Mac")
            if spec.kind == "run" and self.child is not None:
                raise Bad("another program is running")          # process_queue normally waits instead
            if is_live(act):
                self.live_gate(act)
        except Bad as e:
            self.event("refused", what, seq=act["seq"], id=act["id"], reason=str(e))
            return
        if spec.kind == "run":
            return self.start_child(act)
        rc, lines, bal, _ = self.run_quick(act)
        if bal is not None and (act["program"], act["cmd"]) == BALANCE_SOURCE:
            self.note_balance(bal)
        self.event("done" if rc == 0 else "failed", what, seq=act["seq"], id=act["id"], exit=rc,
                   balance_usd=None if bal is None else str(bal),
                   tail=[self.scrub(x) for x in lines[-(REPORT_TAIL_LINES if act["cmd"] == "report" else TAIL_LINES):]])

    def live_gate(self, act: dict) -> None:
        a = self.read_armed()
        if not a["ok"]:
            raise Bad(f"not armed: {a['reason']}")
        if self.stop_file.exists():
            raise Bad("STOP file present")
        if lock_is_held(self.bids_lock):
            raise Bad("a live exp_bids.py session started outside the operator is running")
        if lock_is_held(self.fav_lock):
            raise Bad("an exp_fav.py session started outside the operator is running")
        if self.balance_probe("before a live run") is None:
            raise Bad("balance could not be read with smoke.py auth --live; live run not started")
        a = self.read_armed()
        if not a["ok"]:
            raise Bad(f"not armed: {a['reason']}")
        lim = self.limits(a)
        step = SPECS[(act["program"], act["cmd"])].step_worst(act["params"])
        if lim["left_total_usd"] < step or lim["left_today_usd"] < step:
            raise Bad(f"limits left (total {money(lim['left_total_usd'])}, today {money(lim['left_today_usd'])} USD) "
                      f"are below the worst loss of one step of this program ({money(step)} USD)")

    def start_child(self, act: dict) -> None:
        argv = build_argv(self.python, self.pilot, act)
        self.logs.mkdir(mode=0o700, parents=True, exist_ok=True)
        log = self.logs / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{act['id']}.log"
        f = open(log, "wb")
        try:
            p = subprocess.Popen(argv, cwd=self.pilot, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                                 env=self.child_env(), start_new_session=True)
        finally:
            f.close()
        now = self.now()
        live = is_live(act)
        self.child = {"proc": p, "pid": p.pid, "act": act, "started": now, "log": str(log), "live": live,
                      "timeout_at": now + SPECS[(act["program"], act["cmd"])].timeout(act["params"]),
                      "int_sent": None, "term_sent": None, "kill_sent": None, "stop_seen": None}
        self.st["running"] = {k: v for k, v in self.child.items() if k != "proc"}
        if live:
            self.st["last_balance_probe"] = now
        self.event("started", describe(act), seq=act["seq"], id=act["id"],
                   argv=" ".join(self.rel(x) for x in argv[1:]))
        self.save_state()

    def rel(self, s: str) -> str:
        return s.replace(str(self.pilot) + os.sep, "pilot/")

    def interrupt(self, why: str) -> None:
        c = self.child
        if not c or c["int_sent"]:
            return
        c["int_sent"] = self.now()
        self._signal(c["pid"], signal.SIGINT)
        self.st["running"] = {k: v for k, v in c.items() if k != "proc"}
        self.event("interrupt", describe(c["act"]), seq=c["act"]["seq"], id=c["act"]["id"], reason=why)

    def monitor(self) -> None:
        c = self.child
        if not c:
            return
        if c["proc"] is not None:
            rc = c["proc"].poll()
            alive = rc is None
        else:
            rc, alive = None, pid_alive(c["pid"])
        if not alive:
            return self.finish(rc)
        now = self.now()
        if c["live"]:
            a = self.read_armed()
            if not a["ok"]:
                self.interrupt(f"disarmed: {a['reason']}")
            elif now - self.st.get("last_balance_probe", 0) >= BALANCE_PROBE_S:
                self.balance_probe("during a live run")
        if self.stop_file.exists():
            c["stop_seen"] = c["stop_seen"] or now
            if now - c["stop_seen"] >= STOP_GRACE_S:
                self.interrupt(f"STOP present for {STOP_GRACE_S // 60} min and the program still runs")
        if now >= c["timeout_at"]:
            self.interrupt("ran longer than its bound")
        if c["int_sent"] and not c["term_sent"] and now - c["int_sent"] >= INT_GRACE_S:
            c["term_sent"] = now
            self._signal(c["pid"], signal.SIGTERM)
        if c["term_sent"] and not c["kill_sent"] and now - c["term_sent"] >= TERM_GRACE_S:
            c["kill_sent"] = now
            self._signal(c["pid"], signal.SIGKILL)

    def finish(self, rc) -> None:
        c = self.child
        self.child = None
        self.st["running"] = None
        act = c["act"]
        lines = tail(Path(c["log"]), TAIL_LINES)
        bal = last_balance(lines)            # shown only: a run prints its balance at the start, so it is stale
        outcome = ("done" if rc == 0 else "interrupted" if c["int_sent"] or rc in (130, -2)
                   else "ended" if rc is None else "failed")
        self.event(outcome, describe(act), seq=act["seq"], id=act["id"], exit=rc,
                   minutes=round((self.now() - c["started"]) / 60, 1),
                   reason=None if rc is not None else "exit code unknown (operator restarted meanwhile)",
                   printed_balance_usd=None if bal is None else str(bal), tail=[self.scrub(x) for x in lines])
        if c["live"]:
            self.balance_probe("after a live run")
        self.save_state()

    def recover(self) -> None:
        r = self.st.get("running")
        if not r:
            return
        pid = int(r.get("pid") or 0)
        prog = PROGRAM_FILES.get(r.get("act", {}).get("program"), "?")
        alive = False
        if pid and pid_alive(pid):
            try:
                cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True,
                                     timeout=10).stdout
                alive = prog in cmd
            except (OSError, subprocess.SubprocessError):
                alive = False
        if alive:
            self.child = dict(r, proc=None)
            self.event("adopted", describe(r["act"]), reason="still running from before the operator restart")
        else:
            self.child = dict(r, proc=None)
            self.finish(None)

    # ------------------------------------------------------------------ built-in actions
    def run_op(self, act: dict) -> None:
        cmd, what = act["cmd"], describe(act)
        kw = {"seq": act.get("seq"), "id": act.get("id")}
        if cmd == "stop_all":
            self.write_stop(f"stop_all from control seq {act.get('seq')}")
            for q in self.st["queue"]:
                self.event("skipped", describe(q), seq=q["seq"], id=q["id"], reason="stop_all")
            self.st["queue"] = []
            if self.child:
                self.interrupt("stop_all")
            note = "STOP file created; running program interrupted" if self.child else "STOP file created"
            self.event("done", what, reason=note, **kw)
            if (self.pilot / PROGRAM_FILES["smoke"]).exists():
                a = {"id": f"{act.get('id')}.cancel", "program": "smoke", "cmd": "cancel", "params": {}}
                rc, lines, _, _ = self.run_quick(a)
                self.event("done" if rc == 0 else "failed", "smoke cancel (part of stop_all)", exit=rc,
                           tail=[self.scrub(x) for x in lines[-20:]], **kw)
        elif cmd == "disarm":
            moved = None
            if self.armed_file.exists():
                moved = self.armed_file.with_name(f"ARMED.disarmed-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
                os.replace(self.armed_file, moved)
            if self.child and self.child["live"]:
                self.interrupt("disarm")
            self.event("done", what, reason=f"ARMED moved to {moved.name}" if moved else "was not armed", **kw)
        elif cmd == "set_limits":
            a = self.read_armed()
            if not a["ok"]:
                return self.event("refused", what, reason=f"not armed: {a['reason']}", **kw)
            cur = self.limits(a)
            new_t = act["params"].get("max_total_loss_usd")
            new_d = act["params"].get("max_daily_loss_usd")
            for name, new, old in (("max_total_loss_usd", new_t, cur["total_usd"]),
                                   ("max_daily_loss_usd", new_d, cur["daily_usd"])):
                if new is not None and Decimal(new) > old:
                    return self.event("refused", what, reason=f"{name} {new} is above the current {money(old)}: "
                                                               f"limits can only be lowered", **kw)
            lw = self.st.get("lowered") if (self.st.get("lowered") or {}).get("fp") == a["fp"] else {}
            self.st["lowered"] = {"fp": a["fp"], "total": new_t or (lw or {}).get("total"),
                                  "daily": new_d or (lw or {}).get("daily")}
            lim = self.limits(a)
            self.event("done", what, reason=f"limits now total {money(lim['total_usd'])}, "
                                            f"daily {money(lim['daily_usd'])} USD", **kw)
        elif cmd == "report":
            self.st["dirty"] = True
            self.event("done", what, **kw)

    def write_stop(self, why: str) -> None:
        if not self.stop_file.exists():
            self.stop_file.write_text(f"created by operator.py at {utc(self.now())}: {why}\n"
                                      f"remove this file by hand to allow new runs\n", encoding="utf-8")

    # ------------------------------------------------------------------ limits
    def check_limits(self) -> None:
        a = self.read_armed()
        if not a["ok"]:
            return
        if not self.st.get("baseline") and self.now() - self.st.get("last_balance_probe", 0) >= 300:
            # just armed: read the starting balance now, so the experiment's ledger starts here
            self.balance_probe("armed: starting balance")
        lim = self.limits(a)
        hit = None
        if lim["left_total_usd"] <= 0:
            hit = ("total", lim["total_usd"])
        elif lim["left_today_usd"] <= 0:
            hit = ("daily", lim["daily_usd"])
        if not hit:
            return
        key = f"{hit[0]}:{a['fp']}:{day_of(self.now()) if hit[0] == 'daily' else ''}"
        first = (self.st.get("limit_hit") or {}).get("key") != key
        if first:
            p = self.pnl()
            self.st["limit_hit"] = {"key": key, "kind": hit[0], "utc": utc(self.now()), "limit_usd": money(hit[1]),
                                    "loss_usd": str(p[f"loss_{'total' if hit[0] == 'total' else 'today'}_usd"])}
            self.write_stop(f"{hit[0]} loss limit {money(hit[1])} USD reached")
            self.event("limit", f"{hit[0]} loss limit reached",
                       reason=f"loss {money(self.st['limit_hit']['loss_usd'])} >= limit {money(hit[1])} USD; "
                              f"STOP created")
        if self.child and self.child["live"]:
            self.interrupt(f"{hit[0]} loss limit reached")

    # ------------------------------------------------------------------ control channel
    def git_raw(self, *args, data: bytes = b"", timeout: int = GIT_TIMEOUT_S) -> bytes:
        """git in the main repository, hooks off (a relative core.hooksPath must never pick up a tree's hooks)."""
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
        name = next((x for x in args if not x.startswith("-") and "=" not in x), "?")
        try:
            r = subprocess.run(["git", *GIT_NO_HOOKS, *args], cwd=str(self.repo), input=data, capture_output=True,
                               timeout=timeout, env=env)
        except (OSError, subprocess.SubprocessError) as e:
            raise GitError(f"git {name}: {type(e).__name__}") from None
        if r.returncode != 0:
            msg = (r.stderr or r.stdout).decode("utf-8", "replace").strip().splitlines()
            raise GitError(f"git {name}: " + (msg[-1] if msg else f"exit {r.returncode}"))
        return r.stdout

    def git(self, *args, data: bytes = b"", timeout: int = GIT_TIMEOUT_S) -> str:
        return self.git_raw(*args, data=data, timeout=timeout).decode("utf-8", "replace")

    def fetch_control(self) -> tuple[str, bytes] | None:
        ref = f"refs/remotes/origin/{CONTROL_BRANCH}"
        try:
            self.git("fetch", "--quiet", "--no-tags", "origin", f"+refs/heads/{CONTROL_BRANCH}:{ref}")
        except GitError as e:
            if "couldn't find remote ref" in str(e).lower():
                return None
            raise
        try:
            sha = self.git("rev-parse", "--verify", "--quiet", f"{ref}:{CONTROL_FILE}").strip()
        except GitError:
            return None
        if sha == self.st.get("last_blob"):
            return sha, b""
        try:
            size = int(self.git("cat-file", "-s", sha).strip())
        except ValueError:
            raise GitError("git cat-file: size not understood") from None
        if size > CONTROL_MAX_BYTES:
            return sha, b"x" * (CONTROL_MAX_BYTES + 1)
        return sha, self.git_raw("cat-file", "blob", sha)

    def poll_control(self) -> None:
        try:
            got = self.fetch_control()
        except GitError as e:
            msg = self.scrub(str(e))
            if self.st.get("control_error") != msg:
                self.st["control_error"] = msg
                self.event("error", "fetching the control branch", reason=f"{msg}; retried every cycle")
            return
        if self.st.get("control_error"):
            self.st["control_error"] = None
            self.st["dirty"] = True
        if got is None:
            return
        sha, blob = got
        if sha == self.st.get("last_blob"):
            return
        self.st["last_blob"] = sha
        self.save_state()                         # a blob that crashes anything below is never read again
        try:
            ctl = parse_control(blob)
        except Bad as e:
            self.event("refused", "control file", reason=str(e))
            try:
                lax = parse_control(blob, any_seq=True)
            except Bad:
                return self.save_state()
            return self.salvage(lax, "its seq is invalid")      # the only fault is the seq
        if ctl["seq"] <= self.st["last_seq"]:
            self.save_state()
            return self.event("skipped", f"control seq {ctl['seq']}",
                              reason=f"not newer than the last processed seq {self.st['last_seq']}: not replayed")
        if ctl["seq"] > self.st["last_seq"] + MAX_SEQ_JUMP:
            # a huge seq would burn the number range: refused and NOT consumed (the next normal seq still works)
            self.event("refused", f"control seq {ctl['seq']}",
                       reason=f"more than {MAX_SEQ_JUMP} above the last processed seq {self.st['last_seq']}; "
                              f"not consumed")
            return self.salvage(ctl, "its seq jumps too far")
        self.process_seq(blob, ctl)

    def salvage(self, ctl: dict, why: str) -> None:
        """A file refused only for its seq: carry out its stop_all / disarm (they only reduce risk), nothing else."""
        acts = []
        for i, raw in enumerate(ctl["actions"]):
            try:
                a = validate_action(raw, i, 0)
            except Bad:
                continue
            if (a["program"], a["cmd"]) in SALVAGE_OPS:
                a["seq"], a["issued_ts"] = ctl["seq"], ctl["issued_ts"]
                acts.append(a)
        if acts:
            self.event("received", "control file", reason=f"{why}: only {', '.join(a['cmd'] for a in acts)} "
                                                          f"from it run")
        for a in acts:
            self.start_action(a)
        self.save_state()

    def process_seq(self, blob: bytes, ctl: dict) -> None:
        seq = ctl["seq"]
        # consumed before anything runs: a crash or restart never runs this seq a second time
        self.st["last_seq"] = seq
        self.st["last_seq_issued_utc"] = utc(ctl["issued_ts"])
        self.st["control_note"] = ctl["note"]
        self.save_state()
        err = None
        try:
            _, acts = validate_control(blob)
        except Bad as e:
            err, acts = str(e), []
            for i, raw in enumerate(ctl["actions"]):          # salvage only the risk-reducing built-ins
                try:
                    a = validate_action(raw, i, seq)
                except Bad:
                    continue
                if (a["program"], a["cmd"]) in ALWAYS_OPS:
                    a["seq"], a["issued_ts"] = seq, ctl["issued_ts"]
                    acts.append(a)
        if err is None and ctl["issued_ts"] > self.now() + FUTURE_SKEW_S:
            err = "issued_utc is in the future: check the clocks"
        for q in self.st["queue"]:
            self.event("skipped", describe(q), seq=q["seq"], id=q["id"], reason=f"superseded by seq {seq}")
        self.st["queue"] = []
        if err is not None:
            safe = [a for a in acts if (a["program"], a["cmd"]) in ALWAYS_OPS]
            self.event("refused", f"control seq {seq}",
                       reason=f"{err}; nothing from this seq runs" + (" except stop_all / disarm / set_limits"
                                                                       if safe else ""))
            for a in safe:
                self.start_action(a)
            self.save_state()
            return
        self.event("received", f"control seq {seq}", reason=f"{len(acts)} action(s)")
        for act in acts:
            if act["program"] == "operator":
                self.start_action(act)
            else:
                self.st["queue"].append(act)
        self.save_state()

    def process_queue(self) -> None:
        while self.st["queue"] and not self.quit:
            act = self.st["queue"][0]
            if SPECS[(act["program"], act["cmd"])].kind == "run" and self.child is not None:
                return                      # one program run at a time; quick actions may go meanwhile
            self.st["queue"].pop(0)
            self.save_state()
            self.start_action(act)
            # a quick action can take minutes: ARMED, STOP and the loss limits are checked after each one
            self.monitor()
            self.check_limits()

    # ------------------------------------------------------------------ reports
    def build_report(self) -> tuple[dict, str, str]:
        a = self.read_armed()
        lim = self.limits(a) if a["ok"] else {}
        p = self.pnl()
        cash = p["cash_change_total_usd"]
        # a milestone needs both measures: the balance (a deposit raises it) and the programs' records
        # (realised minus still at risk; a deposit does not move them). The smaller one counts.
        led = p["ledger_realised_total_usd"] - p["ledger_at_risk_total_usd"]
        prof = None if cash is None else min(cash, led)
        step = a["milestone"] if a["ok"] else DEFAULT_MILESTONE_STEP
        reached = int((prof / step).to_integral_value(rounding=ROUND_FLOOR)) if prof is not None and prof > 0 else 0
        if reached > self.st.get("milestones_reached", 0):
            self.st["milestones_reached"] = reached
            self.event("milestone", f"profit passed {money(step * reached)} USD",
                       reason=f"profit {money(prof)} (balance {money(cash)}, records {money(led)})")
        c = self.child
        rep = {
            "operator_version": VERSION,
            "generated_utc": utc(self.now()),
            "armed": a["ok"],
            "armed_reason": None if a["ok"] else a["reason"],
            "stop_file": self.stop_file.exists(),
            "limits": {k: money(v) for k, v in lim.items()},
            "limit_hit": {k: v for k, v in (self.st.get("limit_hit") or {}).items() if k != "key"} or None,
            "pnl": {k: (money(v) if isinstance(v, Decimal) else v) for k, v in p.items()},
            "milestones": {"step_usd": money(step), "profit_usd": None if prof is None else money(prof),
                           "cash_profit_usd": None if cash is None else money(cash), "records_profit_usd": money(led),
                           "reached": reached},
            "control": {"last_seq": self.st["last_seq"], "issued_utc": self.st.get("last_seq_issued_utc"),
                        "note": self.st.get("control_note") or "", "fetch_error": self.st.get("control_error")},
            "queue": [{"seq": q["seq"], "id": q["id"], "action": describe(q)} for q in self.st["queue"]],
            "running": None if not c else {"action": describe(c["act"]), "seq": c["act"]["seq"], "id": c["act"]["id"],
                                           "live": c["live"], "started_utc": utc(c["started"]),
                                           "minutes": round((self.now() - c["started"]) / 60, 1),
                                           "interrupt_sent": c["int_sent"] is not None},
            "report_error": self.st.get("report_error"),
            "events": self.st["events"][-REPORT_EVENTS:],
        }
        rep = self.scrub.obj(rep)
        md = self.render_md(rep)
        ev = "".join(json.dumps(self.scrub.obj({k: v for k, v in e.items() if k != "tail"}), sort_keys=True) + "\n"
                     for e in self.st["events"])
        return rep, md, ev

    def render_md(self, r: dict) -> str:
        L = [f"# Отчёт оператора, {r['generated_utc']}", ""]
        L.append(f"- Взведён (ARMED): **{'да' if r['armed'] else 'нет'}**"
                 + ("" if r["armed"] else f" ({r['armed_reason']})"))
        L.append(f"- Файл STOP: **{'есть' if r['stop_file'] else 'нет'}**")
        lm = r["limits"]
        if lm:
            L.append(f"- Пределы убытка: всего {lm['total_usd']} USD (в ARMED {lm['armed_total_usd']}), "
                     f"за день {lm['daily_usd']} USD (в ARMED {lm['armed_daily_usd']}); осталось всего "
                     f"{lm['left_total_usd']}, сегодня {lm['left_today_usd']}")
        if r["limit_hit"]:
            h = r["limit_hit"]
            L.append(f"- **Предел достигнут:** {h['kind']} в {h['utc']}, убыток {h['loss_usd']} при пределе "
                     f"{h['limit_usd']} USD")
        p = r["pnl"]
        L.append(f"- Баланс pUSD: {p['balance_usd']} (прочитан {p['balance_utc']}); старт {p['baseline_usd']}; "
                 f"изменение всего {p['cash_change_total_usd']}, сегодня {p['cash_change_today_usd']}")
        L.append(f"- По записям программ: итог рассчитанных {p['ledger_realised_total_usd']} "
                 f"(сегодня {p['ledger_realised_today_usd']}), под риском {p['ledger_at_risk_total_usd']}")
        L.append(f"- Убыток для пределов: всего {p['loss_total_usd']}, сегодня {p['loss_today_usd']} USD")
        m = r["milestones"]
        L.append(f"- Прибыль (меньшая из двух: по балансу {m['cash_profit_usd']}, по записям {m['records_profit_usd']}): "
                 f"{m['profit_usd']} USD; ступеней по {m['step_usd']}: {m['reached']}")
        ct = r["control"]
        L.append(f"- Последняя команда: seq {ct['last_seq']} от {ct['issued_utc']}"
                 + (f"; ошибка чтения: {ct['fetch_error']}" if ct["fetch_error"] else ""))
        if r["running"]:
            ru = r["running"]
            L.append(f"- Идёт: {ru['action']} (seq {ru['seq']}, {ru['minutes']} мин)")
        if r["queue"]:
            L.append("- В очереди: " + "; ".join(q["action"] for q in r["queue"]))
        L += ["", "## События (последние)", ""]
        for e in reversed(r["events"]):
            extra = " ".join(f"{k}={e[k]}" for k in ("seq", "id", "exit", "minutes", "balance_usd") if k in e)
            L.append(f"- {e['utc']} **{e['outcome']}** {e['what']}" + (f" ({extra})" if extra else "")
                     + (f": {e['reason']}" if e.get("reason") else ""))
            if e.get("tail"):
                L.append("")
                L.append("  ```")
                L += [f"  {x}" for x in e["tail"][-40:]]
                L.append("  ```")
        return "\n".join(L) + "\n"

    def publish(self) -> bool:
        """Commit the report to `live-reports` and push it, with git plumbing only.

        Nothing from the remote branch is checked out or written to disk (a tree there may hold symlinks
        into the home folder or hooks), and no hook runs. Every commit carries the whole tree: the three
        regular files under reports/, so whatever else someone put on the branch drops out of its tip.
        """
        rep, md, ev = self.build_report()
        leaks = self.scrub.obj_leaks(rep) + self.scrub.leaks(md) + self.scrub.leaks(ev)
        if leaks:
            self.st["report_error"] = f"report withheld: scrubber found {sorted(set(leaks))}"
            self.st["publish_failed_at"] = self.now()
            return False
        files = {"events.jsonl": ev.encode(), "latest.json": (json.dumps(rep, indent=1, sort_keys=True) + "\n").encode(),
                 "latest.md": md.encode()}
        remote = f"refs/remotes/origin/{REPORT_BRANCH}"
        try:
            ents = "".join(f"100644 blob {self.git('hash-object', '-w', '--no-filters', '--stdin', data=b).strip()}\t{n}\n"
                           for n, b in sorted(files.items()))
            sub = self.git("mktree", data=ents.encode()).strip()
            root = self.git("mktree", data=f"040000 tree {sub}\treports\n".encode()).strip()
            for attempt in (1, 2):
                try:
                    self.git("fetch", "--quiet", "--no-tags", "origin", f"+refs/heads/{REPORT_BRANCH}:{remote}")
                except GitError as e:
                    if "couldn't find remote ref" not in str(e).lower():
                        raise                              # offline: no push attempt either
                try:
                    parent = self.git("rev-parse", "--verify", "--quiet", f"{remote}^{{commit}}").strip()
                except GitError:
                    parent = None                          # no branch yet: the first report starts it
                if parent and self.git("rev-parse", f"{parent}^{{tree}}").strip() == root:
                    break                                  # nothing changed
                commit = self.git(*GIT_IDENT, "commit-tree", root, *(["-p", parent] if parent else []), "-m",
                                  f"operator report {rep['generated_utc']} (seq {rep['control']['last_seq']})").strip()
                try:
                    self.git("push", "--quiet", "--no-verify", "origin", f"{commit}:refs/heads/{REPORT_BRANCH}")
                    break
                except GitError:
                    if attempt == 2:                       # someone else moved the branch: once more on top of it
                        raise
        except GitError as e:
            self.st["report_error"] = self.scrub(f"{e}; retried in {PUBLISH_BACKOFF_S // 60} min")
            self.st["publish_failed_at"] = self.now()
            return False
        self.st["report_error"] = None
        self.st["publish_failed_at"] = None
        self.st["last_publish"] = self.now()
        self.st["dirty"] = False
        return True

    # ------------------------------------------------------------------ the loop
    def cycle(self) -> None:
        now = self.now()
        last = self.st.get("last_cycle")
        if last and now - last > self.interval + SLEEP_GAP_S:
            gap = (now - last) / 60
            self.event("woke", "operator loop resumed", reason=f"paused {gap:.0f} min (sleep or stop)")
            for q in self.st["queue"]:
                self.event("skipped", describe(q), seq=q["seq"], id=q["id"],
                           reason=f"stale after a pause of {gap:.0f} min: not run")
            self.st["queue"] = []
        self.st["last_cycle"] = now
        self.monitor()
        self.check_limits()
        self.poll_control()
        self.process_queue()
        self.monitor()
        self.check_limits()
        failed = self.st.get("publish_failed_at")
        if ((self.st.get("dirty") or now - self.st.get("last_publish", 0) >= HEARTBEAT_S)
                and (failed is None or now - failed >= PUBLISH_BACKOFF_S)):
            self.publish()
        self.st["last_cycle"] = self.now()       # the gap is measured from the END of a cycle: long actions are no sleep
        self.save_state()

    def serve(self, max_cycles: int | None = None) -> int:
        def on_signal(signum, frame):
            self.quit = True
        for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(s, on_signal)
        self.event("started", f"operator {VERSION}", reason=f"poll every {self.interval} s")
        n = 0
        try:
            self.recover()
            while not self.quit:
                try:
                    self.cycle()
                    self.st["cycle_error"] = None
                except Exception as e:  # noqa: BLE001  one bad cycle must not end the supervision of a live run
                    self.cycle_failed(e)
                n += 1
                if max_cycles is not None and n >= max_cycles:
                    break
                end = time.time() + self.interval
                while time.time() < end and not self.quit:
                    c = self.child
                    if c and c["proc"] is not None and c["proc"].poll() is not None:
                        break
                    time.sleep(min(1.0, max(0.05, end - time.time())))
        finally:
            # any exit (normal, signal, an exception that got this far): a running program is stopped
            self.stop_child("operator is stopping")
            try:
                self.event("stopped", f"operator {VERSION}")
                self.publish()
                self.save_state()
            except Exception:  # noqa: BLE001
                pass
        return 0

    def cycle_failed(self, e: Exception) -> None:
        msg = self.scrub(f"{type(e).__name__}: {e}")[:300]
        if self.st.get("cycle_error") != msg:           # the same error every minute is reported once
            self.st["cycle_error"] = msg
            self.event("error", "operator cycle", reason=f"{msg}; the loop goes on")
        for step in (self.monitor, self.check_limits):   # supervision first, whatever else failed
            try:
                step()
            except Exception:  # noqa: BLE001
                pass
        try:
            self.st["last_cycle"] = self.now()
            self.save_state()
        except Exception:  # noqa: BLE001
            pass

    def stop_child(self, why: str) -> None:
        if not self.child:
            return
        try:
            self.interrupt(why)
        except Exception:  # noqa: BLE001
            self._signal(self.child["pid"], signal.SIGINT)
        deadline = time.time() + INT_GRACE_S
        while self.child and self.child["proc"] is not None and time.time() < deadline:
            if self.child["proc"].poll() is not None:
                break
            time.sleep(0.5)
        try:                                   # still running after the grace: the next start adopts it
            if self.child:
                self.monitor()
        except Exception:  # noqa: BLE001
            pass


# ----------------------------------------------------------------------------- commands
def repo_of(pilot: Path) -> Path:
    r = subprocess.run(["git", "-C", str(pilot), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("operator: pilot/ is not inside a git working copy")
    return Path(r.stdout.strip())


def state_dir() -> Path:
    return Path.home() / ".polymarket-pilot"


def cmd_run(a) -> int:
    if not 5 <= a.interval <= 600:
        print("operator: --interval must be 5-600 s")
        return 2
    pilot = Path(__file__).resolve().parent
    op = Operator(pilot, repo_of(pilot), state_dir(), interval=a.interval)
    lock = acquire_lock(op.lock_path)
    if lock is None:
        print(f"operator: another operator is running (lock {op.lock_path}); one at a time")
        return 2
    try:
        return op.serve(a.max_cycles)
    finally:
        lock.close()


def cmd_check(a) -> int:
    pilot = Path(__file__).resolve().parent
    try:
        blob = Path(a.file).read_bytes()
    except OSError as e:
        print(f"REFUSED: cannot read {a.file} ({type(e).__name__})")
        return 2
    try:
        ctl, acts = validate_control(blob)
    except Bad as e:
        print(f"REFUSED: {e}")
        return 2
    print(f"seq {ctl['seq']}, issued {utc(ctl['issued_ts'])}, {len(acts)} action(s); note: {ctl['note']!r}")
    for act in acts:
        spec = SPECS[(act["program"], act["cmd"])]
        tag = "LIVE (needs ARMED)" if is_live(act) else spec.kind
        if spec.kind == "op":
            print(f"  {act['id']}: {describe(act)}  [{tag}]  built into the operator")
        else:
            argv = build_argv("python", pilot, act)
            print(f"  {act['id']}: {describe(act)}  [{tag}]  max age {act['max_age_s'] // 60} min")
            print(f"      runs: {' '.join(x.replace(str(pilot) + os.sep, 'pilot/') for x in argv)}")
    return 0


def cmd_status(a) -> int:
    pilot = Path(__file__).resolve().parent
    sd = state_dir()
    if not (sd / "operator-state.json").exists():
        print(f"no operator state yet in {sd}")
    op = Operator(pilot, pilot, sd, say=lambda s: None)
    rep, md, _ = op.build_report()
    print(md)
    return 0


# ----------------------------------------------------------------------------- selftest
FAKE_SMOKE = r'''
import os, sys
from pathlib import Path
home = Path.home() / ".polymarket-pilot"
cmd = sys.argv[1]
if cmd == "status" and os.environ.get("FAKE_UNARM"):
    (home / "ARMED").unlink(missing_ok=True)        # the owner removes ARMED while this quick action runs
if cmd == "auth":
    b = (home / "fake-balance").read_text().strip() if (home / "fake-balance").exists() else "200"
    print("  signer address : 0x" + "ab" * 20)
    print("  account wallet : 0x" + "cd" * 20)
    print(f"  collateral (pUSD) balance: {b}")
elif cmd == "status":
    print("  signer address : 0x" + "ab" * 20)
    print(f"  key file {Path.home()}/.polymarket-pilot/key")
    print("  open orders (this API key): 0")
elif cmd == "cancel":
    print("Nothing to cancel: no order placed by smoke.py is recorded")
elif cmd == "selftest":
    print("selftest: ALL PASS")
sys.exit(0)
'''

FAKE_BIDS = r'''
import argparse, json, os, sys, time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
home = Path.home() / ".polymarket-pilot"
here = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="command", required=True)
r = sub.add_parser("run"); r.add_argument("--config", required=True); r.add_argument("--live", action="store_true")
r.add_argument("--max-windows", type=int, default=12)
rp = sub.add_parser("report"); rp.add_argument("--dry-run", action="store_true")
sub.add_parser("selftest")
a = p.parse_args()
if a.command == "report":
    print("Per level: placed 3 cost 1.00 net -1.00; order 0x" + "ef" * 32 + " by 0x" + "12" * 20)
    print(f"records in {here / 'out'}")              # an absolute path of the checkout, like exp_bids.py prints
    sys.exit(0)
if a.command == "selftest":
    print("selftest: ALL PASS"); sys.exit(0)
if (home / "STOP").exists():
    print("REFUSED: STOP file present"); sys.exit(2)
name = Path(a.config).stem
day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
out = here / "out"; out.mkdir(exist_ok=True)
f = out / f"exp-{name}-{day.replace('-', '')}{'.jsonl' if a.live else '.dryrun.jsonl'}"
mode = "live" if a.live else "dry-run"
step = float(os.environ.get("FAKE_WINDOW_S", "0.2"))
if a.live:
    print("  pUSD balance " + ((home / "fake-balance").read_text().strip() if (home / "fake-balance").exists() else "200"))
try:
    for i in range(a.max_windows):
        if (home / "STOP").exists():
            print("  STOPPING: STOP file"); break
        key = f"{os.getpid()}-{i}"
        ws = int(time.time())
        with open(f, "a") as fh:
            fh.write(json.dumps({"type": "placed", "exp": name, "mode": mode, "key": key, "day": day,
                                 "notional": "1.00", "window_start": ws}) + "\n")
        time.sleep(step)
        pnl = (home / "fake-pnl").read_text().strip() if (home / "fake-pnl").exists() else "0"
        with open(f, "a") as fh:
            fh.write(json.dumps({"type": "order", "exp": name, "mode": mode, "key": key, "day": day,
                                 "cost": "1.00", "pnl": pnl, "window_start": ws}) + "\n")
        if a.live and (home / "fake-balance").exists():
            b = Decimal((home / "fake-balance").read_text().strip()) + Decimal(pnl)
            (home / "fake-balance").write_text(str(b))
        print(f"  window {i + 1}: net {pnl}")
except KeyboardInterrupt:
    print("  interrupted: 0 open orders"); sys.exit(130)
print("  session done"); sys.exit(0)
'''

FAKE_FAV = r'''
import argparse, sys, time
p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="command", required=True)
r = sub.add_parser("run"); r.add_argument("--ticket", type=int, required=True); r.add_argument("--hours", type=int, required=True)
r.add_argument("--live", action="store_true")
sub.add_parser("report"); sub.add_parser("selftest")
a = p.parse_args()
print(f"fav {a.command} ok"); sys.exit(0)
'''

FAKE_FAV_OTHER_CLI = r'''
import argparse, sys
p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="command", required=True)
r = sub.add_parser("run"); r.add_argument("--stake", type=int); r.add_argument("--live", action="store_true")
a = p.parse_args()
print("fav run with another command line"); sys.exit(0)
'''

EVIL_ON_CONTROL_BRANCH = r'''
from pathlib import Path
(Path.home() / "PWNED").write_text("code from the control branch was executed")
'''


def cmd_selftest(a) -> int:
    results: list[tuple[bool, str]] = []

    def expect(name, cond, detail=""):
        results.append((bool(cond), name))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f": {detail}" if detail and not cond else ""))

    def refused(name, fn, needle=""):
        try:
            fn()
        except Bad as e:
            return expect(name, needle in str(e), f"refused with another reason: {e}")
        expect(name, False, "accepted")

    def accepted(name, fn):
        try:
            r = fn()
        except Bad as e:
            return expect(name, False, f"refused: {e}")
        expect(name, True)
        return r

    real_home = os.environ.get("HOME")
    tmp = Path(tempfile.mkdtemp(prefix="pm-operator-selftest-"))
    saved_env = {k: os.environ.get(k) for k in ("HOME", "GIT_CONFIG_NOSYSTEM", "FAKE_WINDOW_S", "PM_WALLET",
                                                 "GIT_CONFIG_GLOBAL")}
    print(f"selftest: throwaway directory {tmp} (removed at the end); the real ~/.polymarket-pilot is not touched")
    try:
        home = tmp / "home"
        home.mkdir()
        os.environ["HOME"] = str(home)
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        os.environ.pop("GIT_CONFIG_GLOBAL", None)
        os.environ["PM_WALLET"] = "0x" + "77" * 20
        (home / ".gitconfig").write_text("[user]\n\tname = Selftest Owner\n\temail = owner@example.org\n"
                                         "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n")
        sd = home / ".polymarket-pilot"
        assert real_home is None or not str(sd).startswith(str(Path(real_home) / ".polymarket-pilot"))

        def sh(*args, cwd=None):
            r = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"{args}: {r.stderr.strip()}")
            return r.stdout

        # --- 1. whitelist and ranges (pure) ---------------------------------------------------------------------
        print("whitelist and parameter ranges")
        v = lambda raw: validate_action(raw, 0, 1)  # noqa: E731
        accepted("smoke status accepted", lambda: v({"program": "smoke", "cmd": "status"}))
        refused("smoke place refused (not on the whitelist)", lambda: v({"program": "smoke", "cmd": "place"}),
                "whitelist")
        refused("smoke roundtrip refused", lambda: v({"program": "smoke", "cmd": "roundtrip"}), "whitelist")
        refused("program 'bash' refused", lambda: v({"program": "bash", "cmd": "-c"}), "whitelist")
        refused("free-form argv key refused", lambda: v({"program": "smoke", "cmd": "status", "argv": ["--x"]}),
                "not allowed")
        refused("unknown parameter refused",
                lambda: v({"program": "exp_bids", "cmd": "report", "params": {"files": ["/etc/passwd"]}}),
                "not allowed")
        refused("config path '../../x' refused", lambda: v({"program": "exp_bids", "cmd": "run",
                                                           "params": {"config": "../../x", "windows": 2}}), "one of")
        refused("config 'tails.json' refused", lambda: v({"program": "exp_bids", "cmd": "run",
                                                         "params": {"config": "tails.json", "windows": 2}}), "one of")
        for bad in (0, 37, "3", True, 3.5, None):
            refused(f"exp_bids windows={bad!r} refused", lambda b=bad: v(
                {"program": "exp_bids", "cmd": "run", "params": {"config": "pairs", "windows": b}}), "windows")
        for good in (1, 36):
            accepted(f"exp_bids windows={good} accepted", lambda g=good: v(
                {"program": "exp_bids", "cmd": "run", "params": {"config": "pairs", "windows": g}}))
        refused("exp_bids live='true' (string) refused", lambda: v(
            {"program": "exp_bids", "cmd": "run", "params": {"config": "pairs", "windows": 2, "live": "true"}}), "live")
        refused("exp_bids run without windows refused", lambda: v(
            {"program": "exp_bids", "cmd": "run", "params": {"config": "pairs"}}), "needs windows")
        for bad in (7, "5", 0, True):
            refused(f"exp_fav ticket={bad!r} refused", lambda b=bad: v(
                {"program": "exp_fav", "cmd": "run", "params": {"ticket": b, "hours": 2}}), "ticket")
        for bad in (0, 13, "2"):
            refused(f"exp_fav hours={bad!r} refused", lambda b=bad: v(
                {"program": "exp_fav", "cmd": "run", "params": {"ticket": 5, "hours": b}}), "hours")
        accepted("exp_fav ticket=10 hours=12 live accepted", lambda: v(
            {"program": "exp_fav", "cmd": "run", "params": {"ticket": 10, "hours": 12, "live": True}}))
        refused("id with a slash refused", lambda: v({"id": "a/b", "program": "smoke", "cmd": "status"}), "id")
        refused("max_age_min 1000 refused", lambda: v({"program": "smoke", "cmd": "status", "max_age_min": 1000}),
                "max_age_min")
        refused("set_limits without values refused", lambda: v({"program": "operator", "cmd": "set_limits"}),
                "needs")
        refused("set_limits negative refused", lambda: v({"program": "operator", "cmd": "set_limits",
                                                          "params": {"max_daily_loss_usd": -5}}), "USD")
        pilot_x = Path("/x/pilot")
        act = v({"program": "exp_bids", "cmd": "run", "params": {"config": "late-tail", "windows": 3, "live": True}})
        expect("exp_bids argv is exactly the documented command line",
               build_argv("py", pilot_x, act) == ["py", "-I", "-B", "-u", "/x/pilot/exp_bids.py", "run", "--config",
                                                   "/x/pilot/experiments/late-tail.json", "--max-windows", "3",
                                                   "--live"])
        act = v({"program": "exp_fav", "cmd": "run", "params": {"ticket": 5, "hours": 4}})
        expect("exp_fav dry argv has no --live",
               build_argv("py", pilot_x, act) == ["py", "-I", "-B", "-u", "/x/pilot/exp_fav.py", "run", "--ticket", "5",
                                                   "--hours", "4"])
        ok_ctl = {"seq": 1, "issued_utc": "2026-11-28T09:00:00Z", "actions": [{"program": "smoke", "cmd": "status"}]}
        enc = lambda o: json.dumps(o).encode()  # noqa: E731
        accepted("minimal control file accepted", lambda: validate_control(enc(ok_ctl)))
        for name, mod in (("seq 0", {"seq": 0}), ("seq '2'", {"seq": "2"}), ("seq true", {"seq": True}),
                          ("bad issued_utc", {"issued_utc": "28.11.2026"}), ("no actions", {"actions": []}),
                          ("11 actions", {"actions": [{"program": "smoke", "cmd": "status"}] * 11}),
                          ("extra top-level key", {"run": "rm -rf /"}),
                          ("duplicate ids", {"actions": [{"id": "x", "program": "smoke", "cmd": "status"},
                                                         {"id": "x", "program": "smoke", "cmd": "auth"}]})):
            refused(f"control file with {name} refused", lambda m=mod: validate_control(enc({**ok_ctl, **m})))
        refused("control file over 64 KB refused",
                lambda: validate_control(enc({**ok_ctl, "note": "x" * 70000})), "bytes")
        refused("control file not JSON refused", lambda: validate_control(b"{not json"), "JSON")
        # review M3: inputs that raised RecursionError / ValueError (and crashed the operator) are now refusals
        refused("control file of 30,000 nested brackets refused (was RecursionError)",
                lambda: validate_control(b"[" * 30000 + b"]" * 30000), "JSON")
        refused("control file with a 5,000-digit seq refused (was ValueError)",
                lambda: validate_control(b'{"seq": 1' + b"0" * 4999 + b', "issued_utc": "2026-11-28T09:00:00Z", '
                                         b'"actions": [{"program": "smoke", "cmd": "status"}]}'), "JSON")
        deep: list = []
        for _ in range(5000):
            deep = [deep]
        expect("a value too large to print does not crash the refusal text",
               short(10**5000) == "<int>" and short(deep).endswith("..."), short(10**5000))
        refused("seq above 1000000000 refused", lambda: validate_control(enc({**ok_ctl, "seq": 10**9 + 1})), "seq")
        ex = Path(__file__).resolve().parent / "control-example.json"
        if ex.exists():
            accepted("pilot/control-example.json is valid", lambda: validate_control(ex.read_bytes()))

        # --- 2. scrubbing (pure) --------------------------------------------------------------------------------
        print("report scrubbing")
        sc = Scrubber()
        user = getpass.getuser()
        dirty = (f"wallet 0x{'ab' * 20} order 0x{'ef' * 32} key {'9f' * 32} path {home}/.polymarket-pilot/key "
                 f"/Users/someone/pilot url https://user:tok@github.com/o/r.git git@github.com:o/r.git "
                 f"secret ZHJ5LXJ1bi1ub3QtYS1zZWNyZXQZHJ5LXJ1bi1ub3Q= mail owner@example.org "
                 f"host {socket.gethostname()} user {user} PM {os.environ['PM_WALLET']}")
        clean = sc(dirty)
        expect("scrubbed text has no address, hex, path, URL, e-mail, token, user or host", not sc.leaks(clean),
               f"{sc.leaks(clean)} in {clean}")
        expect("scrubbed text keeps ordinary words", "wallet" in clean and "order" in clean, clean)
        expect("token ids of 77 digits are hidden too", "<hex>" in sc("token " + "7" * 77))
        sc_user = Scrubber()
        sc_user.literals.append((re.compile(r"(?<![A-Za-z0-9])user(?![A-Za-z0-9])", re.I), "<user>"))
        expect("a user literally named 'user' does not block reports", not sc_user.leaks(sc_user("user user")))
        # review S3: one pass could create a new match, and the leak check then withheld every report
        for crafted in ("/homehttps://x", "/Usershttps://a/b", "a@/homeb.c:d", "/root/home/x@y.z:w"):
            expect(f"scrubbing {crafted!r} reaches a fixed point with no leak", not sc.leaks(sc(crafted)),
                   f"{sc(crafted)!r}: {sc.leaks(sc(crafted))}")
        import random
        rnd = random.Random(20261127)
        frags = ["/home", "/Users", "/root", "/", "https://", "git://", "x", "@", "a.b", ":", "~", "0x", "ab" * 8,
                 " ", "-", "user", "Z9"]
        fuzz_left = [t for t in ("".join(rnd.choice(frags) for _ in range(rnd.randint(1, 10))) for _ in range(20000))
                     if sc.leaks(sc(t))]
        expect("fuzz of 20,000 crafted strings: none leaks after scrubbing", not fuzz_left, str(fuzz_left[:5]))
        # review S6: a checkout outside the home folder (/Volumes/<disk>/...) is scrubbed as <repo>
        sc_vol = Scrubber(Path("/Volumes/Data Disk/polymarket-lab"))
        t = sc_vol("records in /Volumes/Data Disk/polymarket-lab/pilot/out")
        expect("a repository path outside the home folder becomes <repo>",
               t == "records in <repo>/pilot/out" and not sc_vol.leaks(t), t)

        # --- 3. repositories ------------------------------------------------------------------------------------
        print("throwaway git repositories: origin, the Mac's working copy, the coordinator's clone")
        origin = tmp / "origin.git"
        sh("git", "init", "-q", "--bare", str(origin))
        code = tmp / "code"
        sh("git", "clone", "-q", str(origin), str(code))
        pilot = code / "pilot"
        (pilot / "experiments").mkdir(parents=True)
        for n in EXP_BIDS_CONFIGS:
            (pilot / "experiments" / f"{n}.json").write_text("{}\n")
        (pilot / "smoke.py").write_text(FAKE_SMOKE)
        (pilot / "exp_bids.py").write_text(FAKE_BIDS)
        (pilot / "exp_fav.py").write_text(FAKE_FAV)
        (pilot / ".gitignore").write_text("out/\n")
        (code / "README").write_text("code\n")
        sh("git", "add", "-A", cwd=code)
        sh("git", "commit", "-q", "-m", "code", cwd=code)
        sh("git", "push", "-q", "origin", "HEAD:refs/heads/main", cwd=code)
        head0 = sh("git", "rev-parse", "HEAD", cwd=code).strip()
        branch0 = sh("git", "symbolic-ref", "--short", "HEAD", cwd=code).strip()
        status0 = sh("git", "status", "--porcelain", cwd=code)
        coord = tmp / "coord"
        sh("git", "clone", "-q", str(origin), str(coord))
        sh("git", "checkout", "-q", "--orphan", CONTROL_BRANCH, cwd=coord)
        sh("git", "rm", "-q", "-rf", ".", cwd=coord)
        (coord / "pilot").mkdir()
        (coord / "pilot" / "exp_bids.py").write_text(EVIL_ON_CONTROL_BRANCH)
        (coord / "pilot" / "operator.py").write_text(EVIL_ON_CONTROL_BRANCH)

        def push_control(seq, actions, issued=None, raw=None):
            (coord / "control").mkdir(exist_ok=True)
            obj = {"seq": seq, "issued_utc": issued or utc(time.time()), "note": "selftest", "actions": actions}
            (coord / "control" / "desired.json").write_text(raw if raw is not None else json.dumps(obj, indent=1))
            sh("git", "add", "-A", cwd=coord)
            sh("git", "commit", "-q", "--allow-empty", "-m", f"seq {seq}", cwd=coord)
            sh("git", "push", "-q", "origin", f"HEAD:refs/heads/{CONTROL_BRANCH}", cwd=coord)

        lines_said: list[str] = []
        os.environ["FAKE_WINDOW_S"] = "0.15"

        def new_op():
            return Operator(pilot, code, sd, interval=5, say=lines_said.append)

        def cycles(op, n=1, until=None, limit=200):
            for _ in range(limit if until else n):
                op.cycle()
                if until and until(op):
                    return True
                time.sleep(0.1)
            return not until

        def events(op, **kw):
            return [e for e in op.st["events"] if all(e.get(k) == v for k, v in kw.items())]

        # --- 4. control channel, replay -------------------------------------------------------------------------
        print("control channel and replay protection")
        op = new_op()
        lk = acquire_lock(op.lock_path)
        expect("single instance: a second lock is refused", lk is not None and acquire_lock(op.lock_path) is None)
        lk.close()
        op.cycle()
        expect("no control branch yet: no error, nothing runs", not events(op, outcome="error")
               and not events(op, outcome="done"))
        push_control(1, [{"id": "st", "program": "smoke", "cmd": "status"},
                         {"id": "rep", "program": "exp_bids", "cmd": "report"}])
        op.cycle()
        expect("seq 1: smoke status done", events(op, id="st", outcome="done"))
        expect("seq 1: exp_bids report done", events(op, id="rep", outcome="done"))
        st_tail = " ".join(events(op, id="st")[0].get("tail", []))
        expect("program output in the report is scrubbed (address, home path)",
               "<address>" in st_tail and "~" in st_tail and not op.scrub.leaks(st_tail), st_tail)
        n_done = len(events(op, outcome="done"))
        op.cycle()
        op.cycle()
        expect("same seq is not processed again", len(events(op, outcome="done")) == n_done)
        op = new_op()                                     # operator restart: state is re-read
        op.cycle()
        expect("after a restart the seq is not replayed", len(events(op, outcome="done")) == n_done)
        push_control(1, [{"program": "smoke", "cmd": "auth"}])
        op.cycle()
        expect("a new file with an old seq is ignored and reported",
               events(op, outcome="skipped", what="control seq 1") and len(events(op, outcome="done")) == n_done)
        push_control(2, [{"id": "old", "program": "smoke", "cmd": "status"}],
                     issued=utc(time.time() - 2 * 3600))
        op.cycle()
        expect("an action issued 2 h ago is skipped as stale", events(op, id="old", outcome="skipped"))
        push_control(3, [{"id": "fut", "program": "smoke", "cmd": "status"}], issued=utc(time.time() + 3600))
        op.cycle()
        expect("a control file issued 1 h in the future is refused",
               events(op, outcome="refused", what="control seq 3") and not events(op, id="fut"))
        push_control(4, [{"id": "ok", "program": "smoke", "cmd": "status"},
                         {"id": "bad", "program": "smoke", "cmd": "place"}])
        op.cycle()
        expect("one bad action refuses the whole seq", events(op, outcome="refused", what="control seq 4")
               and not events(op, id="ok"))
        push_control(41, [{"id": "halt0", "program": "operator", "cmd": "stop_all"},
                          {"id": "bad0", "program": "smoke", "cmd": "place"}])
        op.cycle()
        expect("an invalid seq still carries out its stop_all", op.stop_file.exists()
               and events(op, id="halt0", outcome="done") and events(op, outcome="refused", what="control seq 41"))
        op.stop_file.unlink()
        push_control(42, [{"id": "halt1", "program": "operator", "cmd": "stop_all"},
                          {"id": "st1", "program": "smoke", "cmd": "status"}], issued=utc(time.time() - 5 * 3600))
        op.cycle()
        expect("a stale stop_all still runs; the stale status does not",
               op.stop_file.exists() and events(op, id="halt1", outcome="done")
               and events(op, id="st1", outcome="skipped"))
        op.stop_file.unlink()
        op.st["last_seq"] = 4                             # the rest of the test numbers seqs from 5 again
        push_control(5, [], raw="{broken json")
        op.cycle()
        expect("broken JSON on the branch is refused and reported", events(op, outcome="refused", what="control file"))
        expect("state file holds the last seq", json.loads(op.state_path.read_text())["last_seq"] == 4)
        # review M3: a hostile file must not crash the operator, before or after a restart
        for name, raw in (("30,000 nested brackets", "[" * 30000 + "]" * 30000),
                          ("a 5,000-digit seq", '{"seq": 1' + "0" * 4999 + ', "issued_utc": "' + utc(time.time())
                           + '", "actions": [{"program": "smoke", "cmd": "status"}]}')):
            push_control(0, [], raw=raw)
            n_ref = len(events(op, outcome="refused", what="control file"))
            crashed = []
            for start in (1, 2):
                try:
                    op.cycle()
                except Exception as e:  # noqa: BLE001
                    crashed.append(f"start {start}: {type(e).__name__}")
                op = new_op()                                  # operator restart
            expect(f"control file of {name}: refused, no crash, not re-read after a restart",
                   not crashed and len(events(op, outcome="refused", what="control file")) == n_ref + 1
                   and op.st["last_seq"] == 4, str(crashed))
        # review S2: a seq far ahead would burn the number range; it is refused and not consumed, its stop_all runs
        push_control(4 + MAX_SEQ_JUMP + 1, [{"id": "jumpstop", "program": "operator", "cmd": "stop_all"},
                                            {"id": "jumpst", "program": "smoke", "cmd": "status"}])
        op.cycle()
        expect("a seq more than 100,000 ahead is refused and not consumed; its stop_all still runs",
               op.st["last_seq"] == 4 and events(op, id="jumpstop", outcome="done") and op.stop_file.exists()
               and not events(op, id="jumpst"))
        op.stop_file.unlink()
        for name, bad_seq in (("seq 1000000001", 10**9 + 1), ("seq 'x'", "x")):
            push_control(0, [], raw=json.dumps({"seq": bad_seq, "issued_utc": utc(time.time()), "actions": [
                {"id": f"salv{len(name)}", "program": "operator", "cmd": "stop_all"},
                {"id": f"salvst{len(name)}", "program": "smoke", "cmd": "status"}]}))
            op.cycle()
            expect(f"a file with {name}: refused, its stop_all still runs, nothing else",
                   op.st["last_seq"] == 4 and events(op, id=f"salv{len(name)}", outcome="done")
                   and op.stop_file.exists() and not events(op, id=f"salvst{len(name)}"))
            op.stop_file.unlink()

        # --- 5. ARMED ---------------------------------------------------------------------------------------------
        print("ARMED and the limits")
        push_control(6, [{"id": "live1", "program": "exp_bids", "cmd": "run",
                          "params": {"config": "pairs", "windows": 2, "live": True}},
                         {"id": "dry1", "program": "exp_bids", "cmd": "run",
                          "params": {"config": "pairs", "windows": 2}}])
        cycles(op, until=lambda o: events(o, id="dry1", outcome="done"))
        expect("live run without ARMED is refused", events(op, id="live1", outcome="refused")
               and "not armed" in events(op, id="live1")[0]["reason"])
        expect("dry run without ARMED runs", events(op, id="dry1", outcome="done"))

        def arm(text, mode=0o600):
            op.armed_file.write_text(text)
            os.chmod(op.armed_file, mode)

        arm("max_total_loss_usd = 30\nmax_daily_loss_usd = 12\n", 0o666)
        expect("ARMED writable by others is not armed", not op.read_armed()["ok"])
        arm("max_total_loss_usd = 30\nmax_daily_loss_usd = 12\nmax_order = 5\n")
        expect("ARMED with an unknown line is not armed", not op.read_armed()["ok"])
        arm("max_total_loss_usd = 1000\nmax_daily_loss_usd = 12\n")
        expect(f"ARMED total above {HARD_MAX_TOTAL_LOSS} is not armed", not op.read_armed()["ok"])
        arm("max_total_loss_usd = 30\nmax_daily_loss_usd = 40\n")
        expect("ARMED daily above total is not armed", not op.read_armed()["ok"])
        arm("# owner, 28.11\nmax_total_loss_usd = 30\nmax_daily_loss_usd = 12\n")
        a0 = op.read_armed()
        expect("ARMED total 30, daily 12 is armed", a0["ok"] and a0["total"] == 30 and a0["daily"] == 12, a0["reason"])
        (sd / "fake-balance").write_text("200")
        (sd / "fake-pnl").write_text("-1.00")
        push_control(7, [{"id": "lower", "program": "operator", "cmd": "set_limits",
                          "params": {"max_total_loss_usd": 25}},
                         {"id": "raise", "program": "operator", "cmd": "set_limits",
                          "params": {"max_daily_loss_usd": 50}},
                         {"id": "live2", "program": "exp_bids", "cmd": "run",
                          "params": {"config": "pairs", "windows": 3, "live": True}}])
        cycles(op, until=lambda o: events(o, id="live2", outcome="done"))
        lim = op.limits(op.read_armed())
        expect("set_limits lowers the total limit to 25", events(op, id="lower", outcome="done")
               and lim["total_usd"] == 25)
        expect("set_limits cannot raise the daily limit", events(op, id="raise", outcome="refused")
               and lim["daily_usd"] == 12)
        expect("armed live run went through and finished", events(op, id="live2", outcome="done"))
        p = op.pnl()
        expect("ledger and balance both show a loss of 3.00", p["ledger_realised_total_usd"] == -3
               and p["cash_change_total_usd"] == -3 and p["loss_today_usd"] == 3,
               f"{p['ledger_realised_total_usd']} {p['cash_change_total_usd']} {p['loss_today_usd']}")
        push_control(8, [{"id": "live3", "program": "exp_bids", "cmd": "run",
                          "params": {"config": "pairs", "windows": 30, "live": True}}])
        cycles(op, until=lambda o: o.child is None and events(o, id="live3", outcome="started")
               and (events(o, id="live3", outcome="interrupted") or events(o, id="live3", outcome="done")))
        p = op.pnl()
        expect("daily limit 12 reached: STOP file created", op.stop_file.exists())
        expect("daily limit: limit event and the live run interrupted",
               events(op, outcome="limit") and events(op, id="live3", outcome="interrupted"))
        expect("balance in state is the probe after the run, not the stale one the run printed at its start",
               Decimal(op.st["balance"]["usd"]) == Decimal((sd / "fake-balance").read_text().strip())
               and Decimal(op.st["balance"]["usd"]) < 200, str(op.st["balance"]))
        expect("the loss stopped within one window of the limit", 12 <= p["loss_today_usd"] <= 12 + 2,
               str(p["loss_today_usd"]))
        push_control(9, [{"id": "live4", "program": "exp_bids", "cmd": "run",
                          "params": {"config": "pairs", "windows": 2, "live": True}},
                         {"id": "dry4", "program": "exp_bids", "cmd": "run",
                          "params": {"config": "pairs", "windows": 1}},
                         {"id": "st4", "program": "smoke", "cmd": "status"}])
        cycles(op, n=3)
        expect("with STOP present a live run is refused", events(op, id="live4", outcome="refused"))
        expect("with STOP present a dry run is refused too", events(op, id="dry4", outcome="refused"))
        expect("with STOP present status still runs", events(op, id="st4", outcome="done"))
        op.stop_file.unlink()
        push_control(10, [{"id": "live5", "program": "exp_bids", "cmd": "run",
                           "params": {"config": "pairs", "windows": 2, "live": True}}])
        cycles(op, n=2)
        expect("STOP removed but daily limit used up: live run refused",
               events(op, id="live5", outcome="refused") and "below" in events(op, id="live5")[0]["reason"])

        # --- 6. disarm, removal of ARMED, stop_all, sleep, exp_fav ----------------------------------------------
        print("disarm, stop_all, sleep, the exp_fav command line")
        for f in (pilot / "out").glob("*.jsonl"):
            f.unlink()
        op.st["baseline"], op.st["day_open"], op.st["limit_hit"] = None, None, None
        today = day_of(time.time())
        rf = pilot / "out" / f"exp-probe-{today.replace('-', '')}.jsonl"
        rf.write_text("\n".join(json.dumps(r) for r in (
            {"type": "placed", "exp": "probe", "mode": "live", "key": "k1", "day": today, "notional": "2.00"},
            {"type": "order", "exp": "probe", "mode": "live", "key": "k1", "day": today, "cost": None, "pnl": None,
             "notional": "2.00"},
            {"type": "placed", "exp": "probe", "mode": "live", "key": "k2", "day": today, "notional": "1.00"},
            {"type": "order", "exp": "probe", "mode": "live", "key": "k3", "day": today, "cost": "0.50",
             "pnl": "-0.50"},
            {"type": "order", "exp": "probe", "mode": "dry-run", "key": "k4", "day": today, "pnl": "-9"})) + "\n{torn")
        lg = op.ledger()
        expect("ledger: unknown cost and no final record count in full; dry-run rows ignored",
               lg["realised_total"] == Decimal("-0.50") and lg["at_risk_total"] == Decimal("3.00")
               and lg["unreadable"] == 1, str(lg))
        rf.unlink()
        ff = pilot / "out" / f"exp-fav-{today.replace('-', '')}.jsonl"
        tnow = time.time()
        fav = []
        for k, (fill, res) in {"k1": (("filled", "10.4", "10.01"), "Yes"), "k2": (("filled", "10.3", "10.00"), "No"),
                               "k3": (("unknown", None, None), None), "k4": (("unfilled", "0", "0"), "No"),
                               "k6": (("unknown", None, None), "No")}.items():
            fav.append({"type": "decision", "key": k, "sent": True, "ticket": "10", "outcome": "Yes", "day": today,
                        "t": tnow, "mode": "live"})
            fav.append({"type": "order", "key": k, "fill_state": fill[0], "filled_shares": fill[1], "cost": fill[2],
                        "mode": "live"})
            if res:
                fav.append({"type": "result", "key": k, "winner": res, "winner_is_split": False, "mode": "live"})
        fav.append({"type": "order", "key": "k6", "post": "late-check", "fill_state": "unfilled",
                    "filled_shares": "0", "cost": "0", "mode": "live"})
        fav.append({"type": "decision", "key": "k5", "sent": False, "ticket": "10", "day": today, "mode": "live"})
        fav.append({"type": "decision", "key": "k7", "sent": True, "ticket": "10", "day": today, "mode": "dry-run"})
        ff.write_text("\n".join(json.dumps(r) for r in fav) + "\n")
        lg = op.ledger()
        expect("exp_fav ledger: won +0.39, lost -10.00, unknown fill unresolved 10.00 at risk, unfilled 0",
               lg["realised_total"] == Decimal("-9.61") and lg["at_risk_total"] == Decimal("10")
               and lg["realised_today"] == Decimal("-9.61"), str(lg))
        ff.unlink()
        if op.stop_file.exists():
            op.stop_file.unlink()
        (sd / "fake-pnl").write_text("0")
        arm("max_total_loss_usd = 30\nmax_daily_loss_usd = 12\n")
        push_control(11, [{"id": "live6", "program": "exp_bids", "cmd": "run",
                           "params": {"config": "tails", "windows": 30, "live": True}},
                          {"id": "after6", "program": "exp_bids", "cmd": "run",
                           "params": {"config": "tails", "windows": 1}}])
        cycles(op, until=lambda o: events(o, id="live6", outcome="started"))
        op.armed_file.unlink()
        cycles(op, until=lambda o: o.child is None or events(o, id="after6"))
        expect("removing ARMED interrupts the live run at once", events(op, id="live6", outcome="interrupted")
               and "disarmed" in events(op, id="live6", outcome="interrupt")[0]["reason"])
        arm("max_total_loss_usd = 30\nmax_daily_loss_usd = 12\n")
        push_control(12, [{"id": "dis", "program": "operator", "cmd": "disarm"},
                          {"id": "live7", "program": "exp_bids", "cmd": "run",
                           "params": {"config": "tails", "windows": 1, "live": True}}])
        cycles(op, n=2)
        expect("disarm moves ARMED aside", events(op, id="dis", outcome="done") and not op.armed_file.exists()
               and list(sd.glob("ARMED.disarmed-*")))
        expect("after disarm a live run is refused", events(op, id="live7", outcome="refused"))
        push_control(13, [{"id": "long", "program": "exp_bids", "cmd": "run",
                           "params": {"config": "tails", "windows": 30}},
                          {"id": "queued", "program": "exp_bids", "cmd": "run",
                           "params": {"config": "tails", "windows": 1}}])
        cycles(op, until=lambda o: events(o, id="long", outcome="started"))
        expect("a second run waits in the queue while one runs", [q["id"] for q in op.st["queue"]] == ["queued"])
        push_control(14, [{"id": "halt", "program": "operator", "cmd": "stop_all"}])
        cycles(op, until=lambda o: o.child is None)
        expect("stop_all: STOP created, running program stopped, queue dropped",
               op.stop_file.exists() and events(op, id="halt", outcome="done")
               and events(op, id="queued", outcome="skipped") and not op.st["queue"]
               and (events(op, id="long", outcome="interrupted") or events(op, id="long", outcome="done")))
        op.stop_file.unlink()
        push_control(15, [{"id": "long2", "program": "exp_bids", "cmd": "run", "params": {"config": "tails",
                                                                                         "windows": 20}},
                          {"id": "q2", "program": "smoke", "cmd": "selftest"},
                          {"id": "q3", "program": "exp_bids", "cmd": "run", "params": {"config": "tails",
                                                                                      "windows": 1}}])
        cycles(op, until=lambda o: events(o, id="long2", outcome="started"))
        cycles(op, n=1)
        expect("a quick action runs while a program run is going", events(op, id="q2", outcome="done"))
        op.st["last_cycle"] = time.time() - 3600         # as if the Mac had slept for an hour
        op.cycle()
        expect("after a sleep the queued action is dropped, not run late",
               events(op, id="q3", outcome="skipped") and "pause" in events(op, id="q3")[0]["reason"])
        cycles(op, until=lambda o: o.child is None)
        (pilot / "exp_fav.py").write_text(FAKE_FAV_OTHER_CLI)
        push_control(16, [{"id": "fav1", "program": "exp_fav", "cmd": "run", "params": {"ticket": 5, "hours": 1}}])
        cycles(op, n=2)
        expect("exp_fav with another command line is refused",
               events(op, id="fav1", outcome="refused") and "command line" in events(op, id="fav1")[0]["reason"])
        (pilot / "exp_fav.py").write_text(FAKE_FAV)
        push_control(17, [{"id": "fav2", "program": "exp_fav", "cmd": "run", "params": {"ticket": 5, "hours": 1}}])
        cycles(op, until=lambda o: events(o, id="fav2", outcome="done"))
        expect("exp_fav with the expected command line runs (dry)", events(op, id="fav2", outcome="done"))
        (pilot / "exp_fav.py").unlink()
        push_control(18, [{"id": "fav3", "program": "exp_fav", "cmd": "report"}])
        cycles(op, n=1)
        expect("a program that is not installed is refused", events(op, id="fav3", outcome="refused"))
        (pilot / "exp_fav.py").write_text(FAKE_FAV)      # the test's own edits undone before the working-copy check

        # --- 6b. the security review's attacks on supervision (REVIEW-operator.md) ------------------------------
        print("review attacks: second live program, long quick actions, crashing cycles, offline reports, deposits")
        if op.stop_file.exists():
            op.stop_file.unlink()
        arm("max_total_loss_usd = 30\nmax_daily_loss_usd = 12\n")
        # S4: an exp_fav session the owner started by hand holds exp_fav.lock
        fav_lk = acquire_lock(sd / "exp_fav.lock")
        push_control(19, [{"id": "favlk", "program": "exp_bids", "cmd": "run",
                           "params": {"config": "tails", "windows": 1, "live": True}}])
        cycles(op, n=2)
        fav_lk.close()
        expect("S4: a live run is refused while an exp_fav.py session holds its lock",
               events(op, id="favlk", outcome="refused") and "exp_fav" in events(op, id="favlk")[0]["reason"])
        # S1: during a live run a selftest is refused, and ARMED is re-checked after every quick action
        os.environ["FAKE_WINDOW_S"] = "0.5"
        push_control(20, [{"id": "s1live", "program": "exp_bids", "cmd": "run",
                           "params": {"config": "tails", "windows": 36, "live": True}}])
        cycles(op, until=lambda o: events(o, id="s1live", outcome="started"))
        os.environ["FAKE_UNARM"] = "1"                    # the first status removes ARMED while it runs
        push_control(21, [{"id": "s1self", "program": "exp_bids", "cmd": "selftest"},
                          {"id": "s1a", "program": "smoke", "cmd": "status"},
                          {"id": "s1b", "program": "smoke", "cmd": "status"}])
        op.cycle()
        os.environ.pop("FAKE_UNARM", None)
        evs = op.st["events"]
        i_int = next((i for i, e in enumerate(evs) if e.get("id") == "s1live" and e["outcome"] == "interrupt"), None)
        i_b = next((i for i, e in enumerate(evs) if e.get("id") == "s1b" and e["outcome"] == "done"), None)
        expect("S1: a selftest is refused while a live program runs",
               events(op, id="s1self", outcome="refused") and "live" in events(op, id="s1self")[0]["reason"])
        expect("S1: ARMED removed during a quick action: the live run is interrupted before the next action",
               i_int is not None and i_b is not None and i_int < i_b, f"interrupt at {i_int}, next action at {i_b}")
        cycles(op, until=lambda o: o.child is None)
        # M3: a cycle that raises while a live run goes on: the loop keeps supervising (ARMED removal still acts)
        old_handlers = {sg: signal.getsignal(sg) for sg in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}
        arm("max_total_loss_usd = 30\nmax_daily_loss_usd = 12\n")
        push_control(22, [{"id": "m3live", "program": "exp_bids", "cmd": "run",
                           "params": {"config": "tails", "windows": 36, "live": True}}])
        polls = []
        real_poll = op.poll_control

        def boom():
            polls.append(1)
            if len(polls) == 1:
                return real_poll()                     # cycle 1 starts the live run
            if len(polls) == 2:
                op.armed_file.unlink()                 # the owner disarms; from now on every cycle raises
            raise RecursionError("maximum recursion depth exceeded (test)")
        op.poll_control = boom
        op.interval = 1
        try:
            rc = op.serve(max_cycles=4)
            escaped = None
        except Exception as e:  # noqa: BLE001
            rc, escaped = None, f"{type(e).__name__}: {e}"
        del op.poll_control
        expect("M3: cycles that raise do not end the loop (4 cycles ran, one error event, serve returned)",
               escaped is None and rc == 0 and len(polls) == 4 and events(op, id="m3live", outcome="started")
               and len(events(op, outcome="error", what="operator cycle")) == 1, f"{escaped} polls={len(polls)}")
        expect("M3: while cycles raise, removing ARMED still interrupts the live run",
               any("disarmed" in e.get("reason", "") for e in events(op, id="m3live", outcome="interrupt"))
               and op.child is None and events(op, id="m3live", outcome="interrupted"),
               str([(e["outcome"], e.get("reason")) for e in events(op, id="m3live")]))
        # M3: any exit of the loop, even an exception, interrupts the running program
        arm("max_total_loss_usd = 30\nmax_daily_loss_usd = 12\n")
        push_control(23, [{"id": "m3exit", "program": "exp_bids", "cmd": "run",
                           "params": {"config": "tails", "windows": 36, "live": True}}])
        cycles(op, until=lambda o: events(o, id="m3exit", outcome="started"))
        child_pid = op.child["pid"] if op.child else 0

        def boom2():
            raise RuntimeError("unexpected (test)")
        op.recover = boom2
        try:
            op.serve(max_cycles=3)
            escaped = None
        except RuntimeError as e:
            escaped = str(e)
        del op.recover
        expect("M3: an exception that ends serve() still interrupts the live program first",
               escaped and op.child is None and events(op, id="m3exit", outcome="interrupted")
               and any("operator is stopping" in e.get("reason", "") for e in events(op, id="m3exit",
                                                                                   outcome="interrupt"))
               and not (child_pid and pid_alive(child_pid)), str(escaped))
        for sg, h in old_handlers.items():
            signal.signal(sg, h)
        op.quit, op.interval = False, 5
        os.environ["FAKE_WINDOW_S"] = "0.15"
        # S5: with the network gone a failed report push is retried at most every 5 minutes
        off = tmp / "origin.git.offline"
        origin.rename(off)
        n_pub = []
        real_publish = op.publish

        def counted():
            n_pub.append(1)
            return real_publish()
        op.publish = counted
        op.st["dirty"] = True
        op.cycle()
        op.cycle()
        expect("S5: offline, the failed report push is not retried in the next cycle",
               len(n_pub) == 1 and op.st.get("report_error"), f"{len(n_pub)} tries, {op.st.get('report_error')}")
        op.st["publish_failed_at"] -= PUBLISH_BACKOFF_S + 1
        op.cycle()
        expect("S5: ... and is retried after the back-off", len(n_pub) == 2)
        off.rename(origin)
        op.st["publish_failed_at"] -= PUBLISH_BACKOFF_S + 1
        op.cycle()
        del op.publish
        expect("S5: back online, the report goes out", op.st.get("report_error") is None and len(n_pub) == 3,
               str(op.st.get("report_error")))
        # S8: a deposit is flagged and does not post a false milestone; a real profit still does
        if op.stop_file.exists():
            op.stop_file.unlink()
        for f in (pilot / "out").glob("*.jsonl"):
            f.unlink()
        arm("max_total_loss_usd = 30\nmax_daily_loss_usd = 12\nmilestone_step_usd = 10\n")
        op.st.update(baseline=None, balance=None, day_open=None, milestones_reached=0, limit_hit=None)
        op.note_balance(Decimal("200"))
        op.note_balance(Decimal("260"))                    # the owner deposits 60
        op.build_report()
        expect("S8: a deposit of 60 is flagged and posts no milestone",
               events(op, outcome="warning") and "deposit" in events(op, outcome="warning")[-1]["reason"]
               and not events(op, outcome="milestone") and op.st["milestones_reached"] == 0)
        rf = pilot / "out" / f"exp-probe-{day_of(time.time()).replace('-', '')}.jsonl"
        rf.write_text(json.dumps({"type": "order", "exp": "probe", "mode": "live", "key": "w1",
                                  "day": day_of(time.time()), "cost": "5.00", "pnl": "25.00",
                                  "window_start": int(time.time())}) + "\n")
        n_warn = len(events(op, outcome="warning"))
        op.note_balance(Decimal("285"))                    # +25 that the records explain
        op.build_report()
        expect("S8: a profit of 25 the records show posts the 20 milestone, with no deposit warning",
               op.st["milestones_reached"] == 2 and events(op, outcome="milestone")
               and len(events(op, outcome="warning")) == n_warn, str(op.st["milestones_reached"]))
        rf.unlink()
        # S9: the first balance read after midnight comes after losses; a recent reading from before midnight opens
        # the day instead
        midnight = (int(time.time()) // 86400 + 1) * 86400
        op.now = lambda: midnight + 900
        op.st["balance"] = {"usd": "150", "utc": utc(midnight - 600), "ts": midnight - 600, "ledger_net": "0"}
        op.st["day_open"] = {"day": day_of(midnight - 600), "usd": "150"}
        op.note_balance(Decimal("140"))
        carried = op.st["day_open"]
        op.st["balance"] = {"usd": "150", "utc": utc(midnight - 5 * 3600), "ts": midnight - 5 * 3600,
                            "ledger_net": "0"}
        op.st["day_open"] = {"day": day_of(midnight - 600), "usd": "150"}
        op.note_balance(Decimal("140"))
        fresh = op.st["day_open"]
        op.now = time.time
        expect("S9: a reading 10 min before midnight opens the new day (loss after midnight counts today)",
               carried == {"day": day_of(midnight + 900), "usd": "150"}, str(carried))
        expect("S9: a reading 5 h old does not: the day opens at the current balance",
               fresh == {"day": day_of(midnight + 900), "usd": "140"}, str(fresh))
        op.st.update(baseline=None, balance=None, day_open=None, milestones_reached=0, limit_hit=None)
        if op.armed_file.exists():
            op.armed_file.unlink()

        # --- 7. reports and the untouched working copy -------------------------------------------------------------
        print("reports branch, scrubbing of what was pushed, the working copy")
        # review M1 + M2: someone with push access puts symlinks into the home folder and hooks on live-reports,
        # and the owner's repository uses a relative core.hooksPath (husky style)
        sh("git", "config", "core.hooksPath", ".githooks", cwd=code)
        key_file = sd / "key"
        key_file.write_text("selftest key fixture: must stay intact\n")
        armed_probe = sd / "ARMED"
        att = tmp / "attacker"
        sh("git", "clone", "-q", "--branch", REPORT_BRANCH, str(origin), str(att))
        for n, target in (("latest.md", "../../key"), ("events.jsonl", "../../../.bashrc"),
                          ("latest.json", "../../ARMED")):
            (att / "reports" / n).unlink(missing_ok=True)
            os.symlink(target, att / "reports" / n)
        (att / ".githooks").mkdir()
        for hk in ("post-commit", "reference-transaction", "post-checkout", "pre-push", "pre-commit", "post-merge"):
            (att / ".githooks" / hk).write_text("#!/bin/sh\necho \"$0\" >> \"$HOME/HOOK_RAN\"\n")
            os.chmod(att / ".githooks" / hk, 0o755)
        sh("git", "add", "-A", cwd=att)
        sh("git", "-c", "user.name=Attacker", "-c", "user.email=attacker@example.invalid", "commit", "-q", "-m",
           "attacker: symlinks and hooks", cwd=att)
        sh("git", "push", "-q", "origin", f"HEAD:refs/heads/{REPORT_BRANCH}", cwd=att)
        push_control(31, [{"id": "evil", "program": "$(touch PWNED_BY_SHELL)", "cmd": "run"}])
        op.st["dirty"] = True
        op.cycle()
        push_control(32, [{"id": "rep32", "program": "exp_bids", "cmd": "report"}])
        op.cycle()
        tip = sh("git", "ls-tree", "-r", f"refs/heads/{REPORT_BRANCH}", cwd=origin)
        modes = sorted({ln.split()[0] for ln in tip.splitlines()})
        names = sorted(ln.split("\t", 1)[1] for ln in tip.splitlines())
        expect("M1: symlinks on live-reports: the key file is intact, no .bashrc written, ARMED not created",
               key_file.read_text() == "selftest key fixture: must stay intact\n" and not (home / ".bashrc").exists()
               and not armed_probe.exists(), key_file.read_text()[:60])
        expect("M2: hooks committed on live-reports never run (relative core.hooksPath)",
               not (home / "HOOK_RAN").exists(),
               (home / "HOOK_RAN").read_text() if (home / "HOOK_RAN").exists() else "")
        expect("M1: the report commit replaces the attacker's tree: three regular files at the tip",
               modes == ["100644"] and names == ["reports/events.jsonl", "reports/latest.json", "reports/latest.md"]
               and op.st.get("report_error") is None, f"{modes} {names} {op.st.get('report_error')}")
        expect("M1: nothing from live-reports is checked out on the Mac (no reports worktree)",
               not (sd / "reports-worktree").exists()
               and "live-reports" not in sh("git", "worktree", "list", cwd=code))
        expect("the shell-injection program name is refused and runs nothing",
               events(op, outcome="refused", what="control seq 31") and not (home / "PWNED_BY_SHELL").exists()
               and not (pilot / "PWNED_BY_SHELL").exists() and not (code / "PWNED_BY_SHELL").exists())
        op.st["dirty"] = True
        op.cycle()
        expect("report published without error", op.st.get("report_error") is None, str(op.st.get("report_error")))
        chk = tmp / "check-reports"
        sh("git", "clone", "-q", "--branch", REPORT_BRANCH, str(origin), str(chk))
        files = sorted(str(f.relative_to(chk)) for f in chk.rglob("*") if f.is_file() and ".git" not in f.parts)
        expect("live-reports holds only the three report files",
               files == ["reports/events.jsonl", "reports/latest.json", "reports/latest.md"], str(files))
        rep = json.loads((chk / "reports" / "latest.json").read_text())
        expect("latest.json has limits, pnl, control and events", all(k in rep for k in
                                                                    ("limits", "pnl", "control", "events")))
        n_commits = int(sh("git", "rev-list", "--count", "HEAD", cwd=chk).strip())
        expect("one report commit per change (several commits pushed)", n_commits >= 5, str(n_commits))
        all_text = "".join((chk / f).read_text() for f in files)
        log_text = sh("git", "log", "--format=%an %ae %s", cwd=chk)
        expect("pushed reports carry no address, key, path, URL, user, host or e-mail",
               not sc.leaks(all_text) and not op.scrub.leaks(all_text), str(op.scrub.leaks(all_text)))
        expect("S6: the checkout's absolute path (outside the home folder here) is not in the reports",
               str(code) not in all_text and os.path.realpath(str(code)) not in all_text
               and str(tmp) not in all_text and "<repo>/pilot/out" in all_text)
        expect("report commits use the neutral identity, not the owner's",
               "Selftest Owner" not in log_text and "owner@example.org" not in log_text and "pm-operator" in log_text)
        expect("the owner's git name is scrubbed from text", "Selftest Owner" not in op.scrub("by Selftest Owner"))
        status1 = sh("git", "status", "--porcelain", cwd=code)
        expect("working copy: same HEAD, same branch, same status",
               sh("git", "rev-parse", "HEAD", cwd=code).strip() == head0
               and sh("git", "symbolic-ref", "--short", "HEAD", cwd=code).strip() == branch0
               and status1 == status0, f"status before {status0!r}, after {status1!r}")
        expect("code on the control branch was never executed or checked out",
               not (home / "PWNED").exists() and EVIL_ON_CONTROL_BRANCH not in (pilot / "exp_bids.py").read_text())
        sh("git", "commit", "-q", "--allow-empty", "-m", "someone else", cwd=chk)
        sh("git", "push", "-q", "origin", f"HEAD:refs/heads/{REPORT_BRANCH}", cwd=chk)
        op.st["dirty"] = True
        expect("report push recovers when the branch moved elsewhere", op.publish(), str(op.st.get("report_error")))
        shim = Path(__file__).resolve().parent / "operator.py"
        if shim.exists():
            shutil.copy(shim, pilot / "operator.py")
            (pilot / "probe_stdlib.py").write_text(
                "import collections, functools, operator\n"
                "print(operator.itemgetter(1)([5, 6]), operator.__lt__(1, 2), len(operator.__all__))\n")
            r = subprocess.run([sys.executable, str(pilot / "probe_stdlib.py")], cwd=pilot, capture_output=True,
                               text=True, timeout=60)
            expect("pilot/operator.py does not break programs started without -I (acts as stdlib operator)",
                   r.returncode == 0 and r.stdout.startswith("6 True"), r.stderr[-300:])
        bad_op = Operator(pilot, code, sd, interval=5, say=lambda s: None)
        bad_op.st["events"].append({"utc": "x", "outcome": "done", "what": "x", "reason": "0x" + "ab" * 20})
        rep2, md2, ev2 = bad_op.build_report()
        expect("an address injected into state is scrubbed before publishing",
               "ab" * 20 not in json.dumps(rep2) + md2 + ev2)
    finally:
        for k, val in saved_env.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(1 for ok, _ in results if ok)
    print(f"selftest: {n_ok}/{len(results)} passed")
    print(f"selftest: {'ALL PASS' if n_ok == len(results) else 'FAILURES'}")
    return 0 if n_ok == len(results) else 1


# ----------------------------------------------------------------------------- main
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="the loop (run it under caffeinate -i)")
    r.add_argument("--interval", type=int, default=POLL_S, help=f"seconds between fetches (default {POLL_S})")
    r.add_argument("--max-cycles", type=int, default=None, help=argparse.SUPPRESS)
    c = sub.add_parser("check", help="validate a control file and show what it would run")
    c.add_argument("file")
    sub.add_parser("status", help="local state, ARMED and limits (no network)")
    sub.add_parser("selftest", help="offline checks with throwaway repositories and fake programs")
    a = p.parse_args(argv)
    return {"run": cmd_run, "check": cmd_check, "status": cmd_status, "selftest": cmd_selftest}[a.command](a)


if __name__ == "__main__":
    sys.exit(main())

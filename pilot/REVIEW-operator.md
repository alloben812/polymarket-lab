# Independent security review of `pilot/operator.py` + `pilot/pm_operator.py` (2026-11-27)

Reviewer: Claude (fresh context, did not write the operator). Scope: `pilot/operator.py` (launcher, 40 lines,
sha256 `4612e545…0b17`), `pilot/pm_operator.py` (2,072 lines, sha256 `bbebf8ae…be80e`; both hashes match
`verification-operator-2026-11-27.txt`), `pilot/OPERATOR.md`, `pilot/control-example.json`, and the record formats
of `exp_bids.py` (lines 640-911) and `exp_fav.py` (lines 456-503, 1029-1250) that the loss ledger reads.
No existing file was changed. All attacks ran against throwaway bare origins, "Mac" clones and coordinator clones
under a temp directory with a temp `HOME`. Nothing was sent to the network, and nothing was committed or pushed in this
repository. The attack scripts are in the reviewer's scratch folder (`opreview/t1_symlink.py` … `t7_fix.py`, `patched.py`).

`python3 -I pilot/operator.py selftest`: 106/106 PASS, exit 0 (reproduced).

## Verdict: NO-GO (as shipped). After M1-M3, GO WITH FIXES

The control channel holds up well. I could not get a shell, a free-form argument, a path, an out-of-range number or
a live run without `ARMED` through `control/desired.json`. Types are checked strictly (`type(v) is int`, bools
rejected for ints), argv is built only from validated values, no shell is used, the fetched ref is only read with
`git rev-parse ref:path` + `git cat-file`, and the working copy stays untouched. Replay protection and the stale and
future checks behave as documented.

The weak spot is the other branch. The operator **checks out the remote `live-reports` branch** into
`~/.polymarket-pilot/reports-worktree` and writes into that checkout. Anyone who can push to the repository, which
is exactly the adversary of this review, can then:

- overwrite any file in the owner's home, the private key file included;
- get code executed on the Mac, through a shell rc file or through git hooks.

Both are demonstrated below. Separately, a 60 KB control file crashes the operator permanently, and a live program
keeps running with no supervisor. All three fixes are small. M1/M2 are one patch, which I tested against the same
attacks.

## Must fix

### M1. Symlinks on the `live-reports` branch: the operator overwrites arbitrary files of the owner (key destroyed, shell rc file written, code execution) — lines 1280-1309, 1311-1322, 1336-1341

`ensure_worktree` checks out the remote branch (`git worktree add -b live-reports <wt> refs/remotes/origin/live-reports`,
line 1305). After a rejected push, `publish` runs `git reset --hard refs/remotes/origin/live-reports` (line 1339).
`write_reports` then writes `reports/latest.json`, `latest.md` and `events.jsonl` with `Path.write_text` (lines
1314-1316), which follows symlinks. A tree with `reports/latest.md -> ../../key` and
`reports/events.jsonl -> ../../../.bashrc` resolves, from `~/.polymarket-pilot/reports-worktree/reports/`, to
`~/.polymarket-pilot/key` and `~/.bashrc`. The attacker needs no user name and no repository path for this.

Reproduced (`t1_symlink.py`). The attacker pushes such a `live-reports` commit and a control file whose action has
program `"$(touch PWNED_BY_SHELL)"`. After one `op.cycle()`:

```
report_error: None
key file now starts with: # Отчёт оператора, 2026-11-27T19:59:05Z |  | - Взведён (ARMED):
.bashrc head: {"outcome": "refused", "reason": "action 1: '$(touch PWNED_BY_SHELL)' 'run' is not on the whitelist; ...
after sourcing .bashrc, PWNED_BY_SHELL exists: True
working copy status: ''
```

The refusal text puts the attacker's string inside a JSON double-quoted string, which is also a double-quoted shell
word, so `$(...)` runs the next time the owner opens a terminal. On macOS the same works with `~/.zshrc`. That
code runs as the owner, next to `~/.polymarket-pilot/key`. Overwriting the key file loses the key unless the owner
has a backup. The report still publishes without error (`report_error: None`), so nothing signals the attack.
Requirement 1 ("never executes code from it") is broken through the second branch.

### M2. Hooks from the `live-reports` tree run when the owner's repo uses a relative `core.hooksPath` — same lines, plus 1320

A relative `core.hooksPath` resolves against the root of the working tree where git runs (githooks(5)). Projects
that set `core.hooksPath=.githooks` (husky and similar tools) are common. For the reports worktree that root is the
attacker's checkout. `git commit --no-verify` (line 1320) still runs `post-commit` and `reference-transaction`, and
`git worktree add` runs `post-checkout`. Reproduced (`t2_hooks.py`, owner repo with `core.hooksPath=.githooks`, hooks
committed on `live-reports`): `hooks from the live-reports tree executed: ['reference-transaction', … 'post-commit', …]`.
This repository does not set `core.hooksPath` today. The owner's Mac clone or a later tool might.

**Patch for M1 + M2 (tested, `patched.py`).** Never check out or write into a tree that came from the remote. Build
the report commit with plumbing in the main repository's object store, with hooks off, and delete the worktree code
(`ensure_worktree`, `write_reports`, and the worktree path in `OPERATOR.md`):

```python
    def git_in(self, *args, data: bytes = b"") -> str:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
        try:
            r = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=str(self.repo), input=data,
                               capture_output=True, timeout=GIT_TIMEOUT_S, env=env)
        except (OSError, subprocess.SubprocessError) as e:
            raise GitError(f"git {args[0]}: {type(e).__name__}") from None
        if r.returncode != 0:
            msg = r.stderr.decode("utf-8", "replace").strip().splitlines()
            raise GitError(f"git {args[0]}: " + (msg[-1] if msg else f"exit {r.returncode}"))
        return r.stdout.decode("utf-8", "replace").strip()

    def publish(self) -> bool:
        rep, md, ev = self.build_report()
        leaks = self.scrub.obj_leaks(rep) + self.scrub.leaks(md) + self.scrub.leaks(ev)
        if leaks:
            self.st["report_error"] = f"report withheld: scrubber found {sorted(set(leaks))}"
            return False
        files = {"events.jsonl": ev.encode(), "latest.json": (json.dumps(rep, indent=1, sort_keys=True) + "\n").encode(),
                 "latest.md": md.encode()}
        remote = f"refs/remotes/origin/{REPORT_BRANCH}"
        try:
            ents = "".join(f"100644 blob {self.git_in('hash-object', '-w', '--stdin', data=b)}\t{n}\n"
                           for n, b in sorted(files.items()))
            root = self.git_in("mktree", data=f"040000 tree {self.git_in('mktree', data=ents.encode())}\treports\n".encode())
            for attempt in (1, 2):
                try:
                    self.git_in("fetch", "--quiet", "--no-tags", "origin", f"+refs/heads/{REPORT_BRANCH}:{remote}")
                except GitError:
                    pass                                   # no branch yet or offline: the push decides
                try:
                    parent = self.git_in("rev-parse", "--verify", "--quiet", f"{remote}^{{commit}}")
                except GitError:
                    parent = None
                if parent and self.git_in("rev-parse", f"{parent}^{{tree}}") == root:
                    break                                  # nothing changed
                commit = self.git_in(*GIT_IDENT, "commit-tree", root, *(["-p", parent] if parent else []), "-m",
                                     f"operator report {rep['generated_utc']} (seq {rep['control']['last_seq']})")
                try:
                    self.git_in("push", "--quiet", "--no-verify", "origin", f"{commit}:refs/heads/{REPORT_BRANCH}")
                    break
                except GitError:
                    if attempt == 2:
                        raise
        except GitError as e:
            self.st["report_error"] = self.scrub(f"{e}; retried next cycle")
            return False
        self.st["report_error"] = None
        self.st["last_publish"] = self.now()
        self.st["dirty"] = False
        return True
```

Result of the same attack (symlinks + relative hooksPath + `post-commit` hook on `live-reports`):

```
Operator        | key intact: False | .bashrc written: True  | hook ran: True  | tip tree modes: ['100644','100755','120000']
PatchedOperator | key intact: True  | .bashrc written: False | hook ran: False | tip tree modes: ['100644']
```

Every report commit carries the whole tree (three regular files), so the attacker's files drop out of the branch
tip. The patched version also publishes on a fresh origin with no `live-reports` branch. Also add
`"-c", "core.hooksPath=/dev/null"` in `Operator.git` (line 1088) for the control fetch. Add a selftest check that
pre-seeds `live-reports` with these symlinks and a hook, then asserts the key is intact and no hook ran. The owner
deletes the old `~/.polymarket-pilot/reports-worktree` once (`git worktree prune` afterwards).

### M3. A hostile or malformed control file crashes the operator for good, and a running live program is left with no supervisor — lines 276-279, 1136-1141, 1381-1383, 1430-1433

`parse_control` catches only `UnicodeDecodeError` and `json.JSONDecodeError`. Two inputs raise other errors:

- a 60 KB file of nested brackets raises `RecursionError`;
- a 5,000-digit integer raises `ValueError` (the CPython int-digits limit).

Both are under the 64 KB cap. `poll_control` sets `last_blob` before parsing but saves state only afterwards, so the
blob is read again after every restart. `serve` has no `try` around `cycle()`, so the exception ends the process.
Children are started with `start_new_session=True`, so they survive it. Reproduced (`t3_crash.py`, `t3b_orphan.py`):

```
deep nesting:   operator start 1: cycle CRASHED with RecursionError; operator start 2: cycle CRASHED with RecursionError
5000-digit int: operator start 1: cycle CRASHED with ValueError;     operator start 2: cycle CRASHED with ValueError
live child started, pid 19103 / serve() raised RecursionError / ARMED removed by the owner; live child still running 3 s later: Ss
```

After the crash nothing enforces "removing ARMED disarms at once" or the loss limits. A live `exp_bids` session can
run up to 3 h and `exp_fav` up to 12 h, held only by their own caps and STOP. The owner also cannot restart the
operator until the branch changes. Any other unexpected exception, such as a full disk in `save_state` or a
`TimeoutExpired` from the `cat-file` at line 1114, has the same effect.

Patch:

```python
# parse_control, line 278
    except (UnicodeDecodeError, ValueError, RecursionError) as e:   # JSONDecodeError is a ValueError
        raise Bad(f"control file is not valid JSON ({type(e).__name__})") from None

# poll_control, line 1136
        self.st["last_blob"] = sha
        self.save_state()                         # a blob that crashes anything below is never read again

# serve, lines 1381-1401: one bad cycle must not end supervision, and any exit stops the child
        try:
            while not self.quit:
                try:
                    self.cycle()
                except Exception as e:  # noqa: BLE001
                    self.event("error", "operator cycle", reason=self.scrub(f"{type(e).__name__}: {e}")[:300])
                    try:
                        self.save_state()
                    except OSError:
                        pass
                n += 1
                ...                                # the existing wait loop
        finally:
            if self.child:
                self.interrupt("operator is stopping")
                ...                                # the existing grace loop
```

Add selftest checks: nested brackets, a 5,000-digit `seq`, and a `cycle()` that raises while a live fake run is
going. Each should produce a refusal or error event while the operator keeps running, and on a real exit the child
should be interrupted.

## Should fix

- **S1. Long quick actions starve the supervisor (lines 1190-1197, 788-807, 76).** `process_queue` runs every quick
  action synchronously and calls `monitor()`/`check_limits()` only at the end of the cycle. A seq of 10
  `selftest` actions (900 s timeout each) during a live run delays the ARMED-removal check and the loss-limit check
  by up to 2.5 h. Reproduced with a 3 s fake selftest: ARMED removed, one cycle took 31 s, and the interrupt came
  only at the end of it. Patch: call `self.monitor(); self.check_limits()` after every `start_action` in
  `process_queue`, and refuse `selftest` while `self.child and self.child["live"]`.
- **S2. `seq` can be burned (lines 286-287, 1142, 1151).** A file with `seq: 1000000000` is consumed. After that
  every later file fails `parse_control` (out of range), including a `stop_all`. Patch: refuse, without consuming,
  any seq greater than `last_seq + 100000`. When `parse_control` fails only on seq, still salvage `stop_all` and
  `disarm`.
- **S3. The scrubber does not reach a fixed point, so a crafted string withholds every report (lines 371-381,
  1326-1329).** Example: `"/homehttps://x"` becomes `"~https://x"`, which matches `URL_RE` again. A fuzz of 200,000
  short strings gave 1,604 inputs that still leak after one pass. An attacker string in `note` or in a refusal reason
  therefore blocks `publish()` until 200 newer events push it out. Fail-safe, but the coordinator goes blind. Patch:
  in `Scrubber.__call__`, repeat the passes until the text stops changing (at most 8). The same fuzz then gives 0 (`t7_fix.py`).
- **S4. `live_gate` checks only the `exp_bids` live lock (line 885).** `exp_fav` has its own
  `~/.polymarket-pilot/exp_fav.lock` (exp_fav.py line 112). An `exp_fav` session the owner started by hand is not
  seen, so two live programs can run at once. Patch: also refuse when `lock_is_held(self.sd / "exp_fav.lock")`.
- **S5. A network blackhole stretches one cycle to about 6-7 minutes (lines 77, 1084-1095, 1324-1344, 1368).** Every
  failed `publish` retries at once in the next cycle: fetch, push, fetch, push, at 90 s each, plus the 90 s control
  fetch. All that time `monitor()` does not run. Patch: back off publish retries (for example at most once per 5 min
  after a failure), and use a shorter git timeout such as 30 s.
- **S6. Paths outside the home folder are not scrubbed (lines 338-369).** `exp_bids.py` prints `records in {OUT_DIR}`
  as an absolute path (exp_bids.py line 945). For a checkout under `/Volumes/<name>/…` that path reaches the report.
  Patch: add `(str(self.repo), "<repo>")` and its `realpath` to the scrubber's literals.
- **S7. `stop_all` cancels only orders that `smoke.py` itself recorded (lines 1014-1018; `OPERATOR.md` line 183).**
  Orders from `exp_bids`/`exp_fav` are cancelled only by those programs when they get SIGINT. If they are SIGKILLed
  (after 3 min), their orders stay until they expire. Say this in `OPERATOR.md` ("Как остановить всё"), or add an
  account-wide cancel to the whitelist once `smoke.py` has one.
- **S8. A deposit hides balance-based losses and produces false milestone posts (lines 754-768, 1204-1209).** The
  baseline is fixed at the first balance after arming. A top-up raises `cash_change_total` by the deposit, so the
  balance-based loss check is relaxed by that amount (the ledger still guards), and a "profit passed" milestone fires.
  The docs ask for a manual `baseline_balance_usd` line. Better: base milestones on the ledger's realised result, or
  flag any balance jump that is larger than the ledger change.
- **S9. Small robustness items.** `subprocess.run(["git","cat-file","blob",…], timeout=30)` at line 1114 can raise
  `TimeoutExpired`, which is not caught (covered by the M3 `try`). `day_open` is the first balance *read* on a UTC day
  and can come after that day's first losses (line 758). The ledger's daily figure uses the placement day
  (exp_bids.py line 839), so a window that crosses midnight counts toward the earlier day.

## Checked and holding

- Whitelist and ranges: no shell; argv only from the table. The `enum`, `int` and `bool` checks reject strings,
  floats and bools-as-ints. `config` becomes a fixed path. Ids cannot contain `/`. `max_age_min` is capped at 360.
  Extra keys at both levels are refused. Money parameters reject NaN, Infinity and negatives.
- Live only with ARMED: `is_live` requires a `run` with `live is True`, and `live_gate` re-reads ARMED (owner uid,
  not group/other-writable, strict lines, total ≤ 300, daily ≤ total), checks STOP and the exp_bids lock, and probes
  the balance. A forged ARMED cannot be produced even through the M1 symlinks, because the report text never parses
  as ARMED lines. `set_limits` only lowers, keyed to the ARMED fingerprint.
- Replay: seq is consumed before anything runs. Not-newer seqs are skipped. Files more than 5 min in the future are
  refused. Actions are stale after 20 min (max 6 h). After a pause of more than interval + 5 min the queue is dropped.
- Loss ledger compared with the real record formats. exp_bids: `placed`/`order` rows and `mode`, `notional`, `cost`,
  `pnl`, `day`, `window_start` match exp_bids.py lines 649-651 and 836-859. `window` rows are correctly ignored (no
  double count). post-error and unconfirmed-close orders count at full notional. exp_fav: `decision`/`order`/`result`,
  `sent`, `late-check`, `fill_state`, `filled_shares`, `cost` (fee included, exp_fav.py line 1164), `winner_is_split`
  match `build_ledger` (exp_fav.py lines 457-503). The ledger counts at-risk exposure as loss, and the balance
  measure counts open positions in full, so both err on the safe side.
- Working copy: only `git fetch` into `refs/remotes/origin/live-control`, `rev-parse`, `cat-file`. HEAD, branch and
  status are unchanged in every attack run (`wc status: ''`).
- Reports: addresses, 32+ hex, tokens, URLs, e-mails, home paths, user, host and git identity are scrubbed. Commits
  use `pm-operator`.

## Residual risks (after the fixes)

- Anyone with push access to the GitHub repository can do what the coordinator can: run the whitelisted programs
  within ARMED limits, lower limits, stop. Keep the repository private with few writers, and protect `live-control`.
- Fetching both branches brings attacker-sized objects into the owner's `.git`, so a disk-fill is possible.
- If `operator-state.json` is deleted, the current control file runs again when it is still within its `max_age`
  (up to 6 h).
- A limit can be overshot by one step that is already under way (one `exp_bids` window ≤ 5 USD, one `exp_fav` ticket
  ≤ 10 USD), and by anything that happens while the Mac sleeps.
- A crash between `Popen` and `save_state` in `start_child` (lines 902-918) leaves an untracked child. exp_bids' own
  lock covers a second exp_bids, not exp_bids + exp_fav.
- Nothing has run on macOS, with real sleep, real programs, or a real GitHub push. Watch the first session live.

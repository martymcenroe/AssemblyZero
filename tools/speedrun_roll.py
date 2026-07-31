#!/usr/bin/env python3
"""Roll one or more speedrun issues end to end, with zero human decisions (#1919).

This replaces the untracked `run_instrumented.sh` scratch script AND the ritual
that surrounded it. The old flow required a human to:

  - know which branch to roll on, and pass it to two tools consistently;
  - notice when a finished arc had left the base carrying the work;
  - pick a name for the next attempt branch and cut it by hand (done wrong on
    2026-07-30: the branch was never pushed, so the run's first PR would have
    failed);
  - read an ABORT message saying "run speedrun_reset.py, verify clean,
    relaunch" and then do exactly that.

Every one of those is now resolved by this tool. It takes a repo and issue
numbers. Nothing else is a decision.

Preserved verbatim from the wrapper, because each was earned:
  - events log     -- start/stop, trapped signals, child exit code
  - heartbeat      -- a line every 15s; the last one is the time of death under
                      SIGKILL, and the only trustworthy run status (the harness
                      fired three phantom "killed" notifications in one night,
                      all disproven by a live heartbeat)
  - direct redirect -- the child's stdout goes straight to a file with no pipe
                      in the path, which is what stopped the kills

Exit codes: 0 all issues rolled; 91 a base or gate problem this tool could not
heal; otherwise the failing child's return code.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import speedrun_clean_check as gate
import speedrun_new_attempt as attempt
import speedrun_reset as reset

HEARTBEAT_SECONDS = 15
DEFAULT_PREFIX = "hardening-run"

# Directories whose contents ARE the pipeline. A tracked modification here means
# the roll would execute code that is not what main says it is (#2007).
_CODE_DIRS = ("tools", "assemblyzero")


class SignalExit(SystemExit):
    """Raised from a signal handler so the restore in `finally` still runs."""


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


class EventLog:
    """Append-only run record. The file, not the harness, is the truth."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> None:
        line = f"{_stamp()} {message}"
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        print(line, flush=True)


class Heartbeat:
    """A line every 15s until stopped. Last line == time of death under SIGKILL."""

    def __init__(self, path: Path, interval: int = HEARTBEAT_SECONDS) -> None:
        self.path = path
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Heartbeat:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._beat, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 5)

    def _beat(self) -> None:
        while not self._stop.is_set():
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(f"{_stamp()} alive\n")
            self._stop.wait(self.interval)


# =============================================================================
# Base resolution -- the ritual this tool exists to delete
# =============================================================================


def attempt_prefix(repo_root: Path) -> str:
    """Naming family for attempt branches, taken from the current one.

    `hardening-run-12` -> `hardening-run`. A branch that does not look like an
    attempt (e.g. `main`) falls back to the campaign default, so a repo sitting
    on its default branch still gets a sensibly named first attempt.
    """
    current = attempt.current_branch(repo_root)
    match = re.match(r"^(.*)-\d+$", current or "")
    return match.group(1) if match else DEFAULT_PREFIX


def next_attempt_name(repo_root: Path, prefix: str) -> str:
    """The next free `{prefix}-{N}`, counting local, graveyard, and remote refs.

    Every namespace is consulted because a name only has to collide in ONE of
    them to break: `git branch` fails on a local clash, `git push` on a remote
    one, and the graveyard holds every previous attempt by construction.
    """
    seen: set[int] = set()
    esc = re.escape(prefix)
    pattern = re.compile(rf"^(?:{esc}|graveyard/{esc})-(\d+)$")

    local = _run(["git", "branch", "--list", "--format=%(refname:short)"], cwd=repo_root)
    remote = _run(["git", "ls-remote", "--heads", "origin"], cwd=repo_root)

    names = [line.strip() for line in local.stdout.splitlines()]
    names += [
        line.split("refs/heads/", 1)[1].strip()
        for line in remote.stdout.splitlines()
        if "refs/heads/" in line
    ]
    for name in names:
        match = pattern.match(name)
        if match:
            seen.add(int(match.group(1)))

    return f"{prefix}-{(max(seen) + 1) if seen else 1}"


def establish_new_attempt(repo_root: Path, log: EventLog) -> str | None:
    """Cut and verify a fresh attempt branch. Returns its name, or None."""
    prefix = attempt_prefix(repo_root)
    name = next_attempt_name(repo_root, prefix)
    log.write(f"BASE establishing new attempt '{name}'")

    code = attempt.main(["--repo", str(repo_root), "--name", name, "--apply"])
    if code != 0:
        log.write(f"BASE FAILED to establish '{name}' (exit {code})")
        return None
    log.write(f"BASE established and verified: {name}")
    return name


def base_is_structurally_sound(repo_root: Path, base: str) -> list[str]:
    """What must hold for ANY base, fresh or mid-arc. Empty == sound.

    Deliberately NOT "level with the default branch": mid-arc a base carries
    the earlier phases, which is the whole point of an integration branch. Only
    a FRESH attempt must be level, and speedrun_new_attempt enforces that.

    What must always hold is that the base exists on origin and tracks its own
    counterpart -- `gh pr create --base` needs the remote ref, and an upstream
    pointing at the default branch is the exact shape that hid the 2026-07-30
    breakage from `git status`.
    """
    problems: list[str] = []
    if not attempt.remote_branch_exists(repo_root, base):
        problems.append(
            f"'{base}' does not exist on origin -- PRs targeting it would fail"
        )
    upstream = attempt.upstream_of(repo_root, base)
    if upstream != f"origin/{base}":
        problems.append(
            f"upstream of '{base}' is '{upstream or 'unset'}', expected "
            f"'origin/{base}'"
        )
    return problems


def ensure_base(repo_root: Path, issue: int, log: EventLog) -> str | None:
    """A base this issue can actually be rolled on. Heals what it can.

    Order matters: structure first (a base that cannot receive PRs is useless
    however clean it looks), then this issue's debris, then this issue's
    already-merged work.
    """
    base = attempt.current_branch(repo_root)
    if not base:
        log.write("BASE detached HEAD -- establishing a fresh attempt")
        return establish_new_attempt(repo_root, log)

    problems = base_is_structurally_sound(repo_root, base)
    if problems:
        log.write(f"BASE '{base}' unusable: {'; '.join(problems)}")
        return establish_new_attempt(repo_root, log)

    findings = gate.check_repo(repo_root, [issue], base)
    debris = [f for f in findings if not f.startswith("ERROR:")]
    errors = [f for f in findings if f.startswith("ERROR:")]
    if errors:
        for e in errors:
            log.write(f"GATE {e}")
        return None
    if not debris:
        log.write(f"BASE '{base}' verified clean for #{issue}")
        return base

    committed = [d for d in debris if d.startswith("committed artifact:")]
    if committed:
        # The base already contains this issue's merged work. No amount of
        # debris cleanup fixes that -- it needs a base that predates it.
        log.write(
            f"BASE '{base}' already contains #{issue}'s work "
            f"({len(committed)} artifact(s)) -- establishing a fresh attempt"
        )
        return establish_new_attempt(repo_root, log)

    # Recoverable debris. The old wrapper printed "run speedrun_reset.py,
    # verify clean, relaunch" and quit; that instruction is now the code path.
    log.write(f"GATE {len(debris)} finding(s) for #{issue} -- self-healing")
    for d in debris:
        log.write(f"  {d}")
    try:
        repo_slug = reset._gh_repo(repo_root)
    except RuntimeError as err:
        log.write(f"RESET could not determine owner/repo: {err}")
        return None
    reset.reset_one_issue(repo_root, repo_slug, issue)

    findings = gate.check_repo(repo_root, [issue], base)
    debris = [f for f in findings if not f.startswith("ERROR:")]
    if debris:
        log.write(f"GATE still dirty after reset ({len(debris)}) -- fresh attempt")
        for d in debris:
            log.write(f"  {d}")
        return establish_new_attempt(repo_root, log)

    log.write(f"BASE '{base}' clean for #{issue} after self-heal")
    return base


# =============================================================================
# The roll
# =============================================================================


def roll_issue(
    repo_root: Path, issue: int, log_dir: Path, az_root: Path, extra: list[str]
) -> int:
    tag = f"run-issue{issue}-{datetime.now().strftime('%H%M%S')}"
    log = EventLog(log_dir / f"{tag}-events.log")
    heartbeat_path = log_dir / f"{tag}-heartbeat.log"
    out_path = log_dir / f"{tag}.log"

    log.write(f"START issue=#{issue} repo={repo_root} pid={os.getpid()}")

    with Heartbeat(heartbeat_path):
        base = ensure_base(repo_root, issue, log)
        if base is None:
            log.write("ABORT could not establish a usable base")
            return 91

        cmd = [
            sys.executable, "tools/orchestrate.py",
            "--issue", str(issue),
            "--repo", str(repo_root),
            "--no-gate-pr",
            "--base-branch", base,
            *extra,
        ]
        log.write(f"LAUNCH base={base} -> {out_path.name}")

        # Direct redirect: the child's stdout goes straight to the file with no
        # pipe in the path. Restoring a pipe here reintroduces the teardown that
        # killed campaign runs.
        with out_path.open("w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.run(
                cmd, cwd=str(az_root), stdout=fh, stderr=subprocess.STDOUT,
                env=_child_env(),
            )
        log.write(f"CHILD EXITED rc={proc.returncode}")

    log.write(f"EXIT rc={proc.returncode}")
    return proc.returncode


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["CLAUDECODE"] = ""         # nested Claude sessions fail without this
    env["PYTHONUNBUFFERED"] = "1"  # Python buffers stdout when not on a TTY
    return env


def install_signal_handlers(log: EventLog) -> None:
    """Log TERM/INT/BREAK/HUP to the events file, then exit via the normal path.

    #2006: the bash wrapper trapped these and logged them; the Python rewrite
    kept the docstring claiming "trapped signals" and shipped none. A roll of
    boostgauge #7 then died seven minutes in leaving only START/BASE/LAUNCH, so
    "killed by a supervisor" and "died silently" were indistinguishable -- and
    those have different remedies.

    The log line is the point, not the graceful exit. SIGKILL cannot be caught,
    but once TERM and INT are recorded, a death with NO signal line becomes
    evidence FOR SIGKILL rather than an absence of information.
    """
    import signal

    def _handler(signum: int, _frame: object) -> None:
        try:
            name = signal.Signals(signum).name
        except ValueError:  # pragma: no cover - platform-specific numbers
            name = str(signum)
        log.write(f"SIGNAL: {name} received")
        raise SignalExit(90)

    for attr in ("SIGTERM", "SIGINT", "SIGBREAK", "SIGHUP"):
        sig = getattr(signal, attr, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _handler)
        except (OSError, ValueError):  # pragma: no cover - not settable here
            continue


def check_assemblyzero_tree(az_root: Path) -> list[str]:
    """Reasons the AssemblyZero tree running this roll is not trustworthy (#2007).

    The checkout is shared across concurrent lanes and can be parked on another
    lane's branch at an older commit, in which case the roll executes stale
    pipeline code with no indication. That happened: `Projects/AssemblyZero` sat
    on `1428-canonical-claude-backup` two commits behind main, and a reset run
    from it failed with a TypeError that was already fixed and merged.

    The assertion is about the COMMIT, not the branch. "Is it named main" is
    wrong in both directions -- on main but behind is exactly the failure above,
    and a detached worktree pinned at origin/main is a perfectly good way to run
    a roll. Untracked files are ignored: other lanes routinely leave one-off
    scripts in tools/, and those do not change the code being executed.
    """
    problems: list[str] = []
    if not (az_root / ".git").exists():
        return [f"{az_root} is not an AssemblyZero checkout"]

    _run(["git", "fetch", "origin"], cwd=az_root)

    behind = _run(
        ["git", "rev-list", "--count", "HEAD..origin/main"], cwd=az_root
    )
    if behind.returncode != 0 or not behind.stdout.strip().isdigit():
        problems.append("cannot compare this tree against origin/main")
    elif int(behind.stdout.strip()) > 0:
        head = _run(["git", "log", "--oneline", "-1"], cwd=az_root).stdout.strip()
        problems.append(
            f"{int(behind.stdout.strip())} commit(s) behind origin/main "
            f"(HEAD: {head}) -- this roll would run stale pipeline code"
        )

    dirty = _run(
        ["git", "status", "--porcelain", "--", *_CODE_DIRS], cwd=az_root
    )
    modified = [
        line for line in dirty.stdout.splitlines() if not line.startswith("??")
    ]
    if modified:
        problems.append(
            f"{len(modified)} tracked modification(s) under "
            f"{'/, '.join(_CODE_DIRS)}/ -- the pipeline is not what main says"
        )
    return problems


def restore_repo(repo_root: Path, issues: list[int], log: EventLog) -> list[str]:
    """Hand the repo back the way it was borrowed (#2005). Returns failures.

    A roll leaves the target checked out on the attempt branch with pipeline
    worktrees registered. Being handed that back is a defect: a run should
    return the repo to the state it took.

    Called from a `finally`, so it runs on success, on failure, and on any
    exception -- including the SignalExit raised by the handlers above. It
    cannot run under SIGKILL; that gap is covered only by the next invocation's
    self-heal, and is stated rather than papered over.
    """
    log.write("RESTORE returning the repo to its default branch")

    for issue in issues:
        reset.remove_worktree(repo_root, issue)

    base = attempt.default_branch(repo_root)
    if not base:
        return ["cannot resolve origin/HEAD; leaving the checkout as it is"]

    checkout = _run(["git", "checkout", base], cwd=repo_root)
    if checkout.returncode != 0:
        return [f"could not check out {base}: {(checkout.stderr or '').strip()}"]

    failures: list[str] = []
    current = attempt.current_branch(repo_root)
    if current != base:
        failures.append(f"expected to end on '{base}', ended on '{current}'")

    worktrees = [
        line for line in _run(
            ["git", "worktree", "list", "--porcelain"], cwd=repo_root
        ).stdout.splitlines() if line.startswith("worktree ")
    ]
    if len(worktrees) != 1:
        failures.append(
            f"{len(worktrees) - 1} pipeline worktree(s) still registered"
        )

    tracked = [
        line for line in _run(
            ["git", "status", "--porcelain"], cwd=repo_root
        ).stdout.splitlines() if not line.startswith("??")
    ]
    if tracked:
        failures.append(f"{len(tracked)} tracked modification(s) left behind")

    if not failures:
        log.write(f"RESTORE verified: on '{base}', no pipeline worktrees, clean")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Roll speedrun issues end to end: resolve and heal the base, gate "
            "it, run the pipeline, all with no human decisions (#1919)."
        )
    )
    parser.add_argument("--repo", required=True, help="Target repo root path")
    parser.add_argument(
        "--issue", type=int, action="append", required=True,
        help="Issue to roll (repeatable; rolled in order)",
    )
    parser.add_argument(
        "--log-dir", default=None,
        help="Where events/heartbeat/output land. Default: <repo>/data/speedrun/runs",
    )
    parser.add_argument(
        "--assemblyzero-root", default=None,
        help="AssemblyZero checkout that owns orchestrate.py. Default: this tool's repo",
    )
    args, extra = parser.parse_known_args(argv)

    repo_root = Path(args.repo).resolve()
    if not (repo_root / ".git").exists():
        print(f"ERROR: {repo_root} is not a git repository root")
        return 91

    az_root = (
        Path(args.assemblyzero_root).resolve()
        if args.assemblyzero_root
        else Path(__file__).resolve().parents[1]
    )
    log_dir = (
        Path(args.log_dir).resolve()
        if args.log_dir
        else repo_root / "data" / "speedrun" / "runs"
    )

    session = EventLog(log_dir / "session-events.log")
    install_signal_handlers(session)

    # #2007: refuse before spending anything if the tree running this roll is
    # not the code main says it is.
    stale = check_assemblyzero_tree(az_root)
    if stale:
        print(f"BLOCKED: the AssemblyZero tree at {az_root} is not trustworthy:")
        for s in stale:
            print(f"  - {s}")
        print(
            "\n  Bring it level with origin/main (or point --assemblyzero-root "
            "at a tree that is)\n  before rolling. A roll that runs stale "
            "pipeline code fails in ways that look\n  like target-repo problems."
        )
        return 91

    code = 0
    try:
        for issue in args.issue:
            code = roll_issue(repo_root, issue, log_dir, az_root, extra)
            if code != 0:
                print(
                    f"\nSTOPPED at #{issue} (exit {code}); later issues not rolled."
                )
                return code
            time.sleep(1)

        print(f"\nAll {len(args.issue)} issue(s) rolled.")
        return 0
    finally:
        # #2005: hand the repo back the way it was borrowed -- on success, on
        # failure, and on the SignalExit raised by the handlers.
        failures = restore_repo(repo_root, args.issue, session)
        if failures:
            print("\nRESTORE INCOMPLETE:")
            for f in failures:
                print(f"  - {f}")


if __name__ == "__main__":
    sys.exit(main())

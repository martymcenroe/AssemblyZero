"""Every entry-point run leaves a record on disk (#3503).

The roll (`tools/speedrun_roll.py`) writes three files per run to the
target repo's `data/speedrun/runs/`, and the repo's own diagnostics quote
them by tag. The two standalone tools wrote nothing unless `--speedrun`
was passed, so a crash on 2026-09-13 left no run id, no node, no
exception, and no list of what the run had created; the cleanup that
followed was archaeology.

`RunRecord` is the standalone tools' record. It is not the speedrun
instrumentation in `assemblyzero/utils/speedrun.py`, which stays opt-in
and measures laps. This measures nothing and remembers everything.

Two files per run, beside the roll's, with the same directory and the
same `<tag>` shape:

    <tag>.log          everything the tool printed: stdout and stderr, teed
    <tag>-events.log   start, node transitions, the crash record, the end,
                       and what was left in place

where `<tag>` is `<tool>-issue<N>-<HHMMSS>`. The prefix is the tool's name
rather than the roll's `run-` on purpose: `factory_report.py` parses
`run-issue*` as roll logs, and a standalone run is not a roll.

Three rules the class keeps:

- It never raises into the run it records. A record that crashes the run
  it exists to explain is worse than no record; every failure inside it
  becomes a warning line in the events log, or on stderr if even that
  fails.
- The first thing it prints is the tag and the log path, so a launcher
  that captured nothing else still captured the way back to the record.
- `finish` is idempotent and restores stdout and stderr.

"What was left in place" is read from the target repo, not tracked from
the writes: registered worktrees other than the main checkout, local and
remote branches named for the issue, and `git status --porcelain` of the
checkout. That is what the next session has to clean up, whatever code
path produced it.
"""
from __future__ import annotations

import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import IO, Optional

_GIT_TIMEOUT_SECONDS = 20
_PORCELAIN_CAP = 40


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class _Tee:
    """A stream that writes to the console and to the run log.

    Everything not defined here is delegated to the console stream, so
    `fileno()`, `isatty()` and `encoding` keep answering for code that
    hands `sys.stdout` to a subprocess or asks whether it is a terminal.
    """

    def __init__(self, console: IO[str], log: IO[str]) -> None:
        self._console = console
        self._log = log

    def write(self, text: str) -> int:
        n = self._console.write(text)
        try:
            self._log.write(text)
            self._log.flush()
        except (OSError, ValueError):
            # fail-open: the console already got the text; a log that cannot
            # take it must not stop the run it exists to record
            pass
        return n if n is not None else len(text)

    def flush(self) -> None:
        self._console.flush()
        try:
            self._log.flush()
        except (OSError, ValueError):
            # fail-open: same as write; the console is the primary stream
            pass

    def __getattr__(self, name: str):
        return getattr(self._console, name)


def _git(target: Path, *args: str) -> tuple[bool, str]:
    """Run one read-only git command against the target. Never raises."""
    try:
        result = subprocess.run(
            ["git", "-C", str(target), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        # fail-open: the False is the signal; every caller prints the reason
        # as an "unknown" line, so a git that cannot answer is on the record
        return False, f"{type(exc).__name__}: {exc}"
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()
    return True, result.stdout


def left_in_place(target: Path, issue: Optional[int]) -> list[str]:
    """What a run has left in the target repo, by inspection.

    Registered worktrees other than the main checkout; local and remote
    branches named for the issue; the checkout's porcelain status, capped.
    Each line is one thing to clean up, or one line saying why the
    question could not be answered. Never raises.
    """
    found: list[str] = []

    ok, out = _git(target, "worktree", "list", "--porcelain")
    if ok:
        blocks = [b for b in out.strip().split("\n\n") if b.strip()]
        for block in blocks[1:]:  # the first block is the main checkout
            path = branch = ""
            for line in block.splitlines():
                if line.startswith("worktree "):
                    path = line[len("worktree "):]
                elif line.startswith("branch "):
                    branch = line[len("branch "):].replace("refs/heads/", "")
            found.append(f"worktree: {path}" + (f" [{branch}]" if branch else ""))
    else:
        found.append(f"worktrees: unknown ({out})")

    if issue is not None:
        ok, out = _git(target, "branch", "--list", f"{issue}-*")
        if ok:
            for line in out.splitlines():
                name = line.strip().lstrip("*+ ").strip()
                if name:
                    found.append(f"branch: {name}")
        else:
            found.append(f"branches: unknown ({out})")

        ok, out = _git(
            target, "for-each-ref", "--format=%(refname:short)",
            f"refs/remotes/origin/{issue}-*",
        )
        if ok:
            for line in out.splitlines():
                if line.strip():
                    found.append(f"remote branch: {line.strip()}")
        else:
            found.append(f"remote branches: unknown ({out})")

    ok, out = _git(target, "status", "--porcelain", "--untracked-files=all")
    if ok:
        lines = [ln for ln in out.splitlines() if ln.strip()]
        for line in lines[:_PORCELAIN_CAP]:
            found.append(f"checkout: {line}")
        if len(lines) > _PORCELAIN_CAP:
            found.append(f"checkout: ... {len(lines) - _PORCELAIN_CAP} more")
    else:
        found.append(f"checkout: git status unavailable ({out})")

    return found


@dataclass
class RunRecord:
    tool: str
    issue: Optional[int]
    target_repo: Path
    tag: str
    out_path: Path
    events_path: Path
    started_at: float
    argv: list[str] = field(default_factory=list)
    last_node: Optional[str] = None
    _log_fh: Optional[IO[str]] = field(default=None, repr=False)
    _orig_stdout: Optional[IO[str]] = field(default=None, repr=False)
    _orig_stderr: Optional[IO[str]] = field(default=None, repr=False)
    _finished: bool = False

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def start(
        cls,
        tool: str,
        target_repo: Path,
        issue: Optional[int],
        argv: Optional[list[str]] = None,
    ) -> "RunRecord":
        """Open the record, tee the streams, print the tag. Never raises."""
        target_repo = Path(target_repo)
        stamp = datetime.now().strftime("%H%M%S")
        who = f"issue{issue}" if issue is not None else "run"
        tag = f"{tool}-{who}-{stamp}"
        runs_dir = target_repo / "data" / "speedrun" / "runs"
        record = cls(
            tool=tool,
            issue=issue,
            target_repo=target_repo,
            tag=tag,
            out_path=runs_dir / f"{tag}.log",
            events_path=runs_dir / f"{tag}-events.log",
            started_at=time.time(),
            argv=list(argv if argv is not None else sys.argv),
        )
        try:
            runs_dir.mkdir(parents=True, exist_ok=True)
            record._log_fh = record.out_path.open(
                "a", encoding="utf-8", errors="replace",
            )
            record._orig_stdout, record._orig_stderr = sys.stdout, sys.stderr
            sys.stdout = _Tee(sys.stdout, record._log_fh)
            sys.stderr = _Tee(sys.stderr, record._log_fh)
        except OSError as exc:
            # fail-open: console-only is the fallback the warning names; the
            # run starts regardless, and the events log is still attempted
            record._warn(f"run log not opened ({exc}); console only")
        print(f"[run] {record.tag} -> {record.out_path}", flush=True)
        record.event(
            f"start tool={tool} issue={issue} target={target_repo} "
            f"cwd={Path.cwd()} argv={' '.join(record.argv)}"
        )
        ok, head = _git(target_repo, "rev-parse", "--short", "HEAD")
        ok2, branch = _git(target_repo, "branch", "--show-current")
        record.event(
            f"target head={head.strip() if ok else 'unknown'} "
            f"branch={branch.strip() if ok2 else 'unknown'}"
        )
        return record

    def node(self, name: str) -> None:
        """A node transition. Called by the tool as the graph streams."""
        if not name or name == "__end__":
            return
        self.last_node = name
        self.event(f"node {name}")

    def crash(self, exc: BaseException) -> None:
        """The crash record: what raised, where the run was, what it left.

        Written before the process exits and before `finish`, so a
        `finish` that never comes (a second exception on the way out)
        still leaves the record.
        """
        message = " ".join(str(exc).split()) or "(no message)"
        self.event(f"crash type={type(exc).__name__} message={message}")
        self.event(f"crash last_node={self.last_node or 'unknown'}")
        for line in traceback.format_exception(type(exc), exc, exc.__traceback__):
            for sub in line.rstrip("\n").splitlines():
                self._write_events(f"    {sub}")
        self._record_left_in_place()

    def finish(self, outcome: str, error_message: str = "") -> None:
        """Close the record. Idempotent. Restores stdout and stderr."""
        if self._finished:
            return
        self._finished = True
        seconds = round(time.time() - self.started_at, 1)
        error = " ".join(str(error_message).split())
        self.event(
            f"end outcome={outcome} seconds={seconds}"
            + (f" error={error}" if error else "")
        )
        items = self._record_left_in_place()
        try:
            print(f"[run] left in place ({len(items)}):", flush=True)
            for item in items:
                print(f"[run]   {item}", flush=True)
            print(f"[run] record: {self.events_path}", flush=True)
        except (OSError, ValueError):
            # fail-open: the events log already holds the list; a console that
            # cannot take it changes nothing about the record
            pass
        self._restore_streams()

    # ------------------------------------------------------------------
    # writing
    # ------------------------------------------------------------------

    def event(self, message: str) -> None:
        self._write_events(f"{_stamp()} {message}")

    def _record_left_in_place(self) -> list[str]:
        items = left_in_place(self.target_repo, self.issue)
        self._write_events(f"{_stamp()} left in place ({len(items)}):")
        for item in items:
            self._write_events(f"    {item}")
        if not items:
            self._write_events("    (nothing)")
        return items

    def _write_events(self, line: str) -> None:
        try:
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with self.events_path.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            # fail-open: the warning carries the lost line to stderr; the
            # record is best-effort by design and never raises into the run
            self._warn(f"events log not written ({exc}): {line}")

    def _warn(self, message: str) -> None:
        stream = self._orig_stderr or sys.stderr
        try:
            stream.write(f"[run] warning: {message}\n")
            stream.flush()
        except (OSError, ValueError):
            # fail-open: the last resort; there is nothing left to report to
            pass

    def _restore_streams(self) -> None:
        if self._orig_stdout is not None:
            sys.stdout = self._orig_stdout
            self._orig_stdout = None
        if self._orig_stderr is not None:
            sys.stderr = self._orig_stderr
            self._orig_stderr = None
        if self._log_fh is not None:
            try:
                self._log_fh.close()
            except OSError:
                # fail-open: a handle that will not close is already useless;
                # the streams were restored above and the run is ending
                pass
            self._log_fh = None

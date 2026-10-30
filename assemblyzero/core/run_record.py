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

- A failure of the record is loud and alerts the operator (ADR 0236,
  #3791), and it does not stop the run. Nothing the run produces reads its
  record: the readers are the people and sessions that diagnose and clean
  up after it. So a log that cannot be opened, written, flushed or closed,
  and a git question about the target that cannot be answered, each call
  ``alert_operator`` with the path and the cause, once per thing that
  broke; a line the events log could not keep is an ERROR line on the
  console instead. Two things do raise: ``left_in_place`` when git cannot
  answer one of its questions, since a partial list would make wrong
  finishing commands (the record turns that into "unknown" and an alert),
  and ``profile`` when the record cannot describe the profile, since the
  run's seats would fail on it later, after spending.
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

from assemblyzero.core import alert

_GIT_TIMEOUT_SECONDS = 20
_PORCELAIN_CAP = 40

_WHERE = "assemblyzero.core.run_record"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _cause(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


class GitQueryError(RuntimeError):
    """git could not answer a question about the target: the command, the
    target, and the cause (the exception, or the exit code and stderr)."""


class _Tee:
    """A stream that writes to the console and to the run log.

    Everything not defined here is delegated to the console stream, so
    `fileno()`, `isatty()` and `encoding` keep answering for code that
    hands `sys.stdout` to a subprocess or asks whether it is a terminal.

    The log is the record's, read through it on every write, because the
    two tees share one log. When the log refuses a write or a flush, the
    record detaches it from both tees before the alert goes out (the alert
    prints through this very stream), so the run goes on console-only and
    the operator is told once (#3791). A tee the record has already closed
    writes to the console only: a logging handler made during the run still
    holds it, and text printed after the record is finished belongs to no
    record, which is not a failure.
    """

    def __init__(self, console: IO[str], record: RunRecord) -> None:
        self._console = console
        self._record = record

    def write(self, text: str) -> int:
        n = self._console.write(text)
        log = self._record._teeing()
        if log is not None:
            try:
                log.write(text)
                log.flush()
            except (OSError, ValueError) as exc:
                self._record._detach_log()
                alert.alert_operator(
                    what=f"write the run log {self._record.out_path}",
                    where=f"{_WHERE}._Tee.write",
                    cause=_cause(exc),
                    consequence=(
                        "the run goes on; from here what it prints reaches the "
                        "console only, and the run log ends at the last line it took"
                    ),
                    repo=str(self._record.target_repo), issue=self._record.issue,
                )
        return n if n is not None else len(text)

    def flush(self) -> None:
        self._console.flush()
        log = self._record._teeing()
        if log is not None:
            try:
                log.flush()
            except (OSError, ValueError) as exc:
                self._record._detach_log()
                alert.alert_operator(
                    what=f"flush the run log {self._record.out_path}",
                    where=f"{_WHERE}._Tee.flush",
                    cause=_cause(exc),
                    consequence=(
                        "the run goes on; from here what it prints reaches the "
                        "console only, and the run log may lack its last lines"
                    ),
                    repo=str(self._record.target_repo), issue=self._record.issue,
                )

    def __getattr__(self, name: str):
        return getattr(self._console, name)


def _git(target: Path, *args: str) -> str:
    """Run one read-only git command against the target; its stdout.

    Raises ``GitQueryError`` naming the command, the target and the cause
    when git cannot run, times out, or exits non-zero (#3791). It used to
    return ``(False, reason)``, which each caller turned into an "unknown"
    line and nobody heard about.
    """
    command = f"git {' '.join(args)}"
    try:
        result = subprocess.run(
            ["git", "-C", str(target), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitQueryError(f"{command} in {target} could not run: {_cause(exc)}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "(no output)"
        raise GitQueryError(
            f"{command} in {target} failed: exit {result.returncode}: {detail}"
        )
    return result.stdout


def left_in_place(target: Path, issue: Optional[int]) -> list[str]:
    """What a run has left in the target repo, by inspection.

    Registered worktrees other than the main checkout; local and remote
    branches named for the issue; the checkout's porcelain status, capped.
    Each line is one thing to clean up.

    Raises ``GitQueryError`` when git cannot answer one of the questions
    (#3791). The list used to carry an "unknown" line in that question's
    place and the answers to the rest. A list missing one kind is not a
    shorter list but a wrong one, and so are the finishing commands built
    from it: a branch offered for ``git branch -d`` while a worktree nobody
    could list still holds it. ``RunRecord`` records the whole list as
    unknown, with the cause, and alerts.
    """
    found: list[str] = []

    out = _git(target, "worktree", "list", "--porcelain")
    blocks = [b for b in out.strip().split("\n\n") if b.strip()]
    for block in blocks[1:]:  # the first block is the main checkout
        path = branch = ""
        for line in block.splitlines():
            if line.startswith("worktree "):
                path = line[len("worktree "):]
            elif line.startswith("branch "):
                branch = line[len("branch "):].replace("refs/heads/", "")
        found.append(f"worktree: {path}" + (f" [{branch}]" if branch else ""))

    if issue is not None:
        out = _git(target, "branch", "--list", f"{issue}-*")
        for line in out.splitlines():
            name = line.strip().lstrip("*+ ").strip()
            if name:
                found.append(f"branch: {name}")

        out = _git(
            target, "for-each-ref", "--format=%(refname:short)",
            f"refs/remotes/origin/{issue}-*",
        )
        for line in out.splitlines():
            if line.strip():
                found.append(f"remote branch: {line.strip()}")

    out = _git(target, "status", "--porcelain", "--untracked-files=all")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    for line in lines[:_PORCELAIN_CAP]:
        found.append(f"checkout: {line}")
    if len(lines) > _PORCELAIN_CAP:
        found.append(f"checkout: ... {len(lines) - _PORCELAIN_CAP} more")

    return found


#: Where the squash-merge orphan recipe lives, named in every branch cleanup.
_GRAFT_ADR = "AssemblyZero docs/adrs/0217-squash-merge-orphan-graft-cleanup.md"


def finishing_commands(target: Path, items: list[str]) -> list[str]:
    """The exact commands that clear what ``left_in_place`` found (#3510).

    A worktree or a branch the run left has an owner only if something says
    how it ends. This says it, in order: worktrees before branches (``git
    branch -d`` refuses while a worktree holds the branch), a prune before the
    delete (a stale remote ref makes ``-d`` prove nothing), and the ADR-0217
    graft for the squash-merge case, where ``-d`` refuses. Never ``-D`` and
    never ``--force``. Checkout lines get no command: which of them are work
    product is the operator's call. Pure; runs nothing.
    """
    worktrees: list[str] = []
    branches: list[str] = []
    remotes: list[str] = []
    for item in items:
        kind, _, rest = item.partition(": ")
        if kind == "worktree":
            worktrees.append(rest.split(" [", 1)[0])
        elif kind == "branch":
            branches.append(rest)
        elif kind == "remote branch":
            remotes.append(rest.removeprefix("origin/"))

    t = str(target)
    out: list[str] = []
    for path in worktrees:
        out.append(
            f"git -C {t} worktree remove {path}    "
            "# move any work product out of it first; never --force"
        )
    if branches:
        out.append(f"git -C {t} fetch --prune origin")
    for name in branches:
        out.append(
            f"git -C {t} branch -d {name}    "
            f"# after a squash merge -d refuses: {_GRAFT_ADR}; never -D"
        )
    for name in remotes:
        out.append(
            f"git -C {t} push origin --delete {name}    "
            "# only once its PR has merged or been closed"
        )
    return out


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
    #: Whether the tees still write into ``_log_fh``. False before the log
    #: opens, once it has refused a write, and once the record is finished.
    _log_live: bool = field(default=False, repr=False)
    _orig_stdout: Optional[IO[str]] = field(default=None, repr=False)
    _orig_stderr: Optional[IO[str]] = field(default=None, repr=False)
    _finished: bool = False
    #: What has already alerted the operator, so one broken events log is
    #: one alert and not one per line the run writes.
    _alerted: set[str] = field(default_factory=set, repr=False)

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
        """Open the record, tee the streams, print the tag.

        A run log that cannot be opened, and a target whose head git cannot
        read, alert the operator with the cause (#3791); the run starts
        regardless, since nothing it does reads its record.
        """
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
        except OSError as exc:
            alert.alert_operator(
                what=f"open the run log {record.out_path}",
                where=f"{_WHERE}.RunRecord.start",
                cause=_cause(exc),
                consequence=(
                    "the run starts regardless; what it prints reaches the "
                    "console only, and the events log is still attempted"
                ),
                repo=str(target_repo), issue=issue,
            )
        else:
            record._log_live = True
            record._orig_stdout, record._orig_stderr = sys.stdout, sys.stderr
            sys.stdout = _Tee(sys.stdout, record)
            sys.stderr = _Tee(sys.stderr, record)
        print(f"[run] {record.tag} -> {record.out_path}", flush=True)
        record.event(
            f"start tool={tool} issue={issue} target={target_repo} "
            f"cwd={Path.cwd()} argv={' '.join(record.argv)}"
        )
        try:
            head = _git(target_repo, "rev-parse", "--short", "HEAD").strip()
            branch = _git(target_repo, "branch", "--show-current").strip()
        except GitQueryError as exc:
            record.event(f"target head=unknown branch=unknown ({exc})")
            alert.alert_operator(
                what=f"read the head of the target {target_repo} for the run record",
                where=f"{_WHERE}.RunRecord.start",
                cause=str(exc),
                consequence=(
                    "the run starts regardless; its record does not say which "
                    "commit or branch it started from"
                ),
                repo=str(target_repo), issue=issue,
            )
        else:
            record.event(f"target head={head} branch={branch}")
        # #3565: from here every model call of the run writes a `model` event.
        from assemblyzero.core.model_record import open_sink

        open_sink(record)
        return record

    def profile(self, profile: dict) -> None:
        """The run's model profile: name, content hash, and the seat table.

        Called by the entry point once it has loaded the profile, so the
        record opens with which model every seat was going to ask (#3565).

        A profile whose seats cannot be resolved raises (#3791). It used to
        be a warning and the run went on, but every entry point resolves the
        same seat table to print it just before this, and a seat that does
        not resolve here fails the stage that uses it, after the run has
        spent on the stages before. A line the events log cannot take is
        ``_write_events``'s to report, and does not raise.
        """
        from assemblyzero.core.seats import seat_table

        self.event(
            f"profile name={profile.get('name')} "
            f"sha256={profile.get('sha256')} "
            f"selected_by={profile.get('selected_by') or 'given'} "
            f"source={profile.get('source')}"
        )
        overrides = profile.get("overrides") or {}
        if overrides:
            self.event(
                "profile overrides "
                + " ".join(f"{k}={v}" for k, v in sorted(overrides.items()))
            )
        for name, seat in seat_table(profile).items():
            self.event(
                f"seat {name} spec={seat.spec} effort={seat.effort or ''} "
                f"resolved={seat.resolved_model_id} provider={seat.provider}"
            )

    def model(self, fields: dict) -> None:
        """One model call: seat, spec, resolved id, provider, fallback,
        effort, duration and tokens, as JSON after the word ``model``."""
        import json

        self.event("model " + json.dumps(fields, sort_keys=True))

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
        """Close the record. Idempotent. Restores stdout and stderr.

        A console that cannot take the left-in-place list alerts the
        operator (#3791): the events log holds it, and the operator may not
        be at the console the run was launched from. The streams are
        restored even when an alert on the way out cannot be delivered and
        raises.
        """
        if self._finished:
            return
        self._finished = True
        try:
            from assemblyzero.core.model_record import close_sink

            close_sink(self)
            seconds = round(time.time() - self.started_at, 1)
            error = " ".join(str(error_message).split())
            self.event(
                f"end outcome={outcome} seconds={seconds}"
                + (f" error={error}" if error else "")
            )
            items, unknown = self._record_left_in_place()
            try:
                if items is None:
                    print(f"[run] left in place: unknown ({unknown})", flush=True)
                else:
                    print(f"[run] left in place ({len(items)}):", flush=True)
                    for item in items:
                        print(f"[run]   {item}", flush=True)
                    commands = finishing_commands(self.target_repo, items)
                    if commands:
                        print("[run] to finish:", flush=True)
                        for command in commands:
                            print(f"[run]   {command}", flush=True)
                print(f"[run] record: {self.events_path}", flush=True)
            except (OSError, ValueError) as exc:
                alert.alert_operator(
                    what="print what the run left in place to the console",
                    where=f"{_WHERE}.RunRecord.finish",
                    cause=_cause(exc),
                    consequence=(
                        "the console did not get the list or the commands that "
                        f"finish it; the events log {self.events_path} holds both"
                    ),
                    repo=str(self.target_repo), issue=self.issue,
                )
        finally:
            self._restore_streams()

    # ------------------------------------------------------------------
    # writing
    # ------------------------------------------------------------------

    def event(self, message: str) -> None:
        self._write_events(f"{_stamp()} {message}")

    def _record_left_in_place(self) -> tuple[list[str] | None, str]:
        """Write what the run left in place to the events log, and return it.

        When git cannot answer, the events log says the list is unknown and
        why, and ``(None, cause)`` comes back: no partial list, and no
        finishing commands built from one. The operator is alerted the first
        time in a record; a crashed run asks twice (``crash``, then
        ``finish``), and the second asking is an ERROR line.
        """
        try:
            items = left_in_place(self.target_repo, self.issue)
        except GitQueryError as exc:
            self._write_events(f"{_stamp()} left in place: unknown ({exc})")
            self._write_events(
                "    nothing here says what this run left: inspect the target's "
                "worktrees, branches and checkout by hand before the next run"
            )
            if "left in place" in self._alerted:
                self._error_line(f"what the run left in place is still unknown: {exc}")
            else:
                self._alerted.add("left in place")
                alert.alert_operator(
                    what=f"list what the run left in place in {self.target_repo}",
                    where=f"{_WHERE}.RunRecord._record_left_in_place",
                    cause=str(exc),
                    consequence=(
                        f"the record {self.events_path} says the list is unknown; "
                        "the target's worktrees, branches and checkout have to be "
                        "inspected by hand before the next run"
                    ),
                    repo=str(self.target_repo), issue=self.issue,
                )
            return None, str(exc)
        self._write_events(f"{_stamp()} left in place ({len(items)}):")
        for item in items:
            self._write_events(f"    {item}")
        if not items:
            self._write_events("    (nothing)")
        commands = finishing_commands(self.target_repo, items)
        if commands:
            self._write_events(f"{_stamp()} to finish:")
            for command in commands:
                self._write_events(f"    {command}")
        return items, ""

    def _write_events(self, line: str) -> None:
        """Append one line to the events log.

        A line the log cannot take is lost from the record, and the run goes
        on (#3791). The first such failure in a record alerts the operator
        with the cause and the line; every later one is an ERROR line on the
        console carrying its line, so a broken events log is one alert and
        not one per node and model call.
        """
        try:
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with self.events_path.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            if "events log" in self._alerted:
                self._error_line(
                    f"events log {self.events_path} not written ({_cause(exc)}): {line}"
                )
            else:
                self._alerted.add("events log")
                alert.alert_operator(
                    what=f"write the events log {self.events_path}",
                    where=f"{_WHERE}.RunRecord._write_events",
                    cause=_cause(exc),
                    consequence=(
                        f"the run goes on; this line is lost from its record: "
                        f"{line.strip()}; each later line the log refuses is an "
                        "ERROR line on stderr instead"
                    ),
                    repo=str(self.target_repo), issue=self.issue,
                )

    def _error_line(self, message: str) -> None:
        """One ERROR line about the record on the console's stderr, past the tee.

        A stderr that cannot take it alerts the operator with the line
        (#3791); it used to be dropped without a word.
        """
        stream = self._orig_stderr or sys.stderr
        try:
            stream.write(f"ERROR [run] {message}\n")
            stream.flush()
        except (OSError, ValueError) as exc:
            alert.alert_operator(
                what="write an ERROR line about the run record to stderr",
                where=f"{_WHERE}.RunRecord._error_line",
                cause=_cause(exc),
                consequence=f"the line is lost from the console: {message}",
                repo=str(self.target_repo), issue=self.issue,
            )

    def _teeing(self) -> IO[str] | None:
        """The run log, while the tees still write into it."""
        return self._log_fh if self._log_live else None

    def _detach_log(self) -> None:
        """Stop both tees writing to the run log, which refused a write.

        The handle stays, so ``_restore_streams`` still closes it.
        """
        self._log_live = False
        self._alerted.add("run log")

    def _restore_streams(self) -> None:
        if self._orig_stdout is not None:
            sys.stdout = self._orig_stdout
            self._orig_stdout = None
        if self._orig_stderr is not None:
            sys.stderr = self._orig_stderr
            self._orig_stderr = None
        if self._log_fh is not None:
            # Detached before the close, so a tee that outlives the record
            # (a logging handler made during the run holds one) writes to
            # the console only instead of into a closed file.
            handle, self._log_fh, self._log_live = self._log_fh, None, False
            try:
                handle.close()
            except OSError as exc:
                if "run log" in self._alerted:
                    self._error_line(
                        f"the run log {self.out_path}, which had already refused "
                        f"a write, did not close either ({_cause(exc)})"
                    )
                else:
                    alert.alert_operator(
                        what=f"close the run log {self.out_path}",
                        where=f"{_WHERE}.RunRecord._restore_streams",
                        cause=_cause(exc),
                        consequence=(
                            "the run has ended; its run log may lack the lines "
                            "still buffered when it closed"
                        ),
                        repo=str(self.target_repo), issue=self.issue,
                    )

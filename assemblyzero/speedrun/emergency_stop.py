"""An emergency stop the operator can reach without an agent (#2422).

2026-08-15: the operator ordered a live roll killed and had no way to do it.
The detached run streams into the console it was launched from, so there was no
free prompt; the detach wrapper makes the run immune to casual interruption by
design; and the stop that did exist was neither taught nor findable. The kill
was finally performed by an agent reading a pid out of the events log and
running a manual tree-kill -- which required knowing the log layout, the pid
convention, and that Git Bash mangles `taskkill /F` into a drive path. The
operator's stated fallback was rebooting the machine.

None of that is an operator interface. This module is the interface.

## The two paths, and why both are needed

**A command** (`--kill`) is the path when a prompt exists. It is exact: it
knows which pid, it stamps the run's own events log, and it returns a
distinguishable code.

**A kill file** is the path when no prompt exists, which was the actual
situation. `data/speedrun/KILL-<issue>` (or a bare `KILL` for any issue) is
something a file manager, a second agent session, or `touch` can create. The
launcher watches for it WHILE a child call is in flight, not merely between
stages -- a stop that only lands at a stage boundary is no use against a call
that has thirteen minutes left to run, which is the case that produced this
issue.

## Killed is a verdict, not a crash

An ordered stop is reported distinctly (`KILL_EXIT_CODE`), stamped into the
run's own events log with `KILLED BY OPERATOR`, and leaves the resume surfaces
readable -- so the postmortem and the healing ledger see a decision rather than
a corpse, and the next launch resumes instead of refusing or resetting.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

#: The launcher's exit code for an operator-ordered stop. Distinct from 0
#: (success), 91 (a gate problem), 92 (a provider storm) and 93 (a requirements
#: conflict), so a stop is never read as any kind of failure.
KILL_EXIT_CODE = 94

#: Stamped into the run's events log. The postmortem and the healing ledger
#: both grep for it, so it is a contract rather than prose.
KILLED_MARKER = "KILLED BY OPERATOR"

#: Where kill files live -- beside `runs/`, under the target repo's data dir.
KILL_DIR_PARTS = ("data", "speedrun")

#: How often the watch looks. A stop the operator has already decided on should
#: land in seconds, and a stat every two seconds costs nothing beside a call
#: measured in minutes.
KILL_POLL_SECONDS = 2.0


def kill_dir(repo_root: Path) -> Path:
    """Directory the operator drops a kill file into."""
    return Path(repo_root).joinpath(*KILL_DIR_PARTS)


def kill_file_candidates(repo_root: Path, issue: int | None = None) -> list[Path]:
    """Every path that means stop, most specific first.

    The bare `KILL` is deliberate: under stress the operator should not have to
    remember which issue number is currently rolling, and a batch is stopped as
    a batch. The issue-scoped name exists so a machine running two campaigns can
    stop one of them.
    """
    base = kill_dir(repo_root)
    names = [f"KILL-{issue}"] if issue is not None else []
    names.append("KILL")
    return [base / name for name in names]


def find_kill_file(repo_root: Path, issue: int | None = None) -> Path | None:
    """The kill file the operator has dropped, or None."""
    for candidate in kill_file_candidates(repo_root, issue):
        try:
            if candidate.exists():
                return candidate
        except OSError:
            # An unreadable data dir must never be the reason a roll cannot be
            # stopped, but it is equally never a reason to stop one.
            continue
    return None


def clear_kill_files(repo_root: Path, issue: int | None = None) -> list[Path]:
    """Remove kill files after acting on them, returning what was removed.

    Load-bearing: a kill file that outlives the run it stopped would stop the
    NEXT launch too, which the operator would experience as a launcher that
    refuses to start and says nothing useful about why.
    """
    removed: list[Path] = []
    for candidate in kill_file_candidates(repo_root, issue):
        try:
            if candidate.exists():
                candidate.unlink()
                removed.append(candidate)
        except OSError:
            continue
    return removed


def stop_command(repo_root: Path, issue: int | None = None) -> str:
    """The exact command that stops this roll, ready to paste."""
    issue_part = f" --issue {issue}" if issue is not None else ""
    return (
        f"poetry run python tools/speedrun_roll.py --repo {repo_root} "
        f"--kill{issue_part}"
    )


def kill_file_command(repo_root: Path, issue: int | None = None) -> str:
    """The promptless stop, as a command that creates the file."""
    target = kill_file_candidates(repo_root, issue)[0]
    return f"touch {target.as_posix()}"


def banner_lines(
    repo_root: Path, issue: int | None, log_path: Path | None = None
) -> list[str]:
    """The stop instructions every launch prints in its first lines.

    An emergency control the operator cannot remember under stress does not
    exist, so it is taught at the moment of launch beside the log path -- not
    filed in a runbook they would have to already be calm enough to find.
    """
    lines = [
        "",
        "  TO STOP THIS ROLL:",
        f"    {stop_command(repo_root, issue)}",
        "",
        "  If this console has no free prompt, create the stop file instead",
        "  (from any other window, or any file manager):",
        f"    {kill_file_command(repo_root, issue)}",
    ]
    if log_path is not None:
        lines += ["", f"  Log: {log_path}"]
    lines.append("")
    return lines


def tree_kill(pid: int | str) -> tuple[bool, str]:
    """Kill a process and everything it spawned.

    The pipeline is four to eight processes deep, so killing the parent alone
    leaves model-calling orphans reparented to nothing that keep writing to the
    target repo. Measured 2026-08-15: eight processes in one roll's tree.
    """
    pid = str(pid)
    if sys.platform == "win32":
        # /T for the tree, /F because a python child mid-subprocess does not
        # answer a polite close. MSYS_NO_PATHCONV is set for the child so Git
        # Bash cannot rewrite `/F` into a drive path -- the exact trap that made
        # the operator's first manual attempt fail.
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        result = subprocess.run(
            ["taskkill", "/PID", pid, "/T", "/F"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env,
        )
        detail = ((result.stdout or "") + (result.stderr or "")).strip()
        return result.returncode == 0, detail

    # POSIX. Kill the child's process GROUP only when it has one of its own,
    # and never otherwise.
    #
    # A child spawned without `start_new_session` INHERITS our process group,
    # so `killpg(getpgid(child))` names the group this process is in and takes
    # us down with the target. Caught on CI: ubuntu-latest ran the mid-call
    # fixtures, the group kill reached pytest, and the job hung at three times
    # its normal duration. An emergency stop whose blast radius includes its
    # own caller is not a stop.
    try:
        target = int(pid)
        group = os.getpgid(target)
    except (OSError, ValueError) as exc:
        return False, str(exc)
    try:
        if group != os.getpgid(0):
            os.killpg(group, signal.SIGKILL)
        else:
            os.kill(target, signal.SIGKILL)
        return True, ""
    except OSError as exc:
        return False, str(exc)


class KillWatch:
    """Watches for a kill file while a child runs, and kills it mid-call.

    The child is a blocking `subprocess` call that can legitimately run for ten
    minutes, so the watch has to be concurrent with it rather than sequenced
    around it. A thread polling `find_kill_file` is the whole mechanism: when
    the file appears it tree-kills the child, which makes the launcher's wait
    return normally, and `fired` tells the caller the death was ordered rather
    than a crash.

    Deliberately NOT a signal handler: on Windows a signal cannot interrupt a
    blocking wait, which is the platform this runs on.
    """

    def __init__(
        self,
        repo_root: Path,
        issue: int | None,
        on_kill: Callable[[str], None] | None = None,
        poll_seconds: float = KILL_POLL_SECONDS,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.issue = issue
        self.on_kill = on_kill or (lambda _m: None)
        self.poll_seconds = poll_seconds
        self.fired = False
        self.kill_file: Path | None = None
        self._proc: subprocess.Popen | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def watch(self, proc: subprocess.Popen) -> KillWatch:
        """Begin watching on behalf of `proc`."""
        self._proc = proc
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __enter__(self) -> KillWatch:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_seconds + 5)
            self._thread = None

    def check_now(self) -> bool:
        """One synchronous look, for stage boundaries and between issues."""
        found = find_kill_file(self.repo_root, self.issue)
        if found is None:
            return False
        self.fired = True
        self.kill_file = found
        return True

    def _loop(self) -> None:
        while not self._stop.is_set():
            proc = self._proc
            if proc is not None and proc.poll() is not None:
                return  # the child finished on its own; nothing to stop
            found = find_kill_file(self.repo_root, self.issue)
            if found is not None:
                self._fire(found)
                return
            self._stop.wait(self.poll_seconds)

    def _fire(self, found: Path) -> None:
        self.fired = True
        self.kill_file = found
        proc = self._proc
        if proc is None or proc.poll() is not None:
            self.on_kill(f"{KILLED_MARKER}: stop file {found.name} seen")
            return
        ok, detail = tree_kill(proc.pid)
        if ok:
            self.on_kill(
                f"{KILLED_MARKER}: stop file {found.name} seen; tree-killed "
                f"pid {proc.pid} mid-call"
            )
        else:
            self.on_kill(
                f"{KILLED_MARKER}: stop file {found.name} seen; pid "
                f"{proc.pid} would not die ({detail or 'no detail'})"
            )
            # A tree-kill that failed still means the operator said stop, so
            # the wait must not be allowed to run to completion.
            try:
                proc.kill()
            except OSError:
                pass


def killed_verdict_lines(issue: int | None, kill_file: Path | None) -> list[str]:
    """What the operator reads after an ordered stop.

    Says stopped rather than failed, and names the resume: the next launch
    reuses the stages that passed, so nothing already paid for is re-paid.
    """
    who = f"#{issue}" if issue is not None else "the roll"
    source = f"stop file {kill_file.name}" if kill_file else "--kill"
    return [
        "",
        f"STOPPED BY OPERATOR: {who} was stopped on purpose ({source}).",
        "  This is not a failure. The stages that had already passed are",
        "  preserved, and the next launch resumes from where this one stopped",
        "  rather than redrawing them.",
        "",
    ]

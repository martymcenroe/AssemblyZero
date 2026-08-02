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

`--detach` hands the roll to Windows Task Scheduler instead of running it here
(#2015). A roll started from an agent session is a descendant of that session's
shell, and a harness kill of the shell takes the entire tree with it -- measured
2026-07-31, and neither DETACHED_PROCESS nor CREATE_BREAKAWAY_FROM_JOB escaped
it. A scheduled task is spawned by the Task Scheduler service, so it is not in
the tree at all and nothing done to the launching session can reach it.

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
from xml.sax.saxutils import escape

import speedrun_clean_check as gate
import speedrun_new_attempt as attempt
import speedrun_reset as reset

# #2040: this tool spawns git, gh and schtasks itself, and a detached roll has
# no console for them to inherit. Installed at import, so it is in force before
# the first _run().
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from assemblyzero.core.no_console import install as _install_no_console

    _install_no_console()
except ImportError:  # pragma: no cover - tool copied outside the package
    pass

# Imported after the sys.path insert above -- the package root is not on the
# path when this tool is run as a script from tools/ (#2077).
from assemblyzero.speedrun.must_resolve import (  # noqa: E402
    RUN_START_ENV,
    RUN_TAG_ENV,
    open_must_resolve_issues,
    refusal_message,
)
from assemblyzero.speedrun.worktrees import (  # noqa: E402
    sweep_pipeline_worktrees,
)

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
    # #2012: the checkout is normally on the DEFAULT branch now, so HEAD is no
    # longer a source of the prefix. It is still honoured when the operator has
    # deliberately checked an attempt out; otherwise the campaign default wins.
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


def resolve_attempt_branch(repo_root: Path) -> str:
    """The newest attempt branch on origin, or "" if there is none (#2012).

    Base discovery used to read the CHECKOUT, which is why every operation left
    the operator parked on an attempt branch: the tooling had to stand on it to
    know its name. Nothing else needs that -- the worktree is cut from an
    explicit base and PRs target it by name -- so the attempt is resolved from
    refs and the main checkout stays on the default branch.

    Graveyarded attempts are excluded by prefix: they are the lab notebook of
    finished runs, not candidates to roll onto.
    """
    prefix = attempt_prefix(repo_root)
    esc = re.escape(prefix)
    pattern = re.compile(rf"^{esc}-(\d+)$")

    result = _run(["git", "ls-remote", "--heads", "origin"], cwd=repo_root)
    best: tuple[int, str] | None = None
    for line in result.stdout.splitlines():
        if "refs/heads/" not in line:
            continue
        name = line.split("refs/heads/", 1)[1].strip()
        match = pattern.match(name)
        if match:
            n = int(match.group(1))
            if best is None or n > best[0]:
                best = (n, name)
    return best[1] if best else ""


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
    base = resolve_attempt_branch(repo_root)
    if not base:
        log.write("BASE no attempt branch exists -- establishing one")
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
        log.write(f"GATE still dirty after reset ({len(debris)}) -- {len(debris)} left")
        for d in debris:
            log.write(f"  {d}")
        return replace_or_refuse(repo_root, base, issue, debris, log)

    log.write(f"BASE '{base}' clean for #{issue} after self-heal")
    return base


def commits_carried(repo_root: Path, base: str) -> int | None:
    """Commits the base holds beyond the default branch, or None if unknowable.

    None is deliberate and is NOT folded into 0. "I could not measure this" and
    "there is nothing here" lead to opposite decisions, and treating the first
    as the second fails in the destructive direction -- it would authorise
    discarding an arc precisely when the tooling cannot see what is on it.
    """
    default = attempt.default_branch(repo_root)
    candidates = [default] if default else []
    candidates += ["origin/main", "origin/master"]

    for ref in candidates:
        if not ref:
            continue
        if _run(
            ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            cwd=repo_root,
        ).returncode != 0:
            continue
        result = _run(
            ["git", "rev-list", "--count", f"{ref}..origin/{base}"], cwd=repo_root
        )
        out = result.stdout.strip()
        if result.returncode == 0 and out.isdigit():
            return int(out)
    return None


def replace_or_refuse(
    repo_root: Path, base: str, issue: int, debris: list[str], log: EventLog
) -> str | None:
    """Cut a fresh attempt only when nothing is lost by it (#2028).

    Replacing the base is right for one that is level with the default branch,
    or already carries this issue's work: nothing accumulated is discarded.

    Mid-arc it is not. On 2026-07-31 a single local branch the reset could not
    delete -- one branch, for #2 -- was met by walking away from a base holding
    four finished phases of #7, #41, #1 and #4, and the log called it routine
    progress. It happened twice; both times the arc survived by accident rather
    than design.

    The costs are not comparable. Refusing costs one stopped run and a message
    naming what to clear. Replacing silently discards every phase accumulated
    so far, and the next roll builds against a base that has never seen them.
    """
    carried = commits_carried(repo_root, base)
    if carried == 0:
        return establish_new_attempt(repo_root, log)

    amount = (
        "an unknown amount of" if carried is None else f"{carried} commit(s) of"
    )
    log.write(
        f"ABORT refusing to replace '{base}': it carries {amount} "
        f"accumulated work beyond the default branch, and {len(debris)} finding(s) "
        f"for #{issue} could not be cleared."
    )
    for d in debris:
        log.write(f"  unresolved: {d}")
    log.write(
        "  Clear the finding(s) above and roll again. A branch carrying commits "
        "reachable from nowhere else refuses a safe delete, which is correct -- "
        "rename it under graveyard/ to keep the commits and free the name."
    )
    return None


# =============================================================================
# The roll
# =============================================================================


def roll_issue(
    repo_root: Path, issue: int, log_dir: Path, az_root: Path, extra: list[str]
) -> int:
    tag = f"run-issue{issue}-{datetime.now().strftime('%H%M%S')}"
    run_start = _stamp()
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
                env=_child_env(tag, run_start),
                # #2037: no console for the pipeline either. Under Task
                # Scheduler the parent has none to inherit, so without this the
                # child allocates its own.
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                ),
            )
        log.write(f"CHILD EXITED rc={proc.returncode}")

    log.write(f"EXIT rc={proc.returncode}")
    return proc.returncode


def _child_env(tag: str = "", start: str = "") -> dict[str, str]:
    env = dict(os.environ)
    env["CLAUDECODE"] = ""         # nested Claude sessions fail without this
    env["PYTHONUNBUFFERED"] = "1"  # Python buffers stdout when not on a TTY
    # #2072: only the launcher knows the tag its events/heartbeat/stdout triplet
    # is named after, and that name is what a human needs to go read the logs.
    # The workflow's own run id identifies a run within the lineage, which is a
    # different thing, so this has to be handed down rather than guessed.
    if tag:
        env[RUN_TAG_ENV] = tag
    if start:
        env[RUN_START_ENV] = start
    return env


# =============================================================================
# Detached launch -- outliving the session that started the roll (#2015)
# =============================================================================

TASK_NAME = "AZ-SpeedrunRoll"

# No <Triggers> element: the task can never fire on its own, so there is no
# far-future trigger date to pick and nothing to clean up on a calendar.
# It exists solely to be started on demand.
#
# ExecutionTimeLimit PT0S means no limit -- the default would stop a long arc
# partway. AllowHardTerminate false keeps the scheduler from killing the roll,
# which is the entire point of running here. The battery settings matter on a
# laptop: the defaults refuse to start, and stop a running task, on battery.
_TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{description}</Description>
  </RegistrationInfo>
  <Triggers />
  <Principals>
    <Principal id="Author">
      <UserId>{user}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>false</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command}</Command>
      <Arguments>{arguments}</Arguments>
      <WorkingDirectory>{working_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _quote(arg: str) -> str:
    return f'"{arg}"' if " " in arg else arg


def windowless_interpreter(executable: str) -> str:
    """pythonw.exe beside this interpreter, if there is one (#2037).

    A scheduled task running python.exe puts a console on the operator's
    desktop for the whole roll. pythonw has none, and is safe here only because
    --detached-stdout rebinds stdout and stderr to the launcher log before
    anything prints -- under pythonw they would otherwise be absent.

    Falls back to the interpreter as given when no pythonw is present, since a
    visible console is much better than a task that cannot start.
    """
    path = Path(executable)
    if path.name.lower() == "python.exe":
        candidate = path.with_name("pythonw.exe")
        if candidate.is_file():
            return str(candidate)
    return executable


def current_user() -> str:
    domain = os.environ.get("USERDOMAIN", "")
    name = os.environ.get("USERNAME", "")
    return f"{domain}\\{name}" if domain else name


def detached_argv(
    args: argparse.Namespace,
    extra: list[str],
    repo_root: Path,
    az_root: Path,
    log_dir: Path,
) -> list[str]:
    """The argv the scheduled task runs: this same roll, minus the detach ask.

    Every path is made absolute because the detached process inherits whatever
    working directory the scheduler gives it, not the one the operator typed in.
    """
    argv = ["--repo", str(repo_root)]
    for issue in args.issue:
        argv += ["--issue", str(issue)]
    argv += [
        "--log-dir", str(log_dir),
        "--assemblyzero-root", str(az_root),
        "--detached-stdout", str(log_dir / "detached-launcher.log"),
        # #2068: the redraw budget must ride the relaunch or the detached run
        # silently falls back to a single attempt. getattr: callers that build
        # a bare Namespace (tests, embedders) predate the flag.
        "--attempts", str(max(1, getattr(args, "attempts", 1))),
    ]
    return argv + extra


def build_task_xml(
    command: str, arguments: str, working_dir: str, description: str, user: str
) -> str:
    return _TASK_XML.format(
        description=escape(description),
        user=escape(user),
        command=escape(command),
        arguments=escape(arguments),
        working_dir=escape(working_dir),
    )


def launch_detached(
    args: argparse.Namespace,
    extra: list[str],
    repo_root: Path,
    az_root: Path,
    log_dir: Path,
) -> int:
    """Hand the roll to Task Scheduler and return immediately (#2015).

    Deliberately logs to `detach-events.log`, NOT the session log: the absence
    of `session-events.log` is the evidence that distinguishes an uncatchable
    kill from an orderly exit, and a launcher writing to it would destroy that
    signal for every future diagnosis.
    """
    if sys.platform != "win32":
        print(
            "ERROR: --detach is implemented against Windows Task Scheduler and "
            f"this is {sys.platform}. Run without --detach, or add an equivalent "
            "for this platform."
        )
        return 91

    log = EventLog(log_dir / "detach-events.log")
    argv = detached_argv(args, extra, repo_root, az_root, log_dir)
    arguments = " ".join(
        _quote(a) for a in [str(Path(__file__).resolve()), *argv]
    )
    issues = ", ".join(f"#{i}" for i in args.issue)
    xml = build_task_xml(
        command=windowless_interpreter(sys.executable),
        arguments=arguments,
        working_dir=str(az_root),
        description=f"Detached speedrun roll of {issues} in {repo_root.name}",
        user=current_user(),
    )

    xml_path = log_dir / "detached-task.xml"
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    # schtasks requires UTF-16 here; it rejects a UTF-8 definition as malformed.
    xml_path.write_text(xml, encoding="utf-16")

    created = _run(
        ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"]
    )
    if created.returncode != 0:
        detail = (created.stdout + created.stderr).strip()
        log.write(f"DETACH create failed: {detail}")
        return 91

    started = _run(["schtasks", "/Run", "/TN", TASK_NAME])
    if started.returncode != 0:
        detail = (started.stdout + started.stderr).strip()
        log.write(f"DETACH start failed: {detail}")
        return 91

    log.write(f"DETACH launched '{TASK_NAME}' for {issues} (interpreter {sys.executable})")
    print(f"Detached: scheduled task '{TASK_NAME}' is rolling {issues}.")
    print("It is parented by the Task Scheduler service, so ending this session")
    print("(or killing this shell) cannot reach it.\n")
    print(f"  launcher narration  {log_dir / 'detached-launcher.log'}")
    print(f"  run lifecycle       {log_dir / 'session-events.log'}")
    print(f"  per-issue logs      {log_dir}")
    print(f"\n  status   schtasks /Query /TN {TASK_NAME}")
    # NOT `schtasks /End`: that ends the task's own process and leaves the
    # pipeline running, reparented to nothing (#2016).
    print(f"  stop     {Path(__file__).name} --repo {repo_root} --detach-stop")
    return 0


def pid_file(log_dir: Path) -> Path:
    return log_dir / "detached-roll.pid"


def is_live_python(pid: str) -> bool:
    """Is this pid a running python process right now?

    Guards the tree kill against pid reuse: a leftover pid file naming a number
    Windows has since handed to something else must not authorise killing that
    something else, on a machine that runs concurrent lanes.
    """
    if not pid.isdigit():
        return False
    result = _run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"])
    out = result.stdout or ""
    # tasklist reports "INFO: No tasks..." on stdout with exit 0 when nothing
    # matches, so the pid must be looked for rather than trusting the code.
    return f'"{pid}"' in out and "python" in out.lower()


def stop_detached(log_dir: Path) -> int:
    """Stop a detached roll and everything it spawned (#2016).

    `schtasks /End` is not enough on its own: it ends the task's own process and
    leaves the pipeline running, reparented to nothing. Measured 2026-07-31 --
    ending a roll left two orchestrate processes alive, and the tree kill that
    followed had to walk four more levels that /End never touched. Those orphans
    keep calling models and keep writing to the target repo.

    So the pid the roll recorded is killed WITH its tree first, and the task is
    ended afterwards to return it to Ready.
    """
    if sys.platform != "win32":
        print(f"ERROR: --detach-stop is Windows-only; this is {sys.platform}")
        return 91

    log = EventLog(log_dir / "detach-events.log")
    path = pid_file(log_dir)
    killed = False
    if path.exists():
        pid = path.read_text(encoding="utf-8").strip()
        if not is_live_python(pid):
            # Windows recycles pids. A stale file plus an unlucky reuse would
            # tree-kill somebody else's work on a shared machine.
            log.write(f"DETACH-STOP pid {pid} is not a live python; refusing")
            print(f"Recorded pid {pid} is not a running python process.")
            print("Refusing to kill it -- the roll is already gone.")
            path.unlink(missing_ok=True)
        else:
            result = _run(["taskkill", "/PID", pid, "/T", "/F"])
            if result.returncode == 0:
                killed = True
                log.write(f"DETACH-STOP tree-killed pid {pid}")
                print(f"Stopped the roll and its process tree (pid {pid}).")
            else:
                detail = (result.stdout + result.stderr).strip()
                log.write(f"DETACH-STOP pid {pid} not killed: {detail}")
                print(f"No live tree for pid {pid} ({detail}).")
            path.unlink(missing_ok=True)
    else:
        print(f"No recorded pid at {path}.")

    ended = _run(["schtasks", "/End", "/TN", TASK_NAME])
    if ended.returncode != 0 and not killed:
        log.write("DETACH-STOP nothing was running")
        print(f"Task '{TASK_NAME}' was not running.")
    return 0


def _redirect_stdio(path: Path) -> None:
    """Point stdout and stderr at a file, for a run with no console (#2015).

    A scheduled task inherits no console. Without this every print in this tool
    -- including EventLog's, which is how a roll narrates itself -- would go
    nowhere or fail outright. Rebinding before anything else makes the narration
    durable instead of merely absent.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = stream
    sys.stderr = stream


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
        # Not required at parse time: --detach-stop names no issue, it stops
        # whatever is running. Enforced below for the paths that do roll.
        "--issue", type=int, action="append", default=None,
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
    parser.add_argument(
        "--detach", action="store_true",
        help=(
            "Run via Windows Task Scheduler so the roll outlives this session, "
            "then return immediately (#2015)"
        ),
    )
    parser.add_argument(
        "--attempts", type=int, default=1,
        help=(
            "Redraw a failed issue up to N times before stopping (#2068). "
            "Base/gate problems (exit 91) are never retried."
        ),
    )
    parser.add_argument(
        "--detach-stop", action="store_true",
        help="Stop a detached roll and every process it spawned (#2016)",
    )
    # Set by --detach on the relaunch; not something anyone types.
    parser.add_argument("--detached-stdout", default=None, help=argparse.SUPPRESS)
    args, extra = parser.parse_known_args(argv)

    if args.detached_stdout:
        _redirect_stdio(Path(args.detached_stdout))

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

    # Stopping is about processes, not code: it must work even from a stale or
    # dirty tree, so it comes before the staleness gate.
    if args.detach_stop:
        return stop_detached(log_dir)

    if not args.issue:
        print("ERROR: --issue is required (repeatable) unless stopping a roll")
        return 91

    # #2007: refuse before spending anything if the tree running this roll is
    # not the code main says it is. Runs before the detach hand-off too, so a
    # stale tree is caught here rather than inside a task nobody is watching.
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

    # #2073: refuse while the target repo has unanswered questions about what
    # its issue text asks for. Checked ONCE per invocation, here rather than per
    # redraw, and before the detach hand-off -- so nothing is spent, no branch
    # is created, and a batch is refused as a whole rather than partly rolled.
    blocking, gh_error = open_must_resolve_issues(repo_root)
    if gh_error:
        # Offline is not a reason to brick a local roll; the auto-filer (#2072)
        # is the enforcement backstop.
        print(f"WARNING: could not check for unresolved questions ({gh_error}); proceeding.")
    elif blocking:
        print(refusal_message(blocking))
        return 91

    if args.detach:
        return launch_detached(args, extra, repo_root, az_root, log_dir)

    # Created only by a process that actually rolls, never by the launcher --
    # see launch_detached on why that separation is load-bearing.
    session = EventLog(log_dir / "session-events.log")
    install_signal_handlers(session)

    # How --detach-stop finds the tree to kill (#2016). Written by whichever
    # process does the rolling, detached or not.
    log_dir.mkdir(parents=True, exist_ok=True)
    pid_file(log_dir).write_text(str(os.getpid()), encoding="utf-8")

    # #2077: sweep EVERY pipeline worktree, not just the issue about to roll.
    # Healing only the current issue is how ten stranded directories piled up
    # in one day. Nothing here deletes content -- dirty work is committed to a
    # graveyard branch first and unregistered directories are relocated -- so a
    # sweep problem is reported and never costs the roll.
    session.write("SWEEP pipeline worktrees")
    try:
        sweep = sweep_pipeline_worktrees(repo_root, log=lambda m: session.write(m.strip()))
        for problem in sweep.problems:
            session.write(f"SWEEP UNRESOLVED {problem.describe()}")
    except Exception as exc:  # noqa: BLE001 - a sweep must never abort a roll
        session.write(f"SWEEP FAILED (continuing): {exc}")

    code = 0
    try:
        for issue in args.issue:
            # #2068: generation quality varies wildly between draws -- the same
            # issue produced 39/41-passing and 4/75-passing initial iterations
            # on consecutive rolls. A failed draw is self-healing (ensure_base
            # clears its debris), so retrying inside the detached task removes
            # the human relaunch from the loop entirely. A base or gate problem
            # (91) is NOT a draw and is never retried.
            for attempt_no in range(1, max(1, args.attempts) + 1):
                code = roll_issue(repo_root, issue, log_dir, az_root, extra)
                if code == 0 or code == 91:
                    break
                if attempt_no < max(1, args.attempts):
                    print(
                        f"\n#{issue} attempt {attempt_no}/{args.attempts} failed "
                        f"(exit {code}) — self-healing and redrawing."
                    )
                    time.sleep(2)
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
        # A finished roll leaves no pid behind to be stopped, or mistaken for a
        # live one once Windows reuses the number.
        pid_file(log_dir).unlink(missing_ok=True)
        failures = restore_repo(repo_root, args.issue, session)
        if failures:
            print("\nRESTORE INCOMPLETE:")
            for f in failures:
                print(f"  - {f}")
                # Also to the events file: a detached run has no one reading
                # stdout, and this is exactly the state the next roll inherits.
                session.write(f"RESTORE INCOMPLETE: {f}")


if __name__ == "__main__":
    sys.exit(main())

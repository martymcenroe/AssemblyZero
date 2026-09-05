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

Detaching the WORK never detaches the VIEW (standard 0026, #2138): after the
hand-off the launching command stays attached, streaming the roll's narration
into the console the operator launched from until the final line. Ctrl+C stops
the view, never the roll. `--no-follow` restores fire-and-forget; `--follow`
re-attaches to a roll already running.

Exit codes: 0 all issues rolled; 91 a base or gate problem this tool could not
heal; otherwise the failing child's return code.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
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

# #2673: installed before anything can PRINT, same reasoning and position as
# orchestrate.py's #2662 block. This tool echoes the requirements-form check —
# raw issue text — before any child process exists, and launching boostgauge
# #384 it died at its own print() on U+2192 under a cp1252 stdout: the seventh
# kill in the class, in the one process that prints first. The child-env
# PYTHONUTF8 half of #2662 (line ~1499) never covered the launcher's own
# streams.
try:
    from assemblyzero.core.utf8_console import install as _install_utf8_console

    _install_utf8_console()
except ImportError:  # pragma: no cover - tool copied outside the package
    pass

# Imported after the sys.path insert above -- the package root is not on the
# path when this tool is run as a script from tools/ (#2077).
from assemblyzero.core import retry_gate  # noqa: E402  (#2423)
from assemblyzero.core.exit_codes import (  # noqa: E402
    CONFLICT_EXIT_CODE,
    is_requirements_conflict,
)
from assemblyzero.workflows.orchestrator.state import STAGE_ORDER  # noqa: E402
from assemblyzero.core.provider_storm import (  # noqa: E402
    # backoff_minutes went with the redraw loop (#2206) -- it survives in
    # provider_storm for a future deliberate wait, but nothing here waits.
    STORM_EXIT_CODE,
)
from assemblyzero.speedrun.archive import (  # noqa: E402  (#2353)
    archive_run,
    readonly_clearings,
    verify_manifest,
)
from assemblyzero.speedrun.box_health import check_box_health  # noqa: E402
from assemblyzero.speedrun.emergency_stop import (  # noqa: E402  (#2422)
    KILL_EXIT_CODE,
    KILLED_MARKER,
    KillWatch,
    banner_lines,
    clear_kill_files,
    find_kill_file,
    killed_verdict_lines,
    tree_kill,
)
from assemblyzero.speedrun.roll_blockers import (  # noqa: E402  (#2436)
    blocker_refusal_message,
    blocker_report_lines,
    blocker_trace_line,
    scan_roll_blockers,
)
from assemblyzero.speedrun.successes import (  # noqa: E402  (#2191)
    completed_on,
    describe,
    record_success,
    redraw_phrase,
)
from assemblyzero.workflows.requirements.contract_fidelity import (  # noqa: E402  (#2646)
    check_contract_fidelity_at_preflight,
)
from assemblyzero.workflows.requirements.form_gate import (  # noqa: E402  (#2227)
    check_form_at_preflight,
)
from assemblyzero.workflows.requirements.precheck import fetch_issue  # noqa: E402
from assemblyzero.speedrun.must_resolve import (  # noqa: E402
    RUN_START_ENV,
    RUN_TAG_ENV,
    merge_questions,
    open_must_resolve_issues,
    read_filed,
    refusal_message,
)
from assemblyzero.speedrun.healing import record_heal  # noqa: E402
from assemblyzero.core import settlement as settlement_mod  # noqa: E402  (#2609)
from assemblyzero.workflows.requirements.audit import (  # noqa: E402  (#2609)
    load_settlement,
    settled_stages,
)
from assemblyzero.speedrun.leavings import (  # noqa: E402
    classify_dirt,
    is_machinery_owned,
    is_pipeline_input,
    preserve_and_clear,
    untracked_files,
)
# #2571: the ref-restore machinery moved to a shared module so the LOADER
# can rebuild inputs too, not just this resume planner. Aliased to the old
# private names so every call site reads unchanged.
from assemblyzero.speedrun.restore import (  # noqa: E402
    graveyard_issue_lld_refs as _graveyard_issue_lld_refs,
    graveyard_leavings_refs as _graveyard_leavings_refs,
    restore_artifact as _restore_artifact,
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


def find_checkpoint(repo_root: Path, issue: int) -> str | None:
    """The newest `[CP:*]` commit for this issue, or None (#2409).

    A checkpoint is the workflow's own statement that a stage completed and its
    work is worth keeping: `[CP:post-impl] issue #1: workflow checkpoint`. It is
    an ordinary commit on the issue's pipeline branches, so it survives the
    worktree being removed but NOT the branches being deleted, which is exactly
    how `d1e9269` became unreferenced on 2026-08-15.

    This is the fact the resume-versus-residue decision turns on. An open LLD
    PR, its branch and an untracked LLD are all normal mid-issue state and say
    nothing either way; a checkpoint says work exists that a reset would
    destroy. Cosmetics do not get a vote.

    Every ref that could carry one is searched, including the worktree's own
    branch, because the checkpointing commit lands wherever the stage ran.
    """
    refs = [
        f"{issue}-impl", f"origin/{issue}-impl",
        f"{issue}-lld", f"origin/{issue}-lld",
        f"{issue}-spec", f"origin/{issue}-spec",
        f"{issue}-fix", f"origin/{issue}-fix",
    ]
    for ref in refs:
        found = _run(
            ["git", "log", "-1", "--format=%h", "--grep=^\\[CP:", ref],
            cwd=repo_root,
        )
        if found.returncode == 0 and found.stdout.strip():
            return found.stdout.strip()
    return None


def refuse_with_exits(
    repo_root: Path, issue: int, debris: list[str], log: EventLog,
    checkpoint: str | None,
) -> None:
    """Name the findings and both exits, then let the caller abort (#2409).

    A plain launch that would otherwise reset says what it found and what the
    operator can do about it. The destructive path is chosen, never inferred:
    the reset closes a PR, deletes a remote branch and removes a worktree, and
    on 2026-08-15 it did all three to an in-flight issue as a silent side
    effect of an ordinary launch command.
    """
    log.write(
        f"GATE {len(debris)} finding(s) for #{issue} -- REFUSING to reset"
    )
    for d in debris:
        log.write(f"  {d}")
    if checkpoint:
        log.write(
            f"  a checkpoint exists ({checkpoint}); a reset would destroy it"
        )
    log.write("  exit 1: repair the findings above, then relaunch to resume")
    log.write(
        "  exit 2: relaunch with --fresh to reset this issue and redraw "
        "(archives, never deletes)"
    )


def settlement_inputs(repo_root: Path, issue: int, stage: str) -> list:
    """Current inputs for ``stage``, as the launcher can see them (#2609).

    The launcher hashes the same things the stage does, so the two agree on
    whether an artifact is settled. A `gh` read that fails yields a None body,
    which unsettles -- the launcher then behaves exactly as it did before.
    """
    try:
        _title, body = fetch_issue(repo_root, issue)
    except Exception:
        # fail-open: only in shape -- a None body unsettles, which restores
        # the pre-#2609 path. A settlement probe must not be able to stop a
        # launch it was only advising.
        body = None
    upstream_stage = settlement_mod.UPSTREAM_OF.get(stage)
    upstream = None
    if upstream_stage:
        record = load_settlement(issue, upstream_stage, repo_root)
        if isinstance(record, dict):
            upstream = record.get("artifact_path") or None
    return settlement_mod.collect_inputs(
        repo_root, issue_body=body, upstream_artifact=upstream
    )


def settled_artifact_names(repo_root: Path, issue: int, log: EventLog) -> set[str]:
    """Basenames of this issue's SETTLED artifacts, for `--fresh` to preserve.

    #2609: `--fresh` resets the RUN. A settled artifact embodies a ruling the
    run being reset did not make, so it survives, and each decision is stated
    -- preserved with its evidence, or archived with the mismatch that
    unsettled it. Silence about either half is what made a reset feel
    arbitrary.
    """
    names: set[str] = set()
    for stage in settled_stages(issue, repo_root):
        record = load_settlement(issue, stage, repo_root)
        if not isinstance(record, dict):
            continue
        artifact = record.get("artifact_path") or ""
        if not artifact:
            continue
        mismatches = settlement_mod.verify(
            record, settlement_inputs(repo_root, issue, stage)
        )
        if mismatches:
            log.write(f"FRESH archiving unsettled {stage}: {Path(artifact).name}")
            for reason in mismatches:
                log.write(f"  {reason}")
            continue
        if not settlement_mod.artifact_matches(record, artifact):
            log.write(
                f"FRESH archiving {stage}: {Path(artifact).name} is not the "
                f"file that settled (edited since)"
            )
            continue
        names.add(Path(artifact).name)
        log.write(
            f"FRESH preserving settled {stage}: {Path(artifact).name} "
            f"(settled {record.get('settled_at', '?')})"
        )
    return names


def partition_by_settledness(
    repo_root: Path, issue: int, committed: list[str]
) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Split committed-artifact findings into (settled, [(finding, why-not)]).

    #2609: the committed-artifact scan reads `docs/lld` only, so every finding
    it can produce is an LLD or a spec -- never implementation code. When those
    artifacts are settled, a base carrying them is the DESIRED state and not
    contamination: it is the arc holding the ruling the pipeline just landed
    there. Reading it as staleness is what made landing an approved artifact
    the trigger for redrawing it.

    #1959's founding case is untouched. That case was a base whose
    implementations were already merged and green; this scan never saw those,
    and does not see them now.
    """
    settled: list[str] = []
    unsettled: list[tuple[str, list[str]]] = []
    for finding in committed:
        path = finding.split(":", 1)[1].strip() if ":" in finding else finding
        stage = settlement_mod.stage_of_artifact_path(path, issue)
        if stage is None:
            unsettled.append((finding, ["not a recognised settleable artifact"]))
            continue
        record = load_settlement(issue, stage, repo_root)
        if record is None:
            unsettled.append((finding, ["no settlement record"]))
            continue
        mismatches = settlement_mod.verify(
            record, settlement_inputs(repo_root, issue, stage)
        )
        if mismatches:
            unsettled.append((finding, mismatches))
        else:
            settled.append(finding)
    return settled, unsettled


def ensure_base(
    repo_root: Path, issue: int, log: EventLog, fresh: bool = False
) -> str | None:
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
        # #2609: settledness decides this, not branch contents. A committed
        # artifact whose inputs still hash as they did when it passed its gate
        # is the ruling this arc exists to carry -- replacing the base would
        # redraw it, which is how landing an approved LLD became the thing
        # that destroyed it.
        settled, unsettled = partition_by_settledness(repo_root, issue, committed)
        for finding in settled:
            log.write(f"BASE settled, preserved: {finding}")
        for finding, why in unsettled:
            log.write(f"BASE unsettled: {finding}")
            for reason in why:
                log.write(f"  {reason}")
        if settled and not unsettled:
            log.write(
                f"BASE '{base}' carries #{issue}'s SETTLED work "
                f"({len(settled)} artifact(s)) -- keeping the base; the roll "
                f"resumes from the settled frontier"
            )
            record_heal(
                repo_root, "base-settled", base, "healed",
                detail=f"{len(settled)} settled artifact(s) preserved on the base",
            )
            debris = [d for d in debris if d not in settled]
            if not debris:
                return base
            committed = []
        elif settled:
            # Mixed: something on this base is settled and something is not.
            # The base is replaced, which redraws the settled ones too. That is
            # the conservative direction and it is chosen, not overlooked -- a
            # partial reprieve would leave an unsettled artifact committed on a
            # base the roll then treats as verified, which is #1959's shape.
            # Both lists are logged above, so the cost is visible rather than
            # silent.
            log.write(
                f"BASE mixed settledness for #{issue}: {len(settled)} settled, "
                f"{len(unsettled)} not -- replacing the base redraws both"
            )

    if committed:
        # The base already contains this issue's merged work. No amount of
        # debris cleanup fixes that -- it needs a base that predates it.
        log.write(
            f"BASE '{base}' already contains #{issue}'s work "
            f"({len(committed)} artifact(s)) -- establishing a fresh attempt"
        )
        fresh = establish_new_attempt(repo_root, log)
        record_heal(
            repo_root, "base-replace", base,
            "healed" if fresh else "failed",
            detail=f"#{issue}'s work already on the base",
        )
        return fresh

    # #2409: recoverable debris is NOT authority to reset. On 2026-08-15 this
    # branch read an in-flight issue's own products -- the open LLD PR the
    # requirements workflow keeps open by design, that PR's branch, and an
    # untracked LLD the halt path left behind -- as contamination, and its
    # remedy destroyed a passed spec stage, impl iteration 0, and the resume
    # seeds. The same command had resumed the same issue two and a half hours
    # earlier, so the gate was inconsistent on nearly identical state.
    #
    # The deciding fact is the checkpoint, not the findings. A checkpoint means
    # work exists that a reset would destroy, so heal around it and let the
    # roll resume. Without one, a plain launch still refuses rather than
    # inferring the destructive path: fleet doctrine is that destructive
    # operations default to dry-run and mutate only under an explicit flag, and
    # a reset that closes a PR and deletes a remote branch as a side effect of
    # `speedrun_roll --issue N` is the opposite of that.
    checkpoint = find_checkpoint(repo_root, issue)
    if checkpoint and not fresh:
        log.write(
            f"GATE {len(debris)} finding(s) for #{issue}, but checkpoint "
            f"{checkpoint} exists -- preserving, no reset"
        )
        for d in debris:
            log.write(f"  {d}")
        log.write(
            f"BASE '{base}' accepted for #{issue} with its work preserved "
            "(--fresh to reset and redraw)"
        )
        record_heal(
            repo_root, "reset-declined", f"#{issue}", "healed",
            detail=f"checkpoint {checkpoint} present; {len(debris)} finding(s) left in place",
        )
        return base

    if not fresh:
        refuse_with_exits(repo_root, issue, debris, log, checkpoint)
        record_heal(
            repo_root, "reset-refused", f"#{issue}", "refused",
            detail=f"{len(debris)} finding(s); --fresh not given",
        )
        return None

    # --fresh: the operator chose this explicitly. The reset preserves rather
    # than deletes (see speedrun_reset.archive_lineage_dirs) and stamps a
    # rescue ref over any checkpoint before the branches go.
    log.write(f"GATE {len(debris)} finding(s) for #{issue} -- --fresh, resetting")
    for d in debris:
        log.write(f"  {d}")
    if checkpoint:
        log.write(f"  checkpoint {checkpoint} will be pinned before the reset")
    try:
        repo_slug = reset._gh_repo(repo_root)
    except RuntimeError as err:
        log.write(f"RESET could not determine owner/repo: {err}")
        return None
    preserve = settled_artifact_names(repo_root, issue, log)
    reset.reset_one_issue(repo_root, repo_slug, issue, preserve)

    findings = gate.check_repo(repo_root, [issue], base)
    debris = [f for f in findings if not f.startswith("ERROR:")]
    if debris:
        log.write(f"GATE still dirty after reset ({len(debris)}) -- {len(debris)} left")
        for d in debris:
            log.write(f"  {d}")
        record_heal(
            repo_root, "reset", f"#{issue}", "partial",
            detail=f"{len(debris)} finding(s) survived the reset",
        )
        return replace_or_refuse(repo_root, base, issue, debris, log)

    record_heal(repo_root, "reset", f"#{issue}", "healed",
                detail="base clean after self-heal")
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
# Resume -- reuse passed stages after a non-conflict failure (#2193)
# =============================================================================

# Stages a relaunch may resume from. lld failing means nothing expensive
# passed (a redraw IS the restart).
#
# #2194 added `pr` on the evidence it asked to wait for: "the first observed
# relaunch-after-pr-failure that redraws an expensive impl is the evidence to
# build from". run-issue7-231606 is that observation, and it is the only one in
# the corpus:
#
#     lld     passed    281.9s
#     spec    passed    699.0s
#     impl    passed    363.6s
#     pr      failed      0.7s   ! [rejected] issue-7 -> issue-7 (non-fast-forward)
#
# 1344.5 seconds of paid work discarded to retry a git push that failed in
# under a second, and the failure was a branch-state rejection rather than
# anything about the content.
#
# `cleanup` is NOT added. The corpus holds zero cleanup failures across 21
# passes, so there is no observed shape to design its integrity checks against
# -- which is the same standard that kept `pr` out until today. Adding it now
# would be guessing at what survives, and a resume into missing state costs
# more than the redraw it saves.
# #2518: `visual` is resumable by construction -- its entire state (rounds,
# overrides, the operator's answer) lives on disk in the target repo's
# data/visual-gate bundle, and the gate re-enters at the exact round it left:
# an unanswered round re-serves, an answered one dispatches without re-asking.
RESUMABLE_STAGES = ("visual", "spec", "impl", "pr")

#: Stages that auto-skip when not applicable and so may legitimately have NO
#: entry in a state file -- including every state file written before they
#: joined STAGE_ORDER. `_halted_stage` treats their absence as history rather
#: than as a gap that declines a killed-run resume (#2518).
_OPTIONAL_STAGES = frozenset({"visual"})

#: Stages whose inputs include the finalized spec. `pr` reads the impl stage's
#: worktree, which only exists because spec produced what impl built from.
_STAGES_NEEDING_SPEC = ("impl", "pr")


def _orchestrator_state_path(az_root: Path, issue: int) -> Path:
    """Where orchestrate.py persists per-issue state (resume.py STATE_DIR,
    which is relative to the child's cwd -- always az_root, see roll_issue)."""
    return az_root / ".assemblyzero" / "orchestrator" / "state" / f"{issue}.json"


def _open_lld_pr_exists(repo_root: Path, issue: int) -> bool:
    """The lld PR still being open proves the reset has not destroyed the
    draft a resume would reuse -- reset_one_issue closes it first thing, so
    closed means the artifacts are already gone and only a redraw is left."""
    result = _run([
        "gh", "pr", "list", "--head", f"{issue}-lld",
        "--state", "open", "--json", "number",
    ], cwd=repo_root)
    if result.returncode != 0:
        return False
    try:
        return bool(json.loads(result.stdout or "[]"))
    except json.JSONDecodeError:
        return False


#: Where a resumable stage's artifact lives on the issue's lld branch, for the
#: case where the orchestrator recorded no path at all (#2414). The branch is
#: issue-scoped, so anything matching under it belongs to this issue.
_STAGE_ARTIFACT_GLOBS = {
    "lld": ("docs/lld/active/LLD-*.md",),
    "spec": ("docs/lld/drafts/spec-*.md", "docs/lld/active/spec-*.md"),
}


def _find_on_lld_branch(repo_root: Path, issue: int, pattern: str) -> str:
    """The repo-relative path of a file matching `pattern` on the lld branch.

    The last match in sort order wins, so a repo carrying spec-0001 and
    spec-0002 resolves to the newer one rather than to whichever git listed
    first.

    #2516: the grafted copies of the lld branch are consulted after the live
    refs. A HALT's own RESTORE renames `{issue}-lld` to
    `graveyard/{issue}-lld-<stamp>` -- the machinery archived the branch the
    next resume needs, so the archive is part of where the resume looks.
    """
    refs = [f"{issue}-lld", f"origin/{issue}-lld"]
    refs += _graveyard_issue_lld_refs(repo_root, issue)
    for ref in refs:
        result = _run(["git", "ls-tree", "-r", "--name-only", ref], cwd=repo_root)
        if result.returncode != 0:
            continue
        matches = sorted(
            line.strip() for line in (result.stdout or "").splitlines()
            if fnmatch.fnmatch(line.strip(), pattern)
        )
        if matches:
            return matches[-1]
    return ""


def _resolve_stage_artifact(
    repo_root: Path, issue: int, data: dict, stage: str
) -> str:
    """Where `stage`'s artifact actually is -- an artifact lookup, not a path
    string lookup (#2414).

    `resume_plan` used to read one field and abandon the resume when it was the
    empty string, so a resume was declined on a MISSING PATH rather than on a
    missing artifact. The artifact may well exist on disk or on the branch;
    nothing checked. The distinction is the whole issue.

    Three places are consulted, cheapest first:

      1. the top-level `<stage>_path`, which `finalize_spec` populates when the
         stage passes;
      2. the stage result's own `artifact_path`, which is recorded per stage
         and survives cases where the top-level field was never set;
      3. the issue's lld branch, listed and matched by glob -- the same source
         `_restore_artifact` already restores from.

    Returns "" only when the artifact cannot be found anywhere, which is the
    case that SHOULD decline: resuming into a missing input is worse than
    redrawing.
    """
    recorded = (data.get(f"{stage}_path", "") or "").strip()
    if recorded:
        return recorded

    results = data.get("stage_results", {}) or {}
    from_result = ((results.get(stage) or {}).get("artifact_path", "") or "").strip()
    if from_result:
        return from_result

    for pattern in _STAGE_ARTIFACT_GLOBS.get(stage, ()):
        found = _find_on_lld_branch(repo_root, issue, pattern)
        if found:
            return str(repo_root / found)
    return ""


# Binding-input paths: a commit touching any of them invalidates a draft
# derived from them. Design docs and ADRs are what the drafter and the reviewer
# read as law; issue text is checked separately against the GitHub API.
#
# #2244 added CLAUDE.md by the tuple's own definition -- it is law the drafter
# reads, from the attempt branch's worktree, as project context. Leaving it out
# reproduced for it the exact invisibility #2205 closed for design docs: a
# correction landed on the default branch never reached a running arc. Live
# case, boostgauge #286: CLAUDE.md listed planned files as existing, and four
# runs each paid a revision iteration for drafts that marked the phantom files
# as Modify. Without this the fix would land on main and every future draw on
# that arc would keep paying the iteration the fix was meant to end.
#: #2609: one definition, imported. `draft_is_stale` and the settlement check
#: answer the same question about the same documents, and two literals would
#: let them disagree -- at which point one of them is silently wrong.
BINDING_DOC_PATHS = settlement_mod.BINDING_DOC_PATHS


def sync_binding_docs_to_arc(
    repo_root: Path, base: str, log: EventLog
) -> list[str]:
    """Carry the default branch's binding-doc rulings onto the arc (#2205).

    The roll's worktree stands on the attempt branch, so the design docs and
    ADRs the drafter and reviewer read as law are the ARC's copies. Issue
    text arrives live from GitHub; docs do not. An arc cut before a ruling
    never sees it, and nothing in the machinery noticed.

    The cost was not theoretical. On 2026-08-10 an arc carried a two-day-old
    aesthetic doc while five rulings sat on the default branch; issue #1's
    spec stage failed twice on an objection the operator had already
    answered, invisibly. Worse, doc rulings had been reaching arcs only when
    a pipeline PR happened to smuggle a snapshot -- nondeterministic and
    version-skewed.

    Preserve-then-proceed, never force: an ordinary merge, a conflict refuses
    loudly rather than guessing, nothing discarded. Returns a list of
    problems; empty means the arc now carries current law.
    """
    default = attempt.default_branch(repo_root)
    if not default:
        return ["cannot resolve the default branch to sync binding docs from"]
    if base == default:
        return []

    _run(["git", "fetch", "--quiet", "origin"], cwd=repo_root)
    pending = _run(
        ["git", "log", "--oneline", f"origin/{base}..origin/{default}", "--",
         *BINDING_DOC_PATHS],
        cwd=repo_root,
    )
    if pending.returncode != 0:
        return [
            f"cannot compare binding docs between '{base}' and '{default}': "
            f"{(pending.stderr or '').strip()}"
        ]
    commits = [ln for ln in pending.stdout.splitlines() if ln.strip()]
    if not commits:
        return []

    log.write(
        f"SYNC {len(commits)} binding-doc commit(s) on '{default}' not yet on "
        f"'{base}' -- carrying them onto the arc before the roll reads them"
    )
    for line in commits[:5]:
        log.write(f"  {line}")

    # A worktree under data/speedrun/** -- evidence space, structurally exempt
    # from dirt classification (standard 0027), and never a ~/Projects sibling
    # (the stranded-worktree failure this campaign already paid for).
    sync_tree = repo_root / "data" / "speedrun" / ".arc-sync"
    problems: list[str] = []
    try:
        if sync_tree.exists():
            _run(["git", "worktree", "remove", str(sync_tree)], cwd=repo_root)
        add = _run(
            ["git", "worktree", "add", str(sync_tree), base], cwd=repo_root
        )
        if add.returncode != 0:
            return [
                f"could not check out '{base}' to sync binding docs: "
                f"{(add.stderr or '').strip()}"
            ]
        # Absorb the arc's own remote movement FIRST (#2473). The local arc
        # ref goes stale the moment a pipeline PR moves origin/<arc>, and
        # nothing in the clone updates it. Building the doc merge on the
        # stale ref made the push below non-fast-forward: the launch died at
        # SYNC BLOCKED and left a diverged local branch stranded. Same
        # preserve-then-proceed rule as the doc merge: a no-op when current,
        # a fast-forward when merely behind, an ordinary merge when a prior
        # stranding left local-only commits -- nothing discarded, a conflict
        # refuses loudly.
        local_sha = _run(["git", "rev-parse", base], cwd=repo_root).stdout.strip()
        remote_sha = _run(
            ["git", "rev-parse", f"origin/{base}"], cwd=repo_root
        ).stdout.strip()
        if local_sha != remote_sha:
            log.write(
                f"SYNC arc '{base}' moved on origin (local {local_sha[:8]}, "
                f"origin {remote_sha[:8]}) -- absorbing before the doc merge"
            )
            absorb = _run(
                ["git", "merge", f"origin/{base}", "-m",
                 f"Merge origin/{base} into {base} - absorb the arc's remote "
                 f"movement before carrying rulings (#2473)"],
                cwd=sync_tree,
            )
            if absorb.returncode != 0:
                conflicted = _run(
                    ["git", "diff", "--name-only", "--diff-filter=U"],
                    cwd=sync_tree,
                ).stdout.split()
                _run(["git", "merge", "--abort"], cwd=sync_tree)
                return [
                    f"the arc '{base}' moved on origin and its movement "
                    f"conflicts with the local copy in "
                    f"{', '.join(conflicted) or 'unknown file(s)'} -- "
                    "resolve by hand, then roll. Nothing was changed."
                ]
        merge = _run(
            ["git", "merge", f"origin/{default}", "-m",
             f"Merge {default} into {base} - carry binding-doc rulings onto "
             f"the arc before rolling (#2205)"],
            cwd=sync_tree,
        )
        if merge.returncode != 0:
            conflicted = _run(
                ["git", "diff", "--name-only", "--diff-filter=U"], cwd=sync_tree
            ).stdout.split()
            _run(["git", "merge", "--abort"], cwd=sync_tree)
            problems.append(
                f"binding docs on '{default}' conflict with '{base}' in "
                f"{', '.join(conflicted) or 'unknown file(s)'} -- resolve by "
                "hand, then roll. Nothing was changed."
            )
        else:
            push = _run(["git", "push", "origin", base], cwd=sync_tree)
            if push.returncode != 0:
                problems.append(
                    f"synced '{base}' locally but could not push it: "
                    f"{(push.stderr or '').strip()}. The local '{base}' now "
                    f"carries the sync merge and origin does not -- the next "
                    f"launch absorbs origin/{base} and retries; no by-hand "
                    f"repair is needed unless the refusal repeats."
                )
            else:
                log.write(
                    f"SYNC verified: '{base}' now carries the binding docs "
                    f"from '{default}'"
                )
    finally:
        _run(["git", "worktree", "remove", "--", str(sync_tree)], cwd=repo_root)
        _run(["git", "worktree", "prune"], cwd=repo_root)
    return problems


def draft_is_stale(repo_root: Path, issue: int, log: EventLog) -> bool:
    """True when a binding input's CONTENT changed since the draft (#2206, #2615).

    A resumed spec is built on a persisted LLD. If the law that LLD was derived
    from has since changed, resuming spends the stage on a draft that is
    already wrong -- and worse, produces a failure that reads as evidence
    against whatever the ruling just fixed. #2206's live case: an LLD drafted
    at 01:27Z was invalidated by design-doc rulings merged at 05:13Z and 06:18Z
    while the issue's own text had last changed BEFORE the draft, so an
    issue-only check would have resumed onto it.

    ## Why this no longer reads timestamps (#2615)

    The old form compared the issue's `updatedAt` against the draft time.
    **GitHub bumps `updatedAt` when a comment is posted**, so the probe fired
    on events that changed nothing about the derivation -- measured across
    three issues with a control, on #2615. The campaign's own standing method,
    *post the sharpened diagnosis on the issue before fixing*, therefore
    invalidated every persisted draft it touched, at full drafter cost, against
    text byte-identical to what the draft already had.

    The question is "did the derivation's INPUTS change", and the inputs are
    the issue BODY and the binding docs. A comment, a label and a reaction
    change none of them.

    ## One fingerprint, not two

    This asks `settlement.verify` the same question `should_skip_stage` asks,
    over inputs built by the same `collect_inputs`. Two parsers of one question
    is the #1698 failure class, and it is exactly how this check and settlement
    would have drifted -- `test_staleness_is_content.py::TestOneFingerprint`
    pins that they cannot.

    It also changes WHAT is measured, deliberately. The old binding-doc probe
    read `git log` over the base BRANCH, which answers "has a doc landed on the
    arc since" -- a proxy that is wrong in both directions (a doc merged but
    not pulled; a working-tree edit never committed). Settlement hashes the
    working tree the stage actually read, so both sides of the comparison are
    now the same thing.

    Unknowable answers stay stale: with no settlement record there is nothing
    to compare content against, and the caller draws fresh, which is safe. A
    run whose lld stage passed has a record by construction (#2616 settles on
    the passed branch), so this costs a one-time redraw only for state
    persisted before settlement existed.
    """
    record = load_settlement(issue, "lld", repo_root)
    if record is None:
        log.write(
            f"RESUME abandoned for #{issue}: no settlement record for the lld "
            "stage, so the draft's inputs cannot be compared by content -- "
            "drawing fresh"
        )
        return True

    mismatches = settlement_mod.verify(
        record, settlement_inputs(repo_root, issue, "lld")
    )
    if mismatches:
        log.write(
            f"RESUME abandoned for #{issue}: a binding input changed since the "
            "draft was made -- drawing fresh against the current law"
        )
        for reason in mismatches:
            log.write(f"  {reason}")
        return True
    return False


def _halted_stage(data: dict, results: dict) -> str | None:
    """The stage a killed run was in the middle of when it was stopped (#2422).

    An ordered stop never gets to record a result. `stage_results` holds the
    stages that FINISHED; `current_stage` names the one that was in flight; and
    nothing is marked failed, because nothing failed. `resume_plan` chose the
    stage to resume by scanning for a failed status, so a killed run matched
    nothing, resumed from nowhere, and redrew every passed stage -- which is
    the opposite of what an ordered stop is supposed to guarantee.

    Measured on boostgauge #1 after the 2026-08-15 kill: `spec` passed, `impl`
    had no entry at all, and `current_stage` read `impl`.

    Two guards keep this from inventing a resume over a gap: a run that
    recorded `completed_at` is finished rather than halted, and every stage
    before the in-flight one must have passed or been skipped.
    """
    if data.get("completed_at"):
        return None
    current = data.get("current_stage", "")
    if current not in STAGE_ORDER:
        return None
    if results.get(current, {}).get("status") in ("passed", "skipped"):
        return None  # it finished; nothing was in flight
    for earlier in STAGE_ORDER[: STAGE_ORDER.index(current)]:
        status = results.get(earlier, {}).get("status")
        if status in ("passed", "skipped"):
            continue
        # #2518: an OPTIONAL stage legitimately owes no entry -- a state file
        # written before the stage joined STAGE_ORDER has none, and that
        # absence is history, not a gap in the run. A recorded failure on it
        # is still a real stop and still declines the resume.
        if earlier in _OPTIONAL_STAGES and status is None:
            continue
        return None
    return current


def resume_plan(
    az_root: Path, repo_root: Path, issue: int, log: EventLog
) -> str | None:
    """The stage to resume #issue from, or None for a fresh draw.

    Resume is offered only when every one of these holds -- anything less
    falls back to the fresh redraw, which is always safe:

      - orchestrate persisted state for this issue, for THIS repo and THIS
        attempt branch (state files are keyed by issue number alone, so a
        same-numbered issue in another campaign repo must not match);
      - the lld stage passed and a later resumable stage failed;
      - the failure was NOT a requirements conflict. A conflict means an
        operator ruling edited the issue text, and the persisted draft embeds
        the pre-ruling text -- resuming spec would re-review the stale LLD
        and re-block on the very conflict the operator just retired
        (boostgauge #253 is the documented case);
      - the lld PR is still open and the passed artifacts exist on disk or
        are restorable from the lld branch.
    """
    state_path = _orchestrator_state_path(az_root, issue)
    if not state_path.is_file():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    try:
        if Path(data.get("target_repo", "")).resolve() != repo_root.resolve():
            return None
    except OSError:
        return None

    base = resolve_attempt_branch(repo_root)
    if not base or data.get("base_branch") != base:
        return None

    results = data.get("stage_results", {}) or {}
    if results.get("lld", {}).get("status") not in ("passed", "skipped"):
        return None

    failed = next(
        (s for s in STAGE_ORDER
         if results.get(s, {}).get("status") in ("failed", "blocked")),
        None,
    )
    # #2422: no failed stage does not mean nothing to resume. A run stopped on
    # the operator's order was in the MIDDLE of a stage, which records no
    # result at all -- so the stage in flight is the stage to resume from.
    halted = False
    if failed is None:
        failed = _halted_stage(data, results)
        halted = failed is not None
    if failed not in RESUMABLE_STAGES:
        return None

    if is_requirements_conflict(results.get(failed, {}).get("error_message", "")):
        return None

    if not _open_lld_pr_exists(repo_root, issue):
        return None

    # #2206: the draft must still be derived from current law. #2615: by
    # CONTENT -- the settled fingerprint of the issue body and the binding
    # docs -- never by timestamps, which a comment moves without changing a
    # single input.
    if draft_is_stale(repo_root, issue, log):
        return None

    # #2414: an artifact lookup, not a path-string lookup. The old form read
    # one field and abandoned on the empty string, so a resume was declined
    # because no PATH was recorded rather than because no ARTIFACT existed --
    # and the artifact is usually sitting on the lld branch, restorable. The
    # decline still happens, but now only when the file genuinely cannot be
    # found: resuming into a missing input is worse than redrawing.
    needed = [("lld", _resolve_stage_artifact(repo_root, issue, data, "lld"))]
    if failed in _STAGES_NEEDING_SPEC:
        needed.append(("spec", _resolve_stage_artifact(repo_root, issue, data, "spec")))

    # #2194: the pr stage reads `state["worktree_path"]` and derives its head
    # branch from whatever is checked out there -- it fails immediately with
    # "No worktree path available for PR creation" without one. That worktree
    # is the "unverified surface" #2194 deferred on; it is verified now, both
    # by run-issue7-231606 and by boostgauge #1's worktree surviving an
    # operator kill intact. Checked rather than assumed, because a resume into
    # a missing worktree costs more than the redraw it saves.
    if failed == "pr":
        worktree = (data.get("worktree_path", "") or "").strip()
        if not worktree or not Path(worktree).is_dir():
            log.write(
                f"RESUME abandoned for #{issue}: the pr stage needs the impl "
                f"worktree and it is gone ({worktree or '<unset>'})"
            )
            return None
    for stage, artifact in needed:
        if not artifact:
            log.write(
                f"RESUME abandoned for #{issue}: no {stage} artifact recorded, "
                f"and none found on the {issue}-lld branch, its "
                f"graveyard/{issue}-lld-* grafts, or the leavings refs"
            )
            return None
        if not _restore_artifact(repo_root, issue, artifact):
            log.write(
                f"RESUME abandoned for #{issue}: {stage} artifact missing and "
                f"not restorable from the {issue}-lld branch, its "
                f"graveyard/{issue}-lld-* grafts, or the leavings refs: "
                f"{artifact}"
            )
            return None

    log.write(
        f"RESUME planned for #{issue}: from '{failed}' "
        f"({'stopped mid-stage' if halted else 'failed stage'}, "
        f"state {state_path.name})"
    )
    return failed


def _preserved_inventory(repo_root: Path, issue: int) -> list[str]:
    """What the machinery preserved for #issue, and where, for a refusal to
    name (#2516). Empty means genuinely nothing was found -- which is itself
    the honest report.
    """
    lines: list[str] = []
    prefix = attempt_prefix(repo_root)
    arc_refs = _run(
        [
            "git", "for-each-ref", "--format=%(refname:short)",
            f"refs/heads/graveyard/{prefix}-*",
            f"refs/remotes/origin/graveyard/{prefix}-*",
        ],
        cwd=repo_root,
    )
    for ref in (arc_refs.stdout or "").splitlines()[:3]:
        if ref.strip():
            lines.append(f"arc branch grafted as '{ref.strip()}'")
    for ref in _graveyard_issue_lld_refs(repo_root, issue)[:3]:
        lines.append(f"lld branch grafted as '{ref}' (content restorable from it)")
    for ref in _graveyard_leavings_refs(repo_root)[:2]:
        lines.append(f"cleared files preserved on '{ref}'")
    lineage = repo_root / "docs" / "lineage" / "active" / f"{issue}-implspec"
    if lineage.is_dir():
        runs = sum(1 for p in lineage.iterdir() if p.is_dir())
        lines.append(
            f"spec lineage intact at '{lineage}' ({runs} run director"
            f"{'y' if runs == 1 else 'ies'})"
        )
    return lines


def ensure_base_for_resume(
    repo_root: Path, issue: int, log: EventLog
) -> str | None:
    """The resume counterpart of ensure_base: verify, never reset.

    The debris ensure_base would clear IS the work a resume reuses -- the lld
    branch, its open PR, the lineage. Only the structural checks run here; any
    problem abandons the resume rather than healing, and the caller falls back
    to the fresh path where the ordinary janitor applies.
    """
    base = resolve_attempt_branch(repo_root)
    if not base:
        # #2516: the machinery's own RESTORE archives the surfaces a resume
        # needs -- branches grafted under graveyard names, files preserved on
        # leavings refs, lineage left in place. A bare "no attempt branch
        # exists" after the machinery itself archived that branch reads as
        # loss when everything is preserved and one rename away. Refuse WITH
        # the inventory, so the operator's next move needs no excavation.
        log.write(
            "RESUME abandoned: no attempt branch exists on origin. "
            "Preserved state, if any, is listed below; a fresh draw follows."
        )
        for line in _preserved_inventory(repo_root, issue):
            log.write(f"RESUME preserved: {line}")
        return None
    problems = base_is_structurally_sound(repo_root, base)
    if problems:
        log.write(
            f"RESUME abandoned: base '{base}' unusable: {'; '.join(problems)}"
        )
        return None
    log.write(
        f"BASE '{base}' accepted for resume of #{issue} "
        "(this issue's work preserved)"
    )
    return base


# =============================================================================
# The roll
# =============================================================================


def _watch_visual_gate_urls(
    repo_root: Path, stop: "threading.Event", log: "EventLog | None" = None,
    announce=print, poll_seconds: float = 5.0,
) -> None:
    """Announce the visual gate's review URL on the LAUNCHER's surfaces (#2520).

    The gate serves inside the orchestrate child, whose stdout is the run
    log; the operator's standing habit is the launcher narration -- this
    process's stdout, which --detached-stdout binds to detached-launcher.log.
    The first live serve cost 26 operator-minutes because no watched surface
    said the URL. Each newly served, still-unanswered round is announced
    exactly once, read from the round's own sentinel so this surface and the
    child's waiting line can never disagree.

    Never raises: a broken sentinel or a scan error skips a beat, and the
    next poll tries again -- announcing is a courtesy that must not touch
    the roll.
    """
    seen: set[str] = set()
    gate_dir = repo_root / "data" / "visual-gate"
    while not stop.wait(poll_seconds):
        try:
            for pending in sorted(gate_dir.glob("*/round-*/feedback-pending.json")):
                key = str(pending)
                if key in seen:
                    continue
                round_dir = pending.parent
                if (round_dir / "feedback.json").is_file() or (
                    round_dir / "feedback-consumed.json"
                ).is_file():
                    seen.add(key)
                    continue
                try:
                    url = str(json.loads(
                        pending.read_text(encoding="utf-8")
                    ).get("url", ""))
                except (OSError, ValueError):
                    continue  # mid-write; the next poll reads it whole
                if not url:
                    continue
                seen.add(key)
                line = (
                    f"VISUAL GATE waiting for the operator -- open {url} "
                    f"(issue {round_dir.parent.name}, {round_dir.name})"
                )
                announce(line, flush=True)
                if log is not None:
                    log.write(line)
        except OSError:
            continue


def roll_issue(
    repo_root: Path, issue: int, log_dir: Path, az_root: Path, extra: list[str],
    resume_from: str | None = None, *, fresh: bool = False,
) -> int:
    # #2409: `fresh` is keyword-only and passed by the caller ONLY when true,
    # for the same reason resume_from travels only when a resume fires -- test
    # stubs replace this function with bare *args lambdas and fixed five-arg
    # defs, so the ordinary path must keep its exact historical call shape.
    tag = f"run-issue{issue}-{datetime.now().strftime('%H%M%S')}"
    run_start = _stamp()
    log = EventLog(log_dir / f"{tag}-events.log")
    heartbeat_path = log_dir / f"{tag}-heartbeat.log"
    out_path = log_dir / f"{tag}.log"

    log.write(f"START issue=#{issue} repo={repo_root} pid={os.getpid()}")

    with Heartbeat(heartbeat_path):
        base: str | None = None
        if resume_from:
            base = ensure_base_for_resume(repo_root, issue, log)
            if base is None:
                log.write(f"RESUME fell back to a fresh draw for #{issue}")
                resume_from = None
        if base is None:
            # The fourth argument travels ONLY when --fresh was given, and
            # positionally, for the reason stated above: test stubs replace
            # ensure_base with bare *args lambdas, which take any number of
            # positional arguments and no keyword ones.
            base = (
                ensure_base(repo_root, issue, log, True)
                if fresh
                else ensure_base(repo_root, issue, log)
            )
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
        if resume_from:
            cmd += ["--resume-from", resume_from]
            log.write(
                f"RESUME #{issue} from '{resume_from}' -- passed stages "
                "reused, not redrawn"
            )
        log.write(f"LAUNCH base={base} -> {out_path.name}")

        # #2422: the stop the operator can reach without a prompt. The watch
        # runs CONCURRENTLY with the child, not around it -- the call that
        # produced this issue had thirteen minutes left to run, and a check
        # that only fires at a stage boundary would not have touched it.
        watch = KillWatch(repo_root, issue, on_kill=log.write)

        # Direct redirect: the child's stdout goes straight to the file with no
        # pipe in the path. Restoring a pipe here reintroduces the teardown that
        # killed campaign runs. Popen rather than run() so the watch has the
        # child to kill while it is still running; the redirect is unchanged.
        with out_path.open("w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.Popen(
                cmd, cwd=str(az_root), stdout=fh, stderr=subprocess.STDOUT,
                env=_child_env(tag, run_start),
                # #2037: no console for the pipeline either. Under Task
                # Scheduler the parent has none to inherit, so without this the
                # child allocates its own.
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                ),
            )
            # #2520: announce the visual gate's URL on the launcher's own
            # surfaces while the child runs -- concurrent, like the kill
            # watch, because the gate serves mid-stage and the operator is
            # watching THIS log.
            gate_stop = threading.Event()
            gate_watch = threading.Thread(
                target=_watch_visual_gate_urls,
                args=(repo_root, gate_stop, log),
                daemon=True,
            )
            gate_watch.start()
            try:
                with watch.watch(proc):
                    returncode = proc.wait()
            finally:
                gate_stop.set()
        log.write(f"CHILD EXITED rc={returncode}")

        if watch.fired:
            # The child's own rc after a tree-kill is whatever Windows chose;
            # it says nothing. The verdict is the operator's order.
            log.write(
                f"{KILLED_MARKER}: #{issue} stopped by operator "
                f"(child rc={returncode} discarded)"
            )
            clear_kill_files(repo_root, issue)
            log.write(f"EXIT rc={KILL_EXIT_CODE}")
            return KILL_EXIT_CODE

    log.write(f"EXIT rc={returncode}")
    return returncode


def _child_env(tag: str = "", start: str = "") -> dict[str, str]:
    env = dict(os.environ)
    env["CLAUDECODE"] = ""         # nested Claude sessions fail without this
    env["PYTHONUNBUFFERED"] = "1"  # Python buffers stdout when not on a TTY
    # #2662: the child's IO is UTF-8, so no stage can be killed by printing the
    # text it exists to process. boostgauge #379 halted three attempts out of
    # three when N0c printed the conflict it had just found -- the sixth kill in
    # the cp1252 class, and the verdict never rendered, so the conflicts
    # themselves were consumed by the crash.
    #
    # This is the half `utf8_console.install()` at orchestrate.py's entry cannot
    # reach: UTF-8 mode also makes every default-encoding `open()` UTF-8, and
    # the pipeline writes LLD and spec artifacts. Measured -- with a stream
    # reconfigure in force, `Path.write_text` still raised on U+2265; with this,
    # it wrote b'\xe2\x89\xa5'.
    #
    # It is NOT sufficient alone, which is why both ship. PYTHONIOENCODING takes
    # precedence over UTF-8 mode for stdio, so an inherited
    # PYTHONIOENCODING=cp1252 -- and a wrapper in this fleet is documented to
    # set one, see dependabot_review's note on #2156 -- defeats this entirely,
    # with the identical crash at the identical position, while the reconfigure
    # holds. Set here rather than only relied upon from the ambient environment
    # for the reason that docstring records: correctness that depends on the
    # launcher leaves every other invocation unprotected.
    env["PYTHONUTF8"] = "1"
    # #2423: --fail-fast rides the environment rather than argv. The pipeline
    # is three processes deep and has several independent retry gates; a flag
    # would have to be threaded through every one of them, which is exactly how
    # a mode ends up honoured in some transports and silently ignored in
    # others. `dict(os.environ)` above already carries it -- this is the
    # explicit statement that it is meant to travel.
    if retry_gate.fail_fast_enabled():
        env[retry_gate.ENV_FAIL_FAST] = "1"
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
    # #2167: an operator's deliberate override must ride the relaunch too, or
    # the detached run re-refuses on the very gate the operator waived.
    if getattr(args, "override_prereqs", False):
        argv.append("--override-prereqs")
    # #2436: same reasoning -- the detached run re-runs every preflight, so an
    # override left behind here would refuse inside a scheduled task where the
    # refusal is invisible and the operator is told the roll simply died.
    if getattr(args, "ignore_blockers", False):
        argv.append("--ignore-blockers")
    # #2191: a confirmed redraw must ride too, or the detached run re-refuses
    # on the gate the operator just typed a phrase to clear -- and refuses
    # non-interactively, where nothing can answer it.
    if getattr(args, "redraw_completed", False):
        argv.append("--redraw-completed")
    # #2193: same for a demanded full redraw -- the detached run must not
    # resume the very state the operator asked to discard.
    if getattr(args, "fresh", False):
        argv.append("--fresh")
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


def _interruptible_sleep(seconds: int, tick: int = 5) -> None:
    """Sleep in short ticks so a stop lands promptly (#2086).

    A single long `time.sleep` is a poor citizen here: `--detach-stop` kills the
    process tree, but between the kill and the wake there is nothing checking
    signals, and on Windows a SIGTERM handler cannot interrupt a blocking sleep.
    Ticking keeps the wait responsive and, just as importantly, keeps it
    testable -- a test can assert the loop is bounded rather than waiting an
    actual quarter of an hour.
    """
    remaining = max(0, int(seconds))
    while remaining > 0:
        time.sleep(min(tick, remaining))
        remaining -= tick


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


def stop_detached(log_dir: Path, repo_root: Path | None = None) -> int:
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

    # #2831: by name would end whatever roll is live on this machine.
    ended, outcome = _end_task_for(repo_root or Path(log_dir).resolve().parents[2])
    if not ended and not killed:
        log.write("DETACH-STOP nothing was running")
    print(outcome)
    return 0


def _active_run_event_logs(log_dir: Path, issue: int | None) -> list[Path]:
    """The run's OWN events logs, newest last.

    `stop_detached` stamps `detach-events.log`, which is the wrapper's record,
    not the run's. A postmortem reads `run-issue<N>-<time>-events.log`, and an
    ordered stop that never appears there is indistinguishable from a crash --
    which is exactly what the 2026-08-15 kill looked like afterwards (#2422).
    """
    pattern = f"run-issue{issue}-*-events.log" if issue is not None else "run-*-events.log"
    try:
        return sorted(Path(log_dir).glob(pattern), key=lambda p: p.stat().st_mtime)
    except OSError:
        return []


def kill_roll(repo_root: Path, log_dir: Path, issue: int | None) -> int:
    """Stop a running roll on the operator's order, and say so in the record.

    The difference from `--detach-stop` is not the killing -- it is that this
    stamps `KILLED BY OPERATOR` into the run's own events log, so the
    postmortem and the healing ledger read an ordered stop rather than a
    corpse, and clears any stop file so the next launch is not stopped by a
    leftover.
    """
    log_dir = Path(log_dir)
    stamped: list[Path] = []

    def _stamp_run_logs(message: str) -> None:
        for path in _active_run_event_logs(log_dir, issue):
            try:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(f"{_stamp()} {message}\n")
                stamped.append(path)
            except OSError:
                continue

    who = f"#{issue}" if issue is not None else "all issues"
    path = pid_file(log_dir)
    killed = False
    pid = ""
    if path.exists():
        pid = path.read_text(encoding="utf-8").strip()
        if not is_live_python(pid):
            # Windows recycles pids; a stale file plus an unlucky reuse would
            # tree-kill somebody else's work on a shared machine.
            print(f"Recorded pid {pid} is not a running python process.")
            print("Nothing to stop -- the roll is already gone.")
            path.unlink(missing_ok=True)
        else:
            ok, detail = tree_kill(pid)
            killed = ok
            if ok:
                print(f"Stopped the roll and its process tree (pid {pid}).")
            else:
                print(f"No live tree for pid {pid} ({detail or 'no detail'}).")
            path.unlink(missing_ok=True)
    else:
        print(f"No roll is recorded as running here ({path}).")

    if killed:
        _stamp_run_logs(
            f"{KILLED_MARKER}: --kill for {who} tree-killed pid {pid}"
        )
    # The stop file is cleared whether or not a tree was found: the operator's
    # order has been carried out either way, and a surviving file would stop
    # the NEXT launch for a reason nobody would connect to today.
    for removed in clear_kill_files(repo_root, issue):
        print(f"Cleared stop file {removed}.")

    if sys.platform == "win32":
        # Return the scheduled task to Ready when one was used. Absence is
        # normal -- a foreground roll never registered one. #2831: only when
        # the task is THIS repo's roll; the name is machine-global.
        _ended, outcome = _end_task_for(repo_root)
        print(f"  {outcome}")

    # #2859: a tree-kill skips RESTORE's `finally`, so the attempt branch
    # `issue-N` was left standing at its last checkpoint -- and the next
    # launch's impl stage refuses a leftover branch that carries commits
    # (#2310), while #2845's recovery looks only under graveyard/. On
    # 2026-09-05 the stop below promised "the next launch resumes from where
    # this one stopped" and the launch that followed halted in three seconds
    # on the leftover name. The RESTORE tail this kill prevented runs here
    # instead: the worktree is removed when git will let it go, and the branch
    # is disposed by the #2310 rule -- renamed under graveyard/ when it holds
    # work, safe-deleted when it holds nothing -- so the resume finds it.
    disposed = _dispose_after_kill(repo_root, issue) if killed else []
    for line in disposed:
        print(f"  {line}")

    if stamped:
        print(f"Stamped '{KILLED_MARKER}' into {len(stamped)} run log(s).")
    print(
        "\n  This was an ordered stop, not a failure. The stages that passed "
        "are preserved;\n  the next launch resumes from where this one stopped."
    )
    return 0


def _dispose_after_kill(repo_root: Path, issue: int | None) -> list[str]:
    """RESTORE's worktree-and-branch tail, for a stop that skipped RESTORE.

    Returns the lines to print. Never raises: the kill has already happened,
    and a cleanup that cannot run is reported, not turned into a failed stop.
    """
    if issue is None:
        return ["no issue named; attempt branches left as they are"]
    lines: list[str] = []
    try:
        if reset.remove_worktree(repo_root, issue):
            lines.append(f"Removed the worktree for #{issue}.")
        base = attempt.default_branch(repo_root)
        failures = reset.dispose_pipeline_branches(repo_root, issue, base)
        for failure in failures:
            lines.append(f"branch not disposed: {failure}")
        if not failures:
            lines.append(
                f"Attempt branch for #{issue} disposed (preserved under "
                f"graveyard/ if it held work); the next launch recovers it."
            )
    except Exception as exc:  # noqa: BLE001 - the stop has happened; report
        # fail-open: the operator's order -- stop the roll -- is already
        # carried out above. A failure in the tidy-up that follows is named
        # here so the operator knows the branch may still be standing; turning
        # it into a non-zero exit would report a stop that succeeded as one
        # that failed, which is the confusion #2422's stamp exists to prevent.
        lines.append(
            f"could not dispose #{issue}'s worktree/branch ({exc}); if "
            f"`issue-{issue}` is still standing, rename it under graveyard/ "
            f"before relaunching"
        )
    return lines


# =============================================================================
# Following a detached roll -- the console the operator launched from IS the
# display (standard 0026, #2138)
# =============================================================================

FOLLOW_POLL_SECONDS = 2
QUIET_NOTE_SECONDS = 300
_START_GRACE_SECONDS = 60
# A viewer that cannot ask the scheduler anything must eventually let go: an
# unbounded unknown-status loop held CI for its full 30-minute timeout when a
# test stub answered every query with nothing (#2138).
_MAX_UNKNOWN_STATUS = 30


def _drain(path: Path, pos: int) -> tuple[int, str]:
    """New content of `path` since byte `pos`. A missing file is quiet."""
    if not path.exists():
        return pos, ""
    with path.open("rb") as fh:
        fh.seek(pos)
        data = fh.read()
    return pos + len(data), data.decode("utf-8", errors="replace")


def _task_status() -> str:
    """The scheduled task's status ('Running', 'Ready', ...), or "" if unknown.

    Unknown is NOT folded into "done": a transient query failure while the
    roll is mid-arc must keep the view attached, not declare victory.
    """
    result = _run(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "CSV", "/NH"])
    if result.returncode != 0:
        return ""
    for line in (result.stdout or "").splitlines():
        fields = [f.strip().strip('"') for f in line.split('","')]
        if len(fields) >= 3 and TASK_NAME in fields[0]:
            return fields[-1]
    return ""


def _task_names_repo(repo_root: Path) -> bool | None:
    """Whether the scheduled task on this machine was registered for `repo_root`.

    #2831: the task name is machine-global -- there is one AZ-SpeedrunRoll --
    so ending it by name ends whatever roll is live. On 2026-09-05 a unit test
    killing its own tmp roll ended the operator's live run 13 that way, which
    is the #2510 wrapper death. The task's own "Task To Run" carries the
    `--repo` it was launched for; end it only when that names this repo.
    None when schtasks cannot say, which is not a licence to end it.
    """
    result = _run(["schtasks", "/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"])
    if result.returncode != 0:
        return None
    wanted = str(Path(repo_root).resolve()).lower().replace("/", "\\")
    for line in (result.stdout or "").splitlines():
        if line.strip().startswith("Task To Run:"):
            command = line.split(":", 1)[1].lower().replace("/", "\\")
            return wanted in command
    return None


def _end_task_for(repo_root: Path) -> tuple[bool, str]:
    """End the scheduled task only when it is this repo's roll.

    Returns (ended, what happened) so the caller can log and print the
    outcome in one line each.
    """
    ours = _task_names_repo(repo_root)
    if ours is None:
        return False, (
            f"Task '{TASK_NAME}' not ended: schtasks could not say which "
            "repository it runs."
        )
    if not ours:
        return False, (
            f"Task '{TASK_NAME}' not ended: it is running another repository's "
            f"roll, not {repo_root}."
        )
    ended = _run(["schtasks", "/End", "/TN", TASK_NAME])
    if ended.returncode != 0:
        return False, f"Task '{TASK_NAME}' was not running."
    return True, f"Task '{TASK_NAME}' ended."


def _task_last_result() -> int | None:
    """The task's Last Result as an exit code, when schtasks will say.

    Clamped to the exit-code range: outside it the value is a scheduler status
    (e.g. SCHED_S_TASK_HAS_NOT_RUN), not the roll's result.
    """
    result = _run(["schtasks", "/Query", "/TN", TASK_NAME, "/V", "/FO", "CSV"])
    if result.returncode != 0:
        return None
    rows = list(csv.reader((result.stdout or "").splitlines()))
    if len(rows) < 2:
        return None
    try:
        code = int(rows[1][rows[0].index("Last Result")].strip())
    except (ValueError, IndexError):
        return None
    return code if 0 <= code < 256 else 1


def _roll_log_candidates(log_dir: Path) -> list[Path]:
    return [
        p for p in log_dir.glob("run-*.log")
        if not p.name.endswith("-events.log")
        and not p.name.endswith("-heartbeat.log")
    ]


def _newest_roll_log(log_dir: Path) -> Path | None:
    """The active attempt's stdout log, where the NODE lines land (#2158)."""
    candidates = _roll_log_candidates(log_dir)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


#: A heartbeat lands every 15 seconds, so four missed beats is the line between
#: "between beats" and "stopped". Long enough that ordinary scheduling jitter
#: does not read as death; short enough that an operator is not told to keep
#: waiting on a run that ended a minute ago.
HEARTBEAT_FRESH_SECONDS = 60

#: The run's OWN last words, in the orchestrator's wording. A log carrying
#: either has ended and is not coming back, whatever its mtime says -- which is
#: what stops a freshly-finished roll being read as a live one for a minute.
_RE_RUN_ENDED = re.compile(
    r"ORCHESTRATION FAILED at stage:|\[ORCHESTRATOR\] All stages passed\."
)


def run_still_writing(
    log_dir: Path, *, now: float | None = None,
    fresh_seconds: float = HEARTBEAT_FRESH_SECONDS,
) -> tuple[bool, str]:
    """Is anything still being written for this roll? (still writing, why).

    #2510: three detached rolls in ten days had their WRAPPER killed while the
    orchestrator carried on working. The follower reads the scheduled task's
    state, so all three times it announced `The roll is done: FAILED` while the
    run was mid-stage -- and on 2026-09-02 at 19:20 an operator believed it and
    ran `speedrun_reset.py` against a live orchestrator, which closed the run's
    LLD PR, deleted its branch locally and on origin, and archived the lineage
    out from under a process still writing into it.

    The task's state is a fact about the WRAPPER. These are the facts about the
    RUN, and both are on disk the whole time.

    Freshness alone is not enough, and getting that wrong costs every roll. A
    run that has just finished normally wrote its closing banner seconds before
    the task flipped to Ready, so an mtime test on its own would hold the
    follower silent for a minute after every successful roll. So the run log's
    own terminal banner wins over its mtime: a log that says how it ended has
    ended. What remains -- fresh, and no banner -- is exactly the orphan.

    Silent on a stat failure by design. A follower that cannot stat a log has
    no evidence the run is alive, and "no evidence" is the answer that lets the
    caller print the verdict it printed before this existed.
    """
    moment = time.time() if now is None else now
    newest_name, newest_age, newest_path = "", None, None
    for pattern in ("*-heartbeat.log", "run-*.log"):
        for path in log_dir.glob(pattern):
            if path.name.endswith("-events.log"):
                continue
            try:
                age = moment - path.stat().st_mtime
            except OSError:
                # fail-open: an unstattable log is no evidence of life. The
                # caller then prints the verdict it would have printed anyway,
                # so this can only lose the new protection, never invent it.
                continue
            if newest_age is None or age < newest_age:
                newest_age, newest_name, newest_path = age, path.name, path
    if newest_age is None or newest_age >= fresh_seconds:
        return False, ""
    if newest_path is not None and not newest_path.name.endswith(
        "-heartbeat.log"
    ):
        try:
            if _RE_RUN_ENDED.search(
                newest_path.read_text(encoding="utf-8", errors="replace")
            ):
                return False, ""
        except OSError:
            # fail-open, same direction as the stat above: an unreadable log
            # cannot be shown to have ended, so freshness decides and the
            # follower keeps watching. Erring toward watching is the safe half.
            pass
    return True, f"{newest_name} was written {int(newest_age)}s ago"


def _newest_heartbeat(log_dir: Path) -> str:
    """`<file>: <last line>` for the freshest heartbeat, or "" without one."""
    beats = sorted(
        log_dir.glob("*-heartbeat.log"), key=lambda p: p.stat().st_mtime
    )
    if not beats:
        return ""
    lines = beats[-1].read_text(
        encoding="utf-8", errors="replace"
    ).strip().splitlines()
    return f"{beats[-1].name}: {lines[-1]}" if lines else ""


# #2159: the roll emits everything once; verbosity is a property of the VIEW.
# Terse keeps the lines an operator acts on; verbose is the full stream. The
# filter is line-buffered because a drain can end mid-line.
_TERSE_MARKERS = (
    "NODE ", "NEXT ", "BASE", "LAUNCH", "EXIT", "START ", "CHILD EXITED",
    "STOPPED", "BLOCKED", "STORM", "ROLL ", "RESTORE", "SWEEP", "JANITOR",
    " attempt ", "OVERRIDE", "Previous run's questions", "must-resolve",
    "VERIFIED", "UNVERIFIED", "Pipeline failed", "WARNING", "Resume", "RESUME",
)


def _is_terse_line(line: str) -> bool:
    return any(marker in line for marker in _TERSE_MARKERS)


# #2160: teach text for events the atlas cannot know (gate refusals,
# storms). One entry per marker; the first matching marker teaches.
_EVENT_TEACH = {
    "STORM BACKOFF": (
        "The model provider stopped answering several times in a row. "
        "Retrying immediately would burn an attempt on the same wall, so "
        "the launcher waits and says for how long."
    ),
    "ROLL BLOCKED": (
        "The run found the issue's own wording ambiguous and filed a "
        "question for the human to rule on. No redraw can help until the "
        "ruling; the machine never rewrites meaning on its own."
    ),
    "BLOCKED:": (
        "A gate refused to spend anything. Refusals are the system "
        "working: the reason names what to fix, and nothing was lost."
    ),
}


def _teach_map() -> dict:
    """(total_steps, title) -> teach text, from every atlas (#2160).

    Keyed by total because the NODE line carries [n/total], and totals
    differ per workflow -- which disambiguates titles both graphs share.
    Import failure degrades to an empty map; teaching never costs a view.
    """
    table: dict = {}
    try:
        from assemblyzero.workflows.implementation_spec.atlas import (
            ATLAS as SPEC_ATLAS, TOTAL_STEPS as SPEC_TOTAL,
        )
        from assemblyzero.workflows.requirements.atlas import (
            ATLAS as REQ_ATLAS, TOTAL_STEPS as REQ_TOTAL,
        )
        for total, atlas in ((REQ_TOTAL, REQ_ATLAS), (SPEC_TOTAL, SPEC_ATLAS)):
            for entry in atlas.values():
                table[(total, entry["title"])] = entry["teach"]
                table[(None, entry["title"])] = entry["teach"]
    except Exception:  # noqa: BLE001 - teaching never costs the view
        pass
    return table


_NODE_LINE = re.compile(r"NODE (?:\[(\d+)/(\d+)\] )?(.+?) -- ")


class _NarrationView:
    """Line-buffered level filter for the follower's streams (#2159, #2160)."""

    def __init__(self, level: str) -> None:
        self.level = level
        self._partial: dict[str, str] = {}
        self._teach = _teach_map() if level in ("tutorial", "quiz") else {}

    def _annotate(self, line: str) -> list[str]:
        """Tutorial mode: the atlas teach text under a NODE line, an event
        teach under its first marker; everything else passes bare."""
        out = [line]
        teach = None
        match = _NODE_LINE.search(line)
        if match:
            total = int(match.group(2)) if match.group(2) else None
            teach = self._teach.get((total, match.group(3)))
        else:
            for marker, text in _EVENT_TEACH.items():
                if marker in line:
                    teach = text
                    break
        if teach:
            width = 66
            words, cur = [], ""
            for word in teach.split():
                if len(cur) + len(word) + 1 > width:
                    words.append(cur)
                    cur = word
                else:
                    cur = f"{cur} {word}".strip()
            words.append(cur)
            out += [f"  | {w}" for w in words]
        return out

    def feed(self, stream: str, chunk: str) -> str:
        if not chunk:
            return ""
        if self.level == "verbose":
            return chunk
        buf = self._partial.get(stream, "") + chunk
        lines = buf.split("\n")
        self._partial[stream] = lines.pop()
        kept = [line for line in lines if _is_terse_line(line)]
        if self.level in ("tutorial", "quiz"):
            kept = [a for line in kept for a in self._annotate(line)]
        return "".join(line + "\n" for line in kept)

    def toggle(self) -> str:
        # Tutorial drops to terse first (annotations off), then verbose,
        # then back to terse -- tutorial is an attach-time choice.
        self.level = "terse" if self.level in ("verbose", "tutorial", "quiz") else "verbose"
        # Stale partials must not replay across a mode switch.
        self._partial.clear()
        return self.level


def _poll_view_keys(view: _NarrationView) -> None:
    """`v` toggles the view level live (#2159). The keypress reaches only the
    VIEW; nothing here can touch the roll. Windows console only; a harmless
    no-op everywhere else (following is Windows-gated anyway)."""
    try:
        import msvcrt
    except ImportError:  # pragma: no cover - non-Windows
        return
    try:
        while msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("v", "V"):
                level = view.toggle()
                print(f"\n[view] narration level: {level}", flush=True)
    except Exception:  # noqa: BLE001 - a key poll must never cost the view
        pass


# =============================================================================
# Quiz mode -- the live roll as exam material (#2161). The display pauses;
# the roll never does, and the logs ARE the buffer: while a question holds
# the screen, nothing drains, and the normal loop catches up on release.
# =============================================================================


def _quiz_bank() -> dict:
    """{total_steps: atlas} for every workflow, or {} when unimportable."""
    try:
        from assemblyzero.workflows.implementation_spec.atlas import (
            ATLAS as SPEC_ATLAS, TOTAL_STEPS as SPEC_TOTAL,
        )
        from assemblyzero.workflows.requirements.atlas import (
            ATLAS as REQ_ATLAS, TOTAL_STEPS as REQ_TOTAL,
        )
        return {REQ_TOTAL: REQ_ATLAS, SPEC_TOTAL: SPEC_ATLAS}
    except Exception:  # noqa: BLE001 - the quiz never costs the view
        return {}


class _QuizMaster:
    """Questions generated from the atlas, never hand-maintained (#2161).

    The correct option is a REAL successor of the current node; distractors
    are real node titles from the same workflow that are NOT successors, so
    the atlas drift guard keeps the exam honest for free. A seed makes the
    draw stable under test.
    """

    def __init__(self, seed: int | None = None) -> None:
        import random

        self._rng = random.Random(seed)
        self._bank = _quiz_bank()
        self.asked = 0
        self.correct = 0

    def question_from_output(self, out: str) -> dict | None:
        match = None
        for m in _NODE_LINE.finditer(out):
            match = m  # the LAST node line in the drained chunk
        if match is None or not match.group(2):
            return None
        return self.build(int(match.group(2)), match.group(3))

    def build(self, total: int, title: str) -> dict | None:
        atlas = self._bank.get(total)
        if not atlas:
            return None
        entry = next(
            (e for e in atlas.values() if e["title"] == title), None
        )
        if entry is None:
            return None
        successors = {
            atlas[s]["title"] for s in entry["successors"] if s in atlas
        }
        non_successors = [
            e["title"] for e in atlas.values()
            if e["title"] not in successors and e["title"] != title
        ]
        if not successors or len(non_successors) < 3:
            return None
        answer_title = self._rng.choice(sorted(successors))
        options = [answer_title] + self._rng.sample(sorted(non_successors), 3)
        self._rng.shuffle(options)
        letters = "abcd"
        answer = letters[options.index(answer_title)]
        return {
            "prompt": (
                f"QUIZ: '{title}' is running. Which of these can the run "
                "enter NEXT?"
            ),
            "options": list(zip(letters, options)),
            "answer": answer,
            "teach": entry["teach"],
        }

    def grade(self, question: dict, key: str | None) -> None:
        if key is None or key == "skip":
            print("  (skipped)\n", flush=True)
            return
        self.asked += 1
        if key == question["answer"]:
            self.correct += 1
            print("  Correct.", flush=True)
        else:
            print(f"  The answer was ({question['answer']}).", flush=True)
        for line in question["teach"].split(". "):
            if line.strip():
                print(f"  | {line.strip().rstrip('.')}.", flush=True)
        print(flush=True)

    def tally(self) -> str:
        if not self.asked:
            return "Quiz: no questions answered."
        return f"Quiz: {self.correct}/{self.asked} correct."


def _read_quiz_key() -> str | None:
    """One quiz keypress if pending: a-d, Enter=skip, q=drop to tutorial."""
    try:
        import msvcrt
    except ImportError:  # pragma: no cover - non-Windows
        return None
    if not msvcrt.kbhit():
        return None
    ch = msvcrt.getwch()
    if ch in "abcdABCD":
        return ch.lower()
    if ch in ("\r", "\n"):
        return "skip"
    if ch in ("q", "Q"):
        return "q"
    return None


def _quiz_hold(question: dict, *, status_fn, beat_fn) -> str | None:
    """Show the question and hold the DISPLAY until answered.

    The roll never pauses -- the logs buffer everything while the screen
    waits. A liveness ticker renders during long holds so a question can
    never mask a dead roll, and a roll that finishes releases the hold.
    """
    print(f"\n  {question['prompt']}", flush=True)
    for letter, text in question["options"]:
        print(f"    {letter}) {text}", flush=True)
    print("  [a-d, Enter to skip, q for tutorial mode]", flush=True)

    last_tick = time.time()
    while True:
        key = _read_quiz_key()
        if key is not None:
            return key
        status = status_fn()
        if status and status != "Running":
            print("  (the roll finished; releasing the question)", flush=True)
            return None
        if time.time() - last_tick >= 30:
            beat = beat_fn()
            if beat:
                print(f"  ... roll alive while you think ({beat})", flush=True)
            last_tick = time.time()
        time.sleep(0.2)


def follow_roll(
    log_dir: Path, *, context_bytes: int = 0, wait_for_start: bool = True,
    level: str = "verbose",
) -> int:
    """Stream the detached roll's narration to THIS console until it finishes.

    The roll runs under Task Scheduler; this process is only a viewer. Nothing
    here can reach the roll: the only schtasks verb used is /Query, and Ctrl+C
    detaches the view and says so. That is what makes following safe to be the
    default (standard 0026, #2138).

    `wait_for_start` covers the launch race: right after the hand-off the task
    may not have reached Running yet, and declaring "done" off that first poll
    would abandon a roll that is seconds old. Re-attaching passes False so a
    finished (or never-started) roll is reported immediately instead of after
    the grace window.
    """
    narration = log_dir / "detached-launcher.log"
    view = _NarrationView(level)
    quiz = _QuizMaster() if level == "quiz" else None
    print(
        "Following the roll. Ctrl+C stops WATCHING only -- the roll keeps "
        f"running. Narration level: {level} (press v to toggle).\n",
        flush=True,
    )
    if level == "tutorial":
        # #2160: orientation comes from an editable markdown file, once per
        # attach. A missing file is one line, never a failure.
        orientation = (
            Path(__file__).resolve().parents[1]
            / "docs" / "tutorial" / "0001-follow-orientation.md"
        )
        try:
            print(orientation.read_text(encoding="utf-8"), flush=True)
        except OSError:
            print(f"(orientation file missing: {orientation})\n", flush=True)

    pos = 0
    if narration.exists():
        pos = max(0, narration.stat().st_size - context_bytes)

    # #2158: the per-roll stdout (stage tables, NODE position lines) streams
    # too. History present at attach is skipped; a fresh attempt's log starts
    # from byte zero; when the attempt changes, the old log's tail drains
    # before the new one takes over.
    roll_positions = {
        p.name: p.stat().st_size for p in _roll_log_candidates(log_dir)
    }
    current_roll: str | None = None

    def _drain_roll_log() -> bool:
        nonlocal current_roll
        newest = _newest_roll_log(log_dir)
        if newest is None:
            return False
        printed = False
        if current_roll and current_roll != newest.name:
            old = log_dir / current_roll
            old_pos, tail = _drain(old, roll_positions.get(current_roll, 0))
            roll_positions[current_roll] = old_pos
            if tail:
                printed = True
                out = view.feed("roll", tail)
                if out:
                    print(out, end="", flush=True)
        current_roll = newest.name
        new_pos, chunk = _drain(newest, roll_positions.get(newest.name, 0))
        roll_positions[newest.name] = new_pos
        if chunk:
            printed = True
            out = view.feed("roll", chunk)
            if out:
                print(out, end="", flush=True)
                # #2161: a NODE transition in quiz mode holds the DISPLAY
                # for a question. The roll never pauses; the logs buffer.
                if quiz is not None and view.level == "quiz":
                    question = quiz.question_from_output(out)
                    if question:
                        key = _quiz_hold(
                            question,
                            status_fn=_task_status,
                            beat_fn=lambda: _newest_heartbeat(log_dir),
                        )
                        if key == "q":
                            view.level = "tutorial"
                            print("[view] narration level: tutorial",
                                  flush=True)
                            quiz.grade(question, "skip")
                        else:
                            quiz.grade(question, key)
        return printed

    seen_running = False
    unknown_streak = 0
    start_deadline = time.time() + _START_GRACE_SECONDS
    last_line_at = time.time()
    #: #2510: set when the scheduled task has ended but the run is still
    #: writing, so the notice is printed once rather than every poll.
    wrapper_ended_at = ""
    try:
        while True:
            _poll_view_keys(view)
            pos, chunk = _drain(narration, pos)
            if chunk:
                # Liveness tracks RAW arrival: filtered-out detail still
                # proves the roll is moving, so terse mode does not emit
                # quiet-notes into an active run.
                last_line_at = time.time()
                out = view.feed("narration", chunk)
                if out:
                    print(out, end="", flush=True)
            if _drain_roll_log():
                last_line_at = time.time()

            status = _task_status()
            if not status:
                unknown_streak += 1
                if unknown_streak >= _MAX_UNKNOWN_STATUS:
                    print(
                        f"\nCannot query the scheduler after {unknown_streak} "
                        "attempts; detaching the view. The roll, if any, is "
                        "unaffected -- re-attach with --follow.",
                        flush=True,
                    )
                    return 1
            elif status == "Running":
                unknown_streak = 0
                seen_running = True
            elif (
                seen_running
                or not wait_for_start
                or time.time() > start_deadline
            ):
                pos, chunk = _drain(narration, pos)
                if chunk:
                    out = view.feed("narration", chunk)
                    if out:
                        print(out, end="", flush=True)
                # #2158: the roll's final stdout lines land between the last
                # drain and the status flip, same race as the narration's.
                _drain_roll_log()
                if seen_running or wait_for_start:
                    code = _task_last_result() or 0
                    # #2510: the task's state is a fact about the WRAPPER. Three
                    # times in ten days the wrapper was killed and the
                    # orchestrator carried on, and this line said FAILED while
                    # the run was two stages from a PR. Say what actually
                    # happened and keep following.
                    still, why = run_still_writing(log_dir)
                    if still:
                        if not wrapper_ended_at:
                            wrapper_ended_at = time.strftime("%H:%M:%S")
                            print(
                                f"\nWrapper ended at {wrapper_ended_at} "
                                f"(task status: {status}, exit {code}), but the "
                                f"run is still writing -- {why}.\n"
                                f"Still following. Do NOT reset or relaunch "
                                f"this issue: the orchestrator is alive and "
                                f"--kill names the dead wrapper (#2510).",
                                flush=True,
                            )
                        time.sleep(FOLLOW_POLL_SECONDS)
                        continue
                    # #2165: the word, not just the number. The full verdict
                    # block streams above this from the narration; this line
                    # is the follower's own sign-off.
                    if quiz is not None:
                        print(f"\n{quiz.tally()}", flush=True)
                    word = "SUCCEEDED" if code == 0 else "FAILED"
                    tail = (
                        f"\nThe roll is done: {word} "
                        f"(task status: {status}, exit {code})."
                    )
                    if wrapper_ended_at:
                        tail += (
                            f"\nThe wrapper had ended at {wrapper_ended_at}; "
                            f"the run kept writing until now, so the exit code "
                            f"above is the wrapper's and not the run's -- read "
                            f"the run log's own closing banner."
                        )
                    print(tail, flush=True)
                    return code
                print(f"\nNo roll is running (task status: {status}).", flush=True)
                return 0

            if time.time() - last_line_at >= QUIET_NOTE_SECONDS:
                quiet = int((time.time() - last_line_at) // 60)
                beat = _newest_heartbeat(log_dir)
                note = f"... still running; narration quiet {quiet}m"
                if beat:
                    note += f" (freshest heartbeat {beat})"
                print(note, flush=True)
                last_line_at = time.time()

            time.sleep(FOLLOW_POLL_SECONDS)
    except KeyboardInterrupt:
        name = Path(__file__).name
        print("\n\nStopped WATCHING. The roll is still running under Task Scheduler.")
        print(f"  re-attach   {name} --repo <repo> --follow")
        print(f"  stop roll   {name} --repo <repo> --detach-stop")
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


def restore_repo(
    repo_root: Path,
    issues: list[int],
    log: EventLog,
    baseline_untracked: set[str] | None = None,
) -> list[str]:
    """Hand the repo back the way it was borrowed (#2005). Returns failures.

    A roll leaves the target checked out on the attempt branch with pipeline
    worktrees registered. Being handed that back is a defect: a run should
    return the repo to the state it took.

    #2145 / standard 0027: `baseline_untracked` is the untracked-file set the
    roll borrowed. Any NEW untracked file the pipeline emitted is preserved
    to a graveyard ref and cleared; a new file the machinery cannot prove it
    made is a restore failure by name, never deleted. "RESTORE verified" may
    only print when the untracked delta is empty. `data/speedrun/**` is
    gitignored, so the evidence never appears in the delta at all.

    Called from a `finally`, so it runs on success, on failure, and on any
    exception -- including the SignalExit raised by the handlers above. It
    cannot run under SIGKILL; that gap is covered only by the next
    invocation's entry janitor, and is stated rather than papered over.
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

    # #2310: a removed worktree leaves its branch standing. Dispose of it here
    # -- AFTER the checkout has moved to the base, so the branch being freed is
    # never the one HEAD is on. Left alone, `issue-{N}` squats on the SHA the
    # relaunch wants to branch from and `worktree add -b` dies on it.
    # Branch names are freed by safe delete when they hold nothing unique, and
    # preserved under graveyard/ when they hold work. Never a force delete.
    # #2325: `base` is passed explicitly. The disposition is decided by
    # counting commits against it, never by asking `git branch -d` -- that
    # command accepts anything merged to its upstream, and every pipeline
    # branch has one, so it would delete exactly the branches worth keeping.
    for issue in issues:
        failures += reset.dispose_pipeline_branches(repo_root, issue, base)
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

    inputs_kept: list[str] = []
    if baseline_untracked is not None:
        new = sorted(set(untracked_files(repo_root)) - baseline_untracked)
        # #2551: the roll's own canonical inputs are not leavings even when
        # the run itself wrote them -- the lld stage saves the approved LLD
        # to docs/lld/active/, the impl stage reads it there on every entry
        # including a resume, and the 13:25 teardown sweep of
        # run-issue331-130125 cleared it between the two. What the loader
        # resolves for a rolling issue stays in place, named in the log.
        inputs_kept = [f for f in new if is_pipeline_input(f, issues)]
        for kept in inputs_kept:
            log.write(f"RESTORE input kept (not litter): {kept}")
        machinery_new = [
            f for f in new
            if is_machinery_owned(f) and f not in inputs_kept
        ]
        operator_new = [
            f for f in new
            if not is_machinery_owned(f) and f not in inputs_kept
        ]

        if machinery_new:
            janitor = preserve_and_clear(
                repo_root, machinery_new,
                log=lambda m: log.write(m.strip()),
            )
            failures += [
                f"pipeline leaving not cleared: {p.describe()}"
                for p in janitor.problems
            ]
            # #2164: exit reconciles are heals too.
            for entry in janitor.entries:
                record_heal(
                    repo_root, "restore-reconcile", entry.path,
                    "healed" if entry.ok else "partial",
                    detail=entry.describe(),
                )
        for f in operator_new:
            # Not the machinery's to touch: a new file it cannot prove it
            # made is surfaced, never preserved or deleted on its author's
            # behalf.
            failures.append(f"new untracked file not made by the pipeline: {f}")

    if not failures:
        kept_note = (
            f" beyond {len(inputs_kept)} canonical input(s) kept in place"
            if inputs_kept else ""
        )
        log.write(
            f"RESTORE verified: on '{base}', no pipeline worktrees, clean, "
            f"no new untracked files{kept_note}"
        )
    return failures


# =============================================================================
# Verdict and prerequisites -- the last words in the narration (#2165, #2167)
# =============================================================================

PREREQS_FILENAME = "prereqs.json"


def prereqs_path(repo_root: Path) -> Path:
    return Path(repo_root) / "data" / "speedrun" / PREREQS_FILENAME


def write_prereqs(repo_root: Path, blocking: list[dict], note: str) -> bool:
    """Record the questions that gate the next launch. Returns True if written.

    #2196: an empty `blocking` list is never written. It records "something
    blocked but I do not know what", and the reader cannot verify an empty list
    closed -- so every later launch refuses, permanently, with no way to
    self-clear. Observed on boostgauge 2026-08-10, where a batch wrote
    `"blocking": []` and the machine then sat idle about an hour and forty-five
    minutes on a gate with nothing behind it; every must-resolve issue had been
    closed within half an hour of the write.

    Declining to write is safe because the launcher still runs the live
    open-must-resolve query on every launch. That query is the same source of
    truth this file caches, so the repo stays guarded -- what is lost is only
    the cached certainty, which in this case was certainty of nothing.
    """
    if not blocking:
        print(
            "  (Not recording a launch gate: this run blocked but produced no "
            "question numbers to record. The live must-resolve query still "
            "guards the next launch.)"
        )
        return False

    path = prereqs_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"created": _stamp(), "note": note, "blocking": blocking},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return True


def _latest_run_tag(log_dir: Path, issue: int) -> str:
    """This issue's newest run tag, read off the log triplet it just wrote.

    roll_issue mints the tag internally and returns only an exit code -- its
    call shape is pinned by test stubs (bare *args lambdas and fixed five-arg
    defs), so the tag is recovered here rather than threaded back. Absence is
    reported as absence, never guessed: a wrong tag sends a human to read the
    wrong log.
    """
    try:
        logs = sorted(Path(log_dir).glob(f"run-issue{issue}-*.log"))
    except OSError:
        return ""
    return logs[-1].stem if logs else ""


def check_already_completed(
    repo_root: Path, issues: list[int], override: bool, *, stream=None
) -> int | None:
    """Refuse to redraw what this arc already finished (#2191).

    Returns None to proceed, 91 to refuse.

    The 2026-08-10 near-miss: issue #4 completed end to end, its LLD and
    implementation PRs merged into `hardening-run-17`, and the operator's next
    launch included `--issue 4` again out of habit. Nothing objected -- the
    launcher would have reset #4's branches and redrawn an issue whose
    implementation was already on the arc. An agent reading the log caught it.

    Arc-scoped: a success on one arc must not nag a deliberate re-run campaign
    on the next one. A gate that fires on a new arc is a false alarm, and this
    one has to be believed the day it fires for real.
    """
    arc = resolve_attempt_branch(repo_root)
    if not arc:
        # No arc resolved means no scope to check against. The ledger is a
        # cache; its absence of opinion must never refuse a launch.
        return None

    hits = [
        entry for entry in (
            completed_on(repo_root, issue, arc) for issue in issues or []
        ) if entry
    ]
    if not hits:
        return None

    print()
    print("=" * 70)
    print("ALREADY ROLLED TO SUCCESS ON THIS ARC")
    print("=" * 70)
    for entry in hits:
        print(f"  {describe(entry)}")
    print(
        "\n  Rolling these again resets their branches and redraws work this "
        "arc has\n  already finished and merged. That is occasionally what you "
        "want, and it is\n  never what you want by accident."
    )

    if override:
        print("\n  --redraw-completed given: redrawing deliberately.")
        return None

    # A phrase, never y/n (standard 0017 Danger Zone): a single keypress is
    # what an auto-answering wrapper blows through.
    if len(hits) == 1:
        expected = redraw_phrase(hits[0]["issue"])
    else:
        expected = " ".join(redraw_phrase(e["issue"]) for e in hits)

    print("\n  To redraw anyway, type this EXACTLY:")
    print(f"    {expected}")
    print("  Anything else refuses. Non-interactive callers pass "
          "--redraw-completed.")

    try:
        got = (stream.readline() if stream is not None else input("> ")).strip()
    except (EOFError, OSError):
        # Non-TTY without the flag: refuse rather than hang forever waiting
        # for input that is never coming.
        print(
            "\nBLOCKED: no console to confirm on. Pass --redraw-completed to "
            "redraw deliberately."
        )
        return 91

    if got != expected:
        print("\nBLOCKED: that is not the confirmation phrase. Nothing was spent.")
        return 91

    print("\n  Confirmed. Redrawing.")
    return None


def check_prereqs(repo_root: Path, override: bool) -> int | None:
    """The previous run's unresolved questions gate this launch (#2167).

    Returns None to proceed, 91 to refuse. Unlike the general must-resolve
    query (which proceeds with a warning offline), this file is local,
    certain knowledge of a known block -- unverifiable closure REFUSES.
    The override runs anyway ONCE and leaves the file, so the following
    launch re-checks: override means "run anyway", never "forget".

    #2196: with ONE exception. A file whose blocking list is empty or
    unreadable is not certain knowledge of a block -- it is certain knowledge
    of nothing, and refusing on it cannot self-heal, because the refusal sat
    above the closure loop while the unlink that clears the file sat below it.
    That state falls back to the live must-resolve query, which is the same
    source of truth this file caches. The gate is not weakened: open questions
    still refuse, by name, and an unreachable gh still refuses.
    """
    path = prereqs_path(repo_root)
    if not path.exists():
        return None

    if override:
        print(
            "OVERRIDE: launching despite the previous run's open questions "
            f"({path.name} kept; the next launch will re-check)."
        )
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        blocking = data.get("blocking") or []
    except (OSError, ValueError):
        blocking = []

    if not blocking:
        # #2196: an empty or unreadable list is certain knowledge of NOTHING,
        # and refusing on it converts an upstream numbers-lost bug into a total
        # launch outage that cannot self-heal -- the refusal sits above the
        # closure loop, and the unlink that clears the file sits below it.
        # Fall back to the live query, which is the same source of truth this
        # file caches. Open questions still block, by name; none means the
        # cached gate was empty and can go.
        print(
            f"A previous run recorded a launch gate in {path.name} with no "
            "readable question numbers. Consulting the live must-resolve "
            "query instead."
        )
        questions, gh_error = open_must_resolve_issues(repo_root)

        if gh_error:
            print(
                "BLOCKED: that file records unresolved questions whose numbers "
                f"could not be read, and gh was unreachable to check for open "
                f"questions directly ({gh_error}). This launch refuses rather "
                "than roll into a wall it cannot see. Resolve the questions and "
                "delete the file, or pass --override-prereqs to run anyway."
            )
            return 91

        if questions:
            print("BLOCKED: the repo has open questions awaiting a ruling:")
            for item in questions:
                print(f"  #{item.get('number')}  {item.get('title', '')}")
            print(
                "\n  Resolve them (edit the source issue, close each question), "
                "then launch again.\n  Deliberately rolling anyway: "
                "--override-prereqs."
            )
            return 91

        path.unlink(missing_ok=True)
        print(
            "No open must-resolve questions remain, so that gate recorded "
            "nothing that is still blocking -- removing it and proceeding."
        )
        return None

    still_open: list[dict] = []
    for item in blocking:
        number = item.get("number")
        state = _run(
            ["gh", "issue", "view", str(number), "--json", "state",
             "--jq", ".state"],
            cwd=repo_root,
        )
        if state.returncode != 0:
            print(
                f"BLOCKED: cannot verify that question #{number} was resolved "
                "(gh unreachable). This launch refuses rather than re-roll "
                "into a known wall. Pass --override-prereqs to run anyway."
            )
            return 91
        if state.stdout.strip().upper() != "CLOSED":
            still_open.append(item)

    if still_open:
        print("BLOCKED: the previous run's questions are still open:")
        for item in still_open:
            print(f"  #{item.get('number')}  {item.get('title', '')}")
        print(
            "\n  Resolve them (edit the source issue, close each question), "
            "then launch again.\n  Do not re-roll without resolution -- the "
            "same conflicts will refire.\n  Deliberately rolling anyway: "
            "--override-prereqs."
        )
        return 91

    path.unlink(missing_ok=True)
    numbers = ", ".join(f"#{i.get('number')}" for i in blocking)
    print(f"Previous run's questions resolved ({numbers}) -- proceeding.")
    return None


def print_verdict(
    repo_root: Path,
    *,
    requested: list[int],
    rolled: list[int],
    blocked: list[int],
    stopped_at: int | None,
    code: int,
    since: str = "",
) -> None:
    """State the outcome in words, last, with the next step (#2165).

    Never raises: a verdict must not cost a run, and it must render even
    when gh is unreachable.

    `since` bounds the filed-questions ledger to this batch (#2179).
    """
    try:
        _render_verdict(
            repo_root, requested, rolled, blocked, stopped_at, code, since,
        )
    except Exception as exc:  # noqa: BLE001 - the verdict is best-effort display
        print(f"(verdict rendering failed: {exc})")


def _blocking_questions(repo_root, since: str) -> tuple[list[dict], str | None]:
    """The questions blocking this batch: the live list, plus what we filed.

    Closes #2179. The live query alone returned short -- six times across
    2026-08-09/10/11, once listing one question of three filed four seconds
    apart -- because GitHub had not finished indexing a just-created issue. The
    ledger records each number at the moment it is created, so the two together
    cannot under-report the way one of them does alone.

    The union also covers the offline case: gh unreachable used to mean an
    empty list for both the summary and the gate, and now means whatever this
    machine knows it filed.
    """
    live, gh_error = open_must_resolve_issues(repo_root)
    recorded = read_filed(repo_root, since=since)
    return merge_questions(live or [], recorded), gh_error


def _requirements_unverified_lines(repo_root, since: str) -> list[str]:
    """The REQUIREMENTS UNVERIFIED banner for this batch, or no lines (#2290).

    Read from the ledger rather than from run state: the gate executes inside a
    child process, so its warning cannot otherwise reach this block. Never
    raises -- the verdict must print even if the ledger cannot be read.
    """
    try:
        from assemblyzero.speedrun.requirements_status import (
            format_banner,
            read_unverified,
        )

        return format_banner(read_unverified(repo_root, since=since))
    except Exception:  # noqa: BLE001 - the verdict always prints
        return []


def _archive_successful_run(repo_root) -> list[str]:
    """Archive and verify the run that just succeeded (#2353).

    Operator, 2026-08-14, on reading "Next step: archive the run": "why am I
    being the monkey here anyway. the roll succeeded. why isn't the archive
    step automatic?" There was no good answer. The tool is deterministic,
    exit-coded, and only ever writes; the launcher already knew the roll had
    succeeded, because it had just printed the instruction. A step the
    runbook itself calls unrecoverable if skipped should not depend on a
    human remembering it.

    Never raises. The roll succeeded, and a failed archive is its own
    problem: named here, loudly, and never allowed to alter the verdict
    above it.
    """
    lines: list[str] = []
    try:
        run = resolve_attempt_branch(repo_root)
        if not run:
            return [
                "  ARCHIVE SKIPPED: no attempt branch could be resolved, so "
                "there is no run name to archive under. Archive by hand per "
                "runbook 0952 section Inspect, step 6.",
            ]

        result = archive_run(Path(repo_root), run)
        graves = len(result.index["branches"]["graveyard"])
        integration = 1 if result.index["branches"]["integration"]["sha"] else 0

        lines.append(f"  Archive: {result.path}")
        lines.append(
            f"    rolls {len(result.index['rolls'])} | branches "
            f"{integration} integration + {graves} graveyard | "
            f"files {len(result.index['manifest'])}"
        )

        if result.complete:
            lines.append("    complete yes")
        else:
            lines.append(
                "    complete NO -- this archive does not authorize deleting "
                "anything"
            )
            for name in result.missing:
                lines.append(f"      missing: {name}")

        mismatched = verify_manifest(result.path)
        if mismatched:
            lines.append(
                f"    manifest MISMATCH on {len(mismatched)} file(s): "
                f"{', '.join(mismatched[:3])}"
            )
        else:
            lines.append("    manifest OK")

        # #2404: the ReadOnly-clearing path is reported so recurrence stays
        # visible. The #2277 setter has a standing presence, so silence here
        # would turn a durable environmental condition into folklore.
        cleared = readonly_clearings()
        if cleared:
            lines.append(
                f"    cleared the Windows ReadOnly attribute on "
                f"{len(cleared)} path(s) to archive (#2404); the setter "
                f"re-flags them, so this is expected to recur"
            )

    except Exception as exc:  # noqa: BLE001 - an archive failure is not a verdict
        lines.append(
            f"  ARCHIVE FAILED: {exc}. The roll still succeeded. Archive by "
            f"hand per runbook 0952 section Inspect, step 6."
        )
    return lines


def _render_verdict(repo_root, requested, rolled, blocked, stopped_at, code, since=""):
    names = ", ".join(f"#{i}" for i in rolled) or "none"
    # #2290: computed before the branches so no verdict path can omit it. The
    # SUCCEEDED branch is the one that matters -- a roll whose requirements were
    # never checked used to print an unqualified success and read exactly like
    # a roll that had been checked and was clean.
    unverified = _requirements_unverified_lines(repo_root, since)
    print()
    if blocked:
        blocked_names = ", ".join(f"#{i}" for i in blocked)
        print(f"ROLL BLOCKED: issue(s) {blocked_names} await an operator ruling.")
        if stopped_at is not None:
            print(
                f"  Also FAILED at #{stopped_at} (exit {code}); later "
                "issues were not rolled."
            )
        print(f"  Rolled successfully: {names}.")
        questions, gh_error = _blocking_questions(repo_root, since)
        if questions:
            print("  This run filed the questions blocking it:")
            for q in questions:
                print(f"    #{q['number']}  {q['title']}")
            write_prereqs(
                repo_root, questions,
                f"blocked issue(s) {blocked_names}",
            )
            shortlist = " and ".join(f"#{q['number']}" for q in questions)
            print(f"\n  Next step: resolve {shortlist}.")
        else:
            # #2179 (and #2224, closed into it): printing the heading with
            # nothing under it, then "Next step: resolve .", told the operator
            # to resolve nothing. Say what is actually known instead.
            if gh_error:
                print(
                    "  Questions were filed during this run, but gh was "
                    f"unreachable to list them ({gh_error}), and this machine "
                    "recorded no numbers locally."
                )
            else:
                print(
                    "  No open questions were found for this block, which is "
                    "unexpected -- something stopped the run without leaving a "
                    "question to rule on."
                )
            print(
                "  Next step: check `gh issue list --label must-resolve "
                "--state open` before launching again."
            )
            # #2196: declines to write an empty gate, which is what bricked
            # every later launch when this path fired.
            write_prereqs(
                repo_root, [],
                f"blocked issue(s) {blocked_names}; question numbers unverified",
            )
        print(
            "  Do not re-roll without resolution -- the next launch will "
            "refuse while these stay open (--override-prereqs to run anyway)."
        )
    elif code == KILL_EXIT_CODE:
        # #2422: an ordered stop reads as a decision, never as a failure. The
        # branch below would have called it "FAILED ... after exhausting its
        # attempts", which is untrue in both halves.
        who = f"#{stopped_at}" if stopped_at is not None else "the batch"
        print(f"ROLL STOPPED BY OPERATOR at {who}.")
        remaining = [i for i in requested if i not in rolled and i != stopped_at]
        if remaining:
            print(f"  Not rolled: {', '.join(f'#{i}' for i in remaining)}.")
        print(f"  Rolled successfully before the stop: {names}.")
        print(
            "  The stages that passed are preserved. Next step: relaunch when "
            "ready -- it resumes\n  from where this stopped rather than "
            "redrawing what was already paid for."
        )
    elif stopped_at is not None:
        print(
            f"ROLL FAILED at #{stopped_at} (exit {code}) after exhausting "
            "its attempts."
        )
        remaining = [i for i in requested if i not in rolled and i != stopped_at]
        if remaining:
            print(f"  Not rolled: {', '.join(f'#{i}' for i in remaining)}.")
        print(f"  Rolled successfully: {names}.")
        print(
            "  Next step: hand an agent runbook 0952 section Inspect for the "
            "post-mortem before rolling again."
        )
    elif rolled == requested and code == 0:
        print(f"ROLL SUCCEEDED: all {len(rolled)} issue(s) rolled ({names}).")
        for line in _archive_successful_run(repo_root):
            print(line)
        print("  Next step: roll the next batch.")
    else:
        print(
            f"ROLL DID NOT COMPLETE (exit {code}) -- interrupted or errored "
            f"mid-batch. Rolled before the interruption: {names}."
        )
        print(
            "  Next step: hand an agent runbook 0952 section Inspect; the "
            "events logs say where it died."
        )

    # #2290: last, so it is the final thing on screen -- the operator's eye
    # lands at the bottom, which is the same reason the verdict itself moved
    # here (#2165). Prints on every branch, success included.
    for line in unverified:
        print(line)


def build_parser() -> argparse.ArgumentParser:
    """The launcher's flag surface, separated from running it (#2295).

    Extracted so a test can compare the operator-facing flags against runbook
    0952's table and parse the runbook's own examples. The runbook claimed to be
    verified against `--help` and its canonical launch example still carried the
    retired `--attempts 3`, so an operator copying it got a preflight refusal
    from the document that was supposed to prevent one. A claim of verification
    that nothing re-checks decays into a claim.
    """
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
            "Retired by operator ruling #2206: only 1 is accepted. A failure "
            "halts for diagnosis; the relaunch resumes from the failed stage "
            "(#2193) instead of redrawing. Values above 1 refuse at preflight, "
            "before anything is spent."
        ),
    )
    parser.add_argument(
        "--detach-stop", action="store_true",
        help="Stop a detached roll and every process it spawned (#2016)",
    )
    parser.add_argument(
        "--fail-fast", action="store_true",
        help=(
            "Diagnosis posture (#2423): every transport gets ONE attempt, so "
            "each defect is paid for exactly once. When the campaign is in "
            "diagnose-and-fix mode, forcing a doomed call through three times "
            "is spend without information. Travels to the pipeline by "
            "environment variable, so it reaches every transport in every "
            "child process rather than only the ones a flag was threaded to."
        ),
    )
    parser.add_argument(
        "--kill", action="store_true",
        help=(
            "EMERGENCY STOP: kill the running roll and its whole process "
            "tree, stamping KILLED BY OPERATOR into the run's events log so "
            "the stop is recorded as ordered rather than as a crash (#2422). "
            "Takes an optional --issue. When this console has no free prompt, "
            "create data/speedrun/KILL instead -- the launcher watches for it "
            "while a call is in flight."
        ),
    )
    parser.add_argument(
        "--override-prereqs", action="store_true",
        help=(
            "Launch even though a previous run's questions are still open "
            "(#2167). Runs anyway ONCE; the prerequisite file survives and "
            "the following launch re-checks."
        ),
    )
    parser.add_argument(
        "--ignore-blockers", action="store_true",
        help=(
            "Launch even though an issue marked `roll-blocker` is open in this "
            "repo or in AssemblyZero (#2436). The launch names every blocker it "
            "rolled past and records the override, so rolling into known-broken "
            "ground stays possible but can never happen by accident."
        ),
    )
    parser.add_argument(
        "--redraw-completed", action="store_true",
        help=(
            "Redraw an issue this arc has already rolled to success (#2191). "
            "Without it an interactive launch demands a typed 'REDRAW <N>' and "
            "a non-interactive one refuses, so a habit-typed issue number "
            "cannot silently redo finished work."
        ),
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help=(
            "Redraw every stage from scratch, ignoring any resumable state "
            "(#2193), AND authorize the destructive reset of this issue "
            "(#2409): closing its open PRs, deleting its branches, removing "
            "its worktree. Displaced artifacts are archived to "
            "data/speedrun/reset-artifacts/, never deleted, and any checkpoint "
            "is pinned to a rescue ref first. Without this flag a launch that "
            "finds gate findings REFUSES and names both exits rather than "
            "resetting on its own initiative."
        ),
    )
    parser.add_argument(
        "--no-follow", action="store_true",
        help=(
            "With --detach: hand the roll off and return immediately instead "
            "of streaming its narration into this console (#2138)"
        ),
    )
    parser.add_argument(
        "--follow", action="store_true",
        help=(
            "Attach to a roll that is already running and stream its "
            "narration into this console (#2138). Takes no --issue."
        ),
    )
    parser.add_argument(
        "--narration", choices=("terse", "verbose", "tutorial", "quiz"),
        default="verbose",
        help=(
            "Starting view level while following (#2159/#2160): terse shows "
            "the lines you act on, verbose shows everything, tutorial is "
            "terse annotated with what each node and gate is for. Press v "
            "in the console to toggle live; the log on disk is always "
            "complete."
        ),
    )
    # Set by --detach on the relaunch; not something anyone types.
    parser.add_argument("--detached-stdout", default=None, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
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

    # #2423: set before anything can spend, and before the detach hand-off so
    # the scheduled task's environment carries it too.
    if getattr(args, "fail_fast", False):
        retry_gate.set_fail_fast(True)
        print(
            "FAIL-FAST: every transport gets one attempt. Each defect is paid "
            "for exactly once."
        )

    # Stopping is about processes, not code: it must work even from a stale or
    # dirty tree, so it comes before the staleness gate. #2422 adds --kill for
    # the same reason and one more: an emergency stop that a gate could refuse
    # is not an emergency stop.
    if getattr(args, "kill", False):
        return kill_roll(repo_root, log_dir, args.issue[0] if args.issue else None)

    if args.detach_stop:
        return stop_detached(log_dir, repo_root=repo_root)

    # #2138 / standard 0026: a viewer, not a launcher. It spends nothing and
    # runs no gates, so it must work even when a gate would refuse a launch.
    if args.follow:
        if args.issue:
            print(
                "ERROR: --follow attaches to a roll already running; it takes "
                "no --issue"
            )
            return 91
        if sys.platform != "win32":
            print(f"ERROR: --follow is Windows-only; this is {sys.platform}")
            return 91
        return follow_roll(
            log_dir, context_bytes=2048, wait_for_start=False,
            level=args.narration,
        )

    if not args.issue:
        print("ERROR: --issue is required (repeatable) unless stopping a roll")
        return 91

    # #2206: automatic retries are deauthorized. Refuse here -- before the
    # detach hand-off and before any gate spends anything -- so the refusal
    # lands in the console the operator is standing in.
    if getattr(args, "attempts", 1) > 1:
        print(
            f"BLOCKED: --attempts {args.attempts} is retired (operator ruling "
            "#2206). Automatic retries are deauthorized:\n"
            "\n  A failed roll halts so its cause can be found. The relaunch "
            "after the fix resumes\n  from the failed stage (#2193), so the "
            "stages that already passed are never re-paid.\n"
            "\n  The campaign's failures proved systematic, not stochastic: a "
            "redraw into an unfixed\n  cause spends tokens to reproduce a "
            "result already known.\n"
            "\n  Relaunch with --attempts 1."
        )
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

    # #1920: refuse before spending anything if this machine is degraded. On
    # 2026-07-29 pytest stopped completing for ~45 minutes; a roll launched into
    # that wastes hours AND makes every failure look like a target-repo problem.
    health = check_box_health(az_root, log_dir)
    if not health.ok:
        print(health.message)
        return 91

    # #2167: the previous run's own unresolved questions gate this launch,
    # from a local file, before the live query -- certain knowledge refuses
    # even offline.
    prereq_refusal = check_prereqs(repo_root, args.override_prereqs)
    if prereq_refusal is not None:
        return prereq_refusal

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

    # #2436: the launcher answers "what will stop this roll" instead of relying
    # on a human having read the board. An open `roll-blocker` in EITHER repo
    # refuses, because a roll executes both trees; --ignore-blockers overrides
    # it deliberately. The result prints on every launch, pass or fail: a check
    # that is silent when it passes cannot be told apart from one that never
    # ran, which is #2381's complaint about box health.
    blockers = scan_roll_blockers(repo_root, az_root)
    for line in blocker_report_lines(blockers, overridden=args.ignore_blockers):
        print(line)
    if blockers.refuses and not args.ignore_blockers:
        print(blocker_refusal_message(blockers))
        return 91

    # #2227: the ADR 0226 form check, report-only by default. Free and instant
    # -- no model calls -- so it runs before anything is spent, like every
    # refusal above it. It refuses ONLY on a malformed decision table: nearly
    # every issue in the fleet is still unconverted prose (ADR 0226 section 8
    # converts on the next roll, not in a sweep), and a gate that fired on the
    # ordinary case would be waved through. Its output names itself so one
    # defect never reads as two complaints beside the semantic gate's.
    form_text, form_refuses = check_form_at_preflight(
        repo_root, args.issue or [], fetch_issue,
    )
    if form_text:
        print(form_text)
    if form_refuses:
        return 91

    # #2646: the contract-to-issue compression, the pipeline's only ungated
    # derivation. Runs here rather than at lld entry for one decisive reason:
    # settlement already hashes the binding docs into every derived artifact,
    # so a contract that CHANGES unsettles what it produced -- but an issue
    # that was wrong against the contract from the start settles cleanly, and
    # #2607's injection then carries the defective table byte-verbatim into
    # the LLD. A finding raised after lld entry invalidates an injected
    # artifact and every derivative; the same finding here is one issue edit.
    # boostgauge #331 spent nineteen ruled conflicts hardening a table that
    # was already missing a row.
    #
    # This is the first preflight check that spends a model call, so it is
    # scoped: only a repo that declares a binding contract for THIS issue in
    # docs/design/visual-gate.json is audited. Every other repo pays nothing.
    fidelity_text, _ = check_contract_fidelity_at_preflight(
        repo_root, args.issue or [], fetch_issue,
    )
    if fidelity_text:
        print(fidelity_text)

    # #2191: refuse to redraw an issue this arc has already rolled to success.
    # Here, before the detach, while the operator's console can still answer.
    completed_refusal = check_already_completed(
        repo_root, args.issue or [], args.redraw_completed,
    )
    if completed_refusal is not None:
        return completed_refusal

    # #2422: a stop file left by a previous kill would silently stop this roll
    # seconds after it started. Clear it here, in the console the operator is
    # standing in, and say so -- rather than in the detached task where the
    # explanation is invisible.
    leftover = find_kill_file(repo_root, args.issue[0] if args.issue else None)
    if leftover is not None:
        for removed in clear_kill_files(
            repo_root, args.issue[0] if args.issue else None
        ):
            print(f"Cleared a leftover stop file from an earlier kill: {removed}")

    # #2422: the emergency stop is taught at the moment of launch, beside the
    # log path. An emergency control the operator cannot remember under stress
    # does not exist, and the 2026-08-15 kill needed an agent to perform.
    for line in banner_lines(
        repo_root, args.issue[0] if args.issue else None, log_dir
    ):
        print(line)

    if args.detach:
        code = launch_detached(args, extra, repo_root, az_root, log_dir)
        if code != 0 or args.no_follow:
            return code
        # Standard 0026: the console the operator launched from is the
        # display. The work is detached; the view is not.
        return follow_roll(log_dir, level=args.narration)

    # Created only by a process that actually rolls, never by the launcher --
    # see launch_detached on why that separation is load-bearing.
    session = EventLog(log_dir / "session-events.log")
    install_signal_handlers(session)

    # #2436: the launch record carries what the blocker check found and whether
    # the operator rolled past it. Written by the process that actually rolls,
    # so the trace lands in the record a postmortem reads rather than only in a
    # console that has since scrolled away.
    session.write(blocker_trace_line(blockers, overridden=args.ignore_blockers))

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
        # #2164: every sweep action is a heal record.
        for entry in sweep.entries:
            record_heal(
                repo_root, "sweep", entry.path.name,
                "healed" if entry.ok else "partial",
                detail=entry.describe(),
            )
    except Exception as exc:  # noqa: BLE001 - a sweep must never abort a roll
        session.write(f"SWEEP FAILED (continuing): {exc}")

    # #2144 / standard 0027: the entry janitor for FILES. A predecessor that
    # died uncontrolled may have left pipeline-authored untracked files in the
    # target repo (run-16's LLD droppings blocked two launches). Preserve them
    # to a pushed graveyard ref, then clear them -- and like the sweep, a
    # janitor problem is reported and never costs the roll.
    session.write("JANITOR pipeline file leavings")
    try:
        # #2551: the rolling issues' canonical inputs (the LLD the loader
        # resolves, the spec-draft fallback) are not leavings -- the 13:01
        # launch sweep of run-issue331-130125 cleared the very LLD the run
        # was about to read. Named so the log shows the input survived.
        machinery, _operator = classify_dirt(
            repo_root, protect_issues=args.issue or []
        )
        for kept in [
            f for f in untracked_files(repo_root)
            if is_pipeline_input(f, args.issue or [])
        ]:
            session.write(f"  file janitor: input kept (not litter): {kept}")
        if machinery:
            janitor = preserve_and_clear(
                repo_root, machinery, log=lambda m: session.write(m.strip())
            )
            for problem in janitor.problems:
                session.write(f"JANITOR UNRESOLVED {problem.describe()}")
            # #2164: every janitor action is a heal record.
            for entry in janitor.entries:
                record_heal(
                    repo_root, "janitor", entry.path,
                    "healed" if entry.ok else "partial",
                    detail=entry.describe(),
                )
        else:
            session.write("  file janitor: nothing to do")
    except Exception as exc:  # noqa: BLE001 - a janitor must never abort a roll
        session.write(f"JANITOR FAILED (continuing): {exc}")

    # #2205: the arc is what the drafter and reviewer read as law. Carry the
    # default branch's binding-doc rulings onto it BEFORE anything is drawn,
    # and before resume planning, whose staleness check reads the same
    # history. A conflict refuses the launch rather than rolling against
    # docs nobody reconciled.
    arc_base = resolve_attempt_branch(repo_root)
    if arc_base:
        try:
            doc_problems = sync_binding_docs_to_arc(repo_root, arc_base, session)
        except Exception as exc:  # noqa: BLE001
            doc_problems = [f"binding-doc sync failed: {exc}"]
        if doc_problems:
            print("BLOCKED: the arc's binding docs could not be brought current:")
            for p in doc_problems:
                print(f"  - {p}")
                session.write(f"SYNC BLOCKED: {p}")
            print(
                "\n  The roll reads design docs and ADRs from the attempt "
                "branch, so rolling now\n  would build against rulings the "
                "operator has already made. Nothing was spent."
            )
            return 91

    # #2145: the untracked set the roll borrows. Everything beyond this at
    # exit is the roll's own emission, and restore_repo reconciles it.
    baseline_untracked = set(untracked_files(repo_root))

    code = 0
    rolled: list[int] = []
    blocked: list[int] = []
    stopped_at: int | None = None
    # #2179: bounds the filed-questions ledger to this batch, so a question
    # closed last week cannot reappear in tonight's summary.
    batch_started = _stamp()
    try:
        for issue in args.issue:
            # #2068: generation quality varies wildly between draws -- the same
            # issue produced 39/41-passing and 4/75-passing initial iterations
            # on consecutive rolls. A failed draw is self-healing (ensure_base
            # clears its debris), so retrying inside the detached task removes
            # the human relaunch from the loop entirely. A base or gate problem
            # (91) is NOT a draw and is never retried.
            # #2193: a relaunch that finds a non-conflict failure with the lld
            # already passed resumes from the failed stage instead of paying
            # for the passed stages again. Planning failures never block a
            # roll -- resume is an optimization, fresh is always correct.
            resume_from: str | None = None
            if not getattr(args, "fresh", False):
                try:
                    resume_from = resume_plan(az_root, repo_root, issue, session)
                except Exception as exc:  # noqa: BLE001
                    session.write(
                        f"RESUME planning failed for #{issue} "
                        f"(continuing fresh): {exc}"
                    )
            if resume_from:
                print(
                    f"\n#{issue}: resuming from '{resume_from}' -- the passed "
                    "stages are reused, not redrawn (--fresh for a full redraw)."
                )
            # #2206: one roll per issue. The redraw loop is retired by
            # operator ruling -- a failure halts for diagnosis, and the
            # relaunch after the fix resumes from the failed stage (#2193)
            # rather than re-paying for the passed ones. The campaign's
            # failures proved overwhelmingly systematic, and a redraw into an
            # unfixed cause spends tokens to reproduce a known result.
            #
            # The sixth argument travels ONLY when a resume fires: test stubs
            # replace roll_issue with both bare *args lambdas and fixed
            # five-arg defs, so the non-resume path must keep the exact
            # pre-#2193 call shape (same convention as the positional
            # restore_repo call below).
            #
            # #2409: `fresh` travels the same way and for the same reason. It
            # is what authorizes the destructive reset, so it is passed only
            # when the operator actually typed --fresh; every other launch
            # reaches ensure_base with fresh=False and gets the refusal.
            fresh_kw = {"fresh": True} if getattr(args, "fresh", False) else {}
            if resume_from:
                code = roll_issue(
                    repo_root, issue, log_dir, az_root, extra, resume_from,
                    **fresh_kw,
                )
            else:
                code = roll_issue(
                    repo_root, issue, log_dir, az_root, extra, **fresh_kw
                )

            # #2166: a requirements conflict means the ISSUE needs an operator
            # ruling. The auto-filer (#2072) has already raised the questions.
            # Stop this issue, keep the batch moving.
            if code == CONFLICT_EXIT_CODE:
                session.write(
                    f"BLOCKED #{issue} on an operator ruling -- "
                    "no redraw can help; continuing the batch"
                )
            # #2086 storms no longer back off and retry -- with one roll per
            # issue there is nothing to wait for, and the operator finds out
            # immediately instead of after an hour of sleeping.
            elif code == STORM_EXIT_CODE:
                session.write(
                    f"STORM ended #{issue} -- the provider stopped answering; "
                    "nothing was redrawn (#2206). Relaunch when it recovers."
                )
            # #2422: an ordered stop is a verdict, not a failure. It gets its
            # own branch BEFORE the generic halt below, so the operator is
            # never told to diagnose a cause they created on purpose.
            elif code == KILL_EXIT_CODE:
                session.write(
                    f"{KILLED_MARKER}: #{issue} stopped on the operator's "
                    "order. Passed stages preserved; the next launch resumes "
                    "from where this stopped."
                )
                for line in killed_verdict_lines(issue, None):
                    print(line)
                stopped_at = issue
                return code
            elif code not in (0, 91):
                session.write(
                    f"HALT #{issue} exited {code} -- no redraw (#2206). "
                    "Diagnose, fix the cause, then relaunch; the passed "
                    "stages resume rather than re-run."
                )
            if code == CONFLICT_EXIT_CODE:
                blocked.append(issue)
                continue
            if code != 0:
                stopped_at = issue
                print(
                    f"\nSTOPPED at #{issue} (exit {code}); later issues not rolled."
                )
                return code
            rolled.append(issue)
            # #2191: rc=0 is the authoritative local outcome, so record it
            # where the next launch's gate can read it before anything is
            # spent. Never raises: the roll has already succeeded.
            record_success(
                repo_root, issue=issue,
                base_branch=resolve_attempt_branch(repo_root) or "",
                run_tag=_latest_run_tag(log_dir, issue),
            )
            time.sleep(1)

        if blocked:
            return CONFLICT_EXIT_CODE
        return 0
    finally:
        # #2005: hand the repo back the way it was borrowed -- on success, on
        # failure, and on the SignalExit raised by the handlers.
        # A finished roll leaves no pid behind to be stopped, or mistaken for a
        # live one once Windows reuses the number.
        pid_file(log_dir).unlink(missing_ok=True)
        # Positional: pre-#2145 test stubs replace restore_repo with bare
        # *args lambdas, and the keyword form would break every one of them.
        failures = restore_repo(repo_root, args.issue, session, baseline_untracked)
        if failures:
            print("\nRESTORE INCOMPLETE:")
            for f in failures:
                print(f"  - {f}")
                # Also to the events file: a detached run has no one reading
                # stdout, and this is exactly the state the next roll inherits.
                session.write(f"RESTORE INCOMPLETE: {f}")
        # #2165/#2167: the verdict is the LAST thing in the narration, after
        # the restore -- the operator's eye lands at the bottom. It also
        # persists the blocking questions as the next launch's prerequisite.
        print_verdict(
            repo_root,
            requested=list(args.issue),
            rolled=rolled,
            blocked=blocked,
            stopped_at=stopped_at,
            code=code,
            since=batch_started,
        )


if __name__ == "__main__":
    sys.exit(main())

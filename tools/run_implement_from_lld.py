#!/usr/bin/env python3
"""CLI entry point for LLD Implementation Workflow (TDD).

Takes an approved LLD and implements it using Test-Driven Development:
1. Load LLD
2. Review test plan (Gemini)
3. Scaffold tests (red phase)
4. Implement code (Claude)
5. Verify tests pass (green phase)
6. E2E validation
7. Generate documentation

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization

Usage:
    # Select from approved LLDs interactively
    python tools/run_implement_from_lld.py --select

    # Full TDD workflow (auto, no human review)
    python tools/run_implement_from_lld.py --issue 42

    # Fast mode (skip E2E)
    python tools/run_implement_from_lld.py --issue 42 --skip-e2e

    # Just scaffold tests
    python tools/run_implement_from_lld.py --issue 42 --scaffold-only

    # With human review at all stages
    python tools/run_implement_from_lld.py --issue 42 --review all

    # With human review at draft stage only
    python tools/run_implement_from_lld.py --issue 42 --review draft

    # With sandbox repo for E2E
    python tools/run_implement_from_lld.py --issue 42 --sandbox-repo mcwiz/assemblyzero-e2e-sandbox

    # Cross-repo (test another project)
    python tools/run_implement_from_lld.py --issue 42 --repo /path/to/other/repo
"""

import argparse
import atexit
import os
import re
import subprocess
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Issue #120: Configure LangSmith tracing (enabled when LANGSMITH_API_KEY is set)
from assemblyzero.tracing import configure_langsmith
configure_langsmith()

# Issue #424: Telemetry instrumentation
from assemblyzero.telemetry import emit, flush, track_tool
from assemblyzero.core.stage_watchdog import StageWatchdog  # noqa: E402  (#2231)
from assemblyzero.core.llm_provider import get_cumulative_cost
from assemblyzero.utils.git import is_generated_work_branch, is_issue_work_branch
atexit.register(flush)


def get_current_branch(repo_path: Path) -> str:
    """Get the current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def _worktree_entries(repo_path: Path) -> list[tuple[Path, str]] | None:
    """`git worktree list --porcelain` as (path, branch) pairs.

    The branch is the short name, or "" for a detached or bare entry. None
    when git itself fails, so a caller cannot mistake "could not list" for
    "no such worktree".
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None

    entries: list[tuple[Path, str]] = []
    path: Path | None = None
    branch = ""
    for line in result.stdout.splitlines() + [""]:
        if line.startswith("worktree "):
            path = Path(line.split(" ", 1)[1])
            branch = ""
        elif line.startswith("branch refs/heads/"):
            branch = line[len("branch refs/heads/"):]
        elif not line and path is not None:
            entries.append((path, branch))
            path = None
    return entries


def find_existing_worktree(repo_path: Path, issue_number: int) -> Path | None:
    """Find this issue's worktree: the one named ``{Repo}-{issue}`` on branch
    ``{issue}-implementation``, both compared whole (#3513).

    A substring match on ``-{issue}`` let issue 42 resume into ``Repo-420``
    and sweep that issue's files into its own checkpoint commits -- the same
    shape as the #1756 branch match.
    """
    entries = _worktree_entries(repo_path)
    if entries is None:
        return None
    want_name = f"{repo_path.name}-{issue_number}"
    want_branch = f"{issue_number}-implementation"
    for path, branch in entries:
        if path.name == want_name and branch == want_branch:
            return path
    return None


def create_worktree(
    repo_path: Path, issue_number: int, start_point: str = "",
    detached: bool = False,
) -> tuple[Path, str]:
    """Create a git worktree for the issue.

    Args:
        repo_path: Path to the main repository.
        issue_number: Issue number.
        start_point: Optional ref to carve the work branch from (#1756
            attempt-branch model — e.g. an explicit --base-branch).
            Empty → current HEAD, i.e. the checked-out branch.
        detached: #3509: cut the worktree on a detached HEAD with no branch.
            A mock run's checkpoint commits are fake; with no branch to hold
            them, removing the worktree at the end leaves nothing behind.
            An existing directory is never reused for a detached cut.

    Returns:
        Tuple of (worktree_path, error_message).
    """
    # Derive project name from repo path
    project_name = repo_path.name

    # Worktree path: ../ProjectName-IssueNumber
    worktree_path = repo_path.parent / f"{project_name}-{issue_number}"

    # Branch name: issue-number-implementation
    branch_name = f"{issue_number}-implementation"

    if detached:
        if worktree_path.exists():
            return worktree_path, (
                f"{worktree_path} already exists. A mock run cuts a fresh "
                "detached worktree and never reuses one."
            )
        add_cmd = ["git", "worktree", "add", "--detach", str(worktree_path)]
        if start_point:
            add_cmd.append(start_point)
        result = subprocess.run(
            add_cmd, cwd=str(repo_path), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            return worktree_path, f"Failed to create worktree: {result.stderr.strip()}"
        return worktree_path, ""

    # Check if worktree already exists AND is valid
    if worktree_path.exists():
        # Verify it's actually a git worktree (has .git file)
        git_marker = worktree_path / ".git"
        if git_marker.exists():
            # #3513: the right name on the wrong branch is not this issue's
            # worktree, and reusing it would commit into another branch.
            on_branch = {
                p.resolve(): b for p, b in (_worktree_entries(repo_path) or [])
            }.get(worktree_path.resolve())
            if on_branch != branch_name:
                return worktree_path, (
                    f"{worktree_path} exists but is on branch "
                    f"{on_branch or '(none: not a worktree of this repo, or detached)'}, "
                    f"not {branch_name}. Refusing to reuse it."
                )
            return worktree_path, ""
        else:
            # #3231: the directory exists but is not a worktree. It used to be
            # rmtree'd on the strength of one missing file, unattended; the
            # ways a worktree loses its .git are the ways that leave work in
            # it. Move it aside, say where, and cut the worktree fresh.
            from datetime import datetime

            aside = worktree_path.with_name(
                f"{worktree_path.name}.bak-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
            )
            worktree_path.rename(aside)
            print(f"    [WARN] {worktree_path} was not a worktree; moved aside to {aside}")

    # Create worktree (from start_point if given, else current HEAD)
    add_cmd = ["git", "worktree", "add", str(worktree_path), "-b", branch_name]
    if start_point:
        add_cmd.append(start_point)
    result = subprocess.run(
        add_cmd,
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        # Maybe branch already exists - try without -b
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), branch_name],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return worktree_path, f"Failed to create worktree: {result.stderr.strip()}"

    # #3511: no push here. The branch used to be pushed the moment the
    # worktree existed, so a run halting at N0, N1 or N3 had already
    # published an empty branch that nothing removed. Checkpoints are local
    # by design (#2339, testing/checkpoints.py); pushing is the pr stage's
    # job, when there is work to push.
    return worktree_path, ""


#: The end state of a standalone run (#3509, #4150). Printed in --help and
#: restated by the final report, so the operator and the run agree on "done".
END_STATE = """\
End state (#3509, #4150)
------------------------
A run SUCCEEDS only when N7 finalize says so (workflow_status "completed").
Every other end is a failure, below. A run that succeeds lands its work:
  - whatever was written after the last checkpoint is committed ([CP:final])
  - untracked and ignored files in the worktree (lineage, anything the
    checkpoints exclude or .gitignore hides) are moved to
    <repo>/data/runs-kept/impl-<issue>-<HHMMSS>/, never deleted;
    caches (__pycache__, .pytest_cache, .ruff_cache, .mypy_cache, .coverage,
    .venv, node_modules) are not kept
  - the worktree and the branch <issue>-implementation are handed to the
    fleet merge driver named in AZ_MERGE_DRIVER, which pushes, opens the PR
    (Closes #<issue>), waits for its checks, merges, and removes the
    worktree and the branch. Nothing is pushed before the driver runs.
  Left: the implementation merged on the base branch, and nothing else.
  A real run refuses to start when AZ_MERGE_DRIVER is unset.
A --mock run cuts a detached worktree (no branch), pushes nothing, runs no
driver and removes the worktree: it leaves nothing at all.
A --scaffold-only run lands nothing, because its tests are red by design: it
keeps the worktree and the branch for the full run.
A run that FAILS or HALTS, or whose end state cannot be reached (a dirty
worktree, a git failure, a driver refusal), keeps its worktree and branch,
goes through the HALT node, which alerts the operator, and exits 1. After a
driver refusal, follow the driver's route for the stage it printed.
The status file is <repo>/data/speedrun/runs/.implement-status-<issue>.json.
"""

#: Ignored entries not worth keeping when a worktree is removed: regenerable
#: caches, named one by one (a closed set, #2475's "decision on record").
_CACHE_NAMES = frozenset({
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".coverage", ".venv", "node_modules",
})


def _git_out(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )


class _FinishStopped(Exception):
    """A step of the end state could not complete; the message is the line."""


def _git_checked(repo: Path, *args: str) -> str:
    """git's stdout, or _FinishStopped naming the command and its stderr.

    #4150 (ledger 0908, lines 296, 345, 353): these reads were unchecked, so a
    failed `git status` read as clean and a failed branch read as no branch.
    """
    result = _git_out(repo, *args)
    if result.returncode != 0:
        raise _FinishStopped(
            f"stopped: `git {' '.join(args)}` failed in {repo} "
            f"(exit {result.returncode}), so the worktree is kept as it is: "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def _keep_uncommitted(worktree: Path, keep_root: Path) -> list[str]:
    """Move every untracked or ignored, non-cache entry out of ``worktree``
    into ``keep_root`` at the same relative path.

    ``git worktree remove`` deletes ignored files without asking and ``git
    status`` calls the tree clean, so this is the only thing standing between
    a lineage directory and the bin. Untracked entries are the checkpoint's
    own exclusions (``.assemblyzero/``, ``data/lineage/``), which no commit
    carries. Returns one line per entry moved; a `git status` that fails is
    _FinishStopped before anything moves."""
    import shutil

    moved: list[str] = []
    listing = _git_checked(worktree, "status", "--porcelain", "--ignored")
    for line in listing.splitlines():
        if not (line.startswith("!! ") or line.startswith("?? ")):
            continue
        rel = line[3:].strip().strip('"').rstrip("/")
        if not rel or set(Path(rel).parts) & _CACHE_NAMES:
            continue
        src = worktree / rel
        if not src.exists():
            continue
        dest = keep_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        moved.append(f"kept: {rel} -> {dest}")
    return moved


def landing_preflight(args) -> str | None:
    """Why this run could not land its result, or None (#4150).

    A real run that will finish a worktree lands it through the merge driver
    named in ``AZ_MERGE_DRIVER``; without it the run would spend its model
    calls and end with a branch nothing can land. A dry run, a mock run, a
    scaffold-only run and a --no-worktree run land nothing and are not asked.
    """
    if args.dry_run or args.mock or args.scaffold_only or args.no_worktree:
        return None
    from assemblyzero.core import merge_driver

    return merge_driver.check_configured()


def _run_completed(values: dict, scaffold_only: bool) -> bool:
    """Whether the final state proves the run did what it was asked (#4150).

    N7 finalize alone sets ``workflow_status`` to "completed" (#2677). A
    scaffold-only run stops after N2 by design, so its proof is the scaffold.
    """
    if values.get("workflow_status") == "completed":
        return True
    return scaffold_only and bool(values.get("test_files"))


def halt_unfinished_run(values: dict, reason: str) -> dict:
    """Send a run that ended without its end state through the testing HALT
    node (#4150, ADR 0236): it saves the state and a recovery plan, and it
    alerts the operator with ``reason`` as the cause."""
    from assemblyzero.core.halt_node import create_halt_node

    return create_halt_node("testing")({**values, "error_message": reason})


def impl_pr_title(issue_number: int) -> str:
    """The implementation PR's title; the driver requires the directive in it."""
    return f"feat: implement #{issue_number} from its approved LLD (Closes #{issue_number})"


def impl_pr_body(issue_number: int, summary: str = "") -> str:
    """The implementation PR's body: the directive on its own line, first,
    because pr-sentinel reads the body and the driver checks it too."""
    body = (
        f"Closes #{issue_number}\n\n"
        f"Implementation of issue #{issue_number}, written by AssemblyZero's "
        "implementation workflow (`tools/run_implement_from_lld.py`) from the "
        "issue's approved LLD, and landed by the fleet merge driver.\n"
    )
    return body + (f"\n{summary.strip()}\n" if summary.strip() else "")


def finish_standalone_run(
    original_repo_root: Path, worktree_path: Path, issue_number: int,
    base_branch: str, mock: bool, *, scaffold_only: bool = False,
    pr_summary: str = "",
) -> tuple[bool, list[str]]:
    """Bring a SUCCESSFUL standalone run to END_STATE (#3509, #4150).

    N9 cleans up only when ``pr_url`` is set, and nothing standalone sets it,
    so every standalone run used to end with its worktree, branch and lineage
    in place and a "Next steps" that asked the operator to commit by hand.

    #4150: a real run then pushed its branch and printed a `gh pr create`
    that this machine's gh wrapper refuses to every process but the merge
    driver. It now hands the worktree and the branch to `merge_driver.land`,
    which pushes, opens the PR, merges and removes both; nothing here pushes.

    Returns ``(finished, lines)``: whether the end state was reached, and one
    line per step taken or refused. Never raises for a git or driver refusal;
    the refusal is the line, and the caller halts on ``finished`` False.
    """
    lines: list[str] = []
    try:
        _finish(
            Path(original_repo_root), Path(worktree_path), issue_number,
            base_branch, mock, scaffold_only, pr_summary, lines,
        )
    except _FinishStopped as stop:
        lines.append(str(stop))
        return False, lines
    return True, lines


def _finish(
    repo: Path, wt: Path, issue_number: int, base_branch: str, mock: bool,
    scaffold_only: bool, pr_summary: str, lines: list[str],
) -> None:
    from datetime import datetime

    from assemblyzero.core import merge_driver
    from assemblyzero.workflows.orchestrator.stages import impl_pr_body_path
    from assemblyzero.workflows.testing.checkpoints import (
        EXCLUDED_PATHS,
        commit_checkpoint,
    )

    # What the nodes after the last checkpoint wrote (N6-N8: e2e, docs,
    # reports) is committed first, so the branch carries the whole result.
    if commit_checkpoint(wt, issue_number, "final"):
        lines.append("committed: [CP:final], the work written after the last checkpoint")

    # #4150: the checkpoint commits everything but its own exclusions, and
    # reports a failed commit only on stdout (#3810). Anything else still
    # untracked or modified is work it did not take; moving that aside as
    # "kept" would land the branch without it. Ignored files are not listed
    # here and are kept below.
    missed = []
    for entry in _git_checked(wt, "status", "--porcelain").splitlines():
        rel = entry[3:].strip().strip('"').rstrip("/")
        if not any(rel == p or rel.startswith(p + "/") for p in EXCLUDED_PATHS):
            missed.append(entry)
    if missed:
        raise _FinishStopped(
            f"stopped: the final checkpoint did not commit everything in {wt}, "
            "so it is kept as it is:\n"
            + "\n".join(f"    {ln}" for ln in missed[:20])
        )

    if scaffold_only and not mock:
        # The suite is red by design: landing it would put failing tests on
        # the base branch. The full run resumes from this worktree.
        lines.append(
            f"kept: {wt} and its branch, for the full run (--scaffold-only "
            "lands nothing: its tests are red by design)"
        )
        return

    keep_root = repo / "data" / "runs-kept" / (
        f"impl-{issue_number}-{datetime.now().strftime('%H%M%S')}"
    )
    lines += _keep_uncommitted(wt, keep_root)

    if mock:
        removed = _git_out(repo, "worktree", "remove", str(wt))
        if removed.returncode != 0:
            raise _FinishStopped(
                f"stopped: `git worktree remove {wt}` refused: {removed.stderr.strip()}"
            )
        lines.append(f"removed worktree: {wt}")
        return

    branch = _git_checked(wt, "branch", "--show-current").strip()
    if not branch:
        raise _FinishStopped(
            f"stopped: {wt} is on no branch (a detached HEAD), so there is "
            "nothing for the merge driver to land; the worktree is kept"
        )

    body_file = impl_pr_body_path(repo, issue_number)
    body_file.parent.mkdir(parents=True, exist_ok=True)
    body_file.write_text(impl_pr_body(issue_number, pr_summary), encoding="utf-8")
    try:
        landing = merge_driver.land(
            worktree=wt, branch=branch, title=impl_pr_title(issue_number),
            body_file=body_file, issue=issue_number, base=base_branch or None,
        )
    except merge_driver.MergeDriverError as exc:
        raise _FinishStopped(
            f"stopped: {exc}\n    The worktree {wt} and the branch {branch} are "
            "kept. Follow the merge driver's route for the stage it printed."
        ) from exc
    lines.append(
        f"landed: PR #{landing.pr_number}, squash {landing.squash_sha}, on "
        f"{base_branch or 'the base branch'}; the driver removed {wt} and {branch}"
    )


def _checkpoint_db_name(issue_number: int) -> str:
    return f"testing_{issue_number}.db" if issue_number > 0 else "testing_workflow.db"


def get_checkpoint_db_path(issue_number: int, target_repo: Path) -> Path:
    """Get path to SQLite checkpoint database.

    Priority:
    1. ASSEMBLYZERO_WORKFLOW_DB environment variable (explicit override)
    2. ``<target_repo>/data/speedrun/checkpoints/testing_{issue_number}.db``
       (``testing_workflow.db`` when issue_number is 0)

    Issue #379 partitioned the database by issue to prevent concurrent
    deadlocks. #3548 keys it by the target repository too: at
    ``~/.assemblyzero/testing_{issue}.db`` two repositories that each had an
    issue 42 shared one database, and a ``--resume`` in one could load the
    other's checkpoints. Same reasoning as #1970 for the LLD approval cache:
    state that belongs to a repository lives in that repository's gitignored
    ``data/``, where no other repository can reach it.

    Args:
        issue_number: GitHub issue number for per-issue partitioning.
        target_repo: The repository the run works against (the checkout,
            not a worktree the run may remove).

    Returns:
        Path to checkpoint database.
    """
    if db_path_env := os.environ.get("ASSEMBLYZERO_WORKFLOW_DB"):
        db_path = Path(db_path_env)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    db_dir = Path(target_repo) / "data" / "speedrun" / "checkpoints"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / _checkpoint_db_name(issue_number)


def legacy_checkpoint_db_path(issue_number: int) -> Path:
    """Where a real run's database lived before #3548.

    ``~/.assemblyzero/testing_{issue}.db``, keyed by the issue alone. Never
    read by default any more; named so the operator can hand it to
    ``--db-path`` when a run that started before #3548 is to be resumed.
    """
    return Path.home() / ".assemblyzero" / _checkpoint_db_name(issue_number)


def legacy_checkpoint_notice(
    issue_number: int, db_path_arg: str | None, mock: bool,
) -> str | None:
    """The line a real run prints when the pre-#3548 database exists.

    #3548's third requirement: an existing ``~/.assemblyzero/testing_{issue}.db``
    is not silently read for a different repository. It is named and
    ignored, with the flag that would use it. ``None`` when there is nothing
    to say: no such file, or the run chose its database (``--db-path``), or
    the run is a mock and never read that location (#3547).
    """
    if db_path_arg or mock:
        return None
    legacy = legacy_checkpoint_db_path(issue_number)
    if not legacy.exists():
        return None
    return (
        f"[implement] Ignoring {legacy}: keyed by the issue alone, it may hold "
        f"another repository's checkpoints (#3548). To resume from it, pass "
        f"--db-path {legacy}"
    )


def checkpoint_db_for_run(
    db_path_arg: str | None, issue_number: int, mock: bool, target_repo: Path,
) -> Path:
    """The checkpoint database this run uses (#3547, #3548).

    ``--db-path`` wins. A ``--mock`` run keeps its database under the
    target's gitignored ``data/mock-runs/``: it used to land at
    ``~/.assemblyzero/testing_{issue}.db`` like a real run's, outside the
    repository it rehearsed against, where a later REAL ``--resume`` for the
    same issue number would read the mock's checkpoints. A real run's is
    under the target's ``data/speedrun/checkpoints/`` (#3548).
    """
    if db_path_arg:
        return Path(db_path_arg)
    if mock:
        return Path(target_repo) / "data" / "mock-runs" / f"impl-{issue_number}" / "checkpoints.db"
    return get_checkpoint_db_path(issue_number, target_repo)


def select_approved_lld(repo_root: Path) -> int | None:
    """Interactively select from approved LLDs in docs/lld/active/.

    Scans for LLD-NNN.md files, extracts issue number, title, and
    approval status from each file.

    Args:
        repo_root: Path to repository root.

    Returns:
        Selected issue number, or None if cancelled/no LLDs found.
    """
    lld_dir = repo_root / "docs" / "lld" / "active"
    if not lld_dir.exists():
        print(f"No LLD directory found: {lld_dir}")
        return None

    # Scan for LLD files
    lld_files = sorted(lld_dir.glob("LLD-*.md"))
    if not lld_files:
        print("No LLD files found in docs/lld/active/")
        return None

    entries = []
    for lld_path in lld_files:
        # Extract issue number from filename (LLD-NNN.md)
        match = re.match(r"LLD-(\d+)\.md", lld_path.name)
        if not match:
            continue
        issue_num = int(match.group(1))

        # Read first line for title, scan for approval status
        content = lld_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        title = ""
        approved = False
        approval_date = ""

        # Title from first heading
        for line in lines[:5]:
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                # Strip issue number prefix if present (e.g., "305 - Feature: ...")
                title = re.sub(r"^\d+\s*[-–—]\s*", "", title)
                break

        # Check for APPROVED in review log
        for line in lines:
            if "APPROVED" in line and "|" in line:
                approved = True
                # Try to extract date from table row
                cells = [c.strip() for c in line.split("|")]
                for cell in cells:
                    if re.match(r"\d{4}-\d{2}-\d{2}", cell):
                        approval_date = cell
                        break
                break

        entries.append({
            "issue": issue_num,
            "title": title[:60],
            "approved": approved,
            "date": approval_date,
            "path": lld_path,
        })

    if not entries:
        print("No valid LLD files found.")
        return None

    # Display menu
    print()
    print("=" * 70)
    print("Approved LLDs ready for implementation")
    print("=" * 70)

    for i, entry in enumerate(entries, 1):
        status = "APPROVED" if entry["approved"] else "pending"
        date_str = f" ({entry['date']})" if entry["date"] else ""
        print(f"  [{i:2d}] #{entry['issue']:>4d}: {entry['title']}")
        print(f"        Status: {status}{date_str}")

    print()
    print("  [ 0] Cancel")
    print()

    # Prompt for selection
    try:
        choice = input(f"Select LLD [0-{len(entries)}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return None

    try:
        idx = int(choice)
    except ValueError:
        print("Invalid selection.")
        return None

    if idx == 0:
        print("Cancelled.")
        return None

    if idx < 1 or idx > len(entries):
        print(f"Invalid selection. Choose 1-{len(entries)} or 0 to cancel.")
        return None

    selected = entries[idx - 1]
    print(f"\nSelected: #{selected['issue']} - {selected['title']}")
    return selected["issue"]


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser for the CLI.

    Separated from main() to enable testing.
    """
    parser = argparse.ArgumentParser(
        description="Run TDD Testing Workflow on an issue with an approved LLD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"{__doc__}\n{END_STATE}",
    )

    # Issue selection (mutually exclusive)
    issue_group = parser.add_mutually_exclusive_group(required=True)
    issue_group.add_argument(
        "--issue",
        type=int,
        help="GitHub issue number (must have approved LLD)",
    )
    issue_group.add_argument(
        "--select",
        action="store_true",
        help="Interactively select from approved LLDs in docs/lld/active/",
    )

    # Optional arguments
    parser.add_argument(
        "--repo",
        type=str,
        help="Target repository path (default: current repo)",
    )
    # #2570: a resume verifies the halt's contract first and refuses by
    # name when the world changed. Explicit, logged override only.
    parser.add_argument(
        "--accept-changed-inputs",
        action="store_true",
        help=(
            "Proceed even when inputs changed since the last halt's resume "
            "contract (#2570). The acceptance is printed, never silent."
        ),
    )
    parser.add_argument(
        "--lld",
        type=str,
        help="Path to LLD file (default: auto-detect from issue number)",
    )
    parser.add_argument(
        "--review",
        choices=["none", "draft", "verdict", "all"],
        default=None,
        dest="review",
        help="Human review stages: none (default) | draft | verdict | all",
    )
    parser.add_argument(
        "--gates",
        default=None,
        dest="gates_deprecated",
        help=argparse.SUPPRESS,  # Hidden deprecated alias for --review
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help=argparse.SUPPRESS,  # Hidden deprecated alias
    )
    # Issue #773: API policy
    parser.add_argument(
        "--allow-api",
        action="store_true",
        dest="allow_api",
        help="Allow paid Anthropic API calls (default: blocked, uses claude -p via Max subscription)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Mock mode - use fixtures instead of real APIs",
    )
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Skip E2E validation (fast mode)",
    )
    parser.add_argument(
        "--scaffold-only",
        action="store_true",
        help="Stop after scaffolding tests",
    )
    parser.add_argument(
        "--sandbox-repo",
        type=str,
        help="Sandbox repository for E2E tests",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum implementation iterations (default: 3)",
    )
    parser.add_argument(
        "--coverage-target",
        type=int,
        help="Coverage target percentage (default: from LLD or 90)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint",
    )
    parser.add_argument(
        "--no-worktree",
        action="store_true",
        help="Skip worktree creation (use current directory)",
    )
    parser.add_argument(
        "--base-branch",
        type=str,
        default="",
        dest="base_branch",
        help=(
            "Integration branch the implementation targets (#1756 "
            "attempt-branch model). Default: the branch the target repo "
            "is checked out on. The worktree branch is carved from it "
            "and the PR advice targets it."
        ),
    )
    parser.add_argument(
        "--db-path",
        type=str,
        help="Path to checkpoint database (overrides default per-issue partitioning)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview execution plan without API calls or file modifications",
    )
    parser.add_argument(
        "--context",
        action="append",
        default=[],
        help="Additional context files to inject into prompts (can be repeated)",
    )
    parser.add_argument(
        "--issue-only",
        action="store_true",
        help="Use issue body as spec (skip LLD/spec file search). For small changes.",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=3.0,
        help="Max API cost in USD before halting (default $3.00, 0=unlimited)",
    )
    parser.add_argument(
        "--token-budget",
        type=int,
        default=0,
        help="Max estimated tokens before circuit breaker trips (0 = unlimited)",
    )

    # Issue #773: Reviewer LLM configuration. #3563: every seat's model,
    # the coder's included (#3553, the operator's 2026-09-24 ruling), comes
    # from the run's model profile (--models; default gemini.toml). --reviewer
    # overrides the test-plan reviewer and, as before (#1072), the revisor;
    # --seat is the general form (e.g. --seat impl.code=claude:sonnet).
    from assemblyzero.core.seats import add_profile_arguments

    add_profile_arguments(parser)
    parser.add_argument(
        "--reviewer",
        default=None,
        help=(
            "Override the impl.test_plan.review and impl.test_plan.revise "
            "seats. Default: the profile's"
        ),
    )
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "max"],
        default=None,
        help="Effort for every seat, over the profile's (default: the profile's, max)",
    )

    # Issue #1071: Retry policy for transient LLM failures.
    parser.add_argument(
        "--retry-policy",
        choices=["default", "aggressive", "none"],
        default="default",
        help=(
            "Retry policy for transient LLM API failures (5xx, 429, "
            "timeouts). 'default': 5 retries, 2s→32s exponential "
            "backoff. 'aggressive': 8 retries, 60s cap. 'none': no "
            "retry (pre-#1071 fail-fast behavior). Server-provided "
            "Retry-After headers are honored regardless of policy. "
            "(#1071)"
        ),
    )

    # Issue #1076: Speed-run instrumentation (lap splits + run log)
    parser.add_argument(
        "--speedrun",
        action="store_true",
        default=False,
        help=(
            "Emit speed-run lap-splits to data/speedrun/{issue}-{attempt}.json "
            "and append one run-log entry to data/speedrun/run-log.jsonl on "
            "completion. For the boostgauge YouTube demo. (#1076)"
        ),
    )

    # Issue #1072: Test-plan policy on BLOCKED at N1.
    parser.add_argument(
        "--test-plan-policy",
        choices=["revise", "auto", "strict"],
        default="revise",
        help=(
            "Behavior when N1 returns BLOCKED on the test plan. "
            "'revise' (default): up to 2 revision cycles, then END. "
            "'auto': continue to scaffold despite BLOCKED (legacy "
            "auto_mode bypass). 'strict': END immediately on BLOCKED "
            "(pre-#1072 behavior). The legacy auto_mode setting still "
            "forces the auto path regardless of this flag. (#1072)"
        ),
    )

    # Issue #517: Global workflow timeout
    from assemblyzero.utils.workflow_timeout import add_timeout_argument
    add_timeout_argument(parser)

    return parser


def apply_review_config(args: argparse.Namespace) -> None:
    """Apply review configuration to args, handling deprecated flags.

    Args:
        args: Parsed arguments namespace. Modified in place.
    """
    # Handle deprecated --gates flag
    if args.gates_deprecated is not None:
        print(
            "WARNING: --gates is deprecated. Use --review instead.",
            file=sys.stderr,
        )
        gates_val = args.gates_deprecated.lower().strip()
        if gates_val in ("draft,verdict", "verdict,draft", "both"):
            args.review = "all"
        else:
            args.review = gates_val

    # Handle deprecated --auto flag
    if args.auto:
        print(
            "WARNING: --auto is deprecated. Use --review none instead.",
            file=sys.stderr,
        )
        if args.review is None:
            args.review = "none"

    # Apply default if --review not specified
    if args.review is None:
        args.review = "none"

    # Set individual gate flags based on --review value
    if args.review == "none":
        args.gates_draft = False
        args.gates_verdict = False
        args.auto_mode = True
    elif args.review == "draft":
        args.gates_draft = True
        args.gates_verdict = False
        args.auto_mode = False
    elif args.review == "verdict":
        args.gates_draft = False
        args.gates_verdict = True
        args.auto_mode = False
    else:  # "all"
        args.gates_draft = True
        args.gates_verdict = True
        args.auto_mode = False


def _write_status_file(
    repo_root: Path,
    issue_number: int,
    status: str,
    error: str = "",
    state: dict | None = None,
    out_dir: Path | None = None,
) -> None:
    """Write a discoverable status file.

    Issue #380: When SQLite checkpointing fails, this file is still
    discoverable so agents can detect success/failure independently.

    #3509: it goes into the checkout's gitignored run-record directory
    (``out_dir``), beside the run's log. It used to be written to the root of
    whichever tree the run was in -- usually the worktree, which the run now
    removes, and otherwise the checkout, as an untracked file.

    Args:
        repo_root: Repository root path (the tree the run worked in).
        issue_number: GitHub issue number.
        status: "SUCCESS" or "FAILED".
        error: Error message if failed.
        state: Final workflow state dict for enrichment.
        out_dir: Where the file goes; the repo root when not given.
    """
    import json
    from datetime import datetime, timezone

    target_dir = Path(out_dir) if out_dir else Path(repo_root)
    status_file = target_dir / f".implement-status-{issue_number}.json"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        status_data = {
            "issue": issue_number,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repo": str(repo_root),
        }
        if error:
            status_data["error"] = error

        if state:
            status_data["iterations"] = state.get("iteration_count", 0)
            status_data["max_iterations"] = state.get("max_iterations", 3)
            status_data["coverage_achieved"] = state.get("coverage_achieved", 0)
            status_data["coverage_target"] = state.get("coverage_target", 90)
            status_data["previous_coverage"] = state.get("previous_coverage", 0)
            status_data["test_files"] = state.get("test_files", [])
            status_data["implementation_files"] = state.get("implementation_files", [])
            # #2926: the adversarial review, or why it did not run.
            from assemblyzero.workflows.testing.nodes.adversarial_node import (
                adversarial_summary,
            )

            status_data["adversarial"] = {
                "verdict": state.get("adversarial_verdict"),
                "test_count": state.get("adversarial_test_count", 0),
                "skipped_reason": state.get("adversarial_skipped_reason"),
                "summary": adversarial_summary(state),
            }

            if state.get("estimated_tokens_used"):
                status_data["tokens_used"] = state["estimated_tokens_used"]
                status_data["token_budget"] = state.get("token_budget", 0)

            # Event timeline from audit trail
            audit_file = Path(repo_root) / "docs/lineage/workflow-audit.jsonl"
            if audit_file.exists():
                events = []
                for line in audit_file.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("issue_number") == issue_number:
                        events.append({
                            "time": entry["timestamp"],
                            "event": entry["event"],
                            "details": entry.get("details", {}),
                        })
                status_data["events"] = events

        status_file.write_text(json.dumps(status_data, indent=2), encoding="utf-8")
        print(f"[implement] Status file: {status_file}")
    except OSError:
        pass  # Non-fatal — best-effort status file


def main():
    parser = create_argument_parser()
    args = parser.parse_args()

    # Issue #773: Set API policy before any providers are created
    from assemblyzero.core.llm_provider import set_api_policy
    set_api_policy(args.allow_api)

    # Apply review configuration
    apply_review_config(args)

    # Set environment variables for mode flags
    if args.auto_mode:
        os.environ["ASSEMBLYZERO_AUTO_MODE"] = "1"

    # Import after setting up path
    from langgraph.checkpoint.sqlite import SqliteSaver

    from assemblyzero.workflows.testing import TestingWorkflowState, build_testing_workflow
    from assemblyzero.workflows.testing.audit import get_repo_root

    # Determine repo root (needed before --select)
    if args.repo:
        repo_root = Path(args.repo).resolve()
        if not repo_root.exists():
            print(f"Error: Repository path does not exist: {repo_root}")
            sys.exit(1)
    else:
        try:
            repo_root = get_repo_root()
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)

    # Handle --select: interactive LLD selection
    if args.select:
        selected = select_approved_lld(repo_root)
        if selected is None:
            sys.exit(0)
        args.issue = selected

    # Validate issue number
    if args.issue is None or args.issue <= 0:
        print("Error: --issue must be a positive integer")
        sys.exit(1)

    # #4150: a real run lands through the fleet merge driver. Refuse here,
    # before the resume contract is consumed, a worktree is cut or a model is
    # called, as the LLD workflow does since #3704.
    # ADR 0236 property 4 for failures this tool owns rather than a graph
    # node: through the module attribute, which the test tiers' recorder replaces.
    from assemblyzero.core import alert

    reason = landing_preflight(args)
    if reason:
        print(f"[implement] ERROR: {reason}", file=sys.stderr)
        alert.alert_operator(
            what="the implementation run refused to start",
            where="tools/run_implement_from_lld.py main, preflight", cause=reason,
            consequence="nothing ran: no worktree was cut and no model was called",
            repo=str(repo_root), issue=args.issue,
        )
        sys.exit(1)

    # #2570: a resume finds the world the halt described, or refuses by
    # name -- before the worktree is touched and any token is spent. A
    # fresh run has no contract and passes silently.
    from assemblyzero.core.resume_contract import check_and_consume

    # #3508: a dry run consumes nothing either; a verified contract is deleted
    # on the way through, and a dry run must leave the halt's record for the
    # real resume that follows it.
    if not args.dry_run and not check_and_consume(
        "testing", args.issue,
        accept_changed=args.accept_changed_inputs,
    ):
        sys.exit(1)

    # Track original repo for worktree cleanup later
    original_repo_root = repo_root
    worktree_path = None

    # Issue #290 / #3508: the dry run exits BEFORE the worktree is cut and
    # the branch pushed. It used to sit after both, so `--dry-run` created a
    # sibling directory, cut a branch, pushed it, and then printed "no files
    # modified". It reports the plan and touches nothing; a test cuts a
    # throwaway repo with a bare origin and shows the worktree list, the
    # branch list and the origin's refs unchanged afterwards.
    if args.dry_run:
        db_path = checkpoint_db_for_run(args.db_path, args.issue, bool(args.mock), repo_root)
        lld_path = repo_root / "docs" / "lld" / "active" / f"LLD-{args.issue:03d}.md"
        print()
        print("[implement] AssemblyZero TDD Testing Workflow")
        print("[implement] Mode: DRY RUN")
        print()
        print("[DRY RUN] Would execute:")
        print("  N0_load_lld -> N1_review_test_plan -> N2_scaffold_tests -> N3_verify_red")
        print("  -> N4_implement_code -> N5_verify_green -> N6_e2e_validation -> N7_finalize")
        print()
        print(f"  Repository: {repo_root}")
        if args.no_worktree:
            print("  Worktree: none (--no-worktree), the run would work in place")
        else:
            current = get_current_branch(repo_root)
            base = args.base_branch or current or "(unreadable)"
            print(
                f"  Worktree would be cut at: {repo_root.parent / f'{repo_root.name}-{args.issue}'}"
            )
            if args.mock:
                print(f"  Branch would be: none (--mock cuts a detached worktree from {base})")
            else:
                print(
                    f"  Branch would be: {args.issue}-implementation from {base}, local "
                    "until the run succeeds; then landed by the merge driver named in "
                    "AZ_MERGE_DRIVER (End state, --help)"
                )
        print(f"  LLD: {lld_path} ({'found' if lld_path.exists() else 'NOT FOUND'})")
        print(f"  Database: {db_path}")
        print(f"  Mock mode: {args.mock}")
        print(f"  Skip E2E: {args.skip_e2e}")
        print(f"  Max iterations: {args.max_iterations}")
        print()
        print("[DRY RUN] Nothing was created, pushed or modified.")
        return 0

    # Handle worktree creation/detection (#1756 attempt-branch model:
    # ANY named integration branch — main or e.g. speedrun-attempt-N —
    # is a valid base; the worktree branch is carved from it and PRs
    # target it. Never assume main.)
    base_branch = args.base_branch
    if not args.no_worktree:
        current_branch = get_current_branch(repo_root)

        if is_issue_work_branch(current_branch, args.issue):
            # Already on THIS issue's work branch - likely in its worktree.
            # Exact match only: the old substring test let issue #1
            # false-match `speedrun-attempt-1` and run in-place with
            # checkpoints as no-ops (#1756).
            print(f"Already on issue branch: {current_branch}")
        elif is_generated_work_branch(current_branch):
            print(
                f"ERROR: On '{current_branch}' — a generated work branch "
                "for a different issue."
            )
            print(
                "       Check out your integration branch (e.g. main or "
                "speedrun-attempt-N) and re-run."
            )
            sys.exit(1)
        elif not current_branch or current_branch == "HEAD":
            print("ERROR: Detached HEAD (or unreadable branch) in the target repo.")
            print(
                "       Check out your integration branch (e.g. main or "
                "speedrun-attempt-N) and re-run."
            )
            sys.exit(1)
        else:
            # Named integration branch: carve the issue worktree from it.
            base_branch = args.base_branch or current_branch
            # #3509: a mock run never resumes into a real worktree; it cuts a
            # fresh detached one below.
            existing = None if args.mock else find_existing_worktree(repo_root, args.issue)

            if existing and existing.exists():
                print(f"Found existing worktree: {existing}")
                repo_root = existing
                worktree_path = existing
            else:
                print(
                    f"Creating worktree for issue #{args.issue} "
                    f"(base: {base_branch})..."
                )
                worktree_path, error = create_worktree(
                    repo_root, args.issue, start_point=args.base_branch,
                    detached=bool(args.mock),
                )
                if error:
                    print(f"Error: {error}")
                    sys.exit(1)
                print(f"Created worktree: {worktree_path}")
                repo_root = worktree_path

    # Set up checkpoint database (Issue #379: per-issue partitioning; #3547:
    # a mock run's lives under the target's data/mock-runs/; #3548: a real
    # run's under the target's data/speedrun/checkpoints/)
    db_path = checkpoint_db_for_run(
        args.db_path, args.issue, bool(args.mock), original_repo_root,
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_notice = legacy_checkpoint_notice(args.issue, args.db_path, bool(args.mock))
    if legacy_notice:
        print(legacy_notice)

    # Startup banner (Issue #380: visible diagnostics for cross-repo debugging)
    print()
    print("[implement] AssemblyZero TDD Testing Workflow")
    print("[implement] ============================")
    print(f"[implement] Issue: #{args.issue}")
    print(f"[implement] Repository: {repo_root}")
    if worktree_path:
        print(f"[implement] Worktree: {worktree_path}")
    print(f"[implement] Database: {db_path}")
    print(f"[implement] Mode: {'auto' if args.auto_mode else 'interactive'}")
    if args.skip_e2e:
        print("[implement] E2E: skipped")
    if args.scaffold_only:
        print("[implement] Mode: scaffold-only")
    if args.issue_only:
        print("[implement] Mode: issue-only (no LLD)")
    if args.dry_run:
        print("[implement] Mode: DRY RUN")
    if args.token_budget > 0:
        print(f"[implement] Token budget: {args.token_budget:,}")
    if args.timeout > 0:
        print(f"[implement] Timeout: {args.timeout} minutes")
    print()

    # #3503: from here on the run leaves a record in the CHECKOUT's
    # data/speedrun/runs/ (not the worktree's, which the run may remove):
    # the tag and log path first, node transitions as the graph streams,
    # a crash record if it dies, and what it left in place at the end.
    from assemblyzero.core.run_record import RunRecord
    record = RunRecord.start("impl", original_repo_root, args.issue)
    # #3509: the status file sits beside the run's log, in the checkout's
    # gitignored data/, not at the root of a worktree the run removes.
    runs_dir = Path(original_repo_root) / "data" / "speedrun" / "runs"

    # Issue #288/#289: Load and validate context files
    context_content = ""
    if args.context:
        from assemblyzero.workflows.testing.path_validator import load_context_files

        print(f"[implement] Loading {len(args.context)} context file(s)...")
        context_content, context_errors = load_context_files(args.context, repo_root)
        for err in context_errors:
            print(f"[implement] {err}")
        if context_errors and not context_content:
            print("[implement] ERROR: All context files failed validation")
            record.finish("fail", "all context files failed validation")
            sys.exit(1)
        if context_content:
            print(f"[implement] Context loaded: {len(context_content):,} chars")

    # #3563: the run's model profile, snapshotted into state; a --resume
    # reads the checkpoint's snapshot instead (LangGraph restores it).
    from assemblyzero.core.seats import describe, profile_from_args, seat_in

    try:
        profile = profile_from_args(
            args, original_repo_root,
            {"reviewer": ("impl.test_plan.review", "impl.test_plan.revise")},
        )
    except ValueError as e:
        print(f"[implement] ERROR: model profile: {e}")
        record.finish("fail", f"model profile: {e}")
        sys.exit(1)
    print(describe(profile))
    # #3565: the run record opens with the profile; seats no state reaches
    # (triage, visual gate, contract fidelity) follow it.
    from assemblyzero.core.model_record import announce_profile

    announce_profile(profile)
    review_seat = seat_in(profile, "impl.test_plan.review")

    # Build initial state
    initial_state: TestingWorkflowState = {
        "issue_number": args.issue,
        "repo_root": str(repo_root),
        "model_profile": profile,
        "config_reviewer": review_seat.spec,  # Issue #773 (legacy, one release)
        "config_effort": review_seat.effort or "",  # Issue #773 (legacy)
        "config_retry_policy": args.retry_policy,  # Issue #1071
        "config_drafter": seat_in(profile, "impl.test_plan.revise").spec,  # Issue #1072 (legacy)
        "test_plan_policy": args.test_plan_policy,  # Issue #1072
        "test_plan_revision_count": 0,  # Issue #1072
        "auto_mode": args.auto_mode,
        "mock_mode": args.mock,
        "skip_e2e": args.skip_e2e,
        "scaffold_only": args.scaffold_only,
        "max_iterations": args.max_iterations,
        "context_files": args.context or [],
        "context_content": context_content,
        "issue_only": args.issue_only,
        "token_budget": args.token_budget,
        "estimated_tokens_used": 0,
        "cost_budget_usd": args.budget,
    }

    # Track worktree for later reference (cleanup, PR creation)
    if worktree_path:
        initial_state["worktree_path"] = str(worktree_path)
        initial_state["original_repo_root"] = str(original_repo_root)

    if args.lld:
        initial_state["lld_path"] = args.lld

    if args.coverage_target:
        initial_state["coverage_target"] = args.coverage_target

    if args.sandbox_repo:
        initial_state["sandbox_repo"] = args.sandbox_repo

    # Build workflow
    try:
        workflow = build_testing_workflow()
    except Exception as e:
        record.crash(e)
        record.finish("halt", str(e))
        raise

    # Run with checkpointing
    thread_id = f"{args.issue}-testing"

    # Clear stale checkpoint DB on fresh runs (Issue #470)
    if not args.resume:
        if db_path.exists():
            db_path.unlink()
            print(f"[implement] Cleared stale checkpoint DB: {db_path}")

    # Issue #517: Global workflow timeout
    from assemblyzero.utils.workflow_timeout import WorkflowTimeout

    # Issue #1076: Speed-run instrumentation. Set up lap-split writer +
    # run-logger if --speedrun was passed; both are no-ops otherwise.
    speedrun_splits = None
    speedrun_logger = None
    if getattr(args, "speedrun", False):
        from assemblyzero.utils.speedrun import (
            LapSplitWriter, RunLogger,
        )
        speedrun_splits = LapSplitWriter.start(repo_root, args.issue)
        speedrun_logger = RunLogger(repo_root)
        speedrun_splits.beat("workflow_started")
        print(
            f"[speedrun] Lap splits: {speedrun_splits.output_path} "
            f"(attempt {speedrun_splits.attempt})"
        )

    def _finalize_speedrun(outcome: str, state: dict | None = None,
                          error_msg: str = "", notes: str = "") -> None:
        """Write terminal beat + run-log entry. Safe to call multiple times."""
        nonlocal speedrun_splits, speedrun_logger
        if speedrun_splits is None or speedrun_logger is None:
            return
        from assemblyzero.utils.speedrun import classify_halt as _classify
        import time as _time
        failure_mode = None
        if outcome != "success":
            failure_mode = _classify(state or {}, error_msg)
        speedrun_splits.finalize(outcome, failure_mode)
        speedrun_logger.complete_run(
            issue=speedrun_splits.issue,
            attempt=speedrun_splits.attempt,
            started_at_iso=speedrun_splits.started_at_iso,
            outcome=outcome,
            total_seconds=_time.time() - speedrun_splits.started_at,
            failure_mode=failure_mode,
            notes=notes,
        )
        # Set to None so subsequent calls in the same run are no-ops.
        speedrun_splits = None
        speedrun_logger = None

    def _run_failed(reason: str, values: dict) -> int:
        """The record a failed run leaves (#3509): status file, speedrun
        split, run record, and what it kept for --resume. The alert has
        already gone, from HALT or from the caller (#4150)."""
        print(f"Status: {reason}")
        # Issue #646: Emit per-issue cost even on failure
        total_cost = get_cumulative_cost()
        if total_cost > 0:
            print(f"Cost:   ${total_cost:.4f}")
            emit(
                "workflow.cost",
                repo="AssemblyZero",
                metadata={
                    "workflow_type": "implementation",
                    "issue_number": args.issue,
                    "total_cost_usd": round(total_cost, 6),
                    "status": "failed",
                },
            )
        _write_status_file(
            repo_root, args.issue, "FAILED", reason, state=values,
            out_dir=runs_dir,
        )
        _finalize_speedrun("fail", state=values, error_msg=reason)
        if worktree_path:
            # #3509: a failed run keeps its worktree and branch for --resume;
            # the report lists both and prints the commands that remove them.
            print(
                f"[implement] Kept for --resume: {worktree_path} "
                f"(see 'left in place' below)"
            )
        print(f"[implement] Checkpoint database (resume state): {db_path}")
        record.finish("fail", reason)
        return 1

    try:
      # #2231: under a watchdog, so a stalled model call is visible WHILE it
      # stalls. Streaming prints a line per node, but a single node can run for
      # many minutes -- the case #1886 was built for, and the one an operator
      # misreads as a hang. This is one of the two entry points the babysit
      # protocol tells an operator to run, which makes it the surface where
      # silence is most costly.
      with WorkflowTimeout(minutes=args.timeout), StageWatchdog("impl"):
        with SqliteSaver.from_conn_string(str(db_path)) as memory:
            app = workflow.compile(checkpointer=memory)

            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 50,
            }

            # Check for resume
            if args.resume:
                checkpoint = memory.get(config)
                if checkpoint:
                    print(f"Resuming from checkpoint for issue #{args.issue}...")
                else:
                    print(f"No checkpoint found for issue #{args.issue}, starting fresh...")

            # Stream events
            for event in app.stream(initial_state, config):
                # Each event is keyed by node name
                for node_name, node_output in event.items():
                    record.node(node_name)
                    if node_name == "__end__":
                        continue

                    # #4150 (ledger 0908, line 1344): a node's error is loud,
                    # on stderr, when it happens. Routing decides what stops.
                    error = (node_output or {}).get("error_message", "")
                    if error:
                        print(f"\n[ERROR] {error}", file=sys.stderr)

            # Get final state
            final_state = app.get_state(config)
            values = dict(final_state.values) if final_state and final_state.values else {}
            if not values:
                # #4150 (ledger 0908, line 1484): this recorded a halt and
                # then exited 0. With no final state the outcome is unknown.
                reason = (
                    "the testing graph produced no final state, so the run's "
                    "outcome is unknown and nothing is landed"
                )
                print(f"[implement] ERROR: {reason}", file=sys.stderr)
                alert.alert_operator(
                    what="the implementation run ended without a final state",
                    where="tools/run_implement_from_lld.py main", cause=reason,
                    consequence="the run exits 1; its worktree and branch are kept",
                    repo=str(original_repo_root), issue=args.issue,
                )
                return _run_failed(reason, {})

            # Print summary
            print("\n" + "=" * 60)
            print("WORKFLOW COMPLETE")
            print("=" * 60)

            # Debug: Show key final state values
            print(f"DEBUG: Final state error_message: '{values.get('error_message', '')}'")
            print(f"DEBUG: Final state next_node: '{values.get('next_node', '')}'")
            print(f"DEBUG: Final state iteration_count: {values.get('iteration_count', 0)}")
            print(f"DEBUG: Final state coverage_achieved: {values.get('coverage_achieved', 0)}")

            if values.get("test_report_path"):
                print(f"Test Report: {values['test_report_path']}")

            # #2926: the adversarial review's outcome, or why it did not
            # run, is in the report where the run is judged.
            from assemblyzero.workflows.testing.nodes.adversarial_node import (
                adversarial_summary,
            )

            print(adversarial_summary(values))

            error = values.get("error_message") or ""
            if error and values.get("workflow_status") != "halted":
                # #4150 (ledger 0908, line 1377): the HALT node alerts on
                # every halt (#3724); an error that reached END another way
                # is sent through it here, so it alerts too.
                halt_unfinished_run(values, error)
            elif not error and not _run_completed(values, bool(args.scaffold_only)):
                # #4150: only N7 finalize sets workflow_status "completed"
                # (#2677). The testing graph still has routes to END with no
                # reason (an iteration cap, a spent budget, an exhausted
                # scaffold, #3581's testing/graph.py rows). Such an end is
                # not a pass, and it must never be landed as one.
                error = (
                    "the run reached END without N7 finalize: workflow_status is "
                    f"{values.get('workflow_status')!r}, not 'completed' (next_node "
                    f"{values.get('next_node')!r}, iteration "
                    f"{values.get('iteration_count', 0)}). A route ended the graph "
                    "without a reason, which is not a pass, so nothing is landed."
                )
                print(f"[implement] ERROR: {error}", file=sys.stderr)
                halt_unfinished_run(values, error)
            if error:
                return _run_failed(error, values)

            # #3509, #4150: the run finishes its own worktree (END_STATE).
            # #1756: the PR targets the integration branch the worktree was
            # carved from, never a default main.
            if worktree_path:
                print()
                print("[implement] Finishing the run (see --help, 'End state'):")
                finished, steps = finish_standalone_run(
                    original_repo_root, Path(worktree_path), args.issue,
                    base_branch or "", mock=bool(args.mock),
                    scaffold_only=bool(args.scaffold_only),
                    pr_summary=adversarial_summary(values),
                )
                for step in steps:
                    print(f"[implement]   {step}")
                if not finished:
                    # #4150 (ledger 0908, line 1442): this printed a note and
                    # returned 0. An end state not reached is a failure.
                    reason = (
                        "the run passed, but its end state was not reached: "
                        + (steps[-1] if steps else "no step reported why")
                    )
                    print(f"[implement] ERROR: {reason}", file=sys.stderr)
                    halt_unfinished_run(values, reason)
                    return _run_failed(reason, values)

            print("Status: SUCCESS")
            # Issue #646: Emit per-issue cost summary
            total_cost = get_cumulative_cost()
            if total_cost > 0:
                print(f"Cost:   ${total_cost:.4f}")
                emit(
                    "workflow.cost",
                    repo="AssemblyZero",
                    metadata={
                        "workflow_type": "implementation",
                        "issue_number": args.issue,
                        "total_cost_usd": round(total_cost, 6),
                    },
                )
            _write_status_file(
                repo_root, args.issue, "SUCCESS", state=values,
                out_dir=runs_dir,
            )
            _finalize_speedrun("success", state=values)
            # #3547: the checkpoint database is an artifact the run leaves.
            print(f"[implement] Checkpoint database (resume state): {db_path}")
            record.finish("success")
            return 0

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted. Use --resume to continue.")
        _finalize_speedrun("halt", error_msg="user interrupt", notes="KeyboardInterrupt")
        record.finish("halt", "user interrupt")
        return 130

    except Exception as e:
        # #4150 (ledger 0908, line 1458): both branches printed to stdout and
        # alerted no one.
        cause = f"{type(e).__name__}: {getattr(e, 'reason', None) or e}"
        # Check if this is an ImplementationError (issue #272)
        if type(e).__name__ == "ImplementationError":
            print(f"\n{'='*60}", file=sys.stderr)
            print("IMPLEMENTATION FAILED", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"File: {getattr(e, 'filepath', 'unknown')}", file=sys.stderr)
            print(f"Reason: {getattr(e, 'reason', str(e))}", file=sys.stderr)
            preview = getattr(e, 'response_preview', None)
            if preview:
                print(f"\nResponse preview:\n{preview[:500]}", file=sys.stderr)
            print("\nThis is a hard failure. The implementation node could not produce valid code.",
                  file=sys.stderr)
            print("Check the LLD specification and try again.", file=sys.stderr)
            record.crash(e)
            record.finish("fail", getattr(e, "reason", str(e)))
            alert.alert_operator(
                what="the implementation node could not produce valid code",
                where="tools/run_implement_from_lld.py main", cause=cause,
                consequence="the run exits 1; its worktree and branch are kept",
                repo=str(original_repo_root), issue=args.issue,
            )
            return 1

        print(f"\n[FATAL] Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        _finalize_speedrun("halt", error_msg=str(e), notes=f"exception:{type(e).__name__}")
        record.crash(e)
        record.finish("halt", str(e))
        alert.alert_operator(
            what="the implementation run crashed",
            where="tools/run_implement_from_lld.py main", cause=cause,
            consequence="the run exits 1; its worktree and branch are kept",
            repo=str(original_repo_root), issue=args.issue,
        )
        return 1


if __name__ == "__main__":
    with track_tool("run_implement_from_lld", repo="AssemblyZero"):
        sys.exit(main())

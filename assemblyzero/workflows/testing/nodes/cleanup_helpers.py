"""Helper functions for N9 cleanup node.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Pure-function helpers that are independently testable without mocking
LangGraph state machinery. All subprocess calls use SUBPROCESS_TIMEOUT
to prevent hanging.
"""

from __future__ import annotations

from assemblyzero.utils.shell import run_command
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SUBPROCESS_TIMEOUT: int = 10  # seconds — max wait for gh/git CLI calls


@dataclass
class IterationSnapshot:
    """Captures coverage data from a single TDD iteration."""

    iteration: int
    coverage_pct: float
    missing_lines: list[str] = field(default_factory=list)
    root_cause: str = ""


@dataclass
class LearningSummaryData:
    """Structured data extracted from lineage artifacts before rendering to markdown."""

    issue_number: int
    outcome: str
    final_coverage: float
    target_coverage: float
    total_iterations: int
    stall_detected: bool
    stall_iteration: int | None
    iteration_snapshots: list[IterationSnapshot] = field(default_factory=list)
    key_artifacts: list[tuple[str, str]] = field(default_factory=list)
    what_worked: list[str] = field(default_factory=list)
    what_didnt_work: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def check_pr_merged(pr_url: str) -> bool:
    """Check if a GitHub PR is merged using gh CLI.

    Args:
        pr_url: Full GitHub PR URL.

    Returns:
        True if PR state is MERGED, False otherwise.

    Raises:
        subprocess.CalledProcessError: If gh CLI invocation fails.
        subprocess.TimeoutExpired: If gh CLI exceeds SUBPROCESS_TIMEOUT.
        ValueError: If pr_url is empty or malformed.
    """
    if not pr_url:
        raise ValueError("pr_url cannot be empty")
    if "github.com" not in pr_url:
        raise ValueError(f"Malformed PR URL: {pr_url}")

    result = run_command(
        ["gh", "pr", "view", pr_url, "--json", "state", "--jq", ".state"],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )
    return result.stdout.strip() == "MERGED"


def remove_worktree(worktree_path: str | Path) -> bool:
    """Remove a git worktree (without --force).

    Args:
        worktree_path: Absolute path to the worktree directory.

    Returns:
        True if worktree was removed successfully, False if it didn't exist.

    Raises:
        subprocess.CalledProcessError: If git worktree remove fails
            (e.g., dirty worktree).
        subprocess.TimeoutExpired: If git CLI exceeds SUBPROCESS_TIMEOUT.
    """
    worktree_path = Path(worktree_path)
    if not worktree_path.exists():
        logger.info("[N9] Worktree path does not exist: %s", worktree_path)
        return False

    result = run_command(
        ["git", "worktree", "remove", str(worktree_path)],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )
    logger.info("[N9] Worktree removed: %s", worktree_path)
    return True


def get_worktree_branch(worktree_path: str | Path) -> str | None:
    """Extract the branch name associated with a worktree.

    Args:
        worktree_path: Absolute path to the worktree directory.

    Returns:
        Branch name string, or None if worktree not found in git worktree list.

    Raises:
        subprocess.TimeoutExpired: If git CLI exceeds SUBPROCESS_TIMEOUT.
    """
    # Keep as plain string to match git porcelain output format exactly.
    # Do NOT use Path.resolve() — on Windows it transforms Unix-style paths
    # from porcelain output into Windows paths, breaking the comparison.
    worktree_str = str(worktree_path)

    result = run_command(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
        timeout=SUBPROCESS_TIMEOUT,
    )

    if result.returncode != 0:
        logger.warning("[N9] git worktree list failed: %s", result.stderr)
        return None

    # Parse porcelain output: blocks separated by blank lines
    current_worktree = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_worktree = line[len("worktree "):]
        elif line.startswith("branch ") and current_worktree == worktree_str:
            branch_ref = line[len("branch "):]
            # Strip refs/heads/ prefix
            if branch_ref.startswith("refs/heads/"):
                return branch_ref[len("refs/heads/"):]
            return branch_ref

    return None


def delete_local_branch(branch_name: str) -> bool:
    """Delete a local git branch using -D (force, for squash-merged branches).

    Args:
        branch_name: Name of the branch to delete.

    Returns:
        True if deleted, False if branch didn't exist.

    Raises:
        subprocess.CalledProcessError: If git branch -D fails for reasons
            other than branch-not-found.
        subprocess.TimeoutExpired: If git CLI exceeds SUBPROCESS_TIMEOUT.
    """
    try:
        run_command(
            ["git", "branch", "-d", branch_name],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        logger.info("[N9] Deleted local branch: %s", branch_name)
        return True
    except subprocess.CalledProcessError as exc:
        if "not found" in exc.stderr.lower() or "error: branch" in exc.stderr.lower():
            logger.info("[N9] Branch not found (already deleted?): %s", branch_name)
            return False
        raise


def archive_lineage(
    repo_root: Path,
    issue_number: int,
    lineage_suffix: str = "testing",
) -> Path | None:
    """Move lineage directory from active/ to done/.

    Args:
        repo_root: Path to the repository root.
        issue_number: GitHub issue number.
        lineage_suffix: Subdirectory suffix (default "testing").

    Returns:
        Path to the new done/ directory, or None if active dir didn't exist.

    Raises:
        OSError: If move operation fails.
    """
    dir_name = f"{issue_number}-{lineage_suffix}"
    active_dir = repo_root / "docs" / "lineage" / "active" / dir_name
    done_base = repo_root / "docs" / "lineage" / "done"

    if not active_dir.exists():
        logger.info("[N9] Active lineage dir not found: %s", active_dir)
        return None

    done_base.mkdir(parents=True, exist_ok=True)
    done_dir = done_base / dir_name

    if done_dir.exists():
        # Collision: append timestamp suffix
        timestamp = int(time.time())
        dir_name_ts = f"{dir_name}-{timestamp}"
        done_dir = done_base / dir_name_ts
        logger.warning(
            "[N9] done/ directory already exists, using suffix: %s", dir_name_ts
        )

    shutil.move(str(active_dir), str(done_dir))
    logger.info("[N9] Lineage archived: %s -> %s", active_dir, done_dir)
    return done_dir


def extract_iteration_data(lineage_dir: Path) -> list[IterationSnapshot]:
    """Parse lineage artifacts to extract per-iteration coverage data.

    Scans for files matching patterns like *green-phase*, *coverage*,
    *failed-response* to reconstruct the iteration history.

    Args:
        lineage_dir: Path to the lineage directory (active or done).

    Returns:
        List of IterationSnapshot in chronological order.
    """
    if not lineage_dir.exists():
        return []

    coverage_pattern = re.compile(r"[Cc]overage:\s*([\d.]+)%")
    alt_coverage_pattern = re.compile(r"([\d.]+)%\s*coverage")
    missing_pattern = re.compile(r"[Mm]issing(?:\s+lines)?:\s*(.+)")

    snapshots: list[IterationSnapshot] = []
    iteration = 0

    # Sort files by name for chronological ordering (numeric prefix)
    files = sorted(lineage_dir.iterdir())

    for file_path in files:
        if not file_path.is_file():
            continue

        name_lower = file_path.name.lower()
        if "green-phase" not in name_lower and "coverage" not in name_lower:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Extract coverage percentage
        coverage_pct = 0.0
        match = coverage_pattern.search(content)
        if not match:
            match = alt_coverage_pattern.search(content)
        if match:
            try:
                coverage_pct = float(match.group(1))
            except ValueError:
                coverage_pct = 0.0

        # Extract missing lines
        missing_lines: list[str] = []
        missing_match = missing_pattern.search(content)
        if missing_match:
            missing_lines = [
                line.strip()
                for line in missing_match.group(1).split(",")
                if line.strip()
            ]

        iteration += 1
        snapshots.append(
            IterationSnapshot(
                iteration=iteration,
                coverage_pct=coverage_pct,
                missing_lines=missing_lines,
                root_cause="",
            )
        )

    return snapshots


def detect_stall(snapshots: list[IterationSnapshot]) -> tuple[bool, int | None]:
    """Detect if coverage stalled (same coverage for 2+ consecutive iterations).

    Args:
        snapshots: Ordered list of iteration snapshots.

    Returns:
        Tuple of (stall_detected, stall_iteration_number).
        stall_iteration_number is None if no stall detected.
    """
    if len(snapshots) < 2:
        return (False, None)

    for i in range(1, len(snapshots)):
        if snapshots[i].coverage_pct == snapshots[i - 1].coverage_pct:
            return (True, snapshots[i].iteration)

    return (False, None)


def build_learning_summary(
    lineage_dir: Path,
    issue_number: int,
    outcome: str,
    final_coverage: float,
    target_coverage: float,
) -> LearningSummaryData:
    """Build structured learning summary data from lineage artifacts.

    Args:
        lineage_dir: Path to the lineage directory.
        issue_number: GitHub issue number.
        outcome: "SUCCESS" or "FAILURE".
        final_coverage: Final test coverage percentage.
        target_coverage: Target coverage percentage.

    Returns:
        Populated LearningSummaryData instance.
    """
    snapshots = extract_iteration_data(lineage_dir)
    stall_detected, stall_iteration = detect_stall(snapshots)

    # Collect key artifacts
    key_artifacts: list[tuple[str, str]] = []
    if lineage_dir.exists():
        for f in sorted(lineage_dir.iterdir()):
            if f.is_file() and f.name != "learning-summary.md":
                # Infer description from filename
                name_lower = f.name.lower()
                if "lld" in name_lower:
                    desc = "LLD document"
                elif "scaffold" in name_lower or "test" in name_lower:
                    desc = "Test scaffold"
                elif "green" in name_lower:
                    desc = "Green phase output"
                elif "red" in name_lower:
                    desc = "Red phase output"
                elif "coverage" in name_lower:
                    desc = "Coverage report"
                elif "failed" in name_lower:
                    desc = "Failed response"
                else:
                    desc = "Artifact"
                key_artifacts.append((f.name, desc))

    # Generate what_worked / what_didnt_work / recommendations
    what_worked: list[str] = []
    what_didnt_work: list[str] = []
    recommendations: list[str] = []

    total_iterations = len(snapshots) if snapshots else 0

    if outcome == "SUCCESS":
        what_worked.append(
            f"Coverage target achieved ({final_coverage}% >= {target_coverage}%)"
        )
        if total_iterations > 0:
            what_worked.append(
                f"TDD loop converged in {total_iterations} iteration(s)"
            )
    else:
        what_didnt_work.append(
            f"Coverage target not met ({final_coverage}% < {target_coverage}%)"
        )

    if stall_detected and stall_iteration is not None:
        what_didnt_work.append(
            f"Coverage stalled at iteration {stall_iteration}"
        )
        recommendations.append(
            "Consider splitting complex functions for easier testing when coverage stalls"
        )

    if total_iterations >= 3:
        recommendations.append(
            "High iteration count — consider improving test scaffold specificity"
        )

    if not recommendations:
        recommendations.append(
            "No specific recommendations — workflow completed as expected"
        )

    return LearningSummaryData(
        issue_number=issue_number,
        outcome=outcome,
        final_coverage=final_coverage,
        target_coverage=target_coverage,
        total_iterations=total_iterations,
        stall_detected=stall_detected,
        stall_iteration=stall_iteration,
        iteration_snapshots=snapshots,
        key_artifacts=key_artifacts,
        what_worked=what_worked,
        what_didnt_work=what_didnt_work,
        recommendations=recommendations,
    )


def render_learning_summary(data: LearningSummaryData) -> str:
    """Render LearningSummaryData to markdown string.

    The output format is versioned (Format Version: 1.0) and documented
    for stable consumption by future learning agents.

    Args:
        data: Structured learning summary data.

    Returns:
        Complete markdown string for learning-summary.md.
    """
    lines: list[str] = []

    lines.append(f"# Learning Summary \u2014 Issue #{data.issue_number}")
    lines.append("")
    lines.append("## Format Version: 1.0")
    lines.append("")
    lines.append("## Outcome")
    lines.append("")
    lines.append(f"- **Result:** {data.outcome}")
    lines.append(f"- **Final Coverage:** {data.final_coverage}%")
    lines.append(f"- **Target Coverage:** {data.target_coverage}%")
    lines.append(f"- **Total Iterations:** {data.total_iterations}")
    lines.append("")

    # Coverage Gap Analysis
    lines.append("## Coverage Gap Analysis")
    lines.append("")
    if data.iteration_snapshots:
        lines.append("| Iteration | Coverage | Missing Lines |")
        lines.append("|-----------|----------|---------------|")
        for snap in data.iteration_snapshots:
            missing = ", ".join(snap.missing_lines) if snap.missing_lines else "\u2014"
            lines.append(f"| {snap.iteration} | {snap.coverage_pct}% | {missing} |")
    else:
        lines.append("No iteration data available.")
    lines.append("")

    # Stall Analysis
    lines.append("## Stall Analysis")
    lines.append("")
    lines.append(f"- **Stall detected:** {'Yes' if data.stall_detected else 'No'}")
    if data.stall_detected and data.stall_iteration is not None:
        lines.append(f"- **Stall iteration:** {data.stall_iteration}")
    lines.append("")

    # Key Artifacts
    lines.append("## Key Artifacts")
    lines.append("")
    if data.key_artifacts:
        lines.append("| File | Description |")
        lines.append("|------|-------------|")
        for filename, desc in data.key_artifacts:
            lines.append(f"| {filename} | {desc} |")
    else:
        lines.append("No artifacts found.")
    lines.append("")

    # What Worked
    lines.append("## What Worked")
    lines.append("")
    if data.what_worked:
        for item in data.what_worked:
            lines.append(f"- {item}")
    else:
        lines.append("- (none recorded)")
    lines.append("")

    # What Didn't Work
    lines.append("## What Didn't Work")
    lines.append("")
    if data.what_didnt_work:
        for item in data.what_didnt_work:
            lines.append(f"- {item}")
    else:
        lines.append("- (none recorded)")
    lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    if data.recommendations:
        for item in data.recommendations:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    lines.append("")

    return "\n".join(lines)


def write_learning_summary(lineage_dir: Path, content: str) -> Path:
    """Write learning summary markdown to the lineage directory.

    Args:
        lineage_dir: Path to the lineage directory (active/ or done/).
        content: Markdown content string.

    Returns:
        Path to the written learning-summary.md file.
    """
    summary_path = lineage_dir / "learning-summary.md"
    summary_path.write_text(content)
    logger.info("[N9] Learning summary written to: %s", summary_path)
    return summary_path

"""Stale TODO comment scanner.

Detects TODO/FIXME/HACK/XXX comments older than 30 days using git blame.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

from assemblyzero.utils.shell import run_command
import os
import re
from datetime import datetime, timedelta, timezone

from assemblyzero.workflows.janitor.state import Finding, ProbeResult

# TODOs older than this many days are flagged
STALE_TODO_DAYS = 30

# Pattern to detect TODO-like comments
_TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b.*", re.IGNORECASE)


def probe_todo(repo_root: str) -> ProbeResult:
    """Scan source files for TODO comments older than 30 days.

    Uses git blame to determine when each TODO line was added.
    Only scans tracked files (respects .gitignore).
    Findings are unfixable (require human decision).
    """
    source_files = find_source_files(repo_root)
    findings: list[Finding] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_TODO_DAYS)

    for rel_path in source_files:
        abs_path = os.path.join(repo_root, rel_path)
        todos = extract_todos(abs_path)
        for line_number, comment_text in todos:
            line_date = get_line_date(repo_root, rel_path, line_number)
            if line_date is None:
                continue
            if line_date < cutoff:
                age_days = (datetime.now(timezone.utc) - line_date).days
                findings.append(
                    Finding(
                        probe="todo",
                        category="stale_todo",
                        message=(
                            f"Stale TODO in {rel_path} line {line_number} "
                            f"({age_days} days old): '{comment_text.strip()}'"
                        ),
                        severity="info",
                        fixable=False,
                        file_path=rel_path,
                        line_number=line_number,
                    )
                )

    if findings:
        return ProbeResult(probe="todo", status="findings", findings=findings)
    return ProbeResult(probe="todo", status="ok")


def find_source_files(repo_root: str) -> list[str]:
    """Find all tracked source files (*.py, *.md, *.ts, *.js).

    Uses `git ls-files` to respect .gitignore.
    """
    result = run_command(
        ["git", "ls-files", "*.py", "*.md", "*.ts", "*.js"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().splitlines() if f]


def extract_todos(file_path: str) -> list[tuple[int, str]]:
    """Extract TODO/FIXME/HACK/XXX comments from a file.

    Returns list of (line_number, comment_text) tuples.
    """
    results: list[tuple[int, str]] = []
    try:
        with open(file_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                match = _TODO_PATTERN.search(line)
                if match:
                    results.append((line_num, match.group(0)))
    except OSError:
        pass
    return results


def get_line_date(
    repo_root: str, file_path: str, line_number: int
) -> datetime | None:
    """Use git blame to determine when a specific line was last modified.

    Returns None if file is not tracked or blame fails.
    """
    result = run_command(
        [
            "git",
            "blame",
            "-L",
            f"{line_number},{line_number}",
            "--porcelain",
            file_path,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        if line.startswith("author-time "):
            try:
                timestamp = int(line[len("author-time ") :])
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (ValueError, OSError):
                return None

    return None

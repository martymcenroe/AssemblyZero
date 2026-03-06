"""Reporter implementations for janitor workflow output.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

from assemblyzero.utils.shell import run_command
import abc
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Literal

from assemblyzero.workflows.janitor.state import (
    Finding,
    FixAction,
    ProbeResult,
    Severity,
)


class ReporterInterface(abc.ABC):
    """Abstract base class for janitor report backends."""

    @abc.abstractmethod
    def find_existing_report(self) -> str | None:
        """Find existing open Janitor Report. Returns identifier or None."""
        ...

    @abc.abstractmethod
    def create_report(self, title: str, body: str, severity: Severity) -> str:
        """Create a new report. Returns identifier."""
        ...

    @abc.abstractmethod
    def update_report(
        self, identifier: str, body: str, severity: Severity
    ) -> str:
        """Update an existing report. Returns identifier."""
        ...


class GitHubReporter(ReporterInterface):
    """Reporter that creates/updates GitHub issues via `gh` CLI."""

    def __init__(self, repo_root: str) -> None:
        """Initialize with repo root for gh CLI execution context."""
        self.repo_root = repo_root
        self._validate_gh_cli()

    def _validate_gh_cli(self) -> None:
        """Check gh CLI is available and authenticated.

        Falls back to GITHUB_TOKEN env var if interactive auth fails.
        """
        try:
            result = run_command(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                cwd=self.repo_root,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("gh auth status timed out after 30s")
        if result.returncode != 0:
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                raise RuntimeError(
                    "gh CLI not authenticated and GITHUB_TOKEN not set. "
                    "Run 'gh auth login' or set GITHUB_TOKEN environment variable."
                )

    def find_existing_report(self) -> str | None:
        """Search for open issues with title matching 'Janitor Report'."""
        try:
            result = run_command(
                [
                    "gh",
                    "issue",
                    "list",
                    "--search",
                    "Janitor Report in:title",
                    "--state",
                    "open",
                    "--json",
                    "url",
                    "--limit",
                    "1",
                ],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return None
        if result.returncode != 0:
            return None

        try:
            issues = json.loads(result.stdout)
            if issues:
                return issues[0]["url"]
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        return None

    def create_report(
        self, title: str, body: str, severity: Severity
    ) -> str:
        """Create a new GitHub issue."""
        try:
            result = run_command(
                [
                    "gh",
                    "issue",
                    "create",
                    "--title",
                    title,
                    "--body",
                    body,
                    "--label",
                    "maintenance",
                ],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("gh issue create timed out after 30s")
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create GitHub issue: {result.stderr}")
        return result.stdout.strip()

    def update_report(
        self, identifier: str, body: str, severity: Severity
    ) -> str:
        """Update an existing GitHub issue body.

        Extracts issue number from URL for gh issue edit.
        """
        # Extract issue number from URL like https://github.com/user/repo/issues/42
        issue_number = identifier.rstrip("/").split("/")[-1]
        try:
            result = run_command(
                [
                    "gh",
                    "issue",
                    "edit",
                    issue_number,
                    "--body",
                    body,
                ],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("gh issue edit timed out after 30s")
        if result.returncode != 0:
            raise RuntimeError(f"Failed to update GitHub issue: {result.stderr}")
        return identifier


class LocalFileReporter(ReporterInterface):
    """Reporter that writes reports to local files. No API calls.

    Output directory: {repo_root}/janitor-reports/
    File naming: janitor-report-{YYYY-MM-DD-HHMMSS}.md
    """

    def __init__(self, repo_root: str) -> None:
        """Initialize with repo root; creates janitor-reports/ if needed."""
        self.repo_root = repo_root
        self.report_dir = Path(repo_root) / "janitor-reports"
        self.report_dir.mkdir(exist_ok=True)

    def find_existing_report(self) -> str | None:
        """Check for existing report file from today."""
        today_prefix = f"janitor-report-{datetime.now().strftime('%Y-%m-%d')}"
        for f in sorted(self.report_dir.glob(f"{today_prefix}*.md")):
            return str(f)
        return None

    def create_report(
        self, title: str, body: str, severity: Severity
    ) -> str:
        """Write report to a new markdown file. Returns file path."""
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        filename = f"janitor-report-{timestamp}.md"
        file_path = self.report_dir / filename
        file_path.write_text(body, encoding="utf-8")
        return str(file_path)

    def update_report(
        self, identifier: str, body: str, severity: Severity
    ) -> str:
        """Overwrite existing report file. Returns file path."""
        Path(identifier).write_text(body, encoding="utf-8")
        return identifier


def build_report_body(
    unfixable_findings: list[Finding],
    fix_actions: list[FixAction],
    probe_results: list[ProbeResult],
) -> str:
    """Build a structured markdown report body.

    Sections:
    - Summary (counts by severity)
    - Auto-Fixed Issues (what was resolved)
    - Requires Human Attention (grouped by category)
    - Probe Errors (any probes that crashed)
    """
    lines: list[str] = []
    lines.append("# Janitor Report")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    severity_counts = {"critical": 0, "warning": 0, "info": 0}
    for f in unfixable_findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    lines.append(f"| Critical | {severity_counts['critical']} |")
    lines.append(f"| Warning | {severity_counts['warning']} |")
    lines.append(f"| Info | {severity_counts['info']} |")
    lines.append("")

    # Auto-Fixed Issues
    lines.append("## Auto-Fixed Issues")
    lines.append("")
    if fix_actions:
        for action in fix_actions:
            status = "[PASS]" if action.applied else ""
            lines.append(f"- {status} {action.description}")
    else:
        lines.append("No auto-fixes applied.")
    lines.append("")

    # Requires Human Attention
    lines.append("## Requires Human Attention")
    lines.append("")
    if unfixable_findings:
        # Group by category
        by_category: dict[str, list[Finding]] = {}
        for f in unfixable_findings:
            by_category.setdefault(f.category, []).append(f)

        for category, findings in by_category.items():
            lines.append(f"### {category}")
            lines.append("")
            for f in findings:
                location = ""
                if f.file_path:
                    location = f" ({f.file_path}"
                    if f.line_number:
                        location += f":{f.line_number}"
                    location += ")"
                lines.append(f"- [!] {f.message}{location}")
            lines.append("")
    else:
        lines.append("No issues require human attention.")
        lines.append("")

    # Probe Errors
    error_probes = [pr for pr in probe_results if pr.status == "error"]
    if error_probes:
        lines.append("## Probe Errors")
        lines.append("")
        for pr in error_probes:
            lines.append(f"- [X] **{pr.probe}**: {pr.error_message}")
        lines.append("")

    return "\n".join(lines)


def get_reporter(
    reporter_type: Literal["github", "local"], repo_root: str
) -> ReporterInterface:
    """Factory function to instantiate the correct reporter."""
    if reporter_type == "github":
        return GitHubReporter(repo_root)
    elif reporter_type == "local":
        return LocalFileReporter(repo_root)
    else:
        raise ValueError(f"Unknown reporter type: {reporter_type}")

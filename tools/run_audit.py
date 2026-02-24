#!/usr/bin/env python3
"""Standalone CLI audit runner for mechanical audit checks.

Runs 6 fully mechanical audit checks without Claude tokens:
- 0832: Command cost optimization (file metrics, line counts)
- 0834: Worktree hygiene (git worktree + status)
- 0836: Gitignore consistency (mandatory security patterns)
- 0837: README compliance (required sections check)
- 0838: Broken references (markdown link validation)
- 0844: File inventory drift (glob vs docs/0003 table)

Issue #343: Standalone CLI Audit Runner

Usage:
    poetry run python tools/run_audit.py                    # all 6 audits
    poetry run python tools/run_audit.py 0834 0836          # specific audits
    poetry run python tools/run_audit.py --repo /path/to/X  # target repo
"""

import argparse
import atexit
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Issue #424: Telemetry instrumentation
from assemblyzero.telemetry import flush, track_tool
atexit.register(flush)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AuditFinding:
    """A single finding from an audit check."""

    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    audit_id: str  # e.g. "0832"
    message: str
    details: str = ""


@dataclass
class AuditResult:
    """Result of a single audit check."""

    audit_id: str
    name: str
    status: str  # PASS, FAIL, WARN, SKIP, ERROR
    findings: list[AuditFinding] = field(default_factory=list)


# Severity ordering for sorting
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

# Mandatory security patterns for gitignore (0836)
SECURITY_PATTERNS = [".env", "*.pem", "*.key", "credentials.json", "secrets.json"]

# Required README sections (0837)
README_REQUIRED_SECTIONS = [
    "title",       # H1 heading
    "overview",
    "status",
    "quick start",
    "project structure",
    "documentation",
    "development",
    "license",
]

# File inventory categories and their glob patterns (0844)
INVENTORY_CATEGORIES = {
    "Standards": "docs/standards/*.md",
    "Templates": "docs/templates/*.md",
    "ADRs": "docs/adrs/*.md",
    "Skills": "docs/skills/06*.md",
    "Audits": "docs/audits/*.md",
    "Runbooks": "docs/runbooks/*.md",
    "Tools": "tools/*.py",
    "Commands": ".claude/commands/*.md",
}


# ---------------------------------------------------------------------------
# Audit checks
# ---------------------------------------------------------------------------

def check_0832_cost_optimization(repo_root: Path) -> AuditResult:
    """0832: Command cost optimization — file metrics, line counts.

    Measures .claude/commands/*.md sizes and flags any >4KB (~1,000 tokens).
    """
    result = AuditResult(audit_id="0832", name="Cost Optimization", status="PASS")

    commands_dir = repo_root / ".claude" / "commands"
    if not commands_dir.exists():
        result.status = "SKIP"
        result.findings.append(AuditFinding(
            severity="INFO",
            audit_id="0832",
            message="No .claude/commands/ directory found",
        ))
        return result

    command_files = sorted(commands_dir.glob("*.md"))
    if not command_files:
        result.status = "SKIP"
        result.findings.append(AuditFinding(
            severity="INFO",
            audit_id="0832",
            message="No command files found",
        ))
        return result

    oversized = []
    for cmd_file in command_files:
        try:
            size = cmd_file.stat().st_size
            line_count = len(cmd_file.read_text(encoding="utf-8").splitlines())
            if size > 4096:
                oversized.append((cmd_file.name, size, line_count))
        except OSError:
            result.findings.append(AuditFinding(
                severity="LOW",
                audit_id="0832",
                message=f"Cannot read {cmd_file.name}",
            ))

    if oversized:
        result.status = "WARN"
        for name, size, lines in oversized:
            result.findings.append(AuditFinding(
                severity="MEDIUM",
                audit_id="0832",
                message=f"Oversized command: {name} ({size:,} bytes, {lines} lines)",
                details=f"Commands >4KB (~1,000 tokens) cost more per invocation. "
                        f"Consider extracting mechanical logic to a Python script.",
            ))
    else:
        result.findings.append(AuditFinding(
            severity="INFO",
            audit_id="0832",
            message=f"All {len(command_files)} commands under 4KB threshold",
        ))

    return result


def check_0834_worktree_hygiene(repo_root: Path) -> AuditResult:
    """0834: Worktree hygiene — detect stale/orphaned worktrees.

    Runs git worktree list and checks for uncommitted changes and age.
    """
    result = AuditResult(audit_id="0834", name="Worktree Hygiene", status="PASS")

    # List worktrees
    try:
        proc = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        result.status = "ERROR"
        result.findings.append(AuditFinding(
            severity="HIGH",
            audit_id="0834",
            message="Cannot run git worktree list",
        ))
        return result

    if proc.returncode != 0:
        result.status = "ERROR"
        result.findings.append(AuditFinding(
            severity="HIGH",
            audit_id="0834",
            message=f"git worktree list failed: {proc.stderr.strip()}",
        ))
        return result

    # Parse porcelain output
    worktrees = _parse_worktree_porcelain(proc.stdout)

    # Filter out main worktree (bare = False, first entry is main)
    non_main = [wt for wt in worktrees if not wt.get("bare") and wt != worktrees[0]]

    if not non_main:
        result.findings.append(AuditFinding(
            severity="INFO",
            audit_id="0834",
            message="No extra worktrees found — clean",
        ))
        return result

    # Check each non-main worktree
    for wt in non_main:
        wt_path = Path(wt["worktree"])

        if not wt_path.exists():
            result.status = "FAIL"
            result.findings.append(AuditFinding(
                severity="HIGH",
                audit_id="0834",
                message=f"Worktree path missing: {wt_path}",
                details="Worktree registered in git but directory does not exist. "
                        "Run: git worktree prune",
            ))
            continue

        # Check for uncommitted changes
        try:
            status_proc = subprocess.run(
                ["git", "-C", str(wt_path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if status_proc.stdout.strip():
                result.status = "FAIL"
                change_count = len(status_proc.stdout.strip().splitlines())
                result.findings.append(AuditFinding(
                    severity="HIGH",
                    audit_id="0834",
                    message=f"Uncommitted changes in {wt_path.name} ({change_count} files)",
                    details="Work may be lost. Commit or stash changes.",
                ))
        except (subprocess.TimeoutExpired, OSError):
            pass

        # Check branch info
        branch = wt.get("branch", "")
        if branch:
            branch_name = branch.replace("refs/heads/", "")
            result.findings.append(AuditFinding(
                severity="INFO",
                audit_id="0834",
                message=f"Worktree: {wt_path.name} on branch {branch_name}",
            ))

    return result


def check_0836_gitignore_consistency(repo_root: Path) -> AuditResult:
    """0836: Gitignore consistency — verify mandatory security patterns.

    Reads .gitignore and verifies security-critical patterns are present.
    Also checks git ls-files for accidentally tracked secrets.
    """
    result = AuditResult(audit_id="0836", name="Gitignore Consistency", status="PASS")

    gitignore_path = repo_root / ".gitignore"

    # Also check parent .gitignore (Projects/.gitignore)
    parent_gitignore = repo_root.parent / ".gitignore"

    gitignore_content = ""
    if gitignore_path.exists():
        try:
            gitignore_content += gitignore_path.read_text(encoding="utf-8")
        except OSError:
            pass

    if parent_gitignore.exists():
        try:
            gitignore_content += "\n" + parent_gitignore.read_text(encoding="utf-8")
        except OSError:
            pass

    if not gitignore_content:
        result.status = "FAIL"
        result.findings.append(AuditFinding(
            severity="HIGH",
            audit_id="0836",
            message="No .gitignore found",
            details="Project has no .gitignore — secrets could be committed.",
        ))
        return result

    # Check security-critical patterns
    missing_patterns = []
    for pattern in SECURITY_PATTERNS:
        if pattern not in gitignore_content:
            missing_patterns.append(pattern)

    if missing_patterns:
        result.status = "FAIL"
        for pattern in missing_patterns:
            result.findings.append(AuditFinding(
                severity="HIGH",
                audit_id="0836",
                message=f"Missing security pattern: {pattern}",
                details="Add this pattern to .gitignore to prevent accidental commits.",
            ))

    # Check for tracked secrets via git ls-files
    secret_globs = ["*.pem", "*.key", ".env", "credentials.json", "secrets.json"]
    for glob_pattern in secret_globs:
        try:
            proc = subprocess.run(
                ["git", "ls-files", glob_pattern],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            tracked = proc.stdout.strip()
            if tracked:
                result.status = "FAIL"
                for tracked_file in tracked.splitlines():
                    result.findings.append(AuditFinding(
                        severity="CRITICAL",
                        audit_id="0836",
                        message=f"SECRET TRACKED: {tracked_file}",
                        details="This file matches a secret pattern and is tracked by git. "
                                "Remove immediately: git rm --cached <file>",
                    ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    if result.status == "PASS":
        result.findings.append(AuditFinding(
            severity="INFO",
            audit_id="0836",
            message=f"All {len(SECURITY_PATTERNS)} security patterns present, no tracked secrets",
        ))

    return result


def check_0837_readme_compliance(repo_root: Path) -> AuditResult:
    """0837: README compliance — check 9 required sections.

    Parses README.md H1/H2 headings and checks for mandatory sections.
    """
    result = AuditResult(audit_id="0837", name="README Compliance", status="PASS")

    readme_path = repo_root / "README.md"
    if not readme_path.exists():
        result.status = "FAIL"
        result.findings.append(AuditFinding(
            severity="HIGH",
            audit_id="0837",
            message="No README.md found",
        ))
        return result

    try:
        content = readme_path.read_text(encoding="utf-8")
    except OSError as e:
        result.status = "ERROR"
        result.findings.append(AuditFinding(
            severity="HIGH",
            audit_id="0837",
            message=f"Cannot read README.md: {e}",
        ))
        return result

    # Extract headings
    headings = []
    for line in content.splitlines():
        if line.startswith("# ") or line.startswith("## "):
            heading_text = line.lstrip("#").strip().lower()
            headings.append(heading_text)

    # Check for required sections
    has_title = any(line.startswith("# ") for line in content.splitlines())
    missing = []

    for section in README_REQUIRED_SECTIONS:
        if section == "title":
            if not has_title:
                missing.append("Title (H1)")
        elif section == "quick start":
            # Allow variations
            if not any(s in h for h in headings for s in ["quick start", "quickstart", "getting started", "installation"]):
                missing.append("Quick Start")
        else:
            if not any(section in h for h in headings):
                missing.append(section.title())

    if missing:
        result.status = "WARN" if len(missing) <= 2 else "FAIL"
        for section in missing:
            result.findings.append(AuditFinding(
                severity="MEDIUM",
                audit_id="0837",
                message=f"Missing README section: {section}",
            ))
    else:
        result.findings.append(AuditFinding(
            severity="INFO",
            audit_id="0837",
            message=f"All {len(README_REQUIRED_SECTIONS)} required sections present",
        ))

    return result


def check_0838_broken_references(repo_root: Path) -> AuditResult:
    """0838: Broken references — extract markdown links, validate paths.

    Regex-extracts ](path) from all .md files and verifies relative paths exist.
    """
    result = AuditResult(audit_id="0838", name="Broken References", status="PASS")

    # Find all markdown files (exclude non-project dirs and generated content)
    md_files = sorted(repo_root.rglob("*.md"))
    # Exclude: .git, node_modules, templates (contain placeholder links),
    # lineage (generated LLDs reference standards by relative path),
    # done (historical archives)
    exclude_parts = {".git", "node_modules", "__pycache__", "templates", "lineage", "done"}
    md_files = [
        f for f in md_files
        if not any(part in exclude_parts for part in f.relative_to(repo_root).parts)
    ]

    if not md_files:
        result.status = "SKIP"
        result.findings.append(AuditFinding(
            severity="INFO",
            audit_id="0838",
            message="No markdown files found",
        ))
        return result

    # Link pattern: [text](path) — skip URLs, anchors, and images from URLs
    link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
    broken_count = 0
    checked_count = 0

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for match in link_pattern.finditer(content):
            link_path = match.group(2).strip()

            # Skip URLs, anchors, mailto, and template variables
            if any(link_path.startswith(prefix) for prefix in [
                "http://", "https://", "#", "mailto:", "{{", "<",
            ]):
                continue

            # Strip anchor from path
            if "#" in link_path:
                link_path = link_path.split("#")[0]
            if not link_path:
                continue

            checked_count += 1

            # Resolve relative to the markdown file's directory
            target = (md_file.parent / link_path).resolve()
            if not target.exists():
                broken_count += 1
                result.findings.append(AuditFinding(
                    severity="MEDIUM",
                    audit_id="0838",
                    message=f"Broken link in {md_file.relative_to(repo_root)}",
                    details=f"Link target not found: {link_path}",
                ))

    if broken_count > 0:
        result.status = "FAIL" if broken_count > 5 else "WARN"
    else:
        result.findings.append(AuditFinding(
            severity="INFO",
            audit_id="0838",
            message=f"All {checked_count} relative links validated",
        ))

    return result


def check_0844_file_inventory_drift(repo_root: Path) -> AuditResult:
    """0844: File inventory drift — glob vs docs/0003 table.

    Parses docs/0003-file-inventory.md summary table and compares
    counts against actual files via glob.
    """
    result = AuditResult(audit_id="0844", name="File Inventory Drift", status="PASS")

    inventory_path = repo_root / "docs" / "0003-file-inventory.md"
    if not inventory_path.exists():
        result.status = "SKIP"
        result.findings.append(AuditFinding(
            severity="INFO",
            audit_id="0844",
            message="No docs/0003-file-inventory.md found",
        ))
        return result

    try:
        content = inventory_path.read_text(encoding="utf-8")
    except OSError as e:
        result.status = "ERROR"
        result.findings.append(AuditFinding(
            severity="HIGH",
            audit_id="0844",
            message=f"Cannot read inventory file: {e}",
        ))
        return result

    # Parse the summary statistics table
    # Format: | Category | Count | Status |
    inventory_counts = _parse_inventory_counts(content)

    if not inventory_counts:
        result.status = "WARN"
        result.findings.append(AuditFinding(
            severity="MEDIUM",
            audit_id="0844",
            message="Could not parse summary statistics from inventory",
        ))
        return result

    # Compare against actual file counts
    drift_found = False
    for category, expected in inventory_counts.items():
        glob_pattern = INVENTORY_CATEGORIES.get(category)
        if not glob_pattern:
            continue

        actual_files = sorted(repo_root.glob(glob_pattern))
        actual = len(actual_files)

        if actual != expected:
            drift_found = True
            result.findings.append(AuditFinding(
                severity="MEDIUM",
                audit_id="0844",
                message=f"Drift in {category}: inventory says {expected}, found {actual}",
                details=f"Glob pattern: {glob_pattern}",
            ))

    if drift_found:
        result.status = "WARN"
    else:
        result.findings.append(AuditFinding(
            severity="INFO",
            audit_id="0844",
            message=f"File inventory matches reality for {len(inventory_counts)} categories",
        ))

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_worktree_porcelain(output: str) -> list[dict]:
    """Parse git worktree list --porcelain output into dicts."""
    worktrees = []
    current: dict = {}

    for line in output.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"worktree": line.split(" ", 1)[1]}
        elif line.startswith("HEAD "):
            current["HEAD"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1]
        elif line == "bare":
            current["bare"] = True

    if current:
        worktrees.append(current)

    return worktrees


def _parse_inventory_counts(content: str) -> dict[str, int]:
    """Parse summary statistics table from 0003-file-inventory.md.

    Expected format:
    | Category | Count | Status |
    |----------|-------|--------|
    | Standards | 9 | All stable |
    """
    counts = {}

    # Find "Summary Statistics" section
    match = re.search(r"##.*Summary Statistics", content, re.IGNORECASE)
    if not match:
        return counts

    section = content[match.end():]
    # Stop at next section
    next_section = re.search(r"\n## ", section)
    if next_section:
        section = section[:next_section.start()]

    # Parse table rows
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        if re.match(r"\|\s*-+", line):
            continue

        # Extract category and count: | Category | Count | ... |
        row_match = re.match(
            r"\|\s*\*?\*?([^*|]+)\*?\*?\s*\|\s*\*?\*?(\d+)\*?\*?\s*\|",
            line,
        )
        if row_match:
            category = row_match.group(1).strip()
            count = int(row_match.group(2))
            # Skip aggregate rows
            if category.lower() not in ("total docs", "total tools", "total", "category"):
                counts[category] = count

    return counts


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

AUDIT_REGISTRY: dict[str, tuple[str, callable]] = {
    "0832": ("Cost Optimization", check_0832_cost_optimization),
    "0834": ("Worktree Hygiene", check_0834_worktree_hygiene),
    "0836": ("Gitignore Consistency", check_0836_gitignore_consistency),
    "0837": ("README Compliance", check_0837_readme_compliance),
    "0838": ("Broken References", check_0838_broken_references),
    "0844": ("File Inventory Drift", check_0844_file_inventory_drift),
}


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_markdown_report(
    results: list[AuditResult],
    repo_root: Path,
) -> str:
    """Format audit results as a markdown report matching existing format."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    lines = [
        f"# CLI Audit Results - {date_str}",
        "",
        f"**Runner:** tools/run_audit.py",
        f"**Project:** {repo_root.name}",
        f"**Timestamp:** {now.isoformat()}",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Audit | Status | Findings |",
        "|-------|--------|----------|",
    ]

    # Summary table
    for r in results:
        finding_count = len([f for f in r.findings if f.severity != "INFO"])
        summary = f"{finding_count} finding(s)" if finding_count else "Clean"
        lines.append(f"| {r.audit_id} {r.name} | {r.status} | {summary} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Group findings by severity
    all_findings = []
    for r in results:
        all_findings.extend(r.findings)

    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        severity_findings = [f for f in all_findings if f.severity == severity]
        if not severity_findings:
            continue

        lines.append(f"## {severity.title()} Findings")
        lines.append("")
        for i, finding in enumerate(severity_findings, 1):
            lines.append(f"{i}. **[{severity}]** {finding.message}")
            if finding.details:
                lines.append(f"   - {finding.details}")
        lines.append("")

    # Statistics
    lines.append("---")
    lines.append("")
    lines.append("## Statistics")
    lines.append("")
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    warned = sum(1 for r in results if r.status == "WARN")
    skipped = sum(1 for r in results if r.status == "SKIP")
    errors = sum(1 for r in results if r.status == "ERROR")
    lines.append(f"- **Total audits:** {len(results)}")
    lines.append(f"- **Passed:** {passed}")
    if failed:
        lines.append(f"- **Failed:** {failed}")
    if warned:
        lines.append(f"- **Warnings:** {warned}")
    if skipped:
        lines.append(f"- **Skipped:** {skipped}")
    if errors:
        lines.append(f"- **Errors:** {errors}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by tools/run_audit.py on {date_str}*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point for standalone audit runner."""
    parser = argparse.ArgumentParser(
        description="Run mechanical audit checks without Claude tokens",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "audits",
        nargs="*",
        help="Specific audit IDs to run (e.g., 0834 0836). Default: all.",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=".",
        help="Target repository path (default: current directory)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: docs/audit-results/{date}-cli.md)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print report to stdout without saving to file",
    )

    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    if not repo_root.exists():
        print(f"Error: Repository path does not exist: {repo_root}", file=sys.stderr)
        return 1

    # Determine which audits to run
    if args.audits:
        audit_ids = args.audits
        invalid = [a for a in audit_ids if a not in AUDIT_REGISTRY]
        if invalid:
            print(f"Error: Unknown audit(s): {', '.join(invalid)}", file=sys.stderr)
            print(f"Available: {', '.join(sorted(AUDIT_REGISTRY.keys()))}", file=sys.stderr)
            return 1
    else:
        audit_ids = sorted(AUDIT_REGISTRY.keys())

    print(f"Running {len(audit_ids)} audit(s) on {repo_root.name}...")
    print()

    # Run audits
    results = []
    for audit_id in audit_ids:
        name, check_fn = AUDIT_REGISTRY[audit_id]
        print(f"  [{audit_id}] {name}...", end=" ", flush=True)
        try:
            result = check_fn(repo_root)
        except Exception as e:
            result = AuditResult(
                audit_id=audit_id,
                name=name,
                status="ERROR",
                findings=[AuditFinding(
                    severity="HIGH",
                    audit_id=audit_id,
                    message=f"Audit crashed: {e}",
                )],
            )
        results.append(result)
        print(result.status)

    print()

    # Generate report
    report = format_markdown_report(results, repo_root)

    # Save or print
    if args.no_save:
        print(report)
    else:
        output_path = args.output
        if not output_path:
            output_dir = repo_root / "docs" / "audit-results"
            output_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            output_path = str(output_dir / f"{date_str}-cli.md")

        output_path = Path(output_path)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report saved: {output_path}")

    # Print summary
    failed = sum(1 for r in results if r.status in ("FAIL", "ERROR"))
    critical = sum(1 for r in results for f in r.findings if f.severity == "CRITICAL")

    if critical:
        print(f"\nCRITICAL: {critical} critical finding(s) require immediate attention!")
        return 2
    elif failed:
        print(f"\nFAILED: {failed} audit(s) need attention.")
        return 1
    else:
        print("\nAll audits passed.")
        return 0


if __name__ == "__main__":
    with track_tool("run_audit", repo="AssemblyZero"):
        sys.exit(main())

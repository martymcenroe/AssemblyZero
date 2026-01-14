#!/usr/bin/env python3
"""
agentos-harvest.py - Cross-Project Pattern Discovery

Scans registered child projects to find patterns that should potentially
be promoted to AgentOS. Part of the bidirectional sync architecture (ADR 0206).

Usage:
    poetry run python tools/agentos-harvest.py [--project NAME] [--format json|markdown] [--verbose]

Examples:
    poetry run python tools/agentos-harvest.py                    # Scan all projects
    poetry run python tools/agentos-harvest.py --project Talos    # Scan only Talos
    poetry run python tools/agentos-harvest.py --format json      # Output as JSON
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Import AgentOS config for path management
try:
    from agentos_config import config
except ImportError:
    # Fallback if running outside AgentOS context
    config = None


# AgentOS root (where this script lives)
AGENTOS_ROOT = Path(__file__).parent.parent.resolve()
REGISTRY_PATH = AGENTOS_ROOT / ".claude" / "project-registry.json"


@dataclass
class PromotionCandidate:
    """A pattern found in a child project that may warrant promotion to AgentOS."""
    category: str           # commands, tools, templates, permissions, claude_md
    name: str               # File or pattern name
    project: str            # Which project it was found in
    path: str               # Full path to the artifact
    reason: str             # Why this is a promotion candidate
    priority: str = "medium"  # low, medium, high
    already_in_agentos: bool = False
    convergent: bool = False  # Found in multiple projects


@dataclass
class HarvestReport:
    """Full harvest report for one or more projects."""
    timestamp: str
    agentos_version: str
    projects_scanned: list
    candidates: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def load_registry() -> dict:
    """Load the project registry."""
    if not REGISTRY_PATH.exists():
        print(f"ERROR: Project registry not found at {REGISTRY_PATH}", file=sys.stderr)
        print("Create it first or run: agentos-generate.py --init-registry", file=sys.stderr)
        sys.exit(1)

    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_agentos_commands() -> set:
    """Get set of command names in AgentOS."""
    commands_dir = AGENTOS_ROOT / ".claude" / "commands"
    if not commands_dir.exists():
        return set()
    return {f.stem for f in commands_dir.glob("*.md")}


def get_agentos_tools() -> set:
    """Get set of tool names in AgentOS."""
    tools_dir = AGENTOS_ROOT / ".claude" / "tools"
    if not tools_dir.exists():
        return set()
    # Include both shell scripts and other tools
    tools = set()
    for pattern in ["*.sh", "*.py", "*.js"]:
        tools.update(f.name for f in tools_dir.glob(pattern))
    return tools


def get_agentos_templates() -> set:
    """Get set of template directories/patterns in AgentOS."""
    templates_dir = AGENTOS_ROOT / ".claude" / "templates"
    if not templates_dir.exists():
        return set()
    # Get subdirectory names (e.g., gemini-prompts)
    return {d.name for d in templates_dir.iterdir() if d.is_dir()}


def scan_project_commands(project_path: Path, project_name: str, agentos_commands: set) -> list:
    """Find commands in project that don't exist in AgentOS."""
    candidates = []
    commands_dir = project_path / ".claude" / "commands"

    if not commands_dir.exists():
        return candidates

    for cmd_file in commands_dir.glob("*.md"):
        cmd_name = cmd_file.stem
        if cmd_name not in agentos_commands:
            candidates.append(PromotionCandidate(
                category="commands",
                name=cmd_name,
                project=project_name,
                path=str(cmd_file),
                reason=f"Command '{cmd_name}' exists in {project_name} but not in AgentOS",
                priority="high"  # Commands are high value
            ))

    return candidates


def scan_project_tools(project_path: Path, project_name: str, agentos_tools: set) -> list:
    """Find tools in project .claude/tools that don't exist in AgentOS."""
    candidates = []
    tools_dir = project_path / ".claude" / "tools"

    if not tools_dir.exists():
        return candidates

    for tool_file in tools_dir.iterdir():
        if tool_file.is_file():
            tool_name = tool_file.name
            if tool_name not in agentos_tools:
                # Check if it looks generic (no hardcoded project names in significant places)
                content = tool_file.read_text(encoding="utf-8", errors="ignore")
                is_generic = project_name.lower() not in content.lower() or \
                             f"for {project_name}" in content.lower()  # OK if just a comment

                priority = "high" if is_generic else "medium"
                reason = f"Tool '{tool_name}' exists in {project_name} but not in AgentOS"
                if not is_generic:
                    reason += f" (contains {project_name}-specific references)"

                candidates.append(PromotionCandidate(
                    category="tools",
                    name=tool_name,
                    project=project_name,
                    path=str(tool_file),
                    reason=reason,
                    priority=priority
                ))

    return candidates


def scan_project_templates(project_path: Path, project_name: str, agentos_templates: set) -> list:
    """Find template directories/prompts in project that don't exist in AgentOS."""
    candidates = []
    claude_dir = project_path / ".claude"

    if not claude_dir.exists():
        return candidates

    # Look for directories that might be templates (e.g., gemini-prompts, hooks)
    skip_dirs = {"commands", "tools", "templates"}  # Standard dirs

    for item in claude_dir.iterdir():
        if item.is_dir() and item.name not in skip_dirs:
            if item.name not in agentos_templates:
                # Count files in directory
                files = list(item.glob("*"))
                file_count = len([f for f in files if f.is_file()])

                if file_count > 0:
                    candidates.append(PromotionCandidate(
                        category="templates",
                        name=item.name,
                        project=project_name,
                        path=str(item),
                        reason=f"Template directory '{item.name}' ({file_count} files) exists in {project_name} but not in AgentOS",
                        priority="medium"
                    ))

    return candidates


def scan_project_permissions(project_path: Path, project_name: str) -> list:
    """Find permission patterns in project that might be generic."""
    candidates = []
    settings_file = project_path / ".claude" / "settings.local.json"

    if not settings_file.exists():
        return candidates

    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except (json.JSONDecodeError, IOError):
        return candidates

    # Check for allow patterns that look generic
    allow_patterns = settings.get("permissions", {}).get("allow", [])

    # Load AgentOS base permissions for comparison
    agentos_settings = AGENTOS_ROOT / ".claude" / "settings.local.json"
    agentos_allow = set()
    if agentos_settings.exists():
        try:
            with open(agentos_settings, "r", encoding="utf-8") as f:
                agentos_data = json.load(f)
                agentos_allow = set(agentos_data.get("permissions", {}).get("allow", []))
        except (json.JSONDecodeError, IOError):
            pass

    for pattern in allow_patterns:
        if pattern not in agentos_allow:
            # Check if it looks generic (not project-specific path)
            # Use config for path if available, otherwise fallback to default
            projects_path = config.projects_root_unix() if config else "/c/Users/mcwiz/Projects"
            is_generic = project_name.lower() not in pattern.lower() and \
                         projects_path not in pattern

            if is_generic:
                candidates.append(PromotionCandidate(
                    category="permissions",
                    name=pattern,
                    project=project_name,
                    path=str(settings_file),
                    reason=f"Permission pattern '{pattern}' may be generic enough for AgentOS",
                    priority="low"
                ))

    return candidates


def scan_claude_md(project_path: Path, project_name: str) -> list:
    """Check for CLAUDE.md sections that duplicate AgentOS content."""
    candidates = []
    project_claude = project_path / "CLAUDE.md"
    agentos_claude = AGENTOS_ROOT / "CLAUDE.md"

    if not project_claude.exists() or not agentos_claude.exists():
        return candidates

    try:
        project_content = project_claude.read_text(encoding="utf-8")
        agentos_content = agentos_claude.read_text(encoding="utf-8")
    except IOError:
        return candidates

    # Look for duplicate sections (simple line-based detection)
    # More sophisticated: parse markdown headers and compare sections
    project_lines = set(line.strip() for line in project_content.split("\n")
                        if line.strip() and not line.startswith("#"))
    agentos_lines = set(line.strip() for line in agentos_content.split("\n")
                        if line.strip() and not line.startswith("#"))

    # Find significant duplicates (lines > 50 chars that appear in both)
    duplicates = [line for line in project_lines & agentos_lines if len(line) > 50]

    if len(duplicates) > 5:  # Threshold for "significant duplication"
        candidates.append(PromotionCandidate(
            category="claude_md",
            name="CLAUDE.md duplication",
            project=project_name,
            path=str(project_claude),
            reason=f"CLAUDE.md has {len(duplicates)} lines duplicating AgentOS content - consider trimming",
            priority="low"
        ))

    return candidates


def detect_convergent_evolution(all_candidates: list) -> list:
    """Find patterns that appear in multiple projects (convergent evolution)."""
    # Group by category + name
    pattern_projects = {}
    for c in all_candidates:
        key = (c.category, c.name)
        if key not in pattern_projects:
            pattern_projects[key] = []
        pattern_projects[key].append(c.project)

    # Mark convergent patterns
    for c in all_candidates:
        key = (c.category, c.name)
        if len(pattern_projects[key]) > 1:
            c.convergent = True
            c.priority = "high"  # Convergent patterns are high priority
            c.reason += f" [CONVERGENT: found in {', '.join(pattern_projects[key])}]"

    return all_candidates


def harvest_project(project: dict, verbose: bool = False) -> list:
    """Harvest promotion candidates from a single project."""
    project_name = project["name"]
    project_path = Path(project["path"])

    if not project_path.exists():
        if verbose:
            print(f"  SKIP: {project_name} - path does not exist: {project_path}", file=sys.stderr)
        return []

    if verbose:
        print(f"  Scanning {project_name}...", file=sys.stderr)

    # Get AgentOS baselines
    agentos_commands = get_agentos_commands()
    agentos_tools = get_agentos_tools()
    agentos_templates = get_agentos_templates()

    candidates = []

    # Scan each category
    candidates.extend(scan_project_commands(project_path, project_name, agentos_commands))
    candidates.extend(scan_project_tools(project_path, project_name, agentos_tools))
    candidates.extend(scan_project_templates(project_path, project_name, agentos_templates))
    candidates.extend(scan_project_permissions(project_path, project_name))
    candidates.extend(scan_claude_md(project_path, project_name))

    if verbose:
        print(f"    Found {len(candidates)} candidates", file=sys.stderr)

    return candidates


def format_markdown(report: HarvestReport, candidates: list) -> str:
    """Format report as markdown.

    Args:
        report: The harvest report (with dict candidates for JSON serialization)
        candidates: Original PromotionCandidate objects (for attribute access)
    """
    lines = [
        "# AgentOS Harvest Report",
        "",
        f"**Generated:** {report.timestamp}",
        f"**AgentOS Version:** {report.agentos_version}",
        f"**Projects Scanned:** {', '.join(report.projects_scanned)}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Category | Count | High Priority |",
        f"|----------|-------|---------------|",
    ]

    for cat, stats in report.summary.items():
        lines.append(f"| {cat} | {stats['total']} | {stats['high']} |")

    lines.extend(["", "---", ""])

    # Group candidates by priority
    high = [c for c in candidates if c.priority == "high"]
    medium = [c for c in candidates if c.priority == "medium"]
    low = [c for c in candidates if c.priority == "low"]

    if high:
        lines.extend([
            "## High Priority (Recommend Promotion)",
            "",
        ])
        for c in high:
            convergent_marker = " **[CONVERGENT]**" if c.convergent else ""
            lines.append(f"### {c.category}: `{c.name}`{convergent_marker}")
            lines.append(f"- **Project:** {c.project}")
            lines.append(f"- **Path:** `{c.path}`")
            lines.append(f"- **Reason:** {c.reason}")
            lines.append("")

    if medium:
        lines.extend([
            "## Medium Priority (Consider Promotion)",
            "",
        ])
        for c in medium:
            lines.append(f"- **{c.category}:** `{c.name}` ({c.project}) - {c.reason}")
        lines.append("")

    if low:
        lines.extend([
            "## Low Priority (Review Later)",
            "",
        ])
        for c in low:
            lines.append(f"- **{c.category}:** `{c.name}` ({c.project})")
        lines.append("")

    if not candidates:
        lines.extend([
            "## No Promotion Candidates Found",
            "",
            "All child projects are aligned with AgentOS.",
        ])

    lines.extend([
        "---",
        "",
        "*Generated by `agentos-harvest.py` - see ADR 0206 for architecture*",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Harvest promotion candidates from child projects"
    )
    parser.add_argument(
        "--project", "-p",
        help="Scan only this project (default: all registered projects)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)"
    )

    args = parser.parse_args()

    # Load registry
    registry = load_registry()
    projects = registry.get("children", [])

    if not projects:
        print("ERROR: No projects registered in project-registry.json", file=sys.stderr)
        sys.exit(1)

    # Filter to specific project if requested
    if args.project:
        projects = [p for p in projects if p["name"].lower() == args.project.lower()]
        if not projects:
            print(f"ERROR: Project '{args.project}' not found in registry", file=sys.stderr)
            sys.exit(1)

    if args.verbose:
        print(f"Harvesting {len(projects)} project(s)...", file=sys.stderr)

    # Harvest all projects
    all_candidates = []
    scanned_projects = []

    for project in projects:
        if project.get("status") != "active":
            if args.verbose:
                print(f"  SKIP: {project['name']} - status is {project.get('status', 'unknown')}", file=sys.stderr)
            continue

        candidates = harvest_project(project, args.verbose)
        all_candidates.extend(candidates)
        scanned_projects.append(project["name"])

    # Detect convergent evolution
    all_candidates = detect_convergent_evolution(all_candidates)

    # Build summary
    summary = {}
    for c in all_candidates:
        if c.category not in summary:
            summary[c.category] = {"total": 0, "high": 0}
        summary[c.category]["total"] += 1
        if c.priority == "high":
            summary[c.category]["high"] += 1

    # Build report
    report = HarvestReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        agentos_version="2.2",  # From index.md
        projects_scanned=scanned_projects,
        candidates=[asdict(c) for c in all_candidates],
        summary=summary
    )

    # Format output
    if args.format == "json":
        output = json.dumps(asdict(report), indent=2)
    else:
        output = format_markdown(report, all_candidates)

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        if args.verbose:
            print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    # Exit with code indicating if candidates were found
    sys.exit(0 if not all_candidates else 1)


if __name__ == "__main__":
    main()

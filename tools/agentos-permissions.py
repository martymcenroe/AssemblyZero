#!/usr/bin/env python3
"""
AgentOS Permission Propagation Tool

Syncs friction-free permissions across projects under Projects/.

Modes:
  --audit        Read-only analysis of redundant/stale permissions
  --clean        Remove redundancies and stale session vends
  --sync         Full sync with auto-promote (patterns in 3+ projects)
  --quick-check  Fast check for cleanup integration (exit code 0/1)

Usage:
  poetry run python tools/agentos-permissions.py --audit --project Aletheia
  poetry run python tools/agentos-permissions.py --clean --project AgentOS --dry-run
  poetry run python tools/agentos-permissions.py --sync --all-projects
  poetry run python tools/agentos-permissions.py --quick-check --project Aletheia
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from collections import Counter
from typing import Optional


# Parent-level broad patterns that cover specific project permissions
# These are extracted from C:\Users\mcwiz\Projects\.claude\settings.local.json
PARENT_BROAD_PATTERNS = [
    # Bash command wildcards
    (r"^Bash\(git:\*\)$", r"^Bash\(git[ -]"),        # git:* covers git commands
    (r"^Bash\(poetry:\*\)$", r"^Bash\(poetry "),     # poetry:* covers poetry commands
    (r"^Bash\(npm:\*\)$", r"^Bash\(npm "),           # npm:* covers npm commands
    (r"^Bash\(npx:\*\)$", r"^Bash\(npx "),           # npx:* covers npx commands
    (r"^Bash\(node:\*\)$", r"^Bash\(node "),         # node:* covers node commands
    (r"^Bash\(docker:\*\)$", r"^Bash\(docker "),     # docker:* covers docker commands
    (r"^Bash\(aws:\*\)$", r"^Bash\(aws "),           # aws:* covers aws commands
    (r"^Bash\(gh:\*\)$", r"^Bash\(gh "),             # gh:* covers gh commands
    (r"^Bash\(cat:\*\)$", r"^Bash\(cat "),           # etc.
    (r"^Bash\(ls:\*\)$", r"^Bash\(ls "),
    (r"^Bash\(grep:\*\)$", r"^Bash\(grep "),
    (r"^Bash\(rg:\*\)$", r"^Bash\(rg "),
    (r"^Bash\(find:\*\)$", r"^Bash\(find "),
    (r"^Bash\(head:\*\)$", r"^Bash\(head "),
    (r"^Bash\(tail:\*\)$", r"^Bash\(tail "),
    (r"^Bash\(chmod:\*\)$", r"^Bash\(chmod "),
    (r"^Bash\(mkdir:\*\)$", r"^Bash\(mkdir "),
    (r"^Bash\(rm:\*\)$", r"^Bash\(rm "),
    (r"^Bash\(cp:\*\)$", r"^Bash\(cp "),
    (r"^Bash\(mv:\*\)$", r"^Bash\(mv "),
    (r"^Bash\(powershell\.exe:\*\)$", r"^Bash\(powershell\.exe "),
    (r"^Bash\(powershell:\*\)$", r"^Bash\(powershell "),
    (r"^Bash\(code:\*\)$", r"^Bash\(code "),
    (r"^Bash\(gemini:\*\)$", r"^Bash\(gemini "),
    (r"^Bash\(tasklist:\*\)$", r"^Bash\(tasklist"),
    (r"^Bash\(shellcheck:\*\)$", r"^Bash\(shellcheck "),
    (r"^Bash\(pytest:\*\)$", r"^Bash\(pytest "),
    (r"^Bash\(ruff:\*\)$", r"^Bash\(ruff "),
    (r"^Bash\(mypy:\*\)$", r"^Bash\(mypy "),
    (r"^Bash\(make:\*\)$", r"^Bash\(make "),
    (r"^Bash\(curl:\*\)$", r"^Bash\(curl "),
    (r"^Bash\(wget:\*\)$", r"^Bash\(wget "),
    (r"^Bash\(tar:\*\)$", r"^Bash\(tar "),
    (r"^Bash\(zip:\*\)$", r"^Bash\(zip "),
    (r"^Bash\(unzip:\*\)$", r"^Bash\(unzip "),
    (r"^Bash\(jq:\*\)$", r"^Bash\(jq "),
    (r"^Bash\(diff:\*\)$", r"^Bash\(diff "),
    (r"^Bash\(date:\*\)$", r"^Bash\(date "),
    (r"^Bash\(sleep:\*\)$", r"^Bash\(sleep "),
    (r"^Bash\(wc:\*\)$", r"^Bash\(wc "),
    (r"^Bash\(sort:\*\)$", r"^Bash\(sort "),
    (r"^Bash\(cut:\*\)$", r"^Bash\(cut "),
    (r"^Bash\(tr:\*\)$", r"^Bash\(tr "),
    (r"^Bash\(awk:\*\)$", r"^Bash\(awk "),
    (r"^Bash\(sed:\*\)$", r"^Bash\(sed "),
    (r"^Bash\(echo:\*\)$", r"^Bash\(echo "),
    (r"^Bash\(touch:\*\)$", r"^Bash\(touch "),
    (r"^Bash\(which:\*\)$", r"^Bash\(which "),
    (r"^Bash\(file:\*\)$", r"^Bash\(file "),
    (r"^Bash\(tree:\*\)$", r"^Bash\(tree "),
    (r"^Bash\(dig:\*\)$", r"^Bash\(dig "),
    (r"^Bash\(nslookup:\*\)$", r"^Bash\(nslookup "),
    (r"^Bash\(docker-compose:\*\)$", r"^Bash\(docker-compose "),
    (r"^Bash\(claude:\*\)$", r"^Bash\(claude "),
    # Path wildcards
    (r"^Bash\(/c/Users/mcwiz/Projects/\*\*:\*\)$", r"^Bash\(/c/Users/mcwiz/Projects/"),
    (r"^Bash\(\./tools/\*\*:\*\)$", r"^Bash\(\./tools/"),
    # Read/Write/Edit wildcards
    (r"^Read\(//c/Users/mcwiz/Projects/\*\*\)$", r"^Read\(//c/Users/mcwiz/Projects/"),
    (r"^Write\(//c/Users/mcwiz/Projects/\*\*\)$", r"^Write\(//c/Users/mcwiz/Projects/"),
    (r"^Edit\(//c/Users/mcwiz/Projects/\*\*\)$", r"^Edit\(//c/Users/mcwiz/Projects/"),
    (r"^Read\(//c/Users/mcwiz/\.claude/\*\*\)$", r"^Read\(//c/Users/mcwiz/\.claude/"),
    # Skills and WebFetch
    (r"^WebFetch$", r"^WebFetch\(domain:"),
    (r"^WebSearch$", None),  # Only exact match
]

# Patterns that indicate session-specific one-time permissions (vends)
SESSION_VEND_PATTERNS = [
    r'Bash\(git -C .* commit -m "\$',      # Git commits with embedded messages
    r"Bash\(git -C .* commit -m '\$",      # Git commits (single quotes)
    r'Bash\(gh pr create .* --body "\$',   # PR creations with body
    r"Bash\(gh pr create .* --body '\$",   # PR creations (single quotes)
    r'Bash\(gh pr create .* --body "',     # PR creations with inline body
    r"Bash\(git -C .* push -u origin HEAD\)", # One-time push with tracking
    r"Bash\(gh pr merge:",                  # PR merge commands
    r"EOF",                                 # Heredoc-style commits
]


def get_projects_dir() -> Path:
    """Get the Projects directory path."""
    return Path.home() / "Projects"


def get_parent_settings_path() -> Path:
    """Get path to parent settings.local.json."""
    return get_projects_dir() / ".claude" / "settings.local.json"


def get_project_settings_path(project_name: str) -> Path:
    """Get path to project's settings.local.json."""
    return get_projects_dir() / project_name / ".claude" / "settings.local.json"


def load_settings(path: Path) -> Optional[dict]:
    """Load settings.local.json from path."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {path}: {e}")
        return None


def save_settings(path: Path, settings: dict):
    """Save settings to path with pretty formatting."""
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding='utf-8')


def load_parent_patterns() -> set:
    """Load the set of permission patterns from parent settings."""
    parent_settings = load_settings(get_parent_settings_path())
    if not parent_settings:
        return set()
    return set(parent_settings.get("permissions", {}).get("allow", []))


def is_covered_by_parent(permission: str, parent_patterns: set) -> bool:
    """Check if a specific permission is covered by a broad parent pattern."""
    # Exact match
    if permission in parent_patterns:
        return True

    # Check if covered by a wildcard pattern
    for broad_pattern, specific_pattern in PARENT_BROAD_PATTERNS:
        # Check if the broad pattern exists in parent
        for parent_perm in parent_patterns:
            if re.match(broad_pattern, parent_perm):
                # If specific pattern is None, only exact match counts
                if specific_pattern is None:
                    continue
                # Check if this permission matches the specific pattern
                if re.match(specific_pattern, permission):
                    return True

    return False


def is_session_vend(permission: str) -> bool:
    """Check if permission looks like a one-time session vend."""
    for pattern in SESSION_VEND_PATTERNS:
        if re.search(pattern, permission):
            return True
    return False


def find_all_projects() -> list:
    """Find all project directories under Projects/ that have settings.local.json."""
    projects_dir = get_projects_dir()
    projects = []

    for item in projects_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            settings_path = item / ".claude" / "settings.local.json"
            if settings_path.exists():
                projects.append(item.name)

    return sorted(projects)


def audit_project(project_name: str, parent_patterns: set) -> dict:
    """Audit a project's permissions and classify them."""
    settings_path = get_project_settings_path(project_name)
    settings = load_settings(settings_path)

    if not settings:
        return {"error": f"Could not load settings for {project_name}"}

    allow_list = settings.get("permissions", {}).get("allow", [])

    redundant = []      # Covered by parent
    session_vends = []  # One-time permissions
    project_specific = []  # Truly project-specific

    for perm in allow_list:
        if is_session_vend(perm):
            session_vends.append(perm)
        elif is_covered_by_parent(perm, parent_patterns):
            redundant.append(perm)
        else:
            project_specific.append(perm)

    return {
        "project": project_name,
        "total": len(allow_list),
        "redundant": redundant,
        "session_vends": session_vends,
        "project_specific": project_specific,
    }


def print_audit_report(audit: dict):
    """Print a formatted audit report."""
    if "error" in audit:
        print(f"ERROR: {audit['error']}")
        return

    print(f"\n## Audit: {audit['project']}")
    print(f"Total permissions: {audit['total']}")
    print()

    print(f"### Redundant (covered by parent): {len(audit['redundant'])}")
    for perm in audit['redundant'][:10]:  # Show first 10
        print(f"  - {perm[:80]}...")
    if len(audit['redundant']) > 10:
        print(f"  ... and {len(audit['redundant']) - 10} more")
    print()

    print(f"### Session Vends (stale): {len(audit['session_vends'])}")
    for perm in audit['session_vends'][:5]:  # Show first 5
        print(f"  - {perm[:80]}...")
    if len(audit['session_vends']) > 5:
        print(f"  ... and {len(audit['session_vends']) - 5} more")
    print()

    print(f"### Project-Specific (keep): {len(audit['project_specific'])}")
    for perm in audit['project_specific'][:10]:  # Show first 10
        print(f"  - {perm[:80]}...")
    if len(audit['project_specific']) > 10:
        print(f"  ... and {len(audit['project_specific']) - 10} more")


def clean_project(project_name: str, parent_patterns: set, dry_run: bool = True) -> dict:
    """Clean a project's settings by removing redundancies and session vends."""
    settings_path = get_project_settings_path(project_name)
    settings = load_settings(settings_path)

    if not settings:
        return {"error": f"Could not load settings for {project_name}"}

    audit = audit_project(project_name, parent_patterns)

    # Keep only project-specific permissions
    new_allow = audit['project_specific']

    removed_count = len(audit['redundant']) + len(audit['session_vends'])

    if dry_run:
        print(f"\n## Dry Run: {project_name}")
        print(f"Would remove {removed_count} permissions:")
        print(f"  - {len(audit['redundant'])} redundant")
        print(f"  - {len(audit['session_vends'])} session vends")
        print(f"Would keep {len(new_allow)} project-specific permissions")
        return {"removed": removed_count, "kept": len(new_allow), "dry_run": True}

    # Create backup
    backup_path = settings_path.with_suffix('.local.json.bak')
    shutil.copy(settings_path, backup_path)
    print(f"Backup created: {backup_path}")

    # Update settings
    settings["permissions"]["allow"] = new_allow
    save_settings(settings_path, settings)

    print(f"\n## Cleaned: {project_name}")
    print(f"Removed {removed_count} permissions")
    print(f"Kept {len(new_allow)} project-specific permissions")

    return {"removed": removed_count, "kept": len(new_allow), "dry_run": False}


def find_common_patterns(projects: list, parent_patterns: set) -> list:
    """Find patterns that appear in 3+ projects (promotion candidates)."""
    pattern_counts = Counter()

    for project_name in projects:
        audit = audit_project(project_name, parent_patterns)
        if "error" in audit:
            continue

        # Count project-specific patterns (not already in parent)
        for perm in audit['project_specific']:
            # Normalize pattern for comparison (remove project-specific paths)
            normalized = re.sub(r'/c/Users/mcwiz/Projects/[^/]+', '/c/Users/mcwiz/Projects/{PROJECT}', perm)
            pattern_counts[normalized] += 1

    # Return patterns in 3+ projects
    return [pattern for pattern, count in pattern_counts.items() if count >= 3]


def quick_check(project_name: str, parent_patterns: set) -> int:
    """Quick check for cleanup integration. Returns exit code."""
    audit = audit_project(project_name, parent_patterns)

    if "error" in audit:
        print(f"ERROR: {audit['error']}")
        return 2

    stale_count = len(audit['session_vends'])
    redundant_count = len(audit['redundant'])

    if stale_count > 0 or redundant_count > 5:
        print(f"Stale permissions detected: {stale_count} vends, {redundant_count} redundant")
        print(f"Consider: poetry run python tools/agentos-permissions.py --clean --project {project_name}")
        return 1

    print(f"Permissions clean: {audit['total']} total, {len(audit['project_specific'])} project-specific")
    return 0


def sync_all(dry_run: bool = True):
    """Full sync: promote common patterns and clean all projects."""
    parent_patterns = load_parent_patterns()
    projects = find_all_projects()

    print(f"Found {len(projects)} projects with settings.local.json")

    # Find common patterns for promotion
    common = find_common_patterns(projects, parent_patterns)

    if common:
        print(f"\n## Patterns to promote (found in 3+ projects): {len(common)}")
        for pattern in common[:10]:
            print(f"  - {pattern[:80]}")
        if len(common) > 10:
            print(f"  ... and {len(common) - 10} more")

        if not dry_run:
            # Add common patterns to parent
            parent_path = get_parent_settings_path()
            parent_settings = load_settings(parent_path)
            if parent_settings:
                # Create backup
                backup_path = parent_path.with_suffix('.local.json.bak')
                shutil.copy(parent_path, backup_path)
                print(f"Parent backup: {backup_path}")

                # Add patterns (de-normalized - would need project name)
                # For now, just log - full implementation would need more work
                print("NOTE: Auto-promotion of patterns not yet implemented")

    # Clean each project
    print("\n## Cleaning projects...")
    for project_name in projects:
        clean_project(project_name, parent_patterns, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(
        description="AgentOS Permission Propagation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--audit", action="store_true",
                           help="Read-only analysis of permissions")
    mode_group.add_argument("--clean", action="store_true",
                           help="Remove redundancies and session vends")
    mode_group.add_argument("--sync", action="store_true",
                           help="Full sync with auto-promote")
    mode_group.add_argument("--quick-check", action="store_true",
                           help="Fast check for cleanup integration")
    mode_group.add_argument("--restore", action="store_true",
                           help="Restore from backup")

    parser.add_argument("--project", "-p",
                       help="Project name (e.g., Aletheia)")
    parser.add_argument("--all-projects", action="store_true",
                       help="Apply to all projects")
    parser.add_argument("--dry-run", "-n", action="store_true",
                       help="Show what would be done without modifying files")

    args = parser.parse_args()

    # Load parent patterns
    parent_patterns = load_parent_patterns()
    if not parent_patterns:
        print("ERROR: Could not load parent settings.local.json")
        print(f"Expected at: {get_parent_settings_path()}")
        sys.exit(1)

    print(f"Loaded {len(parent_patterns)} parent patterns")

    # Execute mode
    if args.audit:
        if args.all_projects:
            for project in find_all_projects():
                audit = audit_project(project, parent_patterns)
                print_audit_report(audit)
        elif args.project:
            audit = audit_project(args.project, parent_patterns)
            print_audit_report(audit)
        else:
            parser.error("--audit requires --project or --all-projects")

    elif args.clean:
        if args.project:
            clean_project(args.project, parent_patterns, dry_run=args.dry_run)
        elif args.all_projects:
            for project in find_all_projects():
                clean_project(project, parent_patterns, dry_run=args.dry_run)
        else:
            parser.error("--clean requires --project or --all-projects")

    elif args.sync:
        sync_all(dry_run=args.dry_run)

    elif args.quick_check:
        if not args.project:
            parser.error("--quick-check requires --project")
        exit_code = quick_check(args.project, parent_patterns)
        sys.exit(exit_code)

    elif args.restore:
        if not args.project:
            parser.error("--restore requires --project")
        settings_path = get_project_settings_path(args.project)
        backup_path = settings_path.with_suffix('.local.json.bak')
        if not backup_path.exists():
            print(f"ERROR: No backup found at {backup_path}")
            sys.exit(1)
        shutil.copy(backup_path, settings_path)
        print(f"Restored {settings_path} from backup")


if __name__ == "__main__":
    main()

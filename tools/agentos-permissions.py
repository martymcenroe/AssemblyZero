#!/usr/bin/env python3
"""
AgentOS Permission Propagation Tool

IMPORTANT: Claude Code permissions DO NOT INHERIT - they REPLACE.
When a project has its own permissions block, it completely overrides the parent.

This tool manages permissions across the master (user-level) and project-level files.

Modes:
  --audit        Read-only analysis of session vends
  --clean        Remove ONLY session vends (keeps all reusable patterns)
  --quick-check  Fast check for cleanup integration (exit code 0/1)
  --merge-up     Collect unique reusable patterns from projects into master
  --restore      Restore from backup

Usage:
  poetry run python tools/agentos-permissions.py --audit --project Aletheia
  poetry run python tools/agentos-permissions.py --clean --project AgentOS --dry-run
  poetry run python tools/agentos-permissions.py --quick-check --project Aletheia
  poetry run python tools/agentos-permissions.py --merge-up --all-projects
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Optional


def get_projects_dir() -> Path:
    """Get the Projects directory path."""
    return Path.home() / "Projects"


def get_master_settings_path() -> Path:
    """Get path to master (user-level) settings.local.json."""
    return Path.home() / ".claude" / "settings.local.json"


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


def is_session_vend(permission: str) -> tuple[bool, str]:
    """
    Check if permission is a one-time session vend that should be removed.

    Returns (is_vend, reason) tuple.

    Session vends are SPECIFIC one-time permissions, not reusable patterns.
    We identify them by looking for:
    - Embedded commit messages (heredocs, specific text)
    - Specific file paths in commands (not wildcards)
    - One-time git operations (specific commits, pushes, merges)
    """

    # Git commits with embedded messages (heredocs)
    if re.search(r'Bash\(git.* commit -m "\$\(cat <<', permission):
        return True, "git commit with heredoc"
    if re.search(r"Bash\(git.* commit -m '\$\(cat <<", permission):
        return True, "git commit with heredoc"
    if "EOF" in permission and "commit" in permission:
        return True, "git commit with EOF marker"

    # Git commits with inline messages (specific, not wildcard)
    if re.search(r'Bash\(git -C [^ ]+ commit -m "[^"]+"\)', permission):
        return True, "specific git commit"

    # PR creations with specific bodies
    if re.search(r'Bash\(gh pr create.* --body "\$', permission):
        return True, "PR creation with heredoc body"
    if re.search(r"Bash\(gh pr create.* --body '\$", permission):
        return True, "PR creation with heredoc body"
    if re.search(r'Bash\(gh pr create.* --body "[^"]{50,}', permission):
        return True, "PR creation with long body"

    # Specific git -C commands (not wildcards) - look for complete commands
    # e.g., Bash(git -C /path status) is a vend, but Bash(git -C /path commit -m "$(cat...") already caught above
    if re.search(r'Bash\(git -C /[^ ]+ (status|add|push|pull|fetch|diff|branch|stash|log)\)', permission):
        # These are specific one-off commands, likely vends
        # But we need to be careful - some might be intentional
        # Only flag if it has a very specific path
        if re.search(r'Bash\(git -C /c/Users/mcwiz/Projects/[^/]+-\d+ ', permission):
            return True, "git command on worktree (has issue ID)"
        # Don't flag commands on main project dirs - those might be intentional

    # Specific push commands with tracking
    if re.search(r'Bash\(git -C .+ push -u origin (HEAD|[a-zA-Z0-9-]+)\)', permission):
        return True, "one-time push with tracking"

    # PR merge commands (one-time)
    if re.search(r'Bash\(gh pr merge', permission):
        return True, "PR merge command"

    # Specific file opens with start command (Windows)
    if re.search(r'Bash\(start "" "[^"]+\\\\[^"]+\.(html|pdf|txt)"\)', permission):
        return True, "specific file open command"

    # Specific CLAUDE_TOOL_INPUT patterns (test commands)
    if "CLAUDE_TOOL_INPUT" in permission:
        return True, "test/debug command"

    # Powershell one-liners with specific date formatting
    if re.search(r'Bash\(powershell\.exe -Command "Get-Date', permission):
        return True, "powershell date command"

    return False, ""


def is_reusable_pattern(permission: str) -> tuple[bool, str]:
    """
    Check if permission is a reusable pattern that should be kept.

    Returns (is_reusable, category) tuple.
    """

    # Skills - always keep
    if permission.startswith("Skill("):
        return True, "Skill"

    # WebFetch/WebSearch - always keep
    if permission.startswith("WebFetch") or permission.startswith("WebSearch"):
        return True, "Web"

    # Read/Write/Edit wildcards - always keep
    if re.match(r"^(Read|Write|Edit)\(.*\*\*\)", permission):
        return True, "File wildcard"

    # Bash wildcards (end with :*) - always keep
    if re.match(r"^Bash\([^)]+:\*\)$", permission):
        return True, "Bash wildcard"

    # Bash path wildcards (./tools/**, /c/Users/...**) - always keep
    if re.search(r"Bash\(\./[^)]+\*\*", permission) or re.search(r"Bash\(/c/Users/[^)]+\*\*", permission):
        return True, "Path wildcard"

    # Environment variable prefixed commands with wildcards - keep
    if re.match(r"^Bash\([A-Z_]+=.+:\*\)$", permission):
        return True, "Env var wildcard"

    # gh commands with wildcards - keep
    if re.match(r"^Bash\(gh (pr|issue) (list|create|view):\*\)$", permission):
        return True, "gh wildcard"

    return False, ""


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


def audit_project(project_name: str) -> dict:
    """Audit a project's permissions and classify them."""
    settings_path = get_project_settings_path(project_name)
    settings = load_settings(settings_path)

    if not settings:
        return {"error": f"Could not load settings for {project_name}"}

    allow_list = settings.get("permissions", {}).get("allow", [])
    deny_list = settings.get("permissions", {}).get("deny", [])

    session_vends = []  # One-time permissions to remove
    reusable = []       # Reusable patterns to keep
    unclear = []        # Neither clearly vend nor clearly reusable

    for perm in allow_list:
        is_vend, vend_reason = is_session_vend(perm)
        if is_vend:
            session_vends.append((perm, vend_reason))
            continue

        is_reuse, reuse_category = is_reusable_pattern(perm)
        if is_reuse:
            reusable.append((perm, reuse_category))
            continue

        # If not clearly a vend or reusable, keep it (err on side of keeping)
        unclear.append(perm)

    return {
        "project": project_name,
        "total_allow": len(allow_list),
        "total_deny": len(deny_list),
        "session_vends": session_vends,
        "reusable": reusable,
        "unclear": unclear,
    }


def print_audit_report(audit: dict):
    """Print a formatted audit report."""
    if "error" in audit:
        print(f"ERROR: {audit['error']}")
        return

    print(f"\n{'='*60}")
    print(f"Audit: {audit['project']}")
    print(f"{'='*60}")
    print(f"Total: {audit['total_allow']} allow, {audit['total_deny']} deny")
    print()

    print(f"### Session Vends (REMOVE): {len(audit['session_vends'])}")
    if audit['session_vends']:
        for perm, reason in audit['session_vends'][:10]:
            print(f"  [{reason}]")
            print(f"    {perm[:100]}{'...' if len(perm) > 100 else ''}")
        if len(audit['session_vends']) > 10:
            print(f"  ... and {len(audit['session_vends']) - 10} more")
    else:
        print("  (none)")
    print()

    print(f"### Reusable Patterns (KEEP): {len(audit['reusable'])}")
    if audit['reusable']:
        # Group by category
        by_category = {}
        for perm, cat in audit['reusable']:
            by_category.setdefault(cat, []).append(perm)
        for cat, perms in sorted(by_category.items()):
            print(f"  {cat}: {len(perms)}")
            for perm in perms[:3]:
                print(f"    - {perm[:70]}{'...' if len(perm) > 70 else ''}")
            if len(perms) > 3:
                print(f"    ... and {len(perms) - 3} more")
    print()

    print(f"### Unclear (KEEP - err on side of caution): {len(audit['unclear'])}")
    if audit['unclear']:
        for perm in audit['unclear'][:10]:
            print(f"  - {perm[:80]}{'...' if len(perm) > 80 else ''}")
        if len(audit['unclear']) > 10:
            print(f"  ... and {len(audit['unclear']) - 10} more")
    else:
        print("  (none)")


def clean_project(project_name: str, dry_run: bool = True) -> dict:
    """Clean a project's settings by removing ONLY session vends."""
    settings_path = get_project_settings_path(project_name)
    settings = load_settings(settings_path)

    if not settings:
        return {"error": f"Could not load settings for {project_name}"}

    audit = audit_project(project_name)
    if "error" in audit:
        return audit

    # Build new allow list: everything EXCEPT session vends
    vend_perms = {perm for perm, _ in audit['session_vends']}
    original_allow = settings.get("permissions", {}).get("allow", [])
    new_allow = [p for p in original_allow if p not in vend_perms]

    removed_count = len(audit['session_vends'])

    if dry_run:
        print(f"\n## Dry Run: {project_name}")
        print(f"Would remove {removed_count} session vends")
        print(f"Would keep {len(new_allow)} permissions")
        if audit['session_vends']:
            print("Vends to remove:")
            for perm, reason in audit['session_vends'][:5]:
                print(f"  [{reason}] {perm[:60]}...")
            if len(audit['session_vends']) > 5:
                print(f"  ... and {len(audit['session_vends']) - 5} more")
        return {"removed": removed_count, "kept": len(new_allow), "dry_run": True}

    if removed_count == 0:
        print(f"\n## {project_name}: No session vends to remove")
        return {"removed": 0, "kept": len(new_allow), "dry_run": False}

    # Create backup
    backup_path = settings_path.with_suffix('.local.json.bak')
    shutil.copy(settings_path, backup_path)
    print(f"Backup created: {backup_path}")

    # Update settings
    settings["permissions"]["allow"] = new_allow
    save_settings(settings_path, settings)

    print(f"\n## Cleaned: {project_name}")
    print(f"Removed {removed_count} session vends")
    print(f"Kept {len(new_allow)} permissions")

    return {"removed": removed_count, "kept": len(new_allow), "dry_run": False}


def quick_check(project_name: str) -> int:
    """Quick check for cleanup integration. Returns exit code."""
    audit = audit_project(project_name)

    if "error" in audit:
        print(f"ERROR: {audit['error']}")
        return 2

    vend_count = len(audit['session_vends'])

    if vend_count > 5:
        print(f"Session vends detected: {vend_count}")
        print(f"Consider: poetry run python tools/agentos-permissions.py --clean --project {project_name}")
        return 1

    print(f"Permissions OK: {audit['total_allow']} total, {vend_count} vends (threshold: 5)")
    return 0


def merge_up(projects: list[str], dry_run: bool = True) -> dict:
    """
    Merge unique reusable patterns from project files into master.

    Only merges patterns that are:
    - NOT already in master
    - NOT session vends
    - Ideally reusable patterns (wildcards, Skills, etc.)

    Returns dict with merge statistics.
    """
    master_path = get_master_settings_path()
    master_settings = load_settings(master_path)

    if not master_settings:
        return {"error": f"Could not load master settings from {master_path}"}

    master_allow = set(master_settings.get("permissions", {}).get("allow", []))
    master_deny = set(master_settings.get("permissions", {}).get("deny", []))

    # Collect unique patterns from all projects
    to_merge_allow = {}  # permission -> (source_project, category)
    to_merge_deny = {}
    skipped_vends = []

    for project in projects:
        settings_path = get_project_settings_path(project)
        settings = load_settings(settings_path)

        if not settings:
            print(f"  Skipping {project}: no settings file")
            continue

        project_allow = settings.get("permissions", {}).get("allow", [])
        project_deny = settings.get("permissions", {}).get("deny", [])

        # Check allow list
        for perm in project_allow:
            if perm in master_allow:
                continue  # Already in master
            if perm in to_merge_allow:
                continue  # Already collected from another project

            # Check if it's a vend (skip vends)
            is_vend, vend_reason = is_session_vend(perm)
            if is_vend:
                skipped_vends.append((perm, project, vend_reason))
                continue

            # Categorize the permission
            is_reuse, category = is_reusable_pattern(perm)
            if is_reuse:
                to_merge_allow[perm] = (project, category)
            else:
                # Not clearly reusable, but not a vend either
                # Include with "unclear" category - user can review
                to_merge_allow[perm] = (project, "unclear")

        # Check deny list (simpler - just merge unique entries)
        for perm in project_deny:
            if perm not in master_deny and perm not in to_merge_deny:
                to_merge_deny[perm] = project

    # Print report
    print(f"\n{'='*60}")
    print("Merge Up Report")
    print(f"{'='*60}")
    print(f"Master: {master_path}")
    print(f"Projects scanned: {len(projects)}")
    print()

    print(f"### New Allow Patterns to Merge: {len(to_merge_allow)}")
    if to_merge_allow:
        # Group by category
        by_category = {}
        for perm, (proj, cat) in to_merge_allow.items():
            by_category.setdefault(cat, []).append((perm, proj))

        for cat, items in sorted(by_category.items()):
            print(f"\n  {cat}: {len(items)}")
            for perm, proj in items[:5]:
                print(f"    [{proj}] {perm[:60]}{'...' if len(perm) > 60 else ''}")
            if len(items) > 5:
                print(f"    ... and {len(items) - 5} more")
    else:
        print("  (none - master is up to date)")
    print()

    print(f"### New Deny Patterns to Merge: {len(to_merge_deny)}")
    if to_merge_deny:
        for perm, proj in list(to_merge_deny.items())[:5]:
            print(f"  [{proj}] {perm[:60]}{'...' if len(perm) > 60 else ''}")
        if len(to_merge_deny) > 5:
            print(f"  ... and {len(to_merge_deny) - 5} more")
    else:
        print("  (none)")
    print()

    print(f"### Skipped Session Vends: {len(skipped_vends)}")
    if skipped_vends:
        for perm, proj, reason in skipped_vends[:3]:
            print(f"  [{proj}] ({reason}) {perm[:50]}...")
        if len(skipped_vends) > 3:
            print(f"  ... and {len(skipped_vends) - 3} more")
    print()

    if dry_run:
        print("## DRY RUN - No changes made")
        print(f"Run without --dry-run to merge {len(to_merge_allow)} allow + {len(to_merge_deny)} deny patterns")
        return {
            "merged_allow": len(to_merge_allow),
            "merged_deny": len(to_merge_deny),
            "skipped_vends": len(skipped_vends),
            "dry_run": True
        }

    if not to_merge_allow and not to_merge_deny:
        print("## Nothing to merge - master is up to date")
        return {
            "merged_allow": 0,
            "merged_deny": 0,
            "skipped_vends": len(skipped_vends),
            "dry_run": False
        }

    # Create backup
    backup_path = master_path.with_suffix('.local.json.bak')
    shutil.copy(master_path, backup_path)
    print(f"Backup created: {backup_path}")

    # Merge into master
    new_allow = list(master_allow) + list(to_merge_allow.keys())
    new_deny = list(master_deny) + list(to_merge_deny.keys())

    master_settings["permissions"]["allow"] = new_allow
    master_settings["permissions"]["deny"] = new_deny
    save_settings(master_path, master_settings)

    print(f"\n## Merged into master:")
    print(f"  +{len(to_merge_allow)} allow patterns")
    print(f"  +{len(to_merge_deny)} deny patterns")
    print(f"  Master now has {len(new_allow)} allow, {len(new_deny)} deny")

    return {
        "merged_allow": len(to_merge_allow),
        "merged_deny": len(to_merge_deny),
        "skipped_vends": len(skipped_vends),
        "dry_run": False
    }


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
                           help="Remove ONLY session vends (keeps reusable patterns)")
    mode_group.add_argument("--quick-check", action="store_true",
                           help="Fast check for cleanup integration")
    mode_group.add_argument("--merge-up", action="store_true",
                           help="Collect unique reusable patterns from projects into master")
    mode_group.add_argument("--restore", action="store_true",
                           help="Restore from backup")

    parser.add_argument("--project", "-p",
                       help="Project name (e.g., Aletheia)")
    parser.add_argument("--all-projects", action="store_true",
                       help="Apply to all projects")
    parser.add_argument("--dry-run", "-n", action="store_true",
                       help="Show what would be done without modifying files")

    args = parser.parse_args()

    # Execute mode
    if args.audit:
        if args.all_projects:
            for project in find_all_projects():
                audit = audit_project(project)
                print_audit_report(audit)
        elif args.project:
            audit = audit_project(args.project)
            print_audit_report(audit)
        else:
            parser.error("--audit requires --project or --all-projects")

    elif args.clean:
        if args.project:
            clean_project(args.project, dry_run=args.dry_run)
        elif args.all_projects:
            for project in find_all_projects():
                clean_project(project, dry_run=args.dry_run)
        else:
            parser.error("--clean requires --project or --all-projects")

    elif args.quick_check:
        if not args.project:
            parser.error("--quick-check requires --project")
        exit_code = quick_check(args.project)
        sys.exit(exit_code)

    elif args.merge_up:
        if args.project:
            projects = [args.project]
        elif args.all_projects:
            projects = find_all_projects()
        else:
            parser.error("--merge-up requires --project or --all-projects")
        result = merge_up(projects, dry_run=args.dry_run)
        if "error" in result:
            print(f"ERROR: {result['error']}")
            sys.exit(1)

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

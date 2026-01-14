#!/usr/bin/env python3
"""
AgentOS Permission Propagation Tool

IMPORTANT: Claude Code permissions DO NOT INHERIT - they REPLACE.
When a project has its own permissions block, it completely overrides the parent.

This tool manages permissions across the master (user-level) and project-level files.

PROTECTED PERMISSIONS:
  - Bash(python:*) and Bash(python3:*) are NEVER allowed in deny lists
  - These are automatically removed during any clean operation

Modes:
  --audit        Read-only analysis of session vends
  --clean        Remove session vends AND protected deny entries
  --quick-check  Fast check for cleanup integration (exit code 0/1)
  --merge-up     LOCKED STEPS: clean all projects, then merge to master, then sync to Projects level
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

# Import AgentOS config for path management
try:
    from agentos_config import config
except ImportError:
    # Fallback if running outside AgentOS context
    config = None


# Permissions that should NEVER be in deny - too important to accidentally block
# This is a hard-coded protection that cannot be overridden
PROTECTED_FROM_DENY = [
    "Bash(python:*)",
    "Bash(python3:*)",
]

# Giant permission detection - permissions longer than this are almost certainly
# one-time garbage (e.g., Gemini prompts saved as permissions)
MAX_PERMISSION_LENGTH = 300

# Markers that indicate embedded content (prompts, scripts, etc.)
# If a permission contains any of these, it's corrupted/one-time
EMBEDDED_CONTENT_MARKERS = [
    '\n',           # Actual newlines (not escaped \n)
    '```',          # Markdown code blocks
    '\\`\\`\\`',    # Escaped markdown code blocks
    '## ',          # Markdown headers
    '\\n\\n',       # Double escaped newlines (embedded text)
    '[BLOCKING]',   # Review markers
    '[HIGH]',       # Review markers
    '[SUGGESTION]', # Review markers
    'QUESTION:',    # Prompt markers
    'CRITICAL INSTRUCTIONS:', # Prompt markers
    'OUTPUT FORMAT:', # Prompt markers
    'def ',         # Python function definitions (code in permission)
    'function ',    # JS function definitions
    'import ',      # Import statements
]


def get_projects_dir() -> Path:
    """Get the Projects directory path."""
    return Path.home() / "Projects"


def get_master_settings_path() -> Path:
    """Get path to master (user-level) settings.local.json."""
    return Path.home() / ".claude" / "settings.local.json"


def get_project_settings_path(project_name: str) -> Path:
    """Get path to project's settings.local.json."""
    return get_projects_dir() / project_name / ".claude" / "settings.local.json"


def get_projects_level_settings_path() -> Path:
    """Get path to Projects-level settings.local.json (~/Projects/.claude/)."""
    return get_projects_dir() / ".claude" / "settings.local.json"


def load_settings(path: Path) -> Optional[dict]:
    """Load settings.local.json from path."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {path}: {e}")
        return None


def validate_json_content(content: str) -> tuple[bool, str]:
    """
    Validate that content is valid JSON.

    Returns (is_valid, error_message) tuple.
    """
    try:
        json.loads(content)
        return True, ""
    except json.JSONDecodeError as e:
        return False, str(e)


def save_settings(path: Path, settings: dict):
    """
    Save settings to path with pretty formatting and JSON validation.

    Validates the JSON before writing to prevent corruption.
    """
    # Serialize to JSON first
    try:
        content = json.dumps(settings, indent=2) + "\n"
    except (TypeError, ValueError) as e:
        raise ValueError(f"Cannot serialize settings to JSON: {e}")

    # Validate the serialized JSON (paranoid check)
    valid, error = validate_json_content(content)
    if not valid:
        raise ValueError(f"Generated invalid JSON: {error}")

    # Write to temp file first, then rename (atomic on most systems)
    temp_path = path.with_suffix('.json.tmp')
    temp_path.write_text(content, encoding='utf-8')

    # Final validation of written file
    try:
        json.loads(temp_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        temp_path.unlink()
        raise ValueError(f"Written file failed validation: {e}")

    # Safe to move
    temp_path.replace(path)


def is_giant_permission(permission: str) -> tuple[bool, str]:
    """
    Detect permissions that are too long to be useful patterns.

    Permissions over MAX_PERMISSION_LENGTH chars are almost certainly one-time
    commands that got saved (like Gemini prompts passed as arguments).

    Returns (is_giant, reason) tuple.
    """
    if len(permission) > MAX_PERMISSION_LENGTH:
        return True, f"giant ({len(permission)} chars)"
    return False, ""


def has_embedded_content(permission: str) -> tuple[bool, str]:
    """
    Detect permissions with embedded prompts/scripts/content.

    These are corrupted permissions where a long prompt or script was
    accidentally saved as a permission string.

    Returns (has_embedded, reason) tuple.
    """
    for marker in EMBEDDED_CONTENT_MARKERS:
        if marker in permission:
            # Truncate marker for display if it's long
            display_marker = marker[:15] + '...' if len(marker) > 15 else marker
            # Escape for display
            display_marker = display_marker.replace('\n', '\\n')
            return True, f"embedded content ({display_marker})"
    return False, ""


def is_session_vend(permission: str) -> tuple[bool, str]:
    """
    Check if permission is a one-time session vend that should be removed.

    Returns (is_vend, reason) tuple.

    Session vends are SPECIFIC one-time permissions, not reusable patterns.
    We identify them by looking for:
    - Giant permissions (>300 chars) - almost certainly garbage
    - Embedded content (newlines, markdown, code) - corrupted permissions
    - Embedded commit messages (heredocs, specific text)
    - Specific file paths in commands (not wildcards)
    - One-time git operations (specific commits, pushes, merges)
    """

    # NEW: Check for giant permissions first (catches Gemini prompts, etc.)
    is_giant, giant_reason = is_giant_permission(permission)
    if is_giant:
        return True, giant_reason

    # NEW: Check for embedded content (newlines, markdown, code)
    has_embedded, embedded_reason = has_embedded_content(permission)
    if has_embedded:
        return True, embedded_reason

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
        # Use config for path if available, otherwise fallback to default
        projects_path = config.projects_root_unix() if config else "/c/Users/mcwiz/Projects"
        pattern = rf'Bash\(git -C {re.escape(projects_path)}/[^/]+-\d+ '
        if re.search(pattern, permission):
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


def clean_deny_list(deny_list: list) -> tuple[list, list]:
    """
    Remove protected permissions from deny list.

    Returns (cleaned_list, removed_list) tuple.
    """
    cleaned = []
    removed = []
    for perm in deny_list:
        if perm in PROTECTED_FROM_DENY:
            removed.append(perm)
        else:
            cleaned.append(perm)
    return cleaned, removed


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
    """Clean a project's settings by removing session vends and protected deny entries."""
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

    # Clean deny list: remove protected permissions
    original_deny = settings.get("permissions", {}).get("deny", [])
    new_deny, removed_from_deny = clean_deny_list(original_deny)

    removed_vends = len(audit['session_vends'])
    removed_protected = len(removed_from_deny)
    total_removed = removed_vends + removed_protected

    if dry_run:
        print(f"\n## Dry Run: {project_name}")
        print(f"Would remove {removed_vends} session vends")
        if removed_protected:
            print(f"Would remove {removed_protected} protected from deny: {removed_from_deny}")
        print(f"Would keep {len(new_allow)} permissions")
        if audit['session_vends']:
            print("Vends to remove:")
            for perm, reason in audit['session_vends'][:5]:
                print(f"  [{reason}] {perm[:60]}...")
            if len(audit['session_vends']) > 5:
                print(f"  ... and {len(audit['session_vends']) - 5} more")
        return {"removed": removed_vends, "removed_from_deny": removed_protected,
                "kept": len(new_allow), "dry_run": True}

    if total_removed == 0:
        print(f"\n## {project_name}: Nothing to clean")
        return {"removed": 0, "removed_from_deny": 0, "kept": len(new_allow), "dry_run": False}

    # Create backup
    backup_path = settings_path.with_suffix('.local.json.bak')
    shutil.copy(settings_path, backup_path)
    print(f"Backup created: {backup_path}")

    # Update settings
    settings["permissions"]["allow"] = new_allow
    settings["permissions"]["deny"] = new_deny
    save_settings(settings_path, settings)

    print(f"\n## Cleaned: {project_name}")
    print(f"Removed {removed_vends} session vends")
    if removed_protected:
        print(f"Removed {removed_protected} protected from deny: {removed_from_deny}")
    print(f"Kept {len(new_allow)} permissions")

    return {"removed": removed_vends, "removed_from_deny": removed_protected,
            "kept": len(new_allow), "dry_run": False}


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
        # Preview what clean/dedupe would do
        preview_allow = list(master_allow) + list(to_merge_allow.keys())
        vends_in_master = sum(1 for p in master_allow if is_session_vend(p)[0])
        dupes_count = len(preview_allow) - len(set(preview_allow))

        print("## DRY RUN - No changes made")
        print(f"Would merge: +{len(to_merge_allow)} allow, +{len(to_merge_deny)} deny")
        if vends_in_master:
            print(f"Would clean: -{vends_in_master} vends from master")
        if dupes_count:
            print(f"Would dedupe: -{dupes_count} duplicates")
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

    # Clean: remove vends from the merged result
    cleaned_allow = []
    removed_vends = []
    for perm in new_allow:
        is_vend, reason = is_session_vend(perm)
        if is_vend:
            removed_vends.append((perm, reason))
        else:
            cleaned_allow.append(perm)

    # Clean: remove protected permissions from deny
    cleaned_deny, removed_from_deny = clean_deny_list(new_deny)

    # Dedupe: remove duplicates while preserving order
    seen = set()
    deduped_allow = []
    for perm in cleaned_allow:
        if perm not in seen:
            seen.add(perm)
            deduped_allow.append(perm)

    seen_deny = set()
    deduped_deny = []
    for perm in cleaned_deny:
        if perm not in seen_deny:
            seen_deny.add(perm)
            deduped_deny.append(perm)

    duplicates_removed = len(cleaned_allow) - len(deduped_allow)

    master_settings["permissions"]["allow"] = deduped_allow
    master_settings["permissions"]["deny"] = deduped_deny
    save_settings(master_path, master_settings)

    print(f"\n## Merged into master:")
    print(f"  +{len(to_merge_allow)} allow patterns merged")
    print(f"  +{len(to_merge_deny)} deny patterns merged")
    if removed_vends:
        print(f"  -{len(removed_vends)} vends cleaned from master")
    if removed_from_deny:
        print(f"  -{len(removed_from_deny)} protected removed from deny: {removed_from_deny}")
    if duplicates_removed:
        print(f"  -{duplicates_removed} duplicates removed")
    print(f"  Master now has {len(deduped_allow)} allow, {len(deduped_deny)} deny")

    # Sync to Projects-level (so both are identical)
    projects_level_path = get_projects_level_settings_path()
    if projects_level_path.exists():
        shutil.copy(master_path, projects_level_path)
        print(f"\n## Synced to Projects level: {projects_level_path}")

    return {
        "merged_allow": len(to_merge_allow),
        "merged_deny": len(to_merge_deny),
        "skipped_vends": len(skipped_vends),
        "cleaned_vends": len(removed_vends),
        "cleaned_from_deny": len(removed_from_deny),
        "duplicates_removed": duplicates_removed,
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

        # LOCKED STEP: Always clean projects first before merge-up
        print("=" * 60)
        print("Step 1: Clean all projects (locked step)")
        print("=" * 60)
        for project in projects:
            clean_project(project, dry_run=args.dry_run)

        print("\n" + "=" * 60)
        print("Step 2: Merge up to master")
        print("=" * 60)
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

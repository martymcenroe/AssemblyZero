#!/usr/bin/env python
"""Unified Requirements Workflow CLI Runner.

Issue #101: Unified Requirements Workflow
Issue #230: Port --all and --resume flags

Usage:
    # Issue workflow (from brief)
    python tools/run_requirements_workflow.py --type issue --brief ideas/active/my-feature.md

    # LLD workflow (from GitHub issue)
    python tools/run_requirements_workflow.py --type lld --issue 42

    # Process ALL briefs in ideas/active/
    python tools/run_requirements_workflow.py --type issue --all

    # Resume interrupted workflow
    python tools/run_requirements_workflow.py --type issue --resume my-feature.md

    # With custom LLM providers
    python tools/run_requirements_workflow.py --type lld --issue 42 \
        --drafter gemini:2.5-flash --reviewer claude:sonnet

    # With specific gates
    python tools/run_requirements_workflow.py --type lld --issue 42 --gates draft

    # Fully automated (no human gates)
    python tools/run_requirements_workflow.py --type lld --issue 42 --gates none

    # Mock mode for testing
    python tools/run_requirements_workflow.py --type lld --issue 42 --mock
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from assemblyzero.workflows.requirements.audit import (
    AUDIT_ACTIVE_DIR,
    IDEAS_ACTIVE_DIR,
    check_existing_lld,
    generate_slug,
    shift_lineage_versions,
)
from assemblyzero.workflows.requirements.config import GateConfig
from assemblyzero.workflows.requirements.graph import create_requirements_graph
from assemblyzero.workflows.requirements.state import create_initial_state, RequirementsWorkflowState


# =============================================================================
# Checkpoint Database (SQLite)
# =============================================================================


def get_checkpoint_db_path() -> Path:
    """Get path to SQLite checkpoint database.

    Supports AGENTOS_WORKFLOW_DB environment variable for worktree isolation.

    Returns:
        Path to checkpoint database.
    """
    if db_path_env := os.environ.get("AGENTOS_WORKFLOW_DB"):
        db_path = Path(db_path_env)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    db_dir = Path.home() / ".assemblyzero"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "requirements_workflow.db"


def checkpoint_exists(slug: str) -> bool:
    """Check if checkpoint exists for a slug.

    Args:
        slug: Workflow slug to check.

    Returns:
        True if checkpoint exists.
    """
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = get_checkpoint_db_path()
        with SqliteSaver.from_conn_string(str(db_path)) as memory:
            config = {"configurable": {"thread_id": slug}}
            checkpoints = list(memory.list(config))
            return len(checkpoints) > 0
    except Exception:
        return False


def audit_dir_exists(slug: str, target_repo: Path) -> bool:
    """Check if audit directory exists for a slug.

    Args:
        slug: Workflow slug to check.
        target_repo: Target repository path.

    Returns:
        True if audit directory exists.
    """
    audit_dir = target_repo / AUDIT_ACTIVE_DIR / slug
    return audit_dir.exists()


def list_briefs(target_repo: Path) -> list[Path]:
    """List all brief files in ideas/active/.

    Args:
        target_repo: Target repository path.

    Returns:
        List of paths to brief files.
    """
    ideas_dir = target_repo / IDEAS_ACTIVE_DIR

    if not ideas_dir.exists():
        return []

    # Find all .md files, sorted alphabetically
    briefs = sorted(ideas_dir.glob("*.md"))
    return briefs


# =============================================================================
# Interactive Selection Functions
# =============================================================================


def extract_brief_title(brief_path: Path) -> str:
    """Extract title from brief file (first # heading).

    Args:
        brief_path: Path to brief file.

    Returns:
        Title string or "(no title)" if not found.
    """
    try:
        content = brief_path.read_text(encoding="utf-8", errors="replace")
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except (OSError, UnicodeDecodeError):
        pass
    return "(no title)"


def select_brief_file(target_repo: Path) -> str | None:
    """Interactively select a brief file from ideas/active/.

    Args:
        target_repo: Path to target repository.

    Returns:
        Selected brief file path (relative to repo), or None if cancelled.
    """
    ideas_dir = target_repo / "ideas" / "active"

    if not ideas_dir.exists():
        print(f"ERROR: ideas/active/ directory not found at {ideas_dir}")
        return None

    # Find markdown files
    briefs = sorted(ideas_dir.glob("*.md"))

    if not briefs:
        print("ERROR: No brief files (*.md) found in ideas/active/")
        return None

    # Display menu
    print(f"\n{'=' * 60}")
    print("Select Brief File from ideas/active/")
    print(f"{'=' * 60}")

    for i, brief in enumerate(briefs, 1):
        title = extract_brief_title(brief)
        print(f"  [{i}] {brief.name}")
        print(f"      {title}")

    print(f"\n  [q] Quit")
    print()

    # Test mode: auto-select first
    if os.environ.get("AGENTOS_TEST_MODE") == "1" and briefs:
        choice = "1"
        print(f"Select brief [1-{len(briefs)}, q]: {choice} (TEST MODE)")
        return str(briefs[0].relative_to(target_repo))

    while True:
        choice = input(f"Select brief [1-{len(briefs)}, q]: ").strip().lower()

        if choice == "q":
            return None

        try:
            idx = int(choice)
            if 1 <= idx <= len(briefs):
                return str(briefs[idx - 1].relative_to(target_repo))
            else:
                print(f"Invalid number. Enter 1-{len(briefs)} or q.")
        except ValueError:
            print("Invalid input. Enter a number or q.")


def select_github_issue(target_repo: Path) -> int | None:
    """Interactively select an open GitHub issue.

    Args:
        target_repo: Path to target repository (for gh CLI context).

    Returns:
        Selected issue number, or None if cancelled.
    """
    print("\nFetching open issues from GitHub...")

    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--json", "number,title,labels"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            cwd=str(target_repo),
        )

        if result.returncode != 0:
            print(f"ERROR: Failed to fetch issues: {result.stderr.strip()}")
            return None

        issues = json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        print("ERROR: Timeout fetching issues from GitHub")
        return None
    except FileNotFoundError:
        print("ERROR: gh CLI not found. Install GitHub CLI: https://cli.github.com/")
        return None
    except json.JSONDecodeError:
        print("ERROR: Failed to parse GitHub response")
        return None

    if not issues:
        print("No open issues found.")
        return None

    # Display menu
    print(f"\n{'=' * 60}")
    print("Select GitHub Issue")
    print(f"{'=' * 60}")

    for i, issue in enumerate(issues, 1):
        labels = ", ".join(label["name"] for label in issue.get("labels", []))
        label_str = f" [{labels}]" if labels else ""
        print(f"  [{i}] #{issue['number']}: {issue['title']}{label_str}")

    print(f"\n  [q] Quit")
    print()

    # Test mode: auto-select first
    if os.environ.get("AGENTOS_TEST_MODE") == "1" and issues:
        choice = "1"
        print(f"Select issue [1-{len(issues)}, q]: {choice} (TEST MODE)")
        return issues[0]["number"]

    while True:
        choice = input(f"Select issue [1-{len(issues)}, q]: ").strip().lower()

        if choice == "q":
            return None

        try:
            idx = int(choice)
            if 1 <= idx <= len(issues):
                return issues[idx - 1]["number"]
            else:
                print(f"Invalid number. Enter 1-{len(issues)} or q.")
        except ValueError:
            print("Invalid input. Enter a number or q.")


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Arguments to parse (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Unified Requirements Workflow for Issue and LLD creation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Issue workflow (from brief)
  python tools/run_requirements_workflow.py --type issue --brief ideas/active/my-feature.md

  # LLD workflow (from GitHub issue)
  python tools/run_requirements_workflow.py --type lld --issue 42

  # Custom LLM providers
  python tools/run_requirements_workflow.py --type lld --issue 42 \\
      --drafter gemini:2.5-flash --reviewer claude:sonnet

  # Fully automated
  python tools/run_requirements_workflow.py --type lld --issue 42 --gates none
        """,
    )

    # Required: workflow type
    parser.add_argument(
        "--type",
        choices=["issue", "lld"],
        required=True,
        help="Workflow type: 'issue' for brief->GitHub issue, 'lld' for issue->LLD",
    )

    # Input (mutually exclusive based on type)
    parser.add_argument(
        "--brief",
        help="Path to brief file (for --type issue)",
    )
    parser.add_argument(
        "--issue",
        type=int,
        help="GitHub issue number (for --type lld)",
    )
    parser.add_argument(
        "--select",
        action="store_true",
        help="Interactively select input file/issue",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process ALL briefs in ideas/active/ sequentially (issue workflow only)",
    )
    parser.add_argument(
        "--resume",
        type=str,
        metavar="FILE",
        help="Resume interrupted workflow by brief filename (issue workflow only)",
    )

    # LLM configuration
    parser.add_argument(
        "--drafter",
        default="claude:opus-4.5",
        help="Drafter LLM spec (default: claude:opus-4.5)",
    )
    parser.add_argument(
        "--reviewer",
        default="gemini:3-pro-preview",
        help="Reviewer LLM spec (default: gemini:3-pro-preview)",
    )

    # Gate configuration
    parser.add_argument(
        "--gates",
        default="draft,verdict",
        help="Human gates: draft,verdict | draft | verdict | none (default: draft,verdict)",
    )

    # Modes
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock providers for testing",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        dest="yes",
        help="Auto-confirm regeneration prompts (shifts existing lineage to n-1)",
    )

    # Paths
    parser.add_argument(
        "--repo",
        help="Target repository path (default: auto-detect from git)",
    )
    parser.add_argument(
        "--context",
        action="append",
        help="Additional context files (LLD workflow only, can be repeated)",
    )

    # Limits
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Maximum revision iterations (default: 20)",
    )

    return parser.parse_args(args)


def _detect_repo_from_path(file_path: Path) -> Path | None:
    """Walk up from file_path to find git repo root.

    Args:
        file_path: Path to a file or directory.

    Returns:
        Path to git repo root, or None if not in a git repo.
    """
    # Start from file's directory
    search_dir = file_path.parent if file_path.is_file() else file_path

    try:
        result = subprocess.run(
            ["git", "-C", str(search_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def _detect_repo_from_cwd() -> Path:
    """Detect git repo from current working directory.

    Returns:
        Path to git repo root, or CWD if not in a git repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return Path.cwd().resolve()


def resolve_roots(args: argparse.Namespace) -> tuple[Path, Path]:
    """Resolve assemblyzero_root and target_repo paths.

    assemblyzero_root: Where AssemblyZero is installed (for templates/prompts).
    target_repo: Where the work happens (outputs, context, gh CLI).

    Priority for target_repo:
    1. --repo flag (explicit override)
    2. Git repo containing the --brief file
    3. Git repo of current working directory
    4. Current working directory (fallback)

    Args:
        args: Parsed CLI arguments.

    Returns:
        Tuple of (assemblyzero_root, target_repo) as Path objects.
    """
    # assemblyzero_root: from env var or package location
    assemblyzero_root_env = os.environ.get("AGENTOS_ROOT")
    if assemblyzero_root_env:
        assemblyzero_root = Path(assemblyzero_root_env).resolve()
    else:
        # Default to parent of tools/ directory
        assemblyzero_root = Path(__file__).parent.parent.resolve()

    # target_repo: explicit --repo takes precedence
    if args.repo:
        target_repo = Path(args.repo).resolve()
    elif args.brief:
        # Try to detect repo from brief file path
        brief_path = Path(args.brief).resolve()
        detected = _detect_repo_from_path(brief_path)
        if detected:
            target_repo = detected
        else:
            # Brief not in a git repo, fall back to CWD
            target_repo = _detect_repo_from_cwd()
    else:
        # Fall back to CWD detection
        target_repo = _detect_repo_from_cwd()

    return assemblyzero_root, target_repo


def build_initial_state(
    args: argparse.Namespace,
    assemblyzero_root: Path,
    target_repo: Path,
) -> RequirementsWorkflowState:
    """Build initial workflow state from CLI arguments.

    Args:
        args: Parsed CLI arguments.
        assemblyzero_root: Path to AssemblyZero installation.
        target_repo: Path to target repository.

    Returns:
        Initialized RequirementsWorkflowState.
    """
    # Parse gate configuration
    gate_config = GateConfig.from_string(args.gates)

    # Build state based on workflow type
    if args.type == "issue":
        # Detect if brief is in ideas/active/ for cleanup after success
        source_idea = ""
        if args.brief:
            brief_path = Path(args.brief).resolve()
            ideas_active = (target_repo / "ideas" / "active").resolve()
            if brief_path.parent == ideas_active:
                source_idea = str(brief_path)

        return create_initial_state(
            workflow_type="issue",
            assemblyzero_root=str(assemblyzero_root),
            target_repo=str(target_repo),
            drafter=args.drafter,
            reviewer=args.reviewer,
            gates_draft=gate_config.draft_gate,
            gates_verdict=gate_config.verdict_gate,
            auto_mode=args.gates == "none",
            mock_mode=args.mock,
            max_iterations=args.max_iterations,
            brief_file=args.brief or "",
            source_idea=source_idea,
        )
    else:  # lld
        return create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(assemblyzero_root),
            target_repo=str(target_repo),
            drafter=args.drafter,
            reviewer=args.reviewer,
            gates_draft=gate_config.draft_gate,
            gates_verdict=gate_config.verdict_gate,
            auto_mode=args.gates == "none",
            mock_mode=args.mock,
            max_iterations=args.max_iterations,
            issue_number=args.issue or 0,
            context_files=args.context or [],
        )


def run_single_workflow(
    args: argparse.Namespace,
    assemblyzero_root: Path,
    target_repo: Path,
) -> int:
    """Run a single workflow instance.

    Args:
        args: Parsed CLI arguments.
        assemblyzero_root: Path to AssemblyZero installation.
        target_repo: Path to target repository.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    # Print header
    print_header(args)

    # Build initial state
    state = build_initial_state(args, assemblyzero_root, target_repo)

    if args.debug:
        print(f"DEBUG: Initial state keys: {list(state.keys())}")

    # Handle dry-run mode
    if args.dry_run:
        print("DRY RUN: Would execute workflow with the above configuration")
        print(f"  Workflow type: {state['workflow_type']}")
        print(f"  Audit dir would be created at: {target_repo}/docs/lineage/active/...")
        if state["workflow_type"] == "lld":
            print(f"  LLD would be saved to: {target_repo}/docs/lld/active/LLD-{args.issue:03d}.md")
        return 0

    # Create and run graph
    try:
        graph = create_requirements_graph()
        compiled = graph.compile()

        print("Starting workflow...")
        print()

        # Calculate recursion limit
        max_iters = state.get("max_iterations", 20)
        recursion_limit = (max_iters * 4) + 10

        final_state = compiled.invoke(
            state,
            config={"recursion_limit": recursion_limit}
        )

        print_result(final_state)

        if final_state.get("error_message"):
            return 1

        return 0

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user.")
        return 130

    except Exception as e:
        print(f"\nERROR: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def run_all_briefs(
    args: argparse.Namespace,
    assemblyzero_root: Path,
    target_repo: Path,
) -> int:
    """Process all briefs in ideas/active/ sequentially.

    Args:
        args: Parsed CLI arguments.
        assemblyzero_root: Path to AssemblyZero installation.
        target_repo: Path to target repository.

    Returns:
        Exit code (0 for success, non-zero for partial/full failure).
    """
    briefs = list_briefs(target_repo)

    if not briefs:
        print("No briefs found in ideas/active/")
        return 0

    total = len(briefs)
    processed = 0
    skipped = 0
    failed = 0

    print()
    print("=" * 60)
    print(f"BATCH PROCESSING - {total} briefs found")
    print("=" * 60)
    print()

    for i, brief_path in enumerate(briefs, 1):
        slug = generate_slug(str(brief_path))
        title = extract_brief_title(brief_path)

        print(f"\n[{i}/{total}] {brief_path.name}")
        print(f"        Slug: {slug}")
        print(f"        Title: {title}")

        # Check if already processed (audit dir exists)
        if audit_dir_exists(slug, target_repo):
            print("        Status: SKIPPED (audit directory exists)")
            skipped += 1
            continue

        # Update args with this brief
        args.brief = str(brief_path.relative_to(target_repo))

        print("        Status: PROCESSING...")
        exit_code = run_single_workflow(args, assemblyzero_root, target_repo)

        if exit_code == 0:
            processed += 1
            print(f"        Result: SUCCESS")
        else:
            failed += 1
            print(f"        Result: FAILED (exit code {exit_code})")

    # Print summary
    print()
    print("=" * 60)
    print("BATCH COMPLETE")
    print("=" * 60)
    print(f"  Total:     {total}")
    print(f"  Processed: {processed}")
    print(f"  Skipped:   {skipped}")
    print(f"  Failed:    {failed}")
    print("=" * 60)

    if failed > 0:
        return 1
    return 0


def run_resume_workflow(
    args: argparse.Namespace,
    assemblyzero_root: Path,
    target_repo: Path,
) -> int:
    """Resume an interrupted workflow.

    Args:
        args: Parsed CLI arguments (args.resume contains the brief filename).
        assemblyzero_root: Path to AssemblyZero installation.
        target_repo: Path to target repository.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    brief_file = args.resume
    slug = generate_slug(brief_file)

    print()
    print("=" * 60)
    print("RESUME WORKFLOW")
    print("=" * 60)
    print(f"Brief: {brief_file}")
    print(f"Slug:  {slug}")
    print("=" * 60)

    # Check if audit directory exists
    has_audit = audit_dir_exists(slug, target_repo)
    has_checkpoint = checkpoint_exists(slug)

    if not has_audit and not has_checkpoint:
        print()
        print("WARNING: No checkpoint or audit directory found for this brief.")
        print("         Starting fresh workflow instead.")
        print()

        # Resolve the brief path
        brief_path = Path(brief_file)
        if not brief_path.is_absolute():
            # Try ideas/active/ first
            ideas_path = target_repo / IDEAS_ACTIVE_DIR / brief_file
            if ideas_path.exists():
                brief_path = ideas_path
            else:
                brief_path = target_repo / brief_file

        if not brief_path.exists():
            print(f"ERROR: Brief file not found: {brief_file}")
            return 1

        args.brief = str(brief_path.relative_to(target_repo))
        return run_single_workflow(args, assemblyzero_root, target_repo)

    # Resume: set brief and run
    print()
    if has_checkpoint:
        print(f"Found checkpoint for '{slug}', resuming...")
    else:
        print(f"Found audit directory for '{slug}', resuming...")
    print()

    # Resolve the brief path
    brief_path = Path(brief_file)
    if not brief_path.is_absolute():
        ideas_path = target_repo / IDEAS_ACTIVE_DIR / brief_file
        if ideas_path.exists():
            brief_path = ideas_path
        else:
            brief_path = target_repo / brief_file

    if not brief_path.exists():
        print(f"ERROR: Brief file not found: {brief_file}")
        return 1

    args.brief = str(brief_path.relative_to(target_repo))
    return run_single_workflow(args, assemblyzero_root, target_repo)


def check_and_shift_existing_lld(
    issue_number: int,
    target_repo: Path,
    yes: bool = False,
) -> bool:
    """Check for existing LLD/lineage and handle regeneration.

    Per Standard 0012, before regenerating an LLD we must:
    1. Check for existing LLD file and lineage directory
    2. Warn the user and require YES confirmation (unless --yes)
    3. Shift lineage versions to preserve history

    Args:
        issue_number: GitHub issue number.
        target_repo: Target repository path.
        yes: If True, auto-confirm and skip interactive prompt.

    Returns:
        True if we should proceed with generation, False to abort.
    """
    existing = check_existing_lld(issue_number, target_repo)

    # Nothing exists - proceed with fresh generation
    if not existing["lld_exists"] and not existing["lineage_exists"]:
        return True

    # Something exists - warn user
    print()
    print("=" * 60)
    print(f"WARNING: LLD already exists for issue #{issue_number}")
    print("=" * 60)

    if existing["lld_exists"]:
        lld_rel = existing["lld_path"].relative_to(target_repo)
        print(f"  LLD file:  {lld_rel}")
    if existing["lineage_exists"]:
        lineage_rel = existing["lineage_path"].relative_to(target_repo)
        print(f"  Lineage:   {lineage_rel}/")

    print()
    print("Regenerating will:")
    if existing["lld_exists"]:
        print("  - Delete the existing LLD file")
    if existing["lineage_exists"]:
        print("  - Move existing lineage to {issue}-lld-n1")
    print()

    # Yes mode - proceed without confirmation
    if yes:
        print("--yes specified, auto-confirming...")
        print()
        operations = shift_lineage_versions(issue_number, target_repo)
        for op in operations:
            print(f"  {op}")
        print()
        return True

    # Interactive confirmation required
    # Test mode: auto-confirm
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        print("Type YES to proceed, or anything else to abort: YES (TEST MODE)")
        operations = shift_lineage_versions(issue_number, target_repo)
        for op in operations:
            print(f"  {op}")
        print()
        return True

    response = input("Type YES to proceed, or anything else to abort: ").strip()
    print()

    if response != "YES":
        print("Aborted by user.")
        return False

    # User confirmed - perform the shift
    operations = shift_lineage_versions(issue_number, target_repo)
    for op in operations:
        print(f"  {op}")
    print()
    return True


def print_header(args: argparse.Namespace) -> None:
    """Print workflow header.

    Args:
        args: Parsed CLI arguments.
    """
    print("=" * 60)
    print("Unified Requirements Workflow")
    print("=" * 60)
    print(f"Type:     {args.type}")
    if args.type == "issue":
        print(f"Brief:    {args.brief}")
    else:
        print(f"Issue:    #{args.issue}")
    print(f"Drafter:  {args.drafter}")
    print(f"Reviewer: {args.reviewer}")
    print(f"Gates:    {args.gates}")
    if args.mock:
        print("Mode:     MOCK (no API calls)")
    print("=" * 60)
    print()


def print_result(final_state: dict[str, Any]) -> None:
    """Print workflow result.

    Args:
        final_state: Final workflow state.
    """
    print()
    print("=" * 60)
    print("Workflow Complete")
    print("=" * 60)

    if final_state.get("error_message"):
        print(f"ERROR: {final_state['error_message']}")
        return

    workflow_type = final_state.get("workflow_type", "lld")

    if workflow_type == "issue":
        issue_url = final_state.get("issue_url", "")
        if issue_url:
            print(f"Issue URL: {issue_url}")
        else:
            print("Issue was not filed (manual mode or error)")
    else:
        lld_path = final_state.get("final_lld_path", "")
        if lld_path:
            print(f"LLD Path: {lld_path}")
            print(f"Status:   {final_state.get('lld_status', 'UNKNOWN')}")
        else:
            print("LLD was not saved (manual mode or error)")

    print(f"Drafts:   {final_state.get('draft_count', 0)}")
    print(f"Reviews:  {final_state.get('verdict_count', 0)}")
    print("=" * 60)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    args = parse_args()

    # Validate --all and --resume are only for issue workflow
    if args.all and args.type != "issue":
        print("ERROR: --all is only supported for issue workflow")
        return 1

    if args.resume and args.type != "issue":
        print("ERROR: --resume is only supported for issue workflow")
        return 1

    # Validate arguments
    if args.type == "issue" and not args.brief and not args.select and not args.all and not args.resume:
        print("ERROR: --brief, --select, --all, or --resume required for issue workflow")
        return 1

    if args.type == "lld" and not args.issue and not args.select:
        print("ERROR: --issue or --select required for LLD workflow")
        return 1

    # Resolve paths (needed for --select, --all, --resume)
    assemblyzero_root, target_repo = resolve_roots(args)

    if args.debug:
        print(f"DEBUG: assemblyzero_root = {assemblyzero_root}")
        print(f"DEBUG: target_repo = {target_repo}")

    # Handle --all: process all briefs
    if args.all:
        return run_all_briefs(args, assemblyzero_root, target_repo)

    # Handle --resume: resume interrupted workflow
    if args.resume:
        return run_resume_workflow(args, assemblyzero_root, target_repo)

    # Handle --select: interactive selection
    if args.select:
        if args.type == "issue":
            selected = select_brief_file(target_repo)
            if selected is None:
                print("Selection cancelled.")
                return 0
            args.brief = selected
        else:  # lld
            selected = select_github_issue(target_repo)
            if selected is None:
                print("Selection cancelled.")
                return 0
            args.issue = selected

    # Pre-generation check for LLD workflow (Standard 0012)
    if args.type == "lld" and args.issue:
        if not check_and_shift_existing_lld(args.issue, target_repo, args.yes):
            return 0  # User aborted

    # Run single workflow
    return run_single_workflow(args, assemblyzero_root, target_repo)


if __name__ == "__main__":
    sys.exit(main())
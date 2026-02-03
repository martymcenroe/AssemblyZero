#!/usr/bin/env python
"""Unified Requirements Workflow CLI Runner.

Issue #101: Unified Requirements Workflow

Usage:
    # Issue workflow (from brief)
    python tools/run_requirements_workflow.py --type issue --brief ideas/active/my-feature.md

    # LLD workflow (from GitHub issue)
    python tools/run_requirements_workflow.py --type lld --issue 42

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

from agentos.workflows.requirements.config import GateConfig
from agentos.workflows.requirements.graph import create_requirements_graph
from agentos.workflows.requirements.state import create_initial_state, RequirementsWorkflowState


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
    """Resolve agentos_root and target_repo paths.

    agentos_root: Where AgentOS is installed (for templates/prompts).
    target_repo: Where the work happens (outputs, context, gh CLI).

    Priority for target_repo:
    1. --repo flag (explicit override)
    2. Git repo containing the --brief file
    3. Git repo of current working directory
    4. Current working directory (fallback)

    Args:
        args: Parsed CLI arguments.

    Returns:
        Tuple of (agentos_root, target_repo) as Path objects.
    """
    # agentos_root: from env var or package location
    agentos_root_env = os.environ.get("AGENTOS_ROOT")
    if agentos_root_env:
        agentos_root = Path(agentos_root_env).resolve()
    else:
        # Default to parent of tools/ directory
        agentos_root = Path(__file__).parent.parent.resolve()

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

    return agentos_root, target_repo


def build_initial_state(
    args: argparse.Namespace,
    agentos_root: Path,
    target_repo: Path,
) -> RequirementsWorkflowState:
    """Build initial workflow state from CLI arguments.

    Args:
        args: Parsed CLI arguments.
        agentos_root: Path to AgentOS installation.
        target_repo: Path to target repository.

    Returns:
        Initialized RequirementsWorkflowState.
    """
    # Parse gate configuration
    gate_config = GateConfig.from_string(args.gates)

    # Build state based on workflow type
    if args.type == "issue":
        return create_initial_state(
            workflow_type="issue",
            agentos_root=str(agentos_root),
            target_repo=str(target_repo),
            drafter=args.drafter,
            reviewer=args.reviewer,
            gates_draft=gate_config.draft_gate,
            gates_verdict=gate_config.verdict_gate,
            auto_mode=args.gates == "none",
            mock_mode=args.mock,
            max_iterations=args.max_iterations,
            brief_file=args.brief or "",
        )
    else:  # lld
        return create_initial_state(
            workflow_type="lld",
            agentos_root=str(agentos_root),
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

    # Validate arguments
    if args.type == "issue" and not args.brief and not args.select:
        print("ERROR: --brief or --select required for issue workflow")
        return 1

    if args.type == "lld" and not args.issue and not args.select:
        print("ERROR: --issue or --select required for LLD workflow")
        return 1

    # Resolve paths (needed for --select)
    agentos_root, target_repo = resolve_roots(args)

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

    if args.debug:
        print(f"DEBUG: agentos_root = {agentos_root}")
        print(f"DEBUG: target_repo = {target_repo}")

    # Print header
    print_header(args)

    # Build initial state
    state = build_initial_state(args, agentos_root, target_repo)

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

        # Calculate recursion limit: each iteration needs ~3 nodes (draft, review, route)
        # Plus startup nodes. Add buffer for safety.
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


if __name__ == "__main__":
    sys.exit(main())
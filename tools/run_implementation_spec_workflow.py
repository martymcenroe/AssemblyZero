#!/usr/bin/env python3
"""CLI tool to run the Implementation Spec Workflow.

Issue #304: Implementation Readiness Review Workflow (LLD → Implementation Spec)

Transforms an approved LLD into an Implementation Spec with enough concrete
detail for autonomous AI implementation (>80% first-try success rate).

Workflow steps:
    N0: Load approved LLD and parse files list
    N1: Analyze codebase, extract current state excerpts
    N2: Generate Implementation Spec draft (Claude)
    N3: Validate mechanical completeness
    N4: Optional human review gate
    N5: Gemini readiness review
    N6: Finalize and write spec to docs/lld/drafts/

Usage:
    # Basic usage (auto mode, no human review)
    python tools/run_implementation_spec_workflow.py --issue 304

    # With human review gate enabled
    python tools/run_implementation_spec_workflow.py --issue 304 --review all

    # With human review at draft stage only
    python tools/run_implementation_spec_workflow.py --issue 304 --review draft

    # Cross-repo (generate spec for another project)
    python tools/run_implementation_spec_workflow.py --issue 42 --repo /path/to/other/repo

    # With explicit LLD path
    python tools/run_implementation_spec_workflow.py --issue 42 --lld docs/lld/active/LLD-042.md

    # Mock mode for testing
    python tools/run_implementation_spec_workflow.py --issue 42 --mock

    # Dry-run (preview execution plan)
    python tools/run_implementation_spec_workflow.py --issue 42 --dry-run
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Issue #120: Configure LangSmith tracing (enabled when LANGSMITH_API_KEY is set)
from assemblyzero.tracing import configure_langsmith

configure_langsmith()

from assemblyzero.workflows.implementation_spec.graph import (
    create_implementation_spec_graph,
)
from assemblyzero.workflows.implementation_spec.nodes.load_lld import find_lld_path
from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState


# =============================================================================
# Checkpoint Database (SQLite)
# =============================================================================


def get_checkpoint_db_path(issue_number: int = 0) -> Path:
    """Get path to SQLite checkpoint database.

    Priority:
    1. ASSEMBLYZERO_WORKFLOW_DB environment variable (explicit override)
    2. Per-issue database: impl_spec_{issue_number}.db
    3. Fallback: impl_spec_workflow.db (when issue_number is 0)

    Issue #379: Partition database by issue to prevent concurrent deadlocks.

    Args:
        issue_number: GitHub issue number for per-issue partitioning.

    Returns:
        Path to checkpoint database.
    """
    if db_path_env := os.environ.get("ASSEMBLYZERO_WORKFLOW_DB"):
        db_path = Path(db_path_env)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    db_dir = Path.home() / ".assemblyzero"
    db_dir.mkdir(parents=True, exist_ok=True)

    if issue_number > 0:
        return db_dir / f"impl_spec_{issue_number}.db"

    return db_dir / "impl_spec_workflow.db"


# =============================================================================
# CLI Argument Parsing
# =============================================================================


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser for the CLI.

    Separated from main() to enable testing.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description="Implementation Spec Workflow: Transform approved LLDs into Implementation Specs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate Implementation Spec from approved LLD
  python tools/run_implementation_spec_workflow.py --issue 304

  # With human review gate
  python tools/run_implementation_spec_workflow.py --issue 304 --review all

  # Cross-repo usage
  python tools/run_implementation_spec_workflow.py --issue 42 --repo /path/to/repo

  # Mock mode for testing
  python tools/run_implementation_spec_workflow.py --issue 42 --mock

  # Dry-run preview
  python tools/run_implementation_spec_workflow.py --issue 42 --dry-run
        """,
    )

    # Required arguments
    parser.add_argument(
        "--issue",
        type=int,
        required=True,
        help="GitHub issue number (must have approved LLD)",
    )

    # Optional arguments
    parser.add_argument(
        "--repo",
        type=str,
        help="Target repository path (default: auto-detect from git)",
    )
    parser.add_argument(
        "--lld",
        type=str,
        help="Path to LLD file (default: auto-detect from issue number)",
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

    # Review configuration (human gates)
    parser.add_argument(
        "--review",
        choices=["none", "draft", "verdict", "all"],
        default="none",
        help="Human review stages: none (default) | draft | verdict | all",
    )

    # Limits
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum revision iterations (default: 3)",
    )

    # Modes
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Mock mode - use fixtures instead of real APIs",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview execution plan without making API calls or writing files",
    )

    # Database
    parser.add_argument(
        "--db-path",
        type=str,
        help="Path to checkpoint database (overrides default per-issue partitioning)",
    )

    # Resume
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint",
    )

    return parser


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Arguments to parse (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = create_argument_parser()
    return parser.parse_args(args)


# =============================================================================
# Repository Detection
# =============================================================================


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
    2. Git repo of current working directory
    3. Current working directory (fallback)

    Args:
        args: Parsed CLI arguments.

    Returns:
        Tuple of (assemblyzero_root, target_repo) as Path objects.
    """
    # assemblyzero_root: from env var or package location
    assemblyzero_root_env = os.environ.get("ASSEMBLYZERO_ROOT")
    if assemblyzero_root_env:
        assemblyzero_root = Path(assemblyzero_root_env).resolve()
    else:
        # Default to parent of tools/ directory
        assemblyzero_root = Path(__file__).parent.parent.resolve()

    # target_repo: explicit --repo takes precedence
    if args.repo:
        target_repo = Path(args.repo).resolve()
    else:
        target_repo = _detect_repo_from_cwd()

    return assemblyzero_root, target_repo


# =============================================================================
# Review Configuration
# =============================================================================


def apply_review_config(args: argparse.Namespace) -> None:
    """Apply review configuration to determine human gate state.

    Sets human_gate_enabled based on --review flag:
    - "none": No human gate (default, fully automated)
    - "draft": Human reviews spec draft (N4 enabled)
    - "verdict": Human reviews after Gemini verdict (N4 enabled)
    - "all": Human gate enabled at all stages

    Args:
        args: Parsed arguments namespace. Modified in place.
    """
    if args.review in ("draft", "verdict", "all"):
        args.human_gate_enabled = True
    else:
        args.human_gate_enabled = False


# =============================================================================
# State Building
# =============================================================================


def build_initial_state(
    args: argparse.Namespace,
    assemblyzero_root: Path,
    target_repo: Path,
) -> ImplementationSpecState:
    """Build initial workflow state from CLI arguments.

    Args:
        args: Parsed CLI arguments.
        assemblyzero_root: Path to AssemblyZero installation.
        target_repo: Path to target repository.

    Returns:
        Initialized ImplementationSpecState.
    """
    # Resolve LLD path
    lld_path = ""
    if args.lld:
        lld_path = str(Path(args.lld).resolve())
    else:
        # Auto-discover LLD from issue number
        found = find_lld_path(args.issue, target_repo)
        if found:
            lld_path = str(found)

    state: ImplementationSpecState = {
        # Input
        "issue_number": args.issue,
        "lld_path": lld_path,
        "repo_root": str(target_repo),
        "assemblyzero_root": str(assemblyzero_root),
        # Loaded content
        "lld_content": "",
        "files_to_modify": [],
        # Codebase analysis
        "current_state_snapshots": {},
        "pattern_references": [],
        # Generated spec
        "spec_draft": "",
        "spec_path": "",
        # Validation
        "completeness_checks": [],
        "completeness_issues": [],
        "validation_passed": False,
        # Review
        "review_verdict": "BLOCKED",
        "review_feedback": "",
        "review_iteration": 0,
        # Workflow control
        "max_iterations": args.max_iterations,
        "human_gate_enabled": args.human_gate_enabled,
        # Routing
        "next_node": "",
        # Error handling
        "error_message": "",
    }

    return state


# =============================================================================
# Display Functions
# =============================================================================


def print_header(
    args: argparse.Namespace,
    assemblyzero_root: Path,
    target_repo: Path,
) -> None:
    """Print workflow header with configuration summary.

    Args:
        args: Parsed CLI arguments.
        assemblyzero_root: Path to AssemblyZero installation.
        target_repo: Path to target repository.
    """
    print()
    print("=" * 60)
    print("Implementation Spec Workflow")
    print("=" * 60)
    print(f"Issue:        #{args.issue}")
    print(f"Repository:   {target_repo}")
    print(f"Drafter:      {args.drafter}")
    print(f"Reviewer:     {args.reviewer}")
    print(f"Review mode:  {args.review}")
    print(f"Human gate:   {'enabled' if args.human_gate_enabled else 'disabled'}")
    print(f"Max iters:    {args.max_iterations}")
    if args.lld:
        print(f"LLD path:     {args.lld}")
    if args.mock:
        print("Mode:         MOCK (no API calls)")
    if args.dry_run:
        print("Mode:         DRY RUN")
    print("=" * 60)
    print()


def print_result(final_state: dict[str, Any]) -> None:
    """Print workflow result summary.

    Args:
        final_state: Final workflow state dictionary.
    """
    print()
    print("=" * 60)
    print("Workflow Complete")
    print("=" * 60)

    if final_state.get("error_message"):
        print(f"Status:   ERROR")
        print(f"Error:    {final_state['error_message']}")
    else:
        verdict = final_state.get("review_verdict", "UNKNOWN")
        spec_path = final_state.get("spec_path", "")
        iterations = final_state.get("review_iteration", 0)

        print(f"Status:   {verdict}")
        if spec_path:
            print(f"Spec:     {spec_path}")
        print(f"Iterations: {iterations}")

    print("=" * 60)


# =============================================================================
# Workflow Execution
# =============================================================================


def run_dry_run(
    args: argparse.Namespace,
    target_repo: Path,
) -> int:
    """Preview execution plan without running the workflow.

    Args:
        args: Parsed CLI arguments.
        target_repo: Path to target repository.

    Returns:
        Exit code (always 0 for dry-run).
    """
    # Try to find the LLD
    lld_path = None
    if args.lld:
        lld_path = Path(args.lld)
    else:
        lld_path = find_lld_path(args.issue, target_repo)

    lld_exists = lld_path is not None and lld_path.exists()

    print("[DRY RUN] Would execute:")
    print("  N0_load_lld -> N1_analyze_codebase -> N2_generate_spec -> N3_validate_completeness")
    print("  -> N4_human_gate (optional) -> N5_review_spec -> N6_finalize_spec")
    print()
    print(f"  LLD: {lld_path or '(auto-discover)'} ({'found' if lld_exists else 'NOT FOUND'})")
    print(f"  Output: docs/lld/drafts/spec-{args.issue:04d}-implementation-readiness.md")
    print(f"  Mock mode: {args.mock}")
    print(f"  Human gate: {'enabled' if args.human_gate_enabled else 'disabled'}")
    print(f"  Max iterations: {args.max_iterations}")
    print()
    print("[DRY RUN] No API calls made, no files modified.")
    return 0


def run_workflow(
    args: argparse.Namespace,
    assemblyzero_root: Path,
    target_repo: Path,
) -> int:
    """Run the Implementation Spec workflow.

    Args:
        args: Parsed CLI arguments.
        assemblyzero_root: Path to AssemblyZero installation.
        target_repo: Path to target repository.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    # Print header
    print_header(args, assemblyzero_root, target_repo)

    # Handle dry-run
    if args.dry_run:
        return run_dry_run(args, target_repo)

    # Build initial state
    state = build_initial_state(args, assemblyzero_root, target_repo)

    if args.debug:
        print(f"DEBUG: Initial state keys: {list(state.keys())}")
        print(f"DEBUG: lld_path = {state.get('lld_path', '')}")
        print(f"DEBUG: repo_root = {state.get('repo_root', '')}")

    # Create and run graph
    try:
        graph = create_implementation_spec_graph()

        # Calculate recursion limit: each iteration can touch N2->N3->N5 (3 nodes)
        # plus entry N0->N1 (2 nodes) and exit N6 (1 node), so budget generously
        max_iters = state.get("max_iterations", 3)
        recursion_limit = (max_iters * 6) + 20

        print("Starting workflow...")
        print()

        # Issue #393: Track final state from stream events instead of
        # get_state() which requires a checkpointer connected to the graph.
        # The graph is pre-compiled without a checkpointer.
        config = {
            "recursion_limit": recursion_limit,
        }

        final_state = dict(state)  # Start with initial state

        # Stream events for visibility
        for event in graph.stream(state, config):
            for node_name, node_output in event.items():
                if node_name == "__end__":
                    continue

                # Accumulate state updates from each node
                final_state.update(node_output)

                # Check for errors from nodes
                error = node_output.get("error_message", "")
                if error:
                    print(f"\n[ERROR] {error}")

        print_result(final_state)

        if final_state.get("error_message"):
            return 1

        return 0

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted. Use --resume to continue.")
        return 130

    except Exception as e:
        print(f"\nERROR: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        return 1


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    args = parse_args()

    # Apply review configuration
    apply_review_config(args)

    # Validate issue number
    if args.issue <= 0:
        print("ERROR: --issue must be a positive integer")
        return 1

    # Resolve paths
    assemblyzero_root, target_repo = resolve_roots(args)

    if args.debug:
        print(f"DEBUG: assemblyzero_root = {assemblyzero_root}")
        print(f"DEBUG: target_repo = {target_repo}")

    if not target_repo.exists():
        print(f"ERROR: Repository path does not exist: {target_repo}")
        return 1

    # Set environment variables for mode flags
    if not args.human_gate_enabled:
        os.environ["ASSEMBLYZERO_AUTO_MODE"] = "1"

    # Run workflow
    return run_workflow(args, assemblyzero_root, target_repo)


if __name__ == "__main__":
    sys.exit(main())
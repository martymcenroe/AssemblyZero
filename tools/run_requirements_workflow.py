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
        help="Workflow type: 'issue' for brief→GitHub issue, 'lld' for issue→LLD",
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
        "--resume",
        action="store_true",
        help="Resume from previous checkpoint",
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


def resolve_roots(args: argparse.Namespace) -> tuple[Path, Path]:
    """Resolve agentos_root and target_repo paths.

    agentos_root: Where AgentOS is installed (for templates/prompts).
    target_repo: Where the work happens (outputs, context, gh CLI).

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

    # target_repo: from --repo or auto-detect from git
    if args.repo:
        target_repo = Path(args.repo).resolve()
    else:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
            )
            if result.returncode == 0:
                target_repo = Path(result.stdout.strip()).resolve()
            else:
                # Fall back to current directory
                target_repo = Path.cwd().resolve()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            target_repo = Path.cwd().resolve()

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
        lld_path = final_state.get("lld_path", "")
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

    # Resolve paths
    agentos_root, target_repo = resolve_roots(args)

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
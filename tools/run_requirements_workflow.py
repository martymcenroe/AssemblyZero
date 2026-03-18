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

    # With human review at draft stage
    python tools/run_requirements_workflow.py --type lld --issue 42 --review draft

    # With human review at all stages
    python tools/run_requirements_workflow.py --type lld --issue 42 --review all

    # Mock mode for testing
    python tools/run_requirements_workflow.py --type lld --issue 42 --mock
"""

import argparse
import atexit
import json
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

# Issue #424: Telemetry instrumentation
from assemblyzero.telemetry import emit, flush, track_tool
atexit.register(flush)

from assemblyzero.workflows.requirements.audit import (
    AUDIT_ACTIVE_DIR,
    IDEAS_ACTIVE_DIR,
    LLD_ACTIVE_DIR,
    check_existing_lld,
    generate_slug,
    next_file_number,
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

    Supports ASSEMBLYZERO_WORKFLOW_DB environment variable for worktree isolation.

    Returns:
        Path to checkpoint database.
    """
    if db_path_env := os.environ.get("ASSEMBLYZERO_WORKFLOW_DB"):
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
    if os.environ.get("ASSEMBLYZERO_TEST_MODE") == "1" and briefs:
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
    if os.environ.get("ASSEMBLYZERO_TEST_MODE") == "1" and issues:
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

  # With human review at draft and verdict stages
  python tools/run_requirements_workflow.py --type lld --issue 42 --review all
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
    parser.add_argument(
        "--resume-review",
        action="store_true",
        dest="resume_review",
        help="Resume LLD workflow at review stage, reusing existing validated draft (Issue #536)",
    )

    # LLM configuration
    parser.add_argument(
        "--drafter",
        default="claude:sonnet",
        help="Drafter LLM spec (default: claude:sonnet)",
    )
    parser.add_argument(
        "--reviewer",
        default="claude:opus",
        help="Reviewer LLM spec (default: claude:opus)",
    )
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "max"],
        default="max",
        help="Claude reviewer effort level (default: max)",
    )

    # Review configuration (human gates)
    parser.add_argument(
        "--review",
        default="none",
        dest="review",
        help="Human review stages: none (default) | draft | verdict | all",
    )
    parser.add_argument(
        "--gates",
        default=None,
        dest="gates_deprecated",
        help=argparse.SUPPRESS,  # Hidden deprecated alias for --review
    )

    # Issue #773: API policy
    parser.add_argument(
        "--allow-api",
        action="store_true",
        dest="allow_api",
        help="Allow paid Anthropic API calls (default: blocked, uses claude -p via Max subscription)",
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
    parser.add_argument(
        "--budget",
        type=float,
        default=3.0,
        help="Max API cost in USD before halting (default $3.00, 0=unlimited)",
    )

    # Issue #517: Global workflow timeout
    from assemblyzero.utils.workflow_timeout import add_timeout_argument
    add_timeout_argument(parser)

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
    assemblyzero_root_env = os.environ.get("ASSEMBLYZERO_ROOT")
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
    gate_config = GateConfig.from_string(args.review)

    # Build state based on workflow type
    if args.type == "issue":
        # Detect if brief is in ideas/active/ for cleanup after success
        source_idea = ""
        if args.brief:
            brief_path = Path(args.brief).resolve()
            ideas_active = (target_repo / "ideas" / "active").resolve()
            if brief_path.parent == ideas_active:
                source_idea = str(brief_path)

        state = create_initial_state(
            workflow_type="issue",
            assemblyzero_root=str(assemblyzero_root),
            target_repo=str(target_repo),
            drafter=args.drafter,
            reviewer=args.reviewer,
            gates_draft=gate_config.draft_gate,
            gates_verdict=gate_config.verdict_gate,
            auto_mode=args.review == "none",
            mock_mode=args.mock,
            max_iterations=args.max_iterations,
            effort=getattr(args, "effort", "max"),
            brief_file=args.brief or "",
            source_idea=source_idea,
        )
    else:  # lld
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(assemblyzero_root),
            target_repo=str(target_repo),
            drafter=args.drafter,
            reviewer=args.reviewer,
            gates_draft=gate_config.draft_gate,
            gates_verdict=gate_config.verdict_gate,
            auto_mode=args.review == "none",
            mock_mode=args.mock,
            max_iterations=args.max_iterations,
            effort=getattr(args, "effort", "max"),
            issue_number=args.issue or 0,
            context_files=args.context or [],
        )

    # Issue #476: API cost budget
    state["cost_budget_usd"] = getattr(args, "budget", 5.0)

    return state


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
    # Issue #517: Global workflow timeout
    from assemblyzero.utils.workflow_timeout import WorkflowTimeout

    try:
      with WorkflowTimeout(minutes=args.timeout):
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


def run_resume_review(
    args: argparse.Namespace,
    assemblyzero_root: Path,
    target_repo: Path,
) -> int:
    """Resume an LLD workflow at the review stage, reusing the existing draft.

    Issue #536: When a workflow halts during review (e.g., Gemini 503/529),
    the draft is already validated. Re-running with --yes would discard it
    and restart from scratch. This function loads the existing draft and
    invokes the graph starting at N3 (review).

    Args:
        args: Parsed CLI arguments.
        assemblyzero_root: Path to AssemblyZero installation.
        target_repo: Path to target repository.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    issue_number = args.issue

    # Check that a resumable draft exists
    resume_info = _draft_is_resumable(issue_number, target_repo)
    if not resume_info:
        print(f"ERROR: No resumable draft found for issue #{issue_number}")
        print("  A resumable draft requires lineage with a draft file but no subsequent verdict.")
        return 1

    print_header(args)
    print(f"[RESUME] Resuming at review with existing draft from:")
    print(f"  {resume_info['draft_path'].relative_to(target_repo)}")
    print(f"  Draft iterations: {resume_info['draft_count']}")
    print()

    # Build initial state and inject the existing draft
    state = build_initial_state(args, assemblyzero_root, target_repo)
    state["current_draft"] = resume_info["draft_content"]
    state["current_draft_path"] = str(resume_info["draft_path"])
    state["audit_dir"] = str(resume_info["lineage_dir"])
    state["draft_count"] = resume_info["draft_count"]
    state["iteration_count"] = resume_info["draft_count"]

    # Load issue content from lineage (001-issue.md)
    issue_file = resume_info["lineage_dir"] / "001-issue.md"
    if issue_file.exists():
        issue_content = issue_file.read_text(encoding="utf-8")
        # Parse title from content
        for line in issue_content.splitlines():
            if line.startswith("# Issue #"):
                state["issue_title"] = line.split(":", 1)[-1].strip() if ":" in line else ""
                break
        state["issue_body"] = issue_content

    if args.debug:
        print(f"DEBUG: Resume state keys: {list(state.keys())}")
        print(f"DEBUG: draft_count={state['draft_count']}, audit_dir={state['audit_dir']}")

    # Create and run graph starting from review (N3)
    from assemblyzero.utils.workflow_timeout import WorkflowTimeout

    try:
        with WorkflowTimeout(minutes=args.timeout):
            graph = create_requirements_graph()
            compiled = graph.compile()

            # Set the graph to start from N3 (review) by running from START
            # but with all pre-review state already populated.
            # The graph will: N0 (load_input) -> N0b -> N1 (generate_draft) -> ...
            # But since current_draft is already set, we need to skip to review.
            #
            # Instead of modifying the graph structure, we use a simpler approach:
            # set lld_status to trigger review routing. The load_input and
            # generate_draft nodes check for existing content.
            #
            # Actually, the simplest approach: create a review-only subgraph.
            from assemblyzero.workflows.requirements.graph import (
                N3_REVIEW,
                N4_HUMAN_GATE_VERDICT,
                N5_FINALIZE,
                N1_GENERATE_DRAFT,
                HALT,
                route_after_review,
                route_from_human_gate_verdict,
            )
            from assemblyzero.core.halt_node import create_halt_node
            from langgraph.graph import END, START, StateGraph
            from assemblyzero.workflows.requirements.state import RequirementsWorkflowState
            from assemblyzero.workflows.requirements.nodes import (
                review,
                human_gate_verdict,
                finalize,
                generate_draft,
            )

            resume_graph = StateGraph(RequirementsWorkflowState)
            resume_graph.add_node(N3_REVIEW, review)
            resume_graph.add_node(N4_HUMAN_GATE_VERDICT, human_gate_verdict)
            resume_graph.add_node(N5_FINALIZE, finalize)
            resume_graph.add_node(N1_GENERATE_DRAFT, generate_draft)
            resume_graph.add_node(HALT, create_halt_node("requirements"))

            # START -> N3 (review)
            resume_graph.add_edge(START, N3_REVIEW)
            resume_graph.add_edge(HALT, END)
            resume_graph.add_edge(N5_FINALIZE, END)

            # N3 routing (same as main graph)
            resume_graph.add_conditional_edges(
                N3_REVIEW,
                route_after_review,
                {
                    "N4_human_gate_verdict": N4_HUMAN_GATE_VERDICT,
                    "N5_finalize": N5_FINALIZE,
                    "N1_generate_draft": N1_GENERATE_DRAFT,
                    "N3_review": N3_REVIEW,
                    "HALT": HALT,
                },
            )

            # If review sends back to draft, re-enter the full draft->review loop
            from assemblyzero.workflows.requirements.graph import (
                N1_5_VALIDATE_MECHANICAL,
                N1B_VALIDATE_TEST_PLAN,
                N_PONDER,
                N2_HUMAN_GATE_DRAFT,
                route_after_generate_draft,
                route_after_validate_mechanical,
                route_after_validate_test_plan,
                route_after_ponder,
                route_from_human_gate_draft,
            )
            from assemblyzero.workflows.requirements.nodes import (
                validate_lld_mechanical,
                validate_test_plan_node,
                ponder_stibbons_node,
                human_gate_draft,
            )

            resume_graph.add_node(N1_5_VALIDATE_MECHANICAL, validate_lld_mechanical)
            resume_graph.add_node(N1B_VALIDATE_TEST_PLAN, validate_test_plan_node)
            resume_graph.add_node(N_PONDER, ponder_stibbons_node)
            resume_graph.add_node(N2_HUMAN_GATE_DRAFT, human_gate_draft)

            resume_graph.add_conditional_edges(
                N1_GENERATE_DRAFT,
                route_after_generate_draft,
                {
                    "N1_5_validate_mechanical": N1_5_VALIDATE_MECHANICAL,
                    "N2_human_gate_draft": N2_HUMAN_GATE_DRAFT,
                    "N3_review": N3_REVIEW,
                    "HALT": HALT,
                },
            )
            resume_graph.add_conditional_edges(
                N1_5_VALIDATE_MECHANICAL,
                route_after_validate_mechanical,
                {
                    "N1b_validate_test_plan": N1B_VALIDATE_TEST_PLAN,
                    "N1_generate_draft": N1_GENERATE_DRAFT,
                    "HALT": HALT,
                },
            )
            resume_graph.add_conditional_edges(
                N1B_VALIDATE_TEST_PLAN,
                route_after_validate_test_plan,
                {
                    "N_ponder_stibbons": N_PONDER,
                    "N1_generate_draft": N1_GENERATE_DRAFT,
                    "HALT": HALT,
                },
            )
            resume_graph.add_conditional_edges(
                N_PONDER,
                route_after_ponder,
                {
                    "N2_human_gate_draft": N2_HUMAN_GATE_DRAFT,
                    "N3_review": N3_REVIEW,
                },
            )
            resume_graph.add_conditional_edges(
                N2_HUMAN_GATE_DRAFT,
                route_from_human_gate_draft,
                {
                    "N3_review": N3_REVIEW,
                    "N1_generate_draft": N1_GENERATE_DRAFT,
                    "END": END,
                },
            )
            resume_graph.add_conditional_edges(
                N4_HUMAN_GATE_VERDICT,
                route_from_human_gate_verdict,
                {
                    "N5_finalize": N5_FINALIZE,
                    "N1_generate_draft": N1_GENERATE_DRAFT,
                    "END": END,
                },
            )

            compiled_resume = resume_graph.compile()

            print("Starting review (resume mode)...")
            print()

            max_iters = state.get("max_iterations", 20)
            recursion_limit = (max_iters * 4) + 10

            final_state = compiled_resume.invoke(
                state,
                config={"recursion_limit": recursion_limit},
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


def _draft_is_resumable(issue_number: int, target_repo: Path) -> dict | None:
    """Check if an LLD lineage has a draft ready for review resume.

    Issue #536: When a workflow halts during review (e.g., Gemini 503/529),
    the lineage contains a draft but no verdict. Re-running with --yes would
    discard the draft and restart from scratch, wasting time and money.

    A draft is resumable if:
    1. The lineage directory exists with at least one draft file
    2. The last artifact is a draft (no verdict follows it)

    Args:
        issue_number: GitHub issue number.
        target_repo: Target repository path.

    Returns:
        Dict with resume info if resumable, None otherwise.
        Keys: lineage_dir, draft_path, draft_content, draft_count
    """
    import re

    lineage_dir = target_repo / AUDIT_ACTIVE_DIR / f"{issue_number}-lld"
    if not lineage_dir.exists():
        return None

    # Enumerate lineage files and find the last draft
    files = sorted(lineage_dir.glob("*.md"))
    if not files:
        return None

    last_draft_path = None
    last_draft_num = 0
    last_verdict_num = 0
    draft_count = 0

    for f in files:
        match = re.match(r"^(\d{3})-(.+)$", f.name)
        if not match:
            continue
        num = int(match.group(1))
        suffix = match.group(2)

        if suffix == "draft.md":
            last_draft_path = f
            last_draft_num = num
            draft_count += 1
        elif suffix == "verdict.md":
            last_verdict_num = num
        elif suffix == "final.md":
            # Already finalized — not resumable
            return None

    # Resumable if we have a draft and no verdict follows it
    if last_draft_path and last_draft_num > last_verdict_num:
        draft_content = last_draft_path.read_text(encoding="utf-8")
        return {
            "lineage_dir": lineage_dir,
            "draft_path": last_draft_path,
            "draft_content": draft_content,
            "draft_count": draft_count,
        }

    return None


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

    # Issue #536: Check if the draft is resumable before offering to discard
    resume_info = _draft_is_resumable(issue_number, target_repo)
    if resume_info and not existing["lld_exists"]:
        # Draft exists but no final LLD — hint about --resume-review
        lineage_rel = resume_info["lineage_dir"].relative_to(target_repo)
        draft_rel = resume_info["draft_path"].relative_to(target_repo)
        print()
        print("=" * 60)
        print(f"RESUMABLE: Validated draft found for issue #{issue_number}")
        print("=" * 60)
        print(f"  Lineage:  {lineage_rel}/")
        print(f"  Draft:    {draft_rel}")
        print(f"  Drafts:   {resume_info['draft_count']}")
        print()
        print("  To resume review with existing draft: --resume-review")
        print("  To re-draft from scratch:             --yes (discards existing draft)")
        print()
        if not yes:
            return False  # Abort — user should choose explicitly

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
    if os.environ.get("ASSEMBLYZERO_TEST_MODE") == "1":
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
    print(f"Review:   {args.review}")
    if args.mock:
        print("Mode:     MOCK (no API calls)")
    if getattr(args, "resume_review", False):
        print("Mode:     RESUME-REVIEW (skipping draft, starting at review)")
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

    # Issue #511: Display cost summary and emit telemetry
    node_costs = final_state.get("node_costs", {})
    if node_costs:
        total = sum(node_costs.values())
        print(f"Cost:     ${total:.4f}")
        for node_name, cost in sorted(node_costs.items()):
            if cost > 0:
                print(f"  {node_name}: ${cost:.4f}")
        emit(
            "workflow.cost",
            repo="AssemblyZero",
            metadata={
                "workflow_type": final_state.get("workflow_type", "unknown"),
                "issue_number": final_state.get("issue_number", 0),
                "total_cost_usd": round(total, 6),
                "cost_by_node": {k: round(v, 6) for k, v in node_costs.items()},
            },
        )

    print("=" * 60)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    args = parse_args()

    # Issue #773: Set API policy before any providers are created
    from assemblyzero.core.llm_provider import set_api_policy
    set_api_policy(args.allow_api)

    # Handle deprecated --gates flag (bridge to --review)
    if args.gates_deprecated is not None:
        print(
            "WARNING: --gates is deprecated. Use --review instead.",
            file=sys.stderr,
        )
        # Map old values to new: "draft,verdict" -> "all", others pass through
        gates_val = args.gates_deprecated.lower().strip()
        if gates_val in ("draft,verdict", "verdict,draft", "both"):
            args.review = "all"
        else:
            args.review = gates_val

    # Validate --all and --resume are only for issue workflow
    if args.all and args.type != "issue":
        print("ERROR: --all is only supported for issue workflow")
        return 1

    if args.resume and args.type != "issue":
        print("ERROR: --resume is only supported for issue workflow")
        return 1

    # Issue #536: Validate --resume-review is only for LLD workflow
    if getattr(args, "resume_review", False) and args.type != "lld":
        print("ERROR: --resume-review is only supported for LLD workflow")
        return 1

    if getattr(args, "resume_review", False) and not args.issue:
        print("ERROR: --resume-review requires --issue")
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

    # Issue #536: Handle --resume-review: resume LLD at review stage
    if getattr(args, "resume_review", False):
        return run_resume_review(args, assemblyzero_root, target_repo)

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
    with track_tool("run_requirements_workflow", repo="AssemblyZero"):
        sys.exit(main())
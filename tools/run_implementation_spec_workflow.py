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
import traceback
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

#: This entry point, as its alerts and its start-up check name it.
ENTRY = "tools/run_implementation_spec_workflow.py"


class RunFailed(Exception):
    """A failure this entry point names itself (ADR 0236, #4098).

    Raised for what the tool owns: a bad argument, a target it cannot
    resolve, an LLD that is not there, a refused resume, a run that ended in
    an error the HALT node never saw. ``main``'s one handler prints it as one
    ERROR line on stderr, alerts the operator, and returns 1; any other
    exception gets its traceback as well.
    """


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

    # LLM configuration. #3563: every seat's model comes from the run's model
    # profile (--models; default gemini.toml, the 2026-09-24 law, #3517).
    # --drafter and --reviewer are per-seat overrides; --seat is the general form.
    from assemblyzero.core.seats import add_profile_arguments

    add_profile_arguments(parser)
    parser.add_argument(
        "--drafter",
        default=None,
        help="Override the spec.draft seat. Default: the profile's",
    )
    parser.add_argument(
        "--reviewer",
        default=None,
        help="Override the spec.review seat. Default: the profile's",
    )
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "max"],
        default=None,
        help="Effort for every seat, over the profile's (default: the profile's, max)",
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

    # Issue #476: Cost budget
    parser.add_argument(
        "--budget",
        type=float,
        default=3.0,
        help="Max API cost in USD before halting (default $3.00, 0=unlimited)",
    )

    # Issue #825: Worktree isolation
    parser.add_argument(
        "--no-worktree",
        action="store_true",
        help="Allow running in the AssemblyZero root directory (not recommended)",
    )

    # #2570: a resume verifies the halt's contract first and refuses by
    # name when the world changed. This flag is the explicit, logged
    # override for a deliberate change (the operator edited the LLD on
    # purpose); it is never the default.
    parser.add_argument(
        "--accept-changed-inputs",
        action="store_true",
        help=(
            "Proceed even when inputs changed since the last halt's resume "
            "contract (#2570). The acceptance is printed, never silent."
        ),
    )

    # Issue #517: Global workflow timeout
    from assemblyzero.utils.workflow_timeout import add_timeout_argument
    add_timeout_argument(parser)

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
        Path to git repo root.

    Raises:
        RunFailed: git timed out or is not installed (ledger 0908, line 293),
            or the working directory is in no repository (line 296). Each
            used to return the working directory as the target.
    """
    cwd = Path.cwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunFailed(
            f"git rev-parse --show-toplevel timed out after {exc.timeout}s in {cwd}"
        ) from exc
    except FileNotFoundError as exc:
        raise RunFailed(
            f"git not found: cannot find the repository that holds the working "
            f"directory {cwd}; pass --repo"
        ) from exc
    if result.returncode != 0:
        raise RunFailed(
            f"no --repo was given and the working directory {cwd} is in no git "
            f"repository (git rev-parse exited {result.returncode}): "
            f"{(result.stderr or '').strip()}. Pass --repo with the target repository"
        )
    return Path(result.stdout.strip()).resolve()


def resolve_roots(args: argparse.Namespace) -> tuple[Path, Path]:
    """Resolve assemblyzero_root and target_repo paths.

    assemblyzero_root: Where AssemblyZero is installed (for templates/prompts).
    target_repo: Where the work happens (outputs, context, gh CLI).

    Priority for target_repo:
    1. --repo flag (explicit override)
    2. Git repo of current working directory

    A working directory in no repository is refused rather than used as the
    target (ledger 0908, line 296).

    Args:
        args: Parsed CLI arguments.

    Returns:
        Tuple of (assemblyzero_root, target_repo) as Path objects.

    Raises:
        RunFailed: the target cannot be resolved, or it is the AssemblyZero
            root without --no-worktree.
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

    # Issue #825: Enforce worktree isolation for AssemblyZero itself.
    # Ledger 0908, line 335: this printed on stdout and exited 1, no alert.
    if target_repo.resolve() == assemblyzero_root.resolve():
        if not getattr(args, "no_worktree", False):
            raise RunFailed(
                f"refusing to run in the AssemblyZero root {assemblyzero_root}: a "
                "run there pollutes its branches. Create a worktree (git worktree "
                "add --relative-paths ../AssemblyZero-ISSUE -b branch-name) and pass "
                "--repo ../AssemblyZero-ISSUE, or use --no-worktree if you must run on main"
            )

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


def resolve_lld_path(args: argparse.Namespace, target_repo: Path) -> Path:
    """The LLD this run reads: --lld (relative to the target unless
    absolute), or the one find_lld_path discovers for the issue.

    Raises:
        RunFailed: there is no such file (ledger 0908, line 414). The path
            used to be left empty and the workflow started anyway.
    """
    if args.lld:
        p = Path(args.lld)
        lld = (p if p.is_absolute() else target_repo / p).resolve()
        if not lld.is_file():
            raise RunFailed(f"--lld {args.lld}: no LLD file at {lld}")
        return lld
    found = find_lld_path(args.issue, target_repo)
    if not found:
        raise RunFailed(
            f"no LLD for issue #{args.issue} under {target_repo}: the spec "
            "workflow needs an approved LLD (pass --lld to name one)"
        )
    return Path(found)


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

    Raises:
        RunFailed: there is no LLD to read (``resolve_lld_path``).
    """
    # #3563: the run's model profile, snapshotted into state below.
    from assemblyzero.core.seats import describe, profile_from_args, seat_in

    profile = profile_from_args(
        args, target_repo, {"drafter": ("spec.draft",), "reviewer": ("spec.review",)},
    )

    # Resolve LLD path (raises when there is none, ledger 0908, line 414)
    lld_path = str(resolve_lld_path(args, target_repo))

    # Issue #525: Create lineage dir so drafts are persisted (survives crashes)
    lineage_base = target_repo / "docs" / "lineage" / "active"
    audit_dir = lineage_base / f"{args.issue}-implspec"
    audit_dir.mkdir(parents=True, exist_ok=True)

    state: ImplementationSpecState = {
        # Input
        "issue_number": args.issue,
        "lld_path": lld_path,
        "repo_root": str(target_repo),
        "assemblyzero_root": str(assemblyzero_root),
        "audit_dir": str(audit_dir),  # Issue #525: persist drafts
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
        # Issue #476: API cost budget
        "cost_budget_usd": args.budget,
        # LLM config. #3563: the model profile is the source; the three
        # legacy keys are written from it for one release.
        "model_profile": profile,
        "config_reviewer": seat_in(profile, "spec.review").spec,
        "config_drafter": seat_in(profile, "spec.draft").spec,
        "config_mock_mode": args.mock,
        "config_effort": seat_in(profile, "spec.review").effort or "",  # Issue #773
        # Issue #511: Per-node LLM cost tracking
        "node_costs": {},
        "node_tokens": {},
    }
    print(describe(profile))
    # #3565: the run record opens with the profile; seats no state reaches
    # (triage, visual gate, contract fidelity) follow it.
    from assemblyzero.core.model_record import announce_profile

    announce_profile(profile)

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
    print(f"Models:       {getattr(args, 'models', None) or '(profile precedence; see [models] below)'}")
    print(f"Overrides:    drafter={getattr(args, 'drafter', None) or '-'} reviewer={getattr(args, 'reviewer', None) or '-'} seat={getattr(args, 'seat', None) or '-'}")
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
        print("Status:   ERROR")
        print(f"ERROR: {final_state['error_message']}", file=sys.stderr)
    else:
        verdict = final_state.get("review_verdict", "UNKNOWN")
        spec_path = final_state.get("spec_path", "")
        iterations = final_state.get("review_iteration", 0)

        print(f"Status:   {verdict}")
        if spec_path:
            print(f"Spec:     {spec_path}")
        print(f"Iterations: {iterations}")

    # Issue #511: Display cost summary and emit telemetry
    node_costs = final_state.get("node_costs", {})
    if node_costs:
        total = sum(node_costs.values())
        print(f"Cost:     ${total:.4f}")
        for node_name, cost in sorted(node_costs.items()):
            if cost > 0:
                print(f"  {node_name}: ${cost:.4f}")
        # Ledger 0908, line 557: an ImportError here dropped the cost
        # telemetry silently. The module is part of AssemblyZero; a run that
        # cannot import it fails.
        from assemblyzero.telemetry import emit
        emit(
            "workflow.cost",
            repo="AssemblyZero",
            metadata={
                "workflow_type": "implementation_spec",
                "issue_number": final_state.get("issue_number", 0),
                "total_cost_usd": round(total, 6),
                "cost_by_node": {k: round(v, 6) for k, v in node_costs.items()},
            },
        )

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
        0 when the spec workflow finished, 1 when it halted (the HALT node
        alerted), 130 when the operator interrupted it.

    Raises:
        RunFailed: no LLD (ledger 0908, line 414), a refused resume contract
            (line 635), or an error that ended the run without HALT (line 683).
        Exception: anything the graph raised (line 696); main's handler alerts.
    """
    # Print header
    print_header(args, assemblyzero_root, target_repo)

    # Handle dry-run
    if args.dry_run:
        return run_dry_run(args, target_repo)

    # Ledger 0908, line 414: the LLD is found, or the run refuses, before the
    # resume contract is consumed and before any state or lineage is built.
    resolve_lld_path(args, target_repo)

    # #2570: a resume finds the world the halt described, or refuses by
    # name -- before any state is built and any token is spent. A fresh
    # run has no contract and passes silently.
    from assemblyzero.core.resume_contract import check_and_consume

    # Ledger 0908, line 635: a refusal returned 1 with no alert. Its lines
    # still print as they come, and become the alert's cause.
    contract_lines: list[str] = []

    def _contract_log(line: str) -> None:
        print(line)
        contract_lines.append(line.strip())

    if not check_and_consume(
        "implementation_spec", args.issue,
        # #4292: the halt files are the repository's own, and a --mock run's
        # are a mock's: issue #N of another repository, or a rehearsal's halt,
        # is never this run's contract.
        repo_root=target_repo,
        mock=bool(args.mock),
        accept_changed=args.accept_changed_inputs,
        log=_contract_log,
    ):
        raise RunFailed(
            "the resume contract refused the run: " + "; ".join(contract_lines)
        )

    # Build initial state
    state = build_initial_state(args, assemblyzero_root, target_repo)

    if args.debug:
        print(f"DEBUG: Initial state keys: {list(state.keys())}")
        print(f"DEBUG: lld_path = {state.get('lld_path', '')}")
        print(f"DEBUG: repo_root = {state.get('repo_root', '')}")

    # Create and run graph
    # Issue #517: Global workflow timeout
    from assemblyzero.utils.workflow_timeout import WorkflowTimeout

    try:
      with WorkflowTimeout(minutes=args.timeout):
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

                # Accumulate state updates from each node (Issue #571)
                if node_output:
                    final_state.update(node_output)

                # Check for errors from nodes (node_output may be None).
                # Ledger 0908, line 683: on stdout; it is on stderr now.
                error = (node_output or {}).get("error_message", "")
                if error:
                    print(f"\n[ERROR] {error}", file=sys.stderr)

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted. Re-run the same command to auto-recover.")
        return 130

    # Ledger 0908, line 696: a graph exception printed on stdout with no
    # type, a traceback only under --debug, and no alert. It propagates now;
    # main's handler prints its type and traceback and alerts.

    print_result(final_state)

    error = final_state.get("error_message")
    if error:
        if final_state.get("workflow_status") == "halted":
            # The HALT node saved the state and alerted the operator.
            return 1
        # An error that reached the end without HALT has alerted no one.
        raise RunFailed(f"the spec workflow ended in an error HALT never saw: {error}")

    return 0


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """Main entry point.

    #4098 (ADR 0236): one handler owns every failure below it. It prints the
    failure at ERROR on stderr, with its traceback when the tool did not name
    it itself, alerts the operator, and returns 1. A run that halted returns
    1 without a second alert: the HALT node sent one.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    args = parse_args()

    # #3729 (ADR 0236): every failure alerts, so a run whose alert channel
    # cannot work refuses before its first node. Mock and dry runs too.
    from assemblyzero.core import alert
    alert.require_alert_channel(ENTRY)

    try:
        return _run(args)
    except Exception as exc:  # noqa: BLE001 - the one handler: reported and alerted below
        named = isinstance(exc, RunFailed)
        cause = str(exc) if named else f"{type(exc).__name__}: {exc}"
        print(f"[spec] ERROR: {cause}", file=sys.stderr)
        if not named:
            traceback.print_exc(file=sys.stderr)
        alert.alert_operator(
            what="the implementation spec workflow failed",
            where=f"{ENTRY} main",
            cause=cause,
            consequence="the run stopped and exited 1; nothing after the failure ran",
            repo=getattr(args, "resolved_repo", "") or (args.repo or ""),
            issue=args.issue,
        )
        return 1


def _run(args: argparse.Namespace) -> int:
    """Everything main guards. Raises on every failure."""
    # Apply review configuration
    apply_review_config(args)

    # Validate issue number (ledger 0908, line 727: stdout, no alert)
    if args.issue <= 0:
        raise RunFailed(f"--issue must be a positive integer, not {args.issue}")

    # Resolve paths
    assemblyzero_root, target_repo = resolve_roots(args)
    # The alert of a later failure names the repository the run resolved.
    args.resolved_repo = str(target_repo)

    if args.debug:
        print(f"DEBUG: assemblyzero_root = {assemblyzero_root}")
        print(f"DEBUG: target_repo = {target_repo}")

    # Ledger 0908, line 738: stdout, no alert.
    if not target_repo.exists():
        raise RunFailed(f"repository path does not exist: {target_repo}")

    # Set environment variables for mode flags
    if not args.human_gate_enabled:
        os.environ["ASSEMBLYZERO_AUTO_MODE"] = "1"

    # Run workflow
    return run_workflow(args, assemblyzero_root, target_repo)


if __name__ == "__main__":
    sys.exit(main())
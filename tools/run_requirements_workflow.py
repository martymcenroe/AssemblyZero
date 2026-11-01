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

    # With custom LLM providers (the default is agy in both seats, #3517)
    python tools/run_requirements_workflow.py --type lld --issue 42 \
        --drafter claude:sonnet --reviewer claude:opus

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
import traceback
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
    check_existing_lld,
    generate_slug,
    shift_lineage_versions,
)
from assemblyzero.core.seats import (  # noqa: E402  (#3563)
    add_profile_arguments,
    describe,
    seat_in,
    profile_from_args,
)
from assemblyzero.utils.git import current_branch, validate_integration_branch
from assemblyzero.workflows.requirements.config import GateConfig
from assemblyzero.workflows.requirements.graph import create_requirements_graph
from assemblyzero.workflows.requirements.state import create_initial_state, RequirementsWorkflowState
from assemblyzero.core.stage_watchdog import StageWatchdog  # noqa: E402  (#2231)
from assemblyzero.workflows.requirements.step_budget import (  # noqa: E402  (#2245)
    DEFAULT_MAX_ITERATIONS,
    invoke_with_budget,
)

#: This entry point, as its alerts and its start-up check name it.
ENTRY = "tools/run_requirements_workflow.py"


class RunFailed(Exception):
    """A failure this entry point names itself (ADR 0236, #4100).

    Raised for what the tool owns: a bad argument, an input that is missing or
    cannot be read, a refused start, a run that ended without its product.
    ``main``'s one handler prints it as one ERROR line on stderr, alerts the
    operator, and returns 1; any other exception gets its traceback as well.
    ``alerted`` is True when the HALT node already alerted for the same
    failure, so ``main`` reports it without a second alert.
    """

    def __init__(self, message: str, *, alerted: bool = False) -> None:
        super().__init__(message)
        self.alerted = alerted


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

    False means the database holds no checkpoint for the slug, which is a
    legitimate answer: sqlite creates an empty database on first use. A
    database that cannot be opened or read raises naming it (ledger 0908, line
    118); it used to return False, and a resume read that as "no checkpoint".

    Args:
        slug: Workflow slug to check.

    Returns:
        True if checkpoint exists.

    Raises:
        RunFailed: the checkpoint database cannot be read.
    """
    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = get_checkpoint_db_path()
    try:
        with SqliteSaver.from_conn_string(str(db_path)) as memory:
            config = {"configurable": {"thread_id": slug}}
            checkpoints = list(memory.list(config))
            return len(checkpoints) > 0
    except Exception as exc:
        raise RunFailed(
            f"cannot read the checkpoint database {db_path}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


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

    An empty list means the directory holds no briefs, which is an answer. A
    missing directory raises (ledger 0908, line 1203): it used to return an
    empty list, and --all exited 0 as if the batch were done.

    Args:
        target_repo: Target repository path.

    Returns:
        List of paths to brief files.

    Raises:
        RunFailed: ideas/active/ does not exist.
    """
    ideas_dir = target_repo / IDEAS_ACTIVE_DIR

    if not ideas_dir.is_dir():
        raise RunFailed(
            f"no ideas/active/ directory at {ideas_dir}: --all has no briefs to process"
        )

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
        Title string, or "(no title)" when the brief has no "# " heading,
        which is an answer about its content.

    Raises:
        RunFailed: the brief cannot be read (ledger 0908, line 175); it used
            to be titled "(no title)" as if it were empty.
    """
    try:
        content = brief_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RunFailed(
            f"cannot read the brief {brief_path}: {type(exc).__name__}: {exc}"
        ) from exc
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return "(no title)"


def select_brief_file(target_repo: Path) -> str | None:
    """Interactively select a brief file from ideas/active/.

    Args:
        target_repo: Path to target repository.

    Returns:
        Selected brief file path (relative to repo), or None when the operator
        quits the menu. Nothing else returns None.

    Raises:
        RunFailed: ideas/active/ is missing or holds no brief (ledger 0908,
            lines 192 and 199); both used to return None, which main read as
            a cancel and exited 0.
    """
    ideas_dir = target_repo / "ideas" / "active"

    if not ideas_dir.is_dir():
        raise RunFailed(
            f"no ideas/active/ directory at {ideas_dir}: --select has no brief to offer"
        )

    # Find markdown files
    briefs = sorted(ideas_dir.glob("*.md"))

    if not briefs:
        raise RunFailed(
            f"no brief files (*.md) in {ideas_dir}: --select has no brief to offer"
        )

    # Display menu
    print(f"\n{'=' * 60}")
    print("Select Brief File from ideas/active/")
    print(f"{'=' * 60}")

    for i, brief in enumerate(briefs, 1):
        title = extract_brief_title(brief)
        print(f"  [{i}] {brief.name}")
        print(f"      {title}")

    print("\n  [q] Quit")
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
        Selected issue number, or None when the operator quits the menu.
        Nothing else returns None.

    Raises:
        RunFailed: gh fails, times out, is missing or prints something that
            is not JSON (ledger 0908, lines 259-270), or there is no open
            issue to offer (line 1668). Each used to return None, which main
            read as a cancel and exited 0.
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
    except subprocess.TimeoutExpired as exc:
        raise RunFailed(
            f"gh issue list timed out after {exc.timeout}s in {target_repo}"
        ) from exc
    except FileNotFoundError as exc:
        raise RunFailed(
            "gh CLI not found. Install GitHub CLI: https://cli.github.com/"
        ) from exc

    if result.returncode != 0:
        raise RunFailed(
            f"gh issue list failed in {target_repo} (exit {result.returncode}): "
            f"{(result.stderr or '').strip()}"
        )

    try:
        issues = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RunFailed(
            f"gh issue list printed output that is not JSON ({exc}): "
            f"{(result.stdout or '').strip()[:200]}"
        ) from exc

    if not issues:
        raise RunFailed(
            f"no open issues in {target_repo}: --select has no issue to offer"
        )

    # Display menu
    print(f"\n{'=' * 60}")
    print("Select GitHub Issue")
    print(f"{'=' * 60}")

    for i, issue in enumerate(issues, 1):
        labels = ", ".join(label["name"] for label in issue.get("labels", []))
        label_str = f" [{labels}]" if labels else ""
        print(f"  [{i}] #{issue['number']}: {issue['title']}{label_str}")

    print("\n  [q] Quit")
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

  # Custom LLM providers (the default is agy in both seats, #3517)
  python tools/run_requirements_workflow.py --type lld --issue 42 \\
      --drafter claude:sonnet --reviewer claude:opus

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

    # LLM configuration. #3563: every seat's model comes from the run's model
    # profile (--models; default gemini.toml, the 2026-09-24 law that agy
    # drafts and validates, #3517). --drafter and --reviewer are kept as
    # per-seat overrides on top of the profile; --seat is the general form.
    add_profile_arguments(parser)
    parser.add_argument(
        "--drafter",
        default=None,
        help=(
            "Override the drafter seats (requirements.analyze, "
            "requirements.draft) with a provider spec. Default: the profile's"
        ),
    )
    parser.add_argument(
        "--reviewer",
        default=None,
        help="Override the requirements.review seat. Default: the profile's",
    )
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "max"],
        default=None,
        help="Effort for every seat, over the profile's (default: the profile's, max)",
    )

    # Issue #1071: Retry policy for transient LLM failures.
    parser.add_argument(
        "--retry-policy",
        choices=["default", "aggressive", "none"],
        default="default",
        help=(
            "Retry policy for transient LLM API failures (5xx, 429, "
            "timeouts). 'default': 5 retries, 2s→32s exponential "
            "backoff. 'aggressive': 8 retries, 60s cap. 'none': no "
            "retry (pre-#1071 fail-fast behavior). Server-provided "
            "Retry-After headers are honored regardless of policy. "
            "(#1071)"
        ),
    )

    # Issue #1076: Speed-run instrumentation.
    parser.add_argument(
        "--speedrun",
        action="store_true",
        default=False,
        help=(
            "Emit speed-run lap-splits and append a run-log entry to "
            "data/speedrun/. (#1076)"
        ),
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
    parser.add_argument(
        "--no-worktree",
        action="store_true",
        help="Skip worktree isolation check (allow running on AssemblyZero main)",
    )

    # Paths
    parser.add_argument(
        "--repo",
        help="Target repository path (default: auto-detect from git)",
    )
    parser.add_argument(
        "--base-branch",
        default="",
        dest="base_branch",
        help=(
            "Integration branch for the LLD PR (#1754 attempt-branch "
            "model). Default: the branch the target repo is checked "
            "out on."
        ),
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
        "--draft-candidates",
        type=int,
        default=1,
        help=(
            "#2573: generate N independent initial LLD drafts, score each by "
            "the full mechanical gate suite, and take the best forward into "
            "review. 1 (default) is the serial path exactly. Capped at 5. "
            "Applies to the lld workflow's initial draft only -- revisions "
            "remain edit-script based."
        ),
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
        Path to git repo root, or None when git says the path is in no
        repository. That is an answer: resolve_roots then takes the working
        directory's repository, the documented order (#115).

    Raises:
        RunFailed: git timed out or is not installed (ledger 0908, line 560);
            it used to fall back to the working directory's repository.
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
    except subprocess.TimeoutExpired as exc:
        raise RunFailed(
            f"git rev-parse --show-toplevel timed out after {exc.timeout}s in "
            f"{search_dir}, the brief's directory"
        ) from exc
    except FileNotFoundError as exc:
        raise RunFailed(
            f"git not found: cannot find the repository that holds {search_dir}"
        ) from exc
    if result.returncode == 0:
        return Path(result.stdout.strip()).resolve()

    return None


def _detect_repo_from_cwd() -> Path:
    """Detect git repo from current working directory.

    Returns:
        Path to git repo root.

    Raises:
        RunFailed: git timed out, is not installed, or says the working
            directory is in no repository (ledger 0908, lines 582 and 585).
            Each used to return the working directory itself as the target.
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
            f"directory {cwd}"
        ) from exc
    if result.returncode != 0:
        raise RunFailed(
            f"no --repo was given and the working directory {cwd} is in no git "
            f"repository (git rev-parse exited {result.returncode}): "
            f"{(result.stderr or '').strip()}"
        )
    return Path(result.stdout.strip()).resolve()


def resolve_roots(args: argparse.Namespace) -> tuple[Path, Path]:
    """Resolve assemblyzero_root and target_repo paths.

    assemblyzero_root: Where AssemblyZero is installed (for templates/prompts).
    target_repo: Where the work happens (outputs, context, gh CLI).

    Priority for target_repo:
    1. --repo flag (explicit override)
    2. Git repo containing the --brief file
    3. Git repo of current working directory

    A working directory in no repository is refused rather than used as the
    target (ledger 0908, line 585).

    Args:
        args: Parsed CLI arguments.

    Returns:
        Tuple of (assemblyzero_root, target_repo) as Path objects.

    Raises:
        RunFailed: git cannot answer, the working directory is in no
            repository, or the target is the AssemblyZero root.
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

    # Issue #825: Worktree isolation — prevent running directly on AssemblyZero main.
    # Ledger 0908, line 633: it printed and exited 1 here, with no alert.
    if target_repo == assemblyzero_root and not getattr(args, "no_worktree", False):
        raise RunFailed(
            f"the target repository resolves to the AssemblyZero root "
            f"{assemblyzero_root}. A run there writes onto that checkout and "
            "conflicts with other agents: run it from a worktree (git worktree "
            "add --relative-paths ../AssemblyZero-worktrees/825 -b 825-feature), "
            "or pass --no-worktree to override this check"
        )

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

    # #3563: the run's model profile, snapshotted into state. The three
    # legacy keys are written from it for one release.
    profile = run_profile_for(args, target_repo)

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
            drafter=seat_in(profile, "requirements.draft").spec,
            reviewer=seat_in(profile, "requirements.review").spec,
            gates_draft=gate_config.draft_gate,
            gates_verdict=gate_config.verdict_gate,
            auto_mode=args.review == "none",
            mock_mode=args.mock,
            max_iterations=args.max_iterations,
            effort=seat_in(profile, "requirements.review").effort or "",
            retry_policy=getattr(args, "retry_policy", "default"),
            brief_file=args.brief or "",
            source_idea=source_idea,
        )
    else:  # lld
        # #1754 attempt-branch model: capture the integration branch the
        # target repo is standing on BEFORE any LLM work burns quota.
        # A generated work branch or detached HEAD aborts here, loudly.
        base_branch = getattr(args, "base_branch", "") or current_branch(
            target_repo
        )
        validate_integration_branch(base_branch)

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(assemblyzero_root),
            target_repo=str(target_repo),
            base_branch=base_branch,
            drafter=seat_in(profile, "requirements.draft").spec,
            reviewer=seat_in(profile, "requirements.review").spec,
            gates_draft=gate_config.draft_gate,
            gates_verdict=gate_config.verdict_gate,
            auto_mode=args.review == "none",
            mock_mode=args.mock,
            max_iterations=args.max_iterations,
            effort=seat_in(profile, "requirements.review").effort or "",
            retry_policy=getattr(args, "retry_policy", "default"),
            issue_number=args.issue or 0,
            context_files=args.context or [],
            draft_candidates=getattr(args, "draft_candidates", 1),
        )

    # Issue #476: API cost budget
    state["cost_budget_usd"] = getattr(args, "budget", 5.0)
    state["model_profile"] = profile
    print(describe(profile))
    # #3565: the run record opens with the profile; seats no state reaches
    # (triage, visual gate, contract fidelity) follow it.
    from assemblyzero.core.model_record import announce_profile

    announce_profile(profile)

    return state


#: #3563: the seats the old flags override. The drafter flag reached N0c and
#: N1 through `config_drafter`; its escalation follows #2375's map.
LEGACY_SEAT_FLAGS = {
    "drafter": ("requirements.analyze", "requirements.draft"),
    "reviewer": ("requirements.review",),
}


def run_profile_for(args: argparse.Namespace, target_repo: Path) -> dict:
    """The model profile this run uses (#3563): --models, then
    AZ_MODEL_PROFILE, then the target's models.toml, then gemini.toml, with
    --seat, --drafter, --reviewer and --effort applied on top. Under --mock
    the issue workflow drafts from `mock:draft` and the LLD workflow from
    `mock:lld` (#3533). A --drafter also sets the N0c escalation seat by
    #2375's map, unless --seat names that seat itself."""
    from assemblyzero.core.seats import apply_overrides

    mock_overrides = (
        {"requirements.draft": "mock:draft"} if getattr(args, "type", "") == "issue" else {}
    )
    profile = profile_from_args(
        args, target_repo, LEGACY_SEAT_FLAGS, mock_overrides=mock_overrides,
    )
    drafter = profile["overrides"].get("requirements.analyze")
    if drafter and "requirements.analyze.escalation" not in profile["overrides"]:
        from assemblyzero.workflows.requirements.nodes.analyze_requirements import (
            escalated_drafter,
        )

        profile = apply_overrides(
            profile,
            {"requirements.analyze.escalation": escalated_drafter(drafter) or drafter},
        )
    return profile


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
        0 when the run produced its issue or LLD (or the operator chose manual
        handling at a gate), 130 when the operator interrupted it.

    Raises:
        RunFailed: the run ended in an error, or ended without its product
            (ledger 0908, lines 1541, 1551 and 1558).
        Exception: anything the graph raised, after the run record and the
            speed-run log keep it (line 931); main's handler alerts.
    """
    # #3503: the record opens before anything is printed, so the tag and the
    # log path are the first line and the header is already in the log. A
    # dry run writes nothing, by definition.
    record = None
    if not args.dry_run:
        from assemblyzero.core.run_record import RunRecord
        record = RunRecord.start("lld", target_repo, args.issue or None)

    # Print header
    print_header(args)

    # Build initial state. Ledger 0908, line 1698: a refusal here (a work
    # branch as the base, a bad profile) escaped main as a bare traceback and
    # left the record open; the record keeps it, and main's handler alerts.
    try:
        state = build_initial_state(args, assemblyzero_root, target_repo)
    except Exception as e:
        if record:
            record.crash(e)
            record.finish("halt", str(e))
        raise

    if args.debug:
        print(f"DEBUG: Initial state keys: {list(state.keys())}")

    # Handle dry-run mode. #3507: the plan names everything a real run would
    # write, delete, shift, cut or push, and this branch touches none of it.
    if args.dry_run:
        print("DRY RUN: Would execute workflow with the above configuration")
        print(f"  Workflow type: {state['workflow_type']}")
        if args.mock and state["workflow_type"] == "lld":
            print(f"  Audit dir would be created at: {target_repo}/data/mock-runs/{args.issue}-lld/docs/lineage/active/...")
        else:
            print(f"  Audit dir would be created at: {target_repo}/docs/lineage/active/...")
        if state["workflow_type"] == "lld":
            # #3510: N5 writes into the LLD worktree (a mock run: under
            # data/mock-runs/), never the checkout.
            if args.mock:
                out_root = f"{target_repo}/data/mock-runs/{args.issue}-lld"
            else:
                out_root = f"{target_repo}/data/worktrees/{args.issue}-lld"
            print(f"  LLD would be saved to: {out_root}/docs/lld/active/LLD-{args.issue:03d}.md")
            existing = check_existing_lld(args.issue, target_repo)
            if (existing["lld_exists"] or existing["lineage_exists"]) and not args.mock:
                print("  Regeneration (Standard 0012) would first:")
                if existing["lld_exists"]:
                    print(
                        f"    leave {existing['lld_path'].relative_to(target_repo)} "
                        "in the checkout as it is; the new LLD replaces it in the worktree"
                    )
                if existing["lineage_exists"]:
                    lineage_rel = existing["lineage_path"].relative_to(target_repo)
                    print(f"    shift {lineage_rel}/ to {args.issue}-lld-n1 (n1 to n2, n2 removed)")
                if not args.yes:
                    print("    and ask for YES first (no --yes given)")
            base = state.get("base_branch")
            if args.mock:
                print("  Worktree: none (--mock cuts no worktree and fetches nothing, #3512)")
            elif base:
                print(f"  Worktree would be cut at: {target_repo}/data/worktrees/{args.issue}-lld")
                print(f"  Branch would be: {args.issue}-lld from origin/{base}, landed on APPROVED "
                      f"by the merge driver named in AZ_MERGE_DRIVER (#3704)")
        print("DRY RUN: nothing was written, deleted, shifted, cut or pushed.")
        return 0

    # Issue #1076: Speed-run instrumentation
    speedrun_splits = None
    speedrun_logger = None
    if getattr(args, "speedrun", False) and getattr(args, "issue", None):
        from assemblyzero.utils.speedrun import LapSplitWriter, RunLogger
        speedrun_splits = LapSplitWriter.start(target_repo, args.issue)
        speedrun_logger = RunLogger(target_repo)
        speedrun_splits.beat("workflow_started")
        print(f"[speedrun] Lap splits: {speedrun_splits.output_path}")

    def _finalize_speedrun(outcome: str, fstate: dict | None = None,
                          error_msg: str = "", notes: str = "") -> None:
        nonlocal speedrun_splits, speedrun_logger
        if speedrun_splits is None or speedrun_logger is None:
            return
        from assemblyzero.utils.speedrun import classify_halt as _classify
        import time as _time
        failure_mode = None
        if outcome != "success":
            failure_mode = _classify(fstate or {}, error_msg)
        speedrun_splits.finalize(outcome, failure_mode)
        speedrun_logger.complete_run(
            issue=speedrun_splits.issue,
            attempt=speedrun_splits.attempt,
            started_at_iso=speedrun_splits.started_at_iso,
            outcome=outcome,
            total_seconds=_time.time() - speedrun_splits.started_at,
            failure_mode=failure_mode,
            notes=notes,
        )
        speedrun_splits = None
        speedrun_logger = None

    # Create and run graph
    # Issue #517: Global workflow timeout
    from assemblyzero.utils.workflow_timeout import WorkflowTimeout

    try:
      with WorkflowTimeout(minutes=args.timeout):
        graph = create_requirements_graph()
        compiled = graph.compile()

        print("Starting workflow...")
        print()

        # #2245: this was `(max_iters * 4) + 10` -- 22 at the default cap of 3,
        # SMALLER than the LangGraph default of 25 it was presumably raising,
        # and unrelated to what the loops actually cost. The budget is now
        # derived from measured per-loop step costs, and exhausting it halts
        # naming the loop that spent it instead of raising GraphRecursionError.
        #
        # #2231: and it says so while it runs. This runner emitted nothing
        # during a multi-minute model call, which is exactly where silence gets
        # misread as a hang -- and it is one of the two entry points the
        # babysit protocol tells an operator to run. Same watchdog the
        # orchestrator has had since #1886.
        stage_name = "lld" if state.get("workflow_type") == "lld" else "issue"
        with StageWatchdog(stage_name):
            final_state = invoke_with_budget(
                compiled,
                state,
                stage=stage_name,
                max_iterations=state.get("max_iterations", DEFAULT_MAX_ITERATIONS),
            )

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user.")
        _finalize_speedrun("halt", error_msg="user interrupt", notes="KeyboardInterrupt")
        if record:
            record.finish("halt", "user interrupt")
        return 130

    except Exception as e:
        # Ledger 0908, line 931: this printed the message on stdout, with a
        # traceback only under --debug, and returned 1 with no alert. The
        # record and the speed-run log keep the crash; main's handler prints
        # it at ERROR with its type and traceback and alerts.
        _finalize_speedrun("halt", error_msg=str(e), notes=f"exception:{type(e).__name__}")
        if record:
            record.crash(e)
            record.finish("halt", str(e))
        raise

    print_result(final_state)

    failure = _run_failure(final_state)
    if failure is not None:
        _finalize_speedrun("fail", fstate=final_state, error_msg=str(failure))
        if record:
            record.finish("fail", str(failure))
        raise failure

    _finalize_speedrun("success", fstate=final_state)
    if record:
        record.finish("success")
    return 0


def _run_failure(final_state: dict[str, Any]) -> RunFailed | None:
    """Why the ended run failed, or None when it produced what it was for.

    The issue workflow's product is a filed issue (``issue_url``), the LLD
    workflow's a saved LLD (``final_lld_path``). An error in the final state
    is a failure; when the HALT node ran (it sets ``recovery_plan_path``) it
    has already alerted, so the failure says so and main does not alert
    twice. An end with neither a product nor an error is a failure too
    (ledger 0908, lines 1551 and 1558; both exited 0). The one end without a
    product that is not a failure is the operator choosing manual handling at
    a human gate, which sets ``next_node`` to END: that is his decision.
    """
    error = (final_state.get("error_message") or "").strip()
    if error:
        return RunFailed(
            f"the workflow ended in an error: {error}",
            alerted=bool(final_state.get("recovery_plan_path")),
        )
    if final_state.get("next_node") == "END":
        return None
    if final_state.get("workflow_type", "lld") == "issue":
        if not final_state.get("issue_url"):
            return RunFailed(
                "the issue workflow ended without filing an issue and recorded no error"
            )
    elif not final_state.get("final_lld_path"):
        return RunFailed(
            "the LLD workflow ended without saving an LLD and recorded no error"
        )
    return None


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
        0 when the review run saved the LLD (or the operator chose manual
        handling at a gate), 130 when the operator interrupted it.

    Raises:
        RunFailed: no resumable draft (ledger 0908, line 967), no
            001-issue.md in its lineage (line 991), or the run ended in an
            error or without an LLD.
        Exception: anything the graph raised, after the run record keeps it
            (line 1175); main's handler alerts.
    """
    issue_number = args.issue

    # Check that a resumable draft exists
    resume_info = _draft_is_resumable(issue_number, target_repo)
    if not resume_info:
        lineage = target_repo / AUDIT_ACTIVE_DIR / f"{issue_number}-lld"
        raise RunFailed(
            f"no resumable draft for issue #{issue_number}: --resume-review needs "
            f"{lineage} to hold a draft with no verdict after it"
        )

    # Ledger 0908, line 991: the review used to run without the issue's body
    # and title when the lineage had no 001-issue.md. It refuses before the
    # record opens, since nothing has run.
    issue_file = resume_info["lineage_dir"] / "001-issue.md"
    if not issue_file.is_file():
        raise RunFailed(
            f"the lineage {resume_info['lineage_dir']} has no 001-issue.md: a "
            "resumed review needs the issue's title and body, and would review "
            "the draft without them"
        )

    # #3503: a resumed run is a run; it leaves the same record.
    from assemblyzero.core.run_record import RunRecord
    record = RunRecord.start("lld", target_repo, issue_number)

    print_header(args)
    print("[RESUME] Resuming at review with existing draft from:")
    print(f"  {resume_info['draft_path'].relative_to(target_repo)}")
    print(f"  Draft iterations: {resume_info['draft_count']}")
    print()

    # Build initial state and inject the existing draft. Ledger 0908, line
    # 1698: a refusal here keeps its record too.
    try:
        state = build_initial_state(args, assemblyzero_root, target_repo)
    except Exception as e:
        record.crash(e)
        record.finish("halt", str(e))
        raise
    state["current_draft"] = resume_info["draft_content"]
    state["current_draft_path"] = str(resume_info["draft_path"])
    state["audit_dir"] = str(resume_info["lineage_dir"])
    state["draft_count"] = resume_info["draft_count"]
    state["iteration_count"] = resume_info["draft_count"]

    # Load issue content from lineage (001-issue.md)
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

            # #2245: same derived budget as the full run above.
            # #2231: and the same heartbeat.
            with StageWatchdog("lld"):
                final_state = invoke_with_budget(
                    compiled_resume,
                    state,
                    stage="lld resume",
                    max_iterations=state.get("max_iterations", DEFAULT_MAX_ITERATIONS),
                )

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user.")
        record.finish("halt", "user interrupt")
        return 130

    except Exception as e:
        # Ledger 0908, line 1175: stdout, a traceback only under --debug,
        # return 1 and no alert. The record keeps the crash; main's handler
        # prints it at ERROR with its traceback and alerts.
        record.crash(e)
        record.finish("halt", str(e))
        raise

    print_result(final_state)

    failure = _run_failure(final_state)
    if failure is not None:
        record.finish("fail", str(failure))
        raise failure

    record.finish("success")
    return 0


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

    A brief that fails stops the batch (ADR 0236: a loop stops when one item
    fails, and the batch's summary is shaped by every item). The failure
    raises out of run_single_workflow, and main's handler names the brief and
    alerts. Ledger 0908, line 1241: it used to print FAILED on stdout, go on
    to the next brief, and exit 1 at the end with no alert.

    Returns:
        0 when every brief was processed or skipped, including when
        ideas/active/ holds none: zero briefs is the whole batch done. 130
        when the operator interrupted a brief; the batch stops with it.

    Raises:
        RunFailed: ideas/active/ is missing (line 1203), or a brief failed.
    """
    briefs = list_briefs(target_repo)

    if not briefs:
        print("No briefs found in ideas/active/: nothing to process")
        return 0

    total = len(briefs)
    processed = 0
    skipped = 0

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

        if exit_code != 0:
            print(
                f"        Result: INTERRUPTED (exit code {exit_code}); the batch "
                f"stops at {brief_path.name}",
                file=sys.stderr,
            )
            return exit_code
        processed += 1
        print("        Result: SUCCESS")

    # Print summary
    print()
    print("=" * 60)
    print("BATCH COMPLETE")
    print("=" * 60)
    print(f"  Total:     {total}")
    print(f"  Processed: {processed}")
    print(f"  Skipped:   {skipped}")
    print("=" * 60)

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
        What run_single_workflow returns.

    Raises:
        RunFailed: the brief is in none of the places --resume looks (ledger
            0908, lines 1306 and 1330), the checkpoint database cannot be
            read, or there is nothing to resume (line 1291): it used to
            print a WARNING and start a fresh workflow.
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

    brief_path = _resolve_resume_brief(brief_file, target_repo)

    # Check if audit directory exists
    has_audit = audit_dir_exists(slug, target_repo)
    has_checkpoint = checkpoint_exists(slug)

    if not has_audit and not has_checkpoint:
        raise RunFailed(
            f"--resume {brief_file}: no checkpoint and no audit directory for "
            f"'{slug}', so there is nothing to resume; start it with --brief instead"
        )

    # Resume: set brief and run
    print()
    if has_checkpoint:
        print(f"Found checkpoint for '{slug}', resuming...")
    else:
        print(f"Found audit directory for '{slug}', resuming...")
    print()

    args.brief = str(brief_path.relative_to(target_repo))
    return run_single_workflow(args, assemblyzero_root, target_repo)


def _resolve_resume_brief(brief_file: str, target_repo: Path) -> Path:
    """The brief --resume names: an absolute path as given, else
    ideas/active/<name>, else <repo>/<name>.

    Raises:
        RunFailed: the brief is in none of those places.
    """
    brief_path = Path(brief_file)
    if brief_path.is_absolute():
        candidates = [brief_path]
    else:
        candidates = [target_repo / IDEAS_ACTIVE_DIR / brief_file, target_repo / brief_file]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    looked = ", ".join(str(c) for c in candidates)
    raise RunFailed(f"--resume: brief file not found: {brief_file} (looked at {looked})")


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
        True if we should proceed with generation, False when the operator
        answered the confirmation prompt with anything but YES.

    Raises:
        RunFailed: a resumable draft exists and --yes was not given (ledger
            0908, line 1446). It used to return False, and main exited 0 as
            "User aborted" with nothing generated and no choice asked for.
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
            raise RunFailed(
                f"issue #{issue_number} has a resumable draft at {draft_rel}, and "
                "the run will not choose for you: pass --resume-review to review "
                "that draft, or --yes to discard it and draft again"
            )

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
        print("  - Write the new LLD into the LLD worktree (the checkout's copy is left as it is)")
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
    print(f"Models:   {getattr(args, 'models', None) or '(profile precedence; see [models] below)'}")
    print(f"Overrides: drafter={getattr(args, 'drafter', None) or '-'} reviewer={getattr(args, 'reviewer', None) or '-'} seat={getattr(args, 'seat', None) or '-'}")
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

    # Ledger 0908, line 1541: the error went to stdout only. The run's caller
    # raises it (_run_failure), and main alerts unless HALT already did.
    if final_state.get("error_message"):
        print(f"ERROR: {final_state['error_message']}", file=sys.stderr)
        return

    workflow_type = final_state.get("workflow_type", "lld")
    manual = final_state.get("next_node") == "END"

    if workflow_type == "issue":
        issue_url = final_state.get("issue_url", "")
        if issue_url:
            print(f"Issue URL: {issue_url}")
        elif manual:
            print("Issue was not filed: manual handling was chosen at a human gate")
        else:
            print("Issue was not filed")
    else:
        lld_path = final_state.get("final_lld_path", "")
        if lld_path:
            print(f"LLD Path: {lld_path}")
            print(f"Status:   {final_state.get('lld_status', 'UNKNOWN')}")
        elif manual:
            print("LLD was not saved: manual handling was chosen at a human gate")
        else:
            print("LLD was not saved")

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

    #4100 (ADR 0236): one handler owns every failure below it (ledger 0908,
    line 1698). It prints the failure at ERROR on stderr, with its traceback
    when the tool did not name it itself, alerts the operator unless the HALT
    node already did, and returns 1. Everything below it raises with its
    cause. Two ends return 0 without a product, because each is the
    operator's own decision: quitting a --select menu, and answering the
    regeneration prompt with anything but YES. An interrupt returns 130.

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
        print(f"[requirements] ERROR: {cause}", file=sys.stderr)
        if not named:
            traceback.print_exc(file=sys.stderr)
        if not getattr(exc, "alerted", False):
            alert.alert_operator(
                what=f"the {args.type} requirements workflow failed",
                where=f"{ENTRY} main{_subject(args)}",
                cause=cause,
                consequence=_consequence(args),
                repo=getattr(args, "resolved_repo", "") or (args.repo or ""),
                issue=args.issue or None,
            )
        return 1


def _subject(args: argparse.Namespace) -> str:
    """The issue or brief a failure belongs to, for the alert's ``where``."""
    if args.type == "lld" and args.issue:
        return f", issue #{args.issue}"
    brief = args.brief or args.resume
    return f", brief {brief}" if brief else ""


def _consequence(args: argparse.Namespace) -> str:
    text = "the run stopped and exited 1; nothing after the failure ran"
    if args.all:
        text += "; the --all batch stopped here, and the briefs after this one were not processed"
    return text


def _run(args: argparse.Namespace) -> int:
    """Everything main guards: arguments, roots, selection, the
    pre-generation check, and the workflow. Raises on every failure."""
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

    # Validate --all and --resume are only for issue workflow. Ledger 0908,
    # lines 1612-1634: each refusal printed on stdout with no alert.
    if args.all and args.type != "issue":
        raise RunFailed("--all is only supported for issue workflow")

    if args.resume and args.type != "issue":
        raise RunFailed("--resume is only supported for issue workflow")

    # Issue #536: Validate --resume-review is only for LLD workflow
    if getattr(args, "resume_review", False) and args.type != "lld":
        raise RunFailed("--resume-review is only supported for LLD workflow")

    if getattr(args, "resume_review", False) and not args.issue:
        raise RunFailed("--resume-review requires --issue")

    # Validate arguments
    if args.type == "issue" and not args.brief and not args.select and not args.all and not args.resume:
        raise RunFailed("--brief, --select, --all, or --resume required for issue workflow")

    if args.type == "lld" and not args.issue and not args.select:
        raise RunFailed("--issue or --select required for LLD workflow")

    # Resolve paths (needed for --select, --all, --resume)
    assemblyzero_root, target_repo = resolve_roots(args)
    # The alert of a later failure names the repository the run resolved.
    args.resolved_repo = str(target_repo)

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

    # Handle --select: interactive selection. Ledger 0908, lines 1662 and
    # 1668: None meant a cancel AND every failure to offer a choice, and both
    # exited 0. The selectors now raise on failure, so None is only the
    # operator quitting the menu: his decision, which exits 0.
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

    # Pre-generation check for LLD workflow (Standard 0012).
    # #3507: not on a dry run. This call deletes the existing LLD and shifts
    # lineage under --yes, and it used to run BEFORE the dry-run exit, so
    # `--dry-run --yes` destroyed a generation and then printed DRY RUN. The
    # dry run reports what this call would do instead (run_single_workflow).
    # #3510: not on a mock run either. A mock run writes under
    # data/mock-runs/ (git_operations.mock_output_root) and has no business
    # shifting a real run's lineage for the same issue number.
    if args.type == "lld" and args.issue and not args.dry_run and not args.mock:
        # #3704: an APPROVED LLD lands through the fleet merge driver, which
        # the machine names in AZ_MERGE_DRIVER. Refuse here, before a model is
        # called, rather than after the draft is written.
        from assemblyzero.core import merge_driver

        reason = merge_driver.check_configured()
        if reason:
            # Ledger 0908, line 1687: stdout and return 1, no alert.
            raise RunFailed(f"[preflight] {reason}")
        # Ledger 0908, line 1690: a resumable draft without --yes reached the
        # exit 0 below; it now raises inside the check. False is only the
        # operator declining the regeneration at the prompt.
        if not check_and_shift_existing_lld(args.issue, target_repo, args.yes):
            print("Nothing was generated: the regeneration was declined at the prompt.")
            return 0

    # Run single workflow
    return run_single_workflow(args, assemblyzero_root, target_repo)


if __name__ == "__main__":
    with track_tool("run_requirements_workflow", repo="AssemblyZero"):
        sys.exit(main())
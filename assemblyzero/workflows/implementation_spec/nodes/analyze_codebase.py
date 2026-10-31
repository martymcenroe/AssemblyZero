"""N1: Analyze Codebase node for Implementation Spec Workflow.

Issue #304: Implementation Readiness Review Workflow (LLD → Implementation Spec)

Reads files listed in the LLD and extracts current state:
- For "Modify" and "Delete" files: reads content and extracts relevant excerpts
- For "Add" files: verifies parent directories exist
- Finds similar implementation patterns in the codebase (existing nodes,
  state definitions, graph constructions) to guide spec generation

This node populates:
- current_state_snapshots: dict[str, str] - file_path → code excerpt
- pattern_references: list[PatternRef] - similar patterns found
- files_to_modify: Updated with current_content for Modify/Delete files
- error_message: "" on success, error text on failure

#3585 (ADR 0236): everything this node gathers is what the drafter is told
about the target repo, so a gap in it is a spec drafted blind. A file the plan
names that is missing, unreadable or unparseable, a file the context needs
that cannot be read, and a base git cannot answer each stop the node: the
helpers raise naming the file and the cause, and the node returns an
``error_message`` that ``route_after_analyze`` sends to HALT, which alerts.
They used to print a WARNING to stdout and leave the context smaller.
"""

import ast
from dataclasses import dataclass
import subprocess
import sys
from pathlib import Path
from typing import Any

from assemblyzero.workflows.implementation_spec.base_tree import (
    BaseTreeError,
    base_ref,
    exists_on_base,
    read_from_base,
    reclassify_against_base,
)
from assemblyzero.workflows.requirements.audit import get_repo_structure
from assemblyzero.workflows.implementation_spec.state import (
    FileToModify,
    ImplementationSpecState,
    PatternRef,
)


# =============================================================================
# Constants
# =============================================================================

# Maximum file size to read (1MB). Larger files are summarized more aggressively.
MAX_FILE_SIZE_BYTES = 1_000_000

# Maximum excerpt length per file (characters). Keeps context manageable.
MAX_EXCERPT_CHARS = 15_000

# Maximum number of pattern references to return.
MAX_PATTERN_REFS = 10

# File extensions considered for pattern matching.
PYTHON_EXTENSIONS = {".py"}

# Directories to skip when scanning for patterns.
SKIP_DIRS = {
    "__pycache__",
    ".git",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    ".venv",
    "venv",
    "done",
}

#: The change types an LLD's Section 2.1 table may carry, as load_lld
#: normalises them.
CHANGE_TYPES = ("Add", "Modify", "Delete")


class CodebaseReadError(RuntimeError):
    """N1 cannot read what it needs (#3585).

    A file the plan or the context needs is missing, is not a file, cannot be
    read or does not parse, or a plan entry carries a change type N1 cannot
    act on. The message names the file and the cause. The node turns it into
    an ``error_message`` routed to HALT.
    """


def _read_or_raise(path: Path, what: str, **read_kwargs: Any) -> str:
    """Read ``path`` as text, or raise CodebaseReadError naming it and why."""
    try:
        return path.read_text(**read_kwargs)
    except (OSError, UnicodeDecodeError) as exc:
        raise CodebaseReadError(
            f"cannot read {what} {path}: {type(exc).__name__}: {exc}"
        ) from exc


def _syntax_detail(exc: SyntaxError) -> str:
    """Where a parse failed, as 'line N: message'."""
    return f"line {exc.lineno}: {exc.msg}" if exc.lineno else exc.msg


def _halt(issue_number: Any, reason: str) -> dict[str, Any]:
    """The node's failure result: loud on stderr, routed to HALT (#3585)."""
    message = f"[N1] analyze_codebase for issue #{issue_number}: {reason}"
    print(f"ERROR {message}", file=sys.stderr, flush=True)
    return {
        "current_state_snapshots": {},
        "pattern_references": [],
        "error_message": message,
    }


# =============================================================================
# Main Node
# =============================================================================


def analyze_codebase(state: ImplementationSpecState) -> dict[str, Any]:
    """N1: Read files and extract current state snapshots.

    Issue #304: Implementation Readiness Review Workflow

    Steps:
    1. Resolve repo root from state
    2. For each "Modify"/"Delete" file: read content, extract relevant excerpt
    3. For each "Add" file: verify parent directory exists
    4. Scan codebase for similar implementation patterns
    5. Return state updates with snapshots and pattern references

    Args:
        state: Current workflow state. Requires:
            - files_to_modify: List[FileToModify] from N0
            - lld_content: Raw LLD markdown (for context in excerpt extraction)
            - repo_root: Repository root path (required; never the cwd, #391)

    Returns:
        Dict with state field updates:
        - current_state_snapshots: Mapping of file_path → code excerpt
        - pattern_references: List[PatternRef] for similar patterns
        - files_to_modify: Updated list with current_content populated
        - error_message: "" on success, error text on failure

    Every failure returns an ``error_message`` naming the issue, the file and
    the cause, which ``route_after_analyze`` sends to HALT (#3585): no files
    in the plan, a Modify or Delete target that is missing, not a file,
    unreadable or unparseable, an unknown change type, a context file that
    cannot be read, and a base git cannot answer. An Add whose parent
    directory does not exist yet is not a failure: the implementation creates
    the directory.
    """
    print("\n[N1] Analyzing codebase...")

    files_to_modify = state.get("files_to_modify", [])
    lld_content = state.get("lld_content", "")
    issue_number = state.get("issue_number", 0)

    # Resolve repo root — never fall back to cwd (Issue #391)
    repo_root_str = state.get("repo_root", "")
    if not repo_root_str:
        print("    [GUARD] ERROR: repo_root not set in state — cannot analyze codebase")
        return {
            "current_state_snapshots": {},
            "pattern_references": [],
            "error_message": "repo_root not set in state. Pass --repo to the CLI.",
        }
    repo_root = Path(repo_root_str)

    # --------------------------------------------------------------------------
    # GUARD: Must have files to analyze (#3585: an empty plan used to pass
    # with a WARNING, and the drafter specified nothing in particular)
    # --------------------------------------------------------------------------
    if not files_to_modify:
        return _halt(
            issue_number,
            "the LLD's Section 2.1 lists no files to modify, so there is nothing "
            "to specify",
        )
    # --------------------------------------------------------------------------

    try:
        return _analyze(
            files_to_modify, lld_content, repo_root,
            state.get("base_branch", ""), issue_number,
        )
    except (BaseTreeError, CodebaseReadError) as exc:
        return _halt(issue_number, f"{type(exc).__name__}: {exc}")


def _analyze(
    files_to_modify: list[FileToModify],
    lld_content: str,
    repo_root: Path,
    base_branch: str,
    issue_number: Any,
) -> dict[str, Any]:
    """The analysis itself, once the guards have passed.

    Returns the node's success result, or its failure result when the symbol
    gather names a file that did not parse. Raises BaseTreeError or
    CodebaseReadError for anything it cannot read; ``analyze_codebase`` halts
    on both.
    """
    print(f"    Repo root: {repo_root}")
    print(f"    Files to analyze: {len(files_to_modify)}")

    # #2033: plan against the tree the implementation will be built on, not the
    # checkout. Mid-arc a file the LLD calls "Add" is already on the attempt
    # branch, put there by an earlier phase, and specifying it as new is what
    # produced a spec describing modules to create instead of modules to extend.
    files_to_modify, base_notes = reclassify_against_base(
        files_to_modify, repo_root, base_branch
    )
    for note in base_notes:
        print(f"    [BASE] {note}")
    base_ref_name = base_ref(repo_root, base_branch) if base_branch else ""

    # Step 1: Load current content for Modify/Delete files. #3585: the first
    # file that cannot be loaded raises, and the node halts; nothing partial
    # reaches the drafter.
    current_state_snapshots: dict[str, str] = {}
    updated_files: list[FileToModify] = []

    for file_spec in files_to_modify:
        loaded, excerpt = _load_planned_file(
            file_spec, repo_root, base_ref_name, lld_content
        )
        updated_files.append(loaded)
        if excerpt is not None:
            current_state_snapshots[loaded["path"]] = excerpt

    print(f"    Loaded {len(current_state_snapshots)} file excerpts")

    # Step 2: Find similar implementation patterns
    pattern_references = find_pattern_references(files_to_modify, repo_root)
    print(f"    Found {len(pattern_references)} pattern references")

    for ref in pattern_references[:3]:
        print(
            f"      - {ref['file_path']}:{ref['start_line']}-{ref['end_line']} "
            f"({ref['pattern_type']})"
        )
    if len(pattern_references) > 3:
        print(f"      ... and {len(pattern_references) - 3} more")

    # Step 3: Build project context (Issue #409 Gap 1)
    project_context = _build_project_context(repo_root)
    if project_context:
        print(f"    Project context: {len(project_context):,} chars")

    # Step 4: Extract import dependencies (Issue #409 Gap 3)
    import_dependencies = _extract_import_dependencies(
        files_to_modify, repo_root
    )
    if import_dependencies:
        print(f"    Import dependencies: {len(import_dependencies):,} chars")

    # Issue #490: Compute repo structure once, cache in state
    repo_structure = get_repo_structure(str(repo_root))

    # Closes #1527: Extract symbol names from all gathered Python file content.
    # Runs over the full current_content (before excerpt trimming) so that
    # methods defined deep in a class body are captured.
    # #2393: the gather reports what it could NOT read. An unparseable
    # target-repo file used to be regex-scraped into the symbol universe
    # silently, then excluded with a line on stdout. #3585: it halts, since a
    # spec judged against a smaller universe than the repo has is judged
    # wrongly. The excerpt step above already halts on such a file; this is
    # the backstop for the yardstick itself.
    gather = gather_symbols(updated_files)
    gathered_symbols = gather.symbols
    if gather.unreadable:
        return _halt(issue_number, gather.describe())

    # #2052: the plan is not the universe. This gathered only files_to_modify,
    # so a spec CALLING an earlier phase's API without modifying its file was
    # judged hallucinated -- boostgauge #2 was blocked for using
    # Telltale.current_peak(), which #41 landed on the base, because
    # telltale.py was not in #2's plan. Mid-arc, calling earlier phases' APIs
    # is the entire point of accumulation, so the base tree's symbols join the
    # universe. No base branch -> unchanged behavior.
    if base_ref_name:
        base_symbols = _extract_symbols_from_base(repo_root, base_ref_name)
        before = len(gathered_symbols)
        gathered_symbols = sorted(set(gathered_symbols) | base_symbols)
        print(
            f"    Gathered {before} planned-file symbol(s) + "
            f"{len(base_symbols)} from {base_ref_name} for API check"
        )
    else:
        print(f"    Gathered {len(gathered_symbols)} target-repo symbols for API check")

    # #2054: names alone were not enough. The drafter still invented kwargs for
    # APIs outside its plan (Telltale(window_seconds=...) against #41's actual
    # parameter -- 41 of 74 tests failed on one TypeError, twice). Ride the
    # base's declared signatures into the drafter's context via
    # project_context, which reaches both the initial and revision prompts.
    if base_ref_name:
        surface = _base_api_surface(repo_root, base_ref_name)
        if surface:
            project_context = (
                f"{project_context}\n\n{surface}" if project_context else surface
            )
            print(
                f"    [BASE] API surface of {base_ref_name} added to drafter "
                f"context ({len(surface):,} chars)"
            )

    return {
        "current_state_snapshots": current_state_snapshots,
        "pattern_references": pattern_references,
        "project_context": project_context,
        "import_dependencies": import_dependencies,
        "files_to_modify": updated_files,
        "repo_structure": repo_structure,
        "gathered_symbols": gathered_symbols,
        "error_message": "",
    }


def _load_planned_file(
    file_spec: FileToModify,
    repo_root: Path,
    base_ref_name: str,
    lld_content: str,
) -> tuple[FileToModify, str | None]:
    """One planned file, with its content loaded, and its excerpt.

    Returns ``(file, excerpt)``: a Modify or Delete target with its content
    and excerpt, or an Add with no content and ``None``.

    Raises:
        CodebaseReadError: a Modify or Delete target that does not exist, is
            not a file, cannot be read or does not parse, or an unknown change
            type (#3585). Each used to be passed on with no content and a
            WARNING on stdout, and the drafter specified a change to a file
            nobody had read.
        BaseTreeError: the base cannot be read.
    """
    file_path = file_spec["path"]
    change_type = file_spec["change_type"]
    full_path = repo_root / file_path

    if change_type == "Add":
        # An Add may create its own package, so a parent that does not exist
        # yet is the plan, not a failure: the implementation makes the
        # directory.
        parent = full_path.parent
        if not parent.exists():
            print(f"    Parent directory does not exist yet for Add: {parent}")
        else:
            print(f"    Verified parent exists: {file_path}")
        return FileToModify(
            path=file_path,
            change_type=change_type,
            description=file_spec["description"],
            current_content=None,
        ), None

    if change_type not in CHANGE_TYPES:
        raise CodebaseReadError(
            f"{file_path} has change type {change_type!r}, which is not one of "
            f"{', '.join(CHANGE_TYPES)}"
        )

    # #2033: the checkout is on the default branch, so a file an earlier phase
    # landed on the attempt branch is absent here while being very much
    # present in the tree the implementation is cut from. Read the base before
    # concluding the file does not exist. Asked with exists_on_base rather than
    # by the content: an empty file the base ships is still the file to modify.
    from_base = (
        not full_path.exists()
        and bool(base_ref_name)
        and exists_on_base(repo_root, base_ref_name, file_path)
    )
    if from_base:
        # A BOM is dropped as the checkout's utf-8-sig read drops it (#2507).
        content = read_from_base(
            repo_root, base_ref_name, file_path
        ).removeprefix(chr(0xFEFF))
        source = f"{file_path} on {base_ref_name}"
    else:
        # ----------------------------------------------------------------------
        # GUARD: File must exist for Modify/Delete
        # ----------------------------------------------------------------------
        if not full_path.exists():
            where = f"the checkout or {base_ref_name}" if base_ref_name else "the checkout"
            raise CodebaseReadError(
                f"{change_type} target {file_path} does not exist in {where}"
            )
        if not full_path.is_file():
            raise CodebaseReadError(f"{change_type} target {file_path} is not a file")

        try:
            file_size = full_path.stat().st_size
        except OSError as exc:
            raise CodebaseReadError(
                f"cannot stat the {change_type} target {full_path}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if file_size > MAX_FILE_SIZE_BYTES:
            print(
                f"    [WARN] Large file ({file_size:,} bytes): {file_path} "
                f"— will summarize aggressively"
            )
        content = _read_or_raise(
            full_path, f"the {change_type} target", encoding="utf-8-sig",
        )
        source = file_path

    # #3779 made interface_surface raise on Python that does not parse, where
    # it summarised the file's head as if it were the interface.
    try:
        excerpt = extract_relevant_excerpt(file_path, content, lld_content)
    except SyntaxError as exc:
        raise CodebaseReadError(
            f"{source} does not parse ({_syntax_detail(exc)})"
        ) from exc

    label = f"[BASE] Loaded from {base_ref_name}" if from_base else "Loaded"
    print(f"    {label}: {file_path} ({len(excerpt):,} chars excerpt)")
    return FileToModify(
        path=file_path,
        change_type=change_type,
        description=file_spec["description"],
        current_content=content,
    ), excerpt


# =============================================================================
# Excerpt Extraction
# =============================================================================


def extract_relevant_excerpt(
    file_path: str, content: str, lld_context: str
) -> str:
    """Extract the portion of a file relevant to the change.

    For Python files, uses AST-based summarization to extract imports,
    class/function signatures, and docstrings. For non-Python files,
    returns truncated content.

    If the file is large, the excerpt is further trimmed to stay within
    MAX_EXCERPT_CHARS.

    Args:
        file_path: Relative path to the file (used to determine file type).
        content: Full file content.
        lld_context: LLD content for identifying which parts of the file
            are most relevant to the planned changes.

    Returns:
        Extracted excerpt suitable for inclusion in the Implementation Spec.

    Raises:
        SyntaxError: a Python file that does not parse (#3779); its head used
            to stand in for its interface. The node halts on it (#3585).
    """
    # Determine file type
    suffix = Path(file_path).suffix.lower()

    if suffix in PYTHON_EXTENSIONS:
        excerpt = _summarize_python_file(content)
    elif suffix in (".md", ".txt", ".rst"):
        # For documentation files, return first portion
        excerpt = _truncate_content(content, MAX_EXCERPT_CHARS)
    elif suffix in (".toml", ".yaml", ".yml", ".json", ".cfg", ".ini"):
        # Config files — return full if small, truncate if large
        excerpt = _truncate_content(content, MAX_EXCERPT_CHARS)
    else:
        # Unknown file type — return truncated content
        excerpt = _truncate_content(content, MAX_EXCERPT_CHARS)

    # Final size guard
    if len(excerpt) > MAX_EXCERPT_CHARS:
        excerpt = excerpt[:MAX_EXCERPT_CHARS] + "\n# ... (truncated)\n"

    return excerpt


# The three signature summarizers moved to core (Tiphys, #1688) so the LLD
# stage and this spec stage extract with one yardstick. The `_`-prefixed
# aliases preserve this module's historical import surface — internal
# callers and existing tests are untouched.
#
# F401 is suppressed deliberately (#3483). Two of these three are unused
# *within* this module and exist only to be importable from it, which is what
# "preserve the historical import surface" means. An automated unused-import
# sweep removed them and broke
# `test_spec_stage_aliases_are_the_core_functions`, whose whole point is that
# the move was aliasing rather than copying. The noqa named E402 but not F401,
# so the sweep had no signal to stop at.
from assemblyzero.core.interface_surface import (  # noqa: E402, F401
    summarize_class as _summarize_class,
    summarize_function as _summarize_function,
    summarize_python_file as _summarize_python_file,
)


def _truncate_content(content: str, max_chars: int) -> str:
    """Truncate content to a maximum number of characters.

    Truncates at a line boundary to avoid partial lines.

    Args:
        content: Content to truncate.
        max_chars: Maximum number of characters.

    Returns:
        Truncated content, with a truncation marker if trimmed.
    """
    if len(content) <= max_chars:
        return content

    # Find last newline before max_chars
    truncated = content[:max_chars]
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]

    return truncated + "\n# ... (truncated)\n"


# =============================================================================
# Pattern Reference Discovery
# =============================================================================


def find_pattern_references(
    files_to_modify: list[FileToModify],
    repo_root: Path,
) -> list[PatternRef]:
    """Find similar implementation patterns in the codebase.

    Scans the repository for existing implementations that are similar
    to the files being added or modified. This helps N2 (generate_spec)
    produce code consistent with existing patterns.

    Strategies:
    1. For node files (nodes/*.py): find other node implementations
       in existing workflows
    2. For state files (state.py): find other state definitions
    3. For graph files (graph.py): find other graph constructions
    4. For test files: find similar test patterns

    Args:
        files_to_modify: List of files from the LLD.
        repo_root: Repository root path.

    Returns:
        List of PatternRef dicts with file locations and relevance info.
        Limited to MAX_PATTERN_REFS entries.

    Raises:
        CodebaseReadError: a candidate pattern file cannot be read (#3585).
            It used to be skipped without a word, and the drafter was shown
            other patterns as if those were all there were.
    """
    patterns: list[PatternRef] = []
    seen_paths: set[str] = set()  # Avoid duplicate pattern references

    workflows_dir = repo_root / "assemblyzero" / "workflows"

    for file_spec in files_to_modify:
        file_path = file_spec["path"]

        # Strategy 1: Node implementations → find sibling nodes
        if "/nodes/" in file_path and file_path.endswith(".py"):
            node_patterns = _find_node_patterns(
                file_path, workflows_dir, repo_root, seen_paths
            )
            patterns.extend(node_patterns)

        # Strategy 2: State definitions → find other state.py files
        elif file_path.endswith("state.py"):
            state_patterns = _find_state_patterns(
                workflows_dir, repo_root, seen_paths
            )
            patterns.extend(state_patterns)

        # Strategy 3: Graph definitions → find other graph.py files
        elif file_path.endswith("graph.py"):
            graph_patterns = _find_graph_patterns(
                workflows_dir, repo_root, seen_paths
            )
            patterns.extend(graph_patterns)

        # Strategy 4: Test files → find similar test patterns
        elif file_path.startswith("tests/") and file_path.endswith(".py"):
            test_patterns = _find_test_patterns(
                file_path, repo_root, seen_paths
            )
            patterns.extend(test_patterns)

        # Strategy 5: CLI tools → find existing tool patterns
        elif file_path.startswith("tools/") and file_path.endswith(".py"):
            tool_patterns = _find_tool_patterns(
                repo_root, seen_paths
            )
            patterns.extend(tool_patterns)

        if len(patterns) >= MAX_PATTERN_REFS:
            break

    return patterns[:MAX_PATTERN_REFS]


def _find_node_patterns(
    target_path: str,
    workflows_dir: Path,
    repo_root: Path,
    seen: set[str],
) -> list[PatternRef]:
    """Find existing node implementations as patterns.

    Looks for node files in other workflow packages to serve as
    implementation examples.

    Args:
        target_path: The target node file path from the LLD.
        workflows_dir: Path to assemblyzero/workflows/.
        repo_root: Repository root path.
        seen: Set of already-referenced file paths.

    Returns:
        List of PatternRef for similar node implementations.
    """
    patterns: list[PatternRef] = []

    if not workflows_dir.exists():
        return patterns

    # Find all node files across workflow packages
    for node_file in sorted(workflows_dir.glob("*/nodes/*.py")):
        if node_file.name == "__init__.py":
            continue

        rel_path = str(node_file.relative_to(repo_root)).replace("\\", "/")

        # Skip if this is the target file itself or already seen
        if rel_path == target_path or rel_path in seen:
            continue

        # Read first portion to determine line count
        content = _read_or_raise(node_file, "the node pattern file", encoding="utf-8-sig")

        lines = content.split("\n")
        end_line = min(len(lines), 50)  # First 50 lines for pattern

        # Determine relevance based on name similarity
        target_name = Path(target_path).stem
        node_name = node_file.stem
        relevance = (
            f"Existing node implementation '{node_name}' in "
            f"{node_file.parent.parent.name} workflow"
        )

        # Boost relevance for similarly-named nodes
        if _names_similar(target_name, node_name):
            relevance = f"Similar node '{node_name}' — " + relevance

        patterns.append(PatternRef(
            file_path=rel_path,
            start_line=1,
            end_line=end_line,
            pattern_type="node implementation",
            relevance=relevance,
        ))
        seen.add(rel_path)

        if len(patterns) >= 3:
            break

    return patterns


def _find_state_patterns(
    workflows_dir: Path,
    repo_root: Path,
    seen: set[str],
) -> list[PatternRef]:
    """Find existing state.py definitions as patterns.

    Args:
        workflows_dir: Path to assemblyzero/workflows/.
        repo_root: Repository root path.
        seen: Set of already-referenced file paths.

    Returns:
        List of PatternRef for state definitions.
    """
    patterns: list[PatternRef] = []

    if not workflows_dir.exists():
        return patterns

    for state_file in sorted(workflows_dir.glob("*/state.py")):
        rel_path = str(state_file.relative_to(repo_root)).replace("\\", "/")
        if rel_path in seen:
            continue

        content = _read_or_raise(state_file, "the state pattern file", encoding="utf-8-sig")

        lines = content.split("\n")
        end_line = min(len(lines), 100)

        workflow_name = state_file.parent.name
        patterns.append(PatternRef(
            file_path=rel_path,
            start_line=1,
            end_line=end_line,
            pattern_type="state definition",
            relevance=f"TypedDict state definition from {workflow_name} workflow",
        ))
        seen.add(rel_path)

        if len(patterns) >= 2:
            break

    return patterns


def _find_graph_patterns(
    workflows_dir: Path,
    repo_root: Path,
    seen: set[str],
) -> list[PatternRef]:
    """Find existing graph.py definitions as patterns.

    Args:
        workflows_dir: Path to assemblyzero/workflows/.
        repo_root: Repository root path.
        seen: Set of already-referenced file paths.

    Returns:
        List of PatternRef for graph constructions.
    """
    patterns: list[PatternRef] = []

    if not workflows_dir.exists():
        return patterns

    for graph_file in sorted(workflows_dir.glob("*/graph.py")):
        rel_path = str(graph_file.relative_to(repo_root)).replace("\\", "/")
        if rel_path in seen:
            continue

        content = _read_or_raise(graph_file, "the graph pattern file", encoding="utf-8-sig")

        lines = content.split("\n")
        end_line = min(len(lines), 100)

        workflow_name = graph_file.parent.name
        patterns.append(PatternRef(
            file_path=rel_path,
            start_line=1,
            end_line=end_line,
            pattern_type="graph construction",
            relevance=f"LangGraph workflow definition from {workflow_name} workflow",
        ))
        seen.add(rel_path)

        if len(patterns) >= 2:
            break

    return patterns


def _find_test_patterns(
    target_path: str,
    repo_root: Path,
    seen: set[str],
) -> list[PatternRef]:
    """Find similar test files as patterns.

    Args:
        target_path: The target test file path from the LLD.
        repo_root: Repository root path.
        seen: Set of already-referenced file paths.

    Returns:
        List of PatternRef for test patterns.
    """
    patterns: list[PatternRef] = []
    tests_dir = repo_root / "tests"

    if not tests_dir.exists():
        return patterns

    # Look for test files with similar naming
    target_name = Path(target_path).stem

    for test_file in sorted(tests_dir.glob("**/*.py")):
        if test_file.name == "__init__.py":
            continue

        rel_path = str(test_file.relative_to(repo_root)).replace("\\", "/")
        if rel_path == target_path or rel_path in seen:
            continue

        # Prefer workflow-related tests
        if "workflow" in test_file.name.lower():
            content = _read_or_raise(test_file, "the test pattern file", encoding="utf-8-sig")

            lines = content.split("\n")
            end_line = min(len(lines), 80)

            patterns.append(PatternRef(
                file_path=rel_path,
                start_line=1,
                end_line=end_line,
                pattern_type="test pattern",
                relevance=f"Existing workflow test: {test_file.name}",
            ))
            seen.add(rel_path)

            if len(patterns) >= 2:
                break

    return patterns


def _find_tool_patterns(
    repo_root: Path,
    seen: set[str],
) -> list[PatternRef]:
    """Find existing CLI tool scripts as patterns.

    Args:
        repo_root: Repository root path.
        seen: Set of already-referenced file paths.

    Returns:
        List of PatternRef for CLI tool patterns.
    """
    patterns: list[PatternRef] = []
    tools_dir = repo_root / "tools"

    if not tools_dir.exists():
        return patterns

    # Find existing run_*.py tools
    for tool_file in sorted(tools_dir.glob("run_*.py")):
        rel_path = str(tool_file.relative_to(repo_root)).replace("\\", "/")
        if rel_path in seen:
            continue

        content = _read_or_raise(tool_file, "the tool pattern file", encoding="utf-8-sig")

        lines = content.split("\n")
        end_line = min(len(lines), 60)

        patterns.append(PatternRef(
            file_path=rel_path,
            start_line=1,
            end_line=end_line,
            pattern_type="CLI tool",
            relevance=f"Existing CLI tool pattern: {tool_file.name}",
        ))
        seen.add(rel_path)

        if len(patterns) >= 2:
            break

    return patterns


# =============================================================================
# Utility
# =============================================================================


def _build_project_context(repo_root: Path) -> str:
    """Build project context from CLAUDE.md, README, and metadata.

    Issue #409 Gap 1: Inject project-level conventions and rules
    into the spec generation prompt.

    Args:
        repo_root: Repository root path.

    Returns:
        Formatted project context string, or empty if nothing found.

    A file that is absent gives no context, which is an answer: not every repo
    has a CLAUDE.md. One that exists and cannot be read raises
    CodebaseReadError naming it (#3585); it used to be dropped without a word,
    and the drafter wrote without the project's rules.
    """
    parts: list[str] = []
    read = {"encoding": "utf-8-sig", "errors": "replace"}

    # CLAUDE.md conventions
    claude_md_path = repo_root / "CLAUDE.md"
    if claude_md_path.exists():
        content = _read_or_raise(claude_md_path, "the project rules", **read)
        # Keep first 2000 chars — enough for key rules
        if len(content) > 2000:
            content = content[:2000] + "\n... (truncated)"
        parts.append(f"### CLAUDE.md (Project Rules)\n\n{content}")

    # README summary
    readme_path = repo_root / "README.md"
    if readme_path.exists():
        content = _read_or_raise(readme_path, "the project README", **read)
        # Just first 1500 chars for project overview
        if len(content) > 1500:
            content = content[:1500] + "\n... (truncated)"
        parts.append(f"### README (Project Overview)\n\n{content}")

    # Project metadata from pyproject.toml
    pyproject_path = repo_root / "pyproject.toml"
    if pyproject_path.exists():
        content = _read_or_raise(pyproject_path, "the project metadata", **read)
        # Extract just [tool.poetry] or [project] section (first 500 chars)
        # Don't include full dependency list
        lines = content.splitlines()
        meta_lines = []
        in_section = False
        for line in lines:
            if line.strip().startswith("[tool.poetry]") or line.strip().startswith("[project]"):
                in_section = True
            elif line.strip().startswith("[") and in_section:
                break
            if in_section:
                meta_lines.append(line)
            if len(meta_lines) > 15:
                break
        if meta_lines:
            parts.append(
                "### Project Metadata\n\n```toml\n"
                + "\n".join(meta_lines)
                + "\n```"
            )

    if not parts:
        return ""

    return "## Project Context\n\n" + "\n\n".join(parts)


def _extract_import_dependencies(
    files_to_modify: list[FileToModify],
    repo_root: Path,
) -> str:
    """Extract intra-project import dependencies for files_to_modify.

    Issue #409 Gap 3: Map which files import from which, so the spec
    drafter understands file ordering and coupling.

    Args:
        files_to_modify: List of files from the LLD.
        repo_root: Repository root path.

    Returns:
        Formatted import dependency map, or empty if nothing found.

    A file not yet on disk (an Add) has no imports, which is an answer. One
    that exists and cannot be read or parsed raises CodebaseReadError naming
    it (#3585); it used to vanish from the map without a word.
    """
    dep_map: dict[str, list[str]] = {}

    for file_spec in files_to_modify:
        file_path = file_spec["path"]
        full_path = repo_root / file_path

        if not full_path.exists() or not file_path.endswith(".py"):
            continue

        # utf-8-sig, not utf-8 (#2507): a UTF-8 BOM survives a plain
        # utf-8 read as U+FEFF, which ast.parse rejects -- so a BOM'd
        # file silently vanished from the drafter's context here while
        # Python's own importer ran it fine. Identical to the repair
        # fail_open_audit made to itself; utf-8-sig == utf-8 when no
        # BOM is present.
        content = _read_or_raise(
            full_path, "the planned file for its imports", encoding="utf-8-sig",
        )
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as exc:
            raise CodebaseReadError(
                f"the planned file {file_path} does not parse, so its imports "
                f"cannot be mapped ({_syntax_detail(exc)})"
            ) from exc

        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        if imports:
            dep_map[file_path] = imports

    if not dep_map:
        return ""

    # Format as readable text
    lines = ["## Import Dependencies (files_to_modify)\n"]
    for file_path, imports in sorted(dep_map.items()):
        filename = Path(file_path).name
        import_list = ", ".join(imports[:10])
        if len(imports) > 10:
            import_list += f" (+{len(imports) - 10} more)"
        lines.append(f"- **{filename}** imports: {import_list}")

    return "\n".join(lines)


def _list_base_python_files(repo_root: Path, base_ref_name: str) -> list[str]:
    """Every non-test .py path on the base ref.

    Raises:
        BaseTreeError: git cannot list the base (#3585). It used to return
            [], which read as a base with no Python, so the API surface and
            the symbol universe silently lost the whole base.

    #3585: the list is no longer capped at 200. Past the cap, calls into the
    files left out were judged against a universe that did not hold them, and
    a stdout note was all that said so.
    """
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--full-tree", "--name-only", base_ref_name],
        cwd=str(repo_root), capture_output=True, text=True, check=False,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "(no stderr)"
        raise BaseTreeError(
            f"cannot list the Python files on {base_ref_name}: `git ls-tree` in "
            f"{repo_root} exited {result.returncode}: {stderr}"
        )
    return [
        p.strip() for p in result.stdout.splitlines()
        if p.strip().endswith(".py") and not p.strip().startswith("tests/")
    ]


def _base_api_surface(
    repo_root: Path, base_ref_name: str, max_chars: int = 12_000
) -> str:
    """Signatures of everything the base publishes, for the drafter (#2054).

    #2052 taught the CHECKER the base's symbol names, so a call to
    Telltale.current_peak() stopped being flagged as hallucinated. The DRAFTER
    still could not see the signatures of files outside its plan, so it
    invented kwargs: boostgauge #2 called Telltale(window_seconds=...) against
    #41's actual parameter and 41 of 74 tests failed on one TypeError, twice,
    until the stagnation guard halted the stage.

    A phase that must CALL an earlier phase's API needs to read that API's
    declaration, exactly as a human would before writing the call.

    Raises:
        BaseTreeError: git cannot list or read the base (#3585).
        CodebaseReadError: a base file does not parse (#3779 made the
            summariser raise; it used to summarise the file's head).

    A base file that is empty (an empty ``__init__.py``) has no interface and
    is skipped; ls-tree listed it, so read_from_base's "" can only mean empty.
    """
    sections: list[str] = [
        "## Existing APIs on the integration branch "
        "(call these EXACTLY as declared — do not invent parameter names)"
    ]
    total = len(sections[0])
    truncated = False
    for rel in _list_base_python_files(repo_root, base_ref_name):
        content = read_from_base(repo_root, base_ref_name, rel)
        if not content:
            continue
        try:
            # The BOM, as in _extract_symbols_from_base (#2507).
            summary = _summarize_python_file(content.removeprefix(chr(0xFEFF))).strip()
        except SyntaxError as exc:
            raise CodebaseReadError(
                f"{rel} on {base_ref_name} does not parse, so its API cannot be "
                f"shown to the drafter ({_syntax_detail(exc)})"
            ) from exc
        if not summary:
            continue
        block = f"### {rel}\n{summary}"
        if total + len(block) > max_chars:
            truncated = True
            break
        sections.append(block)
        total += len(block)
    if len(sections) == 1:
        return ""
    if truncated:
        sections.append(
            "(base API surface truncated — files beyond the budget omitted)"
        )
    return "\n\n".join(sections)


def _extract_symbols_from_base(repo_root: Path, base_ref_name: str) -> set[str]:
    """Class/function names from every non-test .py on the base ref (#2052).

    Read through git, never the checkout -- the checkout sits on the default
    branch and mid-arc carries none of the arc (#2033's two-trees rule).
    Tests are excluded (their helpers are not an API surface).

    Raises:
        BaseTreeError: git cannot list or read the base (#3585). It used to
            return an empty or partial set, so correct calls into the base
            were flagged as hallucinated.
        CodebaseReadError: a base file does not parse (#3585). Its names used
            to be scraped by regex, the fallback #2393 removed from the
            planned files' gather.

    #3585: the sweep is no longer capped at 200 files; past the cap the check
    judged calls into the uncovered files against a universe without them.
    """
    symbols: set[str] = set()
    for rel in _list_base_python_files(repo_root, base_ref_name):
        content = read_from_base(repo_root, base_ref_name, rel)
        if not content:
            continue
        # A BOM in the committed blob survives git-show's decode as U+FEFF,
        # which ast.parse rejects (#2507).
        content = content.removeprefix(chr(0xFEFF))
        try:
            tree = ast.parse(content, filename=rel)
        except SyntaxError as exc:
            raise CodebaseReadError(
                f"{rel} on {base_ref_name} does not parse, so its symbols cannot "
                f"join the universe the spec is checked against "
                f"({_syntax_detail(exc)})"
            ) from exc
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.add(node.name)
    return symbols


@dataclass
class SymbolGather:
    """The symbol universe, and what could not be read into it (#2393)."""

    symbols: list[str]
    #: (path, parse error) for every `.py` file that would not parse.
    unreadable: list[tuple[str, str]]

    def describe(self) -> str:
        """One line naming what did not parse, or "" when everything did.

        The node halts with this line as its reason (#3585).
        """
        if not self.unreadable:
            return ""
        listed = "; ".join(f"{path} ({err})" for path, err in self.unreadable[:3])
        more = (
            f" (and {len(self.unreadable) - 3} more)"
            if len(self.unreadable) > 3
            else ""
        )
        return (
            f"{len(self.unreadable)} target-repo .py file(s) did not parse: "
            f"{listed}{more}. Without them the spec would be judged against a "
            f"smaller universe than the repo has (#2393), so the stage halts (#3585)."
        )


def gather_symbols(files: list[FileToModify]) -> SymbolGather:
    """Class and function names from gathered Python files, plus the misses.

    Closes #1527: produces the symbol set N3's API-hallucination check judges
    every spec against.

    #2393 removed a regex fallback that scraped `^\\s*def (\\w+)` and
    `^\\s*class (\\w+)` out of files that would not parse. That fallback fed
    the YARDSTICK rather than the document being measured, so its errors were
    the hardest kind to see: a name regex invents becomes a false clearance,
    and a name it misses becomes a false hallucination flag. #2391 is a live
    example of what a wrong symbol universe costs -- three revision cycles and
    a dead stage -- and that universe was merely incomplete rather than
    fabricated.

    Standard 0028 section 3 permits deterministic scans of the pipeline's own
    documents on the condition that they "cannot mask a contract failure
    because there is no contract: the document is what it is". A `.py` file in
    the target repo IS a contract that its content is Python. A file that will
    not parse is a real finding about the target repo, and section 4 is direct:
    "No function returns an empty result, an UNKNOWN, or a silent downgrade
    because it could not read its input."

    So an unparseable file is named, with its parse error, in ``unreadable``,
    and this function still gathers every file that does parse. #3585 (ADR
    0236): what the caller does with that list changed. The node used to print
    the exclusion and go on; it now halts, because a spec checked against a
    universe missing a file is checked wrongly, and only the operator can mend
    the file.
    """
    symbols: set[str] = set()
    unreadable: list[tuple[str, str]] = []

    for file_spec in files:
        content = file_spec.get("current_content")
        path = file_spec.get("path", "")

        if not content or not path.endswith(".py"):
            continue

        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            detail = f"line {exc.lineno}: {exc.msg}" if exc.lineno else exc.msg
            unreadable.append((path, detail))
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.add(node.name)

    return SymbolGather(symbols=sorted(symbols), unreadable=unreadable)


def _extract_symbols_from_files(files: list[FileToModify]) -> list[str]:
    """The symbol list alone.

    Raises:
        CodebaseReadError: a file did not parse (#3585). This used to return
            the smaller list without a word, for callers that do not report
            exclusions; a caller that wants the misses uses gather_symbols.
    """
    gather = gather_symbols(files)
    if gather.unreadable:
        raise CodebaseReadError(gather.describe())
    return gather.symbols


def _names_similar(name_a: str, name_b: str) -> bool:
    """Check if two identifier names are similar.

    Uses a simple heuristic: checks if the names share significant
    word overlap (splitting on underscores).

    Args:
        name_a: First identifier name.
        name_b: Second identifier name.

    Returns:
        True if names share at least one significant word.
    """
    # Split on underscores and filter short words
    words_a = {w.lower() for w in name_a.split("_") if len(w) > 2}
    words_b = {w.lower() for w in name_b.split("_") if len(w) > 2}

    if not words_a or not words_b:
        return False

    # Check for word overlap
    return bool(words_a & words_b)
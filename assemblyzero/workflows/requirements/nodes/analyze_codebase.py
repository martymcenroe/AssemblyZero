"""N0.5: Codebase analysis node for Requirements Workflow.

Issue #401: Codebase Context Analysis for Requirements Workflow.

Reads key project files, scans patterns, identifies dependencies, and finds
issue-related code in the target repository. Injects a CodebaseContext dict
into the LangGraph state so the drafter node can produce LLDs grounded in
real codebase structure and conventions.

This node runs before the draft_lld node and after load_input.

#3585 (ADR 0236): an analysis that cannot read what it analyzes returns
``error_message``, which ``route_after_analyze_codebase`` sends to HALT
before N0c spends a model call, and HALT alerts. That covers a missing repo
path, a selected file that cannot be read, a listing that fails and a Tiphys
extraction that raises. A file left out to fit the token budget is a designed
cap and is named in the log; a sensitive, binary or empty file is skipped.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Any

from assemblyzero.core.interface_surface import build_interface_map
from assemblyzero.utils.codebase_reader import (
    BINARY_EXTENSIONS,
    FileReadResult,
    is_sensitive_file,
    parse_project_metadata,
    read_files_within_budget,
)
from assemblyzero.utils.pattern_scanner import (
    detect_frameworks,
    extract_conventions_from_claude_md,
    scan_patterns,
)

logger = logging.getLogger(__name__)

# Stop words filtered from issue text during keyword extraction.
# Kept in sync with validate_mechanical.py STOPWORDS but scoped locally
# for independence.
_STOP_WORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "if", "when", "where",
    "how", "what", "which", "who", "whom", "why", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "no", "not",
    "only", "same", "so", "than", "too", "very", "just", "also", "any",
    "into", "over", "after", "before", "between", "through", "about",
    "then", "them", "they", "their", "there", "here", "been", "being",
    "make", "like", "many", "much", "well", "back", "even", "still",
    "also", "made", "want", "give", "take", "come", "good", "look",
    "know", "help", "tell", "work", "call", "find", "keep", "turn",
    "seem", "show", "part", "long", "open", "type", "file", "line",
    "code", "issue", "feature", "implement", "using", "used", "uses",
    "added", "adds", "update", "updated", "create", "created", "change",
    "changes", "changed", "support", "handle", "handles", "test", "tests",
    "error", "errors", "data", "value", "values", "name", "names",
    "path", "paths", "node", "nodes", "func", "function", "method",
    "class", "module", "import", "config", "state", "result",
}

# Total token budget for all file reads (Issue #401, Section 2.4).
_TOTAL_TOKEN_BUDGET: int = 15_000

# Per-file token budget (Issue #401, Section 2.4).
_PER_FILE_TOKEN_BUDGET: int = 3_000

# Maximum number of related files to return.
_MAX_RELATED_FILES: int = 5


def _loud(message: str) -> str:
    """One ERROR line on stderr and in the log (ADR 0236 property 1)."""
    logger.error("[N0b] %s", message)
    print(f"ERROR [N0b] {message}", file=sys.stderr, flush=True)
    return message


class UnreadableSelectedFile(RuntimeError):
    """A file the analysis selected could not be read (#3585)."""


def _unread_selected(
    selected: list[Path],
    results: list[FileReadResult],
    total_budget: int,
) -> list[Path]:
    """The selected files left out to fit the budget (#3585).

    ``read_files_within_budget`` returns only the files it read with content,
    so a selected file can be missing from its results for one of four
    reasons. Sensitive and binary files are skipped by design, and an empty
    file has nothing to read: all three stay quiet. A file after the total
    budget ran out is a designed cap: it is returned so the caller names it in
    the log. Anything else could not be read, and the drafter would design
    without it. The reader logs that at DEBUG and returns nothing, so this is
    the only place it is seen, and it raises.

    Raises:
        UnreadableSelectedFile: naming the first selected file that could not
            be read, and why.
    """
    by_path = {r["path"]: r for r in results}
    used = 0
    budget_dropped: list[Path] = []
    for path in selected:
        hit = by_path.get(str(path))
        if hit is not None:
            used += hit["token_estimate"]
            continue
        if is_sensitive_file(path) or path.suffix.lower() in BINARY_EXTENSIONS:
            continue
        if used >= total_budget:
            budget_dropped.append(path)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnreadableSelectedFile(f"{path}: {type(exc).__name__}: {exc}") from exc
        if text.strip():
            raise UnreadableSelectedFile(
                f"{path}: it has content and the budgeted reader returned none"
            )
    return budget_dropped


def _empty_codebase_context() -> dict[str, Any]:
    """Return an empty CodebaseContext dict.

    Used as the default/fallback when analysis cannot proceed.
    """
    return {
        "project_description": "",
        "conventions": [],
        "frameworks": [],
        "module_structure": "",
        "key_file_excerpts": {},
        "related_code": {},
        "dependency_summary": "",
        "directory_tree": "",
        "code_patterns": {},
    }


def analyze_codebase(state: dict) -> dict:
    """LangGraph node that reads key project files, scans patterns,
    identifies dependencies, and finds issue-related code.

    Injects CodebaseContext into state for the drafter node.

    Args:
        state: LangGraph state dict containing at minimum:
            - target_repo (str | None): Path to target repository
              (aliased from repo_path for compatibility)
            - issue_body (str): The GitHub issue body
            - issue_text (str): Alternative key for issue body
            - directory_tree (str): Pre-computed directory listing from #389

    Returns:
        dict with ``codebase_context`` and ``interface_map``, or with
        ``error_message`` (#3585) when the analysis cannot read what it
        analyzes, which routes to HALT.
    """
    # Extract repo_path from state – support both 'repo_path' and 'target_repo'
    repo_path_str: str | None = state.get("repo_path") or state.get("target_repo")

    # #3585: both used to return an empty context with a warning, and the
    # drafter designed against nothing.
    if not repo_path_str or not str(repo_path_str).strip():
        return {"error_message": _loud(
            "LLD analysis has no repo path (neither repo_path nor target_repo "
            "is set), so there is no codebase to ground the design in"
        )}

    repo_path = Path(repo_path_str)
    if not repo_path.is_dir():
        return {"error_message": _loud(
            f"LLD analysis cannot read the repo {repo_path}: it is not a "
            f"directory, so there is no codebase to ground the design in"
        )}

    # Resolve to absolute to ensure consistent path handling
    repo_path = repo_path.resolve()

    # ------------------------------------------------------------------
    # #2684: the tree the LLD is designed against is the ARC's, not the
    # checkout's. The checkout stands on the default branch (#2012); mid-arc
    # that tree can carry code the arc does not have, and a drafter that reads
    # it designs from the answer. Cut (or reuse) the LLD worktree from
    # origin/<base_branch> now and read from it; finalize finds it present and
    # rides it, so the LLD PR carries the base's tree rather than HEAD's.
    # Fail closed: if the arc cannot be cut, halt — reading the checkout
    # instead would be the leak this exists to stop, made silent.
    # ------------------------------------------------------------------
    base_branch = str(state.get("base_branch", "") or "")
    issue_number = state.get("issue_number")
    # #3512: a mock run is an offline rehearsal. N5 already cuts no branch
    # and opens no PR under the flag (#2288); this is the same flag read the
    # same way. No fetch, no worktree, no branch. Reading the checkout here is
    # not #2684's leak: the mock drafter reads nothing it is given.
    if base_branch and issue_number and state.get("config_mock_mode"):
        print(
            f"    [mock] no LLD worktree cut and no fetch of origin/{base_branch}; "
            f"analysis reads the checkout"
        )
    elif base_branch and issue_number:
        from assemblyzero.workflows.requirements.git_operations import (
            GitOperationError,
            setup_lld_worktree,
        )

        try:
            worktree_path, _branch = setup_lld_worktree(
                repo_path, int(issue_number), base_branch=base_branch,
            )
        except GitOperationError as exc:
            logger.error("LLD analysis cannot read the arc: %s", exc)
            return {
                "codebase_context": _empty_codebase_context(),
                "interface_map": {},
                "error_message": (
                    f"LLD analysis cannot read the arc: {exc}. Refusing to read "
                    f"the checkout ({repo_path}) in its place (#2684)."
                ),
            }
        print(f"    [BASE] LLD analysis reads origin/{base_branch} via {worktree_path}")
        repo_path = Path(worktree_path).resolve()

    # Extract issue text – try several state keys
    issue_text: str = (
        state.get("issue_text", "")
        or state.get("issue_body", "")
        or ""
    )

    # Directory tree from #389 (may be absent)
    directory_tree: str = state.get("directory_tree", "")

    # ------------------------------------------------------------------
    # Step 1: Select and read key files
    # ------------------------------------------------------------------
    # #3585: a listing that fails raises from the helpers (it used to pass),
    # and a selected file that cannot be read halts (it was left out).
    try:
        key_files = _select_key_files(repo_path)
    except OSError as exc:
        return {"error_message": _loud(
            f"LLD analysis cannot list the key files of {repo_path}: "
            f"{type(exc).__name__}: {exc}"
        )}
    key_read_results = read_files_within_budget(
        key_files,
        total_budget=_TOTAL_TOKEN_BUDGET,
        per_file_budget=_PER_FILE_TOKEN_BUDGET,
    )
    try:
        budget_dropped = _unread_selected(
            key_files, key_read_results, _TOTAL_TOKEN_BUDGET
        )
    except UnreadableSelectedFile as exc:
        return {"error_message": _loud(
            f"LLD analysis cannot read a selected key file in {repo_path}: {exc}"
        )}
    if budget_dropped:
        logger.warning(
            "Codebase analysis: %d key file(s) left out to fit the %d-token budget: %s",
            len(budget_dropped), _TOTAL_TOKEN_BUDGET,
            ", ".join(str(p) for p in budget_dropped),
        )

    # Build key_file_excerpts and file_contents for pattern scanning
    key_file_excerpts: dict[str, str] = {}
    file_contents: dict[str, str] = {}
    tokens_used = 0
    for result in key_read_results:
        if result["content"]:
            rel = result["path"]
            key_file_excerpts[rel] = result["content"]
            file_contents[rel] = result["content"]
            tokens_used += result["token_estimate"]

    # ------------------------------------------------------------------
    # Step 2: Parse project metadata
    # ------------------------------------------------------------------
    metadata = parse_project_metadata(repo_path)
    dependency_summary = metadata.get("dependencies", "")
    dep_list = [
        d.strip() for d in dependency_summary.split(",") if d.strip()
    ] if dependency_summary else []

    # ------------------------------------------------------------------
    # Step 3: Scan code patterns
    # ------------------------------------------------------------------
    # #1816: this result was computed and discarded since the original #401
    # build, despite #401's acceptance explicitly listing "existing code
    # patterns are injected into the drafter prompt". Wired in: detected
    # fields only ("unknown" values carry no signal and are dropped).
    pattern_analysis = scan_patterns(file_contents)
    code_patterns: dict[str, str] = {
        k: v for k, v in pattern_analysis.items() if v and v != "unknown"
    }

    # ------------------------------------------------------------------
    # Step 4: Detect frameworks
    # ------------------------------------------------------------------
    frameworks = detect_frameworks(dep_list, file_contents)

    # ------------------------------------------------------------------
    # Step 5: Extract conventions from CLAUDE.md
    # ------------------------------------------------------------------
    conventions: list[str] = []
    for rel_path, content in file_contents.items():
        if Path(rel_path).name.upper() == "CLAUDE.MD":
            conventions = extract_conventions_from_claude_md(content)
            break

    # ------------------------------------------------------------------
    # Step 6: Build project description from README / CLAUDE.md
    # ------------------------------------------------------------------
    project_description = _build_project_description(file_contents, metadata)

    # ------------------------------------------------------------------
    # Step 7: Build module structure summary
    # ------------------------------------------------------------------
    module_structure = _build_module_structure(directory_tree, file_contents)

    # ------------------------------------------------------------------
    # Step 8: Find issue-related files and read them
    # ------------------------------------------------------------------
    remaining_budget = max(0, _TOTAL_TOKEN_BUDGET - tokens_used)
    related_code: dict[str, str] = {}
    # Full related list, pre-exclusion, kept for Tiphys interface extraction
    # (Step 8b) — the name-based exclusion below exists only to avoid
    # double-reading contents, which doesn't apply to signature extraction.
    related_paths_all: list[Path] = []

    if issue_text and directory_tree:
        try:
            related_paths = _find_related_files(repo_path, issue_text, directory_tree)
        except OSError as exc:
            return {"error_message": _loud(
                f"LLD analysis cannot search {repo_path} for the files the "
                f"issue names: {type(exc).__name__}: {exc}"
            )}
        related_paths_all = list(related_paths)
        # Exclude files already read as key files
        already_read = {Path(p).name for p in key_file_excerpts}
        related_paths = [
            p for p in related_paths if p.name not in already_read
        ]

        related_results = (
            read_files_within_budget(
                related_paths,
                total_budget=remaining_budget,
                per_file_budget=_PER_FILE_TOKEN_BUDGET,
            )
            if related_paths and remaining_budget > 0
            else []
        )
        try:
            budget_dropped = _unread_selected(
                related_paths, related_results, remaining_budget
            )
        except UnreadableSelectedFile as exc:
            return {"error_message": _loud(
                f"LLD analysis cannot read a related file in {repo_path}: {exc}"
            )}
        if budget_dropped:
            logger.warning(
                "Codebase analysis: %d related file(s) left out to fit the "
                "remaining %d-token budget: %s",
                len(budget_dropped), remaining_budget,
                ", ".join(str(p) for p in budget_dropped),
            )
        for result in related_results:
            related_code[result["path"]] = result["content"]

    # ------------------------------------------------------------------
    # Step 8b: Tiphys (#1688) — ground-truth interface surface.
    # Size-adaptive: small repos ship their whole public surface (no
    # selection, no selection miss); large repos use explicit-path +
    # keyword selection with one-hop import expansion.
    #
    # #3585: a failure halts. It used to leave the map empty with a warning,
    # so the drafter worked blind on the very repo this exists to ground it
    # in; interface_surface raises since #3779. A repo with no Python files
    # has an empty surface, which is an answer, not a failure.
    # ------------------------------------------------------------------
    try:
        interface_map = build_interface_map(
            repo_path,
            issue_text=issue_text,
            related_paths=related_paths_all,
        )
    except (OSError, SyntaxError, ValueError) as exc:
        return {"error_message": _loud(
            f"LLD analysis cannot extract the interface surface of {repo_path}: "
            f"{type(exc).__name__}: {exc}"
        )}

    # ------------------------------------------------------------------
    # Step 9: Assemble CodebaseContext
    # ------------------------------------------------------------------
    context: dict[str, Any] = {
        "project_description": project_description,
        "conventions": conventions,
        "frameworks": frameworks,
        "module_structure": module_structure,
        "key_file_excerpts": key_file_excerpts,
        "related_code": related_code,
        "dependency_summary": dependency_summary,
        "directory_tree": directory_tree,
        "code_patterns": code_patterns,
    }

    logger.info(
        "Codebase analysis complete: %d key files, %d related files, "
        "%d conventions, %d frameworks detected, %d interface surfaces",
        len(key_file_excerpts),
        len(related_code),
        len(conventions),
        len(frameworks),
        len(interface_map),
    )

    return {"codebase_context": context, "interface_map": interface_map}


def _select_key_files(repo_path: Path) -> list[Path]:
    """Identify key project files to read.

    Priority order:
        1. CLAUDE.md
        2. README.md
        3. pyproject.toml / package.json
        4. docs/standards/\\*.md, docs/adrs/\\*.md (first 3 each)
        5. Top-level __init__.py files (first 5)

    Args:
        repo_path: Resolved absolute path to the repository root.

    Returns:
        Ordered list of file paths by priority.

    Raises:
        OSError: a docs directory or the repo root cannot be listed (#3585);
            the listing used to be skipped without a word.
    """
    files: list[Path] = []

    # Priority 1: CLAUDE.md
    claude_md = repo_path / "CLAUDE.md"
    if claude_md.is_file():
        files.append(claude_md)

    # Priority 2: README.md (case-insensitive search)
    for name in ("README.md", "readme.md", "Readme.md", "README.rst"):
        readme = repo_path / name
        if readme.is_file():
            files.append(readme)
            break

    # Priority 3: pyproject.toml / package.json
    pyproject = repo_path / "pyproject.toml"
    if pyproject.is_file():
        files.append(pyproject)
    package_json = repo_path / "package.json"
    if package_json.is_file():
        files.append(package_json)

    # Priority 4: Architecture docs (first 3 from each)
    for docs_subdir in ("docs/standards", "docs/adrs"):
        docs_dir = repo_path / docs_subdir
        if docs_dir.is_dir():
            md_files = sorted(docs_dir.glob("*.md"))[:3]
            files.extend(md_files)

    # Priority 5: Top-level __init__.py files (first 5)
    init_files: list[Path] = []
    for child in sorted(repo_path.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            init_py = child / "__init__.py"
            if init_py.is_file():
                init_files.append(init_py)
                if len(init_files) >= 5:
                    break
    files.extend(init_files)

    return files


def _find_related_files(
    repo_path: Path,
    issue_text: str,
    directory_tree: str,
) -> list[Path]:
    """Given issue text, find files likely related to the issue by keyword
    matching against file paths in the directory tree.

    Extracts keywords by splitting *issue_text* on whitespace, filtering to
    words >= 4 chars, lowercasing, and removing common stop words.  Matches
    keywords against *directory_tree* lines.

    Args:
        repo_path: Resolved absolute path to the repository root.
        issue_text: The GitHub issue body text.
        directory_tree: Pre-computed directory tree string.

    Returns:
        At most 5 file paths, ordered by match count descending.

    Raises:
        OSError: from ``_search_for_file``, when a directory cannot be walked.
    """
    if not issue_text or not directory_tree:
        return []

    # Extract keywords
    raw_words = re.findall(r"[a-zA-Z_]+", issue_text.lower())
    keywords = [
        w for w in raw_words
        if len(w) >= 4 and w not in _STOP_WORDS
    ]

    if not keywords:
        return []

    # Deduplicate keywords while preserving order
    seen: set[str] = set()
    unique_keywords: list[str] = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)
    keywords = unique_keywords

    # Score each line in directory_tree
    scored: dict[str, int] = {}
    for line in directory_tree.splitlines():
        stripped = line.strip().rstrip("/")
        if not stripped:
            continue
        # Only consider lines that look like files (contain a dot)
        if "." not in stripped:
            continue
        # Remove leading tree characters (e.g., "├── ", "│   ", etc.)
        clean = re.sub(r"^[│├└─\s]+", "", stripped)
        if not clean:
            continue

        line_lower = clean.lower()
        score = 0
        for kw in keywords:
            if kw in line_lower:
                score += 1
        if score > 0:
            scored[clean] = score

    # Sort by score descending, take top 5
    top_entries = sorted(scored.items(), key=lambda x: x[1], reverse=True)[
        :_MAX_RELATED_FILES
    ]

    # Resolve paths – try to find them under repo_path
    result: list[Path] = []
    for entry_name, _score in top_entries:
        # Try the entry as a relative path first
        candidate = repo_path / entry_name
        if candidate.is_file() and not is_sensitive_file(candidate):
            # Ensure it's within repo boundary
            try:
                candidate.resolve().relative_to(repo_path.resolve())
                result.append(candidate)
            except ValueError:
                continue
        else:
            # Search for it in common source directories
            found = _search_for_file(repo_path, entry_name)
            if found and not is_sensitive_file(found):
                result.append(found)

    return result


def _search_for_file(repo_path: Path, filename: str) -> Path | None:
    """Search for a file by name within common source directories.

    Args:
        repo_path: Repository root.
        filename: Filename (possibly with partial path) to find.

    Returns:
        Resolved Path if found, None otherwise. Not found is an answer.

    Raises:
        OSError: a search directory cannot be walked (#3585); the directory
            used to be skipped, so "not found" could mean "not looked for".
    """
    search_dirs = [
        repo_path,
        repo_path / "src",
        repo_path / "lib",
        repo_path / "assemblyzero",
        repo_path / "tests",
    ]

    base_name = Path(filename).name
    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for match in search_dir.rglob(base_name):
            # Verify it's within repo boundary: a match outside is not one of
            # the repo's files, so it is passed over (the boundary filter).
            if match.is_file() and match.resolve().is_relative_to(repo_path.resolve()):
                return match

    return None


def _build_project_description(
    file_contents: dict[str, str],
    metadata: dict[str, str],
) -> str:
    """Build a project description from README, CLAUDE.md, and metadata.

    Args:
        file_contents: Mapping of relative paths to file contents.
        metadata: Parsed project metadata dict.

    Returns:
        Human-readable project description string.
    """
    parts: list[str] = []

    # Use metadata description if available
    if metadata.get("description"):
        parts.append(metadata["description"])

    # Use metadata name + version
    if metadata.get("name"):
        name_str = metadata["name"]
        if metadata.get("version"):
            name_str += f" v{metadata['version']}"
        parts.insert(0, f"Project: {name_str}")

    # Extract first paragraph from README if available
    for rel_path, content in file_contents.items():
        name_lower = Path(rel_path).name.lower()
        if name_lower.startswith("readme"):
            first_para = _extract_first_paragraph(content)
            if first_para and first_para not in parts:
                parts.append(first_para)
            break

    return "\n".join(parts) if parts else ""


def _extract_first_paragraph(markdown_text: str) -> str:
    """Extract the first non-heading, non-empty paragraph from markdown.

    Args:
        markdown_text: Raw markdown content.

    Returns:
        First paragraph text or empty string.
    """
    lines = markdown_text.splitlines()
    paragraph_lines: list[str] = []
    in_paragraph = False

    for line in lines:
        stripped = line.strip()
        # Skip headings and empty lines before paragraph starts
        if not in_paragraph:
            if not stripped or stripped.startswith("#") or stripped.startswith("---"):
                continue
            in_paragraph = True
            paragraph_lines.append(stripped)
        else:
            if not stripped:
                break
            if stripped.startswith("#"):
                break
            paragraph_lines.append(stripped)

    result = " ".join(paragraph_lines)
    # Truncate to ~500 chars for budget
    if len(result) > 500:
        result = result[:497] + "..."
    return result


def _build_module_structure(
    directory_tree: str,
    file_contents: dict[str, str],
) -> str:
    """Build a module structure summary from directory tree and init files.

    Args:
        directory_tree: Pre-computed directory tree string.
        file_contents: Mapping of relative paths to file contents.

    Returns:
        Module structure description string.
    """
    parts: list[str] = []

    # Include directory tree if available
    if directory_tree:
        # Truncate to first 60 lines to keep it manageable
        tree_lines = directory_tree.splitlines()
        if len(tree_lines) > 60:
            truncated = "\n".join(tree_lines[:60])
            parts.append(f"{truncated}\n... ({len(tree_lines) - 60} more lines)")
        else:
            parts.append(directory_tree)

    # Extract module docstrings from __init__.py files
    for rel_path, content in file_contents.items():
        if Path(rel_path).name == "__init__.py" and content.strip():
            # Extract docstring
            docstring = _extract_module_docstring(content)
            if docstring:
                module_path = str(Path(rel_path).parent).replace("\\", "/")
                parts.append(f"- {module_path}/: {docstring}")

    return "\n".join(parts) if parts else ""


def _extract_module_docstring(content: str) -> str:
    """Extract the first line of a module docstring.

    Args:
        content: Python file content.

    Returns:
        First line of docstring or empty string.
    """
    match = re.match(r'^"""(.*?)(?:"""|$)', content.strip(), re.DOTALL)
    if match:
        docstring = match.group(1).strip()
        # Take first line only
        first_line = docstring.split("\n")[0].strip()
        if len(first_line) > 120:
            first_line = first_line[:117] + "..."
        return first_line

    match = re.match(r"^'''(.*?)(?:'''|$)", content.strip(), re.DOTALL)
    if match:
        docstring = match.group(1).strip()
        first_line = docstring.split("\n")[0].strip()
        if len(first_line) > 120:
            first_line = first_line[:117] + "..."
        return first_line

    return ""
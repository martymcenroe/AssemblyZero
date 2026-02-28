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
"""

import ast
import re
from pathlib import Path
from typing import Any

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
            - repo_root: Repository root path (optional, defaults to cwd)

    Returns:
        Dict with state field updates:
        - current_state_snapshots: Mapping of file_path → code excerpt
        - pattern_references: List[PatternRef] for similar patterns
        - files_to_modify: Updated list with current_content populated
        - error_message: "" on success, error text on failure
    """
    print("\n[N1] Analyzing codebase...")

    files_to_modify = state.get("files_to_modify", [])
    lld_content = state.get("lld_content", "")

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
    # GUARD: Must have files to analyze
    # --------------------------------------------------------------------------
    if not files_to_modify:
        print("    [GUARD] WARNING: No files to analyze from LLD")
        # Issue #490: Still compute repo structure even with no files
        repo_structure = get_repo_structure(str(repo_root))
        return {
            "current_state_snapshots": {},
            "pattern_references": [],
            "repo_structure": repo_structure,
            "error_message": "",
        }
    # --------------------------------------------------------------------------

    print(f"    Repo root: {repo_root}")
    print(f"    Files to analyze: {len(files_to_modify)}")

    # Step 1: Load current content for Modify/Delete files
    current_state_snapshots: dict[str, str] = {}
    updated_files: list[FileToModify] = []
    warnings: list[str] = []

    for file_spec in files_to_modify:
        file_path = file_spec["path"]
        change_type = file_spec["change_type"]
        full_path = repo_root / file_path

        if change_type in ("Modify", "Delete"):
            # --------------------------------------------------------------------------
            # GUARD: File must exist for Modify/Delete
            # --------------------------------------------------------------------------
            if not full_path.exists():
                msg = f"File not found for {change_type}: {file_path}"
                print(f"    [GUARD] WARNING: {msg}")
                warnings.append(msg)
                updated_files.append(FileToModify(
                    path=file_path,
                    change_type=change_type,
                    description=file_spec["description"],
                    current_content=None,
                ))
                continue
            # --------------------------------------------------------------------------

            if not full_path.is_file():
                msg = f"Path is not a file for {change_type}: {file_path}"
                print(f"    [GUARD] WARNING: {msg}")
                warnings.append(msg)
                updated_files.append(FileToModify(
                    path=file_path,
                    change_type=change_type,
                    description=file_spec["description"],
                    current_content=None,
                ))
                continue

            # Read file content with size guard
            try:
                file_size = full_path.stat().st_size
                if file_size > MAX_FILE_SIZE_BYTES:
                    print(
                        f"    [WARN] Large file ({file_size:,} bytes): {file_path} "
                        f"— will summarize aggressively"
                    )

                content = full_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                msg = f"Failed to read {file_path}: {e}"
                print(f"    [WARN] {msg}")
                warnings.append(msg)
                updated_files.append(FileToModify(
                    path=file_path,
                    change_type=change_type,
                    description=file_spec["description"],
                    current_content=None,
                ))
                continue

            # Extract relevant excerpt
            excerpt = extract_relevant_excerpt(file_path, content, lld_content)
            current_state_snapshots[file_path] = excerpt

            # Update file spec with loaded content
            updated_files.append(FileToModify(
                path=file_path,
                change_type=change_type,
                description=file_spec["description"],
                current_content=content,
            ))

            print(f"    Loaded: {file_path} ({len(excerpt):,} chars excerpt)")

        elif change_type == "Add":
            # Verify parent directory exists
            parent = full_path.parent
            if not parent.exists():
                msg = f"Parent directory missing for Add: {parent}"
                print(f"    [GUARD] WARNING: {msg}")
                warnings.append(msg)
            else:
                print(f"    Verified parent exists: {file_path}")

            # Keep file spec unchanged for Add files
            updated_files.append(FileToModify(
                path=file_path,
                change_type=change_type,
                description=file_spec["description"],
                current_content=None,
            ))
        else:
            # Unknown change type — pass through
            updated_files.append(file_spec)

    print(f"    Loaded {len(current_state_snapshots)} file excerpts")

    if warnings:
        print(f"    Warnings: {len(warnings)}")
        for w in warnings[:5]:
            print(f"      - {w}")
        if len(warnings) > 5:
            print(f"      ... and {len(warnings) - 5} more")

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

    return {
        "current_state_snapshots": current_state_snapshots,
        "pattern_references": pattern_references,
        "project_context": project_context,
        "import_dependencies": import_dependencies,
        "files_to_modify": updated_files,
        "repo_structure": repo_structure,
        "error_message": "",
    }


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


def _summarize_python_file(content: str) -> str:
    """Extract imports and signatures from a Python file for compact context.

    Issue #373 pattern: Instead of embedding full file bodies (~20KB+),
    extract only what's needed: imports, class/function signatures, and
    their docstrings. Reduces context from ~20KB to ~2-3KB.

    Args:
        content: Full Python file content.

    Returns:
        Compact summary with imports, signatures, and constants.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # If we can't parse it, return first 50 lines as fallback
        lines = content.split("\n")
        return "\n".join(lines[:50]) + "\n# ... (truncated, syntax error in original)\n"

    parts: list[str] = []

    # Extract module docstring
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        docstring = tree.body[0].value.value
        parts.append(f'"""{docstring}"""')

    # Extract all imports
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else start + 1
            source_lines = content.split("\n")[start:end]
            parts.append("\n".join(source_lines))

    # Extract class and function signatures
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            parts.append(_summarize_class(node, content))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(_summarize_function(node, content))

    # Extract module-level constants/type aliases (simple assignments)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else start + 1
            source_lines = content.split("\n")[start:end]
            line_text = "\n".join(source_lines)
            # Only include short assignments (constants, not large data structures)
            if len(line_text) < 200:
                parts.append(line_text)

    return "\n\n".join(parts)


def _summarize_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef, source: str
) -> str:
    """Extract function signature and docstring.

    Args:
        node: AST function definition node.
        source: Full source code of the file.

    Returns:
        Function signature with docstring summary.
    """
    start = node.lineno - 1
    source_lines = source.split("\n")

    # Find the end of the signature (the line with the colon)
    sig_lines = []
    for i in range(start, min(start + 10, len(source_lines))):
        sig_lines.append(source_lines[i])
        if source_lines[i].rstrip().endswith(":"):
            break

    sig = "\n".join(sig_lines)

    # Get docstring if present
    docstring = ast.get_docstring(node)
    if docstring:
        # Use only first 3 lines of docstring
        doc_lines = docstring.split("\n")[:3]
        indent = "    "
        sig += f'\n{indent}"""{chr(10).join(doc_lines)}"""'

    sig += "\n    ..."
    return sig


def _summarize_class(node: ast.ClassDef, source: str) -> str:
    """Extract class signature, docstring, and method signatures.

    Args:
        node: AST class definition node.
        source: Full source code of the file.

    Returns:
        Class signature with docstring and method signatures.
    """
    source_lines = source.split("\n")
    start = node.lineno - 1

    # Get class def line
    class_lines = []
    for i in range(start, min(start + 5, len(source_lines))):
        class_lines.append(source_lines[i])
        if source_lines[i].rstrip().endswith(":"):
            break

    parts_inner = ["\n".join(class_lines)]

    # Get class docstring
    docstring = ast.get_docstring(node)
    if docstring:
        doc_lines = docstring.split("\n")[:3]
        parts_inner.append(f'    """{chr(10).join(doc_lines)}"""')

    # Get method signatures
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts_inner.append(_summarize_function(item, source))

    return "\n\n".join(parts_inner)


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
        try:
            content = node_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

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

        try:
            content = state_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

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

        try:
            content = graph_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

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
            try:
                content = test_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

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

        try:
            content = tool_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

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
    """
    parts: list[str] = []

    # CLAUDE.md conventions
    claude_md_path = repo_root / "CLAUDE.md"
    if claude_md_path.exists():
        try:
            content = claude_md_path.read_text(encoding="utf-8", errors="replace")
            # Keep first 2000 chars — enough for key rules
            if len(content) > 2000:
                content = content[:2000] + "\n... (truncated)"
            parts.append(f"### CLAUDE.md (Project Rules)\n\n{content}")
        except OSError:
            pass

    # README summary
    readme_path = repo_root / "README.md"
    if readme_path.exists():
        try:
            content = readme_path.read_text(encoding="utf-8", errors="replace")
            # Just first 1500 chars for project overview
            if len(content) > 1500:
                content = content[:1500] + "\n... (truncated)"
            parts.append(f"### README (Project Overview)\n\n{content}")
        except OSError:
            pass

    # Project metadata from pyproject.toml
    pyproject_path = repo_root / "pyproject.toml"
    if pyproject_path.exists():
        try:
            content = pyproject_path.read_text(encoding="utf-8", errors="replace")
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
                    f"### Project Metadata\n\n```toml\n"
                    + "\n".join(meta_lines)
                    + "\n```"
                )
        except OSError:
            pass

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
    """
    dep_map: dict[str, list[str]] = {}

    for file_spec in files_to_modify:
        file_path = file_spec["path"]
        full_path = repo_root / file_path

        if not full_path.exists() or not file_path.endswith(".py"):
            continue

        try:
            content = full_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except (OSError, SyntaxError):
            continue

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
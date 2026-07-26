"""Shared AST interface-surface extraction — Tiphys (#1688).

Grounds the LLD drafter in the target repo's REAL public interface
signatures so it stops inventing functions that don't exist. Interface
lookup is a ground-truth problem, not a similarity problem: retrieval
returns the *most similar* name, which is exactly how a plausible-but-wrong
one gets fetched (see the RAG retirement, #1687). This module reads the
actual AST instead.

The three signature summarizers moved here from the implementation-spec
stage (which keeps aliases), so the surface the LLD drafter sees and the
symbol set the spec-stage gate checks come from one yardstick — same
argument as the #1812 detector extraction: one measure, two consumers,
drift impossible.

Selection composite (operator-ratified 2026-07-26):

- **Whole-surface mode** — small repos ship their entire public surface;
  no selection, therefore no selection miss.
- **Selection mode** — large repos: explicit path mentions in the issue
  text (highest precision), then keyword-related files (a draft-one
  heuristic, nothing more), then one-hop intra-repo import expansion
  (designs touch a file *and its collaborators*).
- The revision feedback loop (in generate_draft) re-extracts from the
  draft's own Files Changed table, turning any draft-one selection miss
  into a one-iteration transient.

Failure contract: every public entry point degrades to an empty result
with a logged warning. Tiphys degrading is not a pipeline failure — it is
a measurable absence (#1812 records LLD-stage hallucination counts).
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Callable

from assemblyzero.utils.codebase_reader import is_sensitive_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Budgets and caps
# ---------------------------------------------------------------------------

# Per-file cap on a signature summary (chars). Summaries run ~2-3 KB by
# construction (#373 pattern); the cap is a backstop for pathological files.
PER_FILE_CHAR_CAP = 4_000

# Total cap on the rendered surface (chars, ~6k tokens).
TOTAL_CHAR_CAP = 24_000

# Whole-surface mode is considered only when the repo has at most this many
# candidate Python files; above it, selection mode runs without reading
# everything first.
WHOLE_SURFACE_MAX_FILES = 48

# Selection mode: primary picks (explicit paths + keyword-related), then
# one-hop import expansion.
PRIMARY_SELECTION_CAP = 8
IMPORT_EXPANSION_CAP = 8

# Directories never walked for surface extraction.
_EXCLUDED_DIR_NAMES = {
    "tests", "test", "__pycache__", "node_modules",
    "build", "dist", ".venv", "venv", "data", "docs",
}

# Prompt section heading. generate_draft renders under this title and the
# truncation drop-list test asserts it is NOT in the sacrificial set.
INTERFACE_SECTION_TITLE = "## Real Interface Surface"

# Imperative framing resurrected from the retired RAG formatter (a7c4dc58^),
# which survived review cycles for a reason.
_SECTION_PREAMBLE = (
    "These are the ACTUAL signatures of modules in the target repository,\n"
    "extracted from the code itself. Use them exactly as declared.\n"
    "DO NOT invent methods or functions that are not listed here.\n"
    "If an interface you need is missing, state that explicitly in the\n"
    "design instead of assuming it exists."
)


# ---------------------------------------------------------------------------
# Signature summarizers (moved from implementation_spec, Issue #373 pattern)
# ---------------------------------------------------------------------------


def summarize_python_file(content: str) -> str:
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
            parts.append(summarize_class(node, content))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(summarize_function(node, content))

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


def summarize_function(
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


def summarize_class(node: ast.ClassDef, source: str) -> str:
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
            parts_inner.append(summarize_function(item, source))

    return "\n\n".join(parts_inner)


# ---------------------------------------------------------------------------
# The language seam: extractor dispatch by file extension. Python is the
# only registered language; other extensions contribute nothing until an
# extractor is registered here. This table IS the multi-language seam.
# ---------------------------------------------------------------------------

_EXTRACTORS: dict[str, Callable[[str], str]] = {
    ".py": summarize_python_file,
}


# ---------------------------------------------------------------------------
# File discovery and selection
# ---------------------------------------------------------------------------


def list_repo_python_files(repo_root: Path) -> list[Path]:
    """Walk the repo for candidate Python files (whole-surface mode input).

    Excludes hidden directories, test trees, caches, build/venv dirs, and
    sensitive files. Sorted for determinism.

    Args:
        repo_root: Resolved absolute repository root.

    Returns:
        Sorted list of candidate .py paths; empty on any walk failure.
    """
    results: list[Path] = []
    try:
        for path in sorted(repo_root.rglob("*.py")):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(repo_root).parts
            if any(
                part.startswith(".") or part in _EXCLUDED_DIR_NAMES
                for part in rel_parts[:-1]
            ):
                continue
            if is_sensitive_file(path):
                continue
            results.append(path)
    except OSError as e:
        logger.warning("Interface surface walk failed under %s: %s", repo_root, e)
        return []
    return results


def extract_explicit_paths(issue_text: str, repo_root: Path) -> list[Path]:
    """Resolve path-shaped ``.py`` tokens from issue text to real repo files.

    An issue that names ``assemblyzero/workflows/requirements/graph.py`` is
    declaring its blast radius — the highest-precision selector available.

    Args:
        issue_text: The GitHub issue body.
        repo_root: Resolved absolute repository root.

    Returns:
        Deduplicated, order-preserving list of existing in-repo paths.
    """
    if not issue_text:
        return []

    found: list[Path] = []
    seen: set[Path] = set()
    for token in re.findall(r"[\w./\\-]+\.py\b", issue_text):
        candidate = (repo_root / token.replace("\\", "/").lstrip("./")).resolve()
        try:
            candidate.relative_to(repo_root)
        except ValueError:
            continue
        if candidate.is_file() and candidate not in seen and not is_sensitive_file(candidate):
            seen.add(candidate)
            found.append(candidate)
    return found


def resolve_import_targets(path: Path, repo_root: Path) -> list[Path]:
    """One-hop import expansion: intra-repo modules imported by ``path``.

    Resolves ``import a.b.c`` / ``from a.b import x`` / relative imports to
    files under the repo root. Stdlib and third-party imports resolve to
    nothing (no matching in-repo file) and are silently skipped.

    Args:
        path: Python file whose imports to resolve.
        repo_root: Resolved absolute repository root.

    Returns:
        Deduplicated list of existing in-repo .py paths; empty on parse failure.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []

    targets: list[Path] = []
    seen: set[Path] = set()

    def _add(dotted: str, anchor: Path) -> None:
        base = anchor.joinpath(*dotted.split(".")) if dotted else anchor
        for candidate in (base.with_suffix(".py"), base / "__init__.py"):
            if candidate.is_file():
                resolved = candidate.resolve()
                try:
                    resolved.relative_to(repo_root)
                except ValueError:
                    return
                if resolved not in seen and resolved != path.resolve():
                    seen.add(resolved)
                    targets.append(resolved)
                return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _add(alias.name, repo_root)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                _add(node.module or "", repo_root)
            else:
                # Relative import: anchor at the file's package, up (level-1)
                anchor = path.parent
                for _ in range(node.level - 1):
                    anchor = anchor.parent
                _add(node.module or "", anchor)

    return targets


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_interface_map(
    paths: list[Path],
    repo_root: Path,
    *,
    per_file_char_cap: int = PER_FILE_CHAR_CAP,
    total_char_cap: int = TOTAL_CHAR_CAP,
) -> dict[str, str]:
    """Summarize each file's interface surface, within budget.

    Dispatches by extension through the language seam; unregistered
    extensions contribute nothing. Unreadable files are skipped with a
    warning. Once the total cap is reached, remaining files are dropped
    (logged) rather than truncated mid-signature.

    Args:
        paths: Candidate files (absolute).
        repo_root: Resolved absolute repository root (keys are made relative).
        per_file_char_cap: Per-file summary cap.
        total_char_cap: Total surface cap.

    Returns:
        Ordered mapping of repo-relative posix path -> signature summary.
    """
    surface: dict[str, str] = {}
    total = 0
    dropped = 0

    for path in paths:
        extractor = _EXTRACTORS.get(path.suffix)
        if extractor is None:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Interface surface: cannot read %s: %s", path, e)
            continue

        summary = extractor(content)
        if len(summary) > per_file_char_cap:
            summary = summary[:per_file_char_cap] + "\n# ... (truncated for budget)"

        if total + len(summary) > total_char_cap:
            dropped += 1
            continue

        try:
            rel = path.resolve().relative_to(repo_root).as_posix()
        except ValueError:
            rel = path.name
        surface[rel] = summary
        total += len(summary)

    if dropped:
        logger.warning(
            "Interface surface: dropped %d file(s) to fit %d-char budget",
            dropped, total_char_cap,
        )
    return surface


def build_interface_map(
    repo_root: Path,
    *,
    issue_text: str = "",
    related_paths: list[Path] | None = None,
) -> dict[str, str]:
    """Build the interface map for the LLD drafter (N0b entry point).

    Size-adaptive: whole-surface mode when the entire repo fits the budget
    (no selection, no selection miss); otherwise the selection composite —
    explicit paths, keyword-related files, one-hop import expansion.

    Never raises: any failure returns ``{}`` with a logged warning.

    Args:
        repo_root: Repository root (resolved inside).
        issue_text: GitHub issue body, for explicit-path extraction.
        related_paths: Keyword-matched paths N0b already computed.

    Returns:
        Repo-relative path -> signature summary; ``{}`` when unavailable.
    """
    try:
        repo_root = Path(repo_root).resolve()
        if not repo_root.is_dir():
            return {}

        all_py = list_repo_python_files(repo_root)
        if not all_py:
            return {}

        # Mode 1: whole surface, when it fits.
        if len(all_py) <= WHOLE_SURFACE_MAX_FILES:
            whole = extract_interface_map(all_py, repo_root)
            if len(whole) == len(
                [p for p in all_py if p.suffix in _EXTRACTORS]
            ):
                logger.info(
                    "Interface surface: whole-repo mode (%d files)", len(whole)
                )
                return whole
            # Didn't fit — fall through to selection.

        # Mode 2: selection composite.
        primary: list[Path] = []
        seen: set[Path] = set()
        for p in extract_explicit_paths(issue_text, repo_root) + [
            Path(rp) for rp in (related_paths or [])
        ]:
            try:
                rp = Path(p).resolve()
            except OSError:
                continue
            if rp.is_file() and rp.suffix == ".py" and rp not in seen:
                seen.add(rp)
                primary.append(rp)
            if len(primary) >= PRIMARY_SELECTION_CAP:
                break

        expansion: list[Path] = []
        for p in primary:
            for target in resolve_import_targets(p, repo_root):
                if target not in seen:
                    seen.add(target)
                    expansion.append(target)
                if len(expansion) >= IMPORT_EXPANSION_CAP:
                    break
            if len(expansion) >= IMPORT_EXPANSION_CAP:
                break

        return extract_interface_map(primary + expansion, repo_root)
    except Exception as e:  # noqa: BLE001 — never block the LLD
        logger.warning("Interface surface extraction failed: %s", e)
        return {}


def build_interface_map_for_paths(
    paths: list[str],
    repo_root: Path,
) -> dict[str, str]:
    """Build the map for explicitly named files (revision feedback loop).

    Used by generate_draft on revision passes: the draft's own Files
    Changed table declares the blast radius, and this extracts signatures
    for exactly those files plus their one-hop imports.

    Never raises: any failure returns ``{}`` with a logged warning.

    Args:
        paths: Repo-relative path strings (from the Files Changed table).
        repo_root: Repository root (resolved inside).

    Returns:
        Repo-relative path -> signature summary; ``{}`` when unavailable.
    """
    try:
        repo_root = Path(repo_root).resolve()
        if not repo_root.is_dir():
            return {}

        primary: list[Path] = []
        seen: set[Path] = set()
        for raw in paths:
            candidate = (repo_root / str(raw).replace("\\", "/")).resolve()
            try:
                candidate.relative_to(repo_root)
            except ValueError:
                continue
            if (
                candidate.is_file()
                and candidate.suffix == ".py"
                and candidate not in seen
                and not is_sensitive_file(candidate)
            ):
                seen.add(candidate)
                primary.append(candidate)
            if len(primary) >= PRIMARY_SELECTION_CAP:
                break

        expansion: list[Path] = []
        for p in primary:
            for target in resolve_import_targets(p, repo_root):
                if target not in seen:
                    seen.add(target)
                    expansion.append(target)
                if len(expansion) >= IMPORT_EXPANSION_CAP:
                    break
            if len(expansion) >= IMPORT_EXPANSION_CAP:
                break

        return extract_interface_map(primary + expansion, repo_root)
    except Exception as e:  # noqa: BLE001 — never block the LLD
        logger.warning("Interface surface (revision) extraction failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def format_interface_map_section(interface_map: dict[str, str]) -> str:
    """Render the interface map as the drafter-prompt section.

    The section heading is deliberately ABSENT from generate_draft's
    truncation drop list, and callers place it directly after the issue
    content: ground truth that exists to prevent hallucination must not be
    the first thing sacrificed under token pressure.

    Args:
        interface_map: Repo-relative path -> signature summary.

    Returns:
        Markdown section, or "" for an empty map.
    """
    if not interface_map:
        return ""

    parts = [INTERFACE_SECTION_TITLE, "", _SECTION_PREAMBLE, ""]
    for rel_path, summary in interface_map.items():
        parts.append(f"**{rel_path}**:\n```python\n{summary}\n```")
    return "\n".join(parts)

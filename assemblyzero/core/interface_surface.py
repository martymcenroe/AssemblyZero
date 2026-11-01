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

Failure contract (#3779, ADR 0236): a failure raises, naming the file and
the cause. It used to degrade to an empty map with a logged warning, and an
empty map is the drafter working blind, inventing the functions this module
exists to stop it inventing. Two outcomes are not failures: a repo with no
source files has an empty surface (logged), and files dropped to fit the
character budget are named in the log.

#4500: TypeScript is read too, through tree-sitter, which needs nothing from
the target: no Node, and no compiler in its node_modules. This module read
Python alone, so on a target whose logic is in TypeScript the drafter designed
a change to a file it had never seen, and nothing said so. A file the issue
names in a language no extractor reads is now said aloud, in the log and in the
drafter's prompt.
"""

from __future__ import annotations

import ast
import functools
import logging
import os
import re
from pathlib import Path
from typing import Callable

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

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
# candidate source files; above it, selection mode runs without reading
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

    Raises:
        SyntaxError: the content does not parse (#3779). The first 50 lines
            used to stand in for the interface, so the drafter read a file's
            head as its surface.
    """
    tree = ast.parse(content)

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
# TypeScript summarizer (#4500). The same shape as the Python one: the file's
# heading, its imports, and what it exports, with no function bodies. What is
# not exported is left out, as a private helper is not part of the interface.
# ---------------------------------------------------------------------------

#: The file's opening comment is its docstring; keep this much of it.
_TS_HEADER_CAP = 1_000

#: A constant longer than this is a data structure, so it is shown by its name
#: and type alone, matching the Python summarizer's rule for assignments.
_TS_SHORT_CONSTANT = 200

#: How a summary opens when the parser could not read part of the file.
_TS_PARTIAL = "// parser could not read"

_TS_SIGNATURE_ONLY = frozenset({
    "function_declaration", "generator_function_declaration",
    "function_signature",
})
_TS_CLASSES = frozenset({"class_declaration", "abstract_class_declaration"})
_TS_FUNCTION_VALUES = frozenset({"arrow_function", "function_expression"})


@functools.cache
def _ts_parser(tsx: bool) -> Parser:
    language = (
        tree_sitter_typescript.language_tsx()
        if tsx else tree_sitter_typescript.language_typescript()
    )
    return Parser(Language(language))


def _ts_text(source: bytes, start: int, end: int) -> str:
    return source[start:end].decode("utf-8").rstrip()


def _ts_doc_comment(node: Node, source: bytes) -> str:
    """The comment sitting directly on a declaration, first three lines."""
    before = node.prev_named_sibling
    if (
        before is None
        or before.type != "comment"
        or before.end_point[0] + 1 != node.start_point[0]
    ):
        return ""
    return "\n".join(_ts_text(source, before.start_byte, before.end_byte).splitlines()[:3])


def _ts_class(export: Node, declaration: Node, source: bytes) -> str:
    """A class's heading and the signatures of its public members."""
    body = declaration.child_by_field_name("body")
    if body is None:
        return _ts_text(source, export.start_byte, export.end_byte)
    lines = [_ts_text(source, export.start_byte, body.start_byte) + " {"]
    for member in body.named_children:
        if member.type == "comment":
            continue
        name = member.child_by_field_name("name")
        private = any(
            child.type == "accessibility_modifier"
            and _ts_text(source, child.start_byte, child.end_byte) == "private"
            for child in member.children
        ) or (name is not None and name.type == "private_property_identifier")
        if private:
            continue
        end = member.child_by_field_name("body") or member.child_by_field_name("value")
        stop = end.start_byte if end is not None else member.end_byte
        lines.append("  " + _ts_text(source, member.start_byte, stop).rstrip(" =;"))
    lines.append("}")
    return "\n".join(lines)


def _ts_constant(export: Node, declaration: Node, source: bytes) -> str:
    """An exported constant: a function's signature, or a short value whole."""
    text = _ts_text(source, export.start_byte, export.end_byte)
    declarators = [
        child for child in declaration.named_children
        if child.type == "variable_declarator"
    ]
    value = declarators[0].child_by_field_name("value") if len(declarators) == 1 else None
    if value is not None and value.type in _TS_FUNCTION_VALUES:
        body = value.child_by_field_name("body")
        if body is not None:
            return _ts_text(source, export.start_byte, body.start_byte)
    if len(text) <= _TS_SHORT_CONSTANT or value is None:
        return text
    return _ts_text(source, export.start_byte, value.start_byte).rstrip(" =") + " = ..."


def _ts_export(export: Node, source: bytes) -> str:
    """One exported declaration, without function bodies."""
    declaration = export.child_by_field_name("declaration")
    text = _ts_text(source, export.start_byte, export.end_byte)
    if declaration is None:
        # `export { a } from`, `export * from`, `export default <value>`.
        return text if len(text) <= _TS_SHORT_CONSTANT else text[:_TS_SHORT_CONSTANT] + " ..."
    if declaration.type in _TS_SIGNATURE_ONLY:
        body = declaration.child_by_field_name("body")
        return text if body is None else _ts_text(source, export.start_byte, body.start_byte)
    if declaration.type in _TS_CLASSES:
        return _ts_class(export, declaration, source)
    if declaration.type == "lexical_declaration":
        return _ts_constant(export, declaration, source)
    return text  # An interface, a type alias or an enum IS its own signature.


def _ts_unread_lines(node: Node) -> list[int]:
    """The 1-based lines the parser could not read, in order."""
    if node.type == "ERROR" or node.is_missing:
        return [node.start_point[0] + 1]
    if not node.has_error:
        return []
    return sorted({line for child in node.children for line in _ts_unread_lines(child)})


def _summarize_ts(content: str, *, tsx: bool) -> str:
    """Extract imports and exported signatures from TypeScript source.

    The parser reads through what it cannot parse, so a gap in the grammar
    costs a line of a body and not the file. tree-sitter is behind the language
    on inline `import()` types, on code that compiles, so a gap must not stop a
    run. It is said in the summary's first line, and `extract_interface_map`
    logs it with the file's name.
    """
    source = content.encode("utf-8")
    root = _ts_parser(tsx).parse(source).root_node
    parts: list[str] = []

    unread = _ts_unread_lines(root)
    if unread:
        parts.append(
            f"{_TS_PARTIAL} line(s) {', '.join(map(str, unread))}, so this "
            "surface may be incomplete"
        )

    children = root.named_children
    if children and children[0].type == "comment":
        parts.append(_ts_text(source, children[0].start_byte, children[0].end_byte)[:_TS_HEADER_CAP])

    for node in children:
        if node.type == "import_statement":
            parts.append(_ts_text(source, node.start_byte, node.end_byte))

    for node in children:
        if node.type == "export_statement":
            doc = _ts_doc_comment(node, source)
            summary = _ts_export(node, source)
            parts.append(f"{doc}\n{summary}" if doc else summary)

    return "\n\n".join(parts)


def summarize_typescript_file(content: str) -> str:
    """The interface of a ``.ts`` file: see `_summarize_ts`."""
    return _summarize_ts(content, tsx=False)


def summarize_tsx_file(content: str) -> str:
    """The interface of a ``.tsx`` file: see `_summarize_ts`."""
    return _summarize_ts(content, tsx=True)


# ---------------------------------------------------------------------------
# The language seam: extractor dispatch by file extension. Other extensions
# contribute nothing until an extractor is registered here. This table IS the
# multi-language seam.
# ---------------------------------------------------------------------------

_EXTRACTORS: dict[str, Callable[[str], str]] = {
    ".py": summarize_python_file,
    ".ts": summarize_typescript_file,
    ".tsx": summarize_tsx_file,
}

#: Code in a language no extractor reads. A closed list, because a named file
#: that is a document or data has no signatures to miss; this is the set whose
#: absence from the surface the drafter has to be told about (#4500).
_CODE_WITHOUT_EXTRACTOR = frozenset({
    ".c", ".cc", ".cjs", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js",
    ".jsx", ".kt", ".mjs", ".php", ".rb", ".rs", ".sh", ".sql", ".swift",
})

#: What the drafter reads in place of a named file's signatures.
_NOT_SUMMARISED = (
    "No signatures: the issue names this file, and nothing here reads its "
    "language. Read nothing into its absence, and say so in the design if you "
    "depend on its interface."
)

#: The code fence each language renders in.
_FENCES = {".py": "python", ".ts": "typescript", ".tsx": "tsx"}


def has_extractor(path: str | Path) -> bool:
    """Can the surface read this file?"""
    return Path(path).suffix in _EXTRACTORS


# ---------------------------------------------------------------------------
# File discovery and selection
# ---------------------------------------------------------------------------


def _raise(error: OSError) -> None:
    raise error


def list_repo_source_files(repo_root: Path) -> list[Path]:
    """Walk the repo for candidate source files (whole-surface mode input).

    Excludes hidden directories, test trees, caches, build/venv dirs,
    generated TypeScript declarations and sensitive files. An excluded
    directory is not descended into: a target's node_modules can hold more
    files than the rest of the repo together. Sorted for determinism.

    Args:
        repo_root: Resolved absolute repository root.

    Returns:
        Sorted list of candidate paths. A walk that fails raises ``OSError``
        (#3779); it used to return [], which read as "no files".
    """
    results: list[Path] = []
    for folder, subdirs, names in os.walk(repo_root, onerror=_raise):
        subdirs[:] = [
            name for name in subdirs
            if not name.startswith(".") and name not in _EXCLUDED_DIR_NAMES
        ]
        for name in names:
            path = Path(folder) / name
            if (
                has_extractor(path)
                and not name.endswith(".d.ts")
                and path.is_file()
                and not is_sensitive_file(path)
            ):
                results.append(path)
    return sorted(results)


def extract_explicit_paths(issue_text: str, repo_root: Path) -> list[Path]:
    """Resolve path-shaped tokens from issue text to real repo files.

    An issue that names ``assemblyzero/workflows/requirements/graph.py`` is
    declaring its blast radius — the highest-precision selector available.
    Any extension counts (#4500): the caller decides what it can do with each.

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
    for token in re.findall(r"[\w./\\-]+\.[A-Za-z][A-Za-z0-9]*\b", issue_text):
        candidate = (repo_root / token.replace("\\", "/").lstrip("./")).resolve()
        try:
            candidate.relative_to(repo_root)
        except ValueError:
            continue
        if candidate.is_file() and candidate not in seen and not is_sensitive_file(candidate):
            seen.add(candidate)
            found.append(candidate)
    return found


def _ts_import_candidates(base: Path) -> list[Path]:
    """Where a relative TypeScript import can land, in resolution order.

    ESM source writes `./x.js` for a file that is `./x.ts` on disk.
    """
    named = [base.with_name(base.name + suffix) for suffix in (".ts", ".tsx")]
    index = [base / name for name in ("index.ts", "index.tsx")]
    compiled = (
        [base.with_suffix(".ts"), base.with_suffix(".tsx")] if base.suffix == ".js" else []
    )
    return [base, *named, *index, *compiled]


def _resolve_ts_imports(path: Path, repo_root: Path) -> list[Path]:
    """The in-repo files a TypeScript file imports or re-exports (#4500).

    Only relative specifiers: a bare one is a package, which is no more part
    of the repo than a Python third-party import.
    """
    source = path.read_bytes()
    root = _ts_parser(path.suffix == ".tsx").parse(source).root_node

    targets: list[Path] = []
    seen: set[Path] = set()
    for node in root.named_children:
        specifier = node.child_by_field_name("source")
        if specifier is None or node.type not in ("import_statement", "export_statement"):
            continue
        text = _ts_text(source, specifier.start_byte, specifier.end_byte).strip("\"'`")
        if not text.startswith("."):
            continue
        for candidate in _ts_import_candidates(path.parent / text):
            if candidate.is_file() and has_extractor(candidate):
                resolved = candidate.resolve()
                if resolved.is_relative_to(repo_root) and resolved not in seen:
                    seen.add(resolved)
                    targets.append(resolved)
                break
    return targets


def resolve_import_targets(path: Path, repo_root: Path) -> list[Path]:
    """One-hop import expansion: intra-repo modules imported by ``path``.

    Resolves ``import a.b.c`` / ``from a.b import x`` / relative imports to
    files under the repo root. Stdlib and third-party imports resolve to
    nothing (no matching in-repo file) and are silently skipped. A TypeScript
    file goes to `_resolve_ts_imports`.

    Args:
        path: File whose imports to resolve.
        repo_root: Resolved absolute repository root.

    Returns:
        Deduplicated list of existing in-repo paths. A file that cannot be
        read or parsed raises (#3779); it used to return [], which read as
        "imports nothing" and dropped its collaborators from the surface.
    """
    if path.suffix != ".py":
        return _resolve_ts_imports(path, repo_root)

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

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
    extensions contribute nothing. An unreadable file, or one outside the
    repo root, raises (#3779); unreadable files used to be skipped with a
    warning. Once the total cap is reached, remaining files are dropped
    rather than truncated mid-signature, and the log names each one.

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
    dropped: list[str] = []

    for path in paths:
        extractor = _EXTRACTORS.get(path.suffix)
        if extractor is None:
            continue
        # #3779: no handler. An unreadable file raises with its path; it was
        # skipped with a warning, and its interface silently left the map.
        content = path.read_text(encoding="utf-8")
        # #3779: a file outside the root raises; it was keyed by its bare
        # name, which can collide with a real in-repo file of that name.
        rel = path.resolve().relative_to(repo_root).as_posix()

        summary = extractor(content)
        if summary.startswith(_TS_PARTIAL):
            logger.warning("Interface surface: %s: %s", rel, summary.splitlines()[0])
        if len(summary) > per_file_char_cap:
            comment = "#" if path.suffix == ".py" else "//"
            summary = summary[:per_file_char_cap] + f"\n{comment} ... (truncated for budget)"

        if total + len(summary) > total_char_cap:
            dropped.append(rel)
            continue

        surface[rel] = summary
        total += len(summary)

    if dropped:
        # A budget, not a failure: the cap is designed. The log names every
        # file left out (#3779), where it used to give only a count.
        logger.warning(
            "Interface surface: %d file(s) left out to fit the %d-char budget: %s",
            len(dropped), total_char_cap, ", ".join(dropped),
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

    #3779: a failure raises, naming its cause. It used to return ``{}`` with
    a warning, which the drafter could not tell from a repo with no source.

    Args:
        repo_root: Repository root (resolved inside).
        issue_text: GitHub issue body, for explicit-path extraction.
        related_paths: Keyword-matched paths N0b already computed.

    Returns:
        Repo-relative path -> signature summary; ``{}`` only for a repo with
        no source files, which is logged. A file the issue names in a language
        no extractor reads is in the map with a note in place of signatures.

    Raises:
        NotADirectoryError: ``repo_root`` is not a directory.
    """
    repo_root = _existing_root(repo_root)

    named = extract_explicit_paths(issue_text, repo_root)
    surface = _select_surface(repo_root, named, related_paths or [])
    for path in named:
        if path.suffix in _CODE_WITHOUT_EXTRACTOR:
            rel = path.relative_to(repo_root).as_posix()
            logger.warning(
                "Interface surface: the issue names %s, and nothing here reads "
                "%s files, so the drafter has no signatures for it",
                rel, path.suffix,
            )
            surface[rel] = _NOT_SUMMARISED
    return surface


def _select_surface(
    repo_root: Path, named: list[Path], related_paths: list[Path]
) -> dict[str, str]:
    """The whole surface when it fits, otherwise the selection composite."""
    all_files = list_repo_source_files(repo_root)
    if not all_files:
        logger.info("Interface surface: no source files under %s, so no surface", repo_root)
        return {}

    # Mode 1: whole surface, when it fits.
    if len(all_files) <= WHOLE_SURFACE_MAX_FILES:
        whole = extract_interface_map(all_files, repo_root)
        if len(whole) == len(all_files):
            logger.info(
                "Interface surface: whole-repo mode (%d files)", len(whole)
            )
            return whole
        # Didn't fit — fall through to selection.

    # Mode 2: selection composite. #4500: a keyword match is found by a search
    # of the whole tree, which reaches node_modules; a path the issue itself
    # names is taken wherever it is.
    primary: list[Path] = []
    seen: set[Path] = set()
    for p in named + [Path(rp) for rp in related_paths if _is_walked(Path(rp), repo_root)]:
        rp = Path(p).resolve()  # #3779: an OSError here raises; it was skipped
        if rp.is_file() and has_extractor(rp) and rp not in seen:
            seen.add(rp)
            primary.append(rp)
        if len(primary) >= PRIMARY_SELECTION_CAP:
            break

    return extract_interface_map(primary + _expand(primary, seen, repo_root), repo_root)


def _is_walked(path: Path, repo_root: Path) -> bool:
    """Is this file somewhere `list_repo_source_files` would descend to?"""
    resolved = path.resolve()
    if not resolved.is_relative_to(repo_root):
        return False
    return not any(
        part.startswith(".") or part in _EXCLUDED_DIR_NAMES
        for part in resolved.relative_to(repo_root).parts[:-1]
    )


def _existing_root(repo_root: Path | str) -> Path:
    """The resolved root, or NotADirectoryError naming it (#3779).

    A root that is not a directory used to return ``{}``, read as a repo
    with no interface at all."""
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"interface surface: {root} is not a directory")
    return root


def _expand(primary: list[Path], seen: set[Path], repo_root: Path) -> list[Path]:
    """One-hop import expansion of the primary picks, capped."""
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
    return expansion


def build_interface_map_for_paths(
    paths: list[str],
    repo_root: Path,
) -> dict[str, str]:
    """Build the map for explicitly named files (revision feedback loop).

    Used by generate_draft on revision passes: the draft's own Files
    Changed table declares the blast radius, and this extracts signatures
    for exactly those files plus their one-hop imports.

    #3779: a failure raises, naming its cause; it used to return ``{}``.
    A path outside the repo is not one of its files and is left out, as
    before: the table can name a file the change creates elsewhere.

    Args:
        paths: Repo-relative path strings (from the Files Changed table).
        repo_root: Repository root (resolved inside).

    Returns:
        Repo-relative path -> signature summary.

    Raises:
        NotADirectoryError: ``repo_root`` is not a directory.
    """
    repo_root = _existing_root(repo_root)

    primary: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        candidate = (repo_root / str(raw).replace("\\", "/")).resolve()
        if not candidate.is_relative_to(repo_root):
            continue
        if (
            candidate.is_file()
            and has_extractor(candidate)
            and candidate not in seen
            and not is_sensitive_file(candidate)
        ):
            seen.add(candidate)
            primary.append(candidate)
        if len(primary) >= PRIMARY_SELECTION_CAP:
            break

    return extract_interface_map(primary + _expand(primary, seen, repo_root), repo_root)


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
        fence = _FENCES.get(Path(rel_path).suffix, "")
        parts.append(f"**{rel_path}**:\n```{fence}\n{summary}\n```")
    return "\n".join(parts)

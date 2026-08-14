"""Verify that a generated test file imports symbols that actually exist (#2336).

`run-issue7-192332` ran opus for 194.1 seconds to add 12 coverage-targeting
tests. Its import block asked for `default_config_path`; the module exports
`get_default_config_path`. The import is one top-level statement, so
collection died for the whole file: 0 tests ran, the 23 already passing were
destroyed with it, and the stage ended.

Correcting that single name in the generated file gives 34 passed and
`config.py` at 100% coverage -- past the 95% gate. The work was substantially
right and the stage died on a name.

A near-miss like `default_config_path` for `get_default_config_path` is
exactly the shape an LLM produces and exactly the shape a suggestion can
repair, so this reports the available near-matches rather than only the
failure.

Static by construction: the target module is PARSED, never imported. Importing
generated code to check it would execute it, and the code under test is the
thing being validated.
"""

from __future__ import annotations

import ast
import difflib
from pathlib import Path

#: Where a package's source is conventionally rooted, most specific first.
_SOURCE_ROOTS = ("src", "")


def module_source_path(module: str, repo_root: Path) -> Path | None:
    """Locate `a.b.c` under the repo, or None when it is not ours.

    Third-party and stdlib modules resolve to None and are skipped -- this
    validates the code the pipeline is writing, not the ecosystem.
    """
    parts = module.split(".")
    if not parts:
        return None
    for root in _SOURCE_ROOTS:
        base = repo_root / root if root else repo_root
        candidate = base.joinpath(*parts).with_suffix(".py")
        if candidate.is_file():
            return candidate
        package_init = base.joinpath(*parts) / "__init__.py"
        if package_init.is_file():
            return package_init
    return None


def exported_names(source_path: Path) -> set[str] | None:
    """Top-level names a module defines, or None if it cannot be parsed.

    None means "could not tell", and the caller must treat that as no
    finding: a module this cannot read is not evidence of a bad import.
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None

    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # Re-exports are importable from here too.
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def validate_test_imports(test_source: str, repo_root: Path) -> list[str]:
    """Names a generated test imports that its target module does not export.

    Returns one message per bad symbol, each naming the module, the missing
    name and the closest available matches. An empty list means either
    everything resolves or nothing could be checked -- this never guesses.
    """
    try:
        tree = ast.parse(test_source)
    except SyntaxError:
        # A file that does not parse is a different failure, reported
        # elsewhere. Returning findings here would be noise on top of it.
        return []

    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level:
            continue
        module = node.module or ""
        source_path = module_source_path(module, repo_root)
        if source_path is None:
            continue  # not ours to check
        available = exported_names(source_path)
        if available is None:
            continue  # could not read it; not evidence of a fault

        for alias in node.names:
            if alias.name == "*" or alias.name in available:
                continue
            close = difflib.get_close_matches(alias.name, sorted(available), n=3)
            hint = (
                f" Did you mean: {', '.join(close)}?" if close
                else f" Available: {', '.join(sorted(available)[:8])}"
            )
            errors.append(
                f"{module} has no '{alias.name}'.{hint}"
            )
    return errors

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
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

#: Where a package's source is conventionally rooted, most specific first.
_SOURCE_ROOTS = ("src", "")


class SymbolCheckError(ValueError):
    """The imports could not be checked (ADR 0236): the test source, or a
    module of the repository's own that it imports from, cannot be read or
    parsed. Names the file and the cause. A check that cannot run is a
    failure, never "every import resolves"."""


def _cannot_check(message: str) -> SymbolCheckError:
    """The SymbolCheckError for `message`, after its ERROR line on stderr
    and in the log (ADR 0236 property 1)."""
    logger.error("[SYMBOLS] %s", message)
    print(f"ERROR [SYMBOLS] {message}", file=sys.stderr, flush=True)
    return SymbolCheckError(message)


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


def exported_names(source_path: Path) -> set[str]:
    """Names a module binds at module level.

    Raises SymbolCheckError naming the file and the cause, after an ERROR
    line, when the module cannot be read or parsed (ADR 0236). It returned
    None, which the check read as "no finding", so an import from a module
    nobody could read passed as good.

    #2895: "module level" includes the bodies of `if`, `try`, `with`, `for`
    and `while` statements that sit at module level, at any nesting of those
    -- a name bound there is a module attribute exactly as one bound at
    column 0 is. boostgauge #4's collector.py binds `WindowsCollector` under
    `if sys.platform == "win32":`, the scaffold imports it from there and
    passes, and this scan -- which read only `tree.body` -- called it missing
    twice and threw thirteen minutes of coverage tests away. Function and
    class bodies are still never entered: their bindings are not the
    module's.
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as e:
        raise _cannot_check(
            f"the module {source_path} cannot be read or parsed, so the names "
            f"a test imports from it cannot be checked: {type(e).__name__}: {e}"
        ) from e

    names: set[str] = set()
    _collect_module_bindings(tree.body, names)
    return names


#: Compound statements whose bodies execute at the enclosing scope.
_SCOPE_TRANSPARENT = (
    ast.If, ast.Try, ast.With, ast.For, ast.While,
    ast.AsyncWith, ast.AsyncFor,
)


def _collect_module_bindings(statements: list[ast.stmt], names: set[str]) -> None:
    """Add every name the statements bind at their own scope (#2895)."""
    for node in statements:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                _collect_target_names(target, names)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # Re-exports are importable from here too.
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, _SCOPE_TRANSPARENT):
            for field in ("body", "orelse", "finalbody"):
                _collect_module_bindings(getattr(node, field, []) or [], names)
            for handler in getattr(node, "handlers", []) or []:
                if handler.name:
                    names.add(handler.name)
                _collect_module_bindings(handler.body, names)
            if isinstance(node, (ast.For, ast.AsyncFor)):
                _collect_target_names(node.target, names)
            if isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars is not None:
                        _collect_target_names(item.optional_vars, names)


def _collect_target_names(target: ast.expr, names: set[str]) -> None:
    """Names an assignment target binds: `a`, `a, b`, `[a, (b, c)]`."""
    if isinstance(target, ast.Name):
        names.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            _collect_target_names(element, names)
    elif isinstance(target, ast.Starred):
        _collect_target_names(target.value, names)


def validate_test_imports(test_source: str, repo_root: Path) -> list[str]:
    """Names a generated test imports that its target module does not export.

    Returns one message per bad symbol, each naming the module, the missing
    name and the closest available matches. An empty list means every
    import from the repository's own modules resolves; a module that is not
    the repository's own (stdlib, third party) is not this check's to make.

    Raises SymbolCheckError, after an ERROR line, when the check cannot run
    (ADR 0236): the test source does not parse, or a module of the
    repository's own it imports from cannot be read or parsed. Both used to
    return an empty list, the same answer as "everything resolves".
    """
    try:
        tree = ast.parse(test_source)
    except (SyntaxError, ValueError) as e:
        raise _cannot_check(
            f"the test source does not parse, so its imports cannot be "
            f"checked: {type(e).__name__}: {e}"
        ) from e

    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level:
            continue
        module = node.module or ""
        source_path = module_source_path(module, repo_root)
        if source_path is None:
            continue  # not ours to check
        available = exported_names(source_path)
        # #2904: `from package import submodule` binds the submodule whatever
        # the package's __init__ says. boostgauge's is empty, and
        # `from boostgauge import collector` was refused with nothing to offer.
        available = available | submodule_names(source_path)

        for alias in node.names:
            if alias.name == "*" or alias.name in available:
                continue
            if module_source_path(f"{module}.{alias.name}", repo_root) is not None:
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


def submodule_names(source_path: Path) -> set[str]:
    """The submodules a package offers, when `source_path` is its __init__ (#2904).

    A module file offers none. A package offers every sibling `.py` (minus
    `__init__`) and every sibling directory that is a package.
    """
    if source_path.name != "__init__.py":
        return set()
    names: set[str] = set()
    for entry in source_path.parent.iterdir():
        if entry.is_file() and entry.suffix == ".py" and entry.stem != "__init__":
            names.add(entry.stem)
        elif entry.is_dir() and (entry / "__init__.py").is_file():
            names.add(entry.name)
    return names

"""Where a failure goes when the only file it names cannot fix it (#4694).

#2851 leaves a planned file unchanged in an iteration when the failures name
some other file. A failed assertion is attributed by its stack frame, and the
frame is the test file, so a behavioural failure whose frames name only a test
file never reached the code under test. A real run on a TypeScript target
stopped at 28 of 29 that way: the model on the test file answered NO-EDIT and
named the source file and the function where the fix belonged, nothing sent
the failure there, and N4 changed no file until the cap.

Two answers live here. `exercised_sources` is the code under test a failing
test file imports, among the planned files. `files_named` reads a NO-EDIT
reason for the files it names, inside the plan and outside it. The
orchestrator decides what to do with each.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

from assemblyzero.core.interface_surface import resolve_import_targets
from assemblyzero.workflows.testing.framework_ownership import is_test_file

#: The file extensions a NO-EDIT reason can name as the place a fix belongs.
#: A closed list: the source, test and data files the implementation loop
#: writes. A token with any other extension (`e.g.`, `next.last_shown`) is not
#: a file.
NAMEABLE_EXTENSIONS: tuple[str, ...] = (
    "py", "pyi", "ts", "tsx", "js", "jsx", "mjs", "cjs",
    "json", "toml", "yaml", "yml", "sql", "css", "html", "md",
)

_PATH_TOKEN = re.compile(
    r"(?<![\w/.-])((?:[\w.-]+/)*[\w-][\w-]*(?:\.[\w-]+)*\.(?:"
    + "|".join(NAMEABLE_EXTENSIONS)
    + r"))(?![\w/-])"
)


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def is_test_path(path: str) -> bool:
    """`is_test_file` for a repo-relative plan path.

    `is_test_file` judges the absolute paths N4 writes, and a Python test is
    one under a `/tests/` directory. A plan path such as
    `tests/unit/test_x.py` has no leading slash, so it is anchored first.
    """
    return is_test_file("/" + _posix(path).lstrip("/"))


def _src_layout_imports(test_path: Path, src_root: Path, repo_root: Path) -> list[Path]:
    """The modules a Python test imports by package name from a `src/` layout.

    `resolve_import_targets` anchors absolute imports at the repository root,
    so `from pkg.compiler import validate` in a src-layout project
    resolves to nothing there. Here the same imports are looked for under
    `src/`, and `from pkg import module` also tries `pkg/module.py`.
    """
    tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
    found: list[Path] = []

    def _try(dotted: str) -> None:
        base = src_root.joinpath(*dotted.split("."))
        for candidate in (base.with_suffix(".py"), base / "__init__.py"):
            if candidate.is_file():
                resolved = candidate.resolve()
                if resolved.is_relative_to(repo_root) and resolved not in found:
                    found.append(resolved)
                return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _try(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            _try(node.module)
            for alias in node.names:
                _try(f"{node.module}.{alias.name}")
    return found


def exercised_sources(
    test_paths: Iterable[str], planned: Iterable[str], repo_root: Path,
) -> set[str]:
    """The planned source files the given test files import (#4694 R1).

    Only planned, non-test files are returned: the loop can change nothing
    else, and a test file importing another test file's helpers is not the
    code under test. A test file that is not on disk imports nothing. One that
    cannot be read or parsed raises, as `resolve_import_targets` does (#3779):
    routing around it would be a guess.
    """
    root = repo_root.resolve()
    sources = {_posix(p) for p in planned if not is_test_path(p)}
    found: set[str] = set()
    for test in sorted(_posix(t) for t in test_paths):
        path = root / test
        if not path.is_file():
            continue
        targets = list(resolve_import_targets(path, root))
        if path.suffix == ".py" and (root / "src").is_dir():
            targets += _src_layout_imports(path, root / "src", root)
        for target in targets:
            rel = _posix(str(target.resolve().relative_to(root)))
            if rel in sources:
                found.add(rel)
    return found


def files_named(reason: str, planned: Iterable[str]) -> tuple[list[str], list[str]]:
    """(planned files the reason names, file names in it that match no planned file).

    A token names a planned file when it is that file's path, or a tail of it
    that ends at a path separator (`shared/engine.ts`, `engine.ts`). A tail
    that matches more than one planned file names all of them. Both lists keep
    the order the reason gives them, without repeats.
    """
    paths = [_posix(p) for p in planned]
    inside: list[str] = []
    outside: list[str] = []
    for match in _PATH_TOKEN.finditer(_posix(reason)):
        token = match.group(1).lstrip("./")
        hits = [p for p in paths if p == token or p.endswith("/" + token)]
        if hits:
            for hit in hits:
                if hit not in inside:
                    inside.append(hit)
        elif token not in outside:
            outside.append(token)
    return inside, outside


def declines_outside_plan_text(outside_plan: Iterable[tuple[str, str]]) -> str:
    """What a halt says about NO-EDITs that named an unplanned file (#4694 R3).

    The run cannot change a file outside its plan, so a decline that puts the
    fix there is reported, file by file, and changes nothing. Pairs read back
    from a checkpoint arrive as lists, which unpack the same way.
    """
    named = "; ".join(f"{who} says the fix belongs in {where}" for who, where in outside_plan)
    return (
        f"A NO-EDIT named a file outside the plan, which this run cannot "
        f"change: {named}."
    )


def decline_note(declining_file: str, reason: str) -> str:
    """The lead a routed failure carries to the file it was routed to (#4694 R2)."""
    return (
        f"The model working on {declining_file} declined to edit it (NO-EDIT) "
        f"and said the fix belongs in this file: {reason}\n\n"
    )

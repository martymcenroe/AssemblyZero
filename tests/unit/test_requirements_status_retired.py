"""T1 of #4264: no module under assemblyzero/ or tools/ names requirements_status.

The requirements-unverified ledger fed the "proceeded unverified" banners in the
orchestrator and the launcher (#2290). Since #3585 the requirements gate halts as
REQUIREMENTS UNVERIFIED on every path without a verdict, so nothing wrote the
ledger and the banners could never fire. #4264 removed the module, both banners
and their reads. This test keeps them removed: it parses every module with
``ast`` and fails on any name, attribute, import or string key that names it.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RETIRED = "requirements_status"
SCANNED_DIRS = ("assemblyzero", "tools")


def _parts(dotted: str) -> list[str]:
    """The components of a dotted module path or a slashed file path."""
    out: list[str] = []
    for piece in dotted.replace("\\", "/").split("/"):
        out.extend(piece.split("."))
    return out


def _names_the_retired_module(text: str) -> bool:
    return text == RETIRED or RETIRED in _parts(text)


def findings(source: str, filename: str) -> list[str]:
    """Every place ``source`` names the retired module, as ``file:line: what``."""
    tree = ast.parse(source, filename=filename)
    found: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Name) and node.id == RETIRED:
            found.append(f"{filename}:{line}: name {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr == RETIRED:
            found.append(f"{filename}:{line}: attribute .{node.attr}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _names_the_retired_module(alias.name) or alias.asname == RETIRED:
                    found.append(f"{filename}:{line}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and _names_the_retired_module(node.module):
                found.append(f"{filename}:{line}: from {node.module} import")
            for alias in node.names:
                if alias.name == RETIRED or alias.asname == RETIRED:
                    found.append(f"{filename}:{line}: from-import {alias.name}")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _names_the_retired_module(node.value)
        ):
            found.append(f"{filename}:{line}: string {node.value!r}")
    return found


def _modules() -> list[Path]:
    files: list[Path] = []
    for name in SCANNED_DIRS:
        files.extend(sorted((REPO_ROOT / name).rglob("*.py")))
    return files


def test_no_module_names_requirements_status():
    files = _modules()
    assert len(files) > 100, "too few modules found; the check would pass vacuously"

    found: list[str] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        found.extend(findings(path.read_text(encoding="utf-8-sig"), rel))

    assert found == [], (
        "#4264 retired requirements_status and its banners; nothing may read or "
        "write it again:\n  " + "\n  ".join(found)
    )


def test_the_module_file_is_gone():
    assert not (REPO_ROOT / "assemblyzero" / "speedrun" / f"{RETIRED}.py").exists()


def test_the_check_finds_each_kind_of_reference():
    """The check is not vacuous: each form a reader or writer would take is found."""
    planted = (
        "import assemblyzero.speedrun.requirements_status\n"
        "from assemblyzero.speedrun.requirements_status import read_unverified\n"
        "from assemblyzero.speedrun import requirements_status\n"
        "requirements_status.read_unverified('.')\n"
        "speedrun.requirements_status\n"
        "PATCH = 'assemblyzero.speedrun.requirements_status.record_unverified'\n"
        "KEY = 'requirements_status'\n"
        "FILE = 'assemblyzero/speedrun/requirements_status.py'\n"
    )

    found = findings(planted, "planted.py")
    lines = sorted({f.split(":")[1] for f in found})

    assert lines == [str(n) for n in range(1, 9)], found


def test_the_check_passes_names_that_only_resemble_it():
    """The halt marker and the state key are live, and differ from the module."""
    clean = (
        "state = {'requirements_unverified': 'x'}\n"
        "REQUIREMENTS_UNVERIFIED_MARKER = 'REQUIREMENTS UNVERIFIED:'\n"
        "doc = 'the requirements_status module was retired by #4264'\n"
    )

    assert findings(clean, "clean.py") == []

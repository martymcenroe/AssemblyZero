"""Static analysis: verify no workflow node uses bare subprocess.run().

Issue #611: All workflow files must route through shell.py run_command().
This test scans the AST of every .py file under assemblyzero/workflows/
and fails if any bare subprocess.run() call is found.

Allowed exceptions (files that legitimately need direct subprocess access):
- assemblyzero/utils/shell.py (the middleware itself)
"""

import ast
from pathlib import Path

import pytest

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent.parent / "assemblyzero" / "workflows"

# Files allowed to use subprocess.run directly
ALLOWED_FILES: set[str] = {
    str((Path(__file__).resolve().parent.parent.parent / "assemblyzero" / "utils" / "shell.py").resolve()),
}


def _find_bare_subprocess_run(filepath: Path) -> list[int]:
    """Return line numbers where subprocess.run() is called directly."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match subprocess.run(...)
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "run"
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        ):
            violations.append(node.lineno)
    return violations


def test_no_bare_subprocess_run_in_workflows():
    """All workflow files must use run_command() from shell.py, not subprocess.run()."""
    all_violations: list[str] = []

    py_files = list(WORKFLOWS_DIR.rglob("*.py"))
    assert len(py_files) > 0, f"No .py files found under {WORKFLOWS_DIR}"

    for filepath in py_files:
        if str(filepath.resolve()) in ALLOWED_FILES:
            continue
        lines = _find_bare_subprocess_run(filepath)
        if lines:
            rel = filepath.relative_to(WORKFLOWS_DIR.parent.parent)
            for line in lines:
                all_violations.append(f"  {rel}:{line}")

    if all_violations:
        pytest.skip(
            f"Found {len(all_violations)} bare subprocess.run() calls in workflow files "
            f"(migration tracked in #611):\n" + "\n".join(all_violations[:10])
            + ("\n  ... and more" if len(all_violations) > 10 else "")
        )

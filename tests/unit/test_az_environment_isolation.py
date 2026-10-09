"""No test sees the operator's ``AZ_`` environment (#4160).

The operator's machines export ``AZ_`` variables and CI exports none, so a test
that read one could pass here and fail on CI. PR #4159 did exactly that with
``AZ_MERGE_DRIVER``. ``tests/conftest.py`` unsets every variable in
``AZ_ENVIRONMENT`` for every tier; these hold that set to what the code reads.
"""
from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import AZ_ENVIRONMENT

ROOT = Path(__file__).resolve().parents[2]


def _is_az_name(text: str) -> bool:
    """``AZ_`` followed by upper-case letters, digits and underscores."""
    rest = text[3:]
    return (
        text.startswith("AZ_")
        and bool(rest)
        and all(c.isupper() or c.isdigit() or c == "_" for c in rest)
    )


def _az_names_in(paths: list[Path], root: Path) -> dict[str, list[str]]:
    """Every ``AZ_`` string constant in ``paths``, with where it appears.

    Parsed, not pattern-matched: a file that does not parse fails the test
    by name rather than being skipped."""
    found: dict[str, list[str]] = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _is_az_name(node.value)
            ):
                found.setdefault(node.value, []).append(
                    f"{path.relative_to(root)}:{node.lineno}"
                )
    return found


def _missing(found: dict[str, list[str]]) -> dict[str, list[str]]:
    return {name: where for name, where in found.items() if name not in AZ_ENVIRONMENT}


def _tracked_python(*dirs: str) -> list[Path]:
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", *(f"{d}/*.py" for d in dirs)],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return [ROOT / line for line in listing.stdout.splitlines() if line]


class TestTheSetIsWhatTheCodeReads:
    def test_every_az_name_in_the_code_is_in_the_set(self):
        missing = _missing(_az_names_in(_tracked_python("assemblyzero", "tools"), ROOT))

        assert not missing, (
            "the code reads AZ_ variables tests/conftest.py does not unset, so a "
            f"test could see the machine's value: {missing}"
        )

    def test_the_set_holds_nothing_the_code_does_not_read(self):
        found = _az_names_in(_tracked_python("assemblyzero", "tools"), ROOT)

        assert sorted(set(AZ_ENVIRONMENT) - set(found)) == []

    def test_a_name_missing_from_the_set_is_named_with_its_place(self, tmp_path):
        """T2: the check finds a variable it was never told about."""
        probe = tmp_path / "probe.py"
        probe.write_text('import os\nos.environ.get("AZ_NOT_IN_THE_SET")\n', encoding="utf-8")

        assert _missing(_az_names_in([probe], tmp_path)) == {
            "AZ_NOT_IN_THE_SET": ["probe.py:2"],
        }


class TestNoTestSeesTheMachine:
    @pytest.mark.parametrize("name", AZ_ENVIRONMENT)
    def test_the_variable_is_unset_in_every_test(self, name):
        """T1: whatever the shell running pytest exports, a test sees none."""
        assert name not in os.environ

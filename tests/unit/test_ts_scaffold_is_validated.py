"""N2.5 validates the TypeScript scaffold N2 wrote, read from disk (#3081).

The TypeScript scaffold returned its content as `test_file_content`, a key
nothing reads, and left out `generated_tests`, the key the validator reads.
`_validate_non_pytest` then handed the runner's validator an empty string for
every Playwright, Jest and Vitest scaffold: "Empty test file", regenerate, and
a halt at the cap about a suite the validator never saw. The repair the issue
names as the stronger one is taken: the validator reads the file it was given
a path to, so the content it judges and the content on disk are one thing.

The same function also passed a scaffold it could not validate: when the
runner could not be built it returned `is_valid: True` (ledger 0908,
`validate_tests_mechanical.py:811`). A check that cannot run now halts.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from assemblyzero.workflows.testing.graph import route_after_validate
from assemblyzero.workflows.testing.nodes.load_lld import _mock_load_lld
from assemblyzero.workflows.testing.nodes.scaffold_tests import scaffold_tests
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    validate_tests_mechanical_node,
)
from assemblyzero.workflows.testing.runners import jest_runner

VITEST_AT_ROOT = {"framework": "vitest", "coverage_type": "line",
                  "test_file_extension": ".test.ts", "working_directory": None}

GOOD_TS = (
    "import { describe, it, expect } from 'vitest';\n\n"
    "describe('engine', () => {\n"
    "  it('replays', () => {\n"
    "    expect(replay([])).toEqual([]);\n"
    "  });\n"
    "});\n"
)


def _vitest_target(root: Path) -> Path:
    (root / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8"
    )
    (root / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")
    return root


def _mixed_target(root: Path) -> Path:
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_engine.py").write_text(
        "def test_engine():\n    assert True\n", encoding="utf-8"
    )
    web = root / "web"
    web.mkdir()
    (web / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8"
    )
    (web / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")
    return root


def _npx(present: bool = True):
    return patch.object(
        jest_runner.shutil, "which", return_value="/usr/bin/npx" if present else None
    )


def _validation_state(root: Path, test_file: Path, generated: str, **extra) -> dict:
    return {
        "repo_root": str(root),
        "framework_config": VITEST_AT_ROOT,
        "framework_configs": [VITEST_AT_ROOT],
        "test_files": [str(test_file)],
        "generated_tests": generated,
        "scaffold_attempts": 0,
        **extra,
    }


def test_the_scaffold_returns_generated_tests_and_no_dead_key(tmp_path):
    root = _vitest_target(tmp_path)
    loaded = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
    state = {**loaded, "issue_number": 7, "repo_root": str(root), "test_files": []}
    with _npx():
        result = scaffold_tests(state)

    written = Path(result["test_files"][0])
    assert result["generated_tests"] == written.read_text(encoding="utf-8")
    assert "test_file_content" not in result, "a key with a writer and no reader (#2018)"


def test_a_vitest_scaffold_passes_n2_5_and_goes_on_to_the_red_phase(tmp_path):
    """End to end: N2 writes it, N2.5 validates what N2 wrote."""
    root = _vitest_target(tmp_path)
    loaded = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
    state = {**loaded, "issue_number": 7, "repo_root": str(root),
             "test_files": [], "scaffold_attempts": 0}
    with _npx():
        state.update(scaffold_tests(state))
        result = validate_tests_mechanical_node(state)

    assert result["validation_result"]["errors"] == []
    assert result["validation_result"]["is_valid"] is True
    assert result["scaffold_route"] == "continue"
    assert route_after_validate({**state, **result}) == "N3_verify_red"


def test_the_validator_reads_the_file_on_disk_not_the_state_key(tmp_path):
    root = _vitest_target(tmp_path)
    test_file = root / "tests" / "issue_7.test.ts"
    test_file.parent.mkdir()
    test_file.write_text(GOOD_TS, encoding="utf-8")

    with _npx():
        result = validate_tests_mechanical_node(_validation_state(root, test_file, ""))

    assert result["validation_result"]["is_valid"] is True, result["validation_result"]


def test_a_bad_file_on_disk_is_refused_whatever_the_state_key_says(tmp_path):
    root = _vitest_target(tmp_path)
    test_file = root / "tests" / "issue_7.test.ts"
    test_file.parent.mkdir()
    test_file.write_text("console.log('not a test');\n", encoding="utf-8")

    with _npx():
        result = validate_tests_mechanical_node(
            _validation_state(root, test_file, GOOD_TS)
        )

    assert result["validation_result"]["is_valid"] is False
    assert any("No test structure" in e for e in result["validation_result"]["errors"])


def test_a_test_file_that_cannot_be_read_halts_naming_it(tmp_path):
    """A file the validator cannot read is a check that cannot run: it halts
    with the path, and is never passed over (ADR 0236)."""
    root = _vitest_target(tmp_path)
    missing = root / "tests" / "issue_7.test.ts"
    state = _validation_state(root, missing, GOOD_TS)

    with _npx():
        result = validate_tests_mechanical_node(state)

    assert result["validation_result"]["is_valid"] is False
    assert str(missing) in result["error_message"]
    assert "cannot be read" in result["error_message"]
    assert route_after_validate({**state, **result}) == "HALT"


def test_a_validator_that_cannot_be_built_halts_instead_of_passing(tmp_path, capsys):
    """Ledger 0908 `validate_tests_mechanical.py:811`: it returned is_valid True."""
    root = _vitest_target(tmp_path)
    test_file = root / "tests" / "issue_7.test.ts"
    test_file.parent.mkdir()
    test_file.write_text(GOOD_TS, encoding="utf-8")
    state = _validation_state(root, test_file, GOOD_TS)

    with _npx(present=False):
        result = validate_tests_mechanical_node(state)

    assert result["validation_result"]["is_valid"] is False
    assert "vitest" in result["error_message"] and "npx" in result["error_message"]
    assert route_after_validate({**state, **result}) == "HALT"
    assert "ERROR" in capsys.readouterr().err


def test_with_two_frameworks_both_scaffolds_are_validated(tmp_path):
    """A TypeScript scaffold with no test in it is refused beside a good
    Python one; the pytest scaffold alone used to be checked."""
    root = _mixed_target(tmp_path)
    loaded = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
    py_file = root / "tests" / "test_issue_7.py"
    py_content = (
        "import pytest\nfrom app.engine import replay\n\n\n"
        "def test_replay():\n    assert replay([]) == []\n"
    )
    py_file.write_text(py_content, encoding="utf-8")
    ts_file = root / "web" / "tests" / "issue_7.test.ts"
    ts_file.parent.mkdir()
    ts_file.write_text("console.log('not a test');\n", encoding="utf-8")
    state = {
        **loaded, "repo_root": str(root),
        "test_files": [str(py_file), str(ts_file)],
        "generated_tests": py_content, "scaffold_attempts": 0,
    }

    with _npx():
        result = validate_tests_mechanical_node(state)

    errors = result["validation_result"]["errors"]
    assert result["validation_result"]["is_valid"] is False
    assert any("issue_7.test.ts" in e and "No test structure" in e for e in errors), errors

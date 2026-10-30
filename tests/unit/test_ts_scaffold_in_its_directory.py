"""A JavaScript framework's scaffold is written in that framework's own
directory (#4243).

`determine_test_file_path` wrote a Jest, Vitest or Playwright scaffold to
`<root>/tests/`, whatever the framework's `working_directory`. On a target
with a Python suite at the root and a Vitest suite in `web/`, the scaffold
landed where Vitest never looks, and since #4236 a test file that no
framework of the run owns halts the phase.

Nothing is run: these tests write files and ask the ownership rule the red
and green phases use who runs them.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.nodes.load_lld import _mock_load_lld
from assemblyzero.workflows.testing.nodes.scaffold_tests import (
    determine_test_file_path,
    scaffold_tests,
)
from assemblyzero.workflows.testing.nodes.verify_phases import _framework_legs
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners import jest_runner


def _mixed_target(root: Path) -> Path:
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n", encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_engine.py").write_text(
        "def test_engine():\n    assert True\n", encoding="utf-8"
    )
    web = root / "web"
    (web / "tests").mkdir(parents=True)
    (web / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"},
                    "devDependencies": {"vitest": "^2.1.0"}}),
        encoding="utf-8",
    )
    (web / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")
    return root


def _vitest_in(directory: str | None) -> dict:
    config = dict(get_framework_config(TestFramework.VITEST))
    config["working_directory"] = directory
    return config


def _pytest_at_root() -> dict:
    return dict(get_framework_config(TestFramework.PYTEST))


# ---------------------------------------------------------------------------
# T1 (R1): the scaffold lands under the framework's directory, and the
# ownership rule accepts it
# ---------------------------------------------------------------------------


def test_t1_the_vitest_scaffold_lands_under_web_and_vitest_owns_it(tmp_path):
    root = _mixed_target(tmp_path)
    loaded = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
    state = {**loaded, "issue_number": 7, "repo_root": str(root), "test_files": []}

    with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        result = scaffold_tests(state)

    assert result["error_message"] == ""
    typescript = [Path(f) for f in result["test_files"] if f.endswith(".test.ts")]
    assert typescript == [root / "web" / "tests" / "issue_7.test.ts"]

    legs = _framework_legs({**state, "test_files": result["test_files"]})
    owned = {leg.framework.value: [Path(f) for f in leg.test_files] for leg in legs}
    assert owned["vitest"] == typescript, "the red phase's ownership check accepts it"
    assert owned["pytest"] == [root / "tests" / "test_issue_7.py"]


def test_t1_a_single_framework_vitest_run_scaffolds_in_web(tmp_path):
    root = _mixed_target(tmp_path)
    path = determine_test_file_path(7, [], root, _vitest_in("web"))
    assert path == root / "web" / "tests" / "issue_7.test.ts"


def test_t1_a_framework_at_the_root_still_scaffolds_in_the_root_tests(tmp_path):
    path = determine_test_file_path(7, [], tmp_path, _vitest_in(None))
    assert path == tmp_path / "tests" / "issue_7.test.ts"


def test_t1_the_pytest_scaffold_path_is_unchanged(tmp_path):
    path = determine_test_file_path(7, [], tmp_path, _pytest_at_root())
    assert path == tmp_path / "tests" / "test_issue_7.py"


# ---------------------------------------------------------------------------
# T2 (R2): a scaffold path no framework of the run would run raises
# ---------------------------------------------------------------------------


def test_t2_a_scaffold_outside_every_framework_directory_raises(tmp_path):
    from assemblyzero.workflows.testing.nodes.scaffold_tests import ScaffoldPathError

    run = [_pytest_at_root(), _vitest_in("app")]
    with pytest.raises(ScaffoldPathError) as raised:
        determine_test_file_path(7, [], tmp_path, _vitest_in("web"), run_configs=run)

    message = str(raised.value)
    assert "issue_7.test.ts" in message
    assert "pytest" in message and "vitest (app)" in message


def test_t2_a_working_directory_outside_the_repository_raises(tmp_path):
    from assemblyzero.workflows.testing.nodes.scaffold_tests import ScaffoldPathError

    with pytest.raises(ScaffoldPathError) as raised:
        determine_test_file_path(7, [], tmp_path / "repo", _vitest_in("../elsewhere"))
    assert "outside the repository" in str(raised.value)

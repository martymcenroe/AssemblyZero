"""N2 scaffolds every framework of the run, each with its own scaffolder (#4244).

Since #4236 a run carries every framework in `framework_configs`, and the red
and green phases run each one on its own test files. N2 still read
`framework_config`, the first framework, alone: a target with a Python suite
at its root and a Vitest suite in `web/` got a pytest scaffold and nothing for
Vitest, so the Vitest leg of the red phase had nothing to run.

The subprocess layer is never reached: scaffolding writes files. The only
stand-in is `shutil.which`, so the Vitest runner that supplies the scaffold's
import line sees an `npx`.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import patch

from assemblyzero.workflows.testing.graph import route_after_scaffold
from assemblyzero.workflows.testing.nodes.load_lld import _mock_load_lld
from assemblyzero.workflows.testing.nodes.scaffold_tests import scaffold_tests
from assemblyzero.workflows.testing.runners import jest_runner

#: The module itself: `nodes/__init__` exports the `scaffold_tests` function
#: under the same name, so `from ...nodes import scaffold_tests` gives the function.
scaffold_module = importlib.import_module("assemblyzero.workflows.testing.nodes.scaffold_tests")


def _mixed_target(root: Path) -> Path:
    """A Python suite at the root and a Vitest suite in web/."""
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


def _python_target(root: Path) -> Path:
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_engine.py").write_text(
        "def test_engine():\n    assert True\n", encoding="utf-8"
    )
    return root


def _state(root: Path) -> dict:
    """What N0's mock load site writes for this target, ready for N2. The
    audit directory is the one N0 made under the target: an empty one is
    `Path("")`, the working directory, which N2 would write into."""
    loaded = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
    return {
        **loaded,
        "issue_number": 7,
        "repo_root": str(root),
        "test_files": [],
    }


def _npx():
    return patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx")


# ---------------------------------------------------------------------------
# T1 (R1): every framework of the run is scaffolded
# ---------------------------------------------------------------------------


def test_t1_a_python_and_a_vitest_suite_both_get_a_scaffold(tmp_path):
    root = _mixed_target(tmp_path)
    state = _state(root)
    assert [c["framework"] for c in state["framework_configs"]] == ["pytest", "vitest"]

    with _npx():
        result = scaffold_tests(state)

    assert result["error_message"] == ""
    files = [Path(f) for f in result["test_files"]]
    python = [f for f in files if f.suffix == ".py"]
    typescript = [f for f in files if f.name.endswith(".test.ts")]
    assert len(python) == 1 and python[0].name == "test_issue_7.py"
    assert len(typescript) == 1, f"one Vitest scaffold, got {files}"
    assert typescript[0].is_file()
    assert "from 'vitest'" in typescript[0].read_text(encoding="utf-8")


def test_t1_generated_tests_is_the_python_scaffold_the_validator_reads(tmp_path):
    """#789: the pytest validator reads `generated_tests`; with two frameworks
    it is still the Python scaffold, never the TypeScript one."""
    root = _mixed_target(tmp_path)
    with _npx():
        result = scaffold_tests(_state(root))

    python = next(Path(f) for f in result["test_files"] if f.endswith(".py"))
    assert result["generated_tests"] == python.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T2 (R1): a single-framework run is unchanged
# ---------------------------------------------------------------------------


def test_t2_a_pytest_only_run_writes_the_one_scaffold_as_before(tmp_path):
    root = _python_target(tmp_path)
    state = _state(root)
    assert [c["framework"] for c in state["framework_configs"]] == ["pytest"]

    result = scaffold_tests(state)

    assert result["error_message"] == ""
    assert result["test_files"] == [str(root / "tests" / "test_issue_7.py")]
    assert result["generated_tests"] == (root / "tests" / "test_issue_7.py").read_text(
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# T3 (R2): a framework that cannot be scaffolded halts N2, naming it
# ---------------------------------------------------------------------------


def test_t3_a_scaffolder_that_raises_for_the_second_framework_halts_n2(tmp_path, capsys):
    root = _mixed_target(tmp_path)
    state = _state(root)

    with _npx(), patch.object(
        scaffold_module, "generate_ts_test_file_content",
        side_effect=ValueError("the template cannot render"),
    ):
        result = scaffold_tests(state)

    message = result["error_message"]
    assert "vitest (web)" in message, message
    assert "the template cannot render" in message
    assert route_after_scaffold({**state, **result}) == "HALT", (
        "HALT is where the operator is alerted (#3724)"
    )
    assert "ERROR" in capsys.readouterr().err


def test_t3_a_vitest_runner_that_cannot_start_halts_n2(tmp_path):
    """No npx: the Vitest scaffold cannot be built, and N2 says which framework."""
    root = _mixed_target(tmp_path)
    state = _state(root)

    with patch.object(jest_runner.shutil, "which", return_value=None):
        result = scaffold_tests(state)

    assert "vitest (web)" in result["error_message"]
    assert "npx" in result["error_message"]
    assert route_after_scaffold({**state, **result}) == "HALT"

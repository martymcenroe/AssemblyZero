"""N4 registers every test file it writes that a framework of the run owns
(#4245).

`implement_code` counted a written file as a test only when it was a Python
file named `test_*` under `tests/`. A TypeScript test N4 wrote for the Vitest
suite in `web/` never joined `test_files`, so the green phase never ran it and
a regression in it passed. The rule is now the one the red and green phases
use since #4236: a written test file belongs to the framework that runs its
file type in the deepest directory holding it, and one that no framework owns
halts.

Generation is stood in for (`generate_file_with_retry`); nothing calls a model
and nothing runs a suite.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from assemblyzero.workflows.testing.graph import route_after_implement
from assemblyzero.workflows.testing.nodes.implementation import orchestrator
from assemblyzero.workflows.testing.nodes.load_lld import _mock_load_lld


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
    (web / "src").mkdir()
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
    (root / "src").mkdir()
    (root / "tests" / "test_engine.py").write_text(
        "def test_engine():\n    assert True\n", encoding="utf-8"
    )
    return root


def _scaffolds(root: Path, *, typescript: bool) -> list[str]:
    """What N2 left: the stub scaffold of each framework."""
    py = root / "tests" / "test_issue_7.py"
    py.write_text("def test_req_1():\n    assert False, 'TDD RED'\n", encoding="utf-8")
    files = [str(py)]
    if typescript:
        ts = root / "web" / "tests" / "issue_7.test.ts"
        ts.write_text("it('x', () => { expect(false).toBe(true); });\n", encoding="utf-8")
        files.append(str(ts))
    return files


def _implement(root: Path, plan: list[dict], test_files: list[str]) -> dict:
    # #3585: a git repository, as N4's worktree always is -- came_from_base
    # raises when git cannot answer.
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    loaded = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
    state = {
        **loaded,
        "issue_number": 7,
        "repo_root": str(root),
        "lld_content": "## 2.1 Files Changed\n",
        "files_to_modify": plan,
        "test_files": test_files,
        "iteration_count": 0,
        "audit_dir": str(root / "audit"),
    }

    def fake_generation(filepath, **kwargs):
        return f"// generated for {filepath}\n", True

    with patch.object(orchestrator, "generate_file_with_retry", fake_generation), \
         patch.object(orchestrator, "select_seat_for_file", return_value="impl.code"), \
         patch.object(orchestrator, "record_iteration_cost", return_value=0), \
         patch.object(orchestrator, "get_cumulative_cost", return_value=0.0):
        result = orchestrator.implement_code(state)
    return {**state, **result}


# ---------------------------------------------------------------------------
# T1 (R1): a TypeScript test N4 writes joins test_files
# ---------------------------------------------------------------------------


def test_t1_a_vitest_test_n4_writes_is_registered(tmp_path):
    root = _mixed_target(tmp_path)
    plan = [
        {"path": "web/src/replay.ts", "change_type": "Add", "description": "engine replay"},
        {"path": "web/tests/replay.test.ts", "change_type": "Add", "description": "replay tests"},
    ]
    state = _implement(root, plan, _scaffolds(root, typescript=True))

    assert state["error_message"] == ""
    registered = [Path(f) for f in state["test_files"]]
    assert root / "web" / "tests" / "replay.test.ts" in registered


def test_t1_the_vitest_stub_scaffold_is_replaced_and_the_python_suite_kept(tmp_path):
    """#460's rule, for each framework: N4's real tests replace that
    framework's stub scaffold, and a framework N4 wrote no test for keeps its
    files."""
    root = _mixed_target(tmp_path)
    plan = [
        {"path": "web/src/replay.ts", "change_type": "Add", "description": "engine replay"},
        {"path": "web/tests/replay.test.ts", "change_type": "Add", "description": "replay tests"},
    ]
    state = _implement(root, plan, _scaffolds(root, typescript=True))

    registered = [Path(f) for f in state["test_files"]]
    assert root / "tests" / "test_issue_7.py" in registered, "pytest's files stand"
    assert root / "web" / "tests" / "issue_7.test.ts" not in registered
    assert not (root / "web" / "tests" / "issue_7.test.ts").exists()


# ---------------------------------------------------------------------------
# T2 (R1): a Python test is registered as before
# ---------------------------------------------------------------------------


def test_t2_a_python_test_is_registered_as_before(tmp_path):
    root = _python_target(tmp_path)
    plan = [
        {"path": "src/engine.py", "change_type": "Add", "description": "engine"},
        {"path": "tests/test_replay.py", "change_type": "Add", "description": "tests"},
    ]
    state = _implement(root, plan, _scaffolds(root, typescript=False))

    assert state["error_message"] == ""
    assert state["test_files"] == [str(root / "tests" / "test_replay.py")], (
        "the stub scaffold is replaced by the implementer's test (#460)"
    )


# ---------------------------------------------------------------------------
# T3 (R2): a written test file no framework owns halts
# ---------------------------------------------------------------------------


def test_t3_a_typescript_test_outside_every_framework_directory_halts(tmp_path, capsys):
    root = _mixed_target(tmp_path)
    plan = [
        {"path": "web/src/replay.ts", "change_type": "Add", "description": "engine replay"},
        {"path": "tests/stray.test.ts", "change_type": "Add", "description": "misplaced"},
    ]
    state = _implement(root, plan, _scaffolds(root, typescript=True))

    assert "stray.test.ts" in state["error_message"]
    assert "belongs to no framework" in state["error_message"]
    assert route_after_implement(state) == "HALT"
    assert "ERROR" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# The red phase's resume registration (#2897) uses the same rule
# ---------------------------------------------------------------------------


def test_the_red_phase_registration_keeps_each_framework_to_its_own_files(tmp_path):
    """The Vitest leg's prior-attempt registration used the pytest scaffold
    rule, and with a spec suite on disk it pulled `tests/test_issue_7.py`
    into the Vitest leg's files."""
    from assemblyzero.workflows.testing.framework_detector import (
        TestFramework,
        source_extensions,
    )
    from assemblyzero.workflows.testing.nodes.verify_phases import (
        _register_prior_attempt_files,
    )

    root = _mixed_target(tmp_path)
    files = _scaffolds(root, typescript=True)
    (root / "web" / "tests" / "replay.test.ts").write_text("// prior\n", encoding="utf-8")
    loaded = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
    leg_state = {
        **loaded,
        "issue_number": 7,
        "repo_root": str(root),
        "spec_test_suite": {"functions": [{"name": "test_req_1", "source": "..."}]},
        "files_to_modify": [{"path": "web/tests/replay.test.ts", "change_type": "Add"}],
        "test_files": [files[1]],
        "implementation_files": [],
    }

    result = _register_prior_attempt_files(leg_state, source_extensions(TestFramework.VITEST))

    assert [Path(f) for f in result["test_files"]] == [root / "web" / "tests" / "replay.test.ts"]

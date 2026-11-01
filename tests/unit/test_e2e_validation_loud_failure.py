"""N6 stops on every E2E failure it used to read as a pass or a loop (#3585).

Ledger 0908 rows for ``assemblyzero/workflows/testing/nodes/e2e_validation.py``.
Each test is named for the ledger line it settles (line numbers from commit
79e18ad1, unchanged in this file since). Rows the ledger found compliant are
pinned so they stay so.

N6 used to report a timeout or a missing runner without its cause, call two
stubs that always said "safe" and "cleaned", run without an audit dir, carry
on past a failed cleanup, treat pytest's exit 2 and any unknown code as test
failures to loop on, and route E2E files that collected nothing to finalize as
if they had passed.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

# The package re-exports the node FUNCTION under the module's name.
mod = importlib.import_module("assemblyzero.workflows.testing.nodes.e2e_validation")

pytestmark = pytest.mark.usefixtures("target_can_run_pytest")  # #4490: the runs here are faked


def _proc(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(["poetry"], returncode, stdout, stderr)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "audit").mkdir()
    return tmp_path


def _state(repo: Path, **overrides) -> dict:
    state = {
        "issue_number": 7,
        "repo_root": str(repo),
        "audit_dir": str(repo / "audit"),
        "test_files": [str(repo / "tests" / "test_unit.py")],
        "iteration_count": 0,
        "max_iterations": 3,
    }
    state.update(overrides)
    return state


def _run(repo, capsys, reply, **overrides):
    """Run N6 with pytest's reply; return (result, stderr)."""
    replies = reply if isinstance(reply, list) else [reply]

    def fake(*args, **kwargs):
        value = replies.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    with patch.object(mod, "run_command", side_effect=fake), \
         patch.object(mod, "check_circuit_breaker", return_value=(False, "")):
        result = mod.e2e_validation(_state(repo, **overrides))
    return result, capsys.readouterr().err


# ----------------------------------------------------------------- line 45


def test_45_an_unparseable_count_is_zero():
    """Pinned: compliant; the count is advisory (stagnation only)."""
    assert mod._parse_e2e_passed("no counts here") == 0
    assert mod._parse_e2e_passed("3 passed, 1 failed") == 3


# ------------------------------------------------------------ lines 182, 188


def test_182_a_timeout_raises_with_the_command_and_the_ceiling(tmp_path):
    with patch.object(mod, "run_command",
                      side_effect=subprocess.TimeoutExpired(["pytest"], 600)), \
         pytest.raises(mod.E2ERunFailed) as caught:
        mod.run_e2e_tests(["tests/test_e2e.py"], None, tmp_path)
    message = str(caught.value)
    assert f"timed out after {mod.E2E_TIMEOUT_SECONDS}s" in message
    assert "poetry run pytest" in message
    assert "tests/test_e2e.py" in message


def test_182_the_node_halts_with_the_timeout(repo, capsys):
    result, err = _run(repo, capsys, subprocess.TimeoutExpired(["pytest"], 600))
    assert "timed out after" in result["error_message"]
    assert "#7" in result["error_message"]
    assert "ERROR [N6]" in err


def test_188_a_missing_runner_raises_with_its_cause(tmp_path):
    with patch.object(mod, "run_command",
                      side_effect=FileNotFoundError("No such file: 'poetry'")), \
         pytest.raises(mod.E2ERunFailed, match="No such file: 'poetry'"):
        mod.run_e2e_tests([], None, tmp_path)


def test_188_the_node_halts_with_the_cause(repo, capsys):
    result, err = _run(repo, capsys, FileNotFoundError("No such file: 'poetry'"))
    assert "No such file: 'poetry'" in result["error_message"]
    assert "ERROR [N6]" in err


# ------------------------------------------------------------ lines 210, 231


def test_210_the_cleanup_stub_does_not_report_success():
    with pytest.raises(NotImplementedError, match="sandbox cleanup"):
        mod.cleanup_sandbox("owner/sandbox")


def test_231_the_safety_stub_does_not_report_safe():
    with pytest.raises(NotImplementedError, match="safety"):
        mod.verify_safety_limits("owner/sandbox", 5, 3)


def test_231_a_sandbox_run_halts_before_any_test_runs(repo, capsys):
    with patch.object(mod, "run_command") as run:
        result = mod.e2e_validation(_state(repo, sandbox_repo="owner/sandbox"))
    assert "owner/sandbox" in result["error_message"]
    assert "not implemented" in result["error_message"]
    assert "ERROR [N6]" in capsys.readouterr().err
    run.assert_not_called()


# ---------------------------------------------------------------- line 291


@pytest.mark.parametrize("audit_dir", ["", "missing"], ids=["unset", "absent"])
def test_291_no_audit_dir_halts_before_the_run(repo, capsys, audit_dir):
    value = str(repo / audit_dir) if audit_dir else ""
    with patch.object(mod, "run_command") as run:
        result = mod.e2e_validation(_state(repo, audit_dir=value))
    assert "audit" in result["error_message"]
    assert "ERROR [N6]" in capsys.readouterr().err
    run.assert_not_called()


# ---------------------------------------------------------------- line 300


def test_300_a_failed_sandbox_cleanup_halts(repo, capsys):
    with patch.object(mod, "verify_safety_limits", return_value=(True, "")), \
         patch.object(mod, "cleanup_sandbox", return_value=(False, "3 issues left open")):
        result, err = _run(repo, capsys, _proc(0, "2 passed"), sandbox_repo="owner/sandbox")
    assert "3 issues left open" in result["error_message"]
    assert "ERROR [N6]" in err


# ------------------------------------------------------------ lines 313, 337


def test_313_e2e_files_that_collect_nothing_halt(repo, capsys):
    e2e = str(repo / "tests" / "e2e" / "test_flow.py")
    result, err = _run(repo, capsys, _proc(5, "5 deselected in 0.01s"), test_files=[e2e])
    assert e2e in result["error_message"]
    assert "exit 5" in result["error_message"]
    assert "ERROR [N6]" in err


def test_313_a_run_with_no_e2e_test_goes_to_finalize(repo, capsys):
    """WON'T DO, pinned: no E2E or integration file and no marked test is
    nothing to validate, the way N4.5 treats a target with no build hook."""
    result, err = _run(repo, capsys, _proc(5, "3 deselected in 0.01s"))
    assert result["error_message"] == ""
    assert result["next_node"] == "N7_finalize"
    assert err == ""


def test_313_e2e_files_are_judged_inside_the_repository(tmp_path):
    """A checkout named for e2e does not make every test file an E2E file."""
    root = tmp_path / "target-e2e-sandbox"
    files = [
        str(root / "tests" / "test_unit.py"),
        str(root / "tests" / "e2e" / "test_flow.py"),
        "tests/integration/test_db.py",
        str(tmp_path / "elsewhere" / "test_x_integration.py"),
    ]
    assert mod._e2e_files(files, root) == files[1:]


def test_337_no_tests_ran_on_a_nonzero_exit_with_e2e_files_halts(repo, capsys):
    integration = str(repo / "tests" / "integration" / "test_db.py")
    result, _ = _run(repo, capsys, _proc(1, "no tests ran in 0.01s"),
                     test_files=[integration])
    assert integration in result["error_message"]


def test_337_no_tests_ran_without_e2e_files_goes_to_finalize(repo, capsys):
    """WON'T DO, pinned: as for 313."""
    result, _ = _run(repo, capsys, _proc(1, "collected 0 items"))
    assert result["error_message"] == ""
    assert result["next_node"] == "N7_finalize"


# ------------------------------------------------------------ lines 331, 334


def test_331_an_internal_error_names_the_issue_and_the_output(repo, capsys):
    result, err = _run(repo, capsys, _proc(3, "INTERNALERROR> KeyError: 'x'"))
    message = result["error_message"]
    assert message.startswith("E2E validation error")
    assert "#7" in message
    assert "INTERNALERROR> KeyError: 'x'" in message
    assert "ERROR [N6]" in err


@pytest.mark.parametrize("code", [2, -9, 137])
def test_334_only_exit_1_is_a_test_failure(repo, capsys, code):
    result, _ = _run(repo, capsys, _proc(code, "interrupted"))
    assert result["error_message"].startswith("E2E validation error")
    assert f"exited {code}" in result["error_message"]
    assert result.get("next_node") != "N4_implement_code"


# ------------------------------------------------------------ lines 394, 417


def test_394_the_circuit_breaker_halts(repo):
    """Pinned: compliant."""
    with patch.object(mod, "run_command", return_value=_proc(1, "1 failed")), \
         patch.object(mod, "check_circuit_breaker",
                      return_value=(True, "[CIRCUIT] budget spent")):
        result = mod.e2e_validation(_state(repo))
    assert result["error_message"] == "[CIRCUIT] budget spent"


def test_417_the_retry_cap_halts(repo, capsys):
    """Pinned: compliant."""
    result, _ = _run(repo, capsys, _proc(1, "1 failed"), iteration_count=3)
    assert result["error_message"].startswith("E2E failed after 3 iterations")


def test_a_test_failure_under_the_cap_loops_to_implementation(repo, capsys):
    """Pinned: exit 1 is the one code that loops."""
    result, _ = _run(repo, capsys, _proc(1, "1 failed"))
    assert result["next_node"] == "N4_implement_code"
    assert result["error_message"] == ""

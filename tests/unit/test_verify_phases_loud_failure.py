"""testing/nodes/verify_phases.py under standard 0034 (#3585, the #3581 sweep).

N3 and N5 used to step past a failed step: a probe that could not read a
directory answered "not a package", a pytest that timed out or was missing
became a synthetic test failure, a red marker that could not be written or
read was a warning, a snapshot or restore that failed was "(non-fatal)", a
git status that failed measured nothing, an audit directory that was gone
skipped its file, a coverage target nothing named became ``assemblyzero``,
a critical test skipped was a warning, and a framework nobody recognised ran
as pytest. Each now writes an ERROR line and raises ``PhaseStepError``; the
phase's entry point turns it into its halt, routed to HALT, which alerts.

The rows the sweep found compliant are pinned at the end: each is a
registered halt site, and the routers send any error to HALT. Line numbers in
the test names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from assemblyzero.workflows.target_env import TargetEnvironmentError
from assemblyzero.workflows.testing.nodes import verify_phases as vp

pytestmark = pytest.mark.usefixtures("coverage_as_reported")  # #4436: routing, not measuring


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
    ).stdout


@pytest.fixture(autouse=True)
def _quiet_workflow_log(monkeypatch):
    monkeypatch.setattr(vp, "log_workflow_execution", lambda **_kw: None)


@pytest.fixture
def git_repo(tmp_path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-qm", "base")
    return root


def _is_step_error(raised) -> None:
    assert type(raised.value).__name__ == "PhaseStepError", type(raised.value)


def _pytest_result(returncode=1, passed=0, failed=0, errors=0, coverage=0.0, stdout=""):
    return {
        "returncode": returncode,
        "stdout": stdout or f"{passed} passed, {failed} failed",
        "stderr": "",
        "parsed": {"passed": passed, "failed": failed, "errors": errors, "coverage": coverage},
    }


def _red_state(tmp_path, **overrides):
    test_file = tmp_path / "tests" / "test_x.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_x():\n    assert False\n", encoding="utf-8")
    state = {
        "test_files": [str(test_file)],
        "repo_root": str(tmp_path),
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 42,
        "iteration_count": 0,
        "files_to_modify": [],
    }
    state.update(overrides)
    return state


def _green_project(tmp_path) -> dict:
    """A pytest project with one package module and one test file."""
    pkg = tmp_path / "pkg"
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text("X = 1\n", encoding="utf-8")
    test_file = tmp_path / "tests" / "test_mod.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_mod():\n    assert True\n", encoding="utf-8")
    return {
        "test_files": [str(test_file)],
        "implementation_files": [str(pkg / "mod.py")],
        "repo_root": str(tmp_path),
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 42,
        "iteration_count": 0,
        "max_iterations": 10,
        "coverage_target": 90,
        "files_to_modify": [],
        "full_suite_validated": True,
        "skip_e2e": True,
    }


# =============================================================================
# run_pytest (767, 791, 798) and the package probe (594)
# =============================================================================


class TestRunPytest:
    def test_594_a_directory_the_probe_cannot_read_raises(self, tmp_path, monkeypatch, capsys):
        d = tmp_path / "src" / "pkg"
        d.mkdir(parents=True)
        real_iterdir = Path.iterdir

        def refusing(self):
            if self == d:
                raise PermissionError(13, "Permission denied", str(self))
            return real_iterdir(self)

        monkeypatch.setattr(Path, "iterdir", refusing)

        with pytest.raises(RuntimeError, match="Permission denied") as raised:
            vp._is_python_package_dir(d)

        _is_step_error(raised)
        assert str(d) in str(raised.value)
        assert "ERROR" in capsys.readouterr().err

    def test_594_kept_a_missing_directory_is_not_a_package(self, tmp_path):
        """Kept: a path that is not there is not a package, which is an answer."""
        assert vp._is_python_package_dir(tmp_path / "absent") is False

    def test_767_an_environment_that_cannot_run_this_raises(self, monkeypatch):
        """Which environments cannot is test_pytest_runs_in_the_target.py's."""
        def refusing(_root, *, coverage):
            assert coverage is True
            raise TargetEnvironmentError("pytest-cov is not installed")

        monkeypatch.setattr(vp, "require_pytest", refusing)
        monkeypatch.setattr(vp, "run_command", lambda *a, **k: pytest.fail("pytest ran"))

        with pytest.raises(RuntimeError, match="pytest-cov") as raised:
            vp.run_pytest(["tests/test_x.py"], coverage_module="pkg")

        _is_step_error(raised)

    def test_767_kept_no_coverage_asked_asks_for_no_coverage(self, monkeypatch):
        asked = []
        monkeypatch.setattr(
            vp, "require_pytest", lambda _root, *, coverage: asked.append(coverage),
        )
        monkeypatch.setattr(
            vp, "run_command",
            lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "1 failed", ""),
        )

        assert vp.run_pytest(["tests/test_x.py"])["returncode"] == 1
        assert asked == [False]

    def test_791_a_pytest_timeout_raises_naming_command_and_timeout(self, monkeypatch, capsys):
        def timing_out(cmd, **_kw):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=vp.PYTEST_TIMEOUT_SECONDS)

        monkeypatch.setattr(vp, "require_pytest", lambda *a, **k: None)
        monkeypatch.setattr(vp, "run_command", timing_out)

        with pytest.raises(RuntimeError, match=f"{vp.PYTEST_TIMEOUT_SECONDS}") as raised:
            vp.run_pytest(["tests/test_x.py"])

        _is_step_error(raised)
        assert "poetry run pytest" in str(raised.value)
        assert "ERROR" in capsys.readouterr().err

    def test_798_poetry_or_pytest_missing_raises(self, monkeypatch):
        def missing(cmd, **_kw):
            raise FileNotFoundError(2, "No such file or directory", "poetry")

        monkeypatch.setattr(vp, "require_pytest", lambda *a, **k: None)
        monkeypatch.setattr(vp, "run_command", missing)

        with pytest.raises(RuntimeError, match="FileNotFoundError") as raised:
            vp.run_pytest(["tests/test_x.py"])

        _is_step_error(raised)


# =============================================================================
# restore_best_on_failure (841)
# =============================================================================


class TestRestoreBest:
    def _state(self, tmp_path):
        good = tmp_path / "good.py"
        bad = tmp_path / "bad.py"
        snaps = tmp_path / "snap"
        snaps.mkdir()
        for name in ("good.py", "bad.py"):
            (snaps / name).write_text("best\n", encoding="utf-8")
        return good, bad, {
            "best_iteration": {
                "passed": 5, "coverage": 80.0,
                "files": {str(good): str(snaps / "good.py"), str(bad): str(snaps / "bad.py")},
            },
        }

    def test_841_a_file_that_cannot_be_restored_is_named_in_the_halt(self, tmp_path, monkeypatch, capsys):
        good, bad, state = self._state(tmp_path)
        real_copy = shutil.copy2

        def copy(src, dst, *a, **k):
            if dst == str(bad):
                raise OSError(28, "No space left on device")
            return real_copy(src, dst, *a, **k)

        monkeypatch.setattr(shutil, "copy2", copy)

        description = vp.restore_best_on_failure(state)

        assert str(bad) in description
        assert "could not be restored" in description
        assert good.read_text(encoding="utf-8") == "best\n"
        assert f"ERROR [N5] could not restore {bad}" in capsys.readouterr().err

    def test_841_nothing_restorable_still_says_why(self, tmp_path, monkeypatch):
        _good, bad, state = self._state(tmp_path)

        def refusing(src, dst, *a, **k):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(shutil, "copy2", refusing)

        description = vp.restore_best_on_failure(state)

        assert description, "a restore that failed entirely must not read as nothing to restore"
        assert str(bad) in description


# =============================================================================
# The red marker (1009, 1022, 1036) and the hollow check (1241)
# =============================================================================


class TestRedMarker:
    def test_1009_an_audit_dir_that_is_gone_raises(self, tmp_path, capsys):
        state = {"audit_dir": str(tmp_path / "gone"), "issue_number": 42}

        with pytest.raises(RuntimeError, match="red marker") as raised:
            vp.write_red_marker(state, failing=3, exit_code=1)

        _is_step_error(raised)
        assert str(tmp_path / "gone") in str(raised.value)
        assert "ERROR [N3]" in capsys.readouterr().err

    def test_1009_kept_no_audit_dir_named_writes_nothing(self):
        """Kept: N0 always names one; a state without one asked for no trail."""
        assert vp.write_red_marker({"issue_number": 42}, failing=3, exit_code=1) is None

    def test_1022_a_marker_that_cannot_be_written_raises(self, tmp_path):
        (tmp_path / vp.RED_MARKER_NAME).mkdir()

        with pytest.raises(RuntimeError, match="IsADirectoryError") as raised:
            vp.write_red_marker({"audit_dir": str(tmp_path)}, failing=3, exit_code=1)

        _is_step_error(raised)

    def test_1022_the_fail_open_tag_is_gone(self):
        import inspect

        assert "fail-open:" not in inspect.getsource(vp.write_red_marker)

    def test_1036_a_marker_that_cannot_be_read_raises(self, tmp_path):
        (tmp_path / vp.RED_MARKER_NAME).write_text("{not json", encoding="utf-8")

        with pytest.raises(RuntimeError, match="JSONDecodeError") as raised:
            vp.read_red_marker({"audit_dir": str(tmp_path)})

        _is_step_error(raised)
        assert vp.RED_MARKER_NAME in str(raised.value)

    def test_1036_the_fail_open_tag_is_gone(self):
        import inspect

        assert "fail-open:" not in inspect.getsource(vp.read_red_marker)

    def test_1036_kept_no_marker_is_none(self, tmp_path):
        assert vp.read_red_marker({"audit_dir": str(tmp_path)}) is None

    def test_1036_kept_a_written_marker_reads_back(self, tmp_path):
        vp.write_red_marker({"audit_dir": str(tmp_path), "issue_number": 7}, failing=2, exit_code=1)
        assert vp.read_red_marker({"audit_dir": str(tmp_path)})["failing"] == 2

    def test_1241_a_test_file_that_cannot_be_read_raises(self, tmp_path):
        unreadable = tmp_path / "test_dir.py"
        unreadable.mkdir()

        with pytest.raises(RuntimeError, match="hollow") as raised:
            vp._describe_hollow_suite({"test_files": [str(unreadable)]})

        _is_step_error(raised)
        assert str(unreadable) in str(raised.value)


# =============================================================================
# The audit trail (1293, 2431)
# =============================================================================


class TestAuditTrail:
    def test_1293_red_with_an_audit_dir_that_is_gone_halts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vp, "run_pytest", lambda *a, **k: _pytest_result(1, failed=1))
        state = _red_state(tmp_path, audit_dir=str(tmp_path / "gone"))

        result = vp.verify_red_phase(state)

        assert "red-phase.txt" in result["error_message"]
        assert result["error_message"].startswith("PHASE STEP FAILED: [N3]")

    def test_1293_kept_red_with_its_audit_dir_writes_the_output(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vp, "run_pytest", lambda *a, **k: _pytest_result(1, failed=1))
        audit = tmp_path / "audit"
        audit.mkdir()

        result = vp.verify_red_phase(_red_state(tmp_path, audit_dir=str(audit)))

        assert result["error_message"] == ""
        assert list(audit.glob("*red-phase.txt"))

    def test_2431_green_with_an_audit_dir_that_is_gone_halts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            vp, "run_pytest",
            lambda *a, **k: _pytest_result(0, passed=1, coverage=95.0,
                                           stdout="TOTAL 10 0 95%\n1 passed"),
        )
        state = {**_green_project(tmp_path), "audit_dir": str(tmp_path / "gone")}

        result = vp.verify_green_phase(state)

        assert "green-phase.txt" in result["error_message"]
        assert result["error_message"].startswith("PHASE STEP FAILED: [N5]")


# =============================================================================
# Which frameworks run (1697, 1729, 3355)
# =============================================================================


class TestFrameworks:
    def test_1697_an_unknown_framework_halts_instead_of_running_pytest(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vp, "run_pytest", lambda *a, **k: pytest.fail("pytest ran"))
        state = _red_state(tmp_path, framework_config={"framework": "nosuchrunner"})

        result = vp.verify_red_phase(state)

        assert "nosuchrunner" in result["error_message"]
        assert result["next_node"] == "end"

    def test_1729_no_framework_to_run_halts_the_red_phase(self, tmp_path, monkeypatch):
        """With test files, #4236's ownership check already halts; with none,
        no framework ran and the phase used to report success."""
        monkeypatch.setattr(vp, "run_pytest", lambda *a, **k: pytest.fail("pytest ran"))
        state = _red_state(tmp_path, framework_configs=[{}], test_files=[])

        result = vp.verify_red_phase(state)

        assert "no framework" in result["error_message"]

    def test_3355_no_framework_to_run_halts_the_green_phase(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vp, "run_pytest", lambda *a, **k: pytest.fail("pytest ran"))
        state = {**_green_project(tmp_path), "framework_configs": [{}], "test_files": []}

        result = vp.verify_green_phase(state)

        assert "no framework" in result["error_message"]


# =============================================================================
# The hill climb (1798, 1821)
# =============================================================================


class TestHillClimb:
    def _state(self, tmp_path):
        impl = tmp_path / "mod.py"
        impl.write_text("X = 1\n", encoding="utf-8")
        audit = tmp_path / "audit"
        audit.mkdir()
        return impl, {"implementation_files": [str(impl)], "test_files": [], "audit_dir": str(audit)}

    def test_1798_a_snapshot_that_fails_raises(self, tmp_path, monkeypatch, capsys):
        _impl, state = self._state(tmp_path)

        def refusing(*a, **k):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(shutil, "copy2", refusing)

        with pytest.raises(RuntimeError, match="No space left") as raised:
            vp._hill_climb(state, tmp_path, 5, 80.0, [], {})

        _is_step_error(raised)
        assert "ERROR [N5]" in capsys.readouterr().err

    def test_1821_a_restore_that_fails_raises(self, tmp_path, monkeypatch):
        impl, state = self._state(tmp_path)
        updates: dict = {}
        vp._hill_climb(state, tmp_path, 9, 90.0, [], updates)
        state["best_iteration"] = updates["best_iteration"]

        def refusing(*a, **k):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(shutil, "copy2", refusing)

        with pytest.raises(RuntimeError, match="Permission denied") as raised:
            vp._hill_climb(state, tmp_path, 3, 40.0, [], {})

        _is_step_error(raised)
        assert str(impl) in str(raised.value)


# =============================================================================
# Droppings and visual samples (1846, 1849, 1885, 1927, 1932, 1956)
# =============================================================================


class TestDroppings:
    def test_1846_git_that_cannot_run_raises(self, git_repo, monkeypatch):
        def missing(*a, **k):
            raise FileNotFoundError(2, "No such file or directory", "git")

        monkeypatch.setattr(vp.subprocess, "run", missing)

        with pytest.raises(RuntimeError, match="FileNotFoundError") as raised:
            vp._snapshot_untracked(git_repo)

        _is_step_error(raised)

    def test_1849_a_failed_git_status_raises_with_code_and_stderr(self, tmp_path, capsys):
        plain = tmp_path / "plain"
        plain.mkdir()

        with pytest.raises(RuntimeError, match="exit 128") as raised:
            vp._snapshot_untracked(plain)

        _is_step_error(raised)
        assert "not a git repository" in str(raised.value)
        assert "ERROR [N5]" in capsys.readouterr().err

    def test_1849_kept_untracked_paths_are_listed(self, git_repo):
        (git_repo / "new.txt").write_text("x", encoding="utf-8")
        assert vp._snapshot_untracked(git_repo) == {"new.txt"}

    def test_1885_a_dropping_that_cannot_be_deleted_raises(self, git_repo, monkeypatch):
        before = vp._snapshot_untracked(git_repo)
        (git_repo / "baseline.png").write_bytes(b"\0")
        (git_repo / "cache.txt").write_text("x", encoding="utf-8")
        real_unlink = Path.unlink

        def unlink(self, *a, **k):
            if self.name == "baseline.png":
                raise PermissionError(13, "Permission denied", str(self))
            return real_unlink(self, *a, **k)

        monkeypatch.setattr(Path, "unlink", unlink)

        with pytest.raises(RuntimeError, match="baseline.png") as raised:
            vp._remove_test_run_droppings(git_repo, before)

        _is_step_error(raised)
        assert not (git_repo / "cache.txt").exists(), "the other dropping is still removed"

    def test_1927_git_that_cannot_run_raises_for_samples(self, git_repo, tmp_path, monkeypatch):
        audit = tmp_path / "audit"
        audit.mkdir()

        def missing(*a, **k):
            raise OSError("git vanished")

        monkeypatch.setattr(vp.subprocess, "run", missing)

        with pytest.raises(RuntimeError, match="git vanished") as raised:
            vp._preserve_visual_samples(git_repo, str(audit))

        _is_step_error(raised)

    def test_1927_the_fail_open_tags_are_gone(self):
        import inspect

        assert "fail-open:" not in inspect.getsource(vp._preserve_visual_samples)

    def test_1932_a_failed_git_status_raises_for_samples(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        audit = tmp_path / "audit"
        audit.mkdir()

        with pytest.raises(RuntimeError, match="exit 128") as raised:
            vp._preserve_visual_samples(plain, str(audit))

        _is_step_error(raised)

    def test_1956_a_sample_that_cannot_be_copied_raises(self, git_repo, tmp_path, monkeypatch):
        """Raised at the first failure: the droppings removal never runs, so
        every image the run drew is still in the worktree."""
        audit = tmp_path / "audit"
        audit.mkdir()
        (git_repo / "a.png").write_bytes(b"\0")
        (git_repo / "b.png").write_bytes(b"\0")
        real_copy = shutil.copy2

        def copy(src, dst, *a, **k):
            if Path(src).name == "a.png":
                raise OSError(28, "No space left on device")
            return real_copy(src, dst, *a, **k)

        monkeypatch.setattr(shutil, "copy2", copy)

        with pytest.raises(RuntimeError, match="a.png") as raised:
            vp._preserve_visual_samples(git_repo, str(audit))

        _is_step_error(raised)
        assert (git_repo / "a.png").is_file() and (git_repo / "b.png").is_file()


# =============================================================================
# Aligning plan files with the spec (2249, 2261, 2270)
# =============================================================================


class TestAlignWithTheSpec:
    def _layout(self, tmp_path):
        spec = tmp_path / "tests" / "test_issue_42.py"
        spec.parent.mkdir(parents=True)
        spec.write_text("def test_a():\n    assert 1\n", encoding="utf-8")
        plan = tmp_path / "tests" / "test_plan.py"
        plan.write_text("def test_a():\n    assert 0\n", encoding="utf-8")
        return spec, plan

    def _refuse_read(self, monkeypatch, target: Path):
        real = Path.read_text

        def read_text(self, *a, **k):
            if self == target:
                raise PermissionError(13, "Permission denied", str(self))
            return real(self, *a, **k)

        monkeypatch.setattr(Path, "read_text", read_text)

    def test_2249_a_spec_suite_that_cannot_be_read_raises(self, tmp_path, monkeypatch):
        spec, plan = self._layout(tmp_path)
        self._refuse_read(monkeypatch, spec)

        with pytest.raises(RuntimeError, match="spec suite") as raised:
            vp._align_plan_files_with_the_spec({"issue_number": 42}, tmp_path, [str(plan)])

        _is_step_error(raised)
        assert str(spec) in str(raised.value)

    def test_2261_a_plan_file_that_cannot_be_read_raises(self, tmp_path, monkeypatch):
        _spec, plan = self._layout(tmp_path)
        self._refuse_read(monkeypatch, plan)

        with pytest.raises(RuntimeError, match="test_plan.py") as raised:
            vp._align_plan_files_with_the_spec({"issue_number": 42}, tmp_path, [str(plan)])

        _is_step_error(raised)

    def test_2270_an_aligned_file_that_cannot_be_written_raises(self, tmp_path, monkeypatch):
        _spec, plan = self._layout(tmp_path)
        monkeypatch.setattr(
            vp, "align_spec_twins",
            lambda plan_source, spec_source: SimpleNamespace(
                aligned=["test_a"], source="def test_a():\n    assert 1\n", imports_added=[],
            ),
        )
        real_write = Path.write_text

        def write_text(self, *a, **k):
            if self == plan:
                raise OSError(30, "Read-only file system", str(self))
            return real_write(self, *a, **k)

        monkeypatch.setattr(Path, "write_text", write_text)

        with pytest.raises(RuntimeError, match="Read-only") as raised:
            vp._align_plan_files_with_the_spec({"issue_number": 42}, tmp_path, [str(plan)])

        _is_step_error(raised)

    def test_2249_the_fail_open_tags_are_gone(self):
        import inspect

        assert "fail-open:" not in inspect.getsource(vp._align_plan_files_with_the_spec)


# =============================================================================
# The coverage scope (2387, 2393) and the coverage figure (3310)
# =============================================================================


class TestCoverageScope:
    # Ledger lines 2387 and 2393 guarded a derivation that is gone (#4436):
    # the scope is the run's changed files, or the repository root when it
    # changed none, so no candidate path is taken from anywhere else.
    # test_changed_line_coverage.py runs both for real.

    def test_3310_a_leg_result_without_a_coverage_figure_halts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            vp, "_verify_green_pytest_single",
            lambda state: {"next_node": "N6_e2e_validation", "error_message": ""},
        )

        result = vp.verify_green_phase(_green_project(tmp_path))

        assert "coverage" in result["error_message"]
        assert result["next_node"] == "end"


# =============================================================================
# The full-suite gate's exit code (3098) and the skip audit (3192)
# =============================================================================


class TestGates:
    def test_3098_a_full_suite_exit_that_contradicts_its_parse_halts(self, git_repo, monkeypatch):
        monkeypatch.setattr(vp, "run_pytest", lambda *a, **k: _pytest_result(3, passed=12))

        gate = vp._full_suite_gate({}, git_repo, vp.TestFramework.PYTEST, None, 0, 10)

        assert gate is not None
        assert gate["full_suite_validated"] is False
        assert "exit 3" in gate["error_message"]

    def test_3098_kept_a_clean_full_suite_passes(self, git_repo, monkeypatch):
        monkeypatch.setattr(vp, "run_pytest", lambda *a, **k: _pytest_result(0, passed=12))

        assert vp._full_suite_gate({}, git_repo, vp.TestFramework.PYTEST, None, 0, 10) is None

    def test_3192_a_critical_skipped_test_halts_the_green_phase(self, tmp_path, monkeypatch):
        output = (
            "tests/test_mod.py::test_auth_login SKIPPED\n"
            "pkg/mod.py 10 0 100%\nTOTAL 10 0 100%\n3 passed, 1 skipped"
        )
        monkeypatch.setattr(
            vp, "run_pytest",
            lambda *a, **k: _pytest_result(0, passed=3, coverage=100.0, stdout=output),
        )

        result = vp.verify_green_phase(_green_project(tmp_path))

        assert "test_auth_login" in result["error_message"]
        assert "critical" in result["error_message"]


# =============================================================================
# Non-pytest runners (3416, 3592, 3599)
# =============================================================================


class _Runner:
    def __init__(self, result):
        self.result = result

    def require_dependencies(self):
        return None

    def run_tests(self, test_paths=None, measure_coverage=False):
        return dict(self.result)

    def compute_scenario_coverage(self, result, total):
        return 1.0


def _runner_result(exit_code, passed=0, failed=0, errors=0, coverage=None, output="out"):
    return {"raw_output": output, "passed": passed, "failed": failed, "errors": errors,
            "exit_code": exit_code, "total": passed + failed + errors,
            "coverage_percent": coverage}


class TestNonPytest:
    def _state(self, tmp_path, **overrides):
        test_file = tmp_path / "web" / "a.test.ts"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("test('a', () => {})\n", encoding="utf-8")
        state = {
            "test_files": [str(test_file)], "repo_root": str(tmp_path), "audit_dir": "",
            "file_counter": 0, "issue_number": 42, "iteration_count": 0,
            "max_iterations": 10, "files_to_modify": [], "full_suite_validated": True,
            "skip_e2e": True,
        }
        state.update(overrides)
        return state

    def test_3416_a_red_runner_that_crashed_halts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vp, "get_runner", lambda *a, **k: _Runner(
            _runner_result(-1, output="Command timed out after 300s")))

        result = vp.verify_red_phase(self._state(tmp_path, framework_config={"framework": "jest"}))

        assert "crashed" in result["error_message"]
        assert "timed out" in result["error_message"]

    def test_3416_kept_no_tests_without_a_crash_rescaffolds(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vp, "get_runner", lambda *a, **k: _Runner(_runner_result(1)))

        result = vp.verify_red_phase(self._state(tmp_path, framework_config={"framework": "jest"}))

        assert result["next_node"] == "N2_scaffold_tests"
        assert result["error_message"] == ""

    def test_3592_a_green_exit_that_contradicts_its_parse_halts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vp, "get_runner", lambda *a, **k: _Runner(
            _runner_result(1, passed=3, coverage=95.0)))

        result = vp.verify_green_phase(
            self._state(tmp_path, framework_config={"framework": "jest", "coverage_target_percent": 90}))

        assert "exit 1" in result["error_message"]

    def test_3592_a_green_runner_that_crashed_halts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vp, "get_runner", lambda *a, **k: _Runner(
            _runner_result(-1, output="Command not found: npx")))

        result = vp.verify_green_phase(
            self._state(tmp_path, framework_config={"framework": "jest"}))

        assert "crashed" in result["error_message"]
        assert result["next_node"] == "end"

    def test_3599_an_invalid_coverage_type_halts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vp, "get_runner", lambda *a, **k: _Runner(
            _runner_result(0, passed=3, coverage=95.0)))

        result = vp.verify_green_phase(self._state(
            tmp_path, framework_config={"framework": "jest", "coverage_type": "bogus"}))

        assert "bogus" in result["error_message"]


# =============================================================================
# The halt itself, and the rows the sweep found compliant
# =============================================================================


class TestTheHalt:
    def test_a_step_failure_routes_to_halt(self, tmp_path, monkeypatch):
        from assemblyzero.workflows.testing.graph import (
            route_after_green,
            route_after_red,
        )

        monkeypatch.setattr(vp, "run_pytest", lambda *a, **k: _pytest_result(1, failed=1))
        red = vp.verify_red_phase(_red_state(tmp_path, audit_dir=str(tmp_path / "gone")))
        assert route_after_red(red) == "HALT"
        assert route_after_green({"error_message": red["error_message"]}) == "HALT"

    def test_the_halt_site_is_registered(self):
        from assemblyzero.core.gate_registry import GATE_REGISTRY

        key = ("assemblyzero/workflows/testing/nodes/verify_phases.py::"
               "_halt_phase_step_failed::return::0")
        assert [g.key for g in GATE_REGISTRY if key in g.sites] == ["impl.phase_step_failed"]

    def test_the_fail_open_tags_are_all_gone(self):
        import inspect

        assert "fail-open:" not in inspect.getsource(vp)


_COMPLIANT = {
    # ledger line: the site's walker key, at this commit
    1271: "_verify_red_pytest_single::return::0",
    1276: "_verify_red_pytest_single::return::1",
    1423: "_verify_red_pytest_single::return::2",
    1605: "_verify_red_pytest_single::return::3",
    # #4436 read the report ahead of the exit-code stop, so these two swapped.
    2526: "_verify_green_pytest_single::return::1",
    2584: "_verify_green_pytest_single::return::0",
    2669: "_zero_collected_route::return::0",
    2721: "_verify_green_pytest_single::return::2",
    2811: "_verify_green_pytest_single::return::3",
    2891: "_verify_green_pytest_single::return::4",
    2960: "_verify_green_pytest_single::return::5",
    2995: "_verify_green_pytest_single::return::6",
    3398: "_verify_red_non_pytest::return::0",
    3408: "_verify_red_non_pytest::return::1",
    3584: "_verify_green_non_pytest::return::0",
    3647: "_verify_green_non_pytest::return::1",
    3672: "_verify_green_non_pytest::return::2",
    3707: "_verify_green_non_pytest::return::3",
}


_SITES: list = []


def _walked_sites() -> list:
    from assemblyzero.core.gate_registry import scan_halt_sites

    if not _SITES:
        _SITES.extend(scan_halt_sites(Path(__file__).resolve().parents[2])[0])
    return _SITES


@pytest.mark.parametrize("line", sorted(_COMPLIANT))
def test_compliant_row_is_a_registered_halt_that_routes_to_halt(line):
    """Won't do (compliant as found): each returns an error_message, the walker
    finds it, a halt-action gate names it, and N3's and N5's routers send any
    error_message to HALT, which alerts."""
    from assemblyzero.core.gate_registry import ACTION_HALT, GATE_REGISTRY
    from assemblyzero.workflows.testing.graph import route_after_green, route_after_red

    key = f"assemblyzero/workflows/testing/nodes/verify_phases.py::{_COMPLIANT[line]}"
    walked = {site.key for site in _walked_sites()}
    assert key in walked
    gates = [g for g in GATE_REGISTRY if key in g.sites]
    assert len(gates) == 1 and gates[0].action == ACTION_HALT, gates
    assert route_after_red({"error_message": "x"}) == "HALT"
    assert route_after_green({"error_message": "x"}) == "HALT"

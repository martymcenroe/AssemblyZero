"""Provisioning failures report themselves instead of crashing (#1993, #1994).

Both defects surfaced on one live roll (boostgauge #19, 2026-07-31) and each
hid the other:

- #1994: `poetry install` runs BEFORE the implementation writes any code, so on
  a base that predates the work -- exactly what an idempotent roll requires --
  the project package does not exist and poetry refuses. The first roll of any
  arc could not provision.
- #1993: the path that reports that failure returned a BARE stage result rather
  than `update_stage_result(state, ...)`, so `issue_number` was gone by the time
  graph.py persisted the state and the run died with `KeyError: 'issue_number'`
  inside save_orchestration_state -- 60 lines of traceback with no mention of
  poetry. Diagnosing the real cause required reproducing the install by hand.

#4238 moved the install into `assemblyzero/workflows/provisioning.py`, shared by
the orchestrator and the standalone runner; the --no-root rule moved with it.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows import provisioning
from assemblyzero.workflows.orchestrator import stages

MISSING_ROOT = (
    "Installing the current project: boostgauge (0.1.0)\n"
    "Error: The current project could not be installed: "
    "No file/folder found for package boostgauge\n"
)


def _completed(returncode=0, stdout="", stderr=""):
    # mock-ok: subprocess boundary, and a REAL CompletedProcess (standard 0024).
    return subprocess.CompletedProcess(
        args=["poetry", "install"], returncode=returncode,
        stdout=stdout, stderr=stderr,
    )


@pytest.fixture
def poetry_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "boostgauge"\nversion = "0.1.0"\n', encoding="utf-8",
    )
    return tmp_path


class TestNoRootFallback:
    def test_successful_install_is_not_retried(self, poetry_project):
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            return _completed()

        provisioning.provision_worktree(poetry_project, run=fake)

        assert calls == [["poetry", "install"]], calls

    def test_absent_root_package_retries_with_no_root(self, poetry_project):
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            if "--no-root" in cmd:
                return _completed()
            return _completed(returncode=1, stderr=MISSING_ROOT)

        lines = provisioning.provision_worktree(poetry_project, run=fake)

        assert calls[-1] == ["poetry", "install", "--no-root"], calls
        assert any("--no-root" in line for line in lines), lines

    def test_the_message_is_matched_on_stdout_too(self, poetry_project):
        """Poetry writes this to stdout in some versions, stderr in others."""
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            if "--no-root" in cmd:
                return _completed()
            return _completed(returncode=1, stdout=MISSING_ROOT)

        provisioning.provision_worktree(poetry_project, run=fake)

        assert ["poetry", "install", "--no-root"] in calls

    def test_an_unrelated_failure_is_not_retried(self, poetry_project):
        """--no-root must not become a blanket retry that masks real breakage."""
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            return _completed(returncode=1, stderr="Could not parse pyproject.toml")

        with pytest.raises(provisioning.ProvisioningError, match="exited 1"):
            provisioning.provision_worktree(poetry_project, run=fake)

        assert calls == [["poetry", "install"]], calls

    def test_a_failing_no_root_retry_still_reports_failure(self, poetry_project):
        def fake(cmd, **kw):
            if "--no-root" in cmd:
                return _completed(returncode=2, stderr="lock file is stale")
            return _completed(returncode=1, stderr=MISSING_ROOT)

        with pytest.raises(provisioning.ProvisioningError) as caught:
            provisioning.provision_worktree(poetry_project, run=fake)

        assert "exited 2" in str(caught.value)
        assert "poetry install --no-root" in str(caught.value)
        assert "lock file is stale" in str(caught.value)


class TestFailureKeepsTheState:
    """#1993: the report must survive the failure it is reporting."""

    @pytest.fixture
    def state(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        (target / "pyproject.toml").write_text("[tool.poetry]", encoding="utf-8")
        return {
            "issue_number": 19,
            "target_repo": str(target),
            "assemblyzero_root": str(tmp_path / "az"),
            "base_branch": "hardening-run-12",
        }

    def _run_with_failing_install(self, state, tmp_path):
        # The worktree does not pre-exist, so the creation path runs too; the
        # fake `git worktree add` materialises it, as the real one would, with
        # the pyproject.toml that calls for the install. Since #4238 a worktree
        # found on disk is installed as well.
        worktree = tmp_path / "target-19"

        def fake(cmd, **kw):
            if "worktree" in cmd and "add" in cmd:
                worktree.mkdir(parents=True, exist_ok=True)
                (worktree / "pyproject.toml").write_text(
                    "[tool.poetry]", encoding="utf-8"
                )
            if cmd[:2] == ["poetry", "install"]:
                return _completed(returncode=1, stderr="boom: dependency resolution failed")
            return _completed()

        with patch.object(stages, "run_command", fake), \
             patch.object(stages, "worktree_path_for", lambda *a, **k: worktree):
            return stages.run_impl_stage(dict(state))

    def test_the_provisioning_path_actually_ran(self, state, tmp_path):
        """Guards the guard: if the install never ran, the assertions below
        prove nothing."""
        result = self._run_with_failing_install(state, tmp_path)

        blob = str(result.get("stage_results", {}).get("impl", {}))
        assert "provisioning failed" in blob, (
            "provisioning was skipped; these tests would be vacuous"
        )

    def test_issue_number_survives_a_provisioning_failure(self, state, tmp_path):
        """save_orchestration_state does state['issue_number']; losing it turned
        a reportable failure into KeyError."""
        result = self._run_with_failing_install(state, tmp_path)

        assert "issue_number" in result, result
        assert result["issue_number"] == 19

    def test_the_failure_is_recorded_as_a_stage_result(self, state, tmp_path):
        result = self._run_with_failing_install(state, tmp_path)

        impl = result.get("stage_results", {}).get("impl", {})
        assert impl.get("status") == "failed", result

    def test_the_real_cause_reaches_the_operator(self, state, tmp_path):
        """The whole point: the poetry output must not be thrown away."""
        result = self._run_with_failing_install(state, tmp_path)

        blob = str(result.get("stage_results", {}).get("impl", {}))
        assert "provisioning failed" in blob
        assert "dependency resolution failed" in blob


class TestEveryExitKeepsTheState:
    """The defect was one exit out of twelve with the wrong shape, so assert on
    the shape rather than on any single path."""

    def test_no_bare_stage_result_returns_remain(self):
        source = Path(stages.__file__).read_text(encoding="utf-8")
        impl = source[source.index("def run_impl_stage("):]
        impl = impl[: impl.index("\ndef ")]

        bare = [
            line.strip()
            for line in impl.splitlines()
            if line.strip().startswith("return _make_stage_result(")
        ]
        assert bare == [], (
            "every return in run_impl_stage must be wrapped in "
            f"update_stage_result(state, ...); found bare: {bare}"
        )

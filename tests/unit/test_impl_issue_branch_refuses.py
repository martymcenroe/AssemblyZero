"""A real run started on its own issue branch refuses at start (#4158).

The finish lands a worktree the run cut, or found from the integration branch.
A real run started from a checkout already on `<issue>-implementation` had no
such worktree, so it reported SUCCESS, exited 0 and landed nothing. It now
refuses before any model call, the transport probe included, and names where
to start. A run that lands nothing (mock, scaffold-only) is not refused.
"""
# ruff: noqa: F811 -- the landing tests' fixtures are imported and requested by name.
from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from assemblyzero.core import merge_driver, preflight
from tests.unit.test_impl_lands_through_driver import (  # noqa: F401 (fixtures)
    COMPLETED,
    _FakeWorkflow,
    _Landed,
    _run_main,
    driver_configured,
    target_repo,
)


def _on_issue_branch(target):
    subprocess.run(
        ["git", "-C", str(target), "switch", "-q", "-c", "42-implementation"],
        capture_output=True, text=True, check=True,
    )
    return target


@pytest.fixture
def no_probe(monkeypatch):
    calls = []
    monkeypatch.setattr(
        preflight, "check_gemini_transport",
        lambda *a, **k: calls.append(a) or preflight.PreflightResult(
            passed=True, available_credentials=1, total_credentials=1,
        ),
    )
    monkeypatch.setattr(preflight, "_TRANSPORT_RESULT", None)
    return calls


class TestT1ARealRunOnItsOwnBranchRefuses:
    def test_main_refuses_before_any_model_call_or_graph(
        self, target_repo, tmp_path, driver_configured, operator_alerts,
        monkeypatch, no_probe,
    ):
        target = _on_issue_branch(target_repo)
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)
        workflow = _FakeWorkflow(COMPLETED)
        compiled = []
        monkeypatch.setattr(
            workflow, "compile", lambda checkpointer=None: compiled.append(1),
        )

        rc, out = _run_main(target, tmp_path, workflow)

        assert rc not in (0, None), out
        assert compiled == []
        assert no_probe == []
        assert land.calls == []
        assert len(operator_alerts) == 1
        cause = operator_alerts[0]["cause"]
        assert "42-implementation" in cause and "integration branch" in cause


class TestT2ItNeverExitsZeroWithoutLanding:
    def test_a_completed_stand_in_run_on_its_own_branch_is_not_a_success(
        self, target_repo, tmp_path, driver_configured, operator_alerts,
        monkeypatch, no_probe,
    ):
        target = _on_issue_branch(target_repo)
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)

        # write_work=False: on this path the run has no worktree_path for the
        # stand-in to write into, and a crash there would hide the defect.
        rc, out = _run_main(target, tmp_path, _FakeWorkflow(COMPLETED, write_work=False))

        assert not (rc in (0, None) and land.calls == []), out


def _args(**overrides):
    base = {
        "dry_run": False, "mock": False, "scaffold_only": False,
        "no_worktree": False, "issue": 42,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestRunsThatLandNothingAreNotRefused:
    @pytest.mark.parametrize("flag", ["dry_run", "mock", "scaffold_only", "no_worktree"])
    def test_not_refused(self, flag, target_repo):
        from tools.run_implement_from_lld import issue_branch_refusal

        target = _on_issue_branch(target_repo)
        assert issue_branch_refusal(_args(**{flag: True}), target) is None

    def test_the_integration_branch_is_not_refused(self, target_repo):
        from tools.run_implement_from_lld import issue_branch_refusal

        assert issue_branch_refusal(_args(), target_repo) is None

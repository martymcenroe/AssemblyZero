"""The implementation run checks its model transport before it starts (#4239).

`preflight_for_specs` used to run only inside the LLD and spec drafters, so an
implementation run with agy missing cut its worktree and branch and learned at
its first model call that it could not run. `transport_preflight` now runs in
`main()` after the merge-driver check and before the resume contract, the
worktree and the branch.

The unit tier's conftest stands in a passing transport check for every test.
T1 puts the real one back and hides agy from this process: HOME points at an
empty directory (agy installs into `~/.local/bin`), PATH holds only the
system directories, and the WSL lookup finds nothing.
"""
# ruff: noqa: F811 -- the landing tests' fixtures are imported and requested by name.
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from assemblyzero.core import gemini_client, merge_driver, preflight
from assemblyzero.core.preflight import check_gemini_transport as REAL_CHECK
from tests.unit.test_impl_lands_through_driver import (  # noqa: F401 (fixtures)
    COMPLETED,
    _FakeWorkflow,
    _Landed,
    _run_main,
    driver_configured,
    target_repo,
)


def _git_state(target: Path) -> tuple[str, str]:
    def out(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(target), *args],
            capture_output=True, text=True, check=True,
        ).stdout

    return out("worktree", "list", "--porcelain"), out("branch", "-a")


@pytest.fixture
def agy_absent(tmp_path, monkeypatch):
    """The real transport check, on a machine where agy cannot be found."""
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(gemini_client, "_find_wsl_agy", lambda: None)
    monkeypatch.setattr(preflight, "check_gemini_transport", REAL_CHECK)
    monkeypatch.setattr(preflight, "_TRANSPORT_RESULT", None)


class TestT1AMissingTransportStopsTheRunBeforeItStarts:
    def test_main_exits_non_zero_and_alerts(
        self, agy_absent, target_repo, tmp_path, driver_configured,
        operator_alerts, monkeypatch,
    ):
        before = _git_state(target_repo)
        consumed = []
        monkeypatch.setattr(
            "assemblyzero.core.resume_contract.check_and_consume",
            lambda *a, **k: consumed.append(a) or True,
        )
        workflow = _FakeWorkflow(COMPLETED)
        with patch.object(workflow, "compile") as compile_graph:
            rc, out = _run_main(target_repo, tmp_path, workflow)

        assert rc not in (0, None), out
        compile_graph.assert_not_called()
        assert consumed == []
        assert _git_state(target_repo) == before
        assert not (target_repo.parent / "target-42").exists()
        assert len(operator_alerts) == 1
        assert "agy CLI was not found" in operator_alerts[0]["cause"]
        assert "transport preflight" in operator_alerts[0]["where"]


class TestT2AWorkingTransportIsCheckedOnceAndTheRunGoesOn:
    def test_the_check_runs_once_and_the_run_lands(
        self, target_repo, tmp_path, driver_configured, operator_alerts,
        monkeypatch,
    ):
        calls = []

        def answered(client=None, model=preflight.DEFAULT_PROBE_MODEL):
            calls.append(model)
            return preflight.PreflightResult(
                passed=True, available_credentials=1, total_credentials=1,
            )

        monkeypatch.setattr(preflight, "check_gemini_transport", answered)
        monkeypatch.setattr(preflight, "_TRANSPORT_RESULT", None)
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)

        rc, out = _run_main(target_repo, tmp_path, _FakeWorkflow(COMPLETED))

        assert rc == 0, out
        assert calls == ["gemini-3.8-flash-high"]
        assert len(land.calls) == 1
        assert operator_alerts == []


def _args(**overrides):
    base = {
        "dry_run": False, "mock": False, "models": None, "seat": None,
        "reviewer": None, "effort": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestRunsThatCallNoModelAreNotAsked:
    @pytest.mark.parametrize("flag", ["dry_run", "mock"])
    def test_no_probe(self, flag, tmp_path, monkeypatch):
        from tools.run_implement_from_lld import transport_preflight

        def must_not_run(*a, **k):
            raise AssertionError("a run that calls no model was probed")

        monkeypatch.setattr(preflight, "preflight_for_specs", must_not_run)
        assert transport_preflight(_args(**{flag: True}), tmp_path) is None

    def test_a_profile_with_no_gemini_seat_needs_no_gemini_probe(
        self, tmp_path, monkeypatch,
    ):
        """Every seat is read: a stand-in profile with only Claude seats is not
        probed. (`claude.toml` itself keeps four seats on Gemini, among them
        `impl.adversarial`, so a run on it is rightly probed.)"""
        from tools.run_implement_from_lld import transport_preflight

        def must_not_run(*a, **k):
            raise AssertionError("a run with no Gemini seat was probed for Gemini")

        monkeypatch.setattr(preflight, "check_gemini_transport", must_not_run)
        monkeypatch.setattr(preflight, "_TRANSPORT_RESULT", None)
        monkeypatch.setattr(
            "assemblyzero.core.seats.profile_from_args", lambda *a, **k: {},
        )
        monkeypatch.setattr(
            "assemblyzero.core.seats.seat_table",
            lambda profile: {
                "impl.test_plan.review": SimpleNamespace(spec="claude:opus"),
                "impl.adversarial": SimpleNamespace(spec="claude:sonnet"),
            },
        )
        assert transport_preflight(_args(), tmp_path) is None

    def test_one_gemini_seat_is_enough_to_need_the_probe(self, tmp_path, monkeypatch):
        from tools.run_implement_from_lld import transport_preflight

        seen = []
        monkeypatch.setattr(
            preflight, "preflight_for_specs",
            lambda *specs, client=None: seen.extend(specs) or None,
        )
        monkeypatch.setattr(
            "assemblyzero.core.seats.profile_from_args", lambda *a, **k: {},
        )
        monkeypatch.setattr(
            "assemblyzero.core.seats.seat_table",
            lambda profile: {
                "impl.test_plan.review": SimpleNamespace(spec="claude:opus"),
                "impl.adversarial": SimpleNamespace(spec="gemini:3.1-pro"),
            },
        )
        assert transport_preflight(_args(), tmp_path) is None
        assert "gemini:3.1-pro" in seen

"""The cleanup stage must not report success when it cannot land the code (#2019).

Boostgauge #7, 2026-07-31: `rc=0`, "All stages passed", implementation PR #159
left open. `landed = impl_merged or not impl_pr_url` read a missing URL as
"there was no PR to land" -- indistinguishable from "there was one and I lost
it", which is what had happened.

So the one stage positioned to notice the arc failed to accumulate was the
stage reporting green. These pin the recovery and the fault.
"""
from unittest.mock import patch

from assemblyzero.workflows.orchestrator import stages
from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.state import create_initial_state

IMPL_PR = "https://github.com/o/r/pull/159"
LLD_PR = "https://github.com/o/r/pull/158"


def _state(tmp_path, pr_passed=True, **overrides):
    state = create_initial_state(
        7, get_default_config(),
        target_repo=str(tmp_path / "target"),
        assemblyzero_root=str(tmp_path / "az"),
    )
    if pr_passed:
        state["stage_results"] = dict(state.get("stage_results", {}))
        state["stage_results"]["pr"] = {"status": "passed", "artifact_path": IMPL_PR}
        state["pr_url"] = IMPL_PR
    state.update(overrides)
    return state


def _run(state, merge_result):
    with patch.object(stages, "_merge_pr", side_effect=merge_result), \
            patch.object(stages, "_delete_landed_working_copies"), \
            patch.object(stages, "_remove_orchestrator_worktrees"):
        return stages.run_cleanup_stage(state)


class TestAMissingUrlIsRecoveredNotExcused:
    def test_it_lands_the_pr_stage_artifact_when_the_url_is_missing(self, tmp_path):
        """Exactly the live shape: pr stage passed with a PR, impl_pr_url gone."""
        merged = []

        def fake(url, timeout, notes, label="LLD"):
            merged.append((label, url))
            return True

        new_state = _run(_state(tmp_path, lld_pr_url=LLD_PR), fake)

        assert ("impl", IMPL_PR) in merged, merged
        assert new_state["stage_results"]["cleanup"]["status"] == "passed"

    def test_the_recovery_is_stated_not_silent(self, tmp_path, capsys):
        _run(_state(tmp_path), lambda *a, **k: True)
        assert "URL was missing from state" in capsys.readouterr().out

    def test_an_unmergeable_recovered_pr_still_fails(self, tmp_path):
        """Recovery must not become a second way to pass without landing."""
        new_state = _run(_state(tmp_path), lambda u, t, n, label="LLD": label != "impl")

        result = new_state["stage_results"]["cleanup"]
        assert result["status"] == "failed", result
        assert "cannot accumulate" in result.get("error_message", "")


class TestARunThatProducedNoPrMayStillPass:
    def test_no_pr_stage_result_means_nothing_to_land(self, tmp_path):
        """An LLD-only run has no implementation PR and is not a failure."""
        new_state = _run(_state(tmp_path, pr_passed=False), lambda *a, **k: False)
        assert new_state["stage_results"]["cleanup"]["status"] == "passed"

    def test_a_failed_pr_stage_is_not_treated_as_a_landable_pr(self, tmp_path):
        state = _state(tmp_path, pr_passed=False)
        state["stage_results"] = dict(state.get("stage_results", {}))
        state["stage_results"]["pr"] = {"status": "failed", "artifact_path": ""}

        new_state = _run(state, lambda *a, **k: False)
        assert new_state["stage_results"]["cleanup"]["status"] == "passed"


class TestTheExplicitUrlStillWins:
    def test_a_present_impl_pr_url_is_used_as_is(self, tmp_path):
        """The normal path once #2018 is fixed -- recovery must not shadow it."""
        explicit = "https://github.com/o/r/pull/999"
        merged = []

        def fake(url, timeout, notes, label="LLD"):
            merged.append((label, url))
            return True

        _run(_state(tmp_path, impl_pr_url=explicit), fake)
        assert ("impl", explicit) in merged, merged
        assert ("impl", IMPL_PR) not in merged

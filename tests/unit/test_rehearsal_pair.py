"""The two instruments a campaign rehearses with (#2288, #2289).

Both had the same defect from opposite ends. The dry run said an expensive
stage would re-execute when it would not be entered at all, and then printed a
completed pipeline's success banner over a state whose spec was recorded
failed. The mock path could not be reached at all, because the orchestrator
hardcoded ``config_mock_mode: False`` -- so every change to the orchestrated
spec stage was first executed by the roll it was meant to protect.

A rehearsal instrument that lies is worse than none, because the system behaves
correctly while its preview says otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.workflows.orchestrator import graph as g  # noqa: E402
from assemblyzero.workflows.orchestrator import stages as st  # noqa: E402
from assemblyzero.workflows.orchestrator.state import STAGE_ORDER  # noqa: E402


def state_with(current_stage: str, **statuses) -> dict:
    """An orchestration state carrying recorded stage results."""
    return {
        "current_stage": current_stage,
        "stage_results": {
            stage: {"status": status, "artifact_path": f"{stage}.md"}
            for stage, status in statuses.items()
        },
    }


# ---------------------------------------------------------------------------
# #2289 -- the dry run tells the truth
# ---------------------------------------------------------------------------


class TestAPassedStageIsNotAnnouncedAsExecuting:
    """The reported case: boostgauge #7, lld passed, spec failed, resumed."""

    @pytest.fixture
    def resumed(self) -> dict:
        return state_with("spec", triage="skipped", lld="passed", spec="failed")

    def test_the_passed_lld_is_not_reached(self, resumed):
        plan = {row["stage"]: row["action"] for row in g.dry_run_plan(resumed)}
        assert plan["lld"] == g.NOT_REACHED
        assert plan["triage"] == g.NOT_REACHED

    def test_the_failed_spec_and_everything_after_it_runs(self, resumed):
        plan = {row["stage"]: row["action"] for row in g.dry_run_plan(resumed)}
        assert plan["spec"] == g.RUNS
        assert plan["impl"] == g.RUNS
        assert plan["pr"] == g.RUNS
        assert plan["cleanup"] == g.RUNS

    def test_the_rendered_plan_does_not_say_the_lld_will_execute(self, resumed):
        """The literal #2289 assertion, against the rendered text an operator
        actually reads rather than the structure underneath it."""
        rendered = g.format_dry_run_plan(resumed, 7)
        lld_line = next(
            line for line in rendered.splitlines() if line.startswith("lld")
        )
        assert g.RUNS not in lld_line
        assert "not reached" in lld_line

    def test_the_recorded_status_is_shown_rather_than_translated(self, resumed):
        rendered = g.format_dry_run_plan(resumed, 7)
        assert "passed" in rendered
        assert "failed" in rendered

    def test_it_says_where_execution_begins(self, resumed):
        assert "Execution begins at: spec" in g.format_dry_run_plan(resumed, 7)

    def test_the_old_mapping_would_fail_this(self, resumed):
        """The falsifier #2289 asked for: restoring 'anything not skipped is
        EXECUTE' must break the assertions above."""
        old = {
            stage: (
                "SKIP"
                if resumed["stage_results"].get(stage, {}).get("status") == "skipped"
                else "EXECUTE"
            )
            for stage in STAGE_ORDER
        }
        assert old["lld"] == "EXECUTE", "the old display announced the redraw"
        new = {row["stage"]: row["action"] for row in g.dry_run_plan(resumed)}
        assert new["lld"] != old["lld"]


class TestAFreshRunStillReadsCorrectly:
    def test_leading_skipped_stages_are_not_reached(self):
        fresh = state_with("triage", triage="skipped")
        plan = {row["stage"]: row["action"] for row in g.dry_run_plan(fresh)}
        # current_stage is still triage on a fresh run, so position cannot be
        # the whole story -- a recorded 'skipped' has to count on its own.
        assert plan["lld"] == g.RUNS

    def test_an_empty_state_runs_everything(self):
        plan = {row["stage"]: row["action"] for row in g.dry_run_plan({})}
        assert set(plan.values()) == {g.RUNS}


class TestADryRunDoesNotClaimAPipelinePassed:
    def test_the_result_is_marked_as_a_dry_run(self):
        assert "dry_run" in g.OrchestrationResult.__annotations__

    def test_the_launcher_prints_a_rehearsal_banner_not_a_success_one(self):
        source = (ROOT / "tools" / "orchestrate.py").read_text(encoding="utf-8")
        dry_at = source.index('if result.get("dry_run")')
        passed_at = source.index("All stages passed.")
        assert dry_at < passed_at, (
            "the dry-run branch must be taken before the success banner"
        )

    def test_the_rehearsal_banner_makes_no_claim_about_passing(self):
        source = (ROOT / "tools" / "orchestrate.py").read_text(encoding="utf-8")
        assert "No stage was executed." in source
        assert "no claim is made about whether it would pass" in source


# ---------------------------------------------------------------------------
# #2288 -- the spec stage can be rehearsed
# ---------------------------------------------------------------------------


class TestMockModeIsReadFromConfig:
    def test_it_is_off_by_default(self):
        assert st.mock_mode({}) is False
        assert st.mock_mode({"config": {}}) is False

    def test_the_flag_turns_it_on(self):
        assert st.mock_mode({"config": {"mock_mode": True}}) is True

    def test_a_missing_config_is_not_an_error(self):
        assert st.mock_mode({"config": None}) is False


class TestEverySubWorkflowStageGetsTheFlag:
    """The hardcoded False was at exactly one of three sites, which is the
    argument for reading it from config rather than passing it to each.

    #2849: the flag must be sent under the name the RECEIVING schema declares,
    and the three sub-workflows do not agree on it. requirements and
    implementation_spec declare `config_mock_mode`; testing declares
    `mock_mode`, and all nine of its readers ask for that. This test used to
    count one literal three times across stages.py, which held the impl stage
    to the wrong name -- LangGraph dropped the undeclared key, and a --mock
    rehearsal ran the impl stage's nodes for real. Each stage is now checked
    against its own sub-workflow's schema, which is the assertion that would
    have failed then.
    """

    @pytest.mark.parametrize(
        "stage, key, schema_module",
        [
            ("lld", "config_mock_mode", "assemblyzero.workflows.requirements.state"),
            ("spec", "config_mock_mode", "assemblyzero.workflows.implementation_spec.state"),
            ("impl", "mock_mode", "assemblyzero.workflows.testing.state"),
        ],
    )
    def test_the_stage_passes_mock_mode_through(self, stage, key, schema_module):
        import importlib
        import inspect

        source = inspect.getsource(getattr(st, f"run_{stage}_stage"))
        assert f'"{key}": mock_mode(state)' in source, (
            f"run_{stage}_stage must send the flag from config under the name "
            f"its sub-workflow declares ({key})"
        )

        module = importlib.import_module(schema_module)
        schema = next(
            v for k, v in vars(module).items()
            if k.endswith("State") and hasattr(v, "__annotations__")
        )
        assert key in schema.__annotations__, (
            f"{schema_module} does not declare {key}; the flag run_{stage}_stage "
            f"sends is dropped at the invoke boundary (#2849)"
        )

    def test_no_site_hardcodes_it_any_more(self):
        source = (
            ROOT / "assemblyzero" / "workflows" / "orchestrator" / "stages.py"
        ).read_text(encoding="utf-8")
        assert '"config_mock_mode": False' not in source
        assert '"mock_mode": False' not in source


class TestARehearsalReachesNothingOutward:
    def test_the_pr_and_cleanup_stages_are_forbidden(self):
        assert set(st.MOCK_FORBIDDEN_STAGES) == {"pr", "cleanup"}

    @pytest.mark.parametrize("stage", ["pr", "cleanup"])
    def test_a_forbidden_stage_is_never_entered(self, stage, monkeypatch):
        """The runner must not be called at all -- not called and then made to
        behave, which would leave the refusal depending on the runner."""
        entered = []
        monkeypatch.setitem(
            st.STAGE_RUNNERS, stage, lambda s: entered.append(stage) or s
        )
        monkeypatch.setattr(g, "save_orchestration_state", lambda s: None)

        result = g._run_stage_node(
            {
                "current_stage": stage,
                "config": {"mock_mode": True},
                "stage_results": {},
            }
        )

        assert entered == [], f"{stage} runner ran during a rehearsal"
        assert result["stage_results"][stage]["status"] == "skipped"
        assert "outward effects" in result["stage_results"][stage]["error_message"]

    @pytest.mark.parametrize("stage", ["pr", "cleanup"])
    def test_the_same_stage_runs_normally_without_mock_mode(
        self, stage, monkeypatch
    ):
        """The falsifier: the refusal is mock mode's doing, not the stage's."""
        entered = []
        monkeypatch.setitem(
            st.STAGE_RUNNERS, stage, lambda s: entered.append(stage) or dict(s)
        )
        monkeypatch.setattr(g, "save_orchestration_state", lambda s: None)
        monkeypatch.setattr(g, "check_human_gate", lambda s, c: True)

        g._run_stage_node(
            {"current_stage": stage, "config": {}, "stage_results": {}}
        )

        # Entered at least once. The stub records no verdict, so the retry loop
        # re-enters it -- the count is the retry policy's business, not this
        # test's. What matters is that without mock mode the stage IS entered.
        assert entered and set(entered) == {stage}


class TestTheOutwardEffectsInsideAllowedStages:
    def test_the_lld_finalizer_cuts_no_branch_in_mock_mode(self):
        # The package re-exports a `finalize` FUNCTION under that name, and
        # `import a.b.finalize as x` resolves via getattr, so it hands back the
        # function. import_module is the only form that returns the module.
        from importlib import import_module

        finalize = import_module(
            "assemblyzero.workflows.requirements.nodes.finalize"
        )

        called = []
        state = {
            "created_files": ["docs/lld/LLD-007.md"],
            "workflow_type": "lld",
            "issue_number": 7,
            "target_repo": ".",
            "config_mock_mode": True,
        }
        # If it reached the worktree path it would raise long before returning.
        result = finalize._commit_and_push_files(state)

        assert called == []
        assert "commit_sha" not in result
        assert "final_lld_pr_url" not in result

    def test_the_spec_does_not_ride_the_lld_pr_in_mock_mode(self):
        source = (
            ROOT / "assemblyzero" / "workflows" / "orchestrator" / "stages.py"
        ).read_text(encoding="utf-8")
        guard_at = source.index("if mock_mode(state):\n                print(\n"
                                "                    f\"    [mock] spec written")
        ride_at = source.index("_ride_spec_on_lld_pr(\n                    spec_path=")
        assert guard_at < ride_at, "the mock check must gate the commit + push"


class TestTheLauncherExposesIt:
    def test_the_flag_exists_and_sets_config(self):
        source = (ROOT / "tools" / "orchestrate.py").read_text(encoding="utf-8")
        assert '"--mock"' in source
        assert 'overrides["mock_mode"] = True' in source

    def test_capacity_does_not_block_a_run_that_spends_nothing(self):
        source = (ROOT / "tools" / "orchestrate.py").read_text(encoding="utf-8")
        assert "not args.dry_run and not args.mock and not args.ignore_capacity" in source

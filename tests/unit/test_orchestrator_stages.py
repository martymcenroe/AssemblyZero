"""Unit tests for orchestrator stage execution.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.stages import (
    STAGE_RUNNERS,
    check_human_gate,
    run_pr_stage,
    run_triage_stage,
    should_skip_stage,
)
from assemblyzero.workflows.orchestrator.state import (
    OrchestrationState,
    StageResult,
    create_initial_state,
)


class TestShouldSkipStage:
    """Tests for should_skip_stage (T020)."""

    def test_skip_lld_with_existing_artifact(self):
        """T020: Pipeline skips stages with existing artifacts."""
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"lld": "docs/lld/active/305-test.md"}

        with patch("assemblyzero.workflows.orchestrator.stages.validate_artifact", return_value=True):
            skip, path = should_skip_stage(state, "lld", existing)
        assert skip is True
        assert path == "docs/lld/active/305-test.md"

    def test_no_skip_when_config_disabled(self):
        config = get_default_config()
        config["skip_existing_lld"] = False
        state = create_initial_state(305, config)
        existing = {"lld": "docs/lld/active/305-test.md"}

        skip, path = should_skip_stage(state, "lld", existing)
        assert skip is False
        assert path is None

    def test_no_skip_impl_stage(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"impl": "../AssemblyZero-305"}

        skip, path = should_skip_stage(state, "impl", existing)
        assert skip is False

    def test_no_skip_pr_stage(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"pr": "https://github.com/test/pr/1"}

        skip, path = should_skip_stage(state, "pr", existing)
        assert skip is False

    def test_no_skip_when_no_artifact(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"triage": None}

        skip, path = should_skip_stage(state, "triage", existing)
        assert skip is False


class TestCheckHumanGate:
    """Tests for check_human_gate (T040)."""

    def test_gate_enabled_returns_false(self):
        """T040: Human gates configurable per stage."""
        config = get_default_config()
        config["gates"]["pr"] = True
        state = create_initial_state(305, config)

        result = check_human_gate(state, "pr")
        assert result is False

    def test_gate_disabled_returns_true(self):
        config = get_default_config()
        config["gates"]["lld"] = False
        state = create_initial_state(305, config)

        result = check_human_gate(state, "lld")
        assert result is True

    def test_gate_not_configured_defaults_to_no_gate(self):
        config = get_default_config()
        config["gates"] = {}
        state = create_initial_state(305, config)

        result = check_human_gate(state, "triage")
        assert result is True


class TestRunTriageStage:
    """Tests for run_triage_stage."""

    @patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
    @patch("assemblyzero.workflows.orchestrator.stages.validate_artifact")
    def test_skips_when_artifact_exists(self, mock_validate, mock_detect):
        mock_detect.return_value = {"triage": "docs/lineage/305/issue-brief.md", "lld": None, "spec": None, "impl": None, "pr": None}
        mock_validate.return_value = True

        config = get_default_config()
        state = create_initial_state(305, config)
        new_state = run_triage_stage(state)

        assert new_state["stage_results"]["triage"]["status"] == "skipped"
        assert new_state["current_stage"] == "lld"


class TestStageRunners:
    """Tests for STAGE_RUNNERS mapping."""

    def test_all_stages_have_runners(self):
        from assemblyzero.workflows.orchestrator.state import STAGE_ORDER
        for stage in STAGE_ORDER:
            assert stage in STAGE_RUNNERS, f"Missing runner for stage: {stage}"


class TestRunImplStageRepoRoot:
    """Closes #1504. The impl stage carved a worktree but plumbed
    repo_root=target_repo (not the worktree). Testing workflow wrote
    files to target_repo; issue-{N} branch stayed empty; pr stage
    halted with "No commits between main and issue-N."
    """

    @patch("assemblyzero.workflows.orchestrator.stages.run_command")
    def test_impl_invokes_testing_with_repo_root_eq_worktree(
        self, mock_run, tmp_path,
    ):
        from assemblyzero.workflows.orchestrator.stages import run_impl_stage

        # subprocess.run is mocked; treat all calls as successful no-ops.
        out = MagicMock()
        out.stdout = ""
        out.stderr = ""
        out.returncode = 0
        mock_run.return_value = out

        config = get_default_config()
        state = create_initial_state(
            4,
            config,
            target_repo=str(tmp_path / "target"),
            assemblyzero_root=str(tmp_path / "az"),
        )
        # spec_path needs to look real to the impl stage
        state["spec_path"] = str(tmp_path / "spec.md")
        (tmp_path / "spec.md").write_text("# spec")

        captured: dict[str, dict] = {}

        class _StubApp:
            def invoke(self, payload: dict) -> dict:
                captured["payload"] = payload
                # Pretend the testing workflow succeeded.
                return {"error_message": ""}

        class _StubGraph:
            def compile(self) -> _StubApp:
                return _StubApp()

        with patch(
            "assemblyzero.workflows.testing.graph.build_testing_workflow",
            return_value=_StubGraph(),
        ):
            run_impl_stage(state)

        payload = captured.get("payload", {})
        worktree_path = payload.get("worktree_path", "")
        repo_root = payload.get("repo_root", "")
        original_repo_root = payload.get("original_repo_root", "")
        assert worktree_path, "worktree_path must be set"
        assert repo_root == worktree_path, (
            f"repo_root must equal worktree_path so the testing workflow "
            f"writes into the worktree; got repo_root={repo_root!r}, "
            f"worktree_path={worktree_path!r}"
        )
        assert original_repo_root == str(tmp_path / "target"), (
            "original_repo_root must remain the target_repo so the LLD "
            "fallback at load_lld.py:815 can find the spec"
        )


class TestRunPrStage:
    """run_pr_stage must emit a pr-sentinel-compliant PR (Closes #1366).

    pr-sentinel validates the PR *body* for ``Closes #N``; the universal rule
    also requires it in the title. The head branch must be the branch actually
    checked out in the worktree, not a hardcoded ``issue-{N}``.
    """

    @patch("assemblyzero.workflows.orchestrator.stages.run_command")
    def test_pr_body_title_carry_closes_and_branch_matches_worktree(self, mock_run):
        issue = 1366
        worktree_branch = "1366-pr-stage-closes-ref"

        def fake_run(cmd, *args, **kwargs):
            out = MagicMock()
            if cmd[:2] == ["git", "rev-parse"]:
                out.stdout = f"{worktree_branch}\n"
            elif cmd[:3] == ["gh", "pr", "create"]:
                out.stdout = "https://github.com/martymcenroe/AssemblyZero/pull/9999\n"
            else:
                out.stdout = ""
            return out

        mock_run.side_effect = fake_run

        config = get_default_config()
        state = create_initial_state(issue, config)
        state["worktree_path"] = "/tmp/AssemblyZero-1366"

        new_state = run_pr_stage(state)

        assert new_state["stage_results"]["pr"]["status"] == "passed"

        # The `gh pr create` invocation must carry Closes #N in body + title
        # and point --head at the real worktree branch.
        pr_calls = [c for c in mock_run.call_args_list if c.args[0][:3] == ["gh", "pr", "create"]]
        assert len(pr_calls) == 1, "expected exactly one `gh pr create` call"
        argv = pr_calls[0].args[0]
        body = argv[argv.index("--body") + 1]
        title = argv[argv.index("--title") + 1]
        head = argv[argv.index("--head") + 1]

        assert f"Closes #{issue}" in body, f"PR body missing Closes #{issue}: {body!r}"
        assert f"Closes #{issue}" in title, f"PR title missing Closes #{issue}: {title!r}"
        assert head == worktree_branch, f"--head {head!r} != worktree branch {worktree_branch!r}"

        # The branch is pushed by its real name, never the hardcoded issue-{N}.
        push_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["git", "push"]]
        assert len(push_calls) == 1, "expected exactly one `git push` call"
        pushed_argv = push_calls[0].args[0]
        assert worktree_branch in pushed_argv
        assert f"issue-{issue}" not in pushed_argv


class TestMakeStageResultTransient:
    """Tests for transient field plumbing through _make_stage_result. Closes #1463."""

    def test_transient_omitted_by_default(self):
        from assemblyzero.workflows.orchestrator.stages import _make_stage_result

        result = _make_stage_result(status="failed", error_message="boom")
        assert "transient" not in result

    def test_transient_false_recorded(self):
        from assemblyzero.workflows.orchestrator.stages import _make_stage_result

        result = _make_stage_result(status="failed", transient=False)
        assert result["transient"] is False

    def test_transient_true_recorded(self):
        from assemblyzero.workflows.orchestrator.stages import _make_stage_result

        result = _make_stage_result(status="failed", transient=True)
        assert result["transient"] is True


class TestIsNonTransientHalt:
    """Tests for the sub-workflow halt detection helper. Closes #1463."""

    def test_recovery_plan_path_set_means_halt(self):
        from assemblyzero.workflows.orchestrator.stages import _is_non_transient_halt

        assert _is_non_transient_halt({"recovery_plan_path": "/tmp/recovery.json"}) is True

    def test_no_recovery_plan_path_means_not_halt(self):
        from assemblyzero.workflows.orchestrator.stages import _is_non_transient_halt

        assert _is_non_transient_halt({}) is False
        assert _is_non_transient_halt({"recovery_plan_path": ""}) is False

    def test_other_state_fields_ignored(self):
        from assemblyzero.workflows.orchestrator.stages import _is_non_transient_halt

        assert _is_non_transient_halt({"error_message": "foo"}) is False


class TestClassifyHaltTransience:
    """Reads the recovery plan JSON to classify transience. Closes #1478."""

    def test_no_recovery_plan_returns_none(self):
        from assemblyzero.workflows.orchestrator.stages import _classify_halt_transience

        assert _classify_halt_transience({}) is None
        assert _classify_halt_transience({"recovery_plan_path": ""}) is None

    def test_transient_true_in_plan_returns_true(self, tmp_path):
        from assemblyzero.workflows.orchestrator.stages import _classify_halt_transience
        import json

        plan = tmp_path / "rp.json"
        plan.write_text(json.dumps({
            "error_type": "quota_exhausted",
            "is_transient": True,
        }), encoding="utf-8")
        assert _classify_halt_transience({"recovery_plan_path": str(plan)}) is True

    def test_transient_false_in_plan_returns_false(self, tmp_path):
        from assemblyzero.workflows.orchestrator.stages import _classify_halt_transience
        import json

        plan = tmp_path / "rp.json"
        plan.write_text(json.dumps({
            "error_type": "max_iterations_reached",
            "is_transient": False,
        }), encoding="utf-8")
        assert _classify_halt_transience({"recovery_plan_path": str(plan)}) is False

    def test_unreadable_plan_conservatively_returns_false(self, tmp_path):
        """If the halt happened but the plan file is missing or malformed,
        treat as non-transient (skip retry) — the operator's resume hint
        is still the right recovery path."""
        from assemblyzero.workflows.orchestrator.stages import _classify_halt_transience

        missing = tmp_path / "missing.json"
        assert _classify_halt_transience({"recovery_plan_path": str(missing)}) is False

        bad = tmp_path / "bad.json"
        bad.write_text("not valid json{", encoding="utf-8")
        assert _classify_halt_transience({"recovery_plan_path": str(bad)}) is False

    def test_is_transient_missing_defaults_to_false(self, tmp_path):
        """A recovery plan without an is_transient field is treated as
        non-transient (conservative default)."""
        from assemblyzero.workflows.orchestrator.stages import _classify_halt_transience
        import json

        plan = tmp_path / "rp.json"
        plan.write_text(json.dumps({"error_type": "unknown"}), encoding="utf-8")
        assert _classify_halt_transience({"recovery_plan_path": str(plan)}) is False


class TestRunStageNodeRetrySkip:
    """Tests that _run_stage_node skips retry on non-transient failures.

    Closes #1463. The smoke build burned ~24 Gemini calls retrying a halt
    that printed `Transient: No`; the retry loop now reads the transient
    field and breaks out instead of running the sub-workflow twice more.
    """

    def _make_state(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        state["current_stage"] = "triage"
        return state

    def test_non_transient_failure_skips_retry(self):
        from assemblyzero.workflows.orchestrator import graph as graph_mod

        call_count = {"n": 0}

        def fake_runner(s):
            call_count["n"] += 1
            new_state = dict(s)
            new_state["stage_results"] = {
                "triage": {
                    "status": "failed",
                    "error_message": "halted",
                    "duration_seconds": 0.0,
                    "attempts": 1,
                    "transient": False,
                }
            }
            return new_state

        with patch.dict(graph_mod.STAGE_RUNNERS, {"triage": fake_runner}, clear=False), \
             patch("assemblyzero.workflows.orchestrator.graph.save_orchestration_state"):
            result = graph_mod._run_stage_node(self._make_state())

        assert call_count["n"] == 1, "non-transient failure must not be retried"
        assert result["stage_results"]["triage"]["status"] == "failed"

    def test_transient_failure_retries_up_to_max(self):
        from assemblyzero.workflows.orchestrator import graph as graph_mod

        call_count = {"n": 0}

        def fake_runner(s):
            call_count["n"] += 1
            new_state = dict(s)
            new_state["stage_results"] = {
                "triage": {
                    "status": "failed",
                    "error_message": "transient",
                    "duration_seconds": 0.0,
                    "attempts": 1,
                    "transient": True,
                }
            }
            return new_state

        with patch.dict(graph_mod.STAGE_RUNNERS, {"triage": fake_runner}, clear=False), \
             patch("assemblyzero.workflows.orchestrator.graph.save_orchestration_state"), \
             patch("assemblyzero.workflows.orchestrator.graph.time.sleep"):
            result = graph_mod._run_stage_node(self._make_state())

        assert call_count["n"] == 3, "transient failure must retry up to max_retries"
        assert result["stage_results"]["triage"]["status"] == "failed"

    def test_failure_without_transient_field_retries_as_today(self):
        """Backward-compat: absent transient field preserves the current
        retry behavior so non-halt failure paths (e.g. gh CLI flakes) keep
        their retry budget."""
        from assemblyzero.workflows.orchestrator import graph as graph_mod

        call_count = {"n": 0}

        def fake_runner(s):
            call_count["n"] += 1
            new_state = dict(s)
            new_state["stage_results"] = {
                "triage": {
                    "status": "failed",
                    "error_message": "no transient field",
                    "duration_seconds": 0.0,
                    "attempts": 1,
                }
            }
            return new_state

        with patch.dict(graph_mod.STAGE_RUNNERS, {"triage": fake_runner}, clear=False), \
             patch("assemblyzero.workflows.orchestrator.graph.save_orchestration_state"), \
             patch("assemblyzero.workflows.orchestrator.graph.time.sleep"):
            result = graph_mod._run_stage_node(self._make_state())

        assert call_count["n"] == 3, "absent transient field defaults to retry-as-today"
        assert result["stage_results"]["triage"]["status"] == "failed"

    def test_passed_status_does_not_retry(self):
        from assemblyzero.workflows.orchestrator import graph as graph_mod

        call_count = {"n": 0}

        def fake_runner(s):
            call_count["n"] += 1
            new_state = dict(s)
            new_state["stage_results"] = {
                "triage": {
                    "status": "passed",
                    "artifact_path": "/tmp/brief.md",
                    "duration_seconds": 0.0,
                    "attempts": 1,
                }
            }
            return new_state

        with patch.dict(graph_mod.STAGE_RUNNERS, {"triage": fake_runner}, clear=False), \
             patch("assemblyzero.workflows.orchestrator.graph.save_orchestration_state"):
            result = graph_mod._run_stage_node(self._make_state())

        assert call_count["n"] == 1
        assert result["stage_results"]["triage"]["status"] == "passed"

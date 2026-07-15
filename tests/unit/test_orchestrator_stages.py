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

    @patch("assemblyzero.workflows.orchestrator.stages._fetch_issue_body_to_temp_brief")
    @patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
    def test_existing_issue_passes_without_authoring_workflow(
        self, mock_detect, mock_fetch, tmp_path
    ):
        """#1770: `--issue N` means the issue exists — triage persists the
        synthesized brief to the canonical location and passes. It must NOT
        invoke the issue-authoring workflow (which filed a duplicate GitHub
        issue per attempt) and must not depend on `issue_brief_path` (a key
        nothing sets)."""
        mock_detect.return_value = {
            "triage": None, "lld": None, "spec": None, "impl": None, "pr": None,
        }
        temp_brief = tmp_path / "temp-brief.md"
        temp_brief.write_text(
            "# feat: config file\n\n## Summary\nA config file.\n\n"
            "## Issue detail\nBody.\n",
            encoding="utf-8",
        )
        mock_fetch.return_value = (str(temp_brief), "")

        target = tmp_path / "boostgauge"
        target.mkdir()

        config = get_default_config()
        state = create_initial_state(7, config, target_repo=str(target))

        new_state = run_triage_stage(state)

        assert new_state["stage_results"]["triage"]["status"] == "passed"
        canonical = target / "docs" / "lineage" / "7" / "issue-brief.md"
        assert canonical.is_file(), "brief must persist to the skip-artifact path"
        assert "## Summary" in canonical.read_text(encoding="utf-8")
        assert new_state["stage_results"]["triage"]["artifact_path"] == str(canonical)

    @patch("assemblyzero.workflows.orchestrator.stages._fetch_issue_body_to_temp_brief")
    @patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
    def test_brief_synthesis_failure_still_fails_stage(
        self, mock_detect, mock_fetch, tmp_path
    ):
        """An unreachable/empty issue still fails triage loudly (#1770
        preserves the #1508 error path)."""
        mock_detect.return_value = {
            "triage": None, "lld": None, "spec": None, "impl": None, "pr": None,
        }
        mock_fetch.return_value = ("", "issue #7 body is empty")

        config = get_default_config()
        state = create_initial_state(7, config, target_repo=str(tmp_path))

        new_state = run_triage_stage(state)

        assert new_state["stage_results"]["triage"]["status"] == "failed"
        assert "empty" in new_state["stage_results"]["triage"]["error_message"]


class TestImplWorktreeUpstreamPush:
    """#1780: the impl worktree branch is pushed -u at creation so
    checkpoint pushes work (crash-resilience)."""

    @patch("assemblyzero.workflows.orchestrator.stages.run_command")
    def test_worktree_creation_pushes_upstream(self, mock_run, tmp_path):
        from assemblyzero.workflows.orchestrator.stages import run_impl_stage

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
        state["spec_path"] = str(tmp_path / "spec.md")
        (tmp_path / "spec.md").write_text("# spec")

        class _StubApp:
            def invoke(self, payload: dict) -> dict:
                return {"error_message": ""}

        class _StubGraph:
            def compile(self) -> _StubApp:
                return _StubApp()

        with patch(
            "assemblyzero.workflows.testing.graph.build_testing_workflow",
            return_value=_StubGraph(),
        ):
            run_impl_stage(state)

        push_calls = [
            c for c in mock_run.call_args_list
            if len(c.args[0]) >= 4 and c.args[0][3:4] == ["push"]
            or ("push" in c.args[0] and "-u" in c.args[0])
        ]
        assert any(
            "-u" in c.args[0] and "issue-4" in c.args[0] for c in push_calls
        ), f"expected a push -u origin issue-4 at worktree creation; calls: {[c.args[0] for c in mock_run.call_args_list]}"


class TestWorktreeRemovalRetry:
    """#1781: transient Windows file locks — retry before declaring residue."""

    @patch("assemblyzero.workflows.orchestrator.stages.time.sleep")
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.remove_worktree")
    def test_lock_then_success_is_removed(self, mock_remove, mock_sleep, tmp_path):
        from assemblyzero.workflows.orchestrator.stages import (
            _remove_orchestrator_worktrees,
        )

        target = tmp_path / "boostgauge"
        target.mkdir()
        (tmp_path / "boostgauge-7-lld").mkdir()
        (tmp_path / "boostgauge-7").mkdir()

        # Each worktree: first attempt locked, second succeeds
        mock_remove.side_effect = [
            OSError("exit 128: file in use"), None,
            OSError("exit 128: file in use"), None,
        ]

        notes: list[str] = []
        _remove_orchestrator_worktrees(str(target), 7, lld_merged=False, notes=notes)

        joined = "\n".join(notes)
        assert "removed LLD worktree" in joined
        assert "removed impl worktree" in joined
        assert "residue" not in joined
        assert mock_remove.call_count == 4

    @patch("assemblyzero.workflows.orchestrator.stages.time.sleep")
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.remove_worktree")
    def test_persistent_lock_reports_residue_without_force(
        self, mock_remove, mock_sleep, tmp_path
    ):
        from assemblyzero.workflows.orchestrator.stages import (
            _remove_orchestrator_worktrees,
        )

        target = tmp_path / "boostgauge"
        target.mkdir()
        (tmp_path / "boostgauge-7").mkdir()

        mock_remove.side_effect = OSError("exit 128: file in use")

        notes: list[str] = []
        _remove_orchestrator_worktrees(str(target), 7, lld_merged=False, notes=notes)

        joined = "\n".join(notes)
        assert "residue left, no --force" in joined
        assert mock_remove.call_count == 5  # #1783: 5 backoff attempts, then honest residue


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


class TestLldStageBaseBranchThreading:
    """#1755: the lld stage must thread base_branch into the requirements
    graph's invoke payload so the LLD PR targets the attempt branch."""

    @patch("assemblyzero.workflows.orchestrator.stages.run_command")
    def test_lld_invoke_payload_carries_base_branch(self, mock_run, tmp_path):
        from assemblyzero.workflows.orchestrator.stages import run_lld_stage

        out = MagicMock()
        out.stdout = ""
        out.stderr = ""
        out.returncode = 0
        mock_run.return_value = out

        config = get_default_config()
        state = create_initial_state(
            7,
            config,
            target_repo=str(tmp_path / "target"),
            assemblyzero_root=str(tmp_path / "az"),
        )
        state["base_branch"] = "speedrun-attempt-1"

        captured: dict[str, dict] = {}
        final_lld = tmp_path / "LLD-007.md"
        final_lld.write_text("# LLD")

        class _StubApp:
            def invoke(self, payload: dict) -> dict:
                captured["payload"] = payload
                return {
                    "error_message": "",
                    "final_lld_path": str(final_lld),
                    "final_verdict": "APPROVED",
                }

        class _StubGraph:
            def compile(self) -> _StubApp:
                return _StubApp()

        with patch(
            "assemblyzero.workflows.requirements.graph.create_requirements_graph",
            return_value=_StubGraph(),
        ):
            run_lld_stage(state)

        payload = captured.get("payload", {})
        assert payload.get("base_branch") == "speedrun-attempt-1", (
            "lld stage must thread the pipeline's base_branch into the "
            f"requirements graph payload; got {payload.get('base_branch')!r}"
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
        state["base_branch"] = "main"

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
        base = argv[argv.index("--base") + 1]

        assert f"Closes #{issue}" in body, f"PR body missing Closes #{issue}: {body!r}"
        assert f"Closes #{issue}" in title, f"PR title missing Closes #{issue}: {title!r}"
        assert head == worktree_branch, f"--head {head!r} != worktree branch {worktree_branch!r}"
        assert base == "main", f"--base {base!r} != state base_branch 'main'"

        # The branch is pushed by its real name, never the hardcoded issue-{N}.
        push_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["git", "push"]]
        assert len(push_calls) == 1, "expected exactly one `git push` call"
        pushed_argv = push_calls[0].args[0]
        assert worktree_branch in pushed_argv
        assert f"issue-{issue}" not in pushed_argv

    @patch("assemblyzero.workflows.orchestrator.stages.run_command")
    def test_pr_base_is_attempt_branch_from_state(self, mock_run):
        """#1755 attempt-branch model: the impl PR targets the integration
        branch captured at pipeline start, never a hardcoded main."""
        issue = 7

        def fake_run(cmd, *args, **kwargs):
            out = MagicMock()
            if cmd[:2] == ["git", "rev-parse"]:
                out.stdout = "issue-7\n"
            elif cmd[:3] == ["gh", "pr", "create"]:
                out.stdout = "https://github.com/owner/boostgauge/pull/99\n"
            else:
                out.stdout = ""
            return out

        mock_run.side_effect = fake_run

        config = get_default_config()
        state = create_initial_state(issue, config)
        state["worktree_path"] = "/tmp/boostgauge-7"
        state["base_branch"] = "speedrun-attempt-1"

        new_state = run_pr_stage(state)

        assert new_state["stage_results"]["pr"]["status"] == "passed"
        pr_calls = [c for c in mock_run.call_args_list if c.args[0][:3] == ["gh", "pr", "create"]]
        argv = pr_calls[0].args[0]
        base = argv[argv.index("--base") + 1]
        assert base == "speedrun-attempt-1", (
            f"impl PR must target the attempt branch — got {base!r}"
        )

    @patch("assemblyzero.workflows.orchestrator.stages.current_branch")
    @patch("assemblyzero.workflows.orchestrator.stages.run_command")
    def test_pr_base_detected_when_state_predates_key(self, mock_run, mock_branch):
        """Persisted states from before #1755 lack base_branch — the pr
        stage detects it from the target repo instead of assuming main."""
        issue = 7

        def fake_run(cmd, *args, **kwargs):
            out = MagicMock()
            if cmd[:2] == ["git", "rev-parse"]:
                out.stdout = "issue-7\n"
            elif cmd[:3] == ["gh", "pr", "create"]:
                out.stdout = "https://github.com/owner/boostgauge/pull/99\n"
            else:
                out.stdout = ""
            return out

        mock_run.side_effect = fake_run
        mock_branch.return_value = "speedrun-attempt-3"

        config = get_default_config()
        state = create_initial_state(issue, config)
        state["worktree_path"] = "/tmp/boostgauge-7"
        state["target_repo"] = "/tmp/boostgauge"
        state.pop("base_branch", None)

        run_pr_stage(state)

        mock_branch.assert_called_once_with("/tmp/boostgauge")
        pr_calls = [c for c in mock_run.call_args_list if c.args[0][:3] == ["gh", "pr", "create"]]
        argv = pr_calls[0].args[0]
        assert argv[argv.index("--base") + 1] == "speedrun-attempt-3"


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


class TestTriageBriefSynthesis:
    """#1508: Triage stage synthesizes a brief from the GitHub issue body
    when no operator-authored brief exists at docs/lineage/{N}/issue-brief.md.

    Pre-fix: the triage sub-workflow's `_load_brief` halted with "No brief
    file specified" in 0 seconds because `brief_file` wasn't threaded into
    the sub-workflow state. This hit every external smoke build on a fresh
    issue with no pre-authored brief (first observed on Chiron #37).
    """

    @patch("assemblyzero.workflows.orchestrator.stages.subprocess.run")
    @patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
    def test_triage_fetches_issue_body_when_no_brief_exists(
        self, mock_detect, mock_subprocess, tmp_path
    ):
        """When no brief on disk: fetch the issue body, synthesize a brief,
        persist it to the canonical skip-artifact path, and PASS.

        #1770 rewrote the tail of this flow: the issue-authoring
        sub-workflow is no longer invoked from triage (it filed duplicate
        GitHub issues and its result was checked against a key nothing
        sets), so this test now pins the persist-and-pass contract."""
        import json as _json

        # No existing artifact at docs/lineage/{N}/issue-brief.md
        mock_detect.return_value = {k: None for k in ("triage", "lld", "spec", "impl", "pr")}

        # Mock `gh issue view` returning a non-empty body
        gh_result = MagicMock()
        gh_result.returncode = 0
        gh_result.stdout = _json.dumps({
            "title": "Fresh issue from GitHub",
            "body": "Body content the operator never pre-authored a Michelle-voice brief for.",
        })
        gh_result.stderr = ""
        mock_subprocess.return_value = gh_result

        target = tmp_path / "target-repo"
        target.mkdir()
        state = create_initial_state(
            37, get_default_config(),
            target_repo=str(target),
            assemblyzero_root="/fake/projects/AssemblyZero",
        )

        result = run_triage_stage(state)

        # gh was called for the right issue against the right cwd
        gh_calls = [
            c for c in mock_subprocess.call_args_list
            if c[0][0][:3] == ["gh", "issue", "view"]
        ]
        assert gh_calls, "gh issue view must be called"
        args = gh_calls[0][0][0]
        assert args[:4] == ["gh", "issue", "view", "37"]
        assert gh_calls[0][1]["cwd"] == str(target)

        # #1770: stage passes; brief persisted to the canonical location
        triage_result = result["stage_results"]["triage"]
        assert triage_result["status"] == "passed"
        canonical = target / "docs" / "lineage" / "37" / "issue-brief.md"
        assert canonical.is_file()
        content = canonical.read_text(encoding="utf-8")
        assert "Fresh issue from GitHub" in content
        assert "Body content the operator never pre-authored" in content
        assert triage_result["artifact_path"] == str(canonical)

    @patch("assemblyzero.workflows.orchestrator.stages.subprocess.run")
    @patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
    def test_triage_fails_gracefully_when_gh_issue_fetch_errors(
        self, mock_detect, mock_subprocess,
    ):
        """When gh fails (issue doesn't exist, network, etc.): stage halts
        with a clear error pointing at the workaround, NOT silently calls
        the sub-workflow with empty brief_file."""
        mock_detect.return_value = {k: None for k in ("triage", "lld", "spec", "impl", "pr")}

        gh_result = MagicMock()
        gh_result.returncode = 1
        gh_result.stdout = ""
        gh_result.stderr = "GraphQL: Could not resolve to an Issue"
        mock_subprocess.return_value = gh_result

        state = create_initial_state(
            99999, get_default_config(),
            target_repo="/fake/projects/Chiron",
            assemblyzero_root="/fake/projects/AssemblyZero",
        )

        result = run_triage_stage(state)

        assert result["stage_results"]["triage"]["status"] == "failed"
        err = result["stage_results"]["triage"]["error_message"]
        assert "cannot synthesize brief" in err
        # Points the operator at the workaround
        assert "docs/lineage/99999/issue-brief.md" in err


class TestSynthesizeBriefSummary:
    """#1530: _synthesize_brief_summary prepends an AI-generated summary to
    the auto-synthesized brief so issues start with a concise overview, not
    raw GitHub issue text.

    All tests mock the provider so no real API/CLI calls are made.
    """

    def _mock_provider(self, response: str | None = None, succeed: bool = True):
        """Build a MagicMock LLMCallResult-returning provider."""
        from assemblyzero.core.llm_provider import LLMCallResult

        result = LLMCallResult(
            success=succeed,
            response=response,
            raw_response=response,
            error_message=None if succeed else "mock error",
            provider="mock",
            model_used="haiku",
            duration_ms=10,
            attempts=1,
        )
        provider = MagicMock()
        provider.invoke.return_value = result
        return provider

    @patch("assemblyzero.workflows.orchestrator.stages.get_provider")
    def test_returns_summary_on_success(self, mock_get_provider):
        """When the model returns a non-empty response, the summary is returned."""
        from assemblyzero.workflows.orchestrator.stages import _synthesize_brief_summary

        expected = "This issue asks for a new summary section in the auto-synthesized brief."
        mock_get_provider.return_value = self._mock_provider(response=expected)

        result = _synthesize_brief_summary("Add summary to briefs", "Detailed description here.")
        assert result == expected

    @patch("assemblyzero.workflows.orchestrator.stages.get_provider")
    def test_returns_empty_on_model_failure(self, mock_get_provider):
        """When the model call fails, the function returns empty string (caller falls back)."""
        from assemblyzero.workflows.orchestrator.stages import _synthesize_brief_summary

        mock_get_provider.return_value = self._mock_provider(response=None, succeed=False)

        result = _synthesize_brief_summary("Some issue", "Some body")
        assert result == ""

    @patch("assemblyzero.workflows.orchestrator.stages.get_provider")
    def test_returns_empty_on_empty_response(self, mock_get_provider):
        """When the model returns an empty/whitespace string, the function returns empty."""
        from assemblyzero.workflows.orchestrator.stages import _synthesize_brief_summary

        mock_get_provider.return_value = self._mock_provider(response="   ")

        result = _synthesize_brief_summary("Some issue", "Some body")
        assert result == ""

    @patch("assemblyzero.workflows.orchestrator.stages.get_provider")
    def test_returns_empty_on_provider_exception(self, mock_get_provider):
        """When get_provider raises, the function returns empty (no crash)."""
        from assemblyzero.workflows.orchestrator.stages import _synthesize_brief_summary

        mock_get_provider.side_effect = RuntimeError("claude not found")

        result = _synthesize_brief_summary("Some issue", "Some body")
        assert result == ""

    @patch("assemblyzero.workflows.orchestrator.stages.get_provider")
    def test_uses_haiku_model(self, mock_get_provider):
        """Provider is requested with 'claude:haiku' (fast/cheap for summaries)."""
        from assemblyzero.workflows.orchestrator.stages import _synthesize_brief_summary

        mock_get_provider.return_value = self._mock_provider(response="A summary.")
        _synthesize_brief_summary("Title", "Body")

        mock_get_provider.assert_called_once_with("claude:haiku")


class TestFetchIssueBriefWithSummary:
    """#1530: _fetch_issue_body_to_temp_brief writes a ## Summary section when
    _synthesize_brief_summary returns non-empty, and falls back to the raw
    title+body passthrough when synthesis fails.
    """

    def _make_gh_result(self, title: str, body: str) -> MagicMock:
        import json as _json
        gh = MagicMock()
        gh.returncode = 0
        gh.stdout = _json.dumps({"title": title, "body": body})
        gh.stderr = ""
        return gh

    @patch("assemblyzero.workflows.orchestrator.stages._synthesize_brief_summary")
    @patch("assemblyzero.workflows.orchestrator.stages.subprocess.run")
    def test_brief_contains_summary_section_when_synthesis_succeeds(
        self, mock_subprocess, mock_synthesize,
    ):
        """When synthesis returns text, the temp brief contains ## Summary and ## Issue detail."""
        from assemblyzero.workflows.orchestrator.stages import _fetch_issue_body_to_temp_brief

        issue_body = "The raw issue body describing the change needed."
        generated_summary = "This is the generated 2-sentence summary."
        mock_subprocess.return_value = self._make_gh_result("My Issue Title", issue_body)
        mock_synthesize.return_value = generated_summary

        temp_path, err = _fetch_issue_body_to_temp_brief(42, "/fake/repo")
        assert not err, f"unexpected error: {err}"
        assert temp_path

        content = Path(temp_path).read_text(encoding="utf-8")
        assert "## Summary" in content, "brief must contain ## Summary section"
        assert generated_summary in content, "generated summary text must be in brief"
        assert "## Issue detail" in content, "brief must contain ## Issue detail section"
        assert issue_body in content, "original issue body must be in ## Issue detail"

    @patch("assemblyzero.workflows.orchestrator.stages._synthesize_brief_summary")
    @patch("assemblyzero.workflows.orchestrator.stages.subprocess.run")
    def test_brief_falls_back_to_raw_when_synthesis_returns_empty(
        self, mock_subprocess, mock_synthesize,
    ):
        """When synthesis returns empty string, the brief falls back to raw title+body passthrough."""
        from assemblyzero.workflows.orchestrator.stages import _fetch_issue_body_to_temp_brief

        issue_body = "The raw issue body."
        mock_subprocess.return_value = self._make_gh_result("My Issue Title", issue_body)
        mock_synthesize.return_value = ""  # synthesis failed

        temp_path, err = _fetch_issue_body_to_temp_brief(42, "/fake/repo")
        assert not err, f"unexpected error: {err}"
        assert temp_path

        content = Path(temp_path).read_text(encoding="utf-8")
        # Raw passthrough: title + body, no ## Summary section
        assert "## Summary" not in content, "raw passthrough must NOT include ## Summary"
        assert "My Issue Title" in content
        assert issue_body in content

    @patch("assemblyzero.workflows.orchestrator.stages._synthesize_brief_summary")
    @patch("assemblyzero.workflows.orchestrator.stages.subprocess.run")
    def test_issue_detail_section_labels_body_when_synthesis_succeeds(
        self, mock_subprocess, mock_synthesize,
    ):
        """The ## Issue detail section must immediately precede the original body text."""
        from assemblyzero.workflows.orchestrator.stages import _fetch_issue_body_to_temp_brief

        issue_body = "Specific body text to locate in ## Issue detail."
        mock_subprocess.return_value = self._make_gh_result("Title", issue_body)
        mock_synthesize.return_value = "A concise summary."

        temp_path, err = _fetch_issue_body_to_temp_brief(1530, "/fake/repo")
        assert not err
        content = Path(temp_path).read_text(encoding="utf-8")
        # ## Issue detail section must appear before the body
        detail_idx = content.index("## Issue detail")
        body_idx = content.index(issue_body)
        assert detail_idx < body_idx, "## Issue detail heading must precede the body text"

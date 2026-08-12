"""A blocked finalize is repaired as edits, never regenerated (#2233).

The measured failure is `run-issue7-234943` (boostgauge, 2026-08-11). Draft
005 passed mechanical validation, passed test-plan validation at 22/22, and
came back from the adversarial reviewer APPROVED. Finalize's own gate then
blocked it, the stage failed, and the orchestrator discarded the whole
attempt:

    VALIDATION: BLOCKED: Unresolved open questions remain
    [ORCHESTRATOR] Stage 'lld' failed (attempt 1/3). Retrying in 10s...
    [ORCHESTRATOR] Next attempt will be regenerated (discarding the previous
    attempt's generated files).

The regenerated attempt re-paid the requirements gate, the initial draft, a
mechanical-fix revision and a review, and produced the identical block,
because the defect was systematic rather than draft-specific.

A finalize validation failure is a mechanical property of a finished
document, so it belongs on the same edge a mechanical-validation failure
already takes: back to the revision node with the errors as feedback, applied
as edit blocks (#2200) so everything unnamed survives byte-identical. These
tests hold that edge open, hold the regeneration shut, and pin the two
terminal states — a repair that cannot be expressed as edits, and a repair
budget that runs out.

Fixture note. `boostgauge-7-234943-005-draft.md` is that run's draft 005,
byte-for-byte, and its role here is the APPROVED document whose content the
repair must preserve. It is no longer the failure TRIGGER: #2232 (482680dc)
landed after the issue was filed and normalised the none-vocabulary, so the
`- [ ] None` scaffold this draft carries no longer blocks once the review
node reports NONE. Both replacement triggers the issue's fixture note offers
are exercised below — a genuine unchecked question, which still blocks by
design, and a directly injected validation error, which covers finalize
failures that have nothing to do with open questions.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.workflows.requirements.graph import (
    create_requirements_graph,
    route_after_finalize,
    route_after_generate_draft,
)
from assemblyzero.workflows.requirements.nodes.finalize import (
    MAX_FINALIZE_REPAIRS,
    finalize,
    open_questions_settled,
    validate_lld_final,
)

fz = import_module("assemblyzero.workflows.requirements.nodes.finalize")
gd = import_module("assemblyzero.workflows.requirements.nodes.generate_draft")

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "lld_revision"

#: The one line in draft 005's Open Questions section, and a genuine question
#: to stand in its place. #2232's own negative tests pin that a real unchecked
#: question still blocks finalize, which is what makes it a valid trigger.
NONE_SCAFFOLD = "- [ ] None"
REAL_QUESTION = "- [ ] Should the config file live in APPDATA instead of the project root?"
ANSWERED = "- [x] Resolved: the config file lives in the project root."


@pytest.fixture(scope="module")
def draft_005() -> str:
    return (FIXTURES / "boostgauge-7-234943-005-draft.md").read_text(encoding="utf-8")


@pytest.fixture
def blocked_draft(draft_005) -> str:
    """Draft 005 with a genuine open question in place of the scaffold."""
    return draft_005.replace(NONE_SCAFFOLD, REAL_QUESTION, 1)


def _result(response: str) -> LLMCallResult:
    return LLMCallResult(
        success=True,
        response=response,
        raw_response=response,
        error_message=None,
        provider="fake",
        model_used="fake-model",
        duration_ms=1,
        attempts=1,
    )


def _edit_block(search: str, replace: str) -> str:
    return f"<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE"


class _Recorder:
    """A drafter that records every call and replays canned responses."""

    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def invoke(self, **kwargs) -> LLMCallResult:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError(
                "drafter invoked more times than the test supplied responses; "
                "a repair makes exactly one call and never falls back"
            )
        return _result(self._responses.pop(0))


@pytest.fixture
def approved_state(tmp_path, blocked_draft):
    """An APPROVED LLD sitting at finalize with a blocking open question."""
    audit = tmp_path / "audit"
    audit.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    return {
        "workflow_type": "lld",
        "assemblyzero_root": str(ROOT),
        "target_repo": str(repo),
        "audit_dir": str(audit),
        "config_mock_mode": False,
        "config_drafter": "fake:model",
        "issue_number": 7,
        "issue_title": "configuration file and CLI arguments",
        "issue_body": "the issue body",
        "current_draft": blocked_draft,
        "lld_status": "APPROVED",
        "open_questions_status": "UNANSWERED",
        "verdict_count": 1,
        "draft_count": 3,
        "iteration_count": 5,
        "max_iterations": 3,
    }


@pytest.fixture
def quiet_finalize(monkeypatch):
    """Finalize's real validation and save logic, without git or telemetry."""
    monkeypatch.setattr(fz, "_commit_and_push_files", lambda state: state)
    monkeypatch.setattr(fz, "log_workflow_execution", lambda **kw: None)
    monkeypatch.setattr(fz, "move_lineage_to_done", lambda *a, **k: None)
    monkeypatch.setattr(fz, "update_lld_status", lambda **kw: None)


def _revise(monkeypatch, state, drafter):
    monkeypatch.setattr(gd, "get_provider", lambda spec, *a, **k: drafter)
    return gd.generate_draft(state)


# ---------------------------------------------------------------------------
# The regression fixture (acceptance 2)
# ---------------------------------------------------------------------------


class TestTheDiscardedApprovedDraft:
    def test_the_fixture_is_the_run_issue7_234943_artifact(self, draft_005):
        """358 lines, the run's title, and the scaffold it died on."""
        assert len(draft_005.splitlines()) == 358
        assert draft_005.startswith(
            "# Issue #7 - Feature: configuration file and CLI arguments"
        )
        assert NONE_SCAFFOLD in draft_005

    def test_2232_is_why_the_scaffold_no_longer_triggers_the_block(self, draft_005):
        """The fixture note, asserted rather than trusted.

        A fresh reader following the issue body literally would use `- [ ]
        None` as the failing input and find it passes. It passes because the
        review node reports NONE for a draft that asks nothing, and #2232
        widened the settled-statuses to include it.
        """
        assert open_questions_settled("NONE") is True
        assert validate_lld_final(draft_005, open_questions_resolved=True) == []

    def test_a_genuine_open_question_still_blocks_finalize(self, blocked_draft):
        """So it is a valid replacement trigger, per the issue's fixture note."""
        assert open_questions_settled("UNANSWERED") is False
        errors = validate_lld_final(blocked_draft, open_questions_resolved=False)
        assert "Unresolved open questions remain" in errors

    def test_draft_005_plus_its_finalize_error_yields_a_one_edit_repair(
        self, monkeypatch, approved_state, quiet_finalize, blocked_draft, tmp_path
    ):
        """The whole acceptance, end to end, on the real artifact.

        Finalize blocks, the router sends it to the revision node, the model
        names ONE edit, and the patched document passes the same finalize gate
        that just rejected it. No stage failed and nothing was regenerated.
        """
        blocked = finalize(dict(approved_state))
        assert blocked["finalize_repair_pending"] is True
        assert route_after_finalize(blocked) == "N1_generate_draft"

        drafter = _Recorder(_edit_block(REAL_QUESTION, ANSWERED))
        revised = _revise(monkeypatch, blocked, drafter)

        assert len(drafter.calls) == 1
        assert revised["current_draft"] == blocked_draft.replace(
            REAL_QUESTION, ANSWERED, 1
        )

        repaired = dict(blocked)
        repaired.update(revised)
        done = finalize(repaired)

        assert done.get("error_message", "") == ""
        assert not done.get("finalize_repair_pending")
        assert Path(done["final_lld_path"]).is_file()
        assert route_after_finalize(done) == "END"

    def test_the_repair_preserves_everything_it_did_not_name(
        self, monkeypatch, approved_state, quiet_finalize, blocked_draft
    ):
        """357 of the fixture's 358 lines come through byte-identical."""
        blocked = finalize(dict(approved_state))
        revised = _revise(
            monkeypatch, blocked, _Recorder(_edit_block(REAL_QUESTION, ANSWERED))
        )

        before = blocked_draft.splitlines()
        after = revised["current_draft"].splitlines()
        assert len(before) == len(after) == 358
        differing = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        assert differing == [9]

    def test_an_injected_finalize_error_routes_the_same_way(
        self, monkeypatch, approved_state, quiet_finalize, draft_005
    ):
        """The issue's second reproduction: a failure unrelated to questions.

        The routing is a property of finalize's gate, not of the checkbox that
        happened to trip it, so an arbitrary validation error must take the
        identical edge.
        """
        state = dict(approved_state)
        state["current_draft"] = draft_005
        state["open_questions_status"] = "NONE"
        monkeypatch.setattr(
            fz, "validate_lld_final", lambda *a, **k: ["Unresolved TODO in table cell"]
        )

        blocked = finalize(state)

        assert blocked["finalize_repair_pending"] is True
        assert blocked["validation_errors"] == ["Unresolved TODO in table cell"]
        assert route_after_finalize(blocked) == "N1_generate_draft"


# ---------------------------------------------------------------------------
# Routing, not regeneration (acceptance 1)
# ---------------------------------------------------------------------------


class TestRoutesToRevision:
    def test_the_graph_carries_the_finalize_to_revision_edge(self):
        """The edge itself. Before #2233 this was an unconditional N5 -> END."""
        edges = {
            (e.source, e.target)
            for e in create_requirements_graph().compile().get_graph().edges
        }

        assert ("N5_finalize", "N1_generate_draft") in edges
        assert ("N5_finalize", "__end__") in edges

    def test_a_blocked_finalize_does_not_fail_the_stage(
        self, approved_state, quiet_finalize
    ):
        """error_message is the channel the orchestrator reads to retry.

        Leaving it empty is what stops `Stage 'lld' failed (attempt 1/3)` and
        the regeneration that followed it.
        """
        blocked = finalize(dict(approved_state))

        assert blocked.get("error_message", "") == ""
        assert "Unresolved open questions remain" in blocked["validation_errors"]

    def test_a_blocked_finalize_saves_nothing(self, approved_state, quiet_finalize):
        """No LLD on disk, no completion logged, no lineage moved."""
        blocked = finalize(dict(approved_state))

        assert not blocked.get("final_lld_path")
        assert not blocked.get("created_files")
        lld_dir = Path(approved_state["target_repo"]) / "docs" / "lld" / "active"
        assert not lld_dir.exists()

    def test_the_completion_log_does_not_fire_on_a_repair(
        self, monkeypatch, approved_state, quiet_finalize
    ):
        """A repair request is not a completed workflow.

        The completion log gates on error_message, which this path deliberately
        leaves empty, so without the early return it would record a blocked
        draft as a finished LLD.
        """
        logged: list[dict] = []
        monkeypatch.setattr(
            fz, "log_workflow_execution", lambda **kw: logged.append(kw)
        )

        finalize(dict(approved_state))

        assert logged == []

    def test_the_revision_takes_the_edit_script_path(
        self, monkeypatch, approved_state, quiet_finalize
    ):
        blocked = finalize(dict(approved_state))
        drafter = _Recorder(_edit_block(REAL_QUESTION, ANSWERED))

        _revise(monkeypatch, blocked, drafter)

        content = drafter.calls[0]["content"]
        assert "<<<<<<< SEARCH" in content
        assert "Do NOT rewrite it" in content

    def test_the_errors_arrive_as_feedback_naming_the_gate_that_spoke(
        self, monkeypatch, approved_state, quiet_finalize
    ):
        """The document already passed mechanical validation.

        Labelling finalize's errors as mechanical ones sends the model hunting
        for structural faults that are not there.
        """
        blocked = finalize(dict(approved_state))

        context = gd.build_revision_context(blocked)

        assert context.startswith("## FINALIZE VALIDATION ERRORS")
        assert "Unresolved open questions remain" in context
        assert "MECHANICAL VALIDATION ERRORS" not in context
        assert "ACTUAL REPOSITORY STRUCTURE" not in context

    def test_a_mechanical_failure_still_reads_as_mechanical(self, approved_state):
        """The shared channel did not swallow the older caller."""
        state = dict(approved_state)
        state["validation_errors"] = ["Critical: Section 11 missing from LLD"]

        context = gd.build_revision_context(state)

        assert context.startswith("## MECHANICAL VALIDATION ERRORS")

    def test_the_preservation_ratio_is_logged(
        self, monkeypatch, approved_state, quiet_finalize, capsys
    ):
        blocked = finalize(dict(approved_state))
        capsys.readouterr()

        _revise(
            monkeypatch, blocked, _Recorder(_edit_block(REAL_QUESTION, ANSWERED))
        )

        out = capsys.readouterr().out
        assert "[EDIT-SCRIPT] Applied 1 edit(s);" in out
        assert "of prior draft preserved byte-identical" in out

    def test_the_repair_request_is_consumed_by_the_revision(
        self, monkeypatch, approved_state, quiet_finalize
    ):
        """A stale flag would send every later finalize back to the drafter."""
        blocked = finalize(dict(approved_state))
        revised = _revise(
            monkeypatch, blocked, _Recorder(_edit_block(REAL_QUESTION, ANSWERED))
        )

        assert revised["finalize_repair_pending"] is False
        assert revised["validation_errors"] == []


# ---------------------------------------------------------------------------
# A repair that cannot be expressed as edits halts (acceptance 3)
# ---------------------------------------------------------------------------


class TestHaltsRatherThanRegenerating:
    def test_a_redrawn_document_is_refused_and_names_the_contract(
        self, monkeypatch, approved_state, quiet_finalize, draft_005
    ):
        """The drafter answers a repair with a whole document, as one did.

        That response carries no edit blocks, so it is not a revision at all.
        Nothing is saved and the halt says so.
        """
        blocked = finalize(dict(approved_state))
        drafter = _Recorder(draft_005)

        out = _revise(monkeypatch, blocked, drafter)

        assert "current_draft" not in out
        assert out["error_message"].startswith("[EDIT-SCRIPT]")
        assert "no well-formed SEARCH/REPLACE blocks" in out["error_message"]
        assert "no full-regeneration fallback" in out["error_message"]
        assert len(drafter.calls) == 1

    def test_the_halt_leaves_the_graph_rather_than_looping(
        self, monkeypatch, approved_state, quiet_finalize, draft_005
    ):
        blocked = finalize(dict(approved_state))
        out = _revise(monkeypatch, blocked, _Recorder(draft_005))

        state = dict(blocked)
        state.update(out)
        assert route_after_generate_draft(state) == "HALT"

    def test_an_unmatched_search_halts_too(
        self, monkeypatch, approved_state, quiet_finalize
    ):
        blocked = finalize(dict(approved_state))
        drafter = _Recorder(_edit_block("text that is not in the draft", "x"))

        out = _revise(monkeypatch, blocked, drafter)

        assert "SEARCH text not found" in out["error_message"]
        assert "current_draft" not in out


# ---------------------------------------------------------------------------
# The budget (acceptance 4)
# ---------------------------------------------------------------------------


class TestRepairBudget:
    def test_a_successful_repair_costs_the_stage_nothing(
        self, monkeypatch, approved_state, quiet_finalize
    ):
        """The orchestrator's retry budget is spent on failed stages only.

        run_lld_stage marks the stage `failed` when no artifact reaches disk,
        and that is what triggered the discard-and-regenerate. A repair that
        lands an LLD is a stage that passed on its first attempt.
        """
        blocked = finalize(dict(approved_state))
        revised = _revise(
            monkeypatch, blocked, _Recorder(_edit_block(REAL_QUESTION, ANSWERED))
        )
        repaired = dict(blocked)
        repaired.update(revised)

        done = finalize(repaired)

        assert done.get("error_message", "") == ""
        assert Path(done["final_lld_path"]).is_file()

    def test_each_repair_is_counted(self, approved_state, quiet_finalize):
        state = dict(approved_state)
        counts = []
        for _ in range(MAX_FINALIZE_REPAIRS):
            state = finalize(state)
            counts.append(state["finalize_repair_count"])
            assert state["finalize_repair_pending"] is True

        assert counts == [1, 2]

    def test_the_budget_stops_the_loop_and_names_why(
        self, approved_state, quiet_finalize
    ):
        """A repair loop that will not converge is a defect to diagnose."""
        state = dict(approved_state)
        for _ in range(MAX_FINALIZE_REPAIRS + 1):
            state = finalize(state)

        assert state["finalize_repair_pending"] is False
        assert state["error_message"].startswith("[FINALIZE]")
        assert "Unresolved open questions remain" in state["error_message"]
        assert "rather than regenerating" in state["error_message"]
        assert route_after_finalize(state) == "END"

    def test_the_budget_is_clamped_to_what_the_graph_can_carry(
        self, approved_state, quiet_finalize
    ):
        """A generous iteration cap does not buy more repairs.

        The clamp is not a preference. A third repair costs more super-steps
        than either caller allows, so raising the cap past it would trade the
        halt below for a GraphRecursionError that names nothing.
        """
        state = dict(approved_state)
        state["max_iterations"] = 10

        for _ in range(MAX_FINALIZE_REPAIRS):
            state = finalize(state)
            assert state["finalize_repair_pending"] is True

        state = finalize(state)
        assert state["finalize_repair_pending"] is False
        assert state["error_message"].startswith("[FINALIZE]")

    def test_the_budget_follows_the_workflow_iteration_cap(
        self, approved_state, quiet_finalize
    ):
        state = dict(approved_state)
        state["max_iterations"] = 1

        # finalize mutates the dict it is handed, so each call gets its own.
        first = dict(finalize(dict(state)))
        second = finalize(dict(first))

        assert first["finalize_repair_pending"] is True
        assert second["finalize_repair_pending"] is False
        assert second["error_message"].startswith("[FINALIZE]")

    def test_at_least_one_repair_is_always_allowed(
        self, approved_state, quiet_finalize
    ):
        """A cap of zero would silently restore the defect."""
        state = dict(approved_state)
        state["max_iterations"] = 0

        assert finalize(state)["finalize_repair_pending"] is True


# ---------------------------------------------------------------------------
# The repair loop fits the graph's step budget
# ---------------------------------------------------------------------------


class TestStepBudget:
    """The loop must reach its own halt, not a GraphRecursionError.

    LangGraph bounds a run by super-steps. The orchestrator's `run_lld_stage`
    passes no `recursion_limit`, so it gets LangGraph's default of 25;
    `tools/run_requirements_workflow.py` computes `(max_iterations * 4) + 10`,
    which is 22 at the default cap. Every repair round trip spends six of
    those, and nothing in the graph notices until it runs out.

    That is what MAX_FINALIZE_REPAIRS is for, and a comment asserting it would
    rot the first time a node is added to the loop. This measures it.
    """

    @staticmethod
    def _drive(monkeypatch, repairs: int, recursion_limit: int) -> int:
        """Run the real compiled graph with every model call stubbed out.

        Returns the number of super-steps consumed, or raises
        GraphRecursionError exactly as a live run would.
        """
        import assemblyzero.workflows.requirements.graph as gr

        blocked = {"n": 0}

        def passthrough(state):
            return {}

        def fake_review(state):
            return {
                "lld_status": "APPROVED",
                "open_questions_status": "NONE",
                "verdict_count": state.get("verdict_count", 0) + 1,
            }

        def fake_draft(state):
            return {
                "current_draft": "# doc\n\n## 1. A\n\nbody\n",
                "draft_count": state.get("draft_count", 0) + 1,
                "validation_errors": [],
                "finalize_repair_pending": False,
                "error_message": "",
            }

        def fake_finalize(state):
            if blocked["n"] < repairs:
                blocked["n"] += 1
                return {
                    "finalize_repair_pending": True,
                    "finalize_repair_count": blocked["n"],
                    "validation_errors": ["forced"],
                    "error_message": "",
                }
            return {"finalize_repair_pending": False, "final_lld_path": "x.md"}

        for name in (
            "load_input",
            "analyze_codebase",
            "analyze_requirements",
            "ponder_stibbons_node",
            "validate_lld_mechanical",
            "validate_test_plan_node",
            "human_gate_draft",
            "human_gate_verdict",
        ):
            monkeypatch.setattr(gr, name, passthrough)
        monkeypatch.setattr(gr, "review", fake_review)
        monkeypatch.setattr(gr, "generate_draft", fake_draft)
        monkeypatch.setattr(gr, "finalize", fake_finalize)

        app = gr.create_requirements_graph().compile()
        steps = 0
        for _ in app.stream(
            {
                "workflow_type": "lld",
                "config_gates_draft": False,
                "config_gates_verdict": False,
                "max_iterations": 3,
                "issue_number": 7,
                "target_repo": "repo",
                "audit_dir": "audit",
            },
            config={"recursion_limit": recursion_limit},
        ):
            steps += 1
        return steps

    def test_a_clean_run_costs_nine_steps(self, monkeypatch, capsys):
        assert self._drive(monkeypatch, repairs=0, recursion_limit=25) == 9
        capsys.readouterr()

    def test_each_repair_costs_six_more(self, monkeypatch, capsys):
        one = self._drive(monkeypatch, repairs=1, recursion_limit=25)
        two = self._drive(monkeypatch, repairs=2, recursion_limit=25)
        capsys.readouterr()

        assert (one, two) == (15, 21)

    @pytest.mark.parametrize("limit", [25, 22])
    def test_a_full_repair_budget_fits_both_callers(
        self, monkeypatch, capsys, limit
    ):
        """The binding property. Both real limits, the budget spent in full."""
        steps = self._drive(
            monkeypatch, repairs=MAX_FINALIZE_REPAIRS, recursion_limit=limit
        )
        capsys.readouterr()

        assert steps <= limit

    def test_one_repair_past_the_budget_is_what_the_clamp_prevents(
        self, monkeypatch, capsys
    ):
        """Mutation: without the clamp, the loop dies namelessly.

        This is the evidence that MAX_FINALIZE_REPAIRS is load-bearing rather
        than cautious. A third repair does not produce the halt message; it
        produces a GraphRecursionError.
        """
        from langgraph.errors import GraphRecursionError

        with pytest.raises(GraphRecursionError):
            self._drive(
                monkeypatch, repairs=MAX_FINALIZE_REPAIRS + 1, recursion_limit=25
            )
        capsys.readouterr()


# ---------------------------------------------------------------------------
# Scope: what the routing must not disturb
# ---------------------------------------------------------------------------


class TestScope:
    def test_a_clean_finalize_still_ends_the_workflow(
        self, monkeypatch, approved_state, quiet_finalize, draft_005
    ):
        state = dict(approved_state)
        state["current_draft"] = draft_005
        state["open_questions_status"] = "NONE"

        done = finalize(state)

        assert not done.get("finalize_repair_pending")
        assert Path(done["final_lld_path"]).is_file()
        assert route_after_finalize(done) == "END"

    def test_a_non_validation_finalize_error_still_ends_the_workflow(
        self, approved_state, quiet_finalize
    ):
        """Only the validation gate repairs. Everything else fails as before."""
        state = dict(approved_state)
        state["issue_number"] = 0

        out = finalize(state)

        assert out["error_message"] == "No issue number for LLD finalization"
        assert not out.get("finalize_repair_pending")
        assert route_after_finalize(out) == "END"

    def test_the_issue_workflow_never_asks_for_a_repair(
        self, monkeypatch, approved_state
    ):
        state = dict(approved_state)
        state["workflow_type"] = "issue"
        monkeypatch.setattr(
            fz, "_finalize_issue", lambda s: {"error_message": "", "issue_url": "u"}
        )
        monkeypatch.setattr(fz, "log_workflow_execution", lambda **kw: None)
        monkeypatch.setattr(fz, "_commit_and_push_files", lambda s: s)

        out = finalize(state)

        assert not out.get("finalize_repair_pending")
        assert route_after_finalize(out) == "END"

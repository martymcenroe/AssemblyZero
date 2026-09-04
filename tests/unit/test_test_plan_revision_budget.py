"""The test-plan revision loop runs, and the cap is what ends it (#2775).

`revise_test_plan` is node N1.5 of the testing workflow. When the reviewer at
N1 rejects a test plan, N1.5 asks a model to rewrite it and the graph loops
back to N1: `N1 -> N1.5 -> N1`. `MAX_REVISION_CYCLES` is how many times that
may happen.

**The defect.** The short-revision return recorded an `error_message`, and
since #2793 a recorded reason routes to HALT. `route_after_review` checks the
error before it checks anything else, so the run ended on the FIRST short
revision and never reached the branch that sends it back to N1.5. The comment
above that return said "increment count and let the router decide whether to
retry or END"; the router never decided. `MAX_REVISION_CYCLES = 2` was
unreachable from this site for as long as the site has existed.

**The fix.** Under the cap, record no reason. At the cap, record one that
names the budget. The row then judges `budget` rather than `model_output`,
under ruling 1 of #2723: what ends the run is the allowance running out, not
a verdict on what the drafter wrote.

Note on the arithmetic, stated rather than assumed: `MAX_REVISION_CYCLES` is
**2**, set by #1072. So a run gets two revision cycles, and the second short
one is the one that halts. These tests are written against the shipped cap.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.core.gate_registry import (
    ACTION_HALT,
    JUDGES_BUDGET,
    registry_by_key,
)
from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.workflows.testing.nodes.revise_test_plan import (
    MAX_REVISION_CYCLES,
    revise_test_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Two requirements, so a one-row table is short and a two-row table is not.
REQUIREMENTS = ["REQ-1 the widget adds", "REQ-2 the widget refuses None"]

SHORT_TABLE = (
    "| ID | Scenario | Type | Requirements |\n"
    "|---|---|---|---|\n"
    "| T001 | combine adds | unit | REQ-1 |\n"
)

FULL_TABLE = SHORT_TABLE + "| T002 | combine refuses None | unit | REQ-2 |\n"


class _Revisor:
    """A reviser that reads its answers off a script and counts its calls."""

    def __init__(self, tables: list[str]) -> None:
        self._tables = tables
        self.calls = 0

    def invoke(self, system_prompt: str, content: str) -> LLMCallResult:
        table = self._tables[min(self.calls, len(self._tables) - 1)]
        self.calls += 1
        return LLMCallResult(
            success=True,
            response=table,
            raw_response=table,
            error_message="",
            provider="gemini",
            model_used="test-double",
            duration_ms=0,
            attempts=1,
        )


def _install_revisor(monkeypatch, tables: list[str]) -> _Revisor:
    """Patch the provider factory `revise_test_plan` imports at call time."""
    revisor = _Revisor(tables)
    monkeypatch.setattr(
        "assemblyzero.core.llm_provider.get_provider",
        lambda *a, **k: revisor,
    )
    return revisor


def _state(revision_count: int) -> dict:
    return {
        "requirements": list(REQUIREMENTS),
        "lld_content": "# LLD\n",
        "gemini_feedback": "not every requirement is covered",
        "test_plan_revision_count": revision_count,
        "issue_number": 4242,
    }


class TestTheNodeItself:
    """What N1.5 hands back, at each point in the allowance."""

    def test_a_short_revision_under_the_cap_records_no_reason(self, monkeypatch):
        """The half the defect turned on.

        A recorded reason is a HALT (#2793). Under the cap there must not be
        one, or the loop this cap bounds can never run a second time.
        """
        _install_revisor(monkeypatch, [SHORT_TABLE])
        result = revise_test_plan(_state(0))

        assert result["test_plan_revision_count"] == 1
        assert result["error_message"] == "", (
            "a reason recorded under the cap routes to HALT, which is how "
            "MAX_REVISION_CYCLES became unreachable"
        )
        assert result["test_plan_section"] == SHORT_TABLE.strip(), (
            "the short table is still handed back, so N1 re-reviews the "
            "revision rather than the plan it replaced"
        )

    def test_a_short_revision_at_the_cap_names_the_budget(self, monkeypatch):
        _install_revisor(monkeypatch, [SHORT_TABLE])
        result = revise_test_plan(_state(MAX_REVISION_CYCLES - 1))

        assert result["test_plan_revision_count"] == MAX_REVISION_CYCLES
        message = result["error_message"]
        assert message.startswith("Test plan revision budget spent"), message
        assert str(MAX_REVISION_CYCLES) in message, (
            "the message must say how large the allowance was"
        )
        assert "1/2" in message, (
            "and how short the plan still is, so a reader knows which side "
            "to repair"
        )

    def test_a_full_revision_clears_the_blocked_state(self, monkeypatch):
        """The success path is unchanged; asserted so the fix cannot have
        bought the loop by breaking the exit from it."""
        _install_revisor(monkeypatch, [FULL_TABLE])
        result = revise_test_plan(_state(0))

        assert result["test_plan_status"] == "PENDING"
        assert result["error_message"] == ""
        assert len(result["test_scenarios"]) == len(REQUIREMENTS)


class TestAReasonRecordedAtN15SurvivesToTheRouter:
    """Why the N1.5 -> N1 edge had to become conditional (#2775).

    N1's BLOCKED return sets `error_message` to "" on purpose (#1490, so a
    blocked plan gets revised instead of ending the run). The edge out of
    N1.5 was unconditional, so N1 ran next and erased whatever reason N1.5
    had just recorded. `route_after_review` then saw no error at all.

    That made all THREE of N1.5's registered halt rows unreachable as halts,
    not only the one #2775 is about: a missing requirements list and a failed
    reviser call were erased the same way, and the run went on to spend its
    remaining revision cycles on a question that had already failed.
    """

    def test_a_recorded_reason_routes_to_halt(self):
        from assemblyzero.workflows.testing.graph import route_after_revision

        assert route_after_revision(
            {"error_message": "Test plan revision budget spent: ..."}
        ) == "HALT"

    def test_no_reason_still_goes_back_for_re_review(self):
        from assemblyzero.workflows.testing.graph import route_after_revision

        assert route_after_revision({"error_message": ""}) == "N1_review_test_plan"
        assert route_after_revision({}) == "N1_review_test_plan"

    def test_n1_still_clears_the_error_it_is_supposed_to_clear(self):
        """The behaviour the conditional edge works around is deliberate and
        must stay. If #1490's clear were removed instead, a BLOCKED plan
        would end the run and the revision loop would never fire at all."""
        source = (
            REPO_ROOT
            / "assemblyzero/workflows/testing/nodes/review_test_plan.py"
        ).read_text(encoding="utf-8")
        assert '"test_plan_status": "BLOCKED",' in source
        assert "#1490" in source, (
            "the reason N1 clears error_message is recorded at that return; "
            "if it has moved, re-read it before trusting this test"
        )


class TestTheRegistryRowMovedWithTheCode:
    def test_the_row_judges_the_budget_now(self):
        row = registry_by_key()["impl.test_plan_revision_incomplete"]
        assert row.judges == JUDGES_BUDGET, (
            "the site that is left fires only when the allowance is spent"
        )
        assert row.action == ACTION_HALT
        assert row.justified_by == "#2775"


class TestTheLoopRunsAndTheCapEndsIt:
    """The claim the issue is about, on the real compiled testing graph."""

    @pytest.fixture
    def roll(self, monkeypatch, tmp_path):
        """Roll the graph with a scripted reviser. Returns (final, revisor)."""

        def _run(tables: list[str]):
            import assemblyzero.workflows.testing.graph as g

            # The HALT node writes a real bundle; send it to tmp rather than
            # the user's home. The node itself is not stubbed -- the bundle
            # is what the cap is supposed to produce.
            monkeypatch.setattr(
                "assemblyzero.core.state_persistence.STATE_DIR", tmp_path
            )

            def fake_load(state):
                return {
                    "lld_content": "# LLD\n",
                    "spec_path": "spec.md",
                    "requirements": list(REQUIREMENTS),
                    "error_message": "",
                }

            def fake_review(state):
                """APPROVED once the plan has a row per requirement."""
                section = state.get("test_plan_section", "") or ""
                rows = [
                    line for line in section.splitlines()
                    if line.strip().startswith("| T")
                ]
                if len(rows) >= len(REQUIREMENTS):
                    return {
                        "test_plan_status": "APPROVED",
                        "gemini_feedback": "",
                        "error_message": "",
                    }
                return {
                    "test_plan_status": "BLOCKED",
                    "gemini_feedback": (
                        f"BLOCKING: {len(rows)}/{len(REQUIREMENTS)} "
                        f"requirements covered"
                    ),
                    "error_message": "",
                }

            def fake_scaffold(state):
                # A marker, so a run that got past the plan loop is
                # distinguishable from one the cap stopped.
                return {"error_message": "REACHED N2", "next_node": "end"}

            revisor = _install_revisor(monkeypatch, tables)
            monkeypatch.setattr(g, "load_lld", fake_load)
            monkeypatch.setattr(g, "review_test_plan", fake_review)
            monkeypatch.setattr(g, "scaffold_tests", fake_scaffold)

            app = g.build_testing_workflow().compile()
            final = app.invoke({
                "issue_number": 4242,
                "repo_root": str(tmp_path),
                "worktree_path": str(tmp_path),
                "audit_dir": "",
                "max_iterations": 5,
            })
            return final, revisor

        return _run

    def test_a_short_revision_no_longer_ends_the_run(self, roll):
        """Short on cycle 1, full on cycle 2: the run gets past the plan.

        Before #2775 this run ended inside cycle 1, holding a plan the
        reviser was about to fix on the next pass.
        """
        final, revisor = roll([SHORT_TABLE, FULL_TABLE])

        assert revisor.calls == 2, (
            f"the loop ran {revisor.calls} time(s); the second revision is "
            f"the one that was unreachable"
        )
        assert final.get("error_message") == "REACHED N2", final.get(
            "error_message"
        )

    def test_a_plan_that_stays_short_halts_at_the_cap(self, roll):
        final, revisor = roll([SHORT_TABLE])

        assert revisor.calls == MAX_REVISION_CYCLES, (
            f"the reviser was asked {revisor.calls} time(s); the allowance "
            f"is {MAX_REVISION_CYCLES}"
        )
        message = final.get("error_message", "")
        assert message.startswith("Test plan revision budget spent"), message

    def test_what_the_defect_actually_was(self, roll, monkeypatch):
        """The prior behaviour, reproduced rather than recalled.

        #2775 says the gate "halts on the first short revision". Rolled, it
        did not. Both of this PR's changes are monkeypatched back out --
        N1.5 returns the old dict, and the edge out of it is forced
        unconditional -- and the run is measured.

        What happens is worse than the issue describes and in a different
        way. N1 clears `error_message` (#1490) one node later, so the reason
        never reaches `route_after_review` at all. The loop DOES run its two
        cycles; it then falls out of the `revise` branch to `end`, with no
        reason and no bundle. The row named a halt that never fired, which
        is why boostgauge recorded zero kills for it in 180 runs and why the
        answer-key audit could never make it runnable.
        """
        import assemblyzero.workflows.testing.graph as g

        calls = {"n": 0}

        def prefix_revise(state):
            calls["n"] += 1
            return {
                "test_plan_revision_count": (
                    state.get("test_plan_revision_count", 0) + 1
                ),
                "test_plan_section": SHORT_TABLE.strip(),
                "error_message": (
                    f"Revised plan covers only 1/{len(REQUIREMENTS)} "
                    f"requirements -- needs another revision cycle"
                ),
            }

        monkeypatch.setattr(g, "revise_test_plan", prefix_revise)
        monkeypatch.setattr(
            g, "route_after_revision", lambda state: "N1_review_test_plan"
        )
        final, _ = roll([SHORT_TABLE])

        assert calls["n"] == MAX_REVISION_CYCLES, (
            "the loop was not cut short on the first revision -- it ran the "
            "full allowance and the reason was simply erased each time"
        )
        assert final.get("error_message") == "", (
            "N1 cleared the reason N1.5 recorded, so nothing downstream "
            "could see it"
        )
        assert not final.get("recovery_plan_path"), (
            "and the run ended with no bundle at all"
        )

    def test_the_cap_leaves_a_bundle(self, roll):
        """A budget halt must still hand back a recovery plan and a
        snapshot; a run that stops with nothing to resume from is the
        failure #2197 and #2570 were about."""
        final, _ = roll([SHORT_TABLE])

        assert final.get("state_snapshot_path"), final.keys()
        assert final.get("recovery_plan_path"), final.keys()

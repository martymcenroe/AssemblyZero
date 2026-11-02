"""A revision whose blocks miss the draft is re-asked once, then halts (#4503).

On a real run on 2026-11-01 the validators sent back a draft with one uncovered
requirement, and the revision's second SEARCH block missed the draft by a few
characters. The run halted at iteration 5 with no re-ask, classified `unknown`,
and told the reader to relaunch to resume from this stage, which no command
does. The relaunch passed cleanly: the model could have fixed it itself.
"""

from __future__ import annotations

import shlex
from importlib import import_module
from pathlib import Path

import pytest

from assemblyzero.core.halt_node import classify_error
from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.core.recovery_plan import build_resume_command, generate_recovery_plan

gd = import_module("assemblyzero.workflows.requirements.nodes.generate_draft")

ROOT = Path(__file__).resolve().parents[2]
DRAFT = (ROOT / "tests" / "fixtures" / "lld_revision" / "boostgauge-7-003-draft.md").read_text(
    encoding="utf-8"
)
#: A line the fixture draft carries once, in its section 6.
ANCHOR = "## 6. Diagram"


def _result(response: str) -> LLMCallResult:
    return LLMCallResult(
        success=True, response=response, raw_response=response, error_message=None,
        provider="fake", model_used="fake-model", duration_ms=1, attempts=1,
    )


def _edit_block(search: str, replace: str) -> str:
    return f"<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE"


#: A SEARCH that misses the draft by a few characters, as on the real run.
NEAR_MISS = _edit_block(ANCHOR.replace("Diagram", "Diagrams"), f"{ANCHOR}\n\nfixed")
GOOD = _edit_block(ANCHOR, f"{ANCHOR}\n\nfixed")


class _Recorder:
    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def invoke(self, **kwargs) -> LLMCallResult:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("the drafter was asked more often than the test allows")
        return _result(self._responses.pop(0))


@pytest.fixture
def run(monkeypatch, tmp_path):
    audit = tmp_path / "audit"
    audit.mkdir()
    (tmp_path / "repo").mkdir()
    state = {
        "workflow_type": "lld",
        "assemblyzero_root": str(ROOT),
        "target_repo": str(tmp_path / "repo"),
        "audit_dir": str(audit),
        "config_mock_mode": False,
        "config_drafter": "fake:model",
        "issue_number": 7,
        "issue_title": "config persistence",
        "issue_body": "the issue body",
        "current_draft": DRAFT,
        "verdict_history": ["REVISE: section 6 needs a sentence"],
        "draft_count": 4,
        "iteration_count": 4,
    }

    def _run(*responses: str):
        drafter = _Recorder(*responses)
        monkeypatch.setattr(gd, "get_provider", lambda spec, *a, **k: drafter)
        return gd.generate_draft(state), drafter

    return _run


class TestTheReAsk:
    def test_t1_a_near_miss_is_re_asked_and_the_second_answer_applies(self, run):
        """T1 (R1): the second prompt names the failed block and shows its section."""
        out, drafter = run(NEAR_MISS, GOOD)

        assert not out.get("error_message")
        assert "fixed" in out["current_draft"]
        assert len(drafter.calls) == 2
        second = drafter.calls[1]["content"]
        assert "block 1" in second
        assert "SEARCH text not found" in second
        section = DRAFT[DRAFT.index(ANCHOR):].split("\n## ", 1)[0]
        assert section in second

    def test_t2_two_failures_halt_after_exactly_two_calls(self, run):
        """T2 (R1, R2): the re-ask is one call, inside the same iteration."""
        out, drafter = run(NEAR_MISS, NEAR_MISS)

        assert len(drafter.calls) == 2
        assert "[EDIT-SCRIPT]" in out["error_message"]
        assert "iteration_count" not in out

    def test_t3_no_path_redraws_the_document(self, run):
        """T3 (R3): both calls are edit-script calls; neither asks for an LLD."""
        _, drafter = run(NEAR_MISS, NEAR_MISS)

        for call in drafter.calls:
            assert "precision patch engine" in call["system_prompt"]
            assert "Do NOT rewrite it" in call["content"]

    def test_the_re_ask_still_counts_as_one_iteration(self, run):
        out, _ = run(NEAR_MISS, GOOD)

        assert out["iteration_count"] == 5


class TestTheHalt:
    def test_t4_the_halt_has_a_class_of_its_own(self, run):
        """T4 (R4): it was `unknown`."""
        out, _ = run(NEAR_MISS, NEAR_MISS)

        assert classify_error(out["error_message"]) == "edit_script_rejected"

    def test_t4_the_halt_says_what_a_relaunch_does(self, run):
        """It said "Relaunch to resume from this stage", which nothing does."""
        out, _ = run(NEAR_MISS, NEAR_MISS)

        assert "resume from this stage" not in out["error_message"]
        assert "drafts the LLD again from the start" in out["error_message"]

    def test_t4_the_printed_command_does_what_the_halt_says(
        self, run, tmp_path, monkeypatch,
    ):
        """The plan's command, through the tool's own parser and its
        regeneration check: it asks, and on YES it moves the lineage aside and
        drafts again from the start."""
        from tools import run_requirements_workflow as tool

        out, _ = run(NEAR_MISS, NEAR_MISS)
        repo = tmp_path / "target"
        lineage = repo / "docs" / "lineage" / "active" / "7-lld"
        lineage.mkdir(parents=True)
        (lineage / "001-issue.md").write_text("issue\n", encoding="utf-8")
        (lineage / "002-draft.md").write_text(DRAFT, encoding="utf-8")
        (lineage / "003-verdict.md").write_text("REVISE\n", encoding="utf-8")
        plan = generate_recovery_plan(
            issue_number=7, workflow="requirements", stage="N1_draft_iter5",
            error_type=classify_error(out["error_message"]),
            error_message=out["error_message"], state={"target_repo": str(repo)},
        )
        assert plan.resume_command == build_resume_command(
            "requirements", 7, {"target_repo": str(repo)},
        )
        assert "drafts the LLD again from the start" in plan.recommendation

        args = tool.parse_args(shlex.split(plan.resume_command)[4:])
        monkeypatch.delenv("ASSEMBLYZERO_TEST_MODE", raising=False)
        monkeypatch.setattr("builtins.input", lambda prompt: "YES")

        assert tool.check_and_shift_existing_lld(args.issue, Path(args.repo), args.yes)
        assert not lineage.exists()
        assert (repo / "docs" / "lineage" / "active" / "7-lld-n1" / "002-draft.md").is_file()

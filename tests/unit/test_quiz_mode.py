"""Quiz narration mode (#2161): the live roll as exam material.

Questions are GENERATED from the atlas, so the drift guard keeps the exam
honest for free. The display pauses; the roll never does; the logs are the
buffer.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402

from assemblyzero.workflows.requirements.atlas import (  # noqa: E402
    ATLAS as REQ_ATLAS,
    TOTAL_STEPS as REQ_TOTAL,
)


def _successor_titles(node_id: str) -> set:
    return {
        REQ_ATLAS[s]["title"]
        for s in REQ_ATLAS[node_id]["successors"]
        if s in REQ_ATLAS
    }


class TestQuestionGeneration:
    def test_the_correct_option_is_a_real_successor(self):
        quiz = sr._QuizMaster(seed=7)
        entry = REQ_ATLAS["N1_5_validate_mechanical"]
        q = quiz.build(REQ_TOTAL, entry["title"])
        options = dict(q["options"])
        assert options[q["answer"]] in _successor_titles("N1_5_validate_mechanical")

    def test_every_distractor_is_a_real_title_but_not_a_successor(self):
        quiz = sr._QuizMaster(seed=7)
        entry = REQ_ATLAS["N1_5_validate_mechanical"]
        q = quiz.build(REQ_TOTAL, entry["title"])
        titles = {e["title"] for e in REQ_ATLAS.values()}
        successors = _successor_titles("N1_5_validate_mechanical")
        for letter, text in q["options"]:
            assert text in titles
            if letter != q["answer"]:
                assert text not in successors

    def test_four_options_lettered_a_to_d(self):
        quiz = sr._QuizMaster(seed=7)
        q = quiz.build(REQ_TOTAL, REQ_ATLAS["N3_review"]["title"])
        assert [letter for letter, _ in q["options"]] == ["a", "b", "c", "d"]

    def test_the_draw_is_stable_under_a_seed(self):
        a = sr._QuizMaster(seed=42).build(REQ_TOTAL, "generate draft")
        b = sr._QuizMaster(seed=42).build(REQ_TOTAL, "generate draft")
        assert a == b

    def test_an_unknown_title_or_total_yields_no_question(self):
        quiz = sr._QuizMaster(seed=7)
        assert quiz.build(99, "generate draft") is None
        assert quiz.build(REQ_TOTAL, "mystery step") is None

    def test_questions_come_from_the_last_node_line_in_a_chunk(self):
        quiz = sr._QuizMaster(seed=7)
        out = (
            "NODE [4/11] generate draft -- The drafter model writes it.\n"
            "detail\n"
            "NODE [6/11] mechanical validation -- Check the structure.\n"
        )
        q = quiz.question_from_output(out)
        assert "mechanical validation" in q["prompt"]


class TestGrading:
    def test_correct_answers_tally_and_teach(self, capsys):
        quiz = sr._QuizMaster(seed=7)
        q = quiz.build(REQ_TOTAL, "adversarial review")
        quiz.grade(q, q["answer"])
        out = capsys.readouterr().out
        assert "Correct." in out
        assert "  | " in out, "teach text reinforces either way"
        assert quiz.tally() == "Quiz: 1/1 correct."

    def test_wrong_answers_reveal_the_letter_without_shaming(self, capsys):
        quiz = sr._QuizMaster(seed=7)
        q = quiz.build(REQ_TOTAL, "adversarial review")
        wrong = next(
            letter for letter, _ in q["options"] if letter != q["answer"]
        )
        quiz.grade(q, wrong)
        out = capsys.readouterr().out
        assert f"The answer was ({q['answer']})." in out
        assert quiz.tally() == "Quiz: 0/1 correct."

    def test_skips_never_count(self, capsys):
        quiz = sr._QuizMaster(seed=7)
        q = quiz.build(REQ_TOTAL, "adversarial review")
        quiz.grade(q, "skip")
        assert quiz.tally() == "Quiz: no questions answered."


class TestTheHold:
    def test_a_finished_roll_releases_the_question(self, capsys):
        quiz = sr._QuizMaster(seed=7)
        q = quiz.build(REQ_TOTAL, "generate draft")
        with patch.object(sr, "_read_quiz_key", lambda: None), \
                patch.object(sr.time, "sleep", lambda s: None):
            key = sr._quiz_hold(q, status_fn=lambda: "Ready", beat_fn=lambda: "")
        assert key is None
        assert "releasing the question" in capsys.readouterr().out

    def test_an_answer_key_returns_promptly(self, capsys):
        quiz = sr._QuizMaster(seed=7)
        q = quiz.build(REQ_TOTAL, "generate draft")
        with patch.object(sr, "_read_quiz_key", lambda: "b"):
            assert sr._quiz_hold(
                q, status_fn=lambda: "Running", beat_fn=lambda: ""
            ) == "b"


class TestFollowIntegration:
    def test_a_node_line_in_the_roll_log_asks_and_tallies(self, tmp_path, capsys):
        runs = tmp_path / "runs"
        runs.mkdir()
        (runs / "detached-launcher.log").write_bytes(b"")
        roll = runs / "run-issue1-101010.log"
        roll.write_bytes(b"")

        def _flip():
            with roll.open("ab") as fh:
                fh.write(
                    b"NODE [4/11] generate draft -- "
                    b"The drafter model writes the document.\n"
                )
                # #2510: a fresh log with no closing banner is what an ORPHANED
                # roll looks like, and the follower now keeps watching one.
                # This test is about the quiz, so the roll finishes properly.
                fh.write(b"[ORCHESTRATOR] All stages passed.\n")
            return "Ready"

        statuses = iter([lambda: "Running", _flip])
        held = {}

        def _hold(question, **_kw):
            held["q"] = question
            return question["answer"]

        with patch.object(sr, "_task_status", lambda: next(statuses)()), \
                patch.object(sr, "_task_last_result", lambda: 0), \
                patch.object(sr, "_quiz_hold", _hold), \
                patch.object(sr, "_poll_view_keys", lambda v: None), \
                patch.object(sr.time, "sleep", lambda s: None):
            sr.follow_roll(runs, level="quiz")

        out = capsys.readouterr().out
        assert "generate draft" in held["q"]["prompt"]
        assert "Correct." in out
        assert "Quiz: 1/1 correct." in out

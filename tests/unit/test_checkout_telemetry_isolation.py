"""The test tiers never write into the checkout's telemetry logs (#4161).

Each test sends one writer's record at the checkout itself, the way a node run
from the checkout does, and checks that the checkout's log did not change and
that the record landed under the test's own directory. The session guard in
``tests/conftest.py`` is the other half: it fails the whole run if any of the
three logs appeared or changed while it ran.
"""
from __future__ import annotations

from tests.checkout_telemetry_guard import CHECKOUT, GUARDED_FILES
from tests.home_state_guard import changes, snapshot

SINK = "checkout-telemetry"


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_t2_a_stage_record_aimed_at_the_checkout_lands_in_tmp(tmp_path):
    from assemblyzero.speedrun import convergence

    before = snapshot(GUARDED_FILES)
    assert convergence.record_stage_enter(CHECKOUT, "lld", 1, 3, run_tag="t4161")

    assert changes(before, snapshot(GUARDED_FILES)) == []
    [line] = _lines(convergence.records_path(tmp_path / SINK))
    assert '"run_tag": "t4161"' in line


def test_t2_a_prompt_failure_aimed_at_the_checkout_lands_in_tmp(tmp_path):
    from assemblyzero.speedrun import prompt_telemetry

    before = snapshot(GUARDED_FILES)
    record = prompt_telemetry.record_failure(
        CHECKOUT, stage="lld", check="test-plan", detail="t4161 detail"
    )

    assert record is not None
    assert changes(before, snapshot(GUARDED_FILES)) == []
    [line] = _lines(prompt_telemetry.telemetry_path(tmp_path / SINK))
    assert "t4161 detail" in line


def test_t2_a_hallucination_check_aimed_at_the_checkout_lands_in_tmp(tmp_path):
    import importlib

    from assemblyzero.workflows.telemetry import hallucination_log

    validate_completeness = importlib.import_module(
        "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
    )

    event = hallucination_log.build_hallucination_event(
        repo="t4161", issue=4161, artifact="spec", iteration=1,
        symbols_checked=0, flagged={}, skipped=True,
    )
    before = snapshot(GUARDED_FILES)
    # The completeness node's own binding, which is what a real run calls.
    validate_completeness.record_hallucination_event(event, None, CHECKOUT)

    assert changes(before, snapshot(GUARDED_FILES)) == []
    [line] = _lines(tmp_path / SINK / hallucination_log.JSONL_RELATIVE_PATH)
    assert '"repo": "t4161"' in line


def test_a_record_sent_to_a_test_directory_stays_there(tmp_path):
    """Only writes aimed at the checkout move."""
    from assemblyzero.speedrun import convergence

    assert convergence.record_stage_enter(tmp_path, "lld", 1, 3, run_tag="mine")

    assert len(_lines(convergence.records_path(tmp_path))) == 1
    assert not (tmp_path / SINK).exists()


def test_t1_the_session_guard_watches_the_paths_a_real_run_writes():
    """The guarded files are exactly where the unredirected writers point."""
    from assemblyzero.speedrun import convergence, prompt_telemetry
    from assemblyzero.workflows.telemetry import hallucination_log

    real = {
        CHECKOUT / "data" / "speedrun" / "telemetry" / convergence.RECORDS_FILENAME,
        CHECKOUT / prompt_telemetry.TELEMETRY_REL / prompt_telemetry.FAILURES_FILENAME,
        CHECKOUT / hallucination_log.JSONL_RELATIVE_PATH,
    }
    assert set(GUARDED_FILES) == real

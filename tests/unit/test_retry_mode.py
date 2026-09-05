"""Acceptance tests for retry classification and clean-slate regeneration (#1941).

The five tests named in the issue body are the acceptance criteria.

The shape being prevented is `run11b-issue4-234552` attempt 2: every generated
file logged `Skipped (already exists)`, the stage resumed attempt 1's artifacts
verbatim, and reproduced its exact outcome -- 50/50 tests, 86.0% coverage, the
same stagnation halt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from assemblyzero.core.retry_mode import (  # noqa: E402
    REGENERATED,
    RESUMED,
    is_regeneration,
    retry_mode_for,
)
from assemblyzero.workflows.testing.nodes.implementation.orchestrator import (  # noqa: E402
    _should_skip_existing_file,
)


# --- "a transient failure takes the resume path and shows RESUMED" -------


def test_transient_failure_resumes():
    assert retry_mode_for({"transient": True}) == RESUMED
    assert not is_regeneration(RESUMED)


def test_transient_resume_reuses_prior_artifacts(tmp_path):
    target = tmp_path / "generated.py"
    target.write_text("from attempt one\n", encoding="utf-8")

    skip = _should_skip_existing_file(
        "Add", target, iteration_count=0, regenerate=is_regeneration(RESUMED)
    )

    assert skip is True, "a capacity storm must not cost the paid work again"


# --- "a deterministic failure regenerates and shows REGENERATED" ---------


def test_deterministic_failure_regenerates():
    assert retry_mode_for({"transient": False}) == REGENERATED
    assert is_regeneration(REGENERATED)


def test_regeneration_does_not_consult_the_skip_path(tmp_path):
    target = tmp_path / "generated.py"
    target.write_text("from attempt one\n", encoding="utf-8")

    skip = _should_skip_existing_file(
        "Add", target, iteration_count=0, regenerate=True
    )

    assert skip is False, (
        "the previous attempt's output is the thing being discarded; "
        "'already on disk' is the reason to replace it, not to keep it"
    )


def test_regeneration_overrides_every_other_reason_to_skip(tmp_path):
    """Whatever else would have caused a skip, regeneration wins."""
    target = tmp_path / "generated.py"
    target.write_text("content\n", encoding="utf-8")

    for iteration in (0, 1, 5):
        assert _should_skip_existing_file(
            "Add", target, iteration_count=iteration, regenerate=True
        ) is False


# --- "no classification is treated as deterministic and regenerates" -----


@pytest.mark.parametrize(
    "stage_result",
    [
        {},
        {"transient": None},
        {"status": "failed"},
        {"transient": "yes"},      # malformed, not a bool
        {"transient": 1},          # truthy but not True
        None,
        "not a dict",
    ],
)
def test_unclassified_failure_regenerates(stage_result):
    assert retry_mode_for(stage_result) == REGENERATED, (
        "replaying an attempt that cannot succeed costs a full stage and "
        "produces no new information"
    )


def test_only_a_real_boolean_true_resumes():
    # The eligibility default (#1463) treats an unmarked failure as transient so
    # ordinary flakes still retry. This asks a different question -- may the next
    # attempt reuse the last one's output -- and the safe answer is the opposite.
    assert retry_mode_for({"transient": True}) == RESUMED
    assert retry_mode_for({}) == REGENERATED


# --- "the run11b shape cannot occur without the table marking it RESUMED" ---


def test_the_run11b_shape_is_legible_in_the_stage_table():
    import orchestrate

    replayed = {
        "error_message": "Stagnation: 50/50 tests, 86.0% coverage, unchanged",
        "attempts": 2,
        "duration_seconds": 754,
        "retry_mode": RESUMED,
    }
    rendered = orchestrate.format_error_message("impl", replayed)

    assert "RESUMED" in rendered, (
        "an identical-outcome replay must be visible without reading transcripts"
    )
    assert "Attempts: 2" in rendered


def test_a_regenerated_attempt_says_so_in_the_stage_table():
    import orchestrate

    rendered = orchestrate.format_error_message("impl", {
        "error_message": "still failing", "attempts": 3,
        "duration_seconds": 100, "retry_mode": REGENERATED,
    })
    assert "REGENERATED" in rendered


def test_a_first_attempt_claims_neither():
    import orchestrate

    rendered = orchestrate.format_error_message("impl", {
        "error_message": "failed", "attempts": 1, "duration_seconds": 10,
    })
    assert "RESUMED" not in rendered and "REGENERATED" not in rendered


# --- "regeneration produces different content when the drafter differs" --


def test_regeneration_lets_new_drafter_output_replace_the_old(tmp_path):
    """The skip path is what pinned the old bytes; without it, new output lands."""
    target = tmp_path / "generated.py"
    target.write_text("value = 1  # attempt one\n", encoding="utf-8")

    assert _should_skip_existing_file(
        "Add", target, iteration_count=0, regenerate=True
    ) is False

    # With the skip bypassed, the runner writes whatever the drafter returned.
    target.write_text("value = 2  # attempt two\n", encoding="utf-8")
    assert target.read_text(encoding="utf-8") != "value = 1  # attempt one\n"


def test_resume_path_is_unchanged_for_first_attempts(tmp_path):
    """No retry mode set means nothing to reuse; existing behaviour stands."""
    target = tmp_path / "generated.py"
    target.write_text("x\n", encoding="utf-8")

    assert is_regeneration(None) is False
    assert is_regeneration("") is False
    assert _should_skip_existing_file(
        "Add", target, iteration_count=0, regenerate=is_regeneration(None)
    ) is True


# --- wiring ---------------------------------------------------------------


def test_graph_records_the_mode_and_threads_it_to_the_next_attempt():
    """The mode must reach the next attempt's state, not just be printed."""
    import inspect

    from assemblyzero.workflows.orchestrator import graph

    source = inspect.getsource(graph._run_stage_node)
    assert "retry_mode_for(stage_result)" in source
    assert 'stage_result["retry_mode"] = mode' in source
    assert 'last_state["retry_mode"] = mode' in source, (
        "without this the next attempt never learns it must regenerate"
    )


def test_impl_stage_passes_retry_mode_to_the_sub_workflow():
    """The mode the graph recorded must reach the sub-workflow's payload.

    #2845 gave this line a second source -- a worktree recovered from a
    preserved attempt enters as RESUMED whatever the state says -- so the
    assertion is on the two parts that must survive any such addition: the
    payload carries the key, and the state's own mode is still what it falls
    back to. Matching the whole expression made an ADDITION look like a
    removal. The override itself is tested behaviourally, against the payload
    the sub-workflow actually receives, in
    `test_impl_resume_from_preserved_attempt.py`.
    """
    import inspect

    from assemblyzero.workflows.orchestrator import stages

    source = inspect.getsource(stages.run_impl_stage)
    assert '"retry_mode":' in source
    assert 'state.get("retry_mode", "")' in source, (
        "the state's mode must remain the fallback, or an ordinary stage "
        "retry stops regenerating"
    )

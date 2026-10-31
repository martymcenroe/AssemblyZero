"""The test tiers never write into the checkout's telemetry logs (#4161).

Each test sends one writer's record at the checkout itself, the way a node run
from the checkout does, and checks that the checkout's log did not change and
that the record landed under the test's own directory. The session guard in
``tests/conftest.py`` is the other half: it fails the whole run if any of the
three logs appeared or changed while it ran.

#4202: a writer handed a relative root (``"."``, which three nodes pass when a
state names no repository) writes under the directory pytest started in. The
tests below that carry the number check that directory is guarded too, and
that a pytest started in an empty directory leaves no ``data/`` there.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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
    """The guarded files are exactly where the unredirected writers point,
    under the checkout and under the directory the run started in (#4202)."""
    from assemblyzero.speedrun import convergence, prompt_telemetry
    from assemblyzero.workflows.telemetry import hallucination_log
    from tests.checkout_telemetry_guard import START_DIR

    real = {
        root / relative
        for root in (CHECKOUT, START_DIR)
        for relative in (
            Path("data") / "speedrun" / "telemetry" / convergence.RECORDS_FILENAME,
            prompt_telemetry.TELEMETRY_REL / prompt_telemetry.FAILURES_FILENAME,
            hallucination_log.JSONL_RELATIVE_PATH,
            _cascade_default_as_written(),
        )
    }
    assert set(GUARDED_FILES) == real


# -- #4249: the cascade config's default path -------------------------------


def _cascade_default_as_written() -> Path:
    """``_DEFAULT_CONFIG_PATH`` as the module defines it, before the redirect.

    The autouse fixture has replaced the attribute by the time a test runs, so
    the module is loaded afresh, under another name, to read the constant.
    """
    import importlib.util

    from assemblyzero.hooks import cascade_patterns

    spec = importlib.util.spec_from_file_location(
        "_cascade_patterns_as_written", cascade_patterns.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    return fresh._DEFAULT_CONFIG_PATH


def _stat(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def test_4249_t1_patterns_loaded_with_no_path_come_from_tmp(tmp_path):
    """T1: a test that loads patterns with no path reads its own directory's
    config, and the checkout's tracked copy keeps its size and mtime.

    Fails before #4249: the default path was relative to the working
    directory, so the load read the checkout's copy (no patterns) instead of
    the one this test placed.
    """
    import json

    from assemblyzero.hooks import cascade_patterns

    checkout_copy = CHECKOUT / _cascade_default_as_written()
    before = _stat(checkout_copy)
    mine = tmp_path / SINK / "data" / "unleashed" / "cascade_block_patterns.json"
    mine.parent.mkdir(parents=True)
    mine.write_text(json.dumps({"enabled": True, "patterns": [{
        "id": "CP-4249", "category": "scope_expansion", "regex": "t4249",
        "description": "this test's own pattern", "risk_weight": 0.5,
    }]}), encoding="utf-8")

    loaded = cascade_patterns.load_user_patterns()

    assert [p["id"] for p in loaded] == ["CP-4249"]
    assert _stat(checkout_copy) == before


def test_4249_t2_the_session_guard_watches_the_checkouts_cascade_config():
    """T2: the guarded paths include the tracked config, at the path the
    module reads it from."""
    assert CHECKOUT / _cascade_default_as_written() in GUARDED_FILES


def test_4249_loading_and_detecting_write_no_config(tmp_path):
    """Kept behaviour, pinned: nothing in the cascade code writes the config.

    #4249 said loading patterns with no path wrote a default config. It does
    not: ``load_user_patterns`` reads only, and the 4:37 PM modification time
    it cited was the worktree's creation by ``git worktree add``. With the
    default path pointed here, a writer added later would leave a file here.
    """
    from assemblyzero.hooks import cascade_patterns
    from assemblyzero.hooks.cascade_detector import detect_cascade_risk

    checkout_copy = CHECKOUT / _cascade_default_as_written()
    before = _stat(checkout_copy)

    assert cascade_patterns.load_user_patterns() == []
    detect_cascade_risk("Should I continue with the next issue?")

    assert not (tmp_path / SINK / "data" / "unleashed").exists()
    assert _stat(checkout_copy) == before


# -- #4202: a relative root is the directory the run started in --------------


def _write_through_every_writer(root, sink_root):
    """One record through each of the three writers, at ``root``, and the
    lines each left under ``sink_root``'s copy of its log."""
    import importlib

    from assemblyzero.speedrun import convergence, prompt_telemetry
    from assemblyzero.workflows.telemetry import hallucination_log

    validate_completeness = importlib.import_module(
        "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
    )
    assert convergence.record_stage_enter(root, "lld", 1, 3, run_tag="t4202")
    assert prompt_telemetry.record_failure(
        root, stage="lld", check="test-plan", detail="t4202 detail"
    ) is not None
    event = hallucination_log.build_hallucination_event(
        repo="t4202", issue=4202, artifact="spec", iteration=1,
        symbols_checked=0, flagged={}, skipped=True,
    )
    validate_completeness.record_hallucination_event(event, None, Path(root))
    return [
        _lines(convergence.records_path(sink_root)),
        _lines(prompt_telemetry.telemetry_path(sink_root)),
        _lines(sink_root / hallucination_log.JSONL_RELATIVE_PATH),
    ]


def test_4202_a_record_aimed_at_the_start_directory_lands_in_tmp(tmp_path, monkeypatch):
    """A run started outside the checkout: "." is that directory, and a write
    there lands under the test's own directory instead.

    Fails before #4202: the redirect knew only the checkout, so the three logs
    appeared under ``started-here/data/``.
    """
    from tests import checkout_telemetry_guard

    started_here = tmp_path / "started-here"
    started_here.mkdir()
    monkeypatch.setattr(
        checkout_telemetry_guard, "START_DIR", started_here.resolve(), raising=False
    )
    monkeypatch.chdir(started_here)

    stage, failure, hallucination = _write_through_every_writer(".", tmp_path / SINK)

    assert not (started_here / "data").exists(), sorted(
        str(p.relative_to(started_here)) for p in started_here.rglob("*")
    )
    assert '"run_tag": "t4202"' in stage[0]
    assert "t4202 detail" in failure[0]
    assert '"repo": "t4202"' in hallucination[0]


def test_4202_a_test_that_moved_into_its_own_directory_keeps_its_writes(tmp_path, monkeypatch):
    """Only the start directory itself moves: "." after a chdir into tmp_path
    is the test's, and its records stay there."""
    from assemblyzero.speedrun import prompt_telemetry

    monkeypatch.chdir(tmp_path)
    assert prompt_telemetry.record_failure(
        ".", stage="lld", check="test-plan", detail="mine"
    ) is not None

    assert len(_lines(prompt_telemetry.telemetry_path(tmp_path))) == 1
    assert not (tmp_path / SINK).exists()


def test_4202_probe_every_writer_aimed_at_the_working_directory(tmp_path):
    """The probe the empty-directory run below executes in a child pytest.

    In this tier it runs from wherever the tier started; the writers are
    handed "." exactly as the three nodes hand it when a state names no
    repository, and every record must land under this test's directory.
    """
    stage, failure, hallucination = _write_through_every_writer(".", tmp_path / SINK)

    assert len(stage) == len(failure) == len(hallucination) == 1


def test_4202_t1_a_run_from_an_empty_directory_leaves_no_data_there(tmp_path):
    """T1 (R2): pytest started in an empty directory, running the probe that
    sends every writer's record at ".", leaves no ``data/`` there.

    Fails before #4202: the child's prompt-failure, stage and hallucination
    logs appeared under the empty directory's ``data/``, as a run started from
    another repository's checkout left them in that checkout.
    """
    empty = tmp_path / "empty"
    empty.mkdir()
    probe = (
        f"{Path(__file__).resolve()}"
        "::test_4202_probe_every_writer_aimed_at_the_working_directory"
    )

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", probe],
        cwd=empty, capture_output=True, text=True, timeout=600,
        check=False,  # the exit code is asserted below, with the child's output
    )

    written = sorted(str(p.relative_to(empty)) for p in empty.rglob("*"))
    assert not (empty / "data").exists(), written
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]

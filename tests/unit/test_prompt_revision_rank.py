"""Acceptance tests for cost-ranked prompt revision (#2075).

The five tests named in the issue body are the acceptance criteria. The rule
that matters most is that `duration-unknown` is never treated as zero cost —
that would sort the most expensive unmeasured failure to the bottom, which is
the exact failure the ranking exists to surface.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from assemblyzero.speedrun.prompt_ranking import (  # noqa: E402
    RUNS_CSV_REL,
    TELEMETRY_REL,
    UNKNOWN_DURATION,
    duration_for,
    load_durations,
    load_telemetry,
    rank,
    render,
)

TEMPLATE = Path(__file__).resolve().parents[2] / "docs/templates/0102-feature-lld-template.md"
PROCEDURE = (
    Path(__file__).resolve().parents[2]
    / "docs/standards/0025-prompt-revision-from-telemetry.md"
)


def _telemetry(repo: Path, records: list[dict]) -> None:
    path = repo / TELEMETRY_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )


def _runs_csv(repo: Path, rows: list[tuple[str, int, float]]) -> None:
    path = repo / RUNS_CSV_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["start_local,issue,outcome,run_seconds,fix_seconds_attributed,source"]
    for start, issue, seconds in rows:
        lines.append(f"{start},{issue},failed,{seconds:.1f},0.0,events")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def _record(fingerprint: str, run_id: str, model: str = "gemini:3.1-pro") -> dict:
    return {
        "ts_local": "2026-08-02 10:00:00", "repo": "x", "issue": 2,
        "stage": "lld", "check": "mechanical", "fingerprint": fingerprint,
        "draft_number": 1, "drafter_model": model, "run_id": run_id,
        "detail_raw": fingerprint,
    }


# --- "fixture telemetry + fixture durations produce the expected order" ---


def test_ranking_is_by_cost_not_by_count(tmp_path):
    _runs_csv(tmp_path, [
        ("2026-08-02 13:37:46", 2, 5400.0),   # expensive roll
        ("2026-08-02 14:00:00", 2, 60.0),     # cheap roll
        ("2026-08-02 15:00:00", 2, 60.0),
        ("2026-08-02 16:00:00", 2, 60.0),
    ])
    _telemetry(tmp_path, [
        # 1 occurrence x 5400s = 5400
        _record("lld:mechanical:expensive", "run-issue2-133746"),
        # 3 occurrences x 60s = 180 — more frequent, far cheaper
        _record("lld:mechanical:cheap", "run-issue2-140000"),
        _record("lld:mechanical:cheap", "run-issue2-150000"),
        _record("lld:mechanical:cheap", "run-issue2-160000"),
    ])

    ranked = rank(load_telemetry(tmp_path), load_durations(tmp_path))

    assert [r.fingerprint for r in ranked] == [
        "lld:mechanical:expensive", "lld:mechanical:cheap",
    ], "counting alone would invert this"
    assert ranked[0].cost == pytest.approx(5400.0)
    assert ranked[1].cost == pytest.approx(180.0)
    assert ranked[1].occurrences == 3


def test_cost_is_occurrences_times_mean_wasted_seconds(tmp_path):
    _runs_csv(tmp_path, [
        ("2026-08-02 10:00:00", 2, 100.0),
        ("2026-08-02 11:00:00", 2, 300.0),
    ])
    _telemetry(tmp_path, [
        _record("lld:mechanical:a", "run-issue2-100000"),
        _record("lld:mechanical:a", "run-issue2-110000"),
    ])

    ranked = rank(load_telemetry(tmp_path), load_durations(tmp_path))

    assert ranked[0].mean_wasted_seconds == pytest.approx(200.0)
    assert ranked[0].cost == pytest.approx(400.0)


def test_the_run_id_tag_joins_to_the_duration_table():
    durations = {(2, "133746"): 5400.0}
    assert duration_for("run-issue2-133746", durations) == 5400.0
    assert duration_for("run11b-issue2-133746", durations) == 5400.0
    assert duration_for("garbage", durations) is None
    assert duration_for("run-issue9-999999", durations) is None


# --- "absent from the duration table: ranked by count, flagged, never zero" ---


def test_missing_duration_is_flagged_and_never_costed_at_zero(tmp_path):
    _runs_csv(tmp_path, [("2026-08-02 10:00:00", 2, 50.0)])
    _telemetry(tmp_path, [
        _record("lld:mechanical:costed", "run-issue2-100000"),
        # No matching row in runs.csv — duration unknown.
        _record("lld:mechanical:unmeasured", "run-issue77-235959"),
        _record("lld:mechanical:unmeasured", "run-issue77-235958"),
    ])

    ranked = rank(load_telemetry(tmp_path), load_durations(tmp_path))
    by_fp = {r.fingerprint: r for r in ranked}

    unmeasured = by_fp["lld:mechanical:unmeasured"]
    assert UNKNOWN_DURATION in unmeasured.flags
    assert unmeasured.cost is None, "zero would sort it below every costed entry"
    assert unmeasured.mean_wasted_seconds is None
    assert unmeasured.occurrences == 2
    assert len(ranked) == 2, "an unmeasured fingerprint is never dropped"


def test_unknown_duration_entries_are_ordered_among_themselves_by_count(tmp_path):
    _telemetry(tmp_path, [
        _record("lld:mechanical:rare", "run-issue77-000001"),
        _record("lld:mechanical:common", "run-issue77-000002"),
        _record("lld:mechanical:common", "run-issue77-000003"),
        _record("lld:mechanical:common", "run-issue77-000004"),
    ])

    ranked = rank(load_telemetry(tmp_path), {})

    assert [r.fingerprint for r in ranked] == [
        "lld:mechanical:common", "lld:mechanical:rare",
    ]
    assert all(UNKNOWN_DURATION in r.flags for r in ranked)


def test_a_costed_entry_outranks_an_unknown_one_even_with_fewer_occurrences(tmp_path):
    _runs_csv(tmp_path, [("2026-08-02 10:00:00", 2, 5000.0)])
    _telemetry(tmp_path, [
        _record("lld:mechanical:costed", "run-issue2-100000"),
        _record("lld:mechanical:unknown1", "run-issue77-000001"),
        _record("lld:mechanical:unknown1", "run-issue77-000002"),
    ])

    ranked = rank(load_telemetry(tmp_path), load_durations(tmp_path))

    assert ranked[0].fingerprint == "lld:mechanical:costed"
    assert ranked[1].flags == (UNKNOWN_DURATION,)
    # But it is still present and still carries its real count.
    assert ranked[1].occurrences == 2


# --- "identical inputs produce byte-identical output" --------------------


def test_output_is_byte_identical_for_identical_input(tmp_path):
    _runs_csv(tmp_path, [
        ("2026-08-02 10:00:00", 2, 100.0),
        ("2026-08-02 11:00:00", 2, 100.0),
    ])
    records = [
        _record("lld:mechanical:b", "run-issue2-100000"),
        _record("lld:mechanical:a", "run-issue2-110000"),
    ]

    _telemetry(tmp_path, records)
    first = render(rank(load_telemetry(tmp_path), load_durations(tmp_path)))

    _telemetry(tmp_path, list(reversed(records)))
    second = render(rank(load_telemetry(tmp_path), load_durations(tmp_path)))

    assert first == second, "equal-cost entries must tie-break on name, not dict order"


# --- "an empty telemetry file produces an empty ranking and exit 0" ------


def test_empty_telemetry_ranks_empty_and_exits_zero(tmp_path, capsys):
    import prompt_revision_rank as cli

    _telemetry(tmp_path, [])

    code = cli.main(["--repo", str(tmp_path)])

    assert code == 0, "no failures recorded is a fact, not an error"
    assert "No validation failures recorded" in capsys.readouterr().out


def test_missing_telemetry_file_is_not_an_error(tmp_path, capsys):
    import prompt_revision_rank as cli

    assert cli.main(["--repo", str(tmp_path)]) == 0
    assert load_telemetry(tmp_path) == []


def test_render_of_an_empty_ranking():
    assert "nothing to rank" in render([])


def test_cli_warns_when_durations_are_absent(tmp_path, capsys):
    import prompt_revision_rank as cli

    _telemetry(tmp_path, [_record("lld:mechanical:a", "run-issue2-100000")])

    code = cli.main(["--repo", str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 0
    assert "duration-unknown" in out
    assert "no durations" in out, "silence would read as 'everything is measured'"


def test_cli_top_limits_the_listing(tmp_path, capsys):
    import prompt_revision_rank as cli

    _runs_csv(tmp_path, [("2026-08-02 10:00:00", 2, 100.0)])
    _telemetry(tmp_path, [
        _record("lld:mechanical:a", "run-issue2-100000"),
        _record("lld:mechanical:b", "run-issue2-100000"),
    ])

    cli.main(["--repo", str(tmp_path), "--top", "1"])
    body = [
        line for line in capsys.readouterr().out.splitlines()
        if line.startswith("lld:")
    ]
    assert len(body) == 1


# --- "the procedure document exists and requires before/after" -----------


def test_procedure_document_exists_and_requires_the_comparison():
    assert PROCEDURE.is_file()
    text = PROCEDURE.read_text(encoding="utf-8")

    assert "before" in text.lower() and "after" in text.lower()
    assert "revert" in text.lower(), "keep-or-revert on evidence is the point"
    assert "before-rate" in text.lower(), "PR bodies must quote it"
    assert "do not fabricate" in text.lower(), "the cold-start rule must be written down"


def test_procedure_names_the_ranking_tool_that_exists():
    text = PROCEDURE.read_text(encoding="utf-8")
    assert "tools/prompt_revision_rank.py" in text
    assert (Path(__file__).resolve().parents[2] / "tools/prompt_revision_rank.py").is_file()


# --- the worked example ---------------------------------------------------


def test_the_mandatory_sections_carry_an_in_place_blocked_marker():
    """The worked example: §11 and §12 went missing 16 times each across 6 rolls.

    §2.1 — the third mandatory section — already carried an in-place BLOCKED
    warning and was dropped far less often. This copies that construct onto the
    two sections that lacked it.
    """
    from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
        MANDATORY_SECTIONS,
    )

    template = TEMPLATE.read_text(encoding="utf-8")

    for section in MANDATORY_SECTIONS:
        assert section in template, f"{section} must exist in the template at all"

    for heading in ("## 11. Risks & Mitigations", "## 12. Definition of Done"):
        index = template.index(heading)
        following = template[index : index + 400]
        assert "MANDATORY" in following and "BLOCKED" in following, (
            f"{heading} must state its own gate in place — a drafter that stops "
            f"early never reaches a warning stored further down"
        )


def test_the_marker_names_the_literal_heading_the_validator_checks():
    """The marker has to name `## 11`, not 'section eleven' — the validator
    matches the literal string, and so must the instruction."""
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "If `## 11` is missing" in template
    assert "If `## 12` is missing" in template

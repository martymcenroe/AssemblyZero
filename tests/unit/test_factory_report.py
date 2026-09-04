"""The factory telemetry rollup (#2575).

Counts, never estimates; honest denominators; a declared gate registry that
cannot silently drift behind the recording sites in the workflow sources.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import factory_report as cli  # noqa: E402

from assemblyzero.speedrun.factory_report import (  # noqa: E402
    DECLARED_CHECKS,
    build_report,
    parse_since,
    read_halt_bundles,
    render_report,
    scan_run_log,
    scan_run_logs,
)
from assemblyzero.speedrun.healing import record_heal  # noqa: E402
from assemblyzero.speedrun.preserved import record_preserved  # noqa: E402
from assemblyzero.speedrun.prompt_telemetry import record_failure  # noqa: E402


# ---------------------------------------------------------------------------
# The registry is kept honest by the source, not by convention
# ---------------------------------------------------------------------------


class TestDeclaredChecks:
    """DECLARED_CHECKS is the denominator for zero-fire reporting.

    Inferring it from observed records would be circular -- a gate that
    never fires is exactly the one absent from the data -- so it is
    declared, and this test is what stops it drifting behind the code.
    """

    def _recording_sites(self) -> set[tuple[str, str]]:
        """Every (stage, check) literal pair at a record_failure(s) site."""
        found: set[tuple[str, str]] = set()
        workflows = REPO_ROOT / "assemblyzero" / "workflows"
        call = re.compile(r"record_failures?\(")
        for path in sorted(workflows.rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if not call.search(line):
                    continue
                # The call's keyword arguments sit within a short window
                # after the opening paren in every current site; widen the
                # window rather than parse Python, and let a miss fail loud.
                window = "\n".join(lines[index : index + 15])
                stage = re.search(r'stage=["\']([^"\']+)["\']', window)
                check = re.search(r'check=["\']([^"\']+)["\']', window)
                if stage and check:
                    found.add((stage.group(1), check.group(1)))
        return found

    def test_every_recording_site_is_declared(self):
        sites = self._recording_sites()
        assert sites, "found no record_failure sites -- the grep is wrong"
        missing = sites - set(DECLARED_CHECKS)
        assert not missing, (
            f"recording sites not in DECLARED_CHECKS: {sorted(missing)}. "
            f"A new gate must be declared or zero-fire reporting silently "
            f"loses its denominator."
        )

    def test_no_declared_check_is_a_phantom(self):
        sites = self._recording_sites()
        phantom = set(DECLARED_CHECKS) - sites
        assert not phantom, (
            f"declared but no recording site emits them: {sorted(phantom)}. "
            f"A phantom entry reports as permanently zero-fire, which reads "
            f"as a perfect gate that does not exist."
        )


# ---------------------------------------------------------------------------
# Window parsing
# ---------------------------------------------------------------------------


class TestParseSince:
    def test_relative_days(self):
        now = datetime(2026, 8, 28, 12, 0, 0)
        assert parse_since("7d", now=now) == now - timedelta(days=7)

    def test_relative_hours_and_weeks(self):
        now = datetime(2026, 8, 28, 12, 0, 0)
        assert parse_since("24h", now=now) == now - timedelta(hours=24)
        assert parse_since("2w", now=now) == now - timedelta(weeks=2)

    def test_absolute_date_and_timestamp(self):
        assert parse_since("2026-08-27") == datetime(2026, 8, 27, 0, 0, 0)
        assert parse_since("2026-08-27 09:30:00") == datetime(
            2026, 8, 27, 9, 30, 0
        )

    def test_empty_means_no_bound(self):
        assert parse_since("") is None
        assert parse_since("   ") is None

    def test_unparseable_raises_rather_than_silently_widening(self):
        """Silently reading everything would put a wrong denominator under
        every number in the report."""
        with pytest.raises(ValueError, match="unparseable"):
            parse_since("last tuesday")


# ---------------------------------------------------------------------------
# Run-log scanning
# ---------------------------------------------------------------------------


def _write_run_log(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


class TestScanRunLog:
    def test_counts_each_marker_once_per_line(self, tmp_path):
        log = _write_run_log(
            tmp_path,
            "run-issue331-111729.log",
            "\n".join(
                [
                    "    [PINNING] refused: 1 line(s) starting 'A'",
                    "    [PINNING] refused: 2 line(s) starting 'B'",
                    "    [PINNING] REGRESSION CLASS: revision modified 'A'",
                    "    [EDIT-SCRIPT] Applied 9 edit(s); 91% preserved",
                    "    [EDIT-SCRIPT] Falling back to full revision: no change",
                    "    [CAP] 3 revision(s) spent, granting one (#2304).",
                    "    [REVIEW] Spec review continues [continue]: round 4 of",
                    "    [STAGE] lld running 60s (nominal ~409s)",
                    "    [STAGE] lld running 120s (nominal ~409s)",
                ]
            ),
        )
        facts = scan_run_log(log)
        assert facts.issue == 331
        assert facts.run_id == "run-issue331-111729"
        assert facts.pinning_refusals == 2
        assert facts.pinning_regressions == 1
        assert facts.edit_scripts_applied == 1
        assert facts.edit_script_fallbacks == 1
        assert facts.fallback_reasons == ["no change"]
        assert len(facts.cap_grants) == 1
        assert facts.review_rounds == {"spec": 4}
        # The watchdog prints once a minute; the LAST elapsed is the floor.
        assert facts.stage_elapsed == {"lld": (120, 409)}

    def test_stray_bytes_do_not_suppress_events(self, tmp_path):
        """The 2026-08-27 near-miss: GNU grep's binary detection silently
        dropped matching lines from a run log carrying stray bytes, which is
        a confident wrong answer. errors="replace" is the Python-side grep -a.
        """
        directory = tmp_path / "data" / "speedrun" / "runs"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "run-issue331-090000.log"
        path.write_bytes(
            b"    [PINNING] refused: 1 line(s) \x97 locked content\n"
            b"    [PINNING] refused: 2 line(s) \xff\xfe bad bytes\n"
            b"    [PINNING] REGRESSION CLASS: revision modified\n"
        )
        facts = scan_run_log(path)
        assert facts.pinning_refusals == 2
        assert facts.pinning_regressions == 1
        assert not facts.unreadable

    def test_unmatched_filename_is_unlinked_not_misattributed(self, tmp_path):
        log = _write_run_log(tmp_path, "run-issueXYZ.log", "[CAP] x")
        facts = scan_run_log(log)
        assert facts.issue is None

    def test_events_and_heartbeat_logs_are_not_scanned_as_runs(self, tmp_path):
        directory = tmp_path / "data" / "speedrun" / "runs"
        _write_run_log(directory, "run-issue1-010101.log", "[CAP] a")
        _write_run_log(directory, "run-issue1-010101-events.log", "[CAP] b")
        _write_run_log(directory, "run-issue1-010101-heartbeat.log", "[CAP] c")
        scanned = scan_run_logs(tmp_path)
        assert [f.run_id for f in scanned] == ["run-issue1-010101"]


# ---------------------------------------------------------------------------
# Halt bundles
# ---------------------------------------------------------------------------


class TestHaltBundles:
    def test_reads_bundles_and_skips_corrupt_ones(self, tmp_path):
        good = tmp_path / "lineage" / "a"
        good.mkdir(parents=True)
        (good / "halt-evidence.json").write_text(
            json.dumps(
                {
                    "workflow": "implementation_spec",
                    "stage": "spec",
                    "halted_at": "2026-08-27T11:17:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        bad = tmp_path / "lineage" / "b"
        bad.mkdir(parents=True)
        (bad / "halt-evidence.json").write_text("{not json", encoding="utf-8")

        bundles = read_halt_bundles([tmp_path])
        assert len(bundles) == 1
        assert bundles[0]["stage"] == "spec"

    def test_a_shared_root_is_scoped_to_the_target_repo(self, tmp_path):
        """The halt path writes one copy beside the state snapshot in the
        SHARED ~/.assemblyzero/workflow_state, which holds every repo the
        fleet has ever rolled. Counting it unscoped attributes other repos'
        halts to this one."""
        shared = tmp_path / "shared_state"
        repo = tmp_path / "target"
        other = tmp_path / "other"
        for directory in (shared / "a", shared / "b", shared / "c", repo, other):
            directory.mkdir(parents=True)

        (shared / "a" / "halt-evidence.json").write_text(
            json.dumps({"stage": "spec", "audit_dir": str(repo / "lineage")}),
            encoding="utf-8",
        )
        (shared / "b" / "halt-evidence.json").write_text(
            json.dumps({"stage": "lld", "audit_dir": str(other / "lineage")}),
            encoding="utf-8",
        )
        (shared / "c" / "halt-evidence.json").write_text(
            json.dumps({"stage": "lld"}), encoding="utf-8"
        )

        bundles = read_halt_bundles([shared], scope_repo=repo)
        assert [b["stage"] for b in bundles] == ["spec"]

    def test_a_bundle_inside_the_repo_needs_no_audit_dir(self, tmp_path):
        repo = tmp_path / "target"
        lineage = repo / "docs" / "lineage" / "run-1"
        lineage.mkdir(parents=True)
        (lineage / "halt-evidence.json").write_text(
            json.dumps({"stage": "spec"}), encoding="utf-8"
        )
        assert len(read_halt_bundles([repo], scope_repo=repo)) == 1

    def test_window_filters_on_the_bundle_date(self, tmp_path):
        root = tmp_path / "l"
        root.mkdir(parents=True)
        (root / "halt-evidence.json").write_text(
            json.dumps({"stage": "lld", "halted_at": "2026-08-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        assert read_halt_bundles([tmp_path], datetime(2026, 8, 27)) == []
        assert len(read_halt_bundles([tmp_path], datetime(2026, 7, 1))) == 1


# ---------------------------------------------------------------------------
# The counted picture
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_repo(tmp_path):
    """A target repo with one record in every store."""
    repo = tmp_path / "target"
    repo.mkdir()

    record_failure(
        repo, stage="lld", check="mechanical",
        detail="Section 2.1 table malformed",
        issue=331, drafter_model="gemini:3.1-pro", run_id="run-issue331-111729",
    )
    record_failure(
        repo, stage="lld", check="mechanical",
        detail="Section 2.1 table malformed",
        issue=331, drafter_model="gemini:3.1-pro", run_id="run-issue331-111729",
    )
    record_failure(
        repo, stage="spec", check="reviewer-revise", detail="missing window",
        issue=331, run_id="run-issue331-111729",
    )

    record_heal(repo, "janitor", "docs/lld/active/LLD-331.md", "healed",
                run_tag="run-issue331-111729")
    record_heal(repo, "janitor", "docs/lld/active/LLD-331.md", "healed",
                run_tag="run-issue331-123221")
    record_heal(repo, "reset", "#331", "partial", run_tag="run-issue331-111729")

    record_preserved(repo, branch="graveyard/leavings-20260827-111730",
                     source="leavings", detail="1 file(s)")
    record_preserved(repo, branch="graveyard/331-lld-20260827-111731",
                     source="halt-restore", detail="attempt branch")

    _write_run_log(
        repo / "data" / "speedrun" / "runs",
        "run-issue331-111729.log",
        "\n".join(
            [
                "    [PINNING] refused: 1 line(s) starting 'A'",
                "    [PINNING] refused: 2 line(s) starting 'B'",
                "    [EDIT-SCRIPT] Applied 3 edit(s); 100% preserved",
                "    [EDIT-SCRIPT] Falling back to full revision: no change",
                "    [EDIT-SCRIPT] Falling back to full revision: no change",
                "    [REVIEW] Spec review continues [continue]: round 6 of",
                "    [STAGE] spec running 300s (nominal ~409s)",
            ]
        ),
    )
    return repo


class TestBuildReport:
    def test_counts_every_store(self, seeded_repo):
        data = build_report(seeded_repo)
        assert data["stores"]["prompt_failures"]["in_window"] == 3
        assert data["stores"]["heals"]["in_window"] == 3
        assert data["stores"]["preserved"]["in_window"] == 2
        assert data["stores"]["run_logs"]["in_window"] == 1

    def test_gates_split_fired_from_zero_fire(self, seeded_repo):
        data = build_report(seeded_repo)
        gates = data["gates"]
        assert gates["per_check"]["lld:mechanical"] == 2
        assert gates["per_check"]["spec:reviewer-revise"] == 1
        # Declared but unfired in this window -- the honest denominator.
        assert "lld:test-plan" in gates["zero_fire"]
        assert "lld:requirements-conflict" in gates["zero_fire"]
        assert gates["undeclared"] == []

    def test_edit_script_fallback_rate_is_counted_not_estimated(
        self, seeded_repo
    ):
        data = build_report(seeded_repo)
        assert data["loops"]["edit_scripts_applied"] == 1
        assert data["loops"]["edit_script_fallbacks"] == 2

    def test_pinning_events_are_summed_across_runs(self, seeded_repo):
        assert build_report(seeded_repo)["pinning"]["refusals"] == 2

    def test_recurring_heal_target_surfaces_as_a_spike(self, seeded_repo):
        data = build_report(seeded_repo)
        targets = dict(data["heals"]["recurring_targets"])
        assert targets["janitor:docs/lld/active/LLD-331.md"] == 2
        # The single reset is not a "recurrence" and must not be listed.
        assert "reset:#331" not in targets

    def test_preservation_counted_by_source(self, seeded_repo):
        by_source = build_report(seeded_repo)["preserved"]["by_source"]
        assert by_source["leavings"] == 1
        assert by_source["halt-restore"] == 1

    def test_window_excludes_older_records(self, seeded_repo):
        future = datetime.now() + timedelta(days=1)
        data = build_report(seeded_repo, since=future)
        assert data["stores"]["prompt_failures"]["in_window"] == 0
        assert data["stores"]["heals"]["in_window"] == 0

    def test_empty_repo_reports_absence_not_zero(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        data = build_report(empty)
        assert data["stores"]["prompt_failures"]["exists"] is False
        assert data["stores"]["run_logs"]["exists"] is False
        assert data["gates"]["zero_fire"] == sorted(
            f"{s}:{c}" for s, c in DECLARED_CHECKS
        )


class TestRenderReport:
    def test_is_deterministic(self, seeded_repo):
        data = build_report(seeded_repo)
        first = render_report(data)
        second = render_report(data)
        assert first == second

    def test_names_a_missing_store_rather_than_printing_zero(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        text = render_report(build_report(empty))
        assert "| NO |" in text
        # The zeros below must read as absence of DATA, not absence of events.
        assert "an absence of data, not an absence of events" in text

    def test_zero_fire_gates_are_not_called_healthy(self, seeded_repo):
        text = render_report(build_report(seeded_repo))
        assert "either perfect \nor dead" in text or "perfect" in text
        assert "lld:test-plan" in text

    def test_shortlist_is_computed_for_the_reader(self, seeded_repo):
        text = render_report(build_report(seeded_repo))
        assert "## Shortlist (computed)" in text
        assert "Top check by failure volume: lld:mechanical (2)" in text
        assert "Edit-script fallback rate: 2/3" in text


class TestCli:
    def test_missing_repo_is_not_an_error(self, tmp_path, capsys):
        assert cli.main(["--repo", str(tmp_path / "nope")]) == 0
        assert "No such repository" in capsys.readouterr().out

    def test_runs_and_prints(self, seeded_repo, capsys):
        assert cli.main(["--repo", str(seeded_repo)]) == 0
        out = capsys.readouterr().out
        assert "# Factory report" in out
        assert "## Shortlist (computed)" in out

    def test_save_path_writes_the_same_text_that_printed(
        self, seeded_repo, tmp_path, capsys
    ):
        target = tmp_path / "out" / "report.md"
        assert cli.main(
            ["--repo", str(seeded_repo), "--save-path", str(target)]
        ) == 0
        out = capsys.readouterr().out
        assert target.is_file()
        assert target.read_text(encoding="utf-8") in out

    def test_default_save_path_names_target_and_date(self, tmp_path):
        path = cli.default_save_path(
            Path("/c/Users/mcwiz/Projects/boostgauge"),
            when=datetime(2026, 8, 28),
        )
        assert path.name == "0904-factory-report-boostgauge-2026-08-28.md"
        assert path.parent.name == "audits"


# ---------------------------------------------------------------------------
# How a run ended (#2717) and how far it got (#2718)
# ---------------------------------------------------------------------------

import os  # noqa: E402

from assemblyzero.speedrun.factory_report import (  # noqa: E402
    CAUSE_TABLE,
    CAUSE_UNCLASSIFIED,
    CAUSE_UNRECORDED,
    _IMPL_NODE_ORDER,
    _STAGE_ORDER,
    classify_cause,
)

_TABLE_HEADER = [
    "STAGE     VERDICT      TIME  ARTIFACT / ERROR",
    "----------------------------------------------------------------------",
]

#: The closing lines of a run that finished: `run-issue1-*` merged PR #200.
PASSED_TAIL = "\n".join(
    _TABLE_HEADER
    + [
        "triage    skipped      0.0s  C:\\Users\\mcwiz\\Projects\\boostgauge\\docs\\lineage\\1\\issue-brie",
        "lld       passed      87.7s  C:\\Users\\mcwiz\\Projects\\boostgauge\\docs\\lld\\active\\LLD-001.m",
        "spec      passed      84.7s  C:\\Users\\mcwiz\\Projects\\boostgauge\\docs\\lld\\drafts\\spec-0001",
        "impl      passed     179.4s  C:\\Users\\mcwiz\\Projects\\boostgauge-1",
        "pr        passed       2.2s  https://github.com/martymcenroe/boostgauge/pull/200",
        "cleanup   passed      66.6s  https://github.com/martymcenroe/boostgauge/pull/200",
        "",
        "[ORCHESTRATOR] All stages passed.",
        "[ORCHESTRATOR] PR: https://github.com/martymcenroe/boostgauge/pull/200",
        "[ORCHESTRATOR] Duration: 420.7s",
    ]
)

#: run-issue4-183941, 2026-09-02: nine review rounds, the hard ceiling.
FAILED_SPEC_TAIL = "\n".join(
    _TABLE_HEADER
    + [
        "triage    skipped      0.0s  C:\\...\\issue-brie",
        "lld       passed     299.7s  C:\\...\\LLD-004.m",
        "visual    skipped      0.0s  no visual deliverable declared for this issue",
        "spec      failed    2341.5s  Iteration cap: 3 review rounds ended REVISE, so the run stop",
        "impl      -               -",
        "pr        -               -",
        "cleanup   -               -",
        "",
        "==========================================================",
        "  ORCHESTRATION FAILED at stage: spec",
        "==========================================================",
        "  Error: Iteration cap: 3 review rounds ended REVISE, so the run stopped rather than spend another round on the same objection. Last feedback: ...",
        "  exit: hard-ceiling",
        "  the loop was still converging at round 8, and stopped only because it reached the hard ceiling of 9 (3x the base cap of 3).",
        "  Attempts: 3 | Duration: 39m 1s",
    ]
)

#: The shape of run-issue4-172600: green reached, then the coverage guard.
#: The untimestamped `[N2] Generating Implementation Spec` line is the SPEC
#: workflow's marker and must not count as an implementation node.
FAILED_IMPL_TAIL = "\n".join(
    [
        "[N2] Generating Implementation Spec revision (iteration 2)...",
        "[09:24:13] [N3] Verifying red phase (all tests should fail)...",
        "[09:24:31] [N4] Implementing code file-by-file (iteration 0)...",
        "[09:31:02] [N5] Verifying green phase (all tests should pass)...",
        "[09:31:40] [N4] Implementing code file-by-file (iteration 1)...",
        "[09:40:12] [N5] Verifying green phase (all tests should pass)...",
    ]
    + _TABLE_HEADER
    + [
        "triage    skipped      0.0s  C:\\...\\issue-brie",
        "lld       skipped      0.0s  C:\\...\\LLD-004.m",
        "spec      passed     605.0s  C:\\...\\spec-0004",
        "impl      failed    2518.4s  Coverage stagnant: 97.0% -> 97.0% (< 1% improvement). Haltin",
        "pr        -               -",
        "cleanup   -               -",
        "",
        "==========================================================",
        "  ORCHESTRATION FAILED at stage: impl",
        "==========================================================",
        "  Error: Coverage stagnant: 97.0% -> 97.0% (< 1% improvement). Halting to prevent token waste.",
        "  Attempts: 3 | Duration: 41m 58s",
    ]
)

#: A run killed mid-call: no table, no banner, the log just stops.
KILLED_TAIL = "\n".join(
    [
        "NODE [5/9] generate spec -- The drafter model writes the implementation spec.",
        "[N2] Generating Implementation Spec revision (iteration 2)...",
        "    [PREFLIGHT] Gemini: 4/4 credentials",
        "    Drafter: gemini:3.1-pro",
        "    [STAGE] spec running 240s (nominal ~90s)",
        "        Calling Claude... (585s)",
        "        Calling Claude... (600s)",
    ]
)

#: Fifteen of the 135 banners on disk carry an empty Error line.
EMPTY_ERROR_TAIL = "\n".join(
    _TABLE_HEADER
    + [
        "lld       failed     86.1s  ",
        "==========================================================",
        "  ORCHESTRATION FAILED at stage: lld",
        "==========================================================",
        "  Error: ",
        "  Attempts: 3 | Duration: 3m 58s",
    ]
)


class TestTerminalParse:
    def test_a_passed_run(self, tmp_path):
        facts = scan_run_log(
            _write_run_log(tmp_path, "run-issue1-010101.log", PASSED_TAIL)
        )
        assert facts.outcome == "passed"
        assert facts.furthest == "cleanup"
        assert facts.cause == ""
        assert facts.stage_verdicts["triage"] == "skipped"

    def test_a_run_that_failed_at_spec_on_the_review_ceiling(self, tmp_path):
        facts = scan_run_log(
            _write_run_log(tmp_path, "run-issue4-183941.log", FAILED_SPEC_TAIL)
        )
        assert facts.outcome == "failed"
        assert facts.failed_stage == "spec"
        assert facts.furthest == "spec"
        assert facts.cause == "spec.review_cap"
        assert facts.exit_label == "hard-ceiling"
        assert facts.error_head.startswith(
            "Iteration cap: 3 review rounds ended REVISE"
        )

    def test_a_run_that_failed_at_impl_names_its_furthest_node(self, tmp_path):
        facts = scan_run_log(
            _write_run_log(tmp_path, "run-issue4-172600.log", FAILED_IMPL_TAIL)
        )
        assert facts.outcome == "failed"
        assert facts.failed_stage == "impl"
        # N5 (green) was the highest node reached; the loop back to N4 does
        # not lower it, and the spec workflow's [N2] never counted.
        assert facts.furthest == "impl:N5"
        assert facts.cause == "impl.stagnation.coverage"

    def test_a_killed_run_has_no_banner_and_carries_its_last_line(self, tmp_path):
        facts = scan_run_log(
            _write_run_log(tmp_path, "run-issue7-180539.log", KILLED_TAIL)
        )
        assert facts.outcome == "killed"
        assert facts.cause == "killed"
        # No table: the watchdog is the only witness to the stage.
        assert facts.furthest == "spec"
        assert facts.error_head == "Calling Claude... (600s)"

    def test_an_empty_error_line_is_unrecorded_not_unclassified(self, tmp_path):
        facts = scan_run_log(
            _write_run_log(tmp_path, "run-issue2-133746.log", EMPTY_ERROR_TAIL)
        )
        assert facts.outcome == "failed"
        assert facts.furthest == "lld"
        assert facts.cause == CAUSE_UNRECORDED

    def test_an_unknown_message_is_unclassified_never_the_nearest_bucket(self):
        assert (
            classify_cause("Something the pipeline never said before")
            == CAUSE_UNCLASSIFIED
        )

    def test_a_passed_run_outranks_a_failed_one(self, tmp_path):
        passed = scan_run_log(
            _write_run_log(tmp_path, "run-issue1-000001.log", PASSED_TAIL)
        )
        failed = scan_run_log(
            _write_run_log(tmp_path, "run-issue1-000002.log", FAILED_IMPL_TAIL)
        )
        assert passed.furthest_key > failed.furthest_key


class TestCauseTable:
    """The table is authored from real banners, and it stays true to both
    the logs it was read from and the code that emits the messages."""

    def test_every_row_matches_its_own_example(self):
        for cause in CAUSE_TABLE:
            assert classify_cause(cause.example) == cause.key, cause.key

    def test_keys_are_unique(self):
        keys = [cause.key for cause in CAUSE_TABLE]
        assert len(keys) == len(set(keys))

    def test_the_three_deterministic_failures_are_told_apart(self):
        """#2761: one generic row swallowed three gates.

        `DETERMINISTIC_FAILURE` is a token three different halts prepend, and
        a single `r"DETERMINISTIC FAILURE"` row claimed every one. Measured on
        boostgauge before this split, `impl.deterministic_failure` was
        credited with 5 kills; 3 of them were the scaffolder's suite-invalid
        halt, which the gate registry's own note already called a different
        gate.

        The tell was inside the table: that row's `example` was the
        scaffolder's message, so the row was documented -- and
        `test_every_row_matches_its_own_example` pinned -- against a gate it
        is not.

        #2761's ruling then split the last of the three, because it also
        named two things. Four now, each with its own key, and the first
        three are real banner heads from the run logs. The green-phase one
        has never fired, so its text comes from the code that composes it.
        """
        scaffolder = (
            "DETERMINISTIC FAILURE: the generated test suite cannot be "
            "validated and the scaffolder reproduced its previous output"
        )
        red_preexisting = (
            "DETERMINISTIC FAILURE: Red phase failed: 3 tests passed "
            "unexpectedly, and neither a red-entry marker nor this run's own "
            "prior writes explain them"
        )
        red_old_message = (
            "DETERMINISTIC FAILURE: Red phase failed: 8 tests passed "
            "unexpectedly. Tests should fail before implementation exists."
        )
        green_unsatisfiable = (
            "DETERMINISTIC FAILURE: Test(s) failing for a reason no "
            "implementation can fix: test_dynamic_256_matches_baseline"
        )
        assert classify_cause(scaffolder) == "impl.scaffold_suite_invalid"
        assert classify_cause(red_preexisting) == "impl.red.preexisting_implementation"
        assert classify_cause(green_unsatisfiable) == "impl.deterministic_failure"

        # run-issue331 died on the pre-#2337 wording. It has to keep landing
        # on the red row, or a historical kill silently becomes unclassified.
        assert classify_cause(red_old_message) == "impl.red.preexisting_implementation"

    def test_no_generic_deterministic_row_absorbs_a_fourth_emitter(self):
        """#2761: there is deliberately no catch-all left.

        A fifth thing that prepends the token should land in `unclassified`
        and be printed verbatim, which is how the table grows deliberately.
        Absorbing it into the nearest row is what produced the original
        defect.
        """
        invented = "DETERMINISTIC FAILURE: something nobody has written yet"
        assert classify_cause(invented) == CAUSE_UNCLASSIFIED

    def test_a_specific_cause_row_precedes_the_generic_one_it_shares_a_prefix_with(
        self,
    ):
        """Order is load-bearing: `classify_cause` takes the FIRST match, so a
        specific row placed after its generic sibling can never fire.

        After #2761 all four token-sharing rows are specific and none is a
        prefix of another, so ordering among them no longer decides anything.
        What still must hold is that every one of them precedes
        `impl.red_phase_failed`, whose bare `Red phase failed` pattern would
        otherwise claim the red-phase deterministic messages.
        """
        keys = [cause.key for cause in CAUSE_TABLE]
        for specific in (
            "impl.scaffold_suite_invalid",
            "impl.red.preexisting_implementation",
            "impl.deterministic_failure",
        ):
            assert keys.index(specific) < keys.index("impl.red_phase_failed"), (
                f"{specific} is ordered after impl.red_phase_failed, whose "
                f"broader pattern will match first"
            )

    def test_every_row_names_code_that_says_what_the_row_claims(self):
        for cause in CAUSE_TABLE:
            path = REPO_ROOT / cause.emitted_by
            assert path.is_file(), f"{cause.key}: {cause.emitted_by} is not a file"
            text = path.read_text(encoding="utf-8", errors="replace")
            assert cause.source_literal in text, (
                f"{cause.key}: {cause.emitted_by} does not contain "
                f"{cause.source_literal!r}; the row names the wrong code"
            )

    def test_stage_order_mirrors_the_orchestrator(self):
        from assemblyzero.workflows.orchestrator.state import STAGE_ORDER

        assert list(_STAGE_ORDER) == list(STAGE_ORDER)

    def test_impl_node_order_covers_every_marker_the_workflow_prints(self):
        printed: set[str] = set()
        testing = REPO_ROOT / "assemblyzero" / "workflows" / "testing"
        marker = re.compile(r"\[(N\d+(?:\.\d+)?[a-z]?)\]")
        for path in testing.rglob("*.py"):
            printed.update(
                marker.findall(path.read_text(encoding="utf-8", errors="replace"))
            )
        assert printed, "found no [N..] markers in the testing workflow"
        missing = printed - set(_IMPL_NODE_ORDER)
        assert not missing, f"markers printed but not ranked: {sorted(missing)}"


class TestConvergence:
    def _seed(self, tmp_path) -> Path:
        """Three days: lld only, then green reached, then back to spec."""
        runs = tmp_path / "data" / "speedrun" / "runs"
        day1 = _write_run_log(runs, "run-issue4-090000.log", EMPTY_ERROR_TAIL)
        day2 = _write_run_log(runs, "run-issue4-100000.log", FAILED_IMPL_TAIL)
        day2b = _write_run_log(runs, "run-issue4-110000.log", FAILED_SPEC_TAIL)
        day3 = _write_run_log(runs, "run-issue4-120000.log", FAILED_SPEC_TAIL)
        base = datetime(2026, 9, 1, 12, 0, 0).timestamp()
        for path, offset in (
            (day1, 0),
            (day2, 86400),
            (day2b, 86400 + 3600),
            (day3, 2 * 86400),
        ):
            os.utime(path, (base + offset, base + offset))
        return tmp_path

    def test_per_day_furthest_and_trend(self, tmp_path):
        data = build_report(self._seed(tmp_path))
        rows = data["convergence"]["by_day"]
        assert [
            (r["day"], r["launches"], r["furthest"], r["trend"]) for r in rows
        ] == [
            ("2026-09-01", 1, "lld", "first"),
            ("2026-09-02", 2, "impl:N5", "up"),
            ("2026-09-03", 1, "spec", "down"),
        ]
        assert rows[1]["run_id"] == "run-issue4-100000"
        assert data["convergence"]["best"]["run_id"] == "run-issue4-100000"

    def test_outcomes_and_causes_are_counted(self, tmp_path):
        data = build_report(self._seed(tmp_path))
        assert data["outcomes"]["counts"] == {"failed": 4}
        assert data["outcomes"]["failed_by_stage"] == {
            "lld": 1, "impl": 1, "spec": 2,
        }
        assert data["outcomes"]["kills_by_cause"]["spec.review_cap"] == 2
        assert data["outcomes"]["kills_by_cause"][CAUSE_UNRECORDED] == 1
        assert data["outcomes"]["kills_by_judges"]["budget"] == 2

    def test_render_puts_convergence_first_and_prints_unclassified(
        self, tmp_path
    ):
        repo = self._seed(tmp_path)
        _write_run_log(
            repo / "data" / "speedrun" / "runs",
            "run-issue4-130000.log",
            EMPTY_ERROR_TAIL.replace("  Error: ", "  Error: A message no row knows"),
        )
        text = render_report(build_report(repo))
        assert text.index("## Convergence") < text.index("## Stores read")
        assert (
            "| 2026-09-02 | 2 | impl:N5 | up | run-issue4-100000 | "
            "impl.stagnation.coverage |"
        ) in text
        assert "run-issue4-130000: A message no row knows" in text
        assert "Top cause of death: spec.review_cap (2)" in text

    def test_an_empty_window_places_nothing(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        data = build_report(empty)
        assert data["convergence"]["by_day"] == []
        assert data["convergence"]["best"] is None
        assert "nothing to place" in render_report(data)

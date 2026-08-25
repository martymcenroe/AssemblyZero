"""Unit tests for the ADR 0226 requirements form checker (#2219).

Two fixtures anchor the suite. `boostgauge-7-body.md` is the live artifact --
the first requirement converted to the new form, frozen here as it stood when
it passed the semantic gate -- and it exercises the no-ID join mode.
`ids-exact-mode.md` is synthetic and exercises the exact mode.

Every positive claim has a negative beside it. A checker whose passing result
has never been made to fail is not a check, and this one's whole value is that
a clean report can be trusted.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.workflows.requirements import form_check as fc  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "requirements"
BOOSTGAUGE_7 = FIXTURES / "boostgauge-7-body.md"
IDS_EXACT = FIXTURES / "ids-exact-mode.md"


@pytest.fixture(scope="module")
def boostgauge_body() -> str:
    return BOOSTGAUGE_7.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ids_body() -> str:
    return IDS_EXACT.read_text(encoding="utf-8")


def kinds(report: fc.FormReport) -> list[str]:
    return [v.kind for v in report.violations]


def details(report: fc.FormReport) -> str:
    return " || ".join(v.detail for v in report.violations)


# ---------------------------------------------------------------------------
# The live fixture (ruling 2: boostgauge #7 is the no-ID artifact)
# ---------------------------------------------------------------------------


class TestBoostgaugeSeven:
    def test_it_passes(self, boostgauge_body):
        report = fc.check_form(boostgauge_body)
        assert report.ok, details(report)

    def test_two_decision_tables_with_twelve_rows_between_them(self, boostgauge_body):
        report = fc.check_form(boostgauge_body)

        assert len(report.tables) == 2
        assert [t.row_count for t in report.tables] == [4, 8]
        assert sum(t.row_count for t in report.tables) == 12

    def test_every_row_joined_to_a_criterion(self, boostgauge_body):
        report = fc.check_form(boostgauge_body)

        for table in report.tables:
            assert table.matched_rows == table.row_count
            assert table.group_size == table.row_count

    def test_it_runs_in_the_weaker_mode_and_says_so(self, boostgauge_body):
        """The no-silent-caps rule: a reader must not mistake the modes."""
        report = fc.check_form(boostgauge_body)
        rendered = fc.render_report(report, "boostgauge #7")

        assert all(not t.exact_join for t in report.tables)
        assert "row join: count and outcome" in rendered
        assert "delegated to the semantic gate" in rendered
        assert "row join: exact" not in rendered

    def test_ears_did_not_run_and_the_zero_carries_its_denominator(
        self, boostgauge_body
    ):
        report = fc.check_form(boostgauge_body)
        rendered = fc.render_report(report, "boostgauge #7")

        assert report.ears_ran is False
        assert report.requirements_examined == 0
        assert (
            "0 requirement sentences examined out of 0; EARS check did not run."
            in rendered
        )

    def test_its_row_criteria_are_not_ears_validated(self, boostgauge_body):
        """Row criteria take the row form and are exempt (ADR 0226 3.2).

        Every one of this issue's twenty-one criteria would fail EARS. If the
        checker ever reads acceptance criteria as requirement sentences, the
        live positive fixture turns into a wall of violations.
        """
        report = fc.check_form(boostgauge_body)

        assert report.criteria_examined == 21
        assert "ears" not in kinds(report)


# ---------------------------------------------------------------------------
# Exact mode
# ---------------------------------------------------------------------------


class TestExactMode:
    def test_it_passes(self, ids_body):
        report = fc.check_form(ids_body)
        assert report.ok, details(report)

    def test_join_is_exact_and_named(self, ids_body):
        report = fc.check_form(ids_body)
        rendered = fc.render_report(report, "cache")

        assert report.tables[0].exact_join
        assert "row join: exact (IDs)" in rendered
        assert "delegated to the semantic gate" not in rendered

    def test_all_five_ears_patterns_are_accepted(self, ids_body):
        report = fc.check_form(ids_body)

        assert report.ears_ran
        assert report.requirements_examined == 5
        assert "ears" not in kinds(report)

    def test_dropped_row_fails(self, ids_body):
        """A row deleted from the grid: incomplete, and its criterion orphaned."""
        broken = ids_body.replace("| E3 | yes | no | retained |\n", "")

        report = fc.check_form(broken)

        assert not report.ok
        assert "table-rows" in kinds(report)
        assert "row-criterion" in kinds(report)
        assert "E3" in details(report)

    def test_dropped_criterion_fails(self, ids_body):
        broken = ids_body.replace(
            "- [ ] E3. Pinned, not over limit: the entry is retained\n", ""
        )

        report = fc.check_form(broken)

        assert not report.ok
        assert "row-criterion" in kinds(report)
        assert "E3 has no acceptance criterion" in details(report)

    def test_duplicated_id_fails(self, ids_body):
        broken = ids_body.replace("| E3 | yes | no |", "| E2 | yes | no |")

        report = fc.check_form(broken)

        assert not report.ok
        assert "table-duplicate" in kinds(report)
        assert "row ID E2 is used twice in this table" in details(report)

    def test_wrong_outcome_criterion_fails(self, ids_body):
        """The criterion names row E2 but carries row E1's outcome."""
        broken = ids_body.replace(
            "- [ ] E2. Not pinned, over limit: the entry is evicted",
            "- [ ] E2. Not pinned, over limit: the entry is retained",
        )

        report = fc.check_form(broken)

        assert not report.ok
        assert "row-criterion" in kinds(report)
        assert "does not carry its row's outcome" in details(report)

    def test_criterion_naming_a_row_that_does_not_exist_fails(self, ids_body):
        broken = ids_body.replace(
            "- [ ] E4. Pinned, over limit:",
            "- [ ] E9. Pinned, over limit:",
        )

        report = fc.check_form(broken)

        assert not report.ok
        assert "E9 names a row this table does not contain" in details(report)

    def test_ids_must_be_unique_across_the_issue(self, ids_body):
        second_table = (
            "\n| ID | Flushed? | Dirty? | Buffer after the sweep |\n"
            "|---|---|---|---|\n"
            "| E1 | no | no | kept |\n"
            "| E2 | no | yes | kept |\n"
            "| E3 | yes | no | dropped |\n"
            "| E4 | yes | yes | dropped |\n"
        )
        broken = ids_body.replace("\n## Acceptance Criteria", second_table + "\n## Acceptance Criteria")

        report = fc.check_form(broken)

        assert "table-duplicate" in kinds(report)
        assert "already by table" in details(report)


# ---------------------------------------------------------------------------
# EARS (acceptance criterion 1)
# ---------------------------------------------------------------------------


def _with_requirements(*bullets: str) -> str:
    body = "## Requirements\n\n"
    body += "".join(f"- {b}\n" for b in bullets)
    return body


class TestEars:
    @pytest.mark.parametrize(
        "sentence",
        [
            "The system shall write the file on exit.",
            "WHEN the user quits the system shall write the file.",
            "WHILE a write is in flight the system shall reject a second write.",
            "IF the file is unreadable THEN the system shall report the error.",
            "WHERE metrics are enabled the system shall count each write.",
        ],
    )
    def test_each_pattern_is_accepted(self, sentence):
        report = fc.check_form(_with_requirements(sentence))

        assert report.ok, details(report)
        assert report.requirements_examined == 1

    @pytest.mark.parametrize(
        "sentence",
        [
            "Config is saved when the app exits.",
            "The system writes the file on exit.",
            "When the user quits the system shall write the file.",
            "Save the position.",
        ],
    )
    def test_a_sentence_matching_no_pattern_is_reported(self, sentence):
        report = fc.check_form(_with_requirements(sentence))

        assert not report.ok
        assert kinds(report) == ["ears"]
        assert "matches no EARS pattern" in details(report)

    def test_the_violation_names_the_offending_sentence_and_its_position(self):
        report = fc.check_form(
            _with_requirements(
                "The system shall start.",
                "Config is saved on exit.",
            )
        )

        assert len(report.violations) == 1
        assert report.violations[0].where == "Requirements bullet 2"
        assert "Config is saved on exit." in report.violations[0].detail

    def test_nested_bullets_are_counted_not_checked(self):
        body = (
            "## Requirements\n\n"
            "- The system shall write the file on exit.\n"
            "  - only the keys the user changed\n"
        )

        report = fc.check_form(body)

        assert report.ok
        assert report.requirements_examined == 1
        assert report.nested_bullets_skipped == 1
        assert "1 nested bullet(s)" in fc.render_report(report, "x")

    def test_a_parenthetical_suffix_is_the_marked_section(self):
        """'## Requirements (EARS)' is the Requirements section (#2465).

        boostgauge #331 and #332 carried exactly this heading and were
        reported form-checker PASS with zero sentences examined. The
        parenthetical names the notation -- a strictly more informative
        heading must not silently downgrade the check to nothing. (This
        flips the earlier exact-equality pin, which treated
        '## Requirements (draft)' as unmarked; examining a draft section
        is strictly safer than examining nothing.)
        """
        body = (
            "## Requirements (EARS)\n\n"
            "- The system shall render the bezel.\n"
            "- The dial is offset from the tick.\n"
        )

        report = fc.check_form(body)

        assert report.ears_ran is True
        assert report.requirements_examined == 2

    def test_the_bare_heading_still_matches(self):
        """boostgauge #2's form: the control that always worked."""
        body = "## Requirements\n\n- The system shall start.\n"

        report = fc.check_form(body)

        assert report.ears_ran is True
        assert report.requirements_examined == 1

    def test_a_non_parenthetical_divergence_is_not_the_section(self):
        """'## Requirements Analysis' is a genuinely different section."""
        body = "## Requirements Analysis\n\n- Config is saved on exit.\n"

        report = fc.check_form(body)

        assert report.ears_ran is False
        assert report.ok

    def test_the_parenthetical_must_be_a_suffix_of_the_exact_heading(self):
        """'## Requirement (EARS)' (singular) is not a match either."""
        body = "## Requirement (EARS)\n\n- Config is saved on exit.\n"

        report = fc.check_form(body)

        assert report.ears_ran is False
        assert report.ok

    def test_the_section_ends_at_the_next_heading(self):
        body = (
            "## Requirements\n\n"
            "- The system shall start.\n\n"
            "## Notes\n\n"
            "- this bullet is not a requirement\n"
        )

        report = fc.check_form(body)

        assert report.requirements_examined == 1
        assert report.ok


# ---------------------------------------------------------------------------
# Table completeness and disjointness (acceptance criteria 2 and 3)
# ---------------------------------------------------------------------------


def _table(rows: str, header: str = "| A? | B? | Result |") -> str:
    return (
        f"{header}\n|---|---|---|\n{rows}\n"
        "\n## Acceptance Criteria\n\n"
        "- [ ] Result, a, b: kept\n"
    )


class TestTableShape:
    def test_missing_row_is_reported(self):
        body = _table(
            "| no | no | kept |\n| no | yes | kept |\n| yes | no | kept |"
        )

        report = fc.check_form(body)

        assert "table-rows" in kinds(report)
        assert "2 binary conditions require 2^2 = 4 rows; it carries 3" in details(
            report
        )

    def test_extra_row_is_reported(self):
        body = _table(
            "| no | no | kept |\n| no | yes | kept |\n"
            "| yes | no | kept |\n| yes | yes | kept |\n| yes | yes | dropped |"
        )

        report = fc.check_form(body)

        assert "table-rows" in kinds(report)
        assert "it carries 5" in details(report)

    def test_repeated_combination_is_reported(self):
        body = _table(
            "| no | no | kept |\n| no | no | dropped |\n"
            "| yes | no | kept |\n| yes | yes | kept |"
        )

        report = fc.check_form(body)

        assert "table-duplicate" in kinds(report)
        assert "rows 1 and 2 repeat the same combination" in details(report)

    def test_three_conditions_require_eight_rows(self, boostgauge_body):
        report = fc.check_form(boostgauge_body)
        size = [t for t in report.tables if t.subject == "size"][0]

        assert size.condition_count == 3
        assert size.expected_rows == 8

    def test_a_table_that_is_not_binary_is_not_a_decision_table(self):
        body = (
            "| Risk | Impact | Mitigation |\n|---|---|---|\n"
            "| a | Med | review |\n| b | Low | none |\n"
        )

        report = fc.check_form(body)

        assert report.tables == []
        assert report.non_decision_tables == 1
        assert "not decision tables" in fc.render_report(report, "x")


# ---------------------------------------------------------------------------
# Row-to-criterion coverage in no-ID mode (acceptance criterion 4)
# ---------------------------------------------------------------------------


class TestNoIdJoin:
    BODY = (
        "| Reset? | Moved? | `position` after quit |\n|---|---|---|\n"
        "| no | no | unchanged |\n"
        "| no | yes | the new position |\n"
        "| yes | no | default |\n"
        "| yes | yes | the new position |\n"
        "\n## Acceptance Criteria\n\n"
        "- [ ] Position, no reset, not moved: `position` unchanged\n"
        "- [ ] Position, no reset, moved: `position` holds the new position\n"
        "- [ ] Position, reset, not moved: `position` holds the default\n"
        "- [ ] Position, reset, moved: `position` holds the new position\n"
    )

    def test_the_group_passes(self):
        report = fc.check_form(self.BODY)
        assert report.ok, details(report)

    def test_a_missing_criterion_fails_on_count_and_on_outcome(self):
        broken = self.BODY.replace(
            "- [ ] Position, reset, not moved: `position` holds the default\n", ""
        )

        report = fc.check_form(broken)

        assert not report.ok
        assert "4 rows require exactly 4 acceptance criteria" in details(report)
        assert "no unclaimed criterion" in details(report)

    def test_a_criterion_with_the_wrong_outcome_fails(self):
        broken = self.BODY.replace(
            "Position, reset, not moved: `position` holds the default",
            "Position, reset, not moved: `position` holds the previous value",
        )

        report = fc.check_form(broken)

        assert not report.ok
        assert "row 3 states 'default'" in details(report)

    def test_duplicate_outcomes_need_distinct_criteria(self):
        """Two rows sharing an outcome cannot both claim one criterion."""
        broken = self.BODY.replace(
            "- [ ] Position, reset, moved: `position` holds the new position",
            "- [ ] Position, reset, moved: `position` holds whatever it held",
        )

        report = fc.check_form(broken)

        assert not report.ok
        assert "the new position" in details(report)

    def test_nested_outcomes_are_matched_by_maximum_matching(self):
        """'unchanged' is a substring of 'unchanged; the CLI value is not written'.

        Greedy assignment in row order consumes the longer criterion for the
        shorter row and then reports a false gap. This is the boostgauge #7
        size table's exact shape, reduced.
        """
        body = (
            "| A? | `size` after quit |\n|---|---|\n"
            "| no | unchanged |\n"
            "| yes | unchanged; the CLI value is not written |\n"
            "\n## Acceptance Criteria\n\n"
            "- [ ] Size, no flag: `size` unchanged\n"
            "- [ ] Size, flag: `size` unchanged; the CLI value is not written\n"
        )

        report = fc.check_form(body)

        assert report.ok, details(report)

    def test_no_criteria_section_is_reported_not_ignored(self):
        body = (
            "| A? | B? | Result |\n|---|---|---|\n"
            "| no | no | kept |\n| no | yes | kept |\n"
            "| yes | no | kept |\n| yes | yes | kept |\n"
        )

        report = fc.check_form(body)

        assert not report.ok
        assert "no '## Acceptance Criteria' section" in details(report)
        assert report.criteria_section_found is False


# ---------------------------------------------------------------------------
# Output honesty (acceptance criterion 5)
# ---------------------------------------------------------------------------


class TestReportHonesty:
    def test_a_clean_report_still_names_what_it_did_not_verify(self, ids_body):
        rendered = fc.render_report(fc.check_form(ids_body), "cache")

        assert "RESULT: PASS" in rendered
        assert "Not verified" in rendered
        assert "states the CORRECT" in rendered

    def test_it_never_claims_correctness(self, boostgauge_body):
        rendered = fc.render_report(fc.check_form(boostgauge_body), "boostgauge #7")

        assert "enumerate every combination and be wrong in every row" in rendered

    def test_counts_carry_denominators(self, ids_body):
        rendered = fc.render_report(fc.check_form(ids_body), "cache")

        assert "5 of 5 requirement sentences" in rendered
        assert "4 of 4 required rows" in rendered
        assert "4 of 4 rows joined to a criterion" in rendered

    def test_an_empty_document_reports_zeroes_with_denominators(self):
        report = fc.check_form("# just a title\n")
        rendered = fc.render_report(report, "empty")

        assert report.ok
        assert "0 requirement sentences examined out of 0" in rendered
        assert "Decision tables: 0 found, so 0 checked." in rendered

    def test_failures_are_listed_with_their_location(self):
        report = fc.check_form(_with_requirements("Config is saved on exit."))
        rendered = fc.render_report(report, "x")

        assert "RESULT: FAIL -- 1 violation(s)." in rendered
        assert "[ears] Requirements bullet 1" in rendered

    def test_the_checker_is_deterministic(self, boostgauge_body):
        first = fc.render_report(fc.check_form(boostgauge_body), "b")
        second = fc.render_report(fc.check_form(boostgauge_body), "b")

        assert first == second


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def _cli(self):
        import check_requirements_form

        return check_requirements_form

    def test_passing_file_exits_zero(self, capsys):
        code = self._cli().main(["--file", str(BOOSTGAUGE_7)])

        assert code == 0
        assert "RESULT: PASS" in capsys.readouterr().out

    def test_violations_exit_one(self, tmp_path, capsys):
        bad = tmp_path / "bad.md"
        bad.write_text(_with_requirements("Config is saved on exit."), encoding="utf-8")

        code = self._cli().main(["--file", str(bad)])

        assert code == 1
        assert "RESULT: FAIL" in capsys.readouterr().out

    def test_missing_file_exits_two(self, tmp_path, capsys):
        code = self._cli().main(["--file", str(tmp_path / "nope.md")])

        assert code == 2
        assert "has been verified" in capsys.readouterr().err

    def test_empty_body_exits_two(self, tmp_path, capsys):
        blank = tmp_path / "blank.md"
        blank.write_text("   \n", encoding="utf-8")

        code = self._cli().main(["--file", str(blank)])

        assert code == 2
        assert "nothing to check" in capsys.readouterr().err

    def test_issue_path_reads_through_gh(self, tmp_path, monkeypatch, capsys):
        cli = self._cli()
        monkeypatch.setattr(
            cli,
            "fetch_issue",
            lambda repo, issue: ("t", BOOSTGAUGE_7.read_text(encoding="utf-8")),
        )

        code = cli.main(["--repo", str(tmp_path), "--issue", "7"])

        assert code == 0
        assert "RESULT: PASS" in capsys.readouterr().out


class TestARequirementSentenceCarriesNoId:
    """The #2368 ruling.

    Converting boostgauge #1 read section 3.2's row-ID convention and ADR 0228's
    group prefix as a general tagging rule, tagged the requirement sentences,
    and read the rejections as the two ADRs contradicting each other. They do
    not: an ID is a join key, and a requirement sentence joins to nothing.

    The matcher therefore does not strip the prefix. What it must do is tell the
    two failures apart, because a tagged-but-good sentence and a malformed one
    need different repairs.
    """

    WORN = [
        "R1 — The renderer shall place the needle at the value's angle.",
        "R2. WHEN the value changes the renderer shall redraw the needle.",
        "R3: WHILE a redraw is in flight the renderer shall drop further updates.",
        "R4) IF the value is out of range THEN the renderer shall clamp it.",
        "R5 WHERE the telltale is enabled the renderer shall draw it behind it.",
    ]

    @pytest.mark.parametrize("sentence", WORN)
    def test_a_worn_id_is_detected(self, sentence):
        assert fc.worn_criterion_id(sentence) == sentence[:2]

    @pytest.mark.parametrize("sentence", WORN)
    def test_the_same_sentence_passes_once_the_prefix_goes(self, sentence):
        """The falsifier. If these did not pass unprefixed, the fixture would be
        testing bad sentences and the ID would be beside the point."""
        bare = fc._WORN_ID.match(sentence).group(2)
        report = fc.check_form(f"## Requirements\n\n- {bare}\n")
        assert kinds(report) == [], f"{bare!r} should be valid EARS on its own"

    def test_an_untagged_sentence_is_not_read_as_tagged(self):
        assert fc.worn_criterion_id("The renderer shall draw.") is None

    def test_a_malformed_sentence_is_not_read_as_tagged(self):
        """No modal verb, so there is no good sentence hiding under a prefix."""
        assert fc.worn_criterion_id("R1 — the needle moves sometimes.") is None

    @pytest.mark.parametrize(
        "sentence",
        [
            "IPv4 addresses shall be accepted.",  # letters+digits, but not an ID
            "R2D2 shall respond to its name.",
            "WHEN1 the value changes the system shall redraw.",
        ],
    )
    def test_an_id_shaped_word_that_is_part_of_the_sentence_is_not_stripped(
        self, sentence
    ):
        assert fc.worn_criterion_id(sentence) is None


class TestTheTwoFailuresReadDifferently:
    def test_a_worn_id_says_so(self):
        report = fc.check_form(
            "## Requirements\n\n- R1 — The renderer shall draw the needle.\n"
        )
        (violation,) = report.violations
        assert violation.kind == "ears"
        assert "'R1'" in violation.detail
        assert "criterion ID" in violation.detail
        assert "drop the prefix" in violation.detail

    def test_a_malformed_sentence_still_gets_the_pattern_list(self):
        report = fc.check_form("## Requirements\n\n- The needle moves.\n")
        (violation,) = report.violations
        assert violation.kind == "ears"
        assert "matches no EARS pattern" in violation.detail
        assert "criterion ID" not in violation.detail

    def test_a_tagged_malformed_sentence_is_reported_as_malformed(self):
        """A prefix does not excuse the sentence under it, and the advice to
        drop four characters would be wrong here -- there is nothing beneath."""
        report = fc.check_form("## Requirements\n\n- R1 — The needle moves.\n")
        (violation,) = report.violations
        assert "matches no EARS pattern" in violation.detail
        assert "criterion ID" not in violation.detail


class TestTheRulingLeavesTheJoinAlone:
    """An ID still means what it meant everywhere it is actually a join key."""

    @pytest.fixture(scope="class")
    def worn_body(self) -> str:
        return (FIXTURES / "ears-worn-id.md").read_text(encoding="utf-8")

    def test_every_requirement_sentence_is_flagged_as_wearing_an_id(
        self, worn_body
    ):
        report = fc.check_form(worn_body)
        ears = [v for v in report.violations if v.kind == "ears"]
        assert len(ears) == 5
        assert all("criterion ID" in v.detail for v in ears)

    def test_the_row_to_criterion_join_still_succeeds(self, worn_body):
        """The criteria in that same fixture are correctly tagged, and the join
        they exist for is untouched by the ruling above."""
        report = fc.check_form(worn_body)
        assert [v for v in report.violations if v.kind == "row-criterion"] == []
        assert [v for v in report.violations if v.kind.startswith("table-")] == []
        assert report.tables and all(t.exact_join for t in report.tables)

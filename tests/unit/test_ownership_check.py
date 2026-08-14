"""Unit tests for the ADR 0228 variable-ownership checker (#2315).

The kill test from ADR 0228 section 4, executed. Four fixtures reconstruct the
2026-08-13 conflicts from the gate's own verbatim text, and each must be caught
by the clause the ADR names for it. A fifth fixture is the same material
written under the discipline and must report nothing, because a checker whose
passing result has never been made to fail is not a check.

`boostgauge-7-retrofit.md` is the real-document case: issue #7's body as it
stood on 2026-08-14, after the retrofit that gave it row IDs and a State
Variables and Ownership section. It is frozen here rather than fetched, so the
suite pins what the checker said about a document that exists.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.workflows.requirements import form_check as fc  # noqa: E402
from assemblyzero.workflows.requirements import ownership_check as oc  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "requirements" / "ownership"


def body(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def kinds(report: fc.FormReport) -> list[str]:
    return [v.kind for v in report.violations]


def ownership_kinds(report: fc.FormReport) -> list[str]:
    return [k for k in kinds(report) if k.startswith("ownership-")]


def details(report: fc.FormReport, kind: str) -> str:
    """Every finding of one kind, rendered whole so `where` is assertable too."""
    return " || ".join(str(v) for v in report.violations if v.kind == kind)


# ---------------------------------------------------------------------------
# The kill test (ADR 0228 section 4), one fixture per clause
# ---------------------------------------------------------------------------


class TestKillTest:
    def test_290_unscoped_blanket_dies_by_clause_3(self):
        report = fc.check_form(body("bg-290-unscoped-blanket.md"))

        assert "ownership-universal" in ownership_kinds(report)
        detail = details(report, "ownership-universal")
        assert "'only'" in detail
        assert "E1" in detail

    def test_290s_only_is_not_rescued_by_a_later_while(self):
        """The trailing "while the app ran" qualifies the direct file edit.

        This is how #290 survived review: a condition marker sits in the same
        sentence as the universal, four clauses after it, conditioning
        something else entirely. A scope check that searched the whole claim
        would pass this and the corpus would keep one member.
        """
        text = (
            "E1. The exit write touches only hand-changed keys: a direct file "
            "edit made while the app ran survives an exit"
        )
        assert oc._unscoped_universals(oc._norm(text)) == ["only"]

    def test_291_undefined_extension_dies_by_clauses_1_and_2(self):
        report = fc.check_form(body("bg-291-undefined-extension.md"))
        found = ownership_kinds(report)

        assert "ownership-undeclared" in found
        assert "telltale_windows.short" in details(report, "ownership-undeclared")

        assert "ownership-non-owner" in found
        assert "`thresholds`" in details(report, "ownership-non-owner")

    def test_292_undefined_boundary_term_dies_by_clause_4(self):
        report = fc.check_form(body("bg-292-boundary-term.md"))

        assert "ownership-boundary" in ownership_kinds(report)
        assert "'threshold'" in details(report, "ownership-boundary")

    def test_294_annexation_dies_by_clause_2(self):
        report = fc.check_form(body("bg-294-annexation.md"))

        assert "ownership-non-owner" in ownership_kinds(report)
        detail = details(report, "ownership-non-owner")
        assert "`theme`" in detail
        assert "`size`" in detail
        assert "owned by E" in detail

    @pytest.mark.parametrize(
        "fixture",
        [
            "bg-290-unscoped-blanket.md",
            "bg-291-undefined-extension.md",
            "bg-292-boundary-term.md",
            "bg-294-annexation.md",
        ],
    )
    def test_every_corpus_fixture_is_caught(self, fixture):
        report = fc.check_form(body(fixture))
        assert ownership_kinds(report), f"{fixture} escaped every clause"


# ---------------------------------------------------------------------------
# The negative half
# ---------------------------------------------------------------------------


class TestCleanDocument:
    def test_the_discipline_applied_reports_nothing(self):
        report = fc.check_form(body("clean-ownership.md"))
        assert ownership_kinds(report) == [], details(report, "ownership-boundary")

    def test_a_citation_is_not_an_assertion(self):
        """R2 names no owned key's value; it points at the exit-write criteria.

        This is the whole of clause 2. If the citation form were read as an
        assertion, the discipline would forbid a non-owner from mentioning a
        variable at all, which no requirement can be written under.
        """
        report = fc.check_form(body("clean-ownership.md"))
        assert "ownership-non-owner" not in ownership_kinds(report)

    def test_removing_the_citation_makes_it_a_violation(self):
        clean = body("clean-ownership.md")
        broken = clean.replace(
            "what the file holds afterwards is governed by the exit-write criteria",
            "`theme` holds the edited value at the next launch",
        )
        assert broken != clean

        report = fc.check_form(broken)
        assert "ownership-non-owner" in ownership_kinds(report)

    def test_a_declared_boundary_term_is_accepted(self):
        """"hand-changed" partitions the keys and is not itself a variable.

        boostgauge #290 turned on whether a direct file edit counts as one, so
        the term needs a membership test. The Boundary term line is where a
        test that is not a variable row goes.
        """
        clean = body("clean-ownership.md")
        assert "ownership-boundary" not in ownership_kinds(fc.check_form(clean))

        stripped = "\n".join(
            line for line in clean.splitlines() if not line.startswith("Boundary term")
        )
        assert "ownership-boundary" in ownership_kinds(fc.check_form(stripped))


# ---------------------------------------------------------------------------
# The vacuous states -- two of them, and neither is a pass
# ---------------------------------------------------------------------------


class TestVacuousStates:
    def test_no_variable_table_says_so(self):
        report = fc.check_form(
            "## Acceptance Criteria\n\n- [ ] E1. `theme` holds its value\n"
        )

        assert not report.ownership.table_found
        assert not report.ownership.ran
        assert ownership_kinds(report) == []

        text = fc.render_report(report, "x")
        assert "Ownership was not checked: no variable table exists" in text
        assert "vacuous result, not a pass" in text

    def test_no_variable_table_never_reads_as_an_ownership_pass(self):
        """The failure this disclosure exists to prevent (#2227).

        The document below is silent about ownership. A report saying only
        "PASS" would be read as a clean bill by anyone skimming, and the
        checker would be asserting something it never looked at.
        """
        report = fc.check_form("## Acceptance Criteria\n\n- [ ] one thing\n")
        text = fc.render_report(report, "x")

        assert "PASS" in text
        assert "Ownership was not checked" in text

    def test_a_prose_owner_table_is_disclosed_not_flooded(self):
        """The real-document state, and the reason it is a third state.

        A table whose owners are prose declares ownership honestly and gives a
        checker nothing to join a criterion to. Running clause 2 against it
        reports every criterion in the document, which is a finding about the
        table's form dressed up as twenty-nine findings about its ownership.
        """
        report = fc.check_form(body("boostgauge-7-retrofit.md"))

        assert report.ownership.table_found
        assert not report.ownership.joinable
        assert not report.ownership.ran
        assert "ownership-non-owner" not in ownership_kinds(report)
        assert "ownership-undeclared" not in ownership_kinds(report)

        text = fc.render_report(report, "boostgauge #7")
        assert "Ownership was NOT checked per criterion" in text
        assert "vacuous result, not a pass" in text


# ---------------------------------------------------------------------------
# The real document
# ---------------------------------------------------------------------------


class TestRetrofittedBoostgaugeSeven:
    def test_it_declares_four_variables(self):
        report = fc.check_form(body("boostgauge-7-retrofit.md"))
        assert len(report.ownership.variables) == 4

    def test_two_rows_name_more_than_one_owner(self):
        """Clause 1's one-owner rule, decidable even without group tags.

        A criterion ID gives its group away by prefix, so a cell citing
        P1-P4 and S1-S8 names two groups whatever its prose says. A semicolon
        separates owners. Both are facts about the cell, not readings of it.
        """
        report = fc.check_form(body("boostgauge-7-retrofit.md"))
        table_findings = [
            v for v in report.violations if v.kind == "ownership-table"
        ]

        assert len(table_findings) == 2
        detail = " || ".join(v.detail for v in table_findings)
        assert "File content per key at quit" in detail
        assert "Running-session values" in detail
        assert "names 2 owner groups" in detail
        assert "names 3 owner groups" in detail

    def test_it_carries_three_unscoped_universals(self):
        report = fc.check_form(body("boostgauge-7-retrofit.md"))
        universals = [
            v for v in report.violations if v.kind == "ownership-universal"
        ]
        assert len(universals) == 3

    def test_the_whole_report_is_five_findings_not_twenty_nine(self):
        """The measurement that shaped the third state.

        Before the prose-owner state existed, this document produced 29
        findings, 24 of them restatements of "your owners are prose". A check
        that floods is one people stop reading, and this number is the
        regression guard on that.
        """
        report = fc.check_form(body("boostgauge-7-retrofit.md"))
        assert len(ownership_kinds(report)) == 5


# ---------------------------------------------------------------------------
# One pass, every violation (#2239)
# ---------------------------------------------------------------------------


class TestOnePass:
    def test_all_five_checks_report_together(self):
        """One revision addresses the set, so all five must run every time."""
        text = (
            "## Variables\n\n"
            "| Variable | Extension | Owner |\n|---|---|---|\n"
            "| `theme` | the `theme` key | `E` (the exit-write criteria) |\n"
            "| `theme` | the `theme` key | `R` (the re-read criteria) |\n"
            "| `size` |  | `E` (the exit-write criteria) |\n"
            "\n## Acceptance Criteria\n\n"
            "- [ ] R1. `theme` always holds the default\n"
            "- [ ] R2. `opacity` holds the file value\n"
            "- [ ] R3. A non-visual key is left alone\n"
        )
        report = fc.check_form(text)
        found = set(ownership_kinds(report))

        assert "ownership-table" in found        # duplicate row, empty extension
        assert "ownership-non-owner" in found    # R1 states `theme`, owned by E
        assert "ownership-undeclared" in found   # R2 states undeclared `opacity`
        assert "ownership-boundary" in found     # "non-visual key"
        assert "ownership-universal" in found    # "always" with no scope

    def test_it_is_deterministic(self):
        text = body("bg-294-annexation.md")
        first = [str(v) for v in fc.check_form(text).violations]
        second = [str(v) for v in fc.check_form(text).violations]
        assert first == second


# ---------------------------------------------------------------------------
# Scope-marker behaviour, where the false-positive risk lives
# ---------------------------------------------------------------------------


class TestUniversalScoping:
    @pytest.mark.parametrize(
        "claim",
        [
            "only hand-changed keys are written",
            "the file is byte-identical after quit",
            "nothing else touches the config file",
            "the app never writes CLI values",
        ],
    )
    def test_a_bare_universal_is_flagged(self, claim):
        assert oc._unscoped_universals(oc._norm(claim))

    @pytest.mark.parametrize(
        "claim",
        [
            "when the app exits, only hand-changed keys are written",
            "only hand-changed keys are written, unless the user reset the config",
            "nothing other than the launch read touches the config file",
            "the file is byte-identical, except where a direct edit occurred",
            "while the app runs it never writes, governed by the exit-write criteria",
        ],
    )
    def test_a_scoped_universal_is_not(self, claim):
        assert oc._unscoped_universals(oc._norm(claim)) == []


class TestBoundaryTermExtraction:
    @pytest.mark.parametrize(
        "phrase,expected",
        [
            ("a non-threshold key", "threshold"),
            ("threshold values", "threshold"),
            ("hand-changed keys", "hand-changed"),
            ("the edited value", ""),      # a participle points back, partitions nothing
            ("these values", ""),          # a stopword, not a term
        ],
    )
    def test_only_real_partitions_survive(self, phrase, expected):
        table = (
            "| Variable | Extension | Owner |\n|---|---|---|\n"
            "| `theme` | the `theme` key | `E` (the exit criteria) |\n"
        )
        text = f"## Variables\n\n{table}\n## Acceptance Criteria\n\n- [ ] E1. {phrase}\n"
        report = fc.check_form(text)
        terms = report.ownership.boundary_terms

        if expected:
            assert terms == [expected]
        else:
            assert terms == []

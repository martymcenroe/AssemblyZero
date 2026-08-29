"""An element named in scope prose reaches a row, an alias, or an exclusion.

boostgauge #331's title said "bezel" through nineteen ruled conflicts. Its
decision table carried `S9 | Bezel seat` -- the seat shadow, not the ring --
and every gate this campaign built audits rows that EXIST, so nothing asked.
The factory ran the nine-row table through fourteen gates with perfect fidelity
and built a face with no bezel (boostgauge #375).

`TestNoNameMatcherSeparatesThem` is the finding this module's design rests on,
kept as a program: the covering case and the near-miss are structurally
identical strings, so the two matchers that read as most helpful both pass
#331 unchanged. Everything else here is downstream of it.

The #331 excerpts below are VERBATIM from the preserved issue body. They are
the evidence, not a paraphrase of it.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.implementation_spec.assertion_manifest import (
    is_criteria_table,
)
from assemblyzero.workflows.requirements import form_gate
from assemblyzero.workflows.requirements.form_gate import check_form_at_preflight
from assemblyzero.workflows.requirements.form_check import (
    check_form,
    is_decision_table,
    parse_tables,
    render_report,
)
from assemblyzero.workflows.requirements.scope_coverage import (
    check_scope_coverage,
    declared_aliases,
    declared_exclusions,
    element_rows,
    scope_sentence_elements,
    title_elements,
)

# ---------------------------------------------------------------------------
# boostgauge #331, verbatim
# ---------------------------------------------------------------------------

TITLE_331 = (
    "feat: static face renderer — bezel, chrome housing, dial, ticks, "
    "numerals, wordmark, screws — baked once, cached"
)

LEDE_331 = (
    "Render the complete static face of the Stingray gauge — everything that "
    "never moves — as one cached `PIL.Image`. Per the render-architecture "
    "ruling (#329) this is the baked half of the renderer: bezel, chrome "
    "housing, dial face, redline band, tick marks, numerals, wordmark, and "
    "screws. No needles and NO pivot cap -- the cap covers the attachment "
    "point of all five needles, so it draws on top of them and belongs to "
    "#332 (ruling on the #333 conflict) — the main needle belongs to #332, "
    "telltales to #2.\n"
)

#: The nine-row S-table, element and ID columns verbatim; binding and assertion
#: cells abbreviated where this module never reads them. S1's cell keeps its
#: "NO gradient" phrasing, which is the control for the exclusion scan.
TABLE_331 = """
## Decision table — static elements and their binding values

| ID | Element | Binding value (quoted from the render contract) | Assertion method |
|---|---|---|---|
| S1 | Dial face | flat `#0A0A0C`, radius R = 0.40 × size; NO gradient, glass sweep, or reflection (#325) | classification at 3 interior points |
| S2 | Redline band | `#AA0F19` crimson, inner 0.88 R to outer 1.00 R | classification at radius 0.94 R |
| S3 | Major ticks | `#FFFFFF`, 11 total at values 0,10,…,100 | stroke predicate at each tick's midpoint |
| S4 | Minor ticks | `#FFFFFF`, 40 total, 4 between each major pair | stroke predicate at 4 sampled minors |
| S5 | Numerals | `#FFFFFF`, values 0–100 step 10, cap height 0.11 R | presence: ≥1 white-classified pixel |
| S6 | Wordmark | `BOOSTGAUGE`, `#FFFFFF`, cap height 0.09 R | presence: ≥1 white-classified pixel |
| S7 | Chrome housing | square, chamfer radius 0.13 × size | the #328 predicate: ≥3 achromatic samples |
| S8 | Screws | 2, centres at pivot + (−0.25 R, 0) and (+0.25 R, 0) | the #326 predicate: centre pixel within ±6 |
| S9 | Bezel seat | dial sits below the bezel plane — the slight inner shadow on the annulus containing 1.01 R | sample at 1.01 R is darker than chrome at 1.10 R |

## Boundary terms

- **Needles** — main needle is the sibling needle issue's; telltales are #2's.
- **Caching lifetime and invalidation policy** — this issue caches per (size, skin) per session.
"""

BODY_331 = LEDE_331 + TABLE_331


@pytest.fixture
def report_331():
    return check_scope_coverage(TITLE_331, BODY_331)


# ---------------------------------------------------------------------------
# The finding the design rests on
# ---------------------------------------------------------------------------


class TestNoNameMatcherSeparatesThem:
    """`Dial face` covers `dial`; `Bezel seat` does not cover `bezel`.

    Same shape, opposite answers -- so the coverage judgement cannot be made
    from names, and the matchers that look most helpful are the ones that ship
    the defect.
    """

    def _norm_tokens(self, text: str) -> set[str]:
        return set(text.lower().replace("-", " ").split())

    def test_the_two_decisive_strings_are_structurally_identical(self) -> None:
        covering = self._norm_tokens("Dial face")
        near_miss = self._norm_tokens("Bezel seat")
        assert len(covering) == len(near_miss) == 2
        # modifier + head, in both, with the extracted term as the modifier
        assert "dial" in covering and "bezel" in near_miss

    def test_substring_matching_would_pass_the_acceptance_case(self) -> None:
        """The measured FALSE PASS. This is why exact matching was chosen."""
        rows = list(element_rows(BODY_331))
        assert any("bezel" in row for row in rows), "S9 does contain the word"
        # ...and yet the ring is bound nowhere: no row NAMES the bezel.
        assert "bezel" not in rows

    def test_token_subset_matching_would_pass_the_acceptance_case(self) -> None:
        rows = list(element_rows(BODY_331))
        subset_hits = [
            row for row in rows if {"bezel"} <= self._norm_tokens(row)
        ]
        assert subset_hits == ["bezel seat"], (
            "token-subset finds S9 for 'bezel', which is the false pass"
        )

    def test_exact_matching_does_not(self, report_331) -> None:
        assert "bezel" not in report_331.matched


# ---------------------------------------------------------------------------
# The acceptance: #331 replayed
# ---------------------------------------------------------------------------


class TestThe331Acceptance:
    def test_the_gate_fires_naming_bezel(self, report_331) -> None:
        assert not report_331.ok
        fired = {v.where.split(" (")[0] for v in report_331.violations}
        assert "bezel" in fired

    def test_the_bezel_finding_says_a_mention_is_not_a_binding(
        self, report_331
    ) -> None:
        finding = next(
            v for v in report_331.violations if v.where.startswith("bezel")
        )
        assert "merely mentions" in finding.detail
        assert finding.kind == "scope-uncovered"

    def test_the_pivot_cap_exclusion_passes_as_the_control(self) -> None:
        """The declared-exclusion control, from #331's own prose."""
        exclusions = declared_exclusions(BODY_331)
        assert "pivot cap" in exclusions
        assert "belongs to" in exclusions["pivot cap"]

    def test_needles_is_excluded_too_by_the_same_clause(self) -> None:
        assert "needles" in declared_exclusions(BODY_331)

    def test_every_element_with_a_row_passes(self, report_331) -> None:
        assert report_331.matched == {
            "chrome housing": "S7",
            "numerals": "S5",
            "wordmark": "S6",
            "screws": "S8",
            "dial face": "S1",
            "redline band": "S2",
        }

    def test_it_fires_on_exactly_two_things(self, report_331) -> None:
        """One shipped defect, one wording gap discharged by a single alias.

        Stated as an exact set because a gate that names nine elements when one
        is missing is a gate people wave through.
        """
        fired = {v.where.split(" (")[0] for v in report_331.violations}
        assert fired == {"bezel", "tick marks"}

    def test_the_coarser_title_wording_is_not_a_second_finding(
        self, report_331
    ) -> None:
        """`ticks` (title) and `tick marks` (scope) are one element."""
        finding = next(
            v for v in report_331.violations if v.where.startswith("tick marks")
        )
        assert "'ticks'" in finding.where

    def test_dial_does_not_fire_because_dial_face_carries_it(
        self, report_331
    ) -> None:
        fired = {v.where.split(" (")[0] for v in report_331.violations}
        assert "dial" not in fired
        assert report_331.matched["dial face"] == "S1"


# ---------------------------------------------------------------------------
# Why it reads criteria tables and not ADR 0226 decision tables
# ---------------------------------------------------------------------------


class TestItLooksAtTheTableThatIsActuallyThere:
    def test_the_331_table_is_not_an_adr_0226_decision_table(self) -> None:
        tables = parse_tables(BODY_331)
        assert len(tables) == 1
        assert not is_decision_table(tables[0])
        assert is_criteria_table(tables[0])

    def test_the_form_check_therefore_examines_nothing(self) -> None:
        """The vacuous result this module exists beside, measured not assumed.

        #2650 changed what this witnesses. The form check still examines no
        table here and still finds no violation -- #2645's reason for keying
        on `is_criteria_table` is unchanged and still pinned above. What it no
        longer does is render that as a bare PASS, so the assertion moved from
        "and passes silently" to "and says so".
        """
        report = check_form(BODY_331)
        assert report.tables == []
        assert report.ok
        assert report.vacuous_tables

        rendered = render_report(report, "boostgauge #331")
        verdict = next(
            line for line in rendered.splitlines() if line.startswith("RESULT:")
        )
        assert "VACUOUS on tables" in verdict
        assert "Decision tables: 0 found" not in rendered
        assert "bezel" not in "\n".join(str(v) for v in report.violations)

    def test_this_module_examines_all_nine_rows(self, report_331) -> None:
        assert report_331.rows_examined == 9
        assert report_331.table_found


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class TestExtraction:
    def test_the_title_yields_its_element_list(self) -> None:
        terms = [e.term for e in title_elements(TITLE_331)]
        assert terms == [
            "bezel", "chrome housing", "dial", "ticks",
            "numerals", "wordmark", "screws",
        ]

    def test_the_participle_tail_is_not_an_enumeration(self) -> None:
        """`baked once, cached` describes behaviour; it names no parts."""
        terms = [e.term for e in title_elements(TITLE_331)]
        assert "baked once" not in terms
        assert "cached" not in terms

    def test_the_scope_sentence_yields_its_element_list(self) -> None:
        terms = [e.term for e in scope_sentence_elements(BODY_331)]
        assert terms == [
            "bezel", "chrome housing", "dial face", "redline band",
            "tick marks", "numerals", "wordmark", "screws",
        ]

    def test_the_sentence_after_the_enumeration_is_not_swallowed(self) -> None:
        terms = [e.term for e in scope_sentence_elements(BODY_331)]
        assert not any("needles" in t for t in terms)

    def test_a_dotted_token_does_not_split_an_enumeration(self) -> None:
        body = "It draws these: alpha, `PIL.Image` handles, beta, gamma. Then stop.\n"
        terms = [e.term for e in scope_sentence_elements(body)]
        assert terms == ["alpha", "`PIL.Image` handles", "beta", "gamma"]

    def test_a_title_with_no_enumeration_yields_nothing(self) -> None:
        assert title_elements("fix: the parser drops a row") == []

    def test_no_title_yields_nothing(self) -> None:
        assert title_elements("") == []


# ---------------------------------------------------------------------------
# The three dispositions
# ---------------------------------------------------------------------------


class TestDispositions:
    def test_an_alias_discharges_a_finding(self) -> None:
        body = BODY_331 + "\n<!-- scope-alias: tick marks -> S3, S4 -->\n"
        report = check_scope_coverage(TITLE_331, body)
        fired = {v.where.split(" (")[0] for v in report.violations}
        assert fired == {"bezel"}
        assert report.aliased["tick marks"] == "S3, S4"

    def test_an_alias_can_discharge_the_acceptance_case_too(self) -> None:
        """Deliberate: the module makes the claim WRITABLE, not unwritable.

        Declaring `bezel -> S9` is wrong on the artifact, and the sibling
        contract-fidelity review is what audits it. What this module ends is
        the claim being made by nobody, in silence.
        """
        body = BODY_331 + "\n<!-- scope-alias: bezel -> S9 -->\n"
        report = check_scope_coverage(TITLE_331, body)
        assert report.aliased["bezel"] == "S9"

    def test_an_exclusion_discharges_a_finding(self) -> None:
        title = "feat: renderer — bezel, dial face, numerals, screws"
        body = (
            "Draws the face. No bezel -- the ring belongs to #999.\n" + TABLE_331
        )
        report = check_scope_coverage(title, body)
        assert "bezel" in report.excluded
        assert report.ok

    def test_an_exclusion_needs_a_reason(self) -> None:
        """`NO gradient, glass sweep, or reflection` is a binding value.

        S1's own cell writes it. Reading it as a scope exclusion would let a
        table cell silently excuse an element the issue promised.
        """
        assert "gradient" not in declared_exclusions(BODY_331)

    def test_a_boundary_terms_section_declares_exclusions(self) -> None:
        exclusions = declared_exclusions(BODY_331)
        assert "caching lifetime and invalidation policy" in exclusions

    def test_an_alias_is_read_regardless_of_arrow_spelling(self) -> None:
        for arrow in ("->", "→"):
            body = f"<!-- scope-alias: tick marks {arrow} S3, S4 -->"
            assert declared_aliases(body) == {"tick marks": "S3, S4"}


# ---------------------------------------------------------------------------
# Silence is not a pass
# ---------------------------------------------------------------------------


class TestVacuousStatesAreDisclosed:
    def test_no_enumeration_is_not_checked(self) -> None:
        report = check_scope_coverage("fix: a typo", TABLE_331)
        assert report.vacuous
        assert "NOT CHECKED" in report.disclosure()
        assert "no scope enumeration" in report.disclosure()
        assert report.ok  # nothing was found wrong, and nothing was judged

    def test_no_criteria_table_is_not_checked(self) -> None:
        report = check_scope_coverage(TITLE_331, LEDE_331)
        assert report.vacuous
        assert "NOT CHECKED" in report.disclosure()
        assert "no criteria table" in report.disclosure()

    def test_a_judged_document_says_what_it_judged(self, report_331) -> None:
        line = report_331.disclosure()
        assert "NOT CHECKED" not in line
        assert "8 element(s) named in scope prose against 9 table row(s)" in line
        assert "2 undisposed" in line

    def test_a_clean_document_reports_zero_undisposed(self) -> None:
        body = (
            BODY_331
            + "\n<!-- scope-alias: tick marks -> S3, S4 -->"
            + "\n<!-- scope-alias: bezel -> S9 -->\n"
        )
        report = check_scope_coverage(TITLE_331, body)
        assert report.ok
        assert "0 undisposed" in report.disclosure()

    def test_an_empty_body_never_raises(self) -> None:
        report = check_scope_coverage("", "")
        assert report.vacuous
        assert report.ok


# ---------------------------------------------------------------------------
# At the seam it actually runs at
# ---------------------------------------------------------------------------


def _fetch(title: str, body: str):
    def fetch(_repo_root, _issue):
        return (title, body)
    return fetch


class TestItRunsAtLauncherPreflight:
    """Free, instant, and before anything is spent -- beside the form check.

    The #331 defect was cheapest to catch here: at ratification, before
    nineteen ruled conflicts hardened a table that was already missing a row.
    """

    def test_the_331_finding_reaches_the_operators_console(self, tmp_path) -> None:
        text, refuse = check_form_at_preflight(
            tmp_path, [331], _fetch(TITLE_331, BODY_331)
        )
        assert "scope coverage:" in text
        assert "bezel" in text

    def test_it_does_not_refuse(self, tmp_path) -> None:
        """Report-only: no issue in the fleet declares an alias yet."""
        _text, refuse = check_form_at_preflight(
            tmp_path, [331], _fetch(TITLE_331, BODY_331)
        )
        assert refuse is False

    def test_it_speaks_on_a_clean_issue_too(self, tmp_path) -> None:
        """A check that is silent when it passes cannot be told from one that
        never ran -- #2381's complaint about box health."""
        body = (
            BODY_331
            + "\n<!-- scope-alias: tick marks -> S3, S4 -->"
            + "\n<!-- scope-alias: bezel -> S9 -->\n"
        )
        text, _ = check_form_at_preflight(tmp_path, [331], _fetch(TITLE_331, body))
        assert "scope coverage:" in text
        assert "0 undisposed" in text

    def test_it_discloses_when_it_checked_nothing(self, tmp_path) -> None:
        text, _ = check_form_at_preflight(
            tmp_path, [7], _fetch("fix: a typo", "Some prose with no table.\n")
        )
        assert "scope coverage: NOT CHECKED" in text

    def test_a_scope_crash_never_costs_the_form_check_its_verdict(
        self, tmp_path, monkeypatch
    ) -> None:
        """The declared fail-open, exercised rather than asserted about."""
        monkeypatch.setattr(
            form_gate, "check_scope_coverage",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        result = form_gate.check_issue(tmp_path, 331, _fetch(TITLE_331, BODY_331))
        assert result.scope is None
        assert result.report is not None  # the form check still reached a verdict
        text, _ = form_gate.render([result])
        assert "scope coverage" not in text  # absent, never a passing line

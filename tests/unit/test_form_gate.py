"""The ADR 0226 form check at launcher preflight (Closes #2227).

#2219 built the checker and deliberately left this open. The operator ruled on
2026-08-12: it RUNS at preflight, report-only by default; the launch refuses
only when the issue carries at least one decision table and that table is
malformed; an unconverted prose issue never refuses; the vacuous-EARS state is
surfaced out loud; and findings are labelled as the form check's own so one
defect never reads as two complaints beside the semantic gate's.

These pin all four halves of that ruling. The bodies are ADR 0226 shaped rather
than minimal fixtures, because the interesting cases -- a prose issue, a table
missing a row, a table whose rows carry IDs -- are distinguished by their form.
"""

import sys
from pathlib import Path
from unittest.mock import patch

from assemblyzero.workflows.requirements.form_check import check_form
from assemblyzero.workflows.requirements.form_gate import (
    LABEL,
    check_form_at_preflight,
    check_issue,
    classify,
)

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402


# An unconverted issue: prose only, no Requirements section, no table. This is
# nearly every issue in the fleet, because ADR 0226 converts on the next roll
# rather than in a sweep.
PROSE_ISSUE = """\
The gauge needle flickers at high update rates.

It should be smoothed. See the attached video for what it looks like now.
"""

# A converted issue whose table is complete: two binary conditions, four rows.
# Shaped like boostgauge #7, the issue ADR 0226 cites as its first conversion --
# no ID column, so the row join is count-and-outcome, and the outcome column's
# header supplies the subject word its criteria must open with.
GOOD_ISSUE = """\
## Requirements

- The system shall persist the window size on exit.
- WHEN the user resizes the window the system shall record the new size.

## Size

| `--reset-config`? | Window resized by hand? | `size` in the file after quit |
|---|---|---|
| no | no | unchanged |
| no | yes | the new size |
| yes | no | default |
| yes | yes | the new size |

## Acceptance Criteria

- size unchanged
- size the new size
- size default
- size the new size again
"""

# The same table with one row removed: two binary conditions require 2^2 rows
# and it carries three. This is a malformed table, and the case that refuses.
MALFORMED_TABLE_ISSUE = GOOD_ISSUE.replace("| yes | yes | the new size |\n", "")

# The ID convention adopted on #2219, which makes the row join exact. IDs carry
# a letter prefix -- bare digits are not row IDs to the checker.
IDS_ISSUE = """\
## Requirements

- The system shall persist the window size on exit.

## Size

| ID | `--reset-config`? | Window resized by hand? | `size` in the file after quit |
|---|---|---|---|
| R010 | no | no | unchanged |
| R020 | no | yes | the new size |
| R030 | yes | no | default |
| R040 | yes | yes | the new size |

## Acceptance Criteria

- R010 size unchanged
- R020 size the new size
- R030 size default
- R040 size the new size
"""

# One row left without its criterion, with IDs present so the join is exact.
MISSING_CRITERION_ISSUE = IDS_ISSUE.replace("- R040 size the new size\n", "")

# A Requirements section whose bullets are not EARS. Findings here must report
# and never refuse: prose sentences are where unconverted issues live.
NON_EARS_ISSUE = """\
## Requirements

- Make the needle smoother.
- Nobody wants a flickering gauge.
"""


def _fetch(bodies):
    def fetch(repo_root, issue):
        if issue not in bodies:
            raise RuntimeError(f"no such issue #{issue}")
        return (f"issue {issue}", bodies[issue])
    return fetch


class TestTheRefusalCondition:
    """"...only when the issue carries at least one decision table and that
    table is malformed." """

    def test_a_malformed_table_refuses(self, tmp_path):
        text, refuse = check_form_at_preflight(
            tmp_path, [7], _fetch({7: MALFORMED_TABLE_ISSUE})
        )
        assert refuse, "three rows for two binary conditions is a malformed table"
        assert "BLOCKED by the form check" in text

    def test_an_unconverted_prose_issue_never_refuses(self, tmp_path):
        """The load-bearing case. Conversion happens on the next roll, not as a
        sweep, so nearly every issue is still prose -- refusing here would block
        almost all of them, and a gate that fires on the ordinary case is one
        people learn to wave through."""
        text, refuse = check_form_at_preflight(
            tmp_path, [7], _fetch({7: PROSE_ISSUE})
        )
        assert not refuse
        # #2650: was "no decision table", which said the same thing about an
        # issue carrying no table and an issue carrying one this check does
        # not examine. This issue is the former, and now says so.
        assert "no table in this issue, so none was checked" in text

    def test_a_well_formed_table_does_not_refuse(self, tmp_path):
        text, refuse = check_form_at_preflight(
            tmp_path, [7], _fetch({7: GOOD_ISSUE})
        )
        assert not refuse, text

    def test_non_ears_prose_reports_but_does_not_refuse(self, tmp_path):
        text, refuse = check_form_at_preflight(
            tmp_path, [7], _fetch({7: NON_EARS_ISSUE})
        )
        assert not refuse, (
            "EARS findings are about prose sentences, which is exactly where "
            "unconverted issues live"
        )
        assert "reported only" in text

    def test_a_missing_row_criterion_refuses_when_ids_make_the_join_exact(
        self, tmp_path
    ):
        text, refuse = check_form_at_preflight(
            tmp_path, [7], _fetch({7: MISSING_CRITERION_ISSUE})
        )
        assert refuse
        assert "R040" in text

    def test_one_bad_issue_in_a_batch_refuses_the_batch(self, tmp_path):
        """A batch is judged as a whole before anything is spent, like every
        other preflight refusal."""
        _text, refuse = check_form_at_preflight(
            tmp_path, [1, 7],
            _fetch({1: PROSE_ISSUE, 7: MALFORMED_TABLE_ISSUE}),
        )
        assert refuse


class TestClassification:
    def test_table_shape_violations_refuse(self):
        report = check_form(MALFORMED_TABLE_ISSUE)
        refusing, _reporting = classify(report)

        assert refusing, "a table missing a row must refuse"
        assert all(v.kind in ("table-rows", "table-duplicate", "row-criterion")
                   for v in refusing)

    def test_ears_violations_only_report(self):
        report = check_form(NON_EARS_ISSUE)
        refusing, reporting = classify(report)

        assert refusing == []
        assert reporting, "the non-EARS bullets must still be reported"
        assert all(v.kind == "ears" for v in reporting)

    def test_a_missing_criterion_refuses_when_the_join_is_exact(self):
        """With row IDs, "row R040 has no criterion opening with R040" is a
        hard fact, and catching it before a roll is the point."""
        report = check_form(MISSING_CRITERION_ISSUE)
        refusing, _ = classify(report)

        assert [v.kind for v in refusing] == ["row-criterion"]
        assert all(t.exact_join for t in report.tables)

    def test_the_same_gap_only_reports_without_row_ids(self):
        """The checker calls the no-ID join weaker and delegates combination
        correctness to the semantic gate, so a text-matched gap is not the
        unambiguous fact a refusal needs."""
        without_ids = GOOD_ISSUE.replace("- size the new size again\n", "")

        report = check_form(without_ids)
        refusing, reporting = classify(report)

        assert not any(t.exact_join for t in report.tables)
        assert all(v.kind != "row-criterion" for v in refusing)
        assert any(v.kind == "row-criterion" for v in reporting), (
            "it must still be reported -- only the refusal is withheld"
        )


class TestTheFleetsOneConvertedIssue:
    """boostgauge #7, frozen from the live issue on 2026-08-12.

    ADR 0226 cites it as the first requirement converted to this form, so it is
    the strongest regression anchor available: if the preflight ever refuses
    THIS, the gate is wrong. It is also the vacuous case in the wild -- its
    criteria live under `## Acceptance Criteria` and it has no
    `## Requirements` section at all, so no sentence in it is EARS-checked.
    """

    BODY = (
        Path(__file__).parent.parent
        / "fixtures" / "form_gate" / "boostgauge-7-converted.md"
    ).read_text(encoding="utf-8")

    def test_it_does_not_refuse(self, tmp_path):
        text, refuse = check_form_at_preflight(
            tmp_path, [7], _fetch({7: self.BODY})
        )
        assert not refuse, text

    def test_its_two_tables_are_read_as_decision_tables(self, tmp_path):
        result = check_issue(tmp_path, 7, _fetch({7: self.BODY}))
        assert len(result.report.tables) == 2
        assert result.report.ok, "the converted issue must pass the form check"

    def test_its_vacuous_ears_state_is_announced(self, tmp_path):
        """It passes every EARS check while verifying nothing about any
        sentence. The launch must say so rather than let that read as clean."""
        text, _ = check_form_at_preflight(tmp_path, [7], _fetch({7: self.BODY}))
        assert "vacuous pass" in text


class TestSilenceIsNotAPass:
    """"An issue with no ## Requirements section passes the form check while
    verifying nothing about its sentences." """

    def test_the_vacuous_result_is_stated_out_loud(self, tmp_path):
        text, refuse = check_form_at_preflight(
            tmp_path, [7], _fetch({7: PROSE_ISSUE})
        )
        assert not refuse
        assert "vacuous pass" in text
        assert "NO sentence" in text

    def test_a_converted_issue_does_not_carry_the_vacuous_note(self, tmp_path):
        text, _ = check_form_at_preflight(tmp_path, [7], _fetch({7: GOOD_ISSUE}))
        assert "vacuous pass" not in text

    def test_the_report_says_it_cannot_report_correctness(self, tmp_path):
        text, _ = check_form_at_preflight(tmp_path, [7], _fetch({7: GOOD_ISSUE}))
        assert "CORRECTNESS" in text


#: A criteria table -- `ID | Element | Binding value | Assertion method`, the
#: shape boostgauge #331 carries and this campaign actually rolls. Not an
#: ADR 0226 decision table, so the form check does not examine it.
CRITERIA_TABLE_ISSUE = """\
Render the static face.

## Requirements

- WHEN `render_face(size)` is called, the skin module shall return a `PIL.Image`.

## Decision table

| ID | Element | Binding value | Assertion method |
|---|---|---|---|
| S1 | Dial face | flat `#0A0A0C` | classification at 3 interior points |
| S9 | Bezel seat | dial sits below the bezel plane | sample at 1.01 R is darker |
"""


class TestATablePresentButUnexaminedSaysSoAtLaunch:
    """#2650. The launch path is the surface an operator reads before spending
    a roll, and it said `no decision table, so none was checked` about an issue
    carrying a nine-row table the rest of the pipeline treats as normative.

    `has_tables` cannot tell those two states apart -- it is False for both --
    so the note it drove reported the checked-nothing case in the words of the
    nothing-to-check case.
    """

    def test_the_note_says_a_table_was_present(self, tmp_path):
        text, refuse = check_form_at_preflight(
            tmp_path, [331], _fetch({331: CRITERIA_TABLE_ISSUE})
        )
        assert not refuse
        assert "1 table(s) present and NOT of the checked kind" in text
        assert "NO table was checked" in text
        assert "vacuous, not a clean bill" in text

    def test_it_no_longer_claims_there_is_no_table(self, tmp_path):
        text, _ = check_form_at_preflight(
            tmp_path, [331], _fetch({331: CRITERIA_TABLE_ISSUE})
        )
        assert "no decision table, so none was checked" not in text
        assert "no table in this issue" not in text

    def test_an_issue_with_no_table_at_all_reads_differently(self, tmp_path):
        """Nothing-to-check and checked-nothing stay different facts."""
        text, _ = check_form_at_preflight(tmp_path, [7], _fetch({7: PROSE_ISSUE}))
        assert "no table in this issue, so none was checked" in text
        assert "NOT of the checked kind" not in text

    def test_a_real_decision_table_carries_no_such_note(self, tmp_path):
        text, _ = check_form_at_preflight(tmp_path, [7], _fetch({7: GOOD_ISSUE}))
        assert "NOT of the checked kind" not in text
        assert "no table in this issue" not in text

    def test_it_still_does_not_refuse(self, tmp_path):
        """Report-only. A criteria table is the ordinary case, not a defect."""
        _text, refuse = check_form_at_preflight(
            tmp_path, [331], _fetch({331: CRITERIA_TABLE_ISSUE})
        )
        assert refuse is False


class TestPresentation:
    """"...labelled as the form check's, distinct from the semantic gate's
    output, so one defect never reads as two complaints in two formats." """

    def test_every_report_names_the_form_check(self, tmp_path):
        text, _ = check_form_at_preflight(tmp_path, [7], _fetch({7: GOOD_ISSUE}))
        assert text.startswith(LABEL)

    def test_the_refusal_is_distinguishable_from_the_semantic_gate(self, tmp_path):
        from assemblyzero.speedrun.must_resolve import refusal_message

        text, refuse = check_form_at_preflight(
            tmp_path, [7], _fetch({7: MALFORMED_TABLE_ISSUE})
        )
        semantic = refusal_message([{"number": 1, "title": "t"}])

        assert refuse
        assert "BLOCKED by the form check" in text
        assert "BLOCKED by the form check" not in semantic
        assert "unanswered" not in text, (
            "the semantic gate's wording must not appear in the form check's"
        )

    def test_it_says_no_model_calls_were_made(self, tmp_path):
        text, _ = check_form_at_preflight(tmp_path, [7], _fetch({7: GOOD_ISSUE}))
        assert "no model calls" in text


class TestAReadFailureIsNotAVerdict:
    def test_an_unreadable_issue_reports_and_proceeds(self, tmp_path):
        """Offline must not brick a local roll -- the same stance the
        must-resolve gate takes. But it must not read as a pass either."""
        text, refuse = check_form_at_preflight(tmp_path, [7], _fetch({}))

        assert not refuse
        assert "could not be checked" in text
        assert "Nothing about this issue's form has been verified" in text

    def test_an_empty_body_is_not_a_pass(self, tmp_path):
        result = check_issue(tmp_path, 7, _fetch({7: "   \n"}))
        assert result.error
        assert result.report is None

    def test_no_issues_produces_no_output(self, tmp_path):
        text, refuse = check_form_at_preflight(tmp_path, [], _fetch({}))
        assert text == "" and refuse is False


class TestTheLauncherRunsIt:
    def test_the_preflight_calls_the_gate(self):
        import inspect

        source = inspect.getsource(sr.main)
        assert "check_form_at_preflight" in source, (
            "the ruling is that it runs at launcher preflight"
        )

    def test_it_refuses_before_anything_is_spent(self, tmp_path):
        """91, and no roll -- the same shape as every other preflight refusal."""
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        rolled = []

        def _healthy(*_a, **_k):
            from assemblyzero.speedrun.box_health import BoxHealth
            return BoxHealth(True, [], "")

        with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
                patch.object(sr, "check_box_health", _healthy), \
                patch.object(sr, "check_prereqs", lambda *a: None), \
                patch.object(sr, "open_must_resolve_issues", lambda r: ([], None)), \
                patch.object(sr, "roll_issue",
                             lambda *a: rolled.append(a) or 0), \
                patch.object(sr, "fetch_issue",
                             lambda r, i: ("t", MALFORMED_TABLE_ISSUE)):
            code = sr.main(["--repo", str(repo), "--issue", "7"])

        assert code == 91
        assert rolled == [], "a form refusal must spend nothing"

    def test_a_prose_issue_still_rolls(self, tmp_path):
        """The regression that would matter most: blocking the whole fleet."""
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        rolled = []

        def _healthy(*_a, **_k):
            from assemblyzero.speedrun.box_health import BoxHealth
            return BoxHealth(True, [], "")

        with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
                patch.object(sr, "check_box_health", _healthy), \
                patch.object(sr, "check_prereqs", lambda *a: None), \
                patch.object(sr, "open_must_resolve_issues", lambda r: ([], None)), \
                patch.object(sr, "restore_repo", lambda *a: []), \
                patch.object(sr, "roll_issue",
                             lambda *a: rolled.append(a) or 0), \
                patch.object(sr, "fetch_issue", lambda r, i: ("t", PROSE_ISSUE)):
            code = sr.main(["--repo", str(repo), "--issue", "7"])

        assert code == 0
        assert len(rolled) == 1

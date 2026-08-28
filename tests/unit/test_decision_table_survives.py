"""A derivation that destroys the source's table SHAPE is caught (#2608).

The observed case: run-issue331-093613, 2026-08-28. The manifest stage
printed "no criteria decision table in the LLD -- assertion manifest not
applicable" and the #2533 protection switched off with one log line.

Established against the preserved run-19 lineage before any code changed:

* the parser is NOT brittle -- it parsed all 15 tables in the LLD and the 1
  in the source issue, correctly. No parse failure exists here;
* the LLD genuinely carries no criteria decision table, because the
  DERIVATION destroyed it: the source's nine-row
  `| ID | Element | Binding value | Assertion method |` table became a
  seven-item bullet list (S1-S6, S8 -- S7 and S9 never returned, and every
  assertion method was lost);
* #2563's literal gate is shape-blind by construction. It fired five
  criticals, the drafter repaired by appending bullets carrying the missing
  numbers, and the gate went green with the table still gone.

So "not applicable" was a misread of a derivation failure as an absence.
This suite pins both halves of the repair: the structure check that fails
in the lld stage where the loop can still fix it, and the abstain that
carries its denominator and travels forward when it does happen.

Composes with #2563's fixture (`test_assertion_literal_conservation.py`)
rather than replacing it: literals and shape are different conserved
quantities and each needs its own gate.
"""

from __future__ import annotations

from assemblyzero.workflows.implementation_spec.assertion_manifest import (
    compile_manifest,
)
from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
    validate_decision_table_survives,
)

#: The observed source shape, two rows of the real #331 table.
ISSUE_WITH_TABLE = """## Decision table — static elements and their binding values

| ID | Element | Binding value (quoted from the render contract) | Assertion method |
|----|---------|------------------------------------------------|------------------|
| S1 | Dial face | flat `#0A0A0C`, radius R = 0.40 × size | classification at 3 interior points |
| S2 | Redline band | `#AA0F19` crimson, inner 0.88 R to outer 1.00 R | classification at radius 0.94 R at values 65/75/85 |
"""

#: The observed derived shape, faithful to the measured run: the table
#: restated as bullets carrying EVERY literal from the source rows -- which
#: is exactly why #2563 goes green on it -- while the table itself is gone.
#: The assertion-method numbers are present because that is what the real
#: drafter appended when the literal gate fired its five criticals.
LLD_AS_BULLETS = """# 331 - Feature

## 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/skins/stingray.py` | Add | The renderer. |

## 3. Requirements

1. The system shall render each static element from the contract:
   - S1: flat `#0A0A0C`, R = 0.40 × size
   - S2: `#AA0F19`, 0.88 R, 1.00 R

## 10.1 Test Scenarios

| ID | Scenario | Type | Expected Output | Pass Criteria |
|----|----------|------|-----------------|---------------|
| 020 | Dial face (REQ-1) | Auto | flat face | classification at 3 interior points |
| 030 | Redline band (REQ-1) | Auto | crimson band | classification at radius 0.94 R at values 65/75/85 |
"""

#: The derivation that kept the shape: same rows, carried as a table.
LLD_WITH_TABLE = """# 331 - Feature

## 3. Requirements

1. The system shall render each static element from the contract.

| ID | Element | Binding value | Assertion method |
|----|---------|---------------|------------------|
| S1 | Dial face | flat `#0A0A0C`, radius R = 0.40 × size | classification at 3 interior points |
| S2 | Redline band | `#AA0F19` crimson, inner 0.88 R to outer 1.00 R | classification at radius 0.94 R |
"""

#: A source genuinely outside the manifest's domain -- most issues.
ISSUE_NO_TABLE = """# Make the button blue

## Requirements

1. The button shall be blue.
2. The button shall stay blue on hover.
"""

LLD_PROSE_ONLY = """# LLD

## 3. Requirements

1. The button renders blue.
"""


class TestTheStructureCheck:
    def test_a_destroyed_table_is_an_error(self):
        """The observed run. Bullets carrying every literal do not satisfy
        this: the manifest compiler reads the TABLE."""
        errors = validate_decision_table_survives(
            ISSUE_WITH_TABLE, LLD_AS_BULLETS
        )
        assert len(errors) == 1
        message = errors[0].message
        assert "S1, S2" in message, "the lost rows are named"
        assert "carries none" in message

    def test_the_message_names_what_was_searched(self):
        """A denominator, not a bare complaint: the LLD's own tables were
        parsed and counted, so the drafter cannot read this as 'your tables
        are malformed'."""
        message = validate_decision_table_survives(
            ISSUE_WITH_TABLE, LLD_AS_BULLETS
        )[0].message
        assert "2 table(s) were parsed in the LLD" in message

    def test_a_carried_table_passes(self):
        assert validate_decision_table_survives(
            ISSUE_WITH_TABLE, LLD_WITH_TABLE
        ) == []

    def test_a_source_without_a_table_yields_no_checks(self):
        """The ordinary case -- most repos, every non-visual issue. Not
        applicable is not failure."""
        assert validate_decision_table_survives(
            ISSUE_NO_TABLE, LLD_PROSE_ONLY
        ) == []

    def test_an_empty_side_yields_no_checks(self):
        assert validate_decision_table_survives("", LLD_AS_BULLETS) == []
        assert validate_decision_table_survives(ISSUE_WITH_TABLE, "") == []

    def test_it_is_blind_to_literals_by_design(self):
        """The division of labour with #2563, asserted. An LLD that keeps
        the TABLE but sheds a literal passes THIS check -- the literal gate
        owns that, and duplicating it here would double-report one defect.
        """
        lossy_but_shaped = LLD_WITH_TABLE.replace("0.88 R", "some radius")
        assert validate_decision_table_survives(
            ISSUE_WITH_TABLE, lossy_but_shaped
        ) == []

    def test_the_sibling_gate_catches_what_this_one_does_not(self):
        """The complement, so the pair is provably not leaving a gap: the
        literal gate fires on exactly the case this check passes."""
        from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
            validate_assertion_literal_conservation,
        )

        lossy_but_shaped = LLD_WITH_TABLE.replace("0.88 R", "some radius")
        assert validate_assertion_literal_conservation(
            ISSUE_WITH_TABLE, lossy_but_shaped
        ), "the literal gate must own the case the shape gate passes"

    def test_bullets_satisfy_the_literal_gate_while_failing_this_one(self):
        """The measured run-19 condition, as a fixture: this is why one gate
        was not enough. Every literal survives into the bullets, so #2563 is
        green; the table is gone, so #2608 fires."""
        from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
            validate_assertion_literal_conservation,
        )

        assert validate_assertion_literal_conservation(
            ISSUE_WITH_TABLE, LLD_AS_BULLETS
        ) == [], "the fixture must reproduce the shape-blind green verdict"
        assert validate_decision_table_survives(
            ISSUE_WITH_TABLE, LLD_AS_BULLETS
        ), "and the shape gate must be what catches it"


class TestTheAbstainCarriesItsDenominator:
    def test_tables_present_but_none_criteria_is_an_abstain(self):
        """The run-19 shape: the document has tables, none is a criteria
        table. That is a shape mismatch worth surfacing, not an empty
        document."""
        result = compile_manifest(LLD_AS_BULLETS, "")
        assert result.applicable is False
        assert result.tables_seen == 2
        assert result.abstained is True
        assert "0 in the criteria shape" in result.denominator()

    def test_no_tables_at_all_is_not_an_abstain(self):
        """The ordinary non-visual issue. It still states its denominator,
        but it is not the case that warrants a warning."""
        result = compile_manifest(LLD_PROSE_ONLY, "")
        assert result.applicable is False
        assert result.tables_seen == 0
        assert result.abstained is False
        assert result.denominator() == "0 tables in the document"

    def test_an_applicable_compile_reports_its_counts(self):
        result = compile_manifest(LLD_WITH_TABLE, "")
        assert result.applicable is True
        assert result.abstained is False
        assert result.tables_seen == 1
        assert "criterion(s) compiled from 1 table(s)" in result.denominator()

    def test_the_two_absences_are_distinguishable(self):
        """The whole point. Before #2608 both rendered as one message, and
        a protection switching off was indistinguishable from a protection
        correctly sitting out."""
        shape_mismatch = compile_manifest(LLD_AS_BULLETS, "")
        genuinely_absent = compile_manifest(LLD_PROSE_ONLY, "")
        assert shape_mismatch.applicable == genuinely_absent.applicable
        assert shape_mismatch.abstained != genuinely_absent.abstained
        assert shape_mismatch.denominator() != genuinely_absent.denominator()


class TestTheNodeTravelsTheAbsenceForward:
    def _run(self, lld: str) -> dict:
        from assemblyzero.workflows.implementation_spec.nodes.compile_manifest import (
            compile_assertion_manifest,
        )

        return compile_assertion_manifest(
            {"lld_content": lld, "repo_root": "", "config_mock_mode": True}
        )

    def test_the_abstain_lands_on_state(self, capsys):
        out = self._run(LLD_AS_BULLETS)
        capsys.readouterr()
        assert out["assertion_manifest_absent"] is True
        assert out["assertion_manifest_abstained"] is True
        assert "0 in the criteria shape" in out["assertion_manifest_absence_reason"]
        assert out["error_message"] == "", "the abstain is survivable, not a halt"

    def test_the_ordinary_absence_also_travels_but_is_not_an_abstain(
        self, capsys
    ):
        out = self._run(LLD_PROSE_ONLY)
        capsys.readouterr()
        assert out["assertion_manifest_absent"] is True
        assert out["assertion_manifest_abstained"] is False

    def test_the_abstain_is_announced_as_a_protection_being_off(self, capsys):
        self._run(LLD_AS_BULLETS)
        printed = capsys.readouterr().out
        assert "ABSTAIN" in printed
        assert "#2533 protection is OFF" in printed
        assert "15 table" not in printed, "the count must be this draft's own"

    def test_the_ordinary_absence_is_not_announced_as_an_abstain(self, capsys):
        self._run(LLD_PROSE_ONLY)
        printed = capsys.readouterr().out
        assert "ABSTAIN" not in printed
        assert "not applicable" in printed


class TestTheGateRepeatsTheReason:
    def _gate(self, state: dict) -> str:
        from assemblyzero.workflows.implementation_spec.nodes.compile_manifest import (
            manifest_gate,
        )

        manifest_gate(state)
        return ""

    def test_the_gate_names_the_abstain_rather_than_only_passing_through(
        self, capsys
    ):
        """Two reassuring lines about a protection that was off is what the
        operator actually saw. The gate repeats WHY."""
        from assemblyzero.workflows.implementation_spec.nodes.compile_manifest import (
            manifest_gate,
        )

        manifest_gate({
            "assertion_manifest": "",
            "assertion_manifest_rows": [],
            "assertion_manifest_abstained": True,
            "assertion_manifest_absence_reason": "15 table(s) parsed, 0 in the criteria shape",
        })
        printed = capsys.readouterr().out
        assert "ABSTAINED" in printed
        assert "15 table(s) parsed" in printed

    def test_a_bare_pass_through_still_works(self, capsys):
        from assemblyzero.workflows.implementation_spec.nodes.compile_manifest import (
            manifest_gate,
        )

        out = manifest_gate(
            {"assertion_manifest": "", "assertion_manifest_rows": []}
        )
        printed = capsys.readouterr().out
        assert "no manifest to gate" in printed
        assert out["error_message"] == ""


class TestTheRunRecordSurfacesIt:
    """#2608's last mile: the absence must reach the record, or a green row
    means two different things and the reader cannot tell which."""

    def test_a_passed_stage_with_an_abstain_is_annotated(self):
        from assemblyzero.workflows.orchestrator.graph import format_stage_table

        table = format_stage_table({
            "spec": {
                "status": "passed",
                "duration_seconds": 12.0,
                "artifact_path": "docs/spec.md",
                "notes": [
                    "assertion manifest ABSTAINED (15 table(s) parsed, 0 in "
                    "the criteria shape) — the #2533 protection did not run "
                    "for this stage (#2608)"
                ],
            }
        })
        assert "DECLARED FALL-THROUGHS" in table
        assert "ABSTAINED" in table
        assert "#2533 protection did not run" in table

    def test_an_ordinary_run_record_carries_no_section(self):
        """The section's presence is the signal, so it must not appear on a
        run where nothing sat out."""
        from assemblyzero.workflows.orchestrator.graph import format_stage_table

        table = format_stage_table({
            "spec": {"status": "passed", "duration_seconds": 12.0}
        })
        assert "DECLARED FALL-THROUGHS" not in table

    def test_the_stage_result_carries_the_note_from_the_sub_result(self):
        from assemblyzero.workflows.orchestrator.stages import (
            _declared_fallthroughs,
        )

        notes = _declared_fallthroughs({
            "assertion_manifest_abstained": True,
            "assertion_manifest_absence_reason":
                "15 table(s) parsed, 0 in the criteria shape",
        })
        assert len(notes) == 1
        assert "15 table(s) parsed" in notes[0]

    def test_no_abstain_yields_no_notes(self):
        from assemblyzero.workflows.orchestrator.stages import (
            _declared_fallthroughs,
        )

        assert _declared_fallthroughs({}) == []
        assert _declared_fallthroughs(
            {"assertion_manifest_abstained": False}
        ) == []

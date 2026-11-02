"""A TypeScript test counts for its criterion, and pinning lets the answer through (#4551).

An implementation-spec run on a TypeScript target halted at the iteration cap.
The reviewer asked for the Python placeholder tests of criteria rows 060 to
130 to be removed, because they were tautologies and the behaviour is tested
in Vitest. After that, `criteria_have_tests` named the same eight criteria on
every revision, because it credited only Python `def test_` functions; pinning
refused revision content in the same rounds; and the halt carried the class
`unknown`.

The fixtures below have the run's shape: an LLD whose rows 010 to 050 are
tested in Python and whose rows 060 to 130 are runtime behaviour tested in
TypeScript, a spec that carries those TypeScript tests in Section 10 and in
the diff of a planned `.test.ts` file, and a halt with an identical complaint
and pinning refusals on the record. The domain is invented.

T1 (R1): rows 060 to 130 covered only by Vitest tests pass. On `main` they
    were reported missing, all eight.
T2 (R1): a criterion with no test in either language still fails.
T3 (R2): the halt for the recurrence shape names the gate that blocked
    progress and carries a class other than `unknown`.
T4 (R3): a revision line answering a named completeness complaint survives
    pinning.
"""

from __future__ import annotations

import pytest

from assemblyzero.core.halt_node import classify_error
from assemblyzero.core.recovery_plan import generate_recovery_plan
from assemblyzero.workflows.implementation_spec.criteria_coverage import (
    criteria_coverage,
)
from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
    _apply_pinning,
)
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_criteria_have_tests,
    validate_completeness,
)
from assemblyzero.workflows.implementation_spec.revision_pinning import (
    complaint_answers,
    enforce_pinning,
    named_tokens,
)
from assemblyzero.workflows.implementation_spec.typescript_bodies import (
    planned_test_files,
    spec_typescript_tests,
    typescript_tests,
)

# ---------------------------------------------------------------------------
# Fixtures: the run's shape, an invented domain
# ---------------------------------------------------------------------------

LLD = """# LLD-007: Held meter readings

## 10. Verification

### 10.1 Test Scenarios

| ID | Scenario | Type | Pass Criteria |
|----|----------|------|---------------|
| 010 | Schema accepts a valid hold window (REQ-1) | unit | Validates without errors |
| 020 | Reading schema accepts `held: true` and its absence (REQ-2) | unit | Both validate |
| 030 | Compiler marks `hold` as inert (REQ-3) | unit | No unmodeled-field error |
| 040 | Compiler rejects tick 0 and ticks past the end (REQ-4) | unit | AssertionError raised |
| 050 | Compiler rejects an unknown held field (REQ-4) | unit | AssertionError raised |
| 060 | TypeScript compilation of `HoldWindow` (REQ-5) | unit | Clean compilation |
| 070 | Single-tick hold repeats the reading and flags `held: true` (REQ-6) | unit | Reading equals tick 4 |
| 080 | Multi-tick hold keeps the first held value (REQ-6) | unit | Tick 7 equals tick 4 |
| 090 | No hold omits the `held` key (REQ-7) | unit | Key absent |
| 100 | State carries `last_shown_reading` (REQ-8) | unit | State holds the last shown value |
| 110 | Billing in `settle()` uses actuals during a hold (REQ-9) | unit | `bill.cost === 5000` |
| 120 | Replay of a log without holds is bit-identical (REQ-10) | unit | Replayed equals live |
| 130 | A held log bills as an unheld log does (REQ-10) | unit | Costs identical |
"""

#: The eight runtime rows, the ones the real run's check named every round.
RUNTIME_ROWS = ["060", "070", "080", "090", "100", "110", "120", "130"]

PYTHON_TESTS = '''```python
# tests/unit/test_compile_meter.py
import pytest

from meter.compile import validate_holds


def test_req_010_schema_accepts_hold_window():
    # Schema accepts a valid hold window (REQ-1)
    assert validate_holds([{"ticks": [5], "fields": ["reading"]}], ticks=16) is None


def test_req_020_reading_schema_accepts_held():
    # Reading schema accepts held: true and its absence (REQ-2)
    assert validate_holds([], ticks=16) is None


def test_req_030_compiler_marks_hold_inert():
    # Compiler marks hold as inert (REQ-3)
    assert validate_holds([{"ticks": [1], "fields": ["reading"]}], ticks=4) is None


def test_req_040_compiler_rejects_tick_bounds():
    # Compiler rejects tick 0 and ticks past the end (REQ-4)
    with pytest.raises(AssertionError):
        validate_holds([{"ticks": [0], "fields": ["reading"]}], ticks=16)
```
'''

#: One Vitest test per runtime row, keyed by row, each citing its REQ tag in
#: a comment as the real spec's did. The titles carry the row number written
#: as "REQ-060", which joins to nothing: only the comment's tag covers.
TS_TESTS = {
    "060": '''it("satisfies REQ-060: HoldWindow type compiles", () => {
  // TypeScript compilation of HoldWindow (REQ-5)
  const hold: HoldWindow = { ticks: [1, 2], fields: ["reading"] };
  expect(hold.ticks).toHaveLength(2);
});''',
    "070": '''it("satisfies REQ-070: a single-tick hold repeats the reading", () => {
  // Single-tick hold repeats the reading and flags held: true (REQ-6)
  const shown = observe(heldMeter, 5);
  expect(shown.reading).toBe(heldMeter.readings[4]);
  expect(shown.held).toBe(true);
});''',
    "080": '''it("satisfies REQ-080: a multi-tick hold keeps the first held value", () => {
  // Multi-tick hold keeps the first held value (REQ-6)
  expect(observe(heldMeter, 7).reading).toBe(heldMeter.readings[4]);
});''',
    "090": '''it("satisfies REQ-090: no hold omits the held key", () => {
  // No hold omits the held key (REQ-7)
  expect("held" in observe(plainMeter, 3)).toBe(false);
});''',
    "100": '''it("satisfies REQ-100: state carries the last shown reading", () => {
  // State carries last_shown_reading (REQ-8)
  expect(fold(heldMeter, 2).last_shown_reading).toBe(20);
});''',
    "110": '''it("satisfies REQ-110: billing uses actuals during a hold", () => {
  // Billing in settle() uses actuals during a hold (REQ-9)
  expect(settle(heldMeter, 2).cost).toBe(5000);
});''',
    "120": '''it("satisfies REQ-120: a log without holds replays bit-identically", () => {
  // Replay of a log without holds is bit-identical (REQ-10)
  expect(replay(plainMeter, log)).toStrictEqual(live);
});''',
    "130": '''it("satisfies REQ-130: a held log bills as an unheld log does", () => {
  // A held log bills as an unheld log does (REQ-10)
  expect(replay(heldMeter, log).cost).toBe(replay(plainMeter, log).cost);
});''',
}


def _section_ten_ts(rows: list[str]) -> str:
    body = "\n\n".join(TS_TESTS[row] for row in rows)
    return f"```typescript\n// web/tests/meter.test.ts\n\n{body}\n```\n"


def _planned_diff(rows: list[str]) -> str:
    added = "\n".join(
        "+  " + line for row in rows for line in TS_TESTS[row].splitlines()
    )
    return (
        "```diff\n"
        "--- a/web/tests/meter.test.ts\n"
        "+++ b/web/tests/meter.test.ts\n"
        "@@ -1,3 +1,4 @@\n"
        ' import { describe, expect, it } from "vitest";\n'
        '-import { observe } from "../src/meter";\n'
        '+import { fold, observe, replay, settle } from "../src/meter";\n'
        "@@ -20,3 +21,60 @@\n"
        ' const plainMeter = loadMeter("plain");\n'
        '+describe("held readings (#7)", () => {\n'
        f"{added}\n"
        "+});\n"
        "```\n"
    )


def _spec(section_ten_rows=(), planned_rows=(), section_ten_extra="") -> str:
    """A spec of the real run's shape: Python tests for rows 010 to 040 in
    Section 10.1, TypeScript tests for the runtime rows where asked."""
    planned = (
        "### 6.4 `web/tests/meter.test.ts` (Modify)\n\n"
        "Add the held-reading tests:\n\n" + _planned_diff(list(planned_rows))
        if planned_rows else ""
    )
    ts = _section_ten_ts(list(section_ten_rows)) if section_ten_rows else ""
    return (
        "# Implementation Spec: 7 - Held meter readings\n\n"
        "## 1. Overview\n\nA hold repeats the last reading and bills actuals.\n\n"
        "## 2. Files to Implement\n\n"
        "| Order | File | Change Type | Description |\n"
        "|-------|------|-------------|-------------|\n"
        "| 1 | `meter/compile.py` | Modify | Validate hold windows. |\n"
        "| 2 | `web/src/meter.ts` | Modify | Repeat held readings. |\n"
        "| 3 | `web/tests/meter.test.ts` | Modify | Runtime tests. |\n\n"
        "## 3. Current State (for Modify/Delete files)\n\n"
        "### 3.1 `web/tests/meter.test.ts`\n\n"
        "```typescript\n"
        'it("reads a meter", () => {\n'
        "  expect(observe(plainMeter, 0).reading).toBe(10);\n"
        "});\n"
        "```\n\n"
        "## 6. Change Instructions\n\n"
        "### 6.1 `meter/compile.py` (Modify)\n\n"
        "```diff\n"
        "+def validate_holds(holds, ticks):\n"
        "+    return None\n"
        "```\n\n"
        f"{planned}\n"
        "## 10. Test Mapping\n\n"
        "### 10.1 Per-criterion test functions\n\n"
        "Rows 010 to 050 are tested in Python, rows 060 to 130 in Vitest.\n\n"
        f"{PYTHON_TESTS}\n{ts}{section_ten_extra}\n"
        "## 11. Implementation Notes\n\nNone.\n"
    )


def _missing_rows(spec: str) -> list[str]:
    return [c.row_id for c in criteria_coverage(spec, LLD).missing]


# ---------------------------------------------------------------------------
# T1 (R1): a TypeScript test the spec carries counts for its criterion
# ---------------------------------------------------------------------------


class TestVitestTestsCoverTheirCriteria:
    """AC1: rows 060 to 130 covered only by Vitest tests pass."""

    def test_rows_060_to_130_in_section_ten_pass(self):
        """T1: the real run's Section 10.1 shape. On main this reported all
        eight runtime rows missing."""
        spec = _spec(section_ten_rows=RUNTIME_ROWS)
        result = check_criteria_have_tests(spec, LLD)
        assert result["passed"] is True, result["details"]
        assert "13/13 LLD pass criteria" in result["details"]
        assert "8 of them TypeScript" in result["details"]

    def test_rows_060_to_130_in_a_planned_test_file_pass(self):
        """T1: the same tests carried only by Section 6's diff of a planned
        `.test.ts` file, read as the file reads after the diff."""
        spec = _spec(planned_rows=RUNTIME_ROWS)
        result = check_criteria_have_tests(spec, LLD)
        assert result["passed"] is True, result["details"]
        [(path, _text)] = planned_test_files(spec)
        assert path == "web/tests/meter.test.ts"

    def test_main_reported_every_runtime_row_missing(self):
        """The defect, pinned: the Python join alone sees none of them."""
        from assemblyzero.workflows.implementation_spec.criteria_coverage import (
            REQ_TAG,
            spec_tests,
        )

        spec = _spec(section_ten_rows=RUNTIME_ROWS)
        python_tags = {
            f"REQ-{n}" for _name, body in spec_tests(spec)
            for n in REQ_TAG.findall(body)
        }
        assert python_tags == {"REQ-1", "REQ-2", "REQ-3", "REQ-4"}

    def test_a_describe_title_names_the_criterion_of_the_tests_it_holds(self):
        text = (
            'describe("REQ-9: billing uses actuals", () => {\n'
            '  it("bills 5000", () => { expect(settle(m, 2).cost).toBe(5000); });\n'
            "});\n"
        )
        [test] = typescript_tests(text)
        assert test.title == "bills 5000"
        assert "REQ-9" in test.source

    def test_tsx_fences_are_read_with_the_tsx_grammar(self):
        spec = _spec(section_ten_extra=(
            "```tsx\n"
            'it("renders the held badge", () => {\n'
            "  // No hold omits the held key (REQ-7)\n"
            "  expect(render(<Badge held />)).toBeTruthy();\n"
            "});\n"
            "```\n"
        ))
        titles = [t.title for t in spec_typescript_tests(spec)]
        assert titles == ["renders the held badge"]


# ---------------------------------------------------------------------------
# T2 (R1): a criterion with no test in either language still fails
# ---------------------------------------------------------------------------


class TestAnUntestedCriterionStillFails:
    """AC1: crediting TypeScript does not credit what is not a test."""

    def test_row_110_with_no_test_in_either_language_fails(self):
        """T2."""
        rows = [r for r in RUNTIME_ROWS if r != "110"]
        spec = _spec(section_ten_rows=rows, planned_rows=rows)
        result = check_criteria_have_tests(spec, LLD)
        assert result["passed"] is False
        assert "REQ-9 (row 110)" in result["details"]
        assert "060" not in _missing_rows(spec)

    def test_a_todo_or_skipped_test_covers_nothing(self):
        rows = [r for r in RUNTIME_ROWS if r != "110"]
        spec = _spec(section_ten_rows=rows, section_ten_extra=(
            "```typescript\n"
            'it.todo("billing uses actuals during a hold (REQ-9)");\n'
            'it.skip("bills 5000 (REQ-9)", () => { expect(1).toBe(1); });\n'
            'test.skip("bills 5000 again (REQ-9)", () => {});\n'
            "```\n"
        ))
        assert "110" in _missing_rows(spec)

    def test_a_test_the_diff_removes_covers_nothing(self):
        rows = [r for r in RUNTIME_ROWS if r != "110"]
        removed = "\n".join("-  " + line for line in TS_TESTS["110"].splitlines())
        spec = _spec(planned_rows=rows).replace(
            "+});\n```", f"+}});\n{removed}\n```", 1,
        )
        assert removed in spec
        assert "110" in _missing_rows(spec)

    def test_a_current_state_excerpt_is_not_a_test_the_spec_carries(self):
        """Section 3 shows the file as it is; only Section 10 and the plan's
        Section 6 are tests the spec carries."""
        spec = _spec(section_ten_rows=[r for r in RUNTIME_ROWS if r != "110"])
        spec = spec.replace(
            'it("reads a meter", () => {',
            'it("reads a meter (REQ-9)", () => {',
        )
        assert "110" in _missing_rows(spec)

    def test_a_longer_tag_does_not_cover_a_shorter_one(self):
        """REQ-90 is not REQ-9."""
        rows = [r for r in RUNTIME_ROWS if r != "110"]
        spec = _spec(section_ten_rows=rows, section_ten_extra=(
            "```typescript\n"
            'it("bills (REQ-90)", () => { expect(settle(m, 2).cost).toBe(5000); });\n'
            "```\n"
        ))
        assert "110" in _missing_rows(spec)

    def test_a_planned_file_that_is_not_a_test_file_is_not_read(self):
        spec = _spec().replace(
            "## 10. Test Mapping",
            "### 6.5 `web/src/meter.ts` (Modify)\n\n"
            "```typescript\n"
            'it("bills (REQ-9)", () => { expect(settle(m, 2).cost).toBe(5000); });\n'
            "```\n\n"
            "## 10. Test Mapping",
        )
        assert planned_test_files(spec) == []
        assert "110" in _missing_rows(spec)


# ---------------------------------------------------------------------------
# T3 (R2): the recurrence halt names its gate and carries a class
# ---------------------------------------------------------------------------

#: A draft with no test that cites a criterion: `criteria_have_tests` names the
#: same rows every round, whatever pinning does. Other checks fail on so thin
#: a draft too, and the halt names each of them beside it.
UNCOVERED = "# Spec\n\n" + ("body line\n" * 40)

REFUSAL = (
    "[PINNING] refused: 2 line(s) starting '- `tick == 0` in `ticks` -> "
    "raises `AssertionError(\"hold' — locked content the verdict did not "
    "name (#2532)"
)
CONSERVATION = (
    "[PINNING] CONSERVATION: the revision removed 1 test(s) no verdict named "
    "(test_req_040_compiler_rejects_tick_bounds) -- revision refused entire, "
    "previous draft kept (#2559)"
)


class TestTheRecurrenceHaltNamesItsGate:
    """AC2: the halt for the recurrence shape carries a named class."""

    @pytest.fixture(autouse=True)
    def _repo(self, tmp_path):
        self.repo = str(tmp_path)

    def _state(self, shown=(), breakdown=(), events=()):
        return {
            "spec_draft": UNCOVERED,
            "files_to_modify": [],
            "pattern_references": [],
            "repo_root": self.repo,
            "lld_content": LLD,
            "review_iteration": 3,
            "max_iterations": 3,
            "checks_shown_to_drafter": list(shown),
            "prior_completeness_breakdown": [dict(e) for e in breakdown],
            "pinning_events": list(events),
        }

    def _halt(self, events, capsys):
        first = validate_completeness(self._state())
        failures = first["completeness_issues"]
        assert any("have no test in the spec" in f for f in failures)
        out = validate_completeness(self._state(
            shown=first["checks_shown_to_drafter"],
            breakdown=[{"iteration": i, "failures": list(failures)} for i in range(3)],
            events=events,
        ))
        capsys.readouterr()
        return out["error_message"]

    def test_refusals_name_the_completeness_check_and_classify(self, capsys):
        """T3: the shape of the real halt, which was classed `unknown`."""
        message = self._halt([REFUSAL, REFUSAL], capsys)
        assert message.startswith("Iteration cap:")
        assert "[RECURRENCE UNDER PINNING]" in message
        opening = "Gate that blocked progress: the completeness check(s) "
        assert opening in message, message
        gate = message[message.index(opening):message.index("(spec.completeness_cap)")]
        assert "criteria_have_tests" in gate
        assert "deadlocked" not in message
        assert classify_error(message) == "completeness_recurrence_under_pinning"

        plan = generate_recovery_plan(
            issue_number=7, workflow="implementation_spec",
            stage="N3_validate_completeness",
            error_type=classify_error(message), error_message=message, state={},
        )
        assert plan.error_type != "unknown"
        assert plan.is_transient is False
        assert "Gate that blocked progress: the completeness check" in plan.recommendation
        assert "Unfixed" not in plan.recommendation

    def test_a_conservation_override_names_the_conservation_gate(self, capsys):
        message = self._halt([CONSERVATION], capsys)
        assert (
            "Gate that blocked progress: the conservation gate "
            "(spec.conservation_gate)"
        ) in message
        assert classify_error(message) == "completeness_recurrence_under_pinning"

    def test_with_no_reversion_the_halt_keeps_its_old_reading(self, capsys):
        """The marker belongs to the recurrence under pinning only."""
        message = self._halt([], capsys)
        assert "[RECURRENCE UNDER PINNING]" not in message
        assert "reached the check unchanged" in message


# ---------------------------------------------------------------------------
# T4 (R3): a line answering a named completeness complaint survives pinning
# ---------------------------------------------------------------------------

#: A previous draft holding a Vitest placeholder for row 110 under its own
#: heading, which no verdict and no complaint token names.
PLACEHOLDER = '  it.todo("row 110 billing");'
PREVIOUS = _spec(
    section_ten_rows=[r for r in RUNTIME_ROWS if r != "110"],
).replace(
    "## 11. Implementation Notes",
    "### 10.2 Runtime placeholders\n\n"
    "```typescript\n"
    'describe("pending", () => {\n'
    f"{PLACEHOLDER}\n"
    "});\n"
    "```\n\n"
    "## 11. Implementation Notes",
)
ANSWER = '  it("bills actuals during a hold (REQ-9)", () => { expect(settle(m, 2).cost).toBe(5000); });'


class TestAnAnswerToANamedComplaintSurvivesPinning:
    """AC3: what pinning lets through for completeness."""

    def _complaint(self) -> str:
        result = check_criteria_have_tests(PREVIOUS, LLD)
        assert result["passed"] is False
        assert "REQ-9 (row 110)" in result["details"]
        return result["details"]

    def test_the_placeholder_is_locked_by_naming_alone(self):
        """The precondition: no token the complaint names is in the
        placeholder's block, so naming alone would refuse the change."""
        tokens = named_tokens("", [self._complaint()])
        block = PREVIOUS[PREVIOUS.index("### 10.2"):PREVIOUS.index("## 11.")]
        assert not any(token in block.lower() for token in tokens)

    def test_the_answering_line_survives_through_the_real_call_site(self, capsys):
        """T4: the drafter replaces the placeholder with the test the check
        named; pinning passes it, and the check then passes."""
        complaint = self._complaint()
        revised = PREVIOUS.replace(PLACEHOLDER, ANSWER)
        text, events = _apply_pinning(
            {}, PREVIOUS, revised,
            response="", review_feedback="", completeness_issues=[complaint],
        )
        capsys.readouterr()
        assert ANSWER in text
        assert not any("refused" in event for event in events)
        assert not any("REGRESSION CLASS" in event for event in events)
        assert any("completeness answer passed" in event for event in events)
        assert check_criteria_have_tests(text, LLD)["passed"] is True

    def test_without_the_answer_vocabulary_the_line_was_refused(self):
        """The defect, pinned: the same revision under naming alone."""
        complaint = self._complaint()
        revised = PREVIOUS.replace(PLACEHOLDER, ANSWER)
        result = enforce_pinning(
            PREVIOUS, revised,
            current_tokens=named_tokens("", [complaint]),
            additions_demanded=True,
        )
        assert PLACEHOLDER in result.text
        assert result.refusals

    def test_a_line_that_answers_nothing_is_still_refused(self, capsys):
        complaint = self._complaint()
        revised = PREVIOUS.replace(
            PLACEHOLDER, '  it("bills something (REQ-90)", () => {});',
        )
        text, events = _apply_pinning(
            {}, PREVIOUS, revised,
            response="", review_feedback="", completeness_issues=[complaint],
        )
        capsys.readouterr()
        assert PLACEHOLDER in text
        assert any("refused" in event for event in events)

    def test_the_vocabulary_reads_the_complaints_keys_and_tokens(self):
        answers = complaint_answers([self._complaint()])
        assert answers.keys == {"REQ-9"}
        assert "settle()" in answers.tokens
        assert answers.answered_by(["// (REQ-9)"])
        assert not answers.answered_by(["// (REQ-90)"])
        assert complaint_answers([]).answered_by([ANSWER]) is False

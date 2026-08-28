"""Injection puts a subsection inside Section 3; extraction must survive it (#2628).

The observed case, as a fixture. boostgauge's `run-issue331-152355` halted at
the iteration cap with `Coverage: 0.0% (0/0 requirements)` and
`No requirements found in Section 3`, three revisions spent, 652s.

**The diagnosis in the issue is refuted by its own artifact, and this file
pins the correction.** The halt was read as a format war -- a machine-owned
table the drafter cannot remove versus a validator demanding numbered-list-
only. The preserved draft carries BOTH: the injected S1-S9 block, and a
four-item numbered list written around it, exactly as both sets of guidance
asked. The drafter complied. Extraction returned zero anyway, because
`### 3.1 Source Decision Table (injected verbatim)` -- a heading injection
itself inserts -- terminated a section boundary that ended at "the next
heading starting with a digit".

Two defects, one seam, both measured on this fixture:

* the section boundary was not level-aware, so Section 3 captured 62
  characters -- a blank line and an HTML comment;
* `strip_injection` let a STRAY begin marker swallow 125 lines including
  Sections 1-3, which was one revision round from firing for real.

The requirements are the DRAFTER's four numbered items, not the table's nine
rows. #2612's own injected preamble says so -- *"Cite these IDs from the
requirements and test-plan sections; do not restate their values"* -- and the
draft's 13 scenarios cite `(REQ-1)`..`(REQ-4)` and no S-ID.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from assemblyzero.core.section_utils import drafter_authored, section_body
from assemblyzero.core.validation.test_plan_validator import (
    check_requirement_coverage,
    extract_requirements,
    extract_test_scenarios,
)
from assemblyzero.workflows.requirements.table_injection import (
    BEGIN_MARKER,
    END_MARKER,
    injected_line_span,
    strip_injection,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures" / "section3" / "lld-331-run152355-failed-iter3.md"
)


@pytest.fixture
def halted_draft() -> str:
    return FIXTURE.read_text(encoding="utf-8")


#: A pre-injection LLD: numbered list, no machine-owned block. The control for
#: every assertion below -- the ordinary format must stay legal.
PLAIN_LLD = """\
# Issue #7: a plain LLD

## 3. Requirements

1. The logger shall write to the configured directory.
2. The logger shall create that directory when absent.

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Expected |
|----|----------|------|----------|
| 010 | Writes to the directory (REQ-1) | Auto | file exists |
| 020 | Creates it when absent (REQ-2) | Auto | dir exists |
"""


class TestTheObservedCase:
    """run-152355, inverted."""

    def test_the_fixture_reproduces_the_shape(self, halted_draft: str) -> None:
        """Guard: everything below is vacuous if the artifact is not the one
        that halted."""
        assert halted_draft.count(BEGIN_MARKER) == 2, "stray + canonical BEGIN"
        assert halted_draft.count(END_MARKER) == 1, "only the canonical END"
        assert "### 3.1 Source Decision Table" in halted_draft
        assert re.search(r"(?m)^1\. When `render_face", halted_draft)

    def test_requirements_extract(self, halted_draft: str) -> None:
        reqs = extract_requirements(halted_draft)
        assert [r["id"] for r in reqs] == ["REQ-1", "REQ-2", "REQ-3", "REQ-4"]

    def test_the_denominator_is_nonzero_and_coverage_passes(
        self, halted_draft: str
    ) -> None:
        """The acceptance's real intent: a nonzero denominator and no format
        revision. Four, not nine -- the number the artifact justifies."""
        reqs = extract_requirements(halted_draft)
        tests = extract_test_scenarios(halted_draft)

        passed, pct, violations = check_requirement_coverage(reqs, tests)

        assert len(reqs) == 4
        assert pct == 100.0
        assert passed is True
        assert violations == []

    def test_no_requirement_is_the_injected_table(self, halted_draft: str) -> None:
        """The nine S-rows are a binding-value reference the requirements
        cite, by #2612's own preamble. Reading them as requirements would
        report nine uncovered requirements on an artifact whose scenarios
        cite none of them."""
        texts = " ".join(r["text"] for r in extract_requirements(halted_draft))
        for row_id in ("S1", "S5", "S9"):
            assert f"| {row_id} |" not in texts

    def test_the_scenarios_cite_only_the_numbered_requirements(
        self, halted_draft: str
    ) -> None:
        cited = set(re.findall(r"\(REQ-(\d+)\)", halted_draft))
        assert cited == {"1", "2", "3", "4"}


class TestTheSectionBoundaryIsLevelAware:
    def test_a_deeper_heading_does_not_end_the_section(
        self, halted_draft: str
    ) -> None:
        body = section_body(
            drafter_authored(halted_draft),
            re.compile(r"3\.?\s*Requirements\b", re.IGNORECASE),
        )
        assert body is not None
        assert "1. When `render_face" in body

    def test_a_same_level_heading_does_end_it(self, halted_draft: str) -> None:
        """The control. Without it, a boundary that never ends would pass the
        test above."""
        body = section_body(
            drafter_authored(halted_draft),
            re.compile(r"3\.?\s*Requirements\b", re.IGNORECASE),
        )
        assert "## 4. Alternatives Considered" not in body
        assert "Alternatives Considered" not in body

    def test_a_missing_section_reports_none(self) -> None:
        assert section_body(
            "# Doc\n\n## 2. Design\n\nprose\n",
            re.compile(r"3\.?\s*Requirements\b", re.IGNORECASE),
        ) is None

    def test_the_last_section_runs_to_the_end(self) -> None:
        body = section_body(
            "# Doc\n\n## 3. Requirements\n\n1. only item\n",
            re.compile(r"3\.?\s*Requirements\b", re.IGNORECASE),
        )
        assert "1. only item" in body


class TestStrayMarkersCannotEatTheDocument:
    """The second defect, and the more dangerous one.

    `reassert` runs on every lld draft and `apply_injection` strips first, so
    an over-reaching span deletes Section 3 and then cannot find `## 3.` to
    insert at. The halt this issue reports is what stopped that from firing.
    """

    def test_the_span_is_the_real_block(self, halted_draft: str) -> None:
        assert injected_line_span(halted_draft) == (108, 126)

    def test_stripping_preserves_every_section(self, halted_draft: str) -> None:
        stripped = strip_injection(halted_draft)
        for heading in ("## 1. Context", "## 2.", "## 3. Requirements", "## 4."):
            assert heading in stripped, f"{heading} was destroyed by the strip"

    def test_stripping_removes_the_block_itself(self, halted_draft: str) -> None:
        """The control: the stripper must still do its job."""
        stripped = strip_injection(halted_draft)
        assert "| S1 | Dial face" not in stripped
        assert END_MARKER not in stripped

    def test_a_stray_begin_is_left_alone(self, halted_draft: str) -> None:
        """It is the drafter's own text; removing it is not this rule's job."""
        stripped = strip_injection(halted_draft)
        assert BEGIN_MARKER in stripped

    def test_a_lone_stray_pair_strips_nothing(self) -> None:
        doc = (
            "# Doc\n\n" + BEGIN_MARKER + "\n"
            "<!-- END MACHINE-OWNED: with extra text -->\n\n"
            "## 3. Requirements\n\n1. a requirement\n"
        )
        assert strip_injection(doc) == doc
        assert extract_requirements(doc)[0]["id"] == "REQ-1"


class TestThePreInjectionFormatStaysLegal:
    """A repo or issue with no decision table must extract exactly as before."""

    def test_a_plain_numbered_list_extracts(self) -> None:
        reqs = extract_requirements(PLAIN_LLD)
        assert [r["id"] for r in reqs] == ["REQ-1", "REQ-2"]

    def test_it_reaches_full_coverage(self) -> None:
        reqs = extract_requirements(PLAIN_LLD)
        tests = extract_test_scenarios(PLAIN_LLD)
        passed, pct, _violations = check_requirement_coverage(reqs, tests)
        assert passed is True
        assert pct == 100.0

    def test_a_genuinely_empty_section_still_reports_zero(self) -> None:
        """#2546/#2552 undisturbed: 0/0 must keep failing loudly. The fix is
        the extractor's boundary, never the zero-denominator law."""
        empty = "# Doc\n\n## 3. Requirements\n\nProse, no numbered items.\n"
        assert extract_requirements(empty) == []

    def test_a_zero_denominator_still_blocks(self) -> None:
        empty = "# Doc\n\n## 3. Requirements\n\nProse only.\n"
        passed, pct, violations = check_requirement_coverage(
            extract_requirements(empty), []
        )
        assert passed is False
        assert pct == 0.0
        assert any("No requirements found" in v["message"] for v in violations)


class TestTheUnwinnableLoopIsGone:
    """A draft whose only 'defect' was table-format requirements must not
    consume a revision."""

    def test_the_halted_draft_now_passes_the_test_plan_validator(
        self, halted_draft: str
    ) -> None:
        from assemblyzero.core.validation.test_plan_validator import (
            validate_test_plan,
        )

        result = validate_test_plan(halted_draft)

        coverage_errors = [
            v for v in result["violations"]
            if v["check_type"] == "coverage" and v["severity"] == "error"
        ]
        assert coverage_errors == [], coverage_errors

    def test_the_guidance_no_longer_forbids_what_injection_emits(self) -> None:
        """Guidance contradicting the pipeline's own output is how this fired."""
        from assemblyzero.workflows.requirements.nodes.validate_test_plan import (
            _build_validation_feedback,
        )

        feedback = _build_validation_feedback({
            "passed": False,
            "coverage_percentage": 0.0,
            "mapped_count": 0,
            "requirements_count": 0,
            "violations": [{
                "check_type": "coverage", "severity": "error",
                "requirement_id": None, "test_id": None,
                "message": "No requirements found in Section 3",
                "line_number": None,
            }],
        })

        assert "Do NOT use tables, bullet points, or REQ-ID prefixes" not in feedback
        assert "MACHINE-OWNED" in feedback
        assert "AFTER any machine-owned block" in feedback

    def test_the_drafter_prompt_says_the_same_thing(self) -> None:
        """Two guidance surfaces, one rule -- they disagreed before."""
        source = (
            Path(__file__).resolve().parents[2]
            / "assemblyzero" / "workflows" / "requirements" / "nodes"
            / "generate_draft.py"
        ).read_text(encoding="utf-8")
        assert "machine-owned block in that section (#2628)" in source


class TestBothExtractorsAgree:
    """#1698: one definition of where Section 3 ends, used by both readers.

    The testing workflow's own `extract_requirements` had the identical defect
    -- its lookahead `(?=\\n##|\\Z)` fired on `### 3.1` because `###` starts
    with `##` -- and measured 0 on this same fixture.
    """

    def test_the_testing_workflow_extractor_agrees(self, halted_draft: str) -> None:
        from assemblyzero.workflows.testing.nodes.load_lld import (
            extract_requirements as testing_extract,
        )

        ids = [r.split(":")[0] for r in testing_extract(halted_draft)]
        assert ids == ["REQ-1", "REQ-2", "REQ-3", "REQ-4"]

    def test_both_agree_on_the_plain_lld_too(self) -> None:
        from assemblyzero.workflows.testing.nodes.load_lld import (
            extract_requirements as testing_extract,
        )

        validator_ids = [r["id"] for r in extract_requirements(PLAIN_LLD)]
        testing_ids = [r.split(":")[0] for r in testing_extract(PLAIN_LLD)]
        assert validator_ids == testing_ids == ["REQ-1", "REQ-2"]

    def test_neither_reads_the_boundary_for_itself(self) -> None:
        """Structural: a second lookahead is how they drifted the first time.

        Read by PATH, not through the module object: `nodes/__init__` binds
        `load_lld` to the FUNCTION of that name, so the attribute has no
        `__file__`.

        Comment lines are excluded before matching. Both modules deliberately
        quote the old lookaheads to explain what went wrong, and a bare
        substring ban would forbid recording the lesson -- the same trap the
        #2615 sweep hit with `updatedAt`.
        """
        root = Path(__file__).resolve().parents[2] / "assemblyzero"
        sources = (
            root / "core" / "validation" / "test_plan_validator.py",
            root / "workflows" / "testing" / "nodes" / "load_lld.py",
        )
        for path in sources:
            code = "\n".join(
                line for line in path.read_text(encoding="utf-8").splitlines()
                if not line.lstrip().startswith("#")
            )
            assert "?=^#{1,3}" not in code, path.name
            assert r"(?=\n##|\Z)" not in code, path.name

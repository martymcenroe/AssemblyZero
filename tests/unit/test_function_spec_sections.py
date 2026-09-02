"""The structural fact-verifier that replaces a window scan (#2620).

`functions_have_io_examples` searches +/-2000 characters around each `def` for
an I/O vocabulary word and any concrete-looking value. That cannot tell whether
the example belongs to the function it is grading -- neighbouring definitions
share the window -- so the operator ruled it a proxy and demoted it.

This check asks a bounded question instead: does the `### 5.N` subsection that
documents a function, between its own heading and the next one, carry the
`**Input Example:**` and `**Output Example:**` blocks template 0701 requires?
Presence within a region is a fact.

**The difference is provable, and `TestTheWindowScanCannotDoThis` proves it**:
one fixture where a neighbour's example satisfies the window scan and this
check still fails. Without that test, "structural" is a claim about intent
rather than a property of the code.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_function_spec_sections_have_examples,
    check_functions_have_io_examples,
    function_spec_sections,
)

DOCUMENTED = """\
### 5.1 `render_face()`

**Signature:**

```python
def render_face(width: int) -> bytes:
    ...
```

**Input Example:**

```python
width = 1024
```

**Output Example:**

```python
b"\\x89PNG..."
```
"""

UNDOCUMENTED = """\
### 5.2 `_draw_ticks()`

**Signature:**

```python
def _draw_ticks(surface) -> None:
    ...
```
"""


def spec(*sections: str) -> str:
    return (
        "# Implementation Spec\n\n## 1. Overview\n\nRender.\n\n"
        "## 5. Function Specifications\n\n" + "\n".join(sections)
        + "\n## 10. Test Mapping\n\n- covered\n"
    )


class TestPresenceIsAFact:
    def test_a_fully_documented_section_passes(self) -> None:
        result = check_function_spec_sections_have_examples(spec(DOCUMENTED))
        assert result["passed"] is True
        assert "All 1 function-specification" in result["details"]

    def test_a_section_missing_both_blocks_fails(self) -> None:
        result = check_function_spec_sections_have_examples(spec(UNDOCUMENTED))
        assert result["passed"] is False
        assert "_draw_ticks()" in result["details"]

    def test_a_section_missing_only_the_output_block_fails(self) -> None:
        half = DOCUMENTED.replace("**Output Example:**", "**Edge Cases:**")
        result = check_function_spec_sections_have_examples(spec(half))
        assert result["passed"] is False
        assert "**Output Example:**" in result["details"]
        assert "**Input Example:**" not in result["details"]

    def test_it_names_every_missing_section(self) -> None:
        result = check_function_spec_sections_have_examples(
            spec(UNDOCUMENTED, UNDOCUMENTED.replace("5.2", "5.3"))
        )
        assert result["passed"] is False
        assert "2 of 2" in result["details"]

    def test_a_mixed_spec_names_only_the_gap(self) -> None:
        result = check_function_spec_sections_have_examples(
            spec(DOCUMENTED, UNDOCUMENTED)
        )
        assert result["passed"] is False
        assert "1 of 2" in result["details"]
        assert "_draw_ticks()" in result["details"]
        assert "render_face()" not in result["details"]


class TestNotApplicableIsNotFailure:
    def test_a_spec_with_no_function_sections_passes(self) -> None:
        result = check_function_spec_sections_have_examples(
            "# Spec\n\n## 1. Overview\n\nNo functions.\n"
        )
        assert result["passed"] is True
        assert "not applicable" in result["details"]

    def test_an_empty_spec_passes(self) -> None:
        assert check_function_spec_sections_have_examples("")["passed"] is True

    def test_other_numbered_sections_are_not_graded(self) -> None:
        """The control: only section 5 subsections. A `### 6.1` is a change
        instruction and owes no example block."""
        other = "### 6.1 `path/to/file.py` (Add)\n\nNo examples here.\n"
        assert check_function_spec_sections_have_examples(
            spec(DOCUMENTED) + other
        )["passed"] is True


class TestTheWindowScanCannotDoThis:
    """The reason this check exists, as a measurement rather than a claim."""

    def test_a_neighbours_example_satisfies_the_window_but_not_the_section(
        self,
    ) -> None:
        """`_draw_ticks` carries no example of its own; `render_face`'s sits a
        few hundred characters away. The window scan is satisfied by proximity.
        The structural check is not, because the example is in another
        subsection's bounds."""
        draft = spec(DOCUMENTED, UNDOCUMENTED)

        window = check_functions_have_io_examples(draft)
        structural = check_function_spec_sections_have_examples(draft)

        assert window["passed"] is True, (
            "the fixture must reproduce the window scan's blind spot, or the "
            "comparison below proves nothing"
        )
        assert structural["passed"] is False
        assert "_draw_ticks()" in structural["details"]

    def test_both_agree_when_everything_is_documented(self) -> None:
        """The control: the structural check is stricter, never merely
        different -- it must not fail what the window scan passes for good
        reason."""
        draft = spec(DOCUMENTED)

        assert check_functions_have_io_examples(draft)["passed"] is True
        assert check_function_spec_sections_have_examples(draft)["passed"] is True


class TestSectionBounds:
    def test_a_section_ends_at_the_next_heading(self) -> None:
        sections = function_spec_sections(spec(UNDOCUMENTED, DOCUMENTED))
        assert len(sections) == 2
        first_body = sections[0][1]
        assert "_draw_ticks" in first_body
        assert "render_face" not in first_body, (
            "a subsection's body must not run into the next one"
        )

    def test_the_heading_line_is_reported(self) -> None:
        draft = spec(DOCUMENTED)
        _heading, _body, line_no = function_spec_sections(draft)[0]
        assert draft.splitlines()[line_no - 1].startswith("### 5.1")


class TestItPassesOnRealSpecs:
    """Verified against boostgauge's preserved specs, read-only.

    Both follow template 0701 exactly -- #331's spec carries seven `### 5.N`
    subsections and seven Input Examples, #1's carries two and two -- so this
    gate passes on real work rather than blocking the roll it was built for.
    The fixture below is the shape those specs actually have.
    """

    @pytest.mark.parametrize("count", [2, 7])
    def test_a_spec_shaped_like_the_preserved_ones_passes(self, count: int) -> None:
        sections = [
            DOCUMENTED.replace("5.1", f"5.{n}").replace(
                "render_face", f"fn_{n}"
            )
            for n in range(1, count + 1)
        ]
        result = check_function_spec_sections_have_examples(spec(*sections))

        assert result["passed"] is True
        assert f"All {count} function-specification" in result["details"]


class TestTheComplaintIsAddressable:
    """#2617's discipline: a new gate's message must name a draft line before
    it ships, or it is the #2555 deadlock class wearing a new artifact."""

    def test_the_message_names_the_subsection_heading_verbatim(self) -> None:
        draft = spec(UNDOCUMENTED)
        details = check_function_spec_sections_have_examples(draft)["details"]

        heading = "### 5.2 `_draw_ticks()`"
        assert heading in details
        assert heading in draft, "the cited heading must occur in the draft"

    def test_the_message_carries_a_dashed_line_citation(self) -> None:
        """`named_line_ranges` requires the dash (#2555), so a bare line
        number would address nothing."""
        import re

        details = check_function_spec_sections_have_examples(
            spec(UNDOCUMENTED)
        )["details"]

        assert re.search(r"line \d+-\d+", details), details


#: The shape that halted boostgauge #421's fifth launch: an Input Example
#: fence that OPENS with a Python comment. `# Called on ...` matches `^#\s`
#: exactly as a markdown heading does, so the subsection ended at the comment
#: and the `**Output Example:**` four lines below it fell outside the region
#: the check measures (#2687).
COMMENT_IN_FENCE = """\
### 5.3 `Telltale.current_peak()`

**Signature:**

```python
def current_peak(self) -> Optional[float]:
    ...
```

**Input Example:**

```python
# Assuming instance history: Sample(0.0, 100.0) -> departed at 10.0
# window = 10.0, decay_rate = 15.0
```

**Output Example:**

```python
70.0 # Evaluates: 100.0 - 15.0 * (12.0 - 10.0)
```
"""

#: The same shape with the Output Example genuinely absent. The fix must not
#: buy its silence by widening the region into a pass for everything.
COMMENT_IN_FENCE_TRULY_MISSING = """\
### 5.4 `Telltale.reset()`

**Signature:**

```python
def reset(self) -> None:
    ...
```

**Input Example:**

```python
# Called on a Telltale instance with active history
```
"""


class TestAFenceIsNotProse:
    """A `#` comment inside a code sample is not a heading (#2687).

    The check's verdict turned on whether the model happened to open an
    example with a comment -- the accident-of-phrasing dependence #2620
    demoted the window scan for, inherited by its replacement in a different
    place. `revision_pinning._blocks` already tracks fence state against the
    same document (#2681); this is that rule in the one place that lacked it.
    """

    def test_a_comment_opening_the_example_fence_does_not_end_the_section(
        self,
    ) -> None:
        sections = function_spec_sections(spec(COMMENT_IN_FENCE))

        assert len(sections) == 1
        body = sections[0][1]
        assert "**Output Example:**" in body, (
            "the block is four lines below the comment and inside the "
            "subsection; a fence-blind bound hides it"
        )

    def test_the_check_passes_on_a_documented_section_that_uses_comments(
        self,
    ) -> None:
        result = check_function_spec_sections_have_examples(
            spec(COMMENT_IN_FENCE)
        )

        assert result["passed"] is True, result["details"]

    def test_a_genuinely_missing_block_still_fails(self) -> None:
        """The gate is not turned off -- same fence, same comment, no block."""
        result = check_function_spec_sections_have_examples(
            spec(COMMENT_IN_FENCE_TRULY_MISSING)
        )

        assert result["passed"] is False
        assert "**Output Example:**" in result["details"]
        assert "### 5.4 `Telltale.reset()`" in result["details"]

    def test_the_verdict_no_longer_depends_on_whether_a_comment_was_written(
        self,
    ) -> None:
        """The discriminating fact, stated as a test.

        Before the fix these two drafts -- identical but for a comment line
        inside the Input Example fence -- got opposite verdicts.
        """
        with_comment = check_function_spec_sections_have_examples(
            spec(COMMENT_IN_FENCE)
        )
        without_comment = check_function_spec_sections_have_examples(
            spec(COMMENT_IN_FENCE.replace(
                "# Assuming instance history: Sample(0.0, 100.0) "
                "-> departed at 10.0\n# window = 10.0, decay_rate = 15.0\n",
                "history = [Sample(0.0, 100.0)]\n",
            ))
        )

        assert with_comment["passed"] == without_comment["passed"] is True

    def test_a_fenced_heading_does_not_open_a_phantom_subsection(self) -> None:
        """A spec quoting template 0701 inside a fence adds no sections."""
        quoting = (
            "### 5.1 `render_face()`\n\n"
            "**Signature:**\n\n"
            "```markdown\n"
            "### 5.9 `not_a_real_function()`\n"
            "```\n\n"
            "**Input Example:**\n\n```python\nwidth = 1024\n```\n\n"
            "**Output Example:**\n\n```python\nb\"png\"\n```\n"
        )
        sections = function_spec_sections(spec(quoting))

        assert [s[0] for s in sections] == ["### 5.1 `render_face()`"]

    def test_an_unterminated_fence_swallows_the_remainder(self) -> None:
        """The generous bound, chosen deliberately.

        This check's failure direction is a false alarm that halts the stage,
        so an over-wide region costs a missed complaint while an over-narrow
        one costs a launch.
        """
        sections = function_spec_sections(
            spec("### 5.1 `f()`\n\n```python\n# never closed\n")
        )

        assert len(sections) == 1
        assert "never closed" in sections[0][1]


@pytest.fixture(scope="module")
def draft() -> str:
    """The preserved draft, byte-for-byte."""
    from pathlib import Path

    path = (
        Path(__file__).parent.parent
        / "fixtures" / "boostgauge41_fenced_comment" / "001-spec-draft.md"
    )
    return path.read_text(encoding="utf-8")


class TestTheDraftThatHaltedLaunchFive:
    """The preserved artifact, whole (#2687).

    `001-spec-draft.md` from boostgauge run `run-issue41-184913`
    (`data/speedrun/reset-artifacts/issue-41/lineage/
    41-implspec-20260902T010133Z/2026-09-02T00-42-11Z/`), byte-for-byte. The
    spec stage halted non-transient on it after three refused or no-op
    revisions. All four of its subsections carry both blocks; two read as
    missing because their example fences open with a comment.
    """

    def test_every_subsection_carries_both_blocks(self, draft: str) -> None:
        sections = function_spec_sections(draft)

        assert len(sections) == 4
        for heading, body, _line in sections:
            assert "**Input Example:**" in body, heading
            assert "**Output Example:**" in body, heading

    def test_the_check_passes_so_no_revision_is_demanded(
        self, draft: str
    ) -> None:
        result = check_function_spec_sections_have_examples(draft)

        assert result["passed"] is True, result["details"]
        assert "All 4 function-specification" in result["details"]

    def test_the_two_hidden_blocks_are_where_the_run_could_not_see_them(
        self, draft: str
    ) -> None:
        """Named exactly, so a regression points at the same two lines."""
        lines = draft.splitlines()

        assert lines[127].startswith("# Assuming instance history:")
        assert lines[131] == "**Output Example:**"
        assert lines[156].startswith("# Called on a Telltale instance")
        assert lines[159] == "**Output Example:**"

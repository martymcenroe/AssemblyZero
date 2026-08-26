"""Revisions edit the named items; what passed stays passed (#2532).

The fixture is the observed S2 regression from boostgauge #331,
run-issue331-233939: the band-background trap (`test_req_2_s2_redline_band`
— a between-tick pixel at 0.95 R in the 60-100 arc is band crimson, not face
black) was flagged early, FIXED by round 9, then REINTRODUCED by the resumed
grant's regeneration while the verdict was naming a different test entirely.
These tests pin that exact shape: the fix survives mechanically, and the
attempt to un-fix it is flagged at the moment it happens.
"""

from __future__ import annotations

from assemblyzero.workflows.implementation_spec.revision_pinning import (
    enforce_pinning,
    named_line_flags,
    named_tokens,
    unlock_requested,
)

#: The reviewed draft: S2 carries its round-9 fix; the wordmark test is the
#: one the CURRENT verdict names.
PREVIOUS = """# Spec

## Section 10: Tests

```python
def test_req_2_s2_redline_band():
    # S2: between-tick pixel at 0.95 R in the 60-100 arc is BAND, not face
    sample = face.getpixel(polar(0.95, value=75))
    assert classify(sample) == "crimson"

def test_req_7_wordmark():
    band = face.crop(wordmark_box())
    assert cap_height(band) == 0.09
```

## Section 11: Conventions

Baselines are self-generated only.
"""

#: The verdict names ONLY the wordmark test.
VERDICT = (
    "REVISE: `test_req_7_wordmark` measures cap height against the wrong "
    "box; compute wordmark_box() from the 0.67 R band centre."
)

#: The regeneration: fixes the named test AND silently reverts S2's fix —
#: the observed un-fixing class.
REGENERATED = """# Spec

## Section 10: Tests

```python
def test_req_2_s2_redline_band():
    # between ticks the face shows through
    sample = face.getpixel(polar(0.95, value=75))
    assert classify(sample) == "face"

def test_req_7_wordmark():
    band = face.crop(wordmark_box(centre=0.67))
    assert cap_height(band) == 0.09
```

## Section 11: Conventions

Baselines are self-generated only.
"""


class TestNamedTokens:
    def test_backticked_and_test_names_extract(self):
        tokens = named_tokens(VERDICT)
        assert "test_req_7_wordmark" in tokens

    def test_completeness_issues_name_too(self):
        tokens = named_tokens("", ["missing excerpt for `stingray.py`"])
        assert "stingray.py" in tokens

    def test_manifest_row_ids_extract(self):
        assert "n4.2" in named_tokens("row N4.2 is asserted twice")


class TestNamedLineFlags:
    def test_the_named_test_block_is_named_and_s2_is_not(self):
        flags = named_line_flags(PREVIOUS, named_tokens(VERDICT))
        lines = PREVIOUS.splitlines()
        s2_line = next(
            i for i, line in enumerate(lines) if "crimson" in line
        )
        wordmark_line = next(
            i for i, line in enumerate(lines) if "wordmark_box" in line
        )
        assert flags[wordmark_line] is True
        assert flags[s2_line] is False

    def test_no_tokens_means_nothing_named(self):
        assert not any(named_line_flags(PREVIOUS, set()))


class TestTheS2Regression:
    """The issue's own case, end to end."""

    def test_the_unfix_is_refused_and_the_fix_survives(self):
        result = enforce_pinning(
            PREVIOUS, REGENERATED, current_tokens=named_tokens(VERDICT),
        )
        assert 'assert classify(sample) == "crimson"' in result.text, (
            "round 9's fix must carry forward byte-verbatim"
        )
        assert '== "face"' not in result.text
        assert result.refusals, "the locked-content change must be refused"

    def test_the_named_fix_still_lands(self):
        result = enforce_pinning(
            PREVIOUS, REGENERATED, current_tokens=named_tokens(VERDICT),
        )
        assert "wordmark_box(centre=0.67)" in result.text, (
            "pinning must never block the change the verdict asked for"
        )

    def test_the_regression_event_fires_at_the_moment_it_happens(self):
        """Ask 3: 'revision modified content no verdict ever objected to'
        is a flagged event — visible now, not one round later."""
        history = [VERDICT, "REVISE: `test_req_9_bezel` samples inside the seat."]
        ever = set()
        for feedback in history:
            ever |= named_tokens(feedback)
        result = enforce_pinning(
            PREVIOUS, REGENERATED,
            current_tokens=named_tokens(VERDICT), ever_tokens=ever,
        )
        assert result.regressions, "the S2-class event must be flagged"
        assert any("s2" in r.lower() or "crimson" in r.lower() or "between" in r.lower()
                   for r in result.regressions), result.regressions

    def test_a_change_a_prior_round_named_is_not_a_regression(self):
        """Content SOME verdict once objected to is not the never-objected
        class, even when the current verdict does not name it."""
        history_naming_s2 = named_tokens(
            "REVISE: `test_req_2_s2_redline_band` asserts face where the "
            "band shows."
        ) | named_tokens(VERDICT)
        result = enforce_pinning(
            PREVIOUS, REGENERATED,
            current_tokens=named_tokens(VERDICT),
            ever_tokens=history_naming_s2,
        )
        assert result.regressions == ()


class TestUnlock:
    def test_unlock_is_parsed_from_the_response(self):
        assert unlock_requested(
            "UNLOCK: the sampling helper both named tests share moves\n# Spec"
        ) == "the sampling helper both named tests share moves"
        assert unlock_requested("# Spec\n\nno unlock here") == ""

    def test_an_unlock_lets_the_restructure_land_and_is_carried(self):
        result = enforce_pinning(
            PREVIOUS, REGENERATED,
            current_tokens=named_tokens(VERDICT),
            unlock_reason="restructuring the sampling helpers",
        )
        assert '== "face"' in result.text, "the unlock lifts the refusal"
        assert result.refusals == ()
        assert result.unlock_reason == "restructuring the sampling helpers"

    def test_an_unlock_does_not_silence_the_regression_flag(self):
        """An unlock explains a change; it does not un-happen it."""
        result = enforce_pinning(
            PREVIOUS, REGENERATED,
            current_tokens=named_tokens(VERDICT),
            ever_tokens=named_tokens(VERDICT),
            unlock_reason="restructure",
        )
        assert result.regressions


class TestTheBoundary:
    def test_identical_revision_changes_nothing(self):
        result = enforce_pinning(
            PREVIOUS, PREVIOUS, current_tokens=named_tokens(VERDICT),
        )
        assert result.text == PREVIOUS
        assert result.refusals == ()
        assert result.regressions == ()

    def test_pure_insertion_passes(self):
        """Adding is not un-fixing: a new test appended in unnamed territory
        lands untouched."""
        added = PREVIOUS.replace(
            "## Section 11",
            "```python\ndef test_new_coverage():\n    assert True\n```\n\n"
            "## Section 11",
        )
        result = enforce_pinning(
            PREVIOUS, added, current_tokens=named_tokens(VERDICT),
        )
        assert "test_new_coverage" in result.text

    def test_separate_regions_are_judged_separately(self):
        """Two changes in one revision get independent verdicts: the named
        one lands, the locked one is refused. (A single region genuinely
        SPANNING named and unnamed lines passes — restructuring around the
        named item is the named item's business.)"""
        mixed = PREVIOUS.replace(
            'assert classify(sample) == "crimson"',
            'assert classify(sample) == "crimson"  # still the band',
        ).replace(
            "band = face.crop(wordmark_box())",
            "band = face.crop(wordmark_box(centre=0.67))",
        )
        result = enforce_pinning(
            PREVIOUS, mixed, current_tokens=named_tokens(VERDICT),
        )
        # The S2 comment tweak and the named fix are separate diff regions;
        # the S2 one is refused, the named one lands.
        assert "wordmark_box(centre=0.67)" in result.text
        assert "# still the band" not in result.text
        assert result.refusals

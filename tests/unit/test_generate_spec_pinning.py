"""The drafter node enforces pinning on every revision path (#2532).

Node-level wiring: the full-regeneration path is the observed regression
vector (run-issue331-233939's resumed grant un-fixed S2 by regenerating), so
these tests drive `generate_spec` itself with a mocked provider and assert
the returned draft — not just the pure module — carries the fix forward.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
    generate_spec,
)

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
"""

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
"""

VERDICT = (
    "REVISE: `test_req_7_wordmark` measures cap height against the wrong "
    "box; compute wordmark_box() from the 0.67 R band centre."
)


def _run(response: str, *, feedback: str = VERDICT, state_extra: dict | None = None):
    drafter = Mock()
    drafter.invoke.return_value = Mock(
        success=True, response=response, error_message=None,
        input_tokens=0, output_tokens=0,
    )
    state = {
        "config_mock_mode": True,  # mock: skips preflight and the edit path
        "lld_content": "# LLD\n\ncontent\n",
        "current_state_snapshots": {},
        "pattern_references": [],
        "assemblyzero_root": "",
        "repo_root": "",
        "issue_number": 331,
        "spec_draft": PREVIOUS,
        "review_feedback": feedback,
        "review_iteration": 0,
        **(state_extra or {}),
    }
    with patch(
        "assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_provider",
        return_value=drafter,
    ), patch(
        "assemblyzero.workflows.implementation_spec.nodes.generate_spec.load_template",
        return_value="# Template",
    ):
        return generate_spec(state)


class TestTheFullRevisionPathIsPinned:
    def test_the_s2_unfix_is_restored_and_the_named_fix_lands(self):
        out = _run(REGENERATED)
        assert out["error_message"] == ""
        assert 'assert classify(sample) == "crimson"' in out["spec_draft"], (
            "the regeneration vector must not un-fix S2"
        )
        assert "wordmark_box(centre=0.67)" in out["spec_draft"]
        assert any("refused" in e for e in out["pinning_events"])

    def test_the_regression_class_is_flagged_at_the_moment_it_happens(self):
        out = _run(REGENERATED, state_extra={
            "review_feedback_history": [VERDICT],
        })
        assert any("REGRESSION CLASS" in e for e in out["pinning_events"])

    def test_an_unlock_line_lifts_the_pin_and_is_logged(self):
        out = _run("UNLOCK: retiring the shared sampler helper\n" + REGENERATED)
        assert '== "face"' in out["spec_draft"], "the unlock lets it land"
        assert any(
            "UNLOCK granted" in e and "retiring the shared sampler" in e
            for e in out["pinning_events"]
        )

    def test_an_unextractable_verdict_abstains(self):
        """Locking the whole document on a naming the extractor cannot read
        would refuse every legitimate fix — unknown is not guilty (#2526)."""
        out = _run(REGENERATED, feedback="Please make it better overall.")
        assert '== "face"' in out["spec_draft"], "abstention passes it through"
        assert any("names nothing extractable" in e for e in out["pinning_events"])

    def test_events_accumulate_across_revisions(self):
        out = _run(REGENERATED, state_extra={
            "pinning_events": ["[PINNING] earlier event"],
        })
        assert out["pinning_events"][0] == "[PINNING] earlier event"
        assert len(out["pinning_events"]) > 1


class TestTheEditScriptPathIsPinned:
    """#1528's edit path gets the same law: a well-formed edit block aimed
    at locked content is refused, while the named fix lands."""

    EDITS = (
        "<<<<<<< SEARCH\n"
        '    assert classify(sample) == "crimson"\n'
        "=======\n"
        '    assert classify(sample) == "face"\n'
        ">>>>>>> REPLACE\n\n"
        "<<<<<<< SEARCH\n"
        "    band = face.crop(wordmark_box())\n"
        "=======\n"
        "    band = face.crop(wordmark_box(centre=0.67))\n"
        ">>>>>>> REPLACE\n"
    )

    def test_a_locked_edit_block_is_refused_and_the_named_one_lands(self):
        drafter = Mock()
        drafter.invoke.return_value = Mock(
            success=True, response=self.EDITS, error_message=None,
            input_tokens=0, output_tokens=0,
        )
        state = {
            "config_mock_mode": False,
            "config_drafter": "claude:whatever",
            "lld_content": "# LLD\n",
            "current_state_snapshots": {},
            "pattern_references": [],
            "assemblyzero_root": "",
            "repo_root": "",
            "issue_number": 331,
            "spec_draft": PREVIOUS,
            "review_feedback": VERDICT,
            "review_iteration": 0,
        }
        preflight = Mock(passed=True, available_credentials=1,
                         total_credentials=1, warnings=[])
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_provider",
            return_value=drafter,
        ), patch(
            "assemblyzero.workflows.implementation_spec.nodes.generate_spec.load_template",
            return_value="# Template",
        ), patch(
            "assemblyzero.core.preflight.check_gemini_available",
            return_value=preflight,
        ):
            out = generate_spec(state)
        assert out["error_message"] == ""
        assert 'assert classify(sample) == "crimson"' in out["spec_draft"]
        assert "wordmark_box(centre=0.67)" in out["spec_draft"]
        assert any("refused" in e for e in out["pinning_events"])
        # One model call: the edit path succeeded post-pinning, so the
        # classic full-revision call never ran.
        assert drafter.invoke.call_count == 1


class TestIterationOneIsUntouched:
    def test_an_initial_draft_writes_no_pinning_events(self):
        drafter = Mock()
        drafter.invoke.return_value = Mock(
            success=True, response="# Spec\n\nfresh draft\n",
            error_message=None, input_tokens=0, output_tokens=0,
        )
        state = {
            "config_mock_mode": True,
            "lld_content": "# LLD\n",
            "current_state_snapshots": {},
            "pattern_references": [],
            "assemblyzero_root": "",
            "repo_root": "",
        }
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_provider",
            return_value=drafter,
        ), patch(
            "assemblyzero.workflows.implementation_spec.nodes.generate_spec.load_template",
            return_value="# Template",
        ):
            out = generate_spec(state)
        assert out["pinning_events"] == []
        assert out["spec_draft"].startswith("# Spec")

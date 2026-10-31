"""revision_pinning under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md. When the pinning merge
malfunctions (it lost tests both inputs hold, or minted duplicates neither
holds) it can no longer hold the revision to what the verdict named. It used
to emit the revision unenforced, which is the pinning gate passing a round it
could not judge; it now raises ``PinningMergeError``, and N2 halts.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from assemblyzero.workflows.implementation_spec import revision_pinning as rp
from assemblyzero.workflows.implementation_spec.graph import route_after_generate_spec

gs = importlib.import_module("assemblyzero.workflows.implementation_spec.nodes.generate_spec")

PREVIOUS = """# Spec

## 6. Change Instructions

```python
def test_one():
    assert render_face(1) == 1

def test_two():
    assert screws() == 4
```

## 10. Mapping

Each criterion maps to one test above.
"""

TOKENS = rp.named_tokens("REVISE: `render_face` must take a size.")


def _flags():
    return rp.named_line_flags(PREVIOUS, TOKENS)


def test_571_a_merge_that_mints_duplicates_raises():
    walked = PREVIOUS.replace(
        "## 10. Mapping",
        "```python\ndef test_two():\n    assert screws() == 4\n```\n\n## 10. Mapping",
    )
    with pytest.raises(rp.PinningMergeError) as caught:
        rp._conservation_override(
            PREVIOUS, PREVIOUS, walked, current_tokens=TOKENS, current_flags=_flags(),
        )
    assert "multiplied" in str(caught.value) and "test_two" in str(caught.value)


def test_583_a_merge_that_loses_tests_both_inputs_hold_raises():
    walked = PREVIOUS.replace("\ndef test_two():\n    assert screws() == 4\n", "\n")
    with pytest.raises(rp.PinningMergeError) as caught:
        rp._conservation_override(
            PREVIOUS, PREVIOUS, walked, current_tokens=TOKENS, current_flags=_flags(),
        )
    assert "test_two" in str(caught.value)


def test_a_revision_that_removes_unnamed_tests_is_still_refused_entire():
    """Kept: tier two is enforcement, not a malfunction; the previous draft
    is emitted with the event. The deletion shares one diff region with the
    named fix, so the walk passes it wholesale and the gate catches it."""
    removed = PREVIOUS.replace(
        "    assert render_face(1) == 1\n\ndef test_two():\n    assert screws() == 4\n",
        "    assert render_face(size=2) == 1\n",
    )
    result = rp.enforce_pinning(PREVIOUS, removed, current_tokens=TOKENS)
    assert result.text == PREVIOUS
    assert "refused entire" in result.conservation_event


def test_a_clean_walk_has_no_override():
    assert rp._conservation_override(
        PREVIOUS, PREVIOUS, PREVIOUS, current_tokens=TOKENS, current_flags=_flags(),
    ) is None


def test_the_drafter_node_halts_on_a_merge_malfunction(tmp_path):
    drafter = Mock()
    drafter.invoke.return_value = Mock(
        success=True, response=PREVIOUS.replace("== 1", "== 2"), error_message=None,
        input_tokens=0, output_tokens=0,
    )
    lineage = tmp_path / "lineage"
    lineage.mkdir()
    state = {
        "config_mock_mode": True, "lld_content": "# LLD\n", "assemblyzero_root": "",
        "repo_root": "", "issue_number": 42, "audit_dir": str(lineage),
        "spec_draft": PREVIOUS, "review_feedback": "REVISE: `render_face` must take a size.",
        "review_iteration": 0, "current_state_snapshots": {}, "pattern_references": [],
    }
    with patch.object(gs, "get_provider", return_value=drafter), patch.object(
        gs, "load_template", return_value="# Template",
    ), patch.object(
        rp, "enforce_pinning", side_effect=rp.PinningMergeError("the walked merge lost 1 test(s)"),
    ):
        result = gs.generate_spec(state)

    assert "the walked merge lost 1 test(s)" in result["error_message"]
    assert "#42" in result["error_message"]
    assert route_after_generate_spec(result) == "HALT"
    assert "spec_draft" not in result
    assert not list(Path(lineage).glob("*-spec-draft.md"))

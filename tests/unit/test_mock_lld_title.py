"""The mock LLD drafter titles its LLD with the run's own issue (#3585).

N1.5 blocks an LLD whose title does not carry the run's issue number. The
mock's canned LLD names issue 42; `MockProvider.invoke` replaces it with the
number the drafter's prompt states, so a `--mock` rehearsal of any issue
clears N1.5, not only issue 42's.
"""

from __future__ import annotations

from assemblyzero.core.llm_provider import MockProvider
from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
    validate_title_issue_number,
)


def _draft(content: str) -> str:
    result = MockProvider(model="lld").invoke("system", content)
    assert result.success
    return result.response


def test_a_first_draft_is_titled_with_the_runs_issue():
    content = (
        "# Issue #7: a feature\n\nbody\n\n"
        "**CRITICAL: This LLD is for GitHub Issue #7. Use this exact issue "
        "number in all references.**"
    )
    draft = _draft(content)
    assert draft.startswith("# 7 - Feature:")
    assert validate_title_issue_number(draft, 7) == []


def test_a_skeleton_prompt_from_the_third_draft_on_is_titled_too():
    content = "[See GitHub Issue #1234 — unchanged from iteration 1. Issue #1234: a feature]"
    draft = _draft(content)
    assert draft.startswith("# 1234 - Feature:")
    assert validate_title_issue_number(draft, 1234) == []


def test_a_prompt_without_the_marker_keeps_the_canned_title_and_n15_blocks_it():
    draft = _draft("no drafter marker here")
    assert draft == MockProvider.DEFAULT_RESPONSES["lld"][0]
    assert validate_title_issue_number(draft, 7) != []


def test_the_canned_lld_is_never_changed_in_place():
    canned = MockProvider.DEFAULT_RESPONSES["lld"][0]
    _draft("**CRITICAL: This LLD is for GitHub Issue #7.**")
    assert MockProvider.DEFAULT_RESPONSES["lld"][0] == canned
    assert canned.startswith("# 42 - Feature:")

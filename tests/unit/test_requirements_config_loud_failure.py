"""The requirements WorkflowConfig under standard 0034 (#3585).

Named for its ledger line in docs/audits/0908-loud-failure-sweep-ledger.md
(base ``79e18ad1``), for ``assemblyzero/workflows/requirements/config.py``. A
config validates itself when built and raises on any error; its validator used
to exist with no caller, so a bad spec or cap was never reported.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.requirements.config import WORKFLOW_PRESETS, WorkflowConfig


@pytest.mark.parametrize(
    ("kwargs", "needle"),
    [
        ({"drafter": "claude-opus"}, "drafter"),
        ({"reviewer": "gemini"}, "reviewer"),
        ({"max_iterations": 0}, "max_iterations"),
    ],
)
def test_122_an_invalid_config_raises_when_built(kwargs, needle):
    with pytest.raises(ValueError, match=needle):
        WorkflowConfig(workflow_type="lld", **kwargs)


def test_a_valid_config_builds_and_validates_clean():
    config = WorkflowConfig(workflow_type="lld", drafter="claude:opus",
                            reviewer="gemini:3.8-flash")
    assert config.validate() == []


def test_every_preset_is_valid():
    """Kept: the presets are built at import, so a bad one would now fail the
    import rather than wait for a caller."""
    assert all(preset.is_valid() for preset in WORKFLOW_PRESETS.values())

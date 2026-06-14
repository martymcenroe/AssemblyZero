"""Regression guards: path constants must be absolute, not repo-relative (#1151).

Pre-#1151, several modules defined path constants as relative strings:

    HISTORY_PATH = "data/hourglass/history.json"
    WORKFLOW_AUDIT_FILE = Path("docs/lineage/workflow-audit.jsonl")
    LLD_STATUS_FILE = Path("docs/lld/lld-status.json")

When code wrote to those paths from a worktree (test, hook, workflow run
with `cwd=worktree`), the worktree's tracked copy of the file got dirtied,
which broke `git worktree remove` (no --force per policy) and produced
the orphan-worktree class of bugs that #1133 made loud.

#1134 fixed the cascade-events instance. This test file guards the
other three by asserting each constant resolves to an absolute path.
A future contributor who reverts to a relative form gets a red test.

If you NEED to add a new tracked-log writer, design it around an absolute
default (see `tools/audit_tracked_log_writers.py` for the audit) and
add a guard here.
"""
from __future__ import annotations

from pathlib import Path


def test_hourglass_history_path_is_absolute():
    from assemblyzero.workflows.death.constants import HISTORY_PATH
    assert Path(HISTORY_PATH).is_absolute(), (
        f"HISTORY_PATH={HISTORY_PATH} must be absolute "
        "(#1151: hourglass state lives outside any repo tree)"
    )


def test_hourglass_age_meter_state_path_is_absolute():
    from assemblyzero.workflows.death.constants import AGE_METER_STATE_PATH
    assert Path(AGE_METER_STATE_PATH).is_absolute(), (
        f"AGE_METER_STATE_PATH={AGE_METER_STATE_PATH} must be absolute "
        "(#1151: hourglass state lives outside any repo tree)"
    )


def test_workflow_audit_file_is_absolute():
    from assemblyzero.workflows.testing.audit import WORKFLOW_AUDIT_FILE
    assert WORKFLOW_AUDIT_FILE.is_absolute(), (
        f"WORKFLOW_AUDIT_FILE={WORKFLOW_AUDIT_FILE} must be absolute "
        "(#1151: workflow audit log lives outside any repo tree)"
    )


def test_lld_status_file_is_absolute():
    from assemblyzero.workflows.requirements.audit import LLD_STATUS_FILE
    assert LLD_STATUS_FILE.is_absolute(), (
        f"LLD_STATUS_FILE={LLD_STATUS_FILE} must be absolute "
        "(#1151: LLD approval cache lives outside any repo tree)"
    )


def test_all_relocated_paths_live_under_claude_home():
    """Defense in depth: the absolute paths should live under ~/.claude/,
    not in arbitrary other absolute locations. Keeps operational state
    consolidated and discoverable.
    """
    from assemblyzero.workflows.death.constants import (
        AGE_METER_STATE_PATH,
        HISTORY_PATH,
    )
    from assemblyzero.workflows.requirements.audit import LLD_STATUS_FILE
    from assemblyzero.workflows.testing.audit import WORKFLOW_AUDIT_FILE

    claude_home = Path.home() / ".claude"
    for label, p in [
        ("HISTORY_PATH", Path(HISTORY_PATH)),
        ("AGE_METER_STATE_PATH", Path(AGE_METER_STATE_PATH)),
        ("WORKFLOW_AUDIT_FILE", WORKFLOW_AUDIT_FILE),
        ("LLD_STATUS_FILE", LLD_STATUS_FILE),
    ]:
        try:
            p.relative_to(claude_home)
        except ValueError:
            raise AssertionError(
                f"{label}={p} must live under {claude_home}, not elsewhere "
                "(#1151: operational state consolidates under ~/.claude/)"
            )

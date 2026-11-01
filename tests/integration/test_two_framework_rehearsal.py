"""Both workflows under --mock on a pytest-plus-Vitest target (#4438 T2).

The rehearsal's `mock` step, through real child processes, with a throwaway
home so a run cannot touch the machine's state directories.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import child_env_with_alert_channel
from tools import rehearse_two_frameworks as rehearsal

pytestmark = pytest.mark.integration


def test_both_workflows_pass_and_leave_nothing_behind(tmp_path, monkeypatch):
    for key, value in child_env_with_alert_channel().items():
        monkeypatch.setenv(key, value)
    home = tmp_path / "home"
    (home / ".assemblyzero" / "telemetry-buffer").mkdir(parents=True)
    (home / ".claude" / "assemblyzero").mkdir(parents=True)
    # The two places every run appends to, there on any machine that has run.
    (home / ".claude" / "assemblyzero" / "workflow-audit.jsonl").touch()
    monkeypatch.setenv("HOME", str(home))
    work = tmp_path / "work"
    work.mkdir()

    code = rehearsal.step_mock(work, home=home)

    logs = "\n".join(
        Path(work / name).read_text(encoding="utf-8", errors="replace")[-2000:]
        for name in ("lld.log", "impl.log")
    )
    assert code == 0, logs
    assert (work / "snapshot-before.txt").read_bytes() == (work / "snapshot-after.txt").read_bytes()

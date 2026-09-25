"""Which user hooks fire inside one nested `claude -p` -- live (#3504, ADR 0232).

Launches ONE real nested call through `ClaudeCLIProvider.invoke`, the way
every workflow node does, from an empty directory inside a throwaway git
repository, and reads the SessionStart hook's own record: session-baseline.sh
writes `{repo}/data/.session-baseline/{session_id}.txt` for the repository
holding the cwd. With `NESTED_SETTINGS_ARGS` in the command no such file may
appear.

Opt-in: it needs a logged-in `claude` on PATH and spends one haiku call, so
it runs only when AZ_LIVE_NESTED_PROBE=1, e.g.

    AZ_LIVE_NESTED_PROBE=1 poetry run pytest tests/integration/test_nested_hooks_live.py -m integration

The recorded run that ADR 0232 cites (2026-09-24) is the same shape, with
and without the flag.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("AZ_LIVE_NESTED_PROBE") != "1",
        reason="live nested claude call; set AZ_LIVE_NESTED_PROBE=1 to run",
    ),
]


def test_a_nested_call_fires_no_session_start_hook(tmp_path, monkeypatch):
    from assemblyzero.core.llm_provider import ClaudeCLIProvider

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    probe = repo / "empty"
    probe.mkdir()
    monkeypatch.chdir(probe)

    result = ClaudeCLIProvider(model="haiku").invoke(
        system_prompt="Reply with the single word OK.", content="OK?",
        timeout_seconds=120,
    )

    assert result.success, result.error_message
    sid = ""
    for line in (result.raw_response or "").splitlines():
        try:
            sid = json.loads(line).get("session_id") or sid
        except ValueError:
            continue
    assert sid, "the stream carried no session id"
    baselines = repo / "data" / ".session-baseline"
    assert not (baselines / f"{sid}.txt").exists(), (
        "SessionStart fired inside a nested call: session-baseline.sh wrote "
        f"{baselines / (sid + '.txt')}"
    )

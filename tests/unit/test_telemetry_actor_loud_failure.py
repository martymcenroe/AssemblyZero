"""GitHub-user detection says when it fails (ADR 0236, #3585).

``detect_github_user`` labels every telemetry event. It never read ``gh``'s
exit code, and it swallowed every exception, so a failed detection was the
silent label "unknown". It now checks the exit code, and a failed detection
writes an ERROR line to stderr naming the cause (never ``gh``'s output) before
it records "unknown", the answer its docstring declares. It also no longer
asks ``gh`` for the token: the username line does not need it.

It does not raise or alert (won't do, recorded in ``data/agent-notes.md``):
every ``emit`` calls it, and the unit tier runs in CI with no ``gh`` login, so a
raise would fail every test that emits there and an alert would land in
whichever test emits first.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from assemblyzero.telemetry import actor
from assemblyzero.telemetry.actor import detect_github_user


@pytest.fixture(autouse=True)
def _no_cache():
    if hasattr(detect_github_user, "_cached"):
        delattr(detect_github_user, "_cached")
    yield
    if hasattr(detect_github_user, "_cached"):
        delattr(detect_github_user, "_cached")


def _gh(returncode: int, stdout: str = "", stderr: str = ""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_34_a_failing_gh_is_an_error_line_not_a_silent_unknown(capsys, operator_alerts):
    with patch.object(actor.subprocess, "run", return_value=_gh(1, stderr="not logged in")):
        assert detect_github_user() == "unknown"

    err = capsys.readouterr().err
    assert "ERROR" in err
    assert "exited 1" in err
    assert "not logged in" not in err, "gh's output is never echoed"


def test_34_the_token_is_never_requested():
    with patch.object(actor.subprocess, "run", return_value=_gh(0)) as run:
        detect_github_user()

    assert "--show-token" not in run.call_args.args[0]


@pytest.mark.parametrize(
    "exc", [FileNotFoundError("gh"), subprocess.TimeoutExpired(["gh"], 5)],
    ids=["gh-missing", "gh-timeout"],
)
def test_48_gh_missing_or_timing_out_is_an_error_line(exc, capsys, operator_alerts):
    with patch.object(actor.subprocess, "run", side_effect=exc):
        assert detect_github_user() == "unknown"

    err = capsys.readouterr().err
    assert "ERROR" in err
    assert type(exc).__name__ in err


def test_a_logged_in_gh_names_the_user_quietly(capsys):
    line = "  ✓ Logged in to github.com account octocat (keyring)"
    with patch.object(actor.subprocess, "run", return_value=_gh(0, stderr=line)):
        assert detect_github_user() == "octocat"

    assert capsys.readouterr().err == ""

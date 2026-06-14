"""Tests for tools/enable_dependabot.py (#1331)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from enable_dependabot import (  # noqa: E402
    EnableResult,
    enable_dependabot_for_repo,
    list_fleet_repos,
)


# ────────────────────────────────────────────────────────────────────
# enable_dependabot_for_repo — dry-run path
# ────────────────────────────────────────────────────────────────────


def _mock_get_response(status_code: int = 200, sa: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = {"security_and_analysis": sa or {}}
    r.text = ""
    return r


def _mock_put_or_patch_response(status_code: int = 204) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.text = ""
    return r


@patch("enable_dependabot.requests")
def test_dry_run_makes_no_mutations(mock_requests: MagicMock) -> None:
    """apply=False: GET happens for state read; NO PATCH / PUT calls."""
    mock_requests.get.return_value = _mock_get_response(
        sa={"dependabot_security_updates": {"status": "disabled"}}
    )
    result = enable_dependabot_for_repo("owner", "repo", pat="fake", apply=False)
    assert result.ok is True
    assert mock_requests.get.called
    assert not mock_requests.patch.called
    assert not mock_requests.put.called
    for v in result.actions.values():
        assert v.startswith("DRY-RUN")


@patch("enable_dependabot.requests")
def test_apply_makes_three_api_calls(mock_requests: MagicMock) -> None:
    """apply=True: GET (state) + PATCH (security_and_analysis) + 2 PUTs."""
    mock_requests.get.return_value = _mock_get_response(sa={})
    mock_requests.patch.return_value = _mock_put_or_patch_response(200)
    mock_requests.put.return_value = _mock_put_or_patch_response(204)
    result = enable_dependabot_for_repo("owner", "repo", pat="fake", apply=True)
    assert result.ok is True
    assert mock_requests.get.call_count == 1
    assert mock_requests.patch.call_count == 1
    assert mock_requests.put.call_count == 2
    assert all("DRY-RUN" not in v for v in result.actions.values())


@patch("enable_dependabot.requests")
def test_apply_records_http_status_per_action(mock_requests: MagicMock) -> None:
    mock_requests.get.return_value = _mock_get_response(sa={})
    mock_requests.patch.return_value = _mock_put_or_patch_response(200)
    mock_requests.put.return_value = _mock_put_or_patch_response(204)
    result = enable_dependabot_for_repo("owner", "repo", pat="fake", apply=True)
    assert "HTTP 200" in result.actions["PATCH security_and_analysis.dependabot_security_updates"]
    assert "HTTP 204" in result.actions["PUT vulnerability-alerts"]
    assert "HTTP 204" in result.actions["PUT automated-security-fixes"]


@patch("enable_dependabot.requests")
def test_apply_marks_non_2xx_as_error(mock_requests: MagicMock) -> None:
    """Non-success HTTP code on PATCH/PUT flips ok=False but doesn't crash."""
    mock_requests.get.return_value = _mock_get_response(sa={})
    mock_requests.patch.return_value = _mock_put_or_patch_response(403)
    mock_requests.put.return_value = _mock_put_or_patch_response(204)
    result = enable_dependabot_for_repo("owner", "repo", pat="fake", apply=True)
    assert result.ok is False
    assert "HTTP 403" in result.actions["PATCH security_and_analysis.dependabot_security_updates"]


@patch("enable_dependabot.requests")
def test_get_failure_returns_early(mock_requests: MagicMock) -> None:
    """If GET /repos fails, return immediately with error — no further calls."""
    mock_requests.get.return_value = _mock_get_response(status_code=404)
    result = enable_dependabot_for_repo("owner", "nope", pat="fake", apply=True)
    assert result.ok is False
    assert "GET /repos" in result.actions
    assert "HTTP 404" in result.actions["GET /repos"]
    # No further mutations attempted
    assert not mock_requests.patch.called
    assert not mock_requests.put.called


@patch("enable_dependabot.requests")
def test_get_state_surfaced_in_result(mock_requests: MagicMock) -> None:
    """The before-state from GET is preserved in EnableResult.before."""
    sa = {
        "dependabot_security_updates": {"status": "disabled"},
        "secret_scanning": {"status": "enabled"},
    }
    mock_requests.get.return_value = _mock_get_response(sa=sa)
    result = enable_dependabot_for_repo("owner", "repo", pat="fake", apply=False)
    assert result.before == sa


# ────────────────────────────────────────────────────────────────────
# Fleet enumeration
# ────────────────────────────────────────────────────────────────────


@patch("enable_dependabot.subprocess")
def test_list_fleet_excludes_forks_and_archives(mock_subprocess: MagicMock) -> None:
    fake_stdout = """[
        {"name": "live", "nameWithOwner": "u/live", "isArchived": false, "isFork": false},
        {"name": "old", "nameWithOwner": "u/old", "isArchived": true, "isFork": false},
        {"name": "fork", "nameWithOwner": "u/fork", "isArchived": false, "isFork": true},
        {"name": "live2", "nameWithOwner": "u/live2", "isArchived": false, "isFork": false}
    ]"""
    mock_subprocess.run.return_value = MagicMock(returncode=0, stdout=fake_stdout, stderr="")
    repos = list_fleet_repos("u")
    assert repos == ["u/live", "u/live2"]


@patch("enable_dependabot.subprocess")
def test_list_fleet_exits_on_gh_failure(mock_subprocess: MagicMock) -> None:
    mock_subprocess.run.return_value = MagicMock(returncode=1, stdout="", stderr="auth error")
    with pytest.raises(SystemExit):
        list_fleet_repos("u")

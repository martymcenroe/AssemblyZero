"""Unit tests for tools/sentinel_migrate.py.

Issue #960. Mocks `requests` and `_pat_session.classic_pat_session` so the
tests do not touch the real GitHub API or require a real gpg PAT.
"""

from __future__ import annotations

import csv
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import sentinel_migrate  # noqa: E402

# A realistic GET response shape from /repos/{owner}/{repo}/branches/main/protection
# for an outlier repo (currently on the legacy `issue-reference` context).
OUTLIER_PROTECTION = {
    "url": "https://api.github.com/repos/martymcenroe/AssemblyZero/branches/main/protection",
    "required_status_checks": {
        "strict": False,
        "contexts": ["issue-reference"],
        "checks": [{"context": "issue-reference", "app_id": 15368}],
    },
    "enforce_admins": {"enabled": True},
    "required_pull_request_reviews": {
        "dismiss_stale_reviews": False,
        "require_code_owner_reviews": False,
        "required_approving_review_count": 1,
    },
    "restrictions": None,
    "required_linear_history": {"enabled": False},
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
}

# After successful migration, the GET response would show the new context.
MIGRATED_PROTECTION = {
    **OUTLIER_PROTECTION,
    "required_status_checks": {
        "strict": False,
        "contexts": ["pr-sentinel / issue-reference"],
        "checks": [{"context": "pr-sentinel / issue-reference", "app_id": 2975092}],
    },
}

WORKER_CHECK_RUNS_SUCCESS = {
    "check_runs": [
        {"name": "test", "conclusion": "success"},
        {"name": "pr-sentinel / issue-reference", "conclusion": "success"},
        {"name": "issue-reference", "conclusion": "failure"},
    ]
}

WORKER_CHECK_RUNS_FAILURE = {
    "check_runs": [
        {"name": "pr-sentinel / issue-reference", "conclusion": "failure"},
    ]
}


@contextmanager
def _fake_pat_session(*args, **kwargs):
    yield "fake_pat_for_tests"


def _mock_response(json_data, status_code=200):
    resp = mock.Mock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = mock.Mock()
    return resp


# --- find_outliers --------------------------------------------------------


class TestFindOutliers:
    def test_returns_only_repos_with_old_context(self, tmp_path):
        csv_path = tmp_path / "audit.csv"
        with csv_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["repo", "review_count", "strict", "contexts", "app_ids", "enforce_admins"])
            w.writerow(["RepoA", "1", "false", "issue-reference", "15368", "true"])
            w.writerow(["RepoB", "1", "false", "pr-sentinel / issue-reference", "null", "true"])
            w.writerow(["RepoC", "1", "false", "issue-reference", "15368", "true"])
            w.writerow(["RepoD", "NO_PROTECTION", "", "", "", ""])

        outliers = sentinel_migrate.find_outliers(csv_path)
        assert outliers == ["RepoA", "RepoC"]

    def test_returns_empty_when_all_migrated(self, tmp_path):
        csv_path = tmp_path / "audit.csv"
        with csv_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["repo", "review_count", "strict", "contexts", "app_ids", "enforce_admins"])
            w.writerow(["RepoA", "1", "false", "pr-sentinel / issue-reference", "null", "true"])

        assert sentinel_migrate.find_outliers(csv_path) == []


# --- current_contexts -----------------------------------------------------


class TestCurrentContexts:
    def test_prefers_checks_array_over_legacy_contexts(self):
        protection = {
            "required_status_checks": {
                "contexts": ["legacy-name"],
                "checks": [{"context": "new-name", "app_id": 999}],
            }
        }
        assert sentinel_migrate.current_contexts(protection) == ["new-name"]

    def test_falls_back_to_legacy_contexts_when_no_checks(self):
        protection = {"required_status_checks": {"contexts": ["only-legacy"]}}
        assert sentinel_migrate.current_contexts(protection) == ["only-legacy"]

    def test_empty_when_no_status_checks(self):
        assert sentinel_migrate.current_contexts({}) == []
        assert sentinel_migrate.current_contexts({"required_status_checks": None}) == []


# --- build_put_payload ----------------------------------------------------


class TestBuildPutPayload:
    def test_replaces_legacy_check_with_worker_check(self):
        payload = sentinel_migrate.build_put_payload(OUTLIER_PROTECTION)
        assert payload["required_status_checks"]["checks"] == [
            {"context": "pr-sentinel / issue-reference", "app_id": 2975092}
        ]

    def test_preserves_enforce_admins_true(self):
        payload = sentinel_migrate.build_put_payload(OUTLIER_PROTECTION)
        assert payload["enforce_admins"] is True

    def test_preserves_review_count(self):
        payload = sentinel_migrate.build_put_payload(OUTLIER_PROTECTION)
        assert payload["required_pull_request_reviews"]["required_approving_review_count"] == 1

    def test_passes_through_optional_settings(self):
        payload = sentinel_migrate.build_put_payload(OUTLIER_PROTECTION)
        assert payload["required_linear_history"] is False
        assert payload["allow_force_pushes"] is False
        assert payload["allow_deletions"] is False

    def test_handles_missing_review_block(self):
        protection = {**OUTLIER_PROTECTION, "required_pull_request_reviews": None}
        payload = sentinel_migrate.build_put_payload(protection)
        assert payload["required_pull_request_reviews"] is None


# --- get_worker_check_status ---------------------------------------------


class TestGetWorkerCheckStatus:
    """The worker only posts on PR events, so verification uses the most
    recent PR's head commit, not main's HEAD."""

    def test_returns_conclusion_from_most_recent_pr(self, monkeypatch):
        responses = iter([
            _mock_response([{"number": 953, "head": {"sha": "abc123"}}]),
            _mock_response(WORKER_CHECK_RUNS_SUCCESS),
        ])
        monkeypatch.setattr(
            sentinel_migrate.requests, "get",
            mock.Mock(side_effect=lambda *a, **kw: next(responses)),
        )
        assert sentinel_migrate.get_worker_check_status("X", "fake_pat") == "success"

    def test_returns_failure_when_worker_failed(self, monkeypatch):
        responses = iter([
            _mock_response([{"number": 1, "head": {"sha": "deadbeef"}}]),
            _mock_response(WORKER_CHECK_RUNS_FAILURE),
        ])
        monkeypatch.setattr(
            sentinel_migrate.requests, "get",
            mock.Mock(side_effect=lambda *a, **kw: next(responses)),
        )
        assert sentinel_migrate.get_worker_check_status("X", "fake_pat") == "failure"

    def test_returns_none_when_no_prs_exist(self, monkeypatch):
        monkeypatch.setattr(
            sentinel_migrate.requests, "get",
            mock.Mock(return_value=_mock_response([])),
        )
        assert sentinel_migrate.get_worker_check_status("X", "fake_pat") is None

    def test_returns_none_when_check_missing_on_pr(self, monkeypatch):
        responses = iter([
            _mock_response([{"number": 1, "head": {"sha": "abc"}}]),
            _mock_response({"check_runs": [{"name": "test", "conclusion": "success"}]}),
        ])
        monkeypatch.setattr(
            sentinel_migrate.requests, "get",
            mock.Mock(side_effect=lambda *a, **kw: next(responses)),
        )
        assert sentinel_migrate.get_worker_check_status("X", "fake_pat") is None


# --- migrate_repo ---------------------------------------------------------


class TestMigrateRepo:
    def test_skips_repo_already_on_fleet_standard(self, monkeypatch):
        monkeypatch.setattr(
            sentinel_migrate, "get_branch_protection",
            mock.Mock(return_value=MIGRATED_PROTECTION),
        )
        result = sentinel_migrate.migrate_repo("X", "fake_pat", dry_run=False)
        assert "already on fleet-standard" in result

    def test_refuses_when_state_unrecognized(self, monkeypatch):
        weird = {**OUTLIER_PROTECTION, "required_status_checks": {"checks": [{"context": "something-else", "app_id": 1}]}}
        monkeypatch.setattr(
            sentinel_migrate, "get_branch_protection",
            mock.Mock(return_value=weird),
        )
        result = sentinel_migrate.migrate_repo("X", "fake_pat", dry_run=False)
        assert "REFUSING" in result
        assert "do not match expected outlier shape" in result

    def test_refuses_when_worker_check_failing(self, monkeypatch):
        monkeypatch.setattr(
            sentinel_migrate, "get_branch_protection",
            mock.Mock(return_value=OUTLIER_PROTECTION),
        )
        monkeypatch.setattr(
            sentinel_migrate, "get_worker_check_status",
            mock.Mock(return_value="failure"),
        )
        result = sentinel_migrate.migrate_repo("X", "fake_pat", dry_run=False)
        assert "REFUSING" in result
        assert "worker check" in result.lower()
        assert "'failure'" in result

    def test_refuses_when_worker_check_missing(self, monkeypatch):
        monkeypatch.setattr(
            sentinel_migrate, "get_branch_protection",
            mock.Mock(return_value=OUTLIER_PROTECTION),
        )
        monkeypatch.setattr(
            sentinel_migrate, "get_worker_check_status",
            mock.Mock(return_value=None),
        )
        result = sentinel_migrate.migrate_repo("X", "fake_pat", dry_run=False)
        assert "REFUSING" in result
        assert "None" in result

    def test_dry_run_does_not_call_put(self, monkeypatch):
        put_mock = mock.Mock()
        monkeypatch.setattr(
            sentinel_migrate, "get_branch_protection",
            mock.Mock(return_value=OUTLIER_PROTECTION),
        )
        monkeypatch.setattr(
            sentinel_migrate, "get_worker_check_status",
            mock.Mock(return_value="success"),
        )
        monkeypatch.setattr(sentinel_migrate, "put_branch_protection", put_mock)

        result = sentinel_migrate.migrate_repo("X", "fake_pat", dry_run=True)
        assert "DRY-RUN" in result
        put_mock.assert_not_called()

    def test_live_run_calls_put_then_verifies(self, monkeypatch):
        put_mock = mock.Mock(return_value=MIGRATED_PROTECTION)
        get_mock = mock.Mock(side_effect=[OUTLIER_PROTECTION, MIGRATED_PROTECTION])
        monkeypatch.setattr(sentinel_migrate, "get_branch_protection", get_mock)
        monkeypatch.setattr(
            sentinel_migrate, "get_worker_check_status",
            mock.Mock(return_value="success"),
        )
        monkeypatch.setattr(sentinel_migrate, "put_branch_protection", put_mock)

        result = sentinel_migrate.migrate_repo("X", "fake_pat", dry_run=False)
        put_mock.assert_called_once()
        assert get_mock.call_count == 2  # before + verify after
        assert "issue-reference → pr-sentinel / issue-reference" in result

    def test_reports_when_put_succeeds_but_verify_unexpected(self, monkeypatch):
        not_quite_migrated = {
            **OUTLIER_PROTECTION,
            "required_status_checks": {
                "strict": False,
                "contexts": ["issue-reference"],
                "checks": [{"context": "issue-reference", "app_id": 15368}],
            },
        }
        monkeypatch.setattr(
            sentinel_migrate, "get_branch_protection",
            mock.Mock(side_effect=[OUTLIER_PROTECTION, not_quite_migrated]),
        )
        monkeypatch.setattr(
            sentinel_migrate, "get_worker_check_status",
            mock.Mock(return_value="success"),
        )
        monkeypatch.setattr(sentinel_migrate, "put_branch_protection", mock.Mock())

        result = sentinel_migrate.migrate_repo("X", "fake_pat", dry_run=False)
        assert "verification did not show expected state" in result


# --- main -----------------------------------------------------------------


class TestMain:
    def test_no_outliers_exits_cleanly(self, monkeypatch, tmp_path, capsys):
        empty_csv = tmp_path / "empty.csv"
        with empty_csv.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["repo", "review_count", "strict", "contexts", "app_ids", "enforce_admins"])
            w.writerow(["A", "1", "false", "pr-sentinel / issue-reference", "null", "true"])

        monkeypatch.setattr(sentinel_migrate, "AUDIT_CSV", empty_csv)
        monkeypatch.setattr(sentinel_migrate.sys, "argv", ["sentinel_migrate.py"])
        monkeypatch.setattr(sentinel_migrate, "classic_pat_session", _fake_pat_session)

        rc = sentinel_migrate.main()
        out = capsys.readouterr().out
        assert rc == 0
        assert "Nothing to do" in out

    def test_uses_classic_pat_session_for_decryption(self, monkeypatch, tmp_path):
        # CSV with one outlier
        csv_path = tmp_path / "audit.csv"
        with csv_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["repo", "review_count", "strict", "contexts", "app_ids", "enforce_admins"])
            w.writerow(["X", "1", "false", "issue-reference", "15368", "true"])

        monkeypatch.setattr(sentinel_migrate, "AUDIT_CSV", csv_path)
        monkeypatch.setattr(sentinel_migrate.sys, "argv", ["sentinel_migrate.py", "--dry-run"])

        session_mock = mock.MagicMock()
        session_mock.return_value.__enter__.return_value = "fake_pat"
        session_mock.return_value.__exit__.return_value = False
        monkeypatch.setattr(sentinel_migrate, "classic_pat_session", session_mock)

        monkeypatch.setattr(
            sentinel_migrate, "get_branch_protection",
            mock.Mock(return_value=OUTLIER_PROTECTION),
        )
        monkeypatch.setattr(
            sentinel_migrate, "get_worker_check_status",
            mock.Mock(return_value="success"),
        )

        rc = sentinel_migrate.main()
        assert rc == 0
        session_mock.assert_called_once()

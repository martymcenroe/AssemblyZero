"""Unit tests for tools/fleet_delete_pr_sentinel.py.

Issue #975. Mocks `requests` and `_pat_session` so tests don't touch the
real GitHub API or require a real classic PAT.
"""

from __future__ import annotations

import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import fleet_delete_pr_sentinel as fdps  # noqa: E402

FAKE_PAT = "ghp_fake_classic_pat_for_testing"


def _resp(json_data, status_code=200):
    r = mock.Mock()
    r.json.return_value = json_data
    r.status_code = status_code
    r.raise_for_status = mock.Mock()
    if status_code >= 400:
        err = requests.HTTPError(f"HTTP {status_code}")
        err.response = r
        r.raise_for_status.side_effect = err
    return r


def _resp_404():
    r = mock.Mock()
    r.status_code = 404
    r.raise_for_status = mock.Mock()
    return r


# --- discover_repos ------------------------------------------------------


class TestDiscoverRepos:
    def test_extracts_repo_names_from_search(self, monkeypatch):
        search_response = _resp({
            "items": [
                {"repository": {"full_name": "martymcenroe/RepoA"}},
                {"repository": {"full_name": "martymcenroe/RepoB"}},
                {"repository": {"full_name": "martymcenroe/RepoA"}},  # dup
                {"repository": {"full_name": "otheruser/RepoC"}},  # filtered
            ]
        })
        monkeypatch.setattr(fdps.requests, "get", mock.Mock(return_value=search_response))

        repos = fdps.discover_repos(FAKE_PAT)
        assert repos == ["RepoA", "RepoB"]

    def test_empty_results(self, monkeypatch):
        monkeypatch.setattr(fdps.requests, "get", mock.Mock(return_value=_resp({"items": []})))
        assert fdps.discover_repos(FAKE_PAT) == []


# --- get_file_info -------------------------------------------------------


class TestGetFileInfo:
    def test_returns_payload_when_present(self, monkeypatch):
        payload = {"sha": "abc123", "path": ".github/workflows/pr-sentinel.yml"}
        monkeypatch.setattr(fdps.requests, "get", mock.Mock(return_value=_resp(payload)))
        result = fdps.get_file_info("X", fdps.WORKFLOW_PATH, FAKE_PAT)
        assert result == payload

    def test_returns_none_on_404(self, monkeypatch):
        monkeypatch.setattr(fdps.requests, "get", mock.Mock(return_value=_resp_404()))
        assert fdps.get_file_info("X", fdps.WORKFLOW_PATH, FAKE_PAT) is None


# --- find_existing_deletion_pr -------------------------------------------


class TestFindExistingDeletionPR:
    def test_returns_pr_number_when_match(self, monkeypatch):
        prs = [
            {"number": 100, "title": "feat: something else"},
            {"number": 101, "title": "chore: delete legacy pr-sentinel.yml (Closes #99)"},
        ]
        monkeypatch.setattr(fdps.requests, "get", mock.Mock(return_value=_resp(prs)))
        assert fdps.find_existing_deletion_pr("X", FAKE_PAT) == 101

    def test_returns_none_when_no_match(self, monkeypatch):
        prs = [{"number": 100, "title": "feat: something else"}]
        monkeypatch.setattr(fdps.requests, "get", mock.Mock(return_value=_resp(prs)))
        assert fdps.find_existing_deletion_pr("X", FAKE_PAT) is None


# --- wait_for_mergeable --------------------------------------------------


class TestWaitForMergeable:
    def test_returns_clean_immediately(self, monkeypatch):
        monkeypatch.setattr(fdps.requests, "get", mock.Mock(return_value=_resp({"mergeable_state": "clean"})))
        assert fdps.wait_for_mergeable("X", 1, FAKE_PAT, sleep_fn=lambda s: None) == "clean"

    def test_returns_unstable_as_acceptable(self, monkeypatch):
        monkeypatch.setattr(fdps.requests, "get", mock.Mock(return_value=_resp({"mergeable_state": "unstable"})))
        assert fdps.wait_for_mergeable("X", 1, FAKE_PAT, sleep_fn=lambda s: None) == "unstable"

    def test_returns_blocked_immediately(self, monkeypatch):
        monkeypatch.setattr(fdps.requests, "get", mock.Mock(return_value=_resp({"mergeable_state": "blocked"})))
        assert fdps.wait_for_mergeable("X", 1, FAKE_PAT, sleep_fn=lambda s: None) == "blocked"

    def test_polls_until_state_resolves(self, monkeypatch):
        states = iter(["unknown", "unknown", "clean"])
        monkeypatch.setattr(
            fdps.requests, "get",
            mock.Mock(side_effect=lambda *a, **kw: _resp({"mergeable_state": next(states)})),
        )
        assert fdps.wait_for_mergeable("X", 1, FAKE_PAT, sleep_fn=lambda s: None) == "clean"


# --- process_repo --------------------------------------------------------


class TestProcessRepo:
    def test_skips_when_file_missing(self, monkeypatch):
        monkeypatch.setattr(fdps, "get_file_info", mock.Mock(return_value=None))
        result = fdps.process_repo("X", FAKE_PAT, dry_run=False)
        assert "not present, skipping" in result

    def test_skips_when_existing_deletion_pr(self, monkeypatch):
        monkeypatch.setattr(fdps, "get_file_info", mock.Mock(return_value={"sha": "abc"}))
        monkeypatch.setattr(fdps, "find_existing_deletion_pr", mock.Mock(return_value=42))
        result = fdps.process_repo("X", FAKE_PAT, dry_run=False)
        assert "open deletion PR already exists (#42)" in result

    def test_dry_run_takes_no_action(self, monkeypatch):
        monkeypatch.setattr(fdps, "get_file_info", mock.Mock(return_value={"sha": "abcdef0123456789"}))
        monkeypatch.setattr(fdps, "find_existing_deletion_pr", mock.Mock(return_value=None))

        # If any of these get called, the test fails (dry-run should skip them).
        monkeypatch.setattr(fdps, "create_issue", mock.Mock(side_effect=AssertionError("must not call")))
        monkeypatch.setattr(fdps, "create_branch", mock.Mock(side_effect=AssertionError("must not call")))
        monkeypatch.setattr(fdps, "delete_file_on_branch", mock.Mock(side_effect=AssertionError("must not call")))
        monkeypatch.setattr(fdps, "create_pr", mock.Mock(side_effect=AssertionError("must not call")))

        result = fdps.process_repo("X", FAKE_PAT, dry_run=True)
        assert "WOULD delete" in result

    def test_full_flow_success(self, monkeypatch):
        monkeypatch.setattr(fdps, "get_file_info", mock.Mock(return_value={"sha": "abc"}))
        monkeypatch.setattr(fdps, "find_existing_deletion_pr", mock.Mock(return_value=None))
        monkeypatch.setattr(fdps, "create_issue", mock.Mock(return_value=999))
        monkeypatch.setattr(fdps, "get_branch_head", mock.Mock(return_value="mainsha"))
        monkeypatch.setattr(fdps, "create_branch", mock.Mock())
        monkeypatch.setattr(fdps, "delete_file_on_branch", mock.Mock())
        monkeypatch.setattr(fdps, "create_pr", mock.Mock(return_value=1234))
        monkeypatch.setattr(fdps, "wait_for_mergeable", mock.Mock(return_value="clean"))
        monkeypatch.setattr(fdps, "merge_pr", mock.Mock(return_value="merge_sha_xxxxxxxx"))

        result = fdps.process_repo("X", FAKE_PAT, dry_run=False)
        assert "PR #1234 merged at merge_sh" in result

    def test_branch_named_after_issue_number(self, monkeypatch):
        monkeypatch.setattr(fdps, "get_file_info", mock.Mock(return_value={"sha": "abc"}))
        monkeypatch.setattr(fdps, "find_existing_deletion_pr", mock.Mock(return_value=None))
        monkeypatch.setattr(fdps, "create_issue", mock.Mock(return_value=42))
        monkeypatch.setattr(fdps, "get_branch_head", mock.Mock(return_value="mainsha"))
        create_branch_mock = mock.Mock()
        monkeypatch.setattr(fdps, "create_branch", create_branch_mock)
        monkeypatch.setattr(fdps, "delete_file_on_branch", mock.Mock())
        monkeypatch.setattr(fdps, "create_pr", mock.Mock(return_value=1))
        monkeypatch.setattr(fdps, "wait_for_mergeable", mock.Mock(return_value="clean"))
        monkeypatch.setattr(fdps, "merge_pr", mock.Mock(return_value="sha"))

        fdps.process_repo("X", FAKE_PAT, dry_run=False)

        _, kwargs = create_branch_mock.call_args[0], create_branch_mock.call_args[1]
        # signature: create_branch(repo, branch, source_sha, pat)
        assert "42-fix" in create_branch_mock.call_args[0]

    def test_pr_title_includes_closes_directive(self, monkeypatch):
        monkeypatch.setattr(fdps, "get_file_info", mock.Mock(return_value={"sha": "abc"}))
        monkeypatch.setattr(fdps, "find_existing_deletion_pr", mock.Mock(return_value=None))
        monkeypatch.setattr(fdps, "create_issue", mock.Mock(return_value=99))
        monkeypatch.setattr(fdps, "get_branch_head", mock.Mock(return_value="mainsha"))
        monkeypatch.setattr(fdps, "create_branch", mock.Mock())
        monkeypatch.setattr(fdps, "delete_file_on_branch", mock.Mock())
        create_pr_mock = mock.Mock(return_value=1)
        monkeypatch.setattr(fdps, "create_pr", create_pr_mock)
        monkeypatch.setattr(fdps, "wait_for_mergeable", mock.Mock(return_value="clean"))
        monkeypatch.setattr(fdps, "merge_pr", mock.Mock(return_value="sha"))

        fdps.process_repo("X", FAKE_PAT, dry_run=False)

        title = create_pr_mock.call_args.kwargs["title"]
        assert "Closes #99" in title

    def test_does_not_merge_when_state_blocked(self, monkeypatch):
        monkeypatch.setattr(fdps, "get_file_info", mock.Mock(return_value={"sha": "abc"}))
        monkeypatch.setattr(fdps, "find_existing_deletion_pr", mock.Mock(return_value=None))
        monkeypatch.setattr(fdps, "create_issue", mock.Mock(return_value=1))
        monkeypatch.setattr(fdps, "get_branch_head", mock.Mock(return_value="sha"))
        monkeypatch.setattr(fdps, "create_branch", mock.Mock())
        monkeypatch.setattr(fdps, "delete_file_on_branch", mock.Mock())
        monkeypatch.setattr(fdps, "create_pr", mock.Mock(return_value=2))
        monkeypatch.setattr(fdps, "wait_for_mergeable", mock.Mock(return_value="blocked"))
        merge_mock = mock.Mock()
        monkeypatch.setattr(fdps, "merge_pr", merge_mock)

        result = fdps.process_repo("X", FAKE_PAT, dry_run=False)
        merge_mock.assert_not_called()
        assert "did not become mergeable" in result
        assert "blocked" in result


# --- main ----------------------------------------------------------------


class TestMain:
    def test_no_repos_exits_cleanly(self, monkeypatch, capsys):
        @contextmanager
        def fake_session(*a, **kw):
            yield FAKE_PAT
        monkeypatch.setattr(fdps, "classic_pat_session", fake_session)
        monkeypatch.setattr(fdps, "discover_repos", mock.Mock(return_value=[]))
        monkeypatch.setattr(fdps.sys, "argv", ["fleet_delete_pr_sentinel.py"])
        rc = fdps.main()
        out = capsys.readouterr().out
        assert rc == 0
        assert "No repos to process" in out

    def test_safety_cap_blocks_huge_discovery(self, monkeypatch, capsys):
        @contextmanager
        def fake_session(*a, **kw):
            yield FAKE_PAT
        monkeypatch.setattr(fdps, "classic_pat_session", fake_session)
        too_many = [f"r{i}" for i in range(fdps.MAX_REPOS_PER_RUN + 1)]
        monkeypatch.setattr(fdps, "discover_repos", mock.Mock(return_value=too_many))
        monkeypatch.setattr(fdps.sys, "argv", ["fleet_delete_pr_sentinel.py"])
        rc = fdps.main()
        out = capsys.readouterr().out
        assert rc == 1
        assert "Refusing" in out

    def test_explicit_repos_flag_overrides_discovery(self, monkeypatch, capsys):
        @contextmanager
        def fake_session(*a, **kw):
            yield FAKE_PAT
        monkeypatch.setattr(fdps, "classic_pat_session", fake_session)
        discover_mock = mock.Mock()
        monkeypatch.setattr(fdps, "discover_repos", discover_mock)
        monkeypatch.setattr(
            fdps, "process_repo",
            mock.Mock(side_effect=lambda repo, pat, dry_run: f"{repo}: skipped"),
        )
        monkeypatch.setattr(fdps.sys, "argv", ["fleet_delete_pr_sentinel.py", "--repos", "RepoA,RepoB", "--dry-run"])

        rc = fdps.main()
        out = capsys.readouterr().out
        assert rc == 0
        discover_mock.assert_not_called()
        assert "RepoA: skipped" in out
        assert "RepoB: skipped" in out

    def test_per_repo_error_continues_queue(self, monkeypatch, capsys):
        @contextmanager
        def fake_session(*a, **kw):
            yield FAKE_PAT
        monkeypatch.setattr(fdps, "classic_pat_session", fake_session)
        monkeypatch.setattr(fdps.sys, "argv", ["fleet_delete_pr_sentinel.py", "--repos", "A,B,C"])

        def _process(repo, pat, dry_run):
            if repo == "B":
                raise requests.HTTPError("boom")
            return f"{repo}: ok"
        monkeypatch.setattr(fdps, "process_repo", mock.Mock(side_effect=_process))

        rc = fdps.main()
        out = capsys.readouterr().out
        assert rc == 0
        assert "A: ok" in out
        assert "B: ERROR" in out
        assert "C: ok" in out, "Queue must continue after a per-repo error"

    def test_summary_line_counts_outcomes(self, monkeypatch, capsys):
        @contextmanager
        def fake_session(*a, **kw):
            yield FAKE_PAT
        monkeypatch.setattr(fdps, "classic_pat_session", fake_session)
        monkeypatch.setattr(fdps.sys, "argv", ["fleet_delete_pr_sentinel.py", "--repos", "A,B,C"])

        def _process(repo, pat, dry_run):
            return {
                "A": "A: PR #1 merged at abcdefgh  ✓",
                "B": "B: open deletion PR already exists (#5), skipping",
                "C": "C: ERROR — boom",
            }[repo]
        monkeypatch.setattr(fdps, "process_repo", mock.Mock(side_effect=_process))

        rc = fdps.main()
        out = capsys.readouterr().out
        assert rc == 0
        assert "merged: 1" in out
        assert "skipped: 1" in out
        assert "errored: 1" in out

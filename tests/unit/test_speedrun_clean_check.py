"""The clean-state gate detects every debris class a killed roll leaves (#1918).

Local classes (worktrees, branches, untracked artifacts) are exercised
against REAL throwaway git repos — no mocks (standard 0024). The two
network-edge finders (origin refs, open PRs) substitute _run with real
subprocess.CompletedProcess instances: an I/O boundary, and still real
result objects.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_clean_check as scc  # noqa: E402


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


def _make_repo(tmp_path, name="boostrepo"):
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("x", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    return repo


def _completed(stdout="", returncode=0):
    # mock-ok: subprocess/network boundary — but the stand-in result is a
    # REAL CompletedProcess, not a MagicMock (standard 0024 §1.3).
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=""
    )


class TestLocalDebris:
    def test_clean_repo_has_zero_local_findings(self, tmp_path):
        repo = _make_repo(tmp_path)
        assert scc.find_worktree_debris(repo, 7) == []
        assert scc.find_local_branch_debris(repo, 7) == []
        assert scc.find_artifact_debris(repo, 7) == []

    def test_issue_branches_are_found(self, tmp_path):
        repo = _make_repo(tmp_path)
        _git(repo, "branch", "issue-7")
        _git(repo, "branch", "7-lld")
        _git(repo, "branch", "unrelated")
        findings = scc.find_local_branch_debris(repo, 7)
        assert "local branch: issue-7" in findings
        assert "local branch: 7-lld" in findings
        assert len(findings) == 2

    def test_worktrees_are_found(self, tmp_path):
        repo = _make_repo(tmp_path)
        _git(repo, "branch", "issue-7")
        wt = tmp_path / "boostrepo-7"
        _git(repo, "worktree", "add", str(wt), "issue-7")
        findings = scc.find_worktree_debris(repo, 7)
        assert len(findings) == 1
        assert "boostrepo-7" in findings[0]
        # The other issue's check does not fire on it
        assert scc.find_worktree_debris(repo, 4) == []

    def test_untracked_lld_artifacts_are_found(self, tmp_path):
        repo = _make_repo(tmp_path)
        active = repo / "docs" / "lld" / "active"
        active.mkdir(parents=True)
        (active / "LLD-007.md").write_text("draft", encoding="utf-8")
        drafts = repo / "docs" / "lld" / "drafts"
        drafts.mkdir(parents=True)
        (drafts / "spec-0007-implementation-readiness.md").write_text(
            "draft", encoding="utf-8"
        )
        findings = scc.find_artifact_debris(repo, 7)
        assert len(findings) == 2
        assert any("LLD-007.md" in f for f in findings)
        # A TRACKED artifact is not debris
        _git(repo, "add", "docs")
        _git(repo, "commit", "-m", "land artifacts")
        assert scc.find_artifact_debris(repo, 7) == []


class TestRemoteDebris:
    def test_origin_refs_found_and_graveyard_exempt(self, tmp_path):
        repo = _make_repo(tmp_path)
        ls_remote = (
            "aaa\trefs/heads/main\n"
            "bbb\trefs/heads/issue-7\n"
            "ccc\trefs/heads/7-lld\n"
            "ddd\trefs/heads/graveyard/run11-issue-7\n"
            "eee\trefs/heads/hardening-run-11\n"
        )
        with patch.object(scc, "_run", return_value=_completed(ls_remote)):
            findings = scc.find_remote_branch_debris(repo, 7)
        assert "remote branch: origin/issue-7" in findings
        assert "remote branch: origin/7-lld" in findings
        assert len(findings) == 2

    def test_open_prs_matched_by_head_branch(self, tmp_path):
        repo = _make_repo(tmp_path)
        pr_json = (
            '[{"number": 135, "headRefName": "4-lld", "title": "docs: LLD-4"},'
            ' {"number": 200, "headRefName": "feature-x", "title": "other"}]'
        )

        def fake_run(cmd, cwd=None):
            if cmd[0] == "gh":
                return _completed(pr_json)
            if cmd[:3] == ["git", "remote", "get-url"]:
                return _completed("https://github.com/owner/boostrepo.git\n")
            return _completed("")

        with patch.object(scc, "_run", side_effect=fake_run):
            findings = scc.find_open_pr_debris(repo, 4)
        assert len(findings) == 1
        assert "#135" in findings[0]
        assert "4-lld" in findings[0]


class TestVerdict:
    def test_check_repo_aggregates_all_classes(self, tmp_path):
        repo = _make_repo(tmp_path)
        _git(repo, "branch", "issue-9")
        with patch.object(
            scc, "find_remote_branch_debris", return_value=[]
        ), patch.object(scc, "find_open_pr_debris", return_value=[]):
            findings = scc.check_repo(repo, [9])
        assert findings == ["local branch: issue-9"]

    def test_main_exit_codes(self, tmp_path):
        repo = _make_repo(tmp_path)
        with patch.object(
            scc, "find_remote_branch_debris", return_value=[]
        ), patch.object(scc, "find_open_pr_debris", return_value=[]):
            clean = scc.main(["--repo", str(repo), "--issue", "9"])
            _git(repo, "branch", "issue-9")
            dirty = scc.main(["--repo", str(repo), "--issue", "9"])
        assert clean == 0
        assert dirty == 1
        assert scc.main(["--repo", str(tmp_path / "nope"), "--issue", "9"]) == 2

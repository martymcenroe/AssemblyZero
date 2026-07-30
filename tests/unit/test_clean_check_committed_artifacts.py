"""The clean gate sees a branch that already contains the work (#1959).

`find_artifact_debris` reads `git status`, so it sees only what a killed roll
left lying around. It could not see the quieter and more dangerous case: a
branch already holding this issue's merged LLD, spec, and implementation. A
roll started there resolves the existing artifacts, finds the tests already
green, and reports success having built nothing — with the preflight that
exists to guarantee a run starts from verified zero signing off on it.

That was boostgauge's live state when this was found: `hardening-run-11`
carried all six arc phases as committed files and the gate returned CLEAN for
every one of the six issues.

Real repos, real commits, no mocks except the two network-edge finders
(standard 0024).
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


class TestCommittedArtifactDebris:
    """#1959: the gate could not see a branch that already held the work.

    Every case commits real files into a real repo — the exact state that
    produced a CLEAN verdict on boostgauge's `hardening-run-11` while all six
    arc phases sat merged on it.
    """

    def _commit_artifacts(self, repo, *rel_paths):
        for rel in rel_paths:
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("content", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "land pipeline artifacts")

    def test_committed_lld_is_found(self, tmp_path):
        repo = _make_repo(tmp_path)
        self._commit_artifacts(repo, "docs/lld/active/LLD-004.md")

        findings = scc.find_committed_artifact_debris(repo, 4, "HEAD")
        assert findings == ["committed artifact: docs/lld/active/LLD-004.md"]

    def test_committed_spec_is_found(self, tmp_path):
        repo = _make_repo(tmp_path)
        self._commit_artifacts(
            repo, "docs/lld/drafts/spec-0004-implementation-readiness.md"
        )

        assert scc.find_committed_artifact_debris(repo, 4, "HEAD") == [
            "committed artifact: "
            "docs/lld/drafts/spec-0004-implementation-readiness.md"
        ]

    def test_other_issues_artifacts_are_not_this_issues_debris(self, tmp_path):
        repo = _make_repo(tmp_path)
        self._commit_artifacts(
            repo, "docs/lld/active/LLD-041.md", "docs/lld/active/LLD-002.md"
        )

        assert scc.find_committed_artifact_debris(repo, 4, "HEAD") == []
        assert scc.find_committed_artifact_debris(repo, 41, "HEAD") == [
            "committed artifact: docs/lld/active/LLD-041.md"
        ]

    def test_clean_branch_has_no_committed_findings(self, tmp_path):
        repo = _make_repo(tmp_path)
        assert scc.find_committed_artifact_debris(repo, 4, "HEAD") == []

    def test_untracked_artifact_is_not_double_reported(self, tmp_path):
        """An uncommitted artifact belongs to the untracked class only."""
        repo = _make_repo(tmp_path)
        (repo / "docs" / "lld" / "active").mkdir(parents=True)
        (repo / "docs/lld/active/LLD-004.md").write_text("x", encoding="utf-8")

        assert scc.find_committed_artifact_debris(repo, 4, "HEAD") == []
        assert scc.find_artifact_debris(repo, 4) == [
            "untracked artifact: docs/lld/active/LLD-004.md"
        ]

    def test_check_repo_surfaces_the_committed_class(self, tmp_path):
        repo = _make_repo(tmp_path)
        self._commit_artifacts(repo, "docs/lld/active/LLD-004.md")

        findings = scc.check_repo(repo, [4], "HEAD")
        assert any(f.startswith("committed artifact:") for f in findings), findings

    def test_main_exits_nonzero_and_names_the_remedy(self, tmp_path, capsys):
        """The regression that matters: this state used to print CLEAN."""
        repo = _make_repo(tmp_path)
        self._commit_artifacts(repo, "docs/lld/active/LLD-004.md")

        with patch.object(scc, "find_open_pr_debris", return_value=[]), \
             patch.object(scc, "find_remote_branch_debris", return_value=[]):
            code = scc.main(["--repo", str(repo), "--issue", "4"])

        out = capsys.readouterr().out
        assert code == 1, out
        assert "CLEAN" not in out
        assert "ALREADY CONTAINS" in out
        assert "wrong base" in out

    def test_verdict_line_names_the_branch_it_measured(self, tmp_path, capsys):
        repo = _make_repo(tmp_path)
        _git(repo, "checkout", "-b", "hardening-run-12")

        with patch.object(scc, "find_open_pr_debris", return_value=[]), \
             patch.object(scc, "find_remote_branch_debris", return_value=[]):
            code = scc.main(["--repo", str(repo), "--issue", "4"])

        out = capsys.readouterr().out
        assert code == 0, out
        assert "CLEAN" in out
        assert "hardening-run-12" in out

    def test_describe_base_survives_a_repo_without_origin(self, tmp_path):
        """Throwaway repos have no origin/HEAD; the gate must not error out."""
        repo = _make_repo(tmp_path)
        assert "main" in scc.describe_base(repo, "main", False)

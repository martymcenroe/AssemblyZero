"""The clean check must read the base as origin has it (#2021).

Boostgauge, 2026-07-31: PR #158 merged LLD-007 into `hardening-run-13`, and the
next roll of #7 reported that base CLEAN and started building on top of it.

`git ls-tree hardening-run-13` resolves the LOCAL branch. Every PR the pipeline
opens merges on origin, and since #2012 the checkout stays on the default
branch forever, so nothing fast-forwards the local attempt branch -- it still
pointed at the commit it was cut from. Before #2012 the checkout stood on the
attempt branch and got dragged forward incidentally; that accident was the only
thing keeping the detector honest.

The decisive fixture here commits the artifact ONLY on the remote and leaves
the local branch behind. A fixture that committed locally would pass against
the broken implementation too, and prove nothing -- which is exactly how this
survived #1959's test pass.
"""

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_clean_check as scc  # noqa: E402


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo_with_remote(tmp_path):
    """A repo whose attempt branch has advanced on origin only.

    Mirrors the live shape: `hardening-run-13` exists on both sides, origin
    carries a merged LLD, and the local ref still points at the branch point.
    """
    upstream = tmp_path / "up.git"
    upstream.mkdir()
    _git(upstream, "init", "--bare", "-b", "main")

    repo = tmp_path / "boostgauge"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("x", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    _git(repo, "remote", "add", "origin", str(upstream))
    _git(repo, "push", "-u", "origin", "main")

    _git(repo, "checkout", "-b", "hardening-run-13")
    _git(repo, "push", "-u", "origin", "hardening-run-13")

    # The pipeline's own merge: lands on origin, never pulled back down.
    clone = tmp_path / "elsewhere"
    _git(tmp_path, "clone", str(upstream), str(clone))
    _git(clone, "checkout", "hardening-run-13")
    lld = clone / "docs" / "lld" / "active"
    lld.mkdir(parents=True)
    (lld / "LLD-007.md").write_text("# LLD 7", encoding="utf-8")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-m", "merge LLD-007")
    _git(clone, "push")

    # Local ref deliberately left at the branch point, as on the real box.
    _git(repo, "checkout", "main")
    return repo


class TestArtifactsThatExistOnlyOnOrigin:
    def test_the_local_ref_is_genuinely_behind(self, repo_with_remote):
        """Pins the fixture itself. If local ever equals origin here, the test
        below would pass against the broken implementation and mean nothing."""
        _git(repo_with_remote, "fetch", "origin")
        local = subprocess.run(
            ["git", "rev-parse", "hardening-run-13"], cwd=str(repo_with_remote),
            capture_output=True, text=True,
        ).stdout.strip()
        remote = subprocess.run(
            ["git", "rev-parse", "origin/hardening-run-13"],
            cwd=str(repo_with_remote), capture_output=True, text=True,
        ).stdout.strip()
        assert local != remote, "fixture must leave the local ref behind"

    def test_a_committed_artifact_on_origin_is_found(self, repo_with_remote):
        """The live miss: reading the local ref saw nothing and a roll of #7
        started on a base already holding its LLD."""
        findings = scc.find_committed_artifact_debris(
            repo_with_remote, 7, "hardening-run-13"
        )
        assert any("LLD-007" in f for f in findings), findings
        assert all(f.startswith("committed artifact:") for f in findings), findings

    def test_an_unrelated_issue_is_still_clean(self, repo_with_remote):
        """The check must stay specific -- a base carrying #7 is a fine base
        for #41 as far as this detector is concerned."""
        assert scc.find_committed_artifact_debris(
            repo_with_remote, 41, "hardening-run-13"
        ) == []


class TestRefResolution:
    def test_a_branch_with_a_remote_resolves_to_origin(self, repo_with_remote):
        assert scc.resolve_base_ref(
            repo_with_remote, "hardening-run-13"
        ) == "origin/hardening-run-13"

    def test_a_local_only_branch_falls_back_to_itself(self, tmp_path):
        """Test fixtures and one-off local bases have no remote counterpart and
        must keep working rather than erroring."""
        repo = tmp_path / "solo"
        repo.mkdir()
        _git(repo, "init", "-b", "main")
        (repo / "a.txt").write_text("x", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "init")

        assert scc.resolve_base_ref(repo, "main") == "main"

    def test_an_already_qualified_ref_is_left_alone(self, repo_with_remote):
        assert scc.resolve_base_ref(
            repo_with_remote, "origin/hardening-run-13"
        ) == "origin/hardening-run-13"

    def test_an_empty_ref_is_returned_unchanged(self, repo_with_remote):
        assert scc.resolve_base_ref(repo_with_remote, "") == ""


class TestLocalOnlyBasesStillWork:
    def test_a_locally_committed_artifact_is_still_found(self, tmp_path):
        """The pre-existing contract: a local-only base must not regress. This
        is the assertion #1959 shipped, and it passed before AND after the
        defect -- which is why it could not be the only one."""
        repo = tmp_path / "local"
        repo.mkdir()
        _git(repo, "init", "-b", "main")
        lld = repo / "docs" / "lld" / "active"
        lld.mkdir(parents=True)
        (lld / "LLD-007.md").write_text("# LLD 7", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "init")

        findings = scc.find_committed_artifact_debris(repo, 7, "main")
        assert any("LLD-007" in f for f in findings), findings

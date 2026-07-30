"""A roll's base must be declared, or be unambiguous (#1968, #1963).

#1959 taught the gate to see a base that already contains the work; #1960
taught the pipeline to carve from a named base. Neither stopped the base being
INHERITED: `graph.py` resolves `base_branch or current_branch(target)`, so with
no `--base-branch` a roll silently adopts whatever the repo is sitting on.

That is not a rare accident. A completed arc leaves the repo checked out on the
integration branch holding all of it, so inheritance is the default outcome of a
successful campaign -- boostgauge sat on `hardening-run-11` with six phases
merged, then on `hardening-run-12`, and so on.

The gate now refuses to guess, and scans the base REF rather than the checkout
so it cannot disagree with the pipeline about which tree is being judged.
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


def _make_repo_with_origin(tmp_path):
    """A repo whose origin/HEAD resolves, so divergence is measurable."""
    upstream = tmp_path / "upstream.git"
    upstream.mkdir()
    _git(upstream, "init", "--bare", "-b", "main")

    repo = tmp_path / "boostrepo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("x", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    _git(repo, "remote", "add", "origin", str(upstream))
    _git(repo, "push", "-u", "origin", "main")
    _git(repo, "remote", "set-head", "origin", "main")
    return repo


def _commit_lld(repo, issue=4):
    target = repo / "docs" / "lld" / "active"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"LLD-{issue:03d}.md").write_text("content", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"land LLD for #{issue}")


def _run_main(repo, *extra):
    with patch.object(scc, "find_open_pr_debris", return_value=[]), \
         patch.object(scc, "find_remote_branch_debris", return_value=[]):
        return scc.main(["--repo", str(repo), "--issue", "4", *extra])


class TestInheritedBaseIsRefused:
    def test_diverged_checkout_without_a_declared_base_is_refused(
        self, tmp_path, capsys
    ):
        repo = _make_repo_with_origin(tmp_path)
        _git(repo, "checkout", "-b", "hardening-run-11")
        _commit_lld(repo)

        code = _run_main(repo)
        out = capsys.readouterr().out

        assert code == 2, out
        assert "no --base-branch given" in out
        assert "hardening-run-11" in out

    def test_the_refusal_names_the_remedy(self, tmp_path, capsys):
        repo = _make_repo_with_origin(tmp_path)
        _git(repo, "checkout", "-b", "hardening-run-11")
        _commit_lld(repo)

        _run_main(repo)
        out = capsys.readouterr().out

        assert "Pass --base-branch explicitly" in out
        assert "orchestrate.py" in out

    def test_checkout_level_with_default_needs_no_declaration(
        self, tmp_path, capsys
    ):
        """Nothing ambiguous to declare -- demanding it would be ceremony."""
        repo = _make_repo_with_origin(tmp_path)

        code = _run_main(repo)
        out = capsys.readouterr().out

        assert code == 0, out
        assert "CLEAN" in out
        assert "checked-out branch main" in out

    def test_undeterminable_divergence_does_not_refuse(self, tmp_path, capsys):
        """A throwaway repo with no origin/HEAD must still be usable: unknown
        is not the same as diverged."""
        repo = tmp_path / "solo"
        repo.mkdir()
        _git(repo, "init", "-b", "main")
        (repo / "README.md").write_text("x", encoding="utf-8")
        _git(repo, "add", "README.md")
        _git(repo, "commit", "-m", "init")

        code = _run_main(repo)
        assert code == 0, capsys.readouterr().out


class TestDeclaredBaseIsTheOneMeasured:
    def test_clean_base_passes_from_a_dirty_checkout(self, tmp_path, capsys):
        """The #1963 seam: `--base-branch main` from a checkout that carries
        the work must judge MAIN, not the checkout."""
        repo = _make_repo_with_origin(tmp_path)
        _git(repo, "checkout", "-b", "hardening-run-11")
        _commit_lld(repo)

        code = _run_main(repo, "--base-branch", "main")
        out = capsys.readouterr().out

        assert code == 0, out
        assert "CLEAN" in out
        assert "declared base main" in out

    def test_dirty_base_is_refused_even_from_a_clean_checkout(
        self, tmp_path, capsys
    ):
        """And the converse, so the check is measuring the ref rather than
        merely ignoring the checkout."""
        repo = _make_repo_with_origin(tmp_path)
        _git(repo, "checkout", "-b", "hardening-run-11")
        _commit_lld(repo)
        _git(repo, "checkout", "main")

        code = _run_main(repo, "--base-branch", "hardening-run-11")
        out = capsys.readouterr().out

        assert code == 1, out
        assert "committed artifact" in out
        assert "BASE ALREADY CONTAINS" in out

    def test_unknown_ref_is_an_error_not_a_pass(self, tmp_path, capsys):
        repo = _make_repo_with_origin(tmp_path)

        code = _run_main(repo, "--base-branch", "no-such-branch")
        out = capsys.readouterr().out

        assert code == 2, out
        assert "ls-tree failed" in out


class TestScanReadsTheRefNotTheIndex:
    def test_uncommitted_artifact_is_not_a_committed_finding(self, tmp_path):
        """Staged-but-uncommitted work belongs to the untracked class; the ref
        scan must not see it."""
        repo = _make_repo_with_origin(tmp_path)
        target = repo / "docs" / "lld" / "active"
        target.mkdir(parents=True)
        (target / "LLD-004.md").write_text("x", encoding="utf-8")
        _git(repo, "add", "-A")

        assert scc.find_committed_artifact_debris(repo, 4, "main") == []

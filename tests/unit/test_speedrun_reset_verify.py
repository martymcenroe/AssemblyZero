"""speedrun_reset verifies its own work without crashing (#2000).

#1959 gave `check_repo` a required `base_ref`. Every caller was updated except
the one inside `speedrun_reset.main()`, and the full suite stayed green because
nothing exercised main() past the reset itself. The TypeError only appeared
when a real reset ran against a real repo:

    TypeError: check_repo() missing 1 required positional argument: 'base_ref'

It fired AFTER the cleanup had already been performed, so the reset did its job
and then died reporting on it -- the same shape as #1993, where the path that
reports an outcome destroyed the report.

These tests drive main() end to end against a real repo, which is the coverage
whose absence let a signature change reach a live run.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_reset as reset  # noqa: E402


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path):
    upstream = tmp_path / "up.git"
    upstream.mkdir()
    _git(upstream, "init", "--bare", "-b", "main")

    r = tmp_path / "boostgauge"
    r.mkdir()
    _git(r, "init", "-b", "main")
    (r / "README.md").write_text("x", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    _git(r, "remote", "add", "origin", str(upstream))
    _git(r, "push", "-u", "origin", "main")
    _git(r, "remote", "set-head", "origin", "main")
    return r


def _main(repo, issue=19):
    """Drive main() with every gh-backed step stubbed at the network edge.

    Both modules reach the network: speedrun_reset for PRs and remote branches,
    and the clean-check it calls for verification. A throwaway repo's origin is
    a local path, which `gh` rejects outright, so both edges must be stubbed or
    the test measures gh's argument parser instead of this code.
    """
    import speedrun_clean_check as gate

    argv = ["speedrun_reset.py", "--repo", str(repo), "--issue", str(issue)]
    with patch.object(sys, "argv", argv), \
         patch.object(reset, "_gh_repo", lambda p: "owner/repo"), \
         patch.object(reset, "close_open_prs", lambda *a: 0), \
         patch.object(reset, "delete_remote_branches", lambda *a: 0), \
         patch.object(reset, "reopen_issue", lambda *a: True), \
         patch.object(gate, "find_open_pr_debris", lambda *a, **k: []), \
         patch.object(gate, "find_remote_branch_debris", lambda *a, **k: []):
        return reset.main()


class TestVerificationRuns:
    def test_reset_on_a_clean_repo_verifies_and_succeeds(self, repo):
        """The regression: this raised TypeError before reaching a verdict."""
        assert _main(repo) == 0

    def test_it_does_not_raise_typeerror(self, repo):
        try:
            _main(repo)
        except TypeError as err:  # pragma: no cover - the failure being pinned
            raise AssertionError(f"main() crashed verifying its own work: {err}")

    def test_remaining_debris_is_reported_as_incomplete(self, repo, capsys):
        """#1918's contract: a reset that cannot prove it finished did not
        finish. Verification must still be able to SAY so."""
        _git(repo, "branch", "issue-19")

        with patch.object(reset, "delete_local_branches", lambda *a: 0):
            code = _main(repo)

        out = capsys.readouterr().out
        assert code == 1, out
        assert "INCOMPLETE" in out
        assert "issue-19" in out

    def test_verification_measures_the_checked_out_branch(self, repo):
        """A reset clears debris from the tree it is standing on, so that is
        the ref its own verification must judge."""
        _git(repo, "checkout", "-b", "hardening-run-12")

        assert _main(repo) == 0

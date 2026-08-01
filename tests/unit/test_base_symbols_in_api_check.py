"""The API-hallucination check must know the base tree, not just the plan (#2052).

boostgauge #2, run-issue2-213425:

    Gathered 10 target-repo symbols for API check
    [FAIL] api_symbols_exist
      - Spec calls methods not found ...: `current_peak`

`Telltale.current_peak()` exists -- #41 landed it on origin/hardening-run-14.
But #2's plan does not MODIFY telltale.py, it calls it, and symbols were
gathered only from files_to_modify. The universe was the plan, so a correct
call into an earlier phase's API read as hallucination and the revise loop
could never fix it, because there was nothing to fix.

The decisive fixture puts the API only on the base branch and keeps the
checkout without it: a symbol readable from the working tree would pass
against the old code and prove nothing (the #2033 fixture rule).
"""

import subprocess

import pytest

from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
    _extract_symbols_from_base,
)


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path):
    """Checkout on main; the attempt branch carries telltale.py, main does not."""
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

    _git(r, "checkout", "-b", "hardening-run-14")
    src = r / "src"
    src.mkdir()
    (src / "telltale.py").write_text(
        "class Telltale:\n    def current_peak(self):\n        return 1\n",
        encoding="utf-8",
    )
    tests_dir = r / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_telltale.py").write_text(
        "def test_helper_not_api():\n    pass\n", encoding="utf-8"
    )
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "phase 41")
    _git(r, "push", "-u", "origin", "hardening-run-14")
    _git(r, "checkout", "main")
    return r


class TestBaseSymbolsAreKnown:
    def test_an_earlier_phases_method_is_in_the_universe(self, repo):
        """The live miss: current_peak flagged as hallucinated."""
        assert not (repo / "src" / "telltale.py").exists(), "fixture: checkout must lack it"
        symbols = _extract_symbols_from_base(repo, "origin/hardening-run-14")
        assert "current_peak" in symbols
        assert "Telltale" in symbols

    def test_test_helpers_are_not_an_api_surface(self, repo):
        symbols = _extract_symbols_from_base(repo, "origin/hardening-run-14")
        assert "test_helper_not_api" not in symbols

    def test_a_missing_ref_yields_an_empty_set(self, repo):
        assert _extract_symbols_from_base(repo, "origin/no-such-branch") == set()

    def test_a_non_repo_yields_an_empty_set(self, tmp_path):
        bare = tmp_path / "empty"
        bare.mkdir()
        assert _extract_symbols_from_base(bare, "origin/x") == set()

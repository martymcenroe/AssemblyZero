"""The drafter must see the signatures of APIs it will call (#2054).

boostgauge #2, run-issue2-214927: the new telltale_manager called
Telltale(window_seconds=...). #41's actual parameter is different, so 41 of 74
tests failed on one TypeError -- twice, identically -- until the stagnation
guard halted the stage.

#2052 taught the CHECKER the base's symbol names, so the correct call to
current_peak() stopped being flagged. The DRAFTER still could not see the
declarations of files outside its plan, so it invented the kwarg. A phase that
must call an earlier phase's API needs to read that API's declaration, exactly
as a human would before writing the call.

Fixture rule as in #2033/#2052: the API lives only on the base branch and the
checkout lacks it, because that is the shape that fails.
"""

import subprocess

import pytest

from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
    _base_api_surface,
)


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

    _git(r, "checkout", "-b", "hardening-run-14")
    src = r / "src"
    src.mkdir()
    (src / "telltale.py").write_text(
        "class Telltale:\n"
        '    """Peak-hold."""\n'
        "    def __init__(self, window: float | None = None):\n"
        "        self.window = window\n"
        "    def current_peak(self):\n"
        "        return 1\n",
        encoding="utf-8",
    )
    tests_dir = r / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_x.py").write_text("def test_h(): pass\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "phase 41")
    _git(r, "push", "-u", "origin", "hardening-run-14")
    _git(r, "checkout", "main")
    return r


class TestTheDrafterSeesDeclarations:
    def test_the_signature_that_was_invented_is_now_readable(self, repo):
        """The live miss: the drafter guessed window_seconds because it never
        saw `def __init__(self, window: ...)`."""
        assert not (repo / "src" / "telltale.py").exists()
        surface = _base_api_surface(repo, "origin/hardening-run-14")

        assert "src/telltale.py" in surface
        assert "window" in surface
        assert "current_peak" in surface

    def test_it_tells_the_drafter_not_to_invent(self, repo):
        surface = _base_api_surface(repo, "origin/hardening-run-14")
        assert "EXACTLY as declared" in surface

    def test_test_helpers_are_not_included(self, repo):
        surface = _base_api_surface(repo, "origin/hardening-run-14")
        assert "test_x.py" not in surface

    def test_no_base_files_yields_empty_not_a_bare_header(self, repo):
        assert _base_api_surface(repo, "origin/no-such-branch") == ""

    def test_the_budget_truncates_visibly(self, repo):
        surface = _base_api_surface(repo, "origin/hardening-run-14", max_chars=80)
        assert surface == "" or "truncated" in surface

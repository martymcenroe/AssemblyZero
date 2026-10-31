"""base_tree under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md. The base tree is the tree the
implementation is cut from, so a question git cannot answer about it raises
``BaseTreeError`` naming the ref, the path and git's own words. It used to
read as "the file is not there", and the spec was planned against a tree that
was not the one it would be built on. A path that is genuinely absent from a
base git can read is still an answer: ``False`` and ``""``.
"""
from __future__ import annotations

import subprocess

import pytest

from assemblyzero.workflows.implementation_spec import base_tree as bt


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


def _repo(tmp_path, *, origin: str | None = "bare"):
    """A checkout on main; `phase` carries src/telltale.py and is pushed.

    ``origin="bare"`` adds a reachable bare origin, ``origin=None`` none at
    all, and any other string is used as the origin URL as given.
    """
    r = tmp_path / "boostgauge"
    r.mkdir()
    _git(r, "init", "-b", "main")
    (r / "README.md").write_text("x", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    if origin == "bare":
        upstream = tmp_path / "up.git"
        upstream.mkdir()
        _git(upstream, "init", "--bare", "-b", "main")
        _git(r, "remote", "add", "origin", str(upstream))
        _git(r, "push", "-u", "origin", "main")
    elif origin is not None:
        _git(r, "remote", "add", "origin", origin)
    _git(r, "switch", "-c", "phase")
    (r / "src").mkdir()
    (r / "src" / "telltale.py").write_text("def peak():\n    return 1\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "phase 41")
    if origin == "bare":
        _git(r, "push", "-u", "origin", "phase")
    _git(r, "switch", "main")
    return r


class TestBaseRef:
    def test_41_a_fetch_that_fails_raises(self, tmp_path):
        repo = _repo(tmp_path, origin=str(tmp_path / "no-such-remote"))

        with pytest.raises(bt.BaseTreeError) as caught:
            bt.base_ref(repo, "phase")
        message = str(caught.value)
        assert "fetch" in message
        assert "phase" in message
        assert "no-such-remote" in message, "git's own stderr must be in the message"

    def test_41_a_repo_with_no_origin_raises(self, tmp_path):
        repo = _repo(tmp_path, origin=None)

        with pytest.raises(bt.BaseTreeError, match="fetch"):
            bt.base_ref(repo, "phase")

    def test_45_a_base_that_is_not_on_origin_raises(self, tmp_path):
        """The local branch is never fast-forwarded (#2021), so falling back
        to it planned against a tree the implementation is not cut from."""
        repo = _repo(tmp_path)
        _git(repo, "branch", "local-only")

        with pytest.raises(bt.BaseTreeError) as caught:
            bt.base_ref(repo, "local-only")
        assert "origin/local-only" in str(caught.value)

    def test_a_pushed_base_resolves_to_origin(self, tmp_path):
        repo = _repo(tmp_path)
        assert bt.base_ref(repo, "phase") == "origin/phase"

    def test_no_base_branch_is_no_base(self, tmp_path):
        """Kept: a run with no base branch reads the checkout only."""
        assert bt.base_ref(tmp_path, "") == ""

    def test_an_origin_ref_is_taken_as_given(self, tmp_path):
        """Kept: an explicit origin/ ref needs no fetch to be named."""
        assert bt.base_ref(tmp_path, "origin/phase") == "origin/phase"


class TestExistsOnBase:
    def test_54_a_ref_git_cannot_read_raises(self, tmp_path):
        repo = _repo(tmp_path)

        with pytest.raises(bt.BaseTreeError) as caught:
            bt.exists_on_base(repo, "origin/no-such-branch", "src/telltale.py")
        message = str(caught.value)
        assert "origin/no-such-branch" in message
        assert "src/telltale.py" in message

    def test_a_path_the_base_lacks_is_false(self, tmp_path):
        """Kept: absence on a readable base is an answer, not a failure."""
        repo = _repo(tmp_path)
        assert bt.exists_on_base(repo, "origin/phase", "src/nope.py") is False

    def test_a_path_the_base_ships_is_true(self, tmp_path):
        repo = _repo(tmp_path)
        assert bt.exists_on_base(repo, "origin/phase", "src/telltale.py") is True
        assert bt.exists_on_base(repo, "origin/phase", "src\\telltale.py") is True

    def test_no_ref_is_false(self, tmp_path):
        assert bt.exists_on_base(tmp_path, "", "src/telltale.py") is False


class TestReadFromBase:
    def test_63_a_ref_git_cannot_read_raises(self, tmp_path):
        repo = _repo(tmp_path)

        with pytest.raises(bt.BaseTreeError) as caught:
            bt.read_from_base(repo, "origin/no-such-branch", "src/telltale.py")
        message = str(caught.value)
        assert "origin/no-such-branch" in message
        assert "src/telltale.py" in message

    def test_63_a_directory_that_is_not_a_repo_raises(self, tmp_path):
        with pytest.raises(bt.BaseTreeError):
            bt.read_from_base(tmp_path, "origin/phase", "src/telltale.py")

    def test_a_path_the_base_lacks_reads_empty(self, tmp_path):
        """Kept: analyze_codebase then reports the missing Modify target."""
        repo = _repo(tmp_path)
        assert bt.read_from_base(repo, "origin/phase", "src/nope.py") == ""

    def test_a_shipped_path_reads_its_content(self, tmp_path):
        repo = _repo(tmp_path)
        assert "def peak" in bt.read_from_base(repo, "origin/phase", "src/telltale.py")

    def test_no_ref_reads_empty(self, tmp_path):
        assert bt.read_from_base(tmp_path, "", "src/telltale.py") == ""


class TestReclassify:
    def test_45_reclassifying_against_a_base_not_on_origin_raises(self, tmp_path):
        repo = _repo(tmp_path)
        files = [{"path": "src/telltale.py", "change_type": "Add", "description": "d"}]

        with pytest.raises(bt.BaseTreeError):
            bt.reclassify_against_base(files, repo, "no-such-branch")

    def test_an_add_the_base_ships_becomes_a_modify(self, tmp_path):
        repo = _repo(tmp_path)
        files = [{"path": "src/telltale.py", "change_type": "Add", "description": "d"}]

        updated, notes = bt.reclassify_against_base(files, repo, "phase")
        assert updated[0]["change_type"] == "Modify"
        assert notes


def test_base_tree_error_is_not_an_os_error():
    """A caller that reads OSError as a missing file must not read a git
    failure that way."""
    assert issubclass(bt.BaseTreeError, RuntimeError)
    assert not issubclass(bt.BaseTreeError, OSError)

"""The spec must be planned against the base, not the checkout (#2033).

The implementation happens in a worktree cut from the attempt branch. The spec
is drafted from `repo_root`, whose checkout has sat permanently on the default
branch since #2012. Mid-arc those are different trees -- `main` carries none of
the arc, the attempt branch carries every phase landed so far.

boostgauge #2 listed `telltale.py`, `gauge.py` and `stingray.py` as files to
Add. All three were already on the base, put there by #41 and #1. The spec
described modules to create; the implementation followed it and deleted
`render` and `render_stingray`, which #1's own tests import.

The fixtures here put the file ONLY on the base branch and leave the checkout
without it, because that is the shape that fails. A fixture with the file in the
working tree passes against the old code and proves nothing.
"""

import subprocess

import pytest

from assemblyzero.workflows.implementation_spec.base_tree import (
    base_ref,
    exists_on_base,
    read_from_base,
    reclassify_against_base,
)


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path):
    """Checkout on main; an attempt branch carrying a file main has never seen."""
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

    # An earlier phase lands telltale.py on the attempt branch.
    _git(r, "checkout", "-b", "hardening-run-14")
    src = r / "src"
    src.mkdir()
    (src / "telltale.py").write_text(
        "def render_stingray():\n    return 'phase 41'\n", encoding="utf-8"
    )
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "phase 41")
    _git(r, "push", "-u", "origin", "hardening-run-14")

    # The checkout goes back to the default branch, per #2012. src/ is gone.
    _git(r, "checkout", "main")
    return r


class TestSeeingTheBase:
    def test_the_checkout_really_lacks_the_file(self, repo):
        """Pins the fixture. If the file were present in the working tree the
        tests below would pass against the old behaviour and mean nothing."""
        assert not (repo / "src" / "telltale.py").exists()

    def test_a_base_file_is_visible(self, repo):
        ref = base_ref(repo, "hardening-run-14")
        assert exists_on_base(repo, ref, "src/telltale.py") is True

    def test_its_contents_can_be_read(self, repo):
        ref = base_ref(repo, "hardening-run-14")
        assert "render_stingray" in read_from_base(repo, ref, "src/telltale.py")

    def test_a_file_on_no_branch_is_not_found(self, repo):
        ref = base_ref(repo, "hardening-run-14")
        assert exists_on_base(repo, ref, "src/nope.py") is False
        assert read_from_base(repo, ref, "src/nope.py") == ""

    def test_the_base_resolves_to_origin(self, repo):
        """#2021: the local attempt ref is never fast-forwarded, so reading it
        would report the tree as it was when the branch was cut."""
        assert base_ref(repo, "hardening-run-14") == "origin/hardening-run-14"


class TestReclassification:
    def test_an_add_the_base_already_ships_becomes_a_modify(self, repo):
        """The live defect: planned as new, already present, spec described a
        module to create."""
        files = [{"path": "src/telltale.py", "change_type": "Add", "description": "d"}]
        updated, notes = reclassify_against_base(files, repo, "hardening-run-14")

        assert updated[0]["change_type"] == "Modify"
        assert any("telltale.py" in n for n in notes)

    def test_a_genuinely_new_file_stays_an_add(self, repo):
        files = [{"path": "src/brand_new.py", "change_type": "Add", "description": "d"}]
        updated, notes = reclassify_against_base(files, repo, "hardening-run-14")

        assert updated[0]["change_type"] == "Add"
        assert notes == []

    def test_an_explicit_modify_is_left_alone(self, repo):
        files = [{"path": "src/telltale.py", "change_type": "Modify", "description": "d"}]
        updated, _ = reclassify_against_base(files, repo, "hardening-run-14")
        assert updated[0]["change_type"] == "Modify"

    def test_a_modify_the_base_lacks_is_not_invented_into_an_add(self, repo):
        """One-way only. An LLD naming the wrong file must still be reported by
        the existing guard rather than quietly rewritten into something valid."""
        files = [{"path": "src/nope.py", "change_type": "Modify", "description": "d"}]
        updated, _ = reclassify_against_base(files, repo, "hardening-run-14")
        assert updated[0]["change_type"] == "Modify"

    def test_the_change_is_stated_not_silent(self, repo):
        files = [{"path": "src/telltale.py", "change_type": "Add", "description": "d"}]
        _, notes = reclassify_against_base(files, repo, "hardening-run-14")
        assert notes and "already ships it" in notes[0]


class TestRunsWithoutAnAttemptBranch:
    """A fresh feature on main must behave exactly as before."""

    def test_no_base_branch_changes_nothing(self, repo):
        files = [{"path": "src/telltale.py", "change_type": "Add", "description": "d"}]
        updated, notes = reclassify_against_base(files, repo, "")

        assert updated[0]["change_type"] == "Add"
        assert notes == []

    def test_an_empty_base_ref_reads_as_absent(self, repo):
        assert exists_on_base(repo, "", "src/telltale.py") is False
        assert read_from_base(repo, "", "src/telltale.py") == ""

    def test_a_base_that_does_not_exist_is_not_fatal(self, repo):
        files = [{"path": "src/telltale.py", "change_type": "Add", "description": "d"}]
        updated, _ = reclassify_against_base(files, repo, "no-such-branch")
        assert updated[0]["change_type"] == "Add"

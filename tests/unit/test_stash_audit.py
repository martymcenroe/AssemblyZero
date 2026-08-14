"""Everything a stash holds, before the drop makes it unrecoverable (#2364).

These tests build real repositories and run real `git stash`. The behaviour
under test is git's own -- that a stash made with `--include-untracked` files
its untracked half in a third parent which `git stash show` does not list --
and a mocked git would let that claim pass without ever being true.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import stash_audit as sa  # noqa: E402


def run(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


@pytest.fixture
def repo(tmp_path) -> Path:
    """A repo with one commit on `main` and an `origin/main` to land against."""
    origin = tmp_path / "origin"
    origin.mkdir()
    run(origin, "init", "-q", "--bare")

    work = tmp_path / "work"
    work.mkdir()
    run(work, "init", "-q", "-b", "main")
    run(work, "config", "user.email", "t@example.com")
    run(work, "config", "user.name", "t")
    (work / "tracked.txt").write_text("original\n", encoding="utf-8")
    run(work, "add", "tracked.txt")
    run(work, "commit", "-qm", "init")
    run(work, "remote", "add", "origin", str(origin))
    run(work, "push", "-q", "origin", "main")
    return work


def stash_everything(repo: Path) -> None:
    run(repo, "stash", "push", "-q", "-m", "wip", "--include-untracked")


class TestGitReallyHidesTheUntrackedHalf:
    """The falsifier for the whole tool. If `git stash show` listed everything,
    none of this would be worth running."""

    def test_stash_show_under_reports(self, repo):
        (repo / "mine.py").write_text("mine\n", encoding="utf-8")
        (repo / "other_lane.py").write_text("theirs\n", encoding="utf-8")
        (repo / "tracked.txt").write_text("edited\n", encoding="utf-8")

        stash_everything(repo)

        listed = run(repo, "stash", "show", "--name-only", "stash@{0}").split()
        assert listed == ["tracked.txt"], "git's own listing shows one of three"

        audited = {f["path"] for f in sa.audit(repo, "stash@{0}", "origin/main")}
        assert audited == {"tracked.txt", "mine.py", "other_lane.py"}


class TestTheTwoHalvesAreLabelled:
    def test_each_path_is_attributed_to_its_half(self, repo):
        (repo / "swept.py").write_text("swept\n", encoding="utf-8")
        (repo / "tracked.txt").write_text("edited\n", encoding="utf-8")
        stash_everything(repo)

        halves = {
            f["path"]: f["half"] for f in sa.audit(repo, "stash@{0}", "origin/main")
        }
        assert halves == {"tracked.txt": "tracked", "swept.py": "untracked"}

    def test_a_stash_without_u_has_no_third_parent_and_that_is_fine(self, repo):
        (repo / "tracked.txt").write_text("edited\n", encoding="utf-8")
        run(repo, "stash", "push", "-q", "-m", "wip")

        assert sa.untracked_paths(repo, "stash@{0}") == []
        findings = sa.audit(repo, "stash@{0}", "origin/main")
        assert [f["path"] for f in findings] == ["tracked.txt"]


class TestLandedVersusLost:
    def test_an_untracked_file_never_landed_is_absent(self, repo):
        (repo / "other_lane.py").write_text("theirs\n", encoding="utf-8")
        stash_everything(repo)

        (finding,) = sa.audit(repo, "stash@{0}", "origin/main")
        assert finding["status"] == sa.ABSENT

    def test_an_untracked_file_that_did_land_is_landed(self, repo):
        (repo / "mine.py").write_text("mine\n", encoding="utf-8")
        stash_everything(repo)

        # It landed on origin between the stash and the audit, byte for byte.
        (repo / "mine.py").write_text("mine\n", encoding="utf-8")
        run(repo, "add", "mine.py")
        run(repo, "commit", "-qm", "land it")
        run(repo, "push", "-q", "origin", "main")

        (finding,) = sa.audit(repo, "stash@{0}", "origin/main")
        assert finding["status"] == sa.LANDED

    def test_a_file_that_landed_with_different_content_differs(self, repo):
        (repo / "mine.py").write_text("version A\n", encoding="utf-8")
        stash_everything(repo)

        (repo / "mine.py").write_text("version B\n", encoding="utf-8")
        run(repo, "add", "mine.py")
        run(repo, "commit", "-qm", "land a different version")
        run(repo, "push", "-q", "origin", "main")

        (finding,) = sa.audit(repo, "stash@{0}", "origin/main")
        assert finding["status"] == sa.DIFFERS, (
            "same path, different bytes -- dropping still loses the stashed one"
        )


class TestTheVerdict:
    def test_it_refuses_when_anything_is_unaccounted(self, repo, capsys):
        (repo / "other_lane.py").write_text("theirs\n", encoding="utf-8")
        stash_everything(repo)

        code = sa.main(["--repo", str(repo)])

        out = capsys.readouterr().out
        assert code == sa.EXIT_UNACCOUNTED
        assert "DO NOT DROP" in out
        assert "other_lane.py" in out

    def test_it_clears_a_stash_whose_every_path_landed(self, repo, capsys):
        (repo / "mine.py").write_text("mine\n", encoding="utf-8")
        stash_everything(repo)
        (repo / "mine.py").write_text("mine\n", encoding="utf-8")
        run(repo, "add", "mine.py")
        run(repo, "commit", "-qm", "land it")
        run(repo, "push", "-q", "origin", "main")

        code = sa.main(["--repo", str(repo)])

        out = capsys.readouterr().out
        assert code == sa.EXIT_ACCOUNTED
        assert "byte-identical" in out
        assert "DO NOT DROP" not in out

    def test_a_clean_verdict_still_says_what_it_did_not_check(self, repo, capsys):
        """Presence is not ownership. The #2364 files would each have read as
        'absent here' and been someone's real work regardless."""
        (repo / "mine.py").write_text("mine\n", encoding="utf-8")
        stash_everything(repo)
        (repo / "mine.py").write_text("mine\n", encoding="utf-8")
        run(repo, "add", "mine.py")
        run(repo, "commit", "-qm", "land it")
        run(repo, "push", "-q", "origin", "main")

        sa.main(["--repo", str(repo)])

        assert "Not verified" in capsys.readouterr().out


class TestItNeverGuessesWhenItCannotRun:
    def test_an_unknown_stash_is_an_error_not_a_pass(self, repo, capsys):
        code = sa.main(["--repo", str(repo), "--stash", "stash@{7}"])

        assert code == sa.EXIT_ERROR
        assert "Nothing about this stash has been verified" in capsys.readouterr().err

    def test_an_unknown_ref_is_an_error_not_a_pass(self, repo, capsys):
        (repo / "mine.py").write_text("mine\n", encoding="utf-8")
        stash_everything(repo)

        code = sa.main(["--repo", str(repo), "--ref", "origin/nonexistent"])

        assert code == sa.EXIT_ERROR
        assert "could not run" in capsys.readouterr().err

    def test_an_empty_stash_reports_that_it_verified_nothing(self, capsys):
        assert "nothing was verified" in sa.render([], "stash@{0}", "origin/main")

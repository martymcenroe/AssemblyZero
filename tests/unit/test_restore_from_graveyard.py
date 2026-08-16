"""The resume reads back from where the janitor preserves to (#2459).

`_restore_artifact` searched only the issue's `{N}-lld` branch. The file
janitor preserves what it clears onto `graveyard/leavings-*` refs. Those are
different places, and the second was never consulted -- so an artifact that was
preserved, committed and pushed read as missing, and the resume was abandoned
for a file one `git show` away.

Measured on boostgauge #1, 2026-08-15: neither `LLD-001.md` nor
`spec-0001-implementation-readiness.md` was on disk, and NEITHER was on
`1-lld`. Both were on `graveyard/leavings-20260815-161853` and `...-161847`,
pushed. The next relaunch would have redrawn the LLD and the spec both.

Neither existing repair covers it. #2414 turned a path-string lookup into an
artifact lookup, and the path here is recorded and real -- the ARTIFACT is what
is missing. #2311 stopped the spec being lost in FUTURE runs, cannot un-clear
what earlier runs swept, and does not cover the LLD, which still lives under
`docs/lld/active/` inside the janitor's allowlist.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402

LLD_REL = "docs/lld/active/LLD-001.md"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path):
    """A repo whose artifact exists ONLY on a graveyard leavings ref.

    Built the way the janitor builds it: the file is committed onto a
    `graveyard/leavings-*` branch and then absent from the working tree and
    from the lld branch.
    """
    r = tmp_path / "boostgauge"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "README.md").write_text("base\n", encoding="utf-8")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "base")
    default = _git(r, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    # The lld branch exists but does NOT carry the artifact -- the measured shape.
    _git(r, "checkout", "-q", "-b", "1-lld")
    (r / "unrelated.md").write_text("x\n", encoding="utf-8")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "lld branch without the draft")
    _git(r, "checkout", "-q", default)

    _git(r, "checkout", "-q", "-b", "graveyard/leavings-20260815-161853")
    target = r / LLD_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# LLD one\n\nreal content\n", encoding="utf-8")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "preserved leavings")
    _git(r, "checkout", "-q", default)

    assert not (r / LLD_REL).exists(), "fixture must start with the file cleared"
    return r


class TestTheMeasuredShapeRestores:
    def test_an_artifact_only_on_a_graveyard_ref_is_restored(self, repo):
        assert sr._restore_artifact(repo, 1, str(repo / LLD_REL)) is True
        assert (repo / LLD_REL).is_file()

    def test_the_content_is_the_preserved_content(self, repo):
        sr._restore_artifact(repo, 1, str(repo / LLD_REL))
        assert "real content" in (repo / LLD_REL).read_text(encoding="utf-8")

    def test_the_old_behaviour_would_have_declined(self, repo):
        """Pins WHY: the lld branch exists and does not carry the file, so a
        lld-branch-only search returns nothing. Without this the test above
        could be passing for an unrelated reason."""
        show = _git(repo, "show", f"1-lld:{LLD_REL}")
        assert show.returncode != 0

    def test_the_refs_are_discovered(self, repo):
        refs = sr._graveyard_leavings_refs(repo)
        assert any("leavings-20260815-161853" in r for r in refs)


class TestTheNewestRefWins:
    def test_a_later_leavings_ref_supersedes_an_earlier_one(self, repo):
        """An older ref may hold a stale draft from a superseded attempt."""
        default = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        _git(repo, "checkout", "-q", "-b", "graveyard/leavings-20260815-999999")
        target = repo / LLD_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# LLD one\n\nNEWER content\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "newer leavings")
        _git(repo, "checkout", "-q", default)
        target.unlink(missing_ok=True)

        sr._restore_artifact(repo, 1, str(target))
        assert "NEWER content" in target.read_text(encoding="utf-8")


class TestItStillDeclinesWhenNothingHasIt:
    def test_absent_everywhere_declines(self, repo):
        missing = repo / "docs" / "lld" / "active" / "LLD-999.md"
        assert sr._restore_artifact(repo, 1, str(missing)) is False

    def test_a_repo_with_no_graveyard_refs_is_not_an_error(self, tmp_path):
        bare = tmp_path / "plain"
        bare.mkdir()
        _git(bare, "init", "-q")
        assert sr._graveyard_leavings_refs(bare) == []
        assert sr._restore_artifact(bare, 1, str(bare / "a.md")) is False

    def test_a_path_outside_the_repo_declines(self, repo):
        assert sr._restore_artifact(repo, 1, "C:/elsewhere/a.md") is False


class TestTheLldBranchStillWinsFirst:
    """The graveyard is the FALLBACK. A committed draft on the lld branch is
    the authoritative copy and must still be preferred."""

    def test_the_lld_branch_copy_is_used_when_present(self, repo):
        default = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        _git(repo, "checkout", "-q", "1-lld")
        target = repo / LLD_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# LLD one\n\nBRANCH content\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "draft on the lld branch")
        _git(repo, "checkout", "-q", default)
        target.unlink(missing_ok=True)

        sr._restore_artifact(repo, 1, str(target))
        assert "BRANCH content" in target.read_text(encoding="utf-8")

    def test_a_file_already_on_disk_is_left_alone(self, repo):
        target = repo / LLD_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ON DISK\n", encoding="utf-8")

        assert sr._restore_artifact(repo, 1, str(target)) is True
        assert target.read_text(encoding="utf-8") == "ON DISK\n"

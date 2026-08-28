"""The loader rebuilds a missing input from refs before concluding absence (#2571).

The working copy is a cache. Issue #331's LLD was deleted from the working
tree three times on 2026-08-27 (see #2551) and survived only on refs — the
`{issue}-lld` branch and the janitor's leavings refs. The restore machinery
already knew how to search those (the speedrun resume planner used it);
this pins its new shared home and the loader's rebuild-on-miss.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from assemblyzero.speedrun.leavings import preserve_and_clear  # noqa: E402
from assemblyzero.speedrun.restore import (  # noqa: E402
    graveyard_leavings_refs,
    restore_artifact,
)
from assemblyzero.workflows.testing.nodes.load_lld import find_lld_path  # noqa: E402


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo with a bare origin, as the janitor tests build one."""
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
        capture_output=True, text=True, check=True,
    )
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-qu", "origin", "main")
    return root


LLD_REL = "docs/lld/active/LLD-007.md"
LLD_BODY = "# LLD-007\n\n## 3. Requirements\n\n1. Render the face.\n"


def _swept_lld(repo: Path) -> None:
    """The observed shape: the LLD preserved onto a leavings ref, working
    copy cleared."""
    target = repo / LLD_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(LLD_BODY, encoding="utf-8")
    result = preserve_and_clear(repo, [LLD_REL])
    assert result.branch, "fixture failed to preserve"
    assert not target.exists()


class TestRestoreArtifact:
    def test_a_swept_input_is_rebuilt_from_the_leavings_ref(self, repo, capsys):
        _swept_lld(repo)
        events: list[str] = []
        assert restore_artifact(
            repo, 7, str(repo / LLD_REL), log=events.append
        ) is True
        assert (repo / LLD_REL).read_text(encoding="utf-8") == LLD_BODY
        assert events and "[REBUILT]" in events[0]
        assert "graveyard/leavings-" in events[0]

    def test_the_live_lld_branch_outranks_the_leavings(self, repo):
        """The lld stage's branch is the freshest home; a stale leavings
        copy must not shadow it."""
        _swept_lld(repo)
        _git(repo, "checkout", "-qb", "7-lld")
        fresh = repo / LLD_REL
        fresh.parent.mkdir(parents=True, exist_ok=True)
        fresh.write_text(LLD_BODY + "\n(revised on the lld branch)\n",
                         encoding="utf-8")
        _git(repo, "add", LLD_REL)
        _git(repo, "commit", "-qm", "lld")
        _git(repo, "checkout", "-q", "main")
        assert not (repo / LLD_REL).exists()

        assert restore_artifact(repo, 7, str(repo / LLD_REL)) is True
        assert "revised on the lld branch" in (repo / LLD_REL).read_text(
            encoding="utf-8"
        )

    def test_nothing_preserved_is_a_clean_false(self, repo):
        assert restore_artifact(repo, 7, str(repo / LLD_REL)) is False
        assert not (repo / LLD_REL).exists()

    def test_a_present_file_is_left_alone(self, repo):
        target = repo / LLD_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("already here\n", encoding="utf-8")
        assert restore_artifact(repo, 7, str(target)) is True
        assert target.read_text(encoding="utf-8") == "already here\n"

    def test_leavings_refs_order_newest_first(self, repo):
        for rel in ("docs/lld/active/LLD-001.md", "docs/lld/active/LLD-002.md"):
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x\n", encoding="utf-8")
            preserve_and_clear(repo, [rel])
        refs = graveyard_leavings_refs(repo)
        assert len(refs) >= 2
        stamps = [ref.rpartition("leavings-")[2] for ref in refs]
        assert stamps == sorted(stamps, reverse=True)


class TestTheLoaderRebuilds:
    def test_find_lld_path_rebuilds_from_refs_on_a_miss(self, repo, capsys):
        """#2571's acceptance: delete the working copy, and the loader
        rebuilds it from the ref and resolves it, logging the rebuild."""
        _swept_lld(repo)
        resolved = find_lld_path(7, repo)
        assert resolved is not None
        assert resolved.read_text(encoding="utf-8") == LLD_BODY
        out = capsys.readouterr().out
        assert "[REBUILT]" in out

    def test_a_present_working_copy_needs_no_refs(self, tmp_path):
        lld = tmp_path / "docs" / "lld" / "active" / "LLD-007.md"
        lld.parent.mkdir(parents=True)
        lld.write_text("cache hit\n", encoding="utf-8")
        assert find_lld_path(7, tmp_path) == lld

    def test_genuine_absence_stays_a_clean_none(self, repo, capsys):
        assert find_lld_path(7, repo) is None
        assert "[WARN]" not in capsys.readouterr().out

    def test_a_plain_directory_is_not_probed_for_refs(self, tmp_path):
        assert find_lld_path(7, tmp_path) is None


class TestTheOldCallSitesStillWork:
    def test_speedrun_roll_aliases_the_shared_machinery(self):
        """Moved, not forked: two copies is how the 2026-08-15 gap
        happened in the first place."""
        import speedrun_roll as sr

        assert sr._restore_artifact is restore_artifact
        assert sr._graveyard_leavings_refs is graveyard_leavings_refs

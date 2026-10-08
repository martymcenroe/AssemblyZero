"""A rebuilt LLD comes from the durable copy or the base, never an old graveyard draft (#3764).

Since #3704 the merge driver deletes `<N>-lld` after landing, so the landed
LLD lives on the base and in the durable handoff copy (#3750). The search
consulted neither and fell through to the graveyard: boostgauge #2,
run-issue2-052813 (2026-10-07), rebuilt `LLD-002.md` from
`graveyard/2-lld-salvage-20260809` and implemented an August draft.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from assemblyzero.core.settlement import sha256_text
from assemblyzero.speedrun.restore import restore_artifact
from assemblyzero.workflows.requirements.audit import save_settlement
from assemblyzero.workflows.requirements.nodes.finalize import durable_lld_path

LLD_REL = "docs/lld/active/LLD-007.md"
AUGUST_DRAFT = "# LLD-007\n\nThe August draft, superseded.\n"
LANDED = "# LLD-007\n\nThe approved LLD, as landed.\n"


def _git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo with a bare origin and an old graveyard copy of the LLD."""
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

    # The graveyard draft: an August attempt, preserved under an archive name.
    _git(root, "switch", "-qc", "graveyard/7-lld-20260809-000000")
    lld = root / LLD_REL
    lld.parent.mkdir(parents=True, exist_ok=True)
    lld.write_text(AUGUST_DRAFT, encoding="utf-8")
    _git(root, "add", LLD_REL)
    _git(root, "commit", "-qm", "august draft")
    _git(root, "switch", "-q", "main")
    assert not lld.exists()
    return root


def _land_on_base(repo: Path) -> None:
    """The LLD as the driver lands it: on main and origin/main, then the
    working copy is gone."""
    lld = repo / LLD_REL
    lld.parent.mkdir(parents=True, exist_ok=True)
    lld.write_text(LANDED, encoding="utf-8")
    _git(repo, "add", LLD_REL)
    _git(repo, "commit", "-qm", "land LLD")
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "rm", "-q", LLD_REL)
    _git(repo, "commit", "-qm", "working copy cleared")


class TestSourceOrder:
    def test_the_durable_copy_wins_over_a_graveyard_draft(self, repo):
        durable = durable_lld_path(repo, 7)
        durable.parent.mkdir(parents=True, exist_ok=True)
        durable.write_text(LANDED, encoding="utf-8")
        events: list[str] = []

        assert restore_artifact(repo, 7, str(repo / LLD_REL), log=events.append) is True

        assert (repo / LLD_REL).read_text(encoding="utf-8") == LANDED
        assert events == [
            f"[REBUILT] {LLD_REL} restored from '{durable}' (#2571, #3764)"
        ]

    def test_the_base_wins_over_an_older_graveyard_copy(self, repo):
        _land_on_base(repo)
        events: list[str] = []

        assert restore_artifact(
            repo, 7, str(repo / LLD_REL), log=events.append, base="main"
        ) is True

        assert (repo / LLD_REL).read_text(encoding="utf-8") == LANDED
        assert events and "restored from 'origin/main'" in events[0]

    def test_a_graveyard_copy_that_is_not_the_settled_lld_is_refused(self, repo):
        save_settlement(7, "lld", {"artifact_sha256": sha256_text(LANDED)}, repo)
        events: list[str] = []

        assert restore_artifact(repo, 7, str(repo / LLD_REL), log=events.append) is False

        assert not (repo / LLD_REL).exists()
        assert len(events) == 1
        assert events[0].startswith(f"[REFUSED] {LLD_REL} on 'graveyard/7-lld-20260809-000000'")
        assert "is not the settled LLD" in events[0]

    def test_a_graveyard_copy_that_is_the_settled_lld_is_used(self, repo):
        save_settlement(7, "lld", {"artifact_sha256": sha256_text(AUGUST_DRAFT)}, repo)

        assert restore_artifact(repo, 7, str(repo / LLD_REL)) is True
        assert (repo / LLD_REL).read_text(encoding="utf-8") == AUGUST_DRAFT

    def test_with_no_settlement_record_the_graveyard_is_still_a_last_resort(self, repo):
        events: list[str] = []
        assert restore_artifact(repo, 7, str(repo / LLD_REL), log=events.append) is True
        assert "graveyard/7-lld-20260809-000000" in events[0]

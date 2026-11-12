"""The universal CLAUDE.md checkers, run on fixtures (#4733, #3730).

`tests/test_universal_claude_md.py` runs these checkers on the installed law,
and skips wherever the law is not on disk, CI among them. These tests feed
them fixture text instead, so the checkers themselves are tested in the unit
tier on every run.
"""

from __future__ import annotations

from pathlib import Path

from assemblyzero.core import seats
from tests.test_universal_claude_md import (
    STATE_FILES,
    find_unresolved_adr_references,
    find_unresolved_file_paths,
)

SPEND_LOCK = "~/.claude/claude-spend.lock"


# ---------------------------------------------------------------------------
# #4733: a state file the law names is checked against its owner, not the disk
# ---------------------------------------------------------------------------


def test_only_the_absent_path_that_is_not_a_state_file_is_reported(tmp_path: Path):
    """#4733 T2: neither file exists under this home; only the second is reported."""
    text = f"Thrown with `{SPEND_LOCK}`. A hook at `~/.claude/hooks/no-such-hook.sh`.\n"
    missing = find_unresolved_file_paths(text, home=tmp_path)
    assert len(missing) == 1, missing
    assert "`~/.claude/hooks/no-such-hook.sh`" in missing[0]
    assert "claude-spend.lock" not in missing[0]


def test_a_path_that_exists_is_not_reported(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    assert find_unresolved_file_paths("See `~/.claude/settings.json`.\n", home=tmp_path) == []


def test_the_spend_lock_fails_when_its_owner_names_another_file(tmp_path: Path, monkeypatch):
    """The exemption holds only while the owning code names the same file."""
    monkeypatch.setattr(seats, "LOCK_NAME", "claude-spend-v2.lock")
    missing = find_unresolved_file_paths(f"Thrown with `{SPEND_LOCK}`.\n", home=tmp_path)
    assert len(missing) == 1, missing
    assert "assemblyzero/core/seats.py LOCK_NAME" in missing[0]
    assert "claude-spend-v2.lock" in missing[0]


def test_the_state_file_list_is_closed_with_one_entry_per_reason():
    """#4733 AC2. A new entry is a decision, so it changes this test too."""
    assert set(STATE_FILES) == {SPEND_LOCK}
    for path, entry in STATE_FILES.items():
        assert entry.reason and entry.owner, path
        assert Path(path).name == entry.owner_name(), path


# ---------------------------------------------------------------------------
# #3730: an ADR number belongs to the repository the text names for it
# ---------------------------------------------------------------------------


def _adr(root: Path, repo: str, name: str) -> None:
    adrs = root / repo / "docs" / "adrs"
    adrs.mkdir(parents=True, exist_ok=True)
    (adrs / name).write_text("# ADR\n", encoding="utf-8")


def test_a_default_adr_and_a_named_adr_resolve_and_a_bare_unplaced_one_fails(tmp_path: Path):
    """#3730 T1. OtherRepo holds an 0003 as well, so a bare ADR-0003 resolving
    would mean the checker searched every repository instead of placing it."""
    _adr(tmp_path, "AssemblyZero", "0216-classic-pat.md")
    _adr(tmp_path, "OtherRepo", "0010-pinned-release.md")
    _adr(tmp_path, "OtherRepo", "0003-home-path.md")
    text = (
        "The classic-PAT pattern is ADR-0216.\n"
        "A production site runs a pinned release (ADR 0010).\n"
        "The decision: `Projects/OtherRepo/docs/adrs/0010-pinned-release.md`.\n"
        "The home path is hardcoded across guards, memory, and ADR-0003.\n"
    )
    missing = find_unresolved_adr_references(text, projects_root=tmp_path)
    assert len(missing) == 1, missing
    assert missing[0].startswith("  - ADR-0003 (line 4)")
    assert "names no repository" in missing[0]


def test_an_adr_named_in_two_repositories_cannot_be_placed(tmp_path: Path):
    _adr(tmp_path, "RepoA", "0005-a.md")
    _adr(tmp_path, "RepoB", "0005-b.md")
    text = (
        "One: `Projects/RepoA/docs/adrs/0005-a.md`.\n"
        "Two: `Projects/RepoB/docs/adrs/0005-b.md`.\n"
        "Per ADR-0005.\n"
    )
    missing = find_unresolved_adr_references(text, projects_root=tmp_path)
    assert len(missing) == 1, missing
    assert missing[0].startswith("  - ADR-0005 (line 3)")
    assert "RepoA, RepoB" in missing[0]
    assert "cannot be placed" in missing[0]


def test_an_adr_missing_from_the_repository_the_text_names_fails(tmp_path: Path):
    """The named repository is searched, and the default is not consulted."""
    _adr(tmp_path, "AssemblyZero", "0007-elsewhere.md")
    text = "Per ADR-0007, `Projects/OtherRepo/docs/adrs/0007-gone.md`.\n"
    missing = find_unresolved_adr_references(text, projects_root=tmp_path)
    assert len(missing) == 1, missing
    assert "ADR-0007 (line 1)" in missing[0]
    assert str(tmp_path / "OtherRepo" / "docs" / "adrs") in missing[0]

"""Acceptance tests for Office owner-file ignore coverage (#1912).

IEEE-IC25-004 committed three Word owner files when a directory was added
wholesale while documents were open. Word, Excel and PowerPoint create a `~$`
companion for EVERY open document and orphan it whenever the app or machine
dies uncleanly; an orphan looks like ordinary content to `git add <dir>`, and
once tracked it churns on every open and close.

Scope was ruled narrow on 2026-08-02: exactly two patterns, no general
heuristics. A conservative list that never false-positives beats a clever one
that teaches people to bypass the guard.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

OWNER_PATTERNS = ("~$*", ".~lock.*#")

IGNORED_SAMPLES = ("~$x.docx", "~$budget.xlsx", ".~lock.foo.docx#")
TRACKED_SAMPLES = ("document.docx", "budget.xlsx", "notes.md", "lock.docx")


def _scaffolded_repo(tmp_path: Path) -> Path:
    """A repo carrying only the scaffolder's own .gitignore."""
    import new_repo

    repo = tmp_path / "scaffolded"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], capture_output=True)
    new_repo.create_gitignore(repo)
    return repo


def _check_ignore(repo: Path, path: str) -> bool:
    """Is `path` ignored by THIS repo's own rules?

    `core.excludesfile` is neutralised deliberately. This machine's global
    gitignore already carries both patterns, so without this every assertion
    below would pass even if the scaffolder template were empty -- the test
    would be measuring the machine rather than the artifact under test.
    """
    result = subprocess.run(
        ["git", "-c", "core.excludesfile=", "-C", str(repo), "check-ignore", "-q", path],
        capture_output=True,
    )
    return result.returncode == 0


# --- "the scaffolder template asserts both patterns present" ------------


def test_scaffolder_template_carries_both_patterns(tmp_path):
    repo = _scaffolded_repo(tmp_path)
    content = (repo / ".gitignore").read_text(encoding="utf-8")

    for pattern in OWNER_PATTERNS:
        assert pattern in content, f"{pattern} missing from the scaffolder template"


def test_the_template_explains_why(tmp_path):
    """Two bare globs invite a later cleanup to delete them as noise."""
    repo = _scaffolded_repo(tmp_path)
    content = (repo / ".gitignore").read_text(encoding="utf-8")
    index = content.index("~$*")
    preamble = content[max(0, index - 700):index]
    assert "#1912" in preamble
    assert "Word" in preamble or "Office" in preamble


def test_the_list_stays_narrow(tmp_path):
    """Scope ruling 2026-08-02: exactly these two, no general heuristics."""
    repo = _scaffolded_repo(tmp_path)
    content = (repo / ".gitignore").read_text(encoding="utf-8")

    index = content.index("~$*")
    block = content[index : index + 60]
    assert "*.tmp" not in block, (
        "a clever list that false-positives teaches people to bypass the guard"
    )


# --- "check-ignore in a fresh scaffolded repo" --------------------------


@pytest.mark.parametrize("name", IGNORED_SAMPLES)
def test_owner_files_are_ignored_in_a_fresh_scaffolded_repo(tmp_path, name):
    assert _check_ignore(_scaffolded_repo(tmp_path), name), f"{name} should be ignored"


@pytest.mark.parametrize("name", TRACKED_SAMPLES)
def test_ordinary_documents_are_not_ignored(tmp_path, name):
    assert not _check_ignore(_scaffolded_repo(tmp_path), name), (
        f"{name} is ordinary content and must remain trackable"
    )


def test_an_owner_file_in_a_subdirectory_is_also_ignored(tmp_path):
    repo = _scaffolded_repo(tmp_path)
    assert _check_ignore(repo, "docs/~$25-004-02-v6k.docx"), (
        "the IEEE-IC25-004 case was exactly this shape"
    )


def test_the_guard_would_have_caught_the_original_incident(tmp_path):
    """The three files IEEE-IC25-004 actually committed."""
    repo = _scaffolded_repo(tmp_path)
    for name in (
        "docs/~$25-004-02-v6k.docx",
        "docs/~$25-004-03-v2a.docx",
        "docs/~$25-004-01-v9z.docx",
    ):
        assert _check_ignore(repo, name)


# --- the machine-level coverage (part 1) --------------------------------


GLOBAL_IGNORE = Path("C:/Users/mcwiz/.gitignore_global")


@pytest.mark.skipif(not GLOBAL_IGNORE.is_file(), reason="fleet global gitignore absent")
def test_the_fleet_global_gitignore_also_carries_both_patterns():
    """Part 1 of the issue: every existing repo fixed at once, no per-repo PR."""
    content = GLOBAL_IGNORE.read_text(encoding="utf-8")
    for pattern in OWNER_PATTERNS:
        assert pattern in content, f"{pattern} missing from the fleet global gitignore"

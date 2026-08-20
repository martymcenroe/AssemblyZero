"""Tests for tools/audit_gitignore_drift.py (#1618).

What is worth testing here is not "does it find missing lines" -- that is a set
difference. It is the three judgements that decide whether the report is worth
reading: that cosmetic template edits do not register as drift, that a repo's own
extra patterns are never reported, and that an ignored `data-g/` is caught no
matter which layer the rule came from.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from audit_gitignore_drift import (  # noqa: E402
    audit_repo,
    backfill,
    ignores_data_g,
    patterns,
)


class TestPatternExtraction:
    def test_drops_comments_and_blanks(self):
        assert patterns("# a comment\n\n*.log\n\n# another\nbuild\n") == ["*.log", "build"]

    def test_normalises_trailing_slash(self):
        """`node_modules/` and `node_modules` are one intent, not two. Reporting
        the slash variant as missing is a false alarm."""
        assert patterns("node_modules/\n") == patterns("node_modules\n") == ["node_modules"]

    def test_preserves_negations(self):
        """`!data-dl/README.md` is load-bearing -- dropping it would make the
        audit tell every repo to add an ignore that swallows its own README."""
        assert "!data-dl/README.md" in patterns("data-dl/*\n!data-dl/README.md\n")

    def test_comment_rewording_is_not_drift(self):
        before = "# old wording\n*.log\nbuild/\n"
        after = "# completely different wording\n#\n*.log\n\nbuild/\n"
        assert patterns(before) == patterns(after)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


class TestDriftDetection:
    def test_missing_pattern_is_reported(self, repo):
        (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        row = audit_repo(repo, ["*.log", "build", "*.bak"])
        assert row["missing"] == ["build", "*.bak"]

    def test_extra_local_patterns_are_never_reported(self, repo):
        """A repo carrying rules the template does not know about is normal.
        Flagging them would cry wolf on every repo and train the reader to
        ignore the output."""
        (repo / ".gitignore").write_text("*.log\nsomething-local/\n", encoding="utf-8")
        row = audit_repo(repo, ["*.log"])
        assert row["missing"] == []

    def test_absent_gitignore_is_flagged_not_crashed(self, repo):
        row = audit_repo(repo, ["*.log"])
        assert row["has_gitignore"] is False
        assert row["missing"] == ["*.log"]

    def test_dirty_tree_is_recorded(self, repo):
        (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        (repo / "untracked.txt").write_text("x", encoding="utf-8")
        assert audit_repo(repo, ["*.log"])["dirty"] is True


class TestDataGTrap:
    def test_clean_repo_does_not_ignore_data_g(self, repo):
        (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        assert ignores_data_g(repo) is False

    def test_data_star_glob_is_caught(self, repo):
        """The specific mistake: `data-*/` reads as tidy and silently stops
        `data-g/` being tracked. Nothing else in the fleet would notice."""
        (repo / ".gitignore").write_text("data/\ndata-*/\n", encoding="utf-8")
        assert ignores_data_g(repo) is True

    def test_explicit_data_g_rule_is_caught(self, repo):
        (repo / ".gitignore").write_text("data-g/\n", encoding="utf-8")
        assert ignores_data_g(repo) is True


class TestBackfill:
    def test_appends_without_touching_existing_lines(self, repo):
        original = "# my own header\n*.log\nlocal-thing/\n"
        (repo / ".gitignore").write_text(original, encoding="utf-8")
        backfill(repo, ["*.bak", "*.parked-*"], "2026-08-20")
        text = (repo / ".gitignore").read_text(encoding="utf-8")
        assert text.startswith(original), "existing content must be untouched"
        assert "*.bak" in text and "*.parked-*" in text
        assert "2026-08-20" in text, "the appended block must be dated"

    def test_never_removes_a_pattern(self, repo):
        (repo / ".gitignore").write_text("keep-me/\n", encoding="utf-8")
        backfill(repo, ["*.bak"], "2026-08-20")
        assert "keep-me" in patterns((repo / ".gitignore").read_text(encoding="utf-8"))

    def test_handles_file_with_no_trailing_newline(self, repo):
        (repo / ".gitignore").write_text("*.log", encoding="utf-8")
        backfill(repo, ["*.bak"], "2026-08-20")
        got = patterns((repo / ".gitignore").read_text(encoding="utf-8"))
        assert got == ["*.log", "*.bak"], "a missing final newline must not fuse two patterns"

    def test_backfilled_file_still_parses_to_the_union(self, repo):
        (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        backfill(repo, ["*.bak", "build"], "2026-08-20")
        assert set(patterns((repo / ".gitignore").read_text(encoding="utf-8"))) == {"*.log", "*.bak", "build"}


class TestAgainstTheRealTemplate:
    def test_template_parses_and_carries_the_data_dl_pair(self):
        from new_repo import GITIGNORE_TEMPLATE
        pats = patterns(GITIGNORE_TEMPLATE)
        assert "data-dl/*" in pats
        assert "!data-dl/README.md" in pats

    def test_template_does_not_ignore_data_g(self, repo):
        """Guards the trap at its source: if anyone ever 'tidies' the template
        into a data-*/ glob, this fails before it reaches 100 repos."""
        from new_repo import create_gitignore
        create_gitignore(repo)
        assert ignores_data_g(repo) is False

    def test_a_repo_scaffolded_now_shows_zero_drift(self, repo):
        from new_repo import GITIGNORE_TEMPLATE, create_gitignore
        create_gitignore(repo)
        row = audit_repo(repo, patterns(GITIGNORE_TEMPLATE))
        assert row["missing"] == [], "the scaffolder's own output must be drift-free"

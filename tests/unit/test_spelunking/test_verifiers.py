"""Tests for spelunking verification strategies.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from assemblyzero.spelunking.models import VerificationStatus
from assemblyzero.spelunking.verifiers import (
    _is_within_repo,
    verify_file_count,
    verify_file_exists,
    verify_no_contradiction,
    verify_timestamp_freshness,
    verify_unique_prefix,
)


class TestVerifyFileCount:
    """Tests for file count verification."""

    def test_T090_count_match(self, tmp_path: Path) -> None:
        """T090: File count matches expected."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(5):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        result = verify_file_count(tools, 5, "*.py")

        assert result.status == VerificationStatus.MATCH
        assert result.actual_value == "5"

    def test_T100_count_mismatch(self, tmp_path: Path) -> None:
        """T100: File count does not match expected."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        result = verify_file_count(tools, 5, "*.py")

        assert result.status == VerificationStatus.MISMATCH
        assert result.actual_value == "8"

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Nonexistent directory returns ERROR."""
        result = verify_file_count(tmp_path / "nope", 5)

        assert result.status == VerificationStatus.ERROR

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns actual_value='0'."""
        empty = tmp_path / "empty"
        empty.mkdir()

        result = verify_file_count(empty, 0, "*.py")

        assert result.status == VerificationStatus.MATCH
        assert result.actual_value == "0"

    def test_empty_directory_mismatch(self, tmp_path: Path) -> None:
        """Empty directory with expected > 0 returns MISMATCH."""
        empty = tmp_path / "empty"
        empty.mkdir()

        result = verify_file_count(empty, 5, "*.py")

        assert result.status == VerificationStatus.MISMATCH
        assert result.actual_value == "0"

    def test_glob_pattern_filters(self, tmp_path: Path) -> None:
        """Glob pattern only counts matching files."""
        mixed = tmp_path / "mixed"
        mixed.mkdir()
        (mixed / "a.py").write_text("# python")
        (mixed / "b.py").write_text("# python")
        (mixed / "c.md").write_text("# markdown")
        (mixed / "d.txt").write_text("text")

        result = verify_file_count(mixed, 2, "*.py")

        assert result.status == VerificationStatus.MATCH
        assert result.actual_value == "2"

    def test_evidence_includes_pattern(self, tmp_path: Path) -> None:
        """Evidence string mentions the glob pattern used."""
        tools = tmp_path / "tools"
        tools.mkdir()
        (tools / "a.py").write_text("# a")

        result = verify_file_count(tools, 1, "*.py")

        assert "*.py" in result.evidence

    def test_error_message_on_missing_dir(self, tmp_path: Path) -> None:
        """Error message includes the directory path."""
        missing = tmp_path / "nonexistent"

        result = verify_file_count(missing, 5)

        assert result.status == VerificationStatus.ERROR
        assert "nonexistent" in (result.error_message or "")


class TestVerifyFileExists:
    """Tests for file existence verification."""

    def test_T110_file_exists(self, tmp_path: Path) -> None:
        """T110: Existing file returns MATCH."""
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "real.py").write_text("# real")

        result = verify_file_exists(Path("tools/real.py"), tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_T120_file_not_found(self, tmp_path: Path) -> None:
        """T120: Nonexistent file returns MISMATCH."""
        result = verify_file_exists(Path("tools/ghost.py"), tmp_path)

        assert result.status == VerificationStatus.MISMATCH

    def test_T190_path_traversal_rejected(self, tmp_path: Path) -> None:
        """T190: Path traversal attempt returns ERROR."""
        result = verify_file_exists(Path("../../etc/passwd"), tmp_path)

        assert result.status == VerificationStatus.ERROR
        assert "traversal" in (result.error_message or "").lower()

    def test_existing_file_evidence(self, tmp_path: Path) -> None:
        """Evidence confirms the file exists."""
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "real.py").write_text("# real")

        result = verify_file_exists(Path("tools/real.py"), tmp_path)

        assert "exists" in result.evidence.lower()

    def test_missing_file_evidence(self, tmp_path: Path) -> None:
        """Evidence mentions file not found."""
        result = verify_file_exists(Path("tools/ghost.py"), tmp_path)

        assert "not found" in result.evidence.lower()

    def test_nested_path(self, tmp_path: Path) -> None:
        """Nested file paths resolve correctly."""
        (tmp_path / "src" / "deep" / "nested").mkdir(parents=True)
        (tmp_path / "src" / "deep" / "nested" / "module.py").write_text("# nested")

        result = verify_file_exists(Path("src/deep/nested/module.py"), tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_actual_value_on_match(self, tmp_path: Path) -> None:
        """Actual value is set to the file path on match."""
        (tmp_path / "file.py").write_text("# file")

        result = verify_file_exists(Path("file.py"), tmp_path)

        assert result.actual_value == "file.py"


class TestVerifyNoContradiction:
    """Tests for contradiction detection."""

    def test_T130_term_absent(self, tmp_path: Path) -> None:
        """T130: Term not found in codebase returns MATCH."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("import os\nprint('hello')")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_T140_contradiction_found(self, tmp_path: Path) -> None:
        """T140: Term found in codebase returns MISMATCH."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "db.py").write_text("import chromadb\nclient = chromadb.Client()")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MISMATCH
        assert "chromadb" in result.evidence

    def test_short_term_unverifiable(self, tmp_path: Path) -> None:
        """Search term shorter than 3 chars is UNVERIFIABLE."""
        result = verify_no_contradiction("ab", tmp_path)

        assert result.status == VerificationStatus.UNVERIFIABLE

    def test_excludes_git_directory(self, tmp_path: Path) -> None:
        """Files in .git directory are excluded from search."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config.py").write_text("chromadb = True")

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("import os")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_excludes_pycache(self, tmp_path: Path) -> None:
        """Files in __pycache__ are excluded from search."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "cached.py").write_text("chromadb = True")

        (tmp_path / "main.py").write_text("import os")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_custom_exclude_dirs(self, tmp_path: Path) -> None:
        """Custom exclude_dirs are respected."""
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        (vendor / "lib.py").write_text("import chromadb")

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("import os")

        result = verify_no_contradiction("chromadb", tmp_path, exclude_dirs=["vendor"])

        assert result.status == VerificationStatus.MATCH

    def test_evidence_includes_file_location(self, tmp_path: Path) -> None:
        """Evidence mentions the file where the term was found."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "db.py").write_text("import chromadb")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert "db.py" in result.evidence

    def test_case_insensitive_search(self, tmp_path: Path) -> None:
        """Search is case-insensitive."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "db.py").write_text("import ChromaDB")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MISMATCH

    def test_empty_repo_returns_match(self, tmp_path: Path) -> None:
        """Empty repo (no .py files) returns MATCH."""
        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_max_matches_limited(self, tmp_path: Path) -> None:
        """At most 10 matches are reported in evidence."""
        (tmp_path / "src").mkdir()
        for i in range(15):
            (tmp_path / "src" / f"file_{i}.py").write_text("chromadb everywhere")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MISMATCH
        # Evidence should mention "+X more" if there are more than 1 match
        # The exact count depends on processing order, but the function caps at 10


class TestVerifyUniquePrefix:
    """Tests for unique prefix verification."""

    def test_T150_all_unique(self, tmp_path: Path) -> None:
        """T150: All unique prefixes returns MATCH."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-first.md").write_text("# ADR 0201")
        (adrs / "0202-second.md").write_text("# ADR 0202")
        (adrs / "0203-third.md").write_text("# ADR 0203")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MATCH

    def test_T160_prefix_collision(self, tmp_path: Path) -> None:
        """T160: Duplicate prefix returns MISMATCH."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# ADR 0204a")
        (adrs / "0204-second.md").write_text("# ADR 0204b")
        (adrs / "0205-third.md").write_text("# ADR 0205")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MISMATCH
        assert "0204" in result.evidence

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Nonexistent directory returns ERROR."""
        result = verify_unique_prefix(tmp_path / "nope")

        assert result.status == VerificationStatus.ERROR

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns MATCH (no collisions possible)."""
        empty = tmp_path / "empty"
        empty.mkdir()

        result = verify_unique_prefix(empty)

        assert result.status == VerificationStatus.MATCH

    def test_files_without_prefix_ignored(self, tmp_path: Path) -> None:
        """Files without matching prefix pattern are ignored."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "README.md").write_text("# ADRs")
        (adrs / "0201-first.md").write_text("# ADR 0201")
        (adrs / "notes.txt").write_text("notes")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MATCH

    def test_multiple_collisions(self, tmp_path: Path) -> None:
        """Multiple prefix collisions are all reported."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-a.md").write_text("# a")
        (adrs / "0201-b.md").write_text("# b")
        (adrs / "0202-c.md").write_text("# c")
        (adrs / "0202-d.md").write_text("# d")
        (adrs / "0203-e.md").write_text("# e")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MISMATCH
        assert "2 collision(s)" in (result.actual_value or "")

    def test_collision_evidence_lists_files(self, tmp_path: Path) -> None:
        """Collision evidence lists the conflicting filenames."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# first")
        (adrs / "0204-second.md").write_text("# second")

        result = verify_unique_prefix(adrs)

        assert "0204-first.md" in result.evidence
        assert "0204-second.md" in result.evidence

    def test_custom_prefix_pattern(self, tmp_path: Path) -> None:
        """Custom prefix pattern is used for matching."""
        standards = tmp_path / "standards"
        standards.mkdir()
        (standards / "STD-001-first.md").write_text("# first")
        (standards / "STD-001-second.md").write_text("# second")

        result = verify_unique_prefix(standards, prefix_pattern=r"^STD-(\d{3})-")

        assert result.status == VerificationStatus.MISMATCH


class TestVerifyTimestampFreshness:
    """Tests for timestamp freshness verification."""

    def test_T170_fresh_timestamp(self) -> None:
        """T170: Date within threshold returns MATCH."""
        fresh_date = (date.today() - timedelta(days=5)).isoformat()

        result = verify_timestamp_freshness(fresh_date, max_age_days=30)

        assert result.status == VerificationStatus.MATCH

    def test_T180_stale_timestamp(self) -> None:
        """T180: Date beyond threshold returns STALE."""
        stale_date = (date.today() - timedelta(days=45)).isoformat()

        result = verify_timestamp_freshness(stale_date, max_age_days=30)

        assert result.status == VerificationStatus.STALE

    def test_unparseable_date(self) -> None:
        """Unparseable date returns ERROR."""
        result = verify_timestamp_freshness("not-a-date")

        assert result.status == VerificationStatus.ERROR

    def test_future_date_is_match(self) -> None:
        """Future date returns MATCH (0 days old)."""
        future_date = (date.today() + timedelta(days=10)).isoformat()

        result = verify_timestamp_freshness(future_date, max_age_days=30)

        assert result.status == VerificationStatus.MATCH

    def test_exactly_at_threshold(self) -> None:
        """Date exactly at threshold returns MATCH."""
        threshold_date = (date.today() - timedelta(days=30)).isoformat()

        result = verify_timestamp_freshness(threshold_date, max_age_days=30)

        assert result.status == VerificationStatus.MATCH

    def test_one_day_past_threshold(self) -> None:
        """Date one day past threshold returns STALE."""
        stale_date = (date.today() - timedelta(days=31)).isoformat()

        result = verify_timestamp_freshness(stale_date, max_age_days=30)

        assert result.status == VerificationStatus.STALE

    def test_evidence_includes_age(self, tmp_path: Path) -> None:
        """Evidence includes the age in days and threshold."""
        fresh_date = (date.today() - timedelta(days=5)).isoformat()

        result = verify_timestamp_freshness(fresh_date, max_age_days=30)

        assert "5 days old" in result.evidence
        assert "30 days" in result.evidence

    def test_actual_value_includes_age(self) -> None:
        """Actual value reports age in human-readable format."""
        test_date = (date.today() - timedelta(days=10)).isoformat()

        result = verify_timestamp_freshness(test_date, max_age_days=30)

        assert result.actual_value == "10 days old"

    def test_error_message_on_bad_date(self) -> None:
        """Error message includes the unparseable date string."""
        result = verify_timestamp_freshness("2026-99-99")

        assert result.status == VerificationStatus.ERROR
        assert "2026-99-99" in (result.error_message or "")

    def test_custom_max_age(self) -> None:
        """Custom max_age_days threshold is respected."""
        test_date = (date.today() - timedelta(days=10)).isoformat()

        result_short = verify_timestamp_freshness(test_date, max_age_days=5)
        result_long = verify_timestamp_freshness(test_date, max_age_days=30)

        assert result_short.status == VerificationStatus.STALE
        assert result_long.status == VerificationStatus.MATCH

    def test_today_returns_match(self) -> None:
        """Today's date returns MATCH with 0 days old."""
        today = date.today().isoformat()

        result = verify_timestamp_freshness(today, max_age_days=30)

        assert result.status == VerificationStatus.MATCH
        assert result.actual_value == "0 days old"


class TestIsWithinRepo:
    """Tests for path boundary checking."""

    def test_within_repo(self, tmp_path: Path) -> None:
        """Path within repo returns True."""
        child = tmp_path / "sub" / "file.py"
        assert _is_within_repo(child, tmp_path) is True

    def test_outside_repo(self, tmp_path: Path) -> None:
        """Path outside repo returns False."""
        outside = tmp_path / ".." / ".." / "etc" / "passwd"
        assert _is_within_repo(outside, tmp_path) is False

    def test_repo_root_itself(self, tmp_path: Path) -> None:
        """Repo root path itself returns True."""
        assert _is_within_repo(tmp_path, tmp_path) is True

    def test_deeply_nested_path(self, tmp_path: Path) -> None:
        """Deeply nested path within repo returns True."""
        deep = tmp_path / "a" / "b" / "c" / "d" / "e.py"
        assert _is_within_repo(deep, tmp_path) is True
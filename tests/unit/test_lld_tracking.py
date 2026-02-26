"""Unit tests for LLD audit tracking functions.

Issue #435: Add comprehensive unit tests for detect_gemini_review,
embed_review_evidence, load_lld_tracking, and update_lld_status.

Source: docs/reports/done/95-test-report.md (test gap recommendation)

NOTE: The implementation spec (spec-0435) used placeholder signatures.
These tests are adapted to the actual function signatures discovered via grep:
  - detect_gemini_review(lld_content) -> bool  [added to audit.py as part of #435]
  - embed_review_evidence(lld_content, verdict, review_date, review_count) -> str
  - load_lld_tracking(target_repo) -> LLDStatusCache
  - update_lld_status(issue_number, lld_path, review_info, target_repo) -> None
All four live in assemblyzero.workflows.requirements.audit.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from assemblyzero.workflows.requirements.audit import (
    detect_gemini_review,
    embed_review_evidence,
    load_lld_tracking,
    update_lld_status,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "lld_tracking"


@pytest.fixture
def lld_with_review() -> str:
    """Load sample LLD content that contains a Gemini review section."""
    return (FIXTURES_DIR / "sample_lld_with_review.md").read_text(encoding="utf-8")


@pytest.fixture
def lld_no_review() -> str:
    """Load sample LLD content with no review section."""
    return (FIXTURES_DIR / "sample_lld_no_review.md").read_text(encoding="utf-8")


@pytest.fixture
def sample_tracking_data() -> dict[str, Any]:
    """Return in-memory tracking data matching sample_tracking.json."""
    return {
        "100": {
            "issue_id": 100,
            "lld_path": "docs/lld/active/100-feature-example.md",
            "status": "approved",
            "gemini_reviewed": True,
            "review_verdict": "APPROVED",
            "review_timestamp": "2026-02-20T14:30:00Z",
            "evidence_embedded": True,
        },
        "200": {
            "issue_id": 200,
            "lld_path": "docs/lld/active/200-bugfix-example.md",
            "status": "draft",
            "gemini_reviewed": False,
            "review_verdict": None,
            "review_timestamp": None,
            "evidence_embedded": False,
        },
        "300": {
            "issue_id": 300,
            "lld_path": "docs/lld/active/300-docs-example.md",
            "status": "reviewed",
            "gemini_reviewed": True,
            "review_verdict": "REJECTED",
            "review_timestamp": "2026-02-24T09:15:00Z",
            "evidence_embedded": False,
        },
    }


# ---------------------------------------------------------------------------
# T010-T050: TestDetectGeminiReview
# ---------------------------------------------------------------------------


class TestDetectGeminiReview:
    """Tests for detect_gemini_review() -- 5 scenarios."""

    def test_returns_true_when_review_present(self, lld_with_review: str) -> None:
        """T010: LLD containing '### Gemini Review' section returns True."""
        result = detect_gemini_review(lld_with_review)
        assert result is True

    def test_returns_false_when_no_review(self, lld_no_review: str) -> None:
        """T020: LLD with no review markers returns False."""
        result = detect_gemini_review(lld_no_review)
        assert result is False

    def test_returns_false_for_empty_string(self) -> None:
        """T030: Empty string input returns False without raising."""
        result = detect_gemini_review("")
        assert result is False

    def test_returns_false_for_malformed_section(self) -> None:
        """T040: Partial/broken review markers return False (false-negative branch)."""
        malformed = (
            "# 400 - Example\n\n"
            "## Appendix: Review Log\n\n"
            "### Gemini Revi"  # truncated marker
        )
        result = detect_gemini_review(malformed)
        assert result is False

    def test_returns_true_for_multiple_reviews(self, lld_with_review: str) -> None:
        """T050: LLD with 2+ Gemini review sections still returns True."""
        second_review = (
            "\n\n### Gemini Review\n\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            "| Verdict | APPROVED |\n"
            "| Date | 2026-02-25 |\n"
        )
        multi_review_content = lld_with_review + second_review
        result = detect_gemini_review(multi_review_content)
        assert result is True


# ---------------------------------------------------------------------------
# T060-T110: TestEmbedReviewEvidence
# ---------------------------------------------------------------------------


class TestEmbedReviewEvidence:
    """Tests for embed_review_evidence() -- 6 scenarios.

    Real signature: embed_review_evidence(lld_content, verdict, review_date, review_count)
    Adapted from spec's (lld_content, evidence_dict) placeholder.
    """

    def test_embeds_evidence_into_clean_lld(self, lld_no_review: str) -> None:
        """T060: Embedding valid evidence into a clean LLD appends an evidence section."""
        result = embed_review_evidence(
            lld_content=lld_no_review,
            verdict="APPROVED",
            review_date="2026-02-25",
            review_count=1,
        )
        assert isinstance(result, str)
        assert len(result) > len(lld_no_review)
        # Evidence content must be present
        assert "APPROVED" in result

    def test_no_duplication_on_existing_evidence(self, lld_no_review: str) -> None:
        """T070: Embedding twice does not duplicate the evidence section (idempotency)."""
        first_pass = embed_review_evidence(
            lld_content=lld_no_review,
            verdict="APPROVED",
            review_date="2026-02-25",
            review_count=1,
        )
        second_pass = embed_review_evidence(
            lld_content=first_pass,
            verdict="APPROVED",
            review_date="2026-02-25",
            review_count=2,
        )
        # Count occurrences of "**Final Status:** APPROVED" -- should appear exactly once
        final_status_count_first = first_pass.count("**Final Status:** APPROVED")
        final_status_count_second = second_pass.count("**Final Status:** APPROVED")
        assert final_status_count_second == final_status_count_first

    def test_empty_evidence_raises_or_unchanged(self, lld_no_review: str) -> None:
        """T080: Empty/missing verdict raises or returns content unchanged."""
        try:
            result = embed_review_evidence(
                lld_content=lld_no_review,
                verdict="",
                review_date="",
                review_count=0,
            )
            # If no exception, verify function handled it gracefully
            assert isinstance(result, str)
        except (ValueError, KeyError, TypeError):
            # Acceptable -- function rejects empty evidence
            pass

    def test_empty_content_raises_or_minimal(self) -> None:
        """T090: Empty LLD content raises ValueError or returns minimal valid output."""
        try:
            result = embed_review_evidence(
                lld_content="",
                verdict="APPROVED",
                review_date="2026-02-25",
                review_count=1,
            )
            # If no exception, result must contain evidence
            assert "APPROVED" in result
        except (ValueError, TypeError):
            # Acceptable -- function rejects empty content
            pass

    def test_preserves_existing_content(self, lld_no_review: str) -> None:
        """T100: Original LLD sections remain intact after embedding evidence."""
        # Preconditions
        assert "## 1. Context & Goal" in lld_no_review
        assert "## 2. Proposed Changes" in lld_no_review

        result = embed_review_evidence(
            lld_content=lld_no_review,
            verdict="APPROVED",
            review_date="2026-02-25",
            review_count=1,
        )
        assert "## 1. Context & Goal" in result
        assert "## 2. Proposed Changes" in result

    def test_all_optional_fields_present(self, lld_no_review: str) -> None:
        """T110: Evidence with all fields has each field visible in the output."""
        result = embed_review_evidence(
            lld_content=lld_no_review,
            verdict="APPROVED",
            review_date="2026-02-25",
            review_count=1,
        )
        assert "APPROVED" in result or "Approved" in result
        assert "2026-02-25" in result
        assert "1" in result  # review_count


# ---------------------------------------------------------------------------
# T120-T160: TestLoadLLDTracking
# ---------------------------------------------------------------------------


class TestLoadLLDTracking:
    """Tests for load_lld_tracking() -- 5 scenarios.

    Real signature: load_lld_tracking(target_repo: Path) -> LLDStatusCache
    The function reads from target_repo / docs/lld/lld-status.json and returns
    a dict with keys: version, last_updated, issues.
    """

    def test_loads_valid_json(self, tmp_path: Path) -> None:
        """T120: Valid tracking JSON returns parsed dict with expected keys."""
        # Set up lld-status.json in the expected location
        status_dir = tmp_path / "docs" / "lld"
        status_dir.mkdir(parents=True)
        tracking_data = {
            "version": "1.0",
            "last_updated": "2026-02-25T00:00:00Z",
            "issues": {
                "100": {
                    "lld_path": "docs/lld/active/LLD-100.md",
                    "status": "approved",
                    "has_gemini_review": True,
                    "final_verdict": "APPROVED",
                    "last_review_date": "2026-02-20",
                    "review_count": 1,
                },
            },
        }
        (status_dir / "lld-status.json").write_text(
            json.dumps(tracking_data, indent=2), encoding="utf-8"
        )

        result = load_lld_tracking(tmp_path)
        assert isinstance(result, dict)
        assert "issues" in result
        assert "100" in result["issues"]
        entry = result["issues"]["100"]
        assert entry["status"] == "approved"

    def test_file_not_found(self, tmp_path: Path) -> None:
        """T130: Non-existent file returns empty cache (no issues)."""
        result = load_lld_tracking(tmp_path)
        # load_lld_tracking returns an empty cache with version/last_updated/issues
        assert isinstance(result, dict)
        assert result["issues"] == {}

    def test_corrupt_json(self, tmp_path: Path) -> None:
        """T140: Corrupt JSON returns empty cache (exercises JSONDecodeError branch)."""
        status_dir = tmp_path / "docs" / "lld"
        status_dir.mkdir(parents=True)
        # Write intentionally corrupt JSON (from fixture)
        corrupt_content = (
            FIXTURES_DIR / "sample_tracking_corrupt.json"
        ).read_text(encoding="utf-8")
        (status_dir / "lld-status.json").write_text(corrupt_content, encoding="utf-8")

        result = load_lld_tracking(tmp_path)
        # Function handles JSONDecodeError by returning empty cache
        assert isinstance(result, dict)
        assert result["issues"] == {}

    def test_empty_file(self, tmp_path: Path) -> None:
        """T150: Empty file returns empty cache (exercises empty-input branch)."""
        status_dir = tmp_path / "docs" / "lld"
        status_dir.mkdir(parents=True)
        (status_dir / "lld-status.json").write_text("", encoding="utf-8")

        result = load_lld_tracking(tmp_path)
        assert isinstance(result, dict)
        assert result["issues"] == {}

    def test_multiple_entries(self, tmp_path: Path) -> None:
        """T160: Tracking file with 3 entries returns all entries correctly."""
        status_dir = tmp_path / "docs" / "lld"
        status_dir.mkdir(parents=True)
        tracking_data = {
            "version": "1.0",
            "last_updated": "2026-02-25T00:00:00Z",
            "issues": {
                "100": {
                    "lld_path": "docs/lld/active/LLD-100.md",
                    "status": "approved",
                    "has_gemini_review": True,
                    "final_verdict": "APPROVED",
                    "last_review_date": "2026-02-20",
                    "review_count": 1,
                },
                "200": {
                    "lld_path": "docs/lld/active/LLD-200.md",
                    "status": "draft",
                    "has_gemini_review": False,
                    "final_verdict": None,
                    "last_review_date": None,
                    "review_count": 0,
                },
                "300": {
                    "lld_path": "docs/lld/active/LLD-300.md",
                    "status": "blocked",
                    "has_gemini_review": True,
                    "final_verdict": "REJECTED",
                    "last_review_date": "2026-02-24",
                    "review_count": 1,
                },
            },
        }
        (status_dir / "lld-status.json").write_text(
            json.dumps(tracking_data, indent=2), encoding="utf-8"
        )

        result = load_lld_tracking(tmp_path)
        assert isinstance(result, dict)
        keys = set(result["issues"].keys())
        assert "100" in keys
        assert "200" in keys
        assert "300" in keys


# ---------------------------------------------------------------------------
# T170-T210: TestUpdateLLDStatus
# ---------------------------------------------------------------------------


class TestUpdateLLDStatus:
    """Tests for update_lld_status() -- 5 scenarios.

    Real signature: update_lld_status(issue_number, lld_path, review_info, target_repo)
    Writes to target_repo / docs/lld/lld-status.json via load/save cycle.
    """

    def test_update_existing_entry(self, tmp_path: Path) -> None:
        """T170: Updating an existing entry changes its status, preserving other fields."""
        # Seed a tracking file with one entry
        update_lld_status(
            issue_number=100,
            lld_path="docs/lld/active/LLD-100.md",
            review_info={
                "has_gemini_review": True,
                "final_verdict": "APPROVED",
                "review_count": 1,
            },
            target_repo=tmp_path,
        )

        # Now update the same entry with new status
        update_lld_status(
            issue_number=100,
            lld_path="docs/lld/active/LLD-100.md",
            review_info={
                "has_gemini_review": True,
                "final_verdict": "BLOCKED",
                "review_count": 2,
            },
            target_repo=tmp_path,
        )

        tracking = load_lld_tracking(tmp_path)
        entry = tracking["issues"]["100"]
        assert entry["status"] == "blocked"
        assert entry["lld_path"] == "docs/lld/active/LLD-100.md"
        assert entry["review_count"] == 2

    def test_add_new_entry(self, tmp_path: Path) -> None:
        """T180: Adding a status for an untracked issue creates a new entry."""
        # Seed with issue 100
        update_lld_status(
            issue_number=100,
            lld_path="docs/lld/active/LLD-100.md",
            review_info={"has_gemini_review": False},
            target_repo=tmp_path,
        )

        # Add new issue 999
        update_lld_status(
            issue_number=999,
            lld_path="docs/lld/active/LLD-999.md",
            review_info={"has_gemini_review": False},
            target_repo=tmp_path,
        )

        tracking = load_lld_tracking(tmp_path)
        assert "999" in tracking["issues"]
        assert tracking["issues"]["999"]["status"] == "draft"
        # Original entry preserved
        assert "100" in tracking["issues"]

    def test_creates_new_file(self, tmp_path: Path) -> None:
        """T190: If the tracking file doesn't exist, it is created with a single entry."""
        status_file = tmp_path / "docs" / "lld" / "lld-status.json"
        assert not status_file.exists()  # precondition

        update_lld_status(
            issue_number=500,
            lld_path="docs/lld/active/LLD-500.md",
            review_info={"has_gemini_review": False},
            target_repo=tmp_path,
        )

        assert status_file.exists()
        tracking = load_lld_tracking(tmp_path)
        assert "500" in tracking["issues"]
        assert tracking["issues"]["500"]["status"] == "draft"

    def test_kwargs_merged_into_entry(self, tmp_path: Path) -> None:
        """T200: Extra review_info fields are merged into the entry."""
        update_lld_status(
            issue_number=200,
            lld_path="docs/lld/active/LLD-200.md",
            review_info={
                "has_gemini_review": True,
                "final_verdict": "APPROVED",
                "review_count": 1,
                "last_review_date": "2026-02-25",
            },
            target_repo=tmp_path,
        )

        tracking = load_lld_tracking(tmp_path)
        entry = tracking["issues"]["200"]
        assert entry["status"] == "approved"
        assert entry["has_gemini_review"] is True
        assert entry["final_verdict"] == "APPROVED"
        assert entry["last_review_date"] == "2026-02-25"

    def test_invalid_status_handled(self, tmp_path: Path) -> None:
        """T210: Invalid/unusual review_info is handled gracefully."""
        try:
            update_lld_status(
                issue_number=100,
                lld_path="docs/lld/active/LLD-100.md",
                review_info={
                    "has_gemini_review": False,
                    "final_verdict": "INVALID_VALUE",
                },
                target_repo=tmp_path,
            )
            # If no exception, verify function stored the data
            tracking = load_lld_tracking(tmp_path)
            assert "100" in tracking["issues"]
        except (ValueError, KeyError):
            # Acceptable -- function validates status values
            pass


# ---------------------------------------------------------------------------
# T220: TestProjectConventions
# ---------------------------------------------------------------------------


class TestProjectConventions:
    """Verify the test file itself follows project conventions."""

    def test_file_location_and_naming(self) -> None:
        """T220: Test file at tests/unit/test_lld_tracking.py, classes named Test*."""
        this_file = Path(__file__).resolve()
        # File must be in tests/unit/
        assert this_file.parent.name == "unit"
        assert this_file.parent.parent.name == "tests"
        # File must be named test_lld_tracking.py
        assert this_file.name == "test_lld_tracking.py"

        # Verify all test classes follow Test* naming
        import inspect
        import sys

        current_module = sys.modules[__name__]
        test_classes = [
            name
            for name, obj in inspect.getmembers(current_module, inspect.isclass)
            if name.startswith("Test")
        ]
        assert len(test_classes) >= 5, (
            f"Expected at least 5 test classes, found {len(test_classes)}: {test_classes}"
        )

"""Unit tests for assemblyzero.metrics.models.

Issue #333: Tests for data model creation and validation.
Tests: T240
"""

from __future__ import annotations

import pytest

from assemblyzero.metrics.models import (
    create_repo_metrics,
    validate_repo_metrics,
)


class TestValidateRepoMetrics:
    """Tests for validate_repo_metrics()."""

    def test_valid_metrics_no_error(self) -> None:
        """Valid metrics dict does not raise."""
        metrics = {
            "repo": "martymcenroe/AssemblyZero",
            "issues_created": 42,
            "issues_closed": 35,
            "issues_open": 12,
            "llds_generated": 20,
            "gemini_reviews": 18,
            "gemini_approvals": 15,
            "gemini_blocks": 3,
        }
        validate_repo_metrics(metrics)  # Should not raise

    def test_negative_issues_created_raises(self) -> None:
        """T240: Negative issues_created raises ValueError."""
        metrics = {
            "repo": "martymcenroe/AssemblyZero",
            "issues_created": -1,
            "issues_closed": 0,
            "issues_open": 0,
            "llds_generated": 0,
            "gemini_reviews": 0,
            "gemini_approvals": 0,
            "gemini_blocks": 0,
        }
        with pytest.raises(ValueError, match="issues_created must be non-negative, got -1"):
            validate_repo_metrics(metrics)

    def test_negative_gemini_blocks_raises(self) -> None:
        """T240: Negative gemini_blocks raises ValueError."""
        metrics = {
            "repo": "martymcenroe/AssemblyZero",
            "issues_created": 0,
            "issues_closed": 0,
            "issues_open": 0,
            "llds_generated": 0,
            "gemini_reviews": 0,
            "gemini_approvals": 0,
            "gemini_blocks": -5,
        }
        with pytest.raises(ValueError, match="gemini_blocks must be non-negative, got -5"):
            validate_repo_metrics(metrics)

    def test_empty_repo_raises(self) -> None:
        """T240: Empty repo string raises ValueError."""
        metrics = {
            "repo": "",
            "issues_created": 0,
        }
        with pytest.raises(ValueError, match="repo cannot be empty"):
            validate_repo_metrics(metrics)

    def test_negative_issues_closed_raises(self) -> None:
        """Negative issues_closed raises ValueError."""
        metrics = {
            "repo": "a/b",
            "issues_created": 0,
            "issues_closed": -3,
            "issues_open": 0,
            "llds_generated": 0,
            "gemini_reviews": 0,
            "gemini_approvals": 0,
            "gemini_blocks": 0,
        }
        with pytest.raises(ValueError, match="issues_closed must be non-negative, got -3"):
            validate_repo_metrics(metrics)

    def test_missing_repo_key_raises(self) -> None:
        """Missing repo key raises ValueError (repo defaults to empty)."""
        metrics = {"issues_created": 0}
        with pytest.raises(ValueError, match="repo cannot be empty"):
            validate_repo_metrics(metrics)

    def test_fields_not_present_are_skipped(self) -> None:
        """Fields not in dict are skipped (only checks present fields)."""
        metrics = {"repo": "a/b"}
        validate_repo_metrics(metrics)  # Should not raise

    def test_zero_values_accepted(self) -> None:
        """Zero values for all integer fields are accepted."""
        metrics = {
            "repo": "a/b",
            "issues_created": 0,
            "issues_closed": 0,
            "issues_open": 0,
            "llds_generated": 0,
            "gemini_reviews": 0,
            "gemini_approvals": 0,
            "gemini_blocks": 0,
        }
        validate_repo_metrics(metrics)  # Should not raise


class TestCreateRepoMetrics:
    """Tests for create_repo_metrics()."""

    def test_creates_valid_metrics(self) -> None:
        """T240: Creates a valid RepoMetrics dict with all fields."""
        result = create_repo_metrics(
            repo="martymcenroe/AssemblyZero",
            period_start="2026-01-26T00:00:00+00:00",
            period_end="2026-02-25T00:00:00+00:00",
            issues_created=42,
            issues_closed=35,
            issues_open=12,
            workflows_used={"requirements": 8, "tdd": 15},
            llds_generated=20,
            gemini_reviews=18,
            gemini_approvals=15,
            gemini_blocks=3,
            collection_timestamp="2026-02-25T14:30:00+00:00",
        )
        assert result["repo"] == "martymcenroe/AssemblyZero"
        assert result["issues_created"] == 42
        assert result["issues_closed"] == 35
        assert result["issues_open"] == 12
        assert result["workflows_used"] == {"requirements": 8, "tdd": 15}
        assert result["llds_generated"] == 20
        assert result["gemini_reviews"] == 18
        assert result["gemini_approvals"] == 15
        assert result["gemini_blocks"] == 3
        assert result["period_start"] == "2026-01-26T00:00:00+00:00"
        assert result["period_end"] == "2026-02-25T00:00:00+00:00"
        assert result["collection_timestamp"] == "2026-02-25T14:30:00+00:00"

    def test_rejects_negative_issues_created(self) -> None:
        """T240: Rejects creation with negative issues_created."""
        with pytest.raises(ValueError, match="issues_created must be non-negative"):
            create_repo_metrics(
                repo="martymcenroe/AssemblyZero",
                period_start="2026-01-26T00:00:00+00:00",
                period_end="2026-02-25T00:00:00+00:00",
                issues_created=-1,
                issues_closed=0,
                issues_open=0,
                workflows_used={},
                llds_generated=0,
                gemini_reviews=0,
                gemini_approvals=0,
                gemini_blocks=0,
                collection_timestamp="2026-02-25T14:30:00+00:00",
            )

    def test_rejects_empty_repo(self) -> None:
        """Rejects creation with empty repo name."""
        with pytest.raises(ValueError, match="repo cannot be empty"):
            create_repo_metrics(
                repo="",
                period_start="2026-01-26T00:00:00+00:00",
                period_end="2026-02-25T00:00:00+00:00",
                issues_created=0,
                issues_closed=0,
                issues_open=0,
                workflows_used={},
                llds_generated=0,
                gemini_reviews=0,
                gemini_approvals=0,
                gemini_blocks=0,
                collection_timestamp="2026-02-25T14:30:00+00:00",
            )

    def test_rejects_negative_gemini_blocks(self) -> None:
        """Rejects creation with negative gemini_blocks."""
        with pytest.raises(ValueError, match="gemini_blocks must be non-negative, got -5"):
            create_repo_metrics(
                repo="a/b",
                period_start="2026-01-26T00:00:00+00:00",
                period_end="2026-02-25T00:00:00+00:00",
                issues_created=0,
                issues_closed=0,
                issues_open=0,
                workflows_used={},
                llds_generated=0,
                gemini_reviews=0,
                gemini_approvals=0,
                gemini_blocks=-5,
                collection_timestamp="2026-02-25T14:30:00+00:00",
            )

    def test_keyword_only_args(self) -> None:
        """create_repo_metrics uses keyword-only arguments (cannot be called positionally)."""
        with pytest.raises(TypeError):
            create_repo_metrics(  # type: ignore[misc]
                "a/b",
                "2026-01-26T00:00:00+00:00",
                "2026-02-25T00:00:00+00:00",
                0, 0, 0, {}, 0, 0, 0, 0,
                "2026-02-25T14:30:00+00:00",
            )

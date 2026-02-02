"""Tests for the review audit log.

Test Scenarios from LLD:
- 040: Audit entry written - All 14 required fields present
- 050: Audit tail reads correctly
- 060: Viewer formats table (covered implicitly)
"""

import json
import tempfile
from pathlib import Path

import pytest

from agentos.core.audit import (
    ReviewAuditLog,
    ReviewLogEntry,
    create_log_entry,
)


@pytest.fixture
def temp_log_path():
    """Create a temporary log file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_governance.jsonl"


class TestReviewAuditLog:
    """Tests for ReviewAuditLog class."""

    def test_040_audit_entry_has_all_required_fields(self, temp_log_path: Path):
        """Test that audit entries contain all 14 required fields."""
        audit_log = ReviewAuditLog(log_path=temp_log_path)

        entry = create_log_entry(
            node="review_lld",
            model="gemini-3-pro-preview",
            model_verified="gemini-3-pro-preview",
            issue_id=50,
            verdict="APPROVED",
            critique="LLD meets all requirements",
            tier_1_issues=[],
            raw_response='{"verdict": "APPROVED"}',
            duration_ms=5000,
            credential_used="api-key-1",
            rotation_occurred=False,
            attempts=1,
            sequence_id=1,
        )

        audit_log.log(entry)

        # Read back and verify all fields
        entries = audit_log.tail(1)
        assert len(entries) == 1

        logged_entry = entries[0]

        # Verify all 14 required fields
        required_fields = [
            "id",
            "sequence_id",
            "timestamp",
            "node",
            "model",
            "model_verified",
            "issue_id",
            "verdict",
            "critique",
            "tier_1_issues",
            "raw_response",
            "duration_ms",
            "credential_used",
            "rotation_occurred",
            "attempts",
        ]

        for field in required_fields:
            assert field in logged_entry, f"Missing required field: {field}"

        # Verify specific values
        assert logged_entry["node"] == "review_lld"
        assert logged_entry["model"] == "gemini-3-pro-preview"
        assert logged_entry["issue_id"] == 50
        assert logged_entry["verdict"] == "APPROVED"
        assert logged_entry["credential_used"] == "api-key-1"
        assert logged_entry["rotation_occurred"] is False
        assert logged_entry["attempts"] == 1

    def test_050_audit_tail_reads_correctly(self, temp_log_path: Path):
        """Test that tail returns correct number of entries in order."""
        audit_log = ReviewAuditLog(log_path=temp_log_path)

        # Write 5 entries
        for i in range(5):
            entry = create_log_entry(
                node="review_lld",
                model="gemini-3-pro-preview",
                model_verified="gemini-3-pro-preview",
                issue_id=50 + i,
                verdict="APPROVED" if i % 2 == 0 else "BLOCK",
                critique=f"Entry {i}",
                tier_1_issues=[],
                raw_response="{}",
                duration_ms=1000 * i,
                credential_used=f"key-{i}",
                rotation_occurred=False,
                attempts=1,
                sequence_id=i + 1,
            )
            audit_log.log(entry)

        # Test tail(3) returns last 3 entries
        entries = audit_log.tail(3)
        assert len(entries) == 3

        # Verify order (oldest first)
        assert entries[0]["issue_id"] == 52
        assert entries[1]["issue_id"] == 53
        assert entries[2]["issue_id"] == 54

    def test_tail_empty_log(self, temp_log_path: Path):
        """Test tail on non-existent log returns empty list."""
        audit_log = ReviewAuditLog(log_path=temp_log_path)

        entries = audit_log.tail(10)
        assert entries == []

    def test_iterator(self, temp_log_path: Path):
        """Test iterating over all entries."""
        audit_log = ReviewAuditLog(log_path=temp_log_path)

        # Write 3 entries
        for i in range(3):
            entry = create_log_entry(
                node="review_lld",
                model="gemini-3-pro-preview",
                model_verified="gemini-3-pro-preview",
                issue_id=i,
                verdict="APPROVED",
                critique=f"Entry {i}",
                tier_1_issues=[],
                raw_response="{}",
                duration_ms=1000,
                credential_used="key",
                rotation_occurred=False,
                attempts=1,
                sequence_id=i,
            )
            audit_log.log(entry)

        # Iterate and count
        all_entries = list(audit_log)
        assert len(all_entries) == 3

    def test_count(self, temp_log_path: Path):
        """Test entry counting."""
        audit_log = ReviewAuditLog(log_path=temp_log_path)

        assert audit_log.count() == 0

        # Write entries
        for i in range(3):
            entry = create_log_entry(
                node="test",
                model="test",
                model_verified="test",
                issue_id=i,
                verdict="APPROVED",
                critique="",
                tier_1_issues=[],
                raw_response="",
                duration_ms=0,
                credential_used="",
                rotation_occurred=False,
                attempts=1,
                sequence_id=i,
            )
            audit_log.log(entry)

        assert audit_log.count() == 3

    def test_140_credential_logged(self, temp_log_path: Path):
        """Test that credential_used field is properly logged."""
        audit_log = ReviewAuditLog(log_path=temp_log_path)

        entry = create_log_entry(
            node="review_lld",
            model="gemini-3-pro-preview",
            model_verified="gemini-3-pro-preview",
            issue_id=50,
            verdict="APPROVED",
            critique="Test",
            tier_1_issues=[],
            raw_response="{}",
            duration_ms=5000,
            credential_used="my-special-key",
            rotation_occurred=True,
            attempts=3,
            sequence_id=1,
        )

        audit_log.log(entry)

        entries = audit_log.tail(1)
        assert entries[0]["credential_used"] == "my-special-key"
        assert entries[0]["rotation_occurred"] is True
        assert entries[0]["attempts"] == 3


class TestCreateLogEntry:
    """Tests for create_log_entry factory function."""

    def test_creates_uuid(self):
        """Test that entry has a valid UUID."""
        entry = create_log_entry(
            node="test",
            model="test",
            model_verified="test",
            issue_id=1,
            verdict="APPROVED",
            critique="",
            tier_1_issues=[],
            raw_response="",
            duration_ms=0,
            credential_used="",
            rotation_occurred=False,
            attempts=1,
            sequence_id=0,
        )

        assert "id" in entry
        assert len(entry["id"]) == 36  # UUID format

    def test_creates_timestamp(self):
        """Test that entry has an ISO8601 timestamp."""
        entry = create_log_entry(
            node="test",
            model="test",
            model_verified="test",
            issue_id=1,
            verdict="APPROVED",
            critique="",
            tier_1_issues=[],
            raw_response="",
            duration_ms=0,
            credential_used="",
            rotation_occurred=False,
            attempts=1,
            sequence_id=0,
        )

        assert "timestamp" in entry
        assert "T" in entry["timestamp"]  # ISO8601 format

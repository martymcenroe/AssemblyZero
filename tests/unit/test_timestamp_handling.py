"""Unit tests for timestamp handling in LLD workflow.

Issue #164: LLD workflow generates future-dated timestamps (Claude hallucination)

Problem: The LLD template contains {YYYY-MM-DD HH:MM} placeholders that Claude
fills in by hallucinating dates, often resulting in future-dated timestamps.

Fix: Remove timestamp placeholders from template and inject system timestamps
programmatically during finalization.
"""

import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


class TestTemplateNoHallucinationPlaceholders:
    """Test that LLD template doesn't require Claude to hallucinate timestamps."""

    def test_template_has_no_datetime_placeholders(self):
        """LLD template should not contain {YYYY-MM-DD...} placeholders.

        These placeholders force Claude to guess timestamps, which leads to
        hallucinated dates (often future-dated or incorrect).
        """
        # Find template relative to test file
        test_dir = Path(__file__).parent.parent.parent
        template_path = test_dir / "docs" / "templates" / "0102-feature-lld-template.md"

        assert template_path.exists(), f"Template not found at {template_path}"

        content = template_path.read_text(encoding="utf-8")

        # These patterns indicate Claude needs to fill in timestamps
        hallucination_patterns = [
            r"\{YYYY-MM-DD[^}]*\}",  # Date placeholders
            r"\{HH:MM[^}]*\}",  # Time placeholders
            r"\{date\}",  # Generic date placeholder
            r"\{timestamp\}",  # Generic timestamp placeholder
        ]

        for pattern in hallucination_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert not matches, (
                f"Template contains timestamp placeholder '{matches[0]}' that "
                f"Claude would need to hallucinate. Remove and use system time."
            )


class TestReviewDateFromSystem:
    """Test that review dates come from system time, not LLM."""

    def test_save_lld_uses_current_date(self, tmp_path):
        """Review date in finalize should be current system date, not hallucinated."""
        from assemblyzero.workflows.requirements.nodes.finalize import _save_lld_file
        from assemblyzero.workflows.requirements.state import create_initial_state

        target_repo = tmp_path / "repo"
        target_repo.mkdir()
        audit_dir = target_repo / "audit"
        audit_dir.mkdir()

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path / "assemblyzero"),
            target_repo=str(target_repo),
            issue_number=42,
        )
        state["current_draft"] = "# Test LLD\n\nContent here"
        state["lld_status"] = "APPROVED"
        state["verdict_count"] = 1
        state["audit_dir"] = str(audit_dir)

        # Capture the date that gets used
        with patch(
            "assemblyzero.workflows.requirements.nodes.finalize.datetime"
        ) as mock_datetime:
            # Set a known "now" time
            fixed_now = datetime(2026, 2, 3, 14, 30, 0)
            mock_datetime.now.return_value = fixed_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = _save_lld_file(state)

        # Verify the LLD was saved
        assert result.get("error_message", "") == ""
        lld_path = Path(result.get("final_lld_path", ""))
        assert lld_path.exists()

        # Read and verify the embedded date matches our fixed time
        lld_content = lld_path.read_text(encoding="utf-8")

        # The review date should be 2026-02-03 (our mocked date)
        assert "2026-02-03" in lld_content, (
            "LLD should contain the system date (2026-02-03), not a hallucinated date"
        )

    def test_review_date_is_within_tolerance(self, tmp_path):
        """Review date should be within a few seconds of actual system time."""
        from assemblyzero.workflows.requirements.nodes.finalize import _save_lld_file
        from assemblyzero.workflows.requirements.state import create_initial_state

        target_repo = tmp_path / "repo"
        target_repo.mkdir()
        audit_dir = target_repo / "audit"
        audit_dir.mkdir()

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path / "assemblyzero"),
            target_repo=str(target_repo),
            issue_number=42,
        )
        state["current_draft"] = "# Test LLD"
        state["lld_status"] = "APPROVED"
        state["verdict_count"] = 1
        state["audit_dir"] = str(audit_dir)

        # Record time before and after
        before = datetime.now()
        result = _save_lld_file(state)
        after = datetime.now()

        lld_path = Path(result.get("final_lld_path", ""))
        lld_content = lld_path.read_text(encoding="utf-8")

        # Extract the date from the LLD (format: YYYY-MM-DD in Review Summary)
        date_match = re.search(r"\| 1 \| (\d{4}-\d{2}-\d{2}) \|", lld_content)
        assert date_match, "Could not find review date in LLD Review Summary table"

        review_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()

        # The review date should match today's date
        assert before.date() <= review_date <= after.date(), (
            f"Review date {review_date} should be between {before.date()} and {after.date()}"
        )


class TestEmbedReviewEvidenceUsesProvidedDate:
    """Test that embed_review_evidence uses the provided date, not a hardcoded one."""

    def test_uses_provided_review_date(self):
        """embed_review_evidence should use exactly the date passed to it."""
        from assemblyzero.workflows.requirements.audit import embed_review_evidence

        lld_content = "# Test LLD\n\n* **Status:** Draft"
        specific_date = "2026-02-15"  # A specific date

        result = embed_review_evidence(
            lld_content=lld_content,
            verdict="APPROVED",
            review_date=specific_date,
            review_count=1,
        )

        # The specific date should appear in the output
        assert specific_date in result, (
            f"embed_review_evidence should use the provided date '{specific_date}'"
        )

    def test_does_not_use_hardcoded_date(self):
        """Verify the function doesn't ignore the provided date."""
        from assemblyzero.workflows.requirements.audit import embed_review_evidence

        lld_content = "# Test LLD\n\n* **Status:** Draft"
        provided_date = "1999-12-31"  # Obviously wrong if hardcoded

        result = embed_review_evidence(
            lld_content=lld_content,
            verdict="APPROVED",
            review_date=provided_date,
            review_count=1,
        )

        assert provided_date in result, (
            "embed_review_evidence must use the provided date, not generate its own"
        )


class TestNoFutureDates:
    """Test that the workflow never produces future-dated timestamps."""

    def test_finalize_never_produces_future_date(self, tmp_path):
        """The finalize step should never produce a date in the future."""
        from assemblyzero.workflows.requirements.nodes.finalize import _save_lld_file
        from assemblyzero.workflows.requirements.state import create_initial_state

        target_repo = tmp_path / "repo"
        target_repo.mkdir()
        audit_dir = target_repo / "audit"
        audit_dir.mkdir()

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path / "assemblyzero"),
            target_repo=str(target_repo),
            issue_number=42,
        )
        state["current_draft"] = "# Test LLD"
        state["lld_status"] = "APPROVED"
        state["verdict_count"] = 1
        state["audit_dir"] = str(audit_dir)

        result = _save_lld_file(state)

        lld_path = Path(result.get("final_lld_path", ""))
        lld_content = lld_path.read_text(encoding="utf-8")

        # Find all dates in YYYY-MM-DD format
        date_pattern = r"\b(\d{4})-(\d{2})-(\d{2})\b"
        dates_found = re.findall(date_pattern, lld_content)

        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        for year, month, day in dates_found:
            try:
                found_date = datetime(int(year), int(month), int(day)).date()
                # Skip dates that are clearly metadata (like template version dates)
                if found_date.year < 2026:
                    continue
                assert found_date <= today, (
                    f"Found future date {found_date} in LLD. "
                    f"Today is {today}. This indicates timestamp hallucination."
                )
            except ValueError:
                pass  # Invalid date, skip

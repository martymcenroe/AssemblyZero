

```python
"""Integration tests for the full cascade hook pipeline.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution
Tests: T150 (hook exit codes), T260, T270, T280 (CLAUDE.md validation)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Validation utility ──


def validate_claude_md_cascade_rule(
    claude_md_path: str | Path,
) -> dict[str, bool]:
    """Validate that CLAUDE.md contains the required cascade prevention rule.

    Checks that the CLAUDE.md file includes an explicit instruction
    directing models to ask open-ended questions after task completion
    instead of offering numbered yes/no options.

    Args:
        claude_md_path: Path to the CLAUDE.md file.

    Returns:
        Dict with validation results.
    """
    result = {
        "rule_present": False,
        "contains_open_ended": False,
        "forbids_numbered_options": False,
        "section_correct": False,
    }

    path = Path(claude_md_path)
    if not path.exists():
        return result

    content = path.read_text(encoding="utf-8")
    content_lower = content.lower()

    # Check rule is present — look for cascade prevention section
    cascade_section_patterns = [
        r"##\s+cascade\s+prevention",
        r"##\s+.*task\s+completion\s+behavior",
        r"cascade\s+prevention",
    ]
    for pattern in cascade_section_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            result["rule_present"] = True
            break

    if not result["rule_present"]:
        return result

    # Check for open-ended phrasing
    open_ended_patterns = [
        r"what would you like",
        r"what would you like to work on",
        r"open-ended\s+question",
        r"open.ended",
    ]
    for pattern in open_ended_patterns:
        if re.search(pattern, content_lower):
            result["contains_open_ended"] = True
            break

    # Check for prohibition of numbered options
    forbid_patterns = [
        r"never\b.*numbered",
        r"never\b.*yes/no",
        r"never\b.*offer.*numbered",
        r"do\s+not\b.*numbered",
        r"do\s+not\b.*yes/no",
    ]
    for pattern in forbid_patterns:
        if re.search(pattern, content_lower):
            result["forbids_numbered_options"] = True
            break

    # Check section placement — should be a top-level ## section
    # Find where the cascade rule appears
    cascade_match = re.search(r"(##\s+cascade\s+prevention|##\s+.*task\s+completion)", content, re.IGNORECASE)
    if cascade_match:
        # Verify it's a top-level section (## not ###)
        line = cascade_match.group(0)
        if line.startswith("## ") and not line.startswith("### "):
            result["section_correct"] = True

    return result


# ── T260: CLAUDE.md contains cascade prevention rule ──


class TestClaudeMdCascadeRule:
    """T260/T270/T280: CLAUDE.md cascade prevention rule (REQ-7)."""

    def test_rule_present(self) -> None:
        """T260: CLAUDE.md contains cascade prevention rule."""
        result = validate_claude_md_cascade_rule("CLAUDE.md")
        assert result["rule_present"] is True, (
            "CLAUDE.md must contain a cascade prevention rule. "
            "Expected a section header containing 'Cascade Prevention' or 'Task Completion Behavior'."
        )

    def test_open_ended_phrasing(self) -> None:
        """T270: CLAUDE.md rule uses open-ended phrasing."""
        result = validate_claude_md_cascade_rule("CLAUDE.md")
        assert result["contains_open_ended"] is True, (
            "CLAUDE.md cascade rule must contain open-ended phrasing like "
            "'What would you like to work on next?' or reference 'open-ended question'."
        )

    def test_forbids_numbered_options(self) -> None:
        """T270: CLAUDE.md rule forbids numbered yes/no options."""
        result = validate_claude_md_cascade_rule("CLAUDE.md")
        assert result["forbids_numbered_options"] is True, (
            "CLAUDE.md cascade rule must explicitly forbid numbered yes/no options "
            "for deciding next steps."
        )

    def test_section_correct(self) -> None:
        """T280: CLAUDE.md rule is in correct section."""
        result = validate_claude_md_cascade_rule("CLAUDE.md")
        assert result["section_correct"] is True, (
            "CLAUDE.md cascade rule must be in a top-level ## section "
            "(not nested under ###)."
        )


# ── T150: Hook exit codes ──


class TestHookExitCodes:
    """T150: Hook main() exits with correct code based on detection."""

    def test_hook_allows_clean_output(self) -> None:
        """Clean model output → exit(0)."""
        hook_input = json.dumps({
            "tool_name": "bash",
            "tool_input": {"command": "echo hello"},
            "tool_output": "hello\n",
        })
        result = subprocess.run(
            [sys.executable, ".claude/hooks/post_output_cascade_check.py"],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_hook_blocks_cascade_output(self) -> None:
        """Cascade model output → exit(2)."""
        hook_input = json.dumps({
            "tool_name": "bash",
            "tool_input": {"command": "fix issue"},
            "tool_output": "I've fixed issue #42. Should I continue with issue #43?\n1. Yes, proceed\n2. No, stop here",
        })
        result = subprocess.run(
            [sys.executable, ".claude/hooks/post_output_cascade_check.py"],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 2

    def test_hook_allows_empty_output(self) -> None:
        """Empty model output → exit(0)."""
        hook_input = json.dumps({
            "tool_name": "bash",
            "tool_input": {"command": "true"},
            "tool_output": "",
        })
        result = subprocess.run(
            [sys.executable, ".claude/hooks/post_output_cascade_check.py"],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_hook_allows_permission_prompt(self) -> None:
        """Permission prompt → exit(0)."""
        hook_input = json.dumps({
            "tool_name": "bash",
            "tool_input": {"command": "git push"},
            "tool_output": "Allow bash command: git push origin main? (y/n)",
        })
        result = subprocess.run(
            [sys.executable, ".claude/hooks/post_output_cascade_check.py"],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0


# ── Full pipeline integration test ──


class TestFullPipeline:
    """Integration test: detection → action → telemetry."""

    def test_end_to_end_block(self, tmp_path: Path) -> None:
        """Full pipeline: cascade input → detection → block → log event."""
        from assemblyzero.hooks.cascade_detector import detect_cascade_risk, CascadeRiskLevel
        from assemblyzero.hooks.cascade_action import handle_cascade_detection
        from assemblyzero.telemetry.cascade_events import get_cascade_stats, log_cascade_event, create_cascade_event

        log_file = tmp_path / "cascade-events.jsonl"
        model_output = "I've fixed issue #42. Should I continue with issue #43?\n1. Yes, proceed\n2. No, stop here"

        # Step 1: Detect
        result = detect_cascade_risk(model_output)
        assert result["detected"] is True
        assert result["risk_level"] in (CascadeRiskLevel.HIGH, CascadeRiskLevel.CRITICAL)

        # Step 2: Create and log event
        event = create_cascade_event(
            result=result,
            session_id="integration-test-sess",
            model_output=model_output,
            action_taken="blocked",
        )
        log_cascade_event(event, log_path=log_file)

        # Step 3: Verify telemetry
        stats = get_cascade_stats(log_path=log_file, since_hours=1)
        assert stats["total_checks"] == 1
        assert stats["blocks"] == 1

        # Step 4: Verify logged event structure
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        parsed = json.loads(lines[0])
        assert parsed["event_type"] == "cascade_risk"
        assert parsed["auto_approve_blocked"] is True
        assert parsed["session_id"] == "integration-test-sess"

    def test_end_to_end_allow(self, tmp_path: Path) -> None:
        """Full pipeline: clean input → detection → allow."""
        from assemblyzero.hooks.cascade_detector import detect_cascade_risk
        from assemblyzero.hooks.cascade_action import handle_cascade_detection

        model_output = "I've updated the file. Here are the changes:\n- Added error handling\n- Updated tests"

        result = detect_cascade_risk(model_output)
        assert result["detected"] is False
        assert result["recommended_action"] == "allow"

        should_allow = handle_cascade_detection(
            result=result,
            session_id="integration-test-sess",
            model_output=model_output,
        )
        assert should_allow is True
```

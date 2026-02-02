# File: tools/verdict_analyzer/parser.py

```python
"""Parse verdict markdown files."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

# Define PARSER_VERSION locally to avoid circular import
PARSER_VERSION = "1.0.0"


@dataclass
class BlockingIssue:
    """A blocking issue extracted from a verdict."""

    tier: int
    category: str
    description: str


@dataclass
class VerdictRecord:
    """A parsed verdict record."""

    filepath: str
    verdict_type: str
    decision: str
    content_hash: str
    parser_version: str
    blocking_issues: list[BlockingIssue] = field(default_factory=list)


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_verdict(filepath: Path) -> VerdictRecord:
    """Parse a verdict markdown file.

    Args:
        filepath: Path to the verdict markdown file.

    Returns:
        VerdictRecord with parsed data.
    """
    content = filepath.read_text(encoding="utf-8")
    content_hash = compute_content_hash(content)

    # Determine verdict type (LLD vs Issue)
    # LLD format: "# 105 - Feature: ..." or has "## 1. Context & Goal"
    # Issue format: "# Issue #42 - ..." or has "## User Story"
    verdict_type = "lld"
    if re.search(r"^#\s*Issue\s*#\d+", content, re.MULTILINE | re.IGNORECASE):
        verdict_type = "issue"
    elif "## User Story" in content or "## Acceptance Criteria" in content:
        verdict_type = "issue"

    # Extract decision (APPROVED, BLOCKED, CONDITIONAL)
    decision = "UNKNOWN"
    decision_match = re.search(
        r"##\s*Verdict:\s*(APPROVED|BLOCKED|CONDITIONAL)", content, re.IGNORECASE
    )
    if decision_match:
        decision = decision_match.group(1).upper()

    # Extract blocking issues by tier
    blocking_issues: list[BlockingIssue] = []

    # Find the Blocking Issues section
    blocking_section_match = re.search(
        r"##\s*Blocking Issues\s*(.*?)(?=^##[^#]|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )

    if blocking_section_match:
        blocking_section = blocking_section_match.group(1)

        # Parse each tier
        for tier in [1, 2, 3]:
            tier_match = re.search(
                rf"###\s*Tier\s*{tier}\s*(.*?)(?=###\s*Tier|\Z)",
                blocking_section,
                re.DOTALL | re.IGNORECASE,
            )
            if tier_match:
                tier_content = tier_match.group(1)

                # Extract bullet points
                bullets = re.findall(r"^\s*[-*]\s*(.+)$", tier_content, re.MULTILINE)
                for bullet in bullets:
                    # Clean up the bullet text
                    desc = bullet.strip()
                    # Remove bold markers
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", desc)

                    # Infer category from description
                    category = _infer_category(desc)

                    blocking_issues.append(
                        BlockingIssue(tier=tier, category=category, description=desc)
                    )

    return VerdictRecord(
        filepath=str(filepath),
        verdict_type=verdict_type,
        decision=decision,
        content_hash=content_hash,
        parser_version=PARSER_VERSION,
        blocking_issues=blocking_issues,
    )


def _infer_category(description: str) -> str:
    """Infer category from issue description."""
    desc_lower = description.lower()

    category_keywords = {
        "security": ["security", "vulnerability", "injection", "xss", "csrf", "auth"],
        "testing": ["test", "coverage", "unit test", "integration"],
        "error_handling": ["error", "exception", "handling", "try", "catch"],
        "documentation": ["doc", "comment", "readme", "example"],
        "performance": ["performance", "slow", "optimize", "cache"],
        "logging": ["log", "logging", "debug", "trace"],
        "validation": ["valid", "input", "sanitize", "check"],
        "architecture": ["architecture", "design", "pattern", "structure"],
    }

    for category, keywords in category_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            return category

    return "general"
```
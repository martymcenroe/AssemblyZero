"""Parse verdict markdown files."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

# Define PARSER_VERSION locally to avoid circular import
# Bump version when parser logic changes to trigger re-parsing
PARSER_VERSION = "1.4.0"


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
    # Detection methods (in priority order):
    # 1. Header: "# Issue Review:" vs "# Governance Verdict:" / "# LLD Review:"
    # 2. Path: contains "-lld" → LLD, otherwise → issue
    verdict_type = "lld"  # default

    # Check header first (most reliable)
    if re.search(r"^#\s*Issue\s+Review:", content, re.MULTILINE | re.IGNORECASE):
        verdict_type = "issue"
    elif re.search(r"^#\s*(Governance\s+Verdict|LLD\s+Review):", content, re.MULTILINE | re.IGNORECASE):
        verdict_type = "lld"
    # Fallback to path-based detection
    elif "-lld" in str(filepath).lower():
        verdict_type = "lld"
    elif "-issue" in str(filepath).lower() or "test-" in str(filepath).lower():
        verdict_type = "issue"

    # Extract decision from multiple possible formats:
    # Format 1: # Governance Verdict: APPROVED
    # Format 2: **Verdict: REJECTED**
    # Format 3: [x] **APPROVED** - Ready to enter backlog (checkbox-style)
    decision = "UNKNOWN"

    # Try header format first: # Governance Verdict: APPROVED
    decision_match = re.search(
        r"#\s*(?:Governance\s+)?Verdict:\s*(APPROVED|BLOCK(?:ED)?|CONDITIONAL)",
        content,
        re.IGNORECASE,
    )
    if decision_match:
        raw_decision = decision_match.group(1).upper()
        decision = "BLOCKED" if raw_decision == "BLOCK" else raw_decision
    else:
        # Try bold format: **Verdict: REJECTED**
        bold_match = re.search(
            r"\*\*Verdict:\s*(APPROVED|REJECTED|BLOCK(?:ED)?|CONDITIONAL)\*?\*?",
            content,
            re.IGNORECASE,
        )
        if bold_match:
            raw_decision = bold_match.group(1).upper()
            decision = "BLOCKED" if raw_decision in ("BLOCK", "REJECTED") else raw_decision
        else:
            # Try checkbox format: [x] **APPROVED** or [x] **REVISE**
            checkbox_match = re.search(
                r"\[x\]\s*\*\*(APPROVED|REVISE|DISCUSS|REJECTED|BLOCK(?:ED)?)\*\*",
                content,
                re.IGNORECASE,
            )
            if checkbox_match:
                raw_decision = checkbox_match.group(1).upper()
                # Map various outcomes to our standard decisions
                if raw_decision == "APPROVED":
                    decision = "APPROVED"
                elif raw_decision in ("REVISE", "DISCUSS", "REJECTED", "BLOCK", "BLOCKED"):
                    decision = "BLOCKED"

    # Extract blocking issues by tier
    # Supports two formats:
    # Format 1 (Issue Review): ## Tier 1: BLOCKING Issues / ### Security
    # Format 2 (Legacy): ## Blocking Issues / ### Tier 1
    blocking_issues: list[BlockingIssue] = []

    # Try Format 1: ## Tier N: BLOCKING/HIGH PRIORITY Issues
    tier_patterns = [
        (1, r"##\s*Tier\s*1[:\s]+BLOCKING\s+Issues?\s*(.*?)(?=^##\s|\Z)"),
        (2, r"##\s*Tier\s*2[:\s]+HIGH\s+PRIORITY\s+Issues?\s*(.*?)(?=^##\s|\Z)"),
        (3, r"##\s*Tier\s*3[:\s]+SUGGESTIONS?\s*(.*?)(?=^##\s|\Z)"),
    ]

    for tier, pattern in tier_patterns:
        tier_match = re.search(pattern, content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
        if tier_match:
            tier_content = tier_match.group(1)

            # Find category subsections (### Security, ### Quality, etc.)
            category_matches = re.findall(
                r"###\s*(\w+)\s*(.*?)(?=###\s*\w|\Z)",
                tier_content,
                re.DOTALL,
            )

            for category_name, category_content in category_matches:
                category = category_name.lower()
                # Skip "No issues found" entries
                if "no issues found" in category_content.lower():
                    continue

                # Extract bullet points with checkboxes: - [ ] or - [x]
                bullets = re.findall(
                    r"^\s*-\s*\[[ x]\]\s*(.+?)(?=^\s*-\s*\[|\Z)",
                    category_content,
                    re.MULTILINE | re.DOTALL,
                )

                for bullet in bullets:
                    desc = bullet.strip()
                    # Skip empty or "No issues" entries
                    if not desc or "no issues" in desc.lower():
                        continue
                    # Remove bold markers
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", desc)
                    # Collapse whitespace
                    desc = " ".join(desc.split())

                    blocking_issues.append(
                        BlockingIssue(tier=tier, category=category, description=desc)
                    )

    # Try Format 2 (Legacy): ## Blocking Issues / ### Tier N
    if not blocking_issues:
        blocking_section_match = re.search(
            r"##\s*Blocking Issues\s*(.*?)(?=^##[^#]|\Z)",
            content,
            re.MULTILINE | re.DOTALL,
        )

        if blocking_section_match:
            blocking_section = blocking_section_match.group(1)

            for tier in [1, 2, 3]:
                tier_match = re.search(
                    rf"###\s*Tier\s*{tier}\s*(.*?)(?=###\s*Tier|\Z)",
                    blocking_section,
                    re.DOTALL | re.IGNORECASE,
                )
                if tier_match:
                    tier_content = tier_match.group(1)

                    bullets = re.findall(r"^\s*[-*]\s*(.+)$", tier_content, re.MULTILINE)
                    for bullet in bullets:
                        desc = bullet.strip()
                        desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", desc)
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
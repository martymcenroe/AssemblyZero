# File: tools/verdict_analyzer/parser.py

```python
"""Parse verdict markdown files (LLD + Issue formats)."""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Increment this when parser logic changes to trigger re-parsing
PARSER_VERSION = "1.0.0"


@dataclass
class BlockingIssue:
    """Represents a blocking issue from a verdict."""

    tier: int
    category: str
    description: str

    def __post_init__(self):
        """Validate tier is 1, 2, or 3."""
        if self.tier not in (1, 2, 3):
            raise ValueError(f"Tier must be 1, 2, or 3, got {self.tier}")


@dataclass
class VerdictRecord:
    """Represents a parsed verdict file."""

    file_path: str
    content_hash: str
    verdict_type: str  # 'lld' or 'issue'
    title: str
    verdict: str  # 'APPROVED', 'BLOCKED', etc.
    blocking_issues: list[BlockingIssue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    parser_version: str = PARSER_VERSION

    def __post_init__(self):
        """Validate verdict_type."""
        if self.verdict_type not in ("lld", "issue"):
            raise ValueError(f"verdict_type must be 'lld' or 'issue', got {self.verdict_type}")


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_verdict(file_path: Path, content: Optional[str] = None) -> VerdictRecord:
    """Parse a verdict markdown file.

    Args:
        file_path: Path to the verdict file
        content: Optional content string (if not provided, reads from file)

    Returns:
        VerdictRecord with parsed data
    """
    if content is None:
        content = file_path.read_text(encoding="utf-8")

    content_hash = compute_content_hash(content)

    # Determine verdict type from content or filename
    verdict_type = _detect_verdict_type(file_path, content)

    # Parse title
    title = _extract_title(content)

    # Parse verdict status
    verdict = _extract_verdict_status(content)

    # Parse blocking issues
    blocking_issues = extract_blocking_issues(content)

    # Parse recommendations
    recommendations = _extract_recommendations(content)

    logger.debug(f"Parsed verdict: {file_path}")

    return VerdictRecord(
        file_path=str(file_path),
        content_hash=content_hash,
        verdict_type=verdict_type,
        title=title,
        verdict=verdict,
        blocking_issues=blocking_issues,
        recommendations=recommendations,
        parser_version=PARSER_VERSION,
    )


def _detect_verdict_type(file_path: Path, content: str) -> str:
    """Detect whether this is an LLD or Issue verdict."""
    path_str = str(file_path).lower()
    content_lower = content.lower()

    # Check filename patterns
    if "lld" in path_str or "low-level-design" in path_str:
        return "lld"
    if "issue" in path_str:
        return "issue"

    # Check content patterns
    if "## lld" in content_lower or "low-level design" in content_lower:
        return "lld"
    if "## issue" in content_lower or "issue verdict" in content_lower:
        return "issue"

    # Default to lld if unclear
    return "lld"


def _extract_title(content: str) -> str:
    """Extract title from verdict content."""
    # Look for # Title pattern
    match = re.search(r"^#\s+(.+?)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # Look for Title: pattern
    match = re.search(r"Title:\s*(.+?)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    return "Unknown"


def _extract_verdict_status(content: str) -> str:
    """Extract verdict status (APPROVED, BLOCKED, etc.)."""
    content_upper = content.upper()

    # Look for explicit verdict patterns
    patterns = [
        r"VERDICT:\s*(APPROVED|BLOCKED|NEEDS_REVISION|PENDING)",
        r"STATUS:\s*(APPROVED|BLOCKED|NEEDS_REVISION|PENDING)",
        r"\*\*(APPROVED|BLOCKED|NEEDS_REVISION|PENDING)\*\*",
        r"##\s*VERDICT:\s*(APPROVED|BLOCKED|NEEDS_REVISION|PENDING)",
    ]

    for pattern in patterns:
        match = re.search(pattern, content_upper)
        if match:
            return match.group(1)

    # Check for verdict in content
    if "APPROVED" in content_upper:
        return "APPROVED"
    if "BLOCKED" in content_upper:
        return "BLOCKED"
    if "NEEDS_REVISION" in content_upper or "NEEDS REVISION" in content_upper:
        return "NEEDS_REVISION"

    return "UNKNOWN"


def extract_blocking_issues(content: str) -> list[BlockingIssue]:
    """Extract blocking issues from verdict content."""
    issues = []

    # Pattern for tier markers like "Tier 1:", "**Tier 2**", "[Tier 3]"
    tier_pattern = r"(?:\*\*)?(?:\[)?Tier\s*(\d)(?:\])?(?:\*\*)?[:\s]*(.+?)(?=(?:\*\*)?(?:\[)?Tier\s*\d|\Z)"

    # Also look for structured list items
    list_pattern = r"[-*]\s*(?:\*\*)?(?:\[)?Tier\s*(\d)(?:\])?(?:\*\*)?[:\s]*\[?([^\]]+)\]?\s*[-:]\s*(.+?)(?=\n[-*]|\n\n|\Z)"

    # Try structured list pattern first
    for match in re.finditer(list_pattern, content, re.IGNORECASE | re.DOTALL):
        try:
            tier = int(match.group(1))
            category = match.group(2).strip()
            description = match.group(3).strip()
            if tier in (1, 2, 3):
                issues.append(BlockingIssue(tier=tier, category=category, description=description))
        except (ValueError, IndexError):
            continue

    # If no structured items found, try the simpler pattern
    if not issues:
        # Look for section-based blocking issues
        blocking_section = re.search(
            r"(?:blocking issues|issues found)[:\s]*\n(.+?)(?=\n##|\Z)",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if blocking_section:
            section_content = blocking_section.group(1)
            for match in re.finditer(
                r"[-*]\s*\[?Tier\s*(\d)\]?\s*[-:]\s*\[?([^\]:\n]+)\]?\s*[-:]\s*(.+?)(?=\n[-*]|\Z)",
                section_content,
                re.IGNORECASE,
            ):
                try:
                    tier = int(match.group(1))
                    category = match.group(2).strip()
                    description = match.group(3).strip()
                    if tier in (1, 2, 3):
                        issues.append(BlockingIssue(tier=tier, category=category, description=description))
                except (ValueError, IndexError):
                    continue

    return issues


def _extract_recommendations(content: str) -> list[str]:
    """Extract recommendations from verdict content."""
    recommendations = []

    # Look for recommendations section
    rec_section = re.search(
        r"(?:recommendations?)[:\s]*\n(.+?)(?=\n##|\Z)",
        content,
        re.IGNORECASE | re.DOTALL,
    )

    if rec_section:
        section_content = rec_section.group(1)
        # Extract list items
        for match in re.finditer(r"[-*]\s*(.+?)(?=\n[-*]|\n\n|\Z)", section_content):
            rec = match.group(1).strip()
            if rec:
                recommendations.append(rec)

    return recommendations
```
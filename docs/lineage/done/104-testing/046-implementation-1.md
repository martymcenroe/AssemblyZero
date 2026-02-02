# File: tools/verdict_analyzer/parser.py

```python
"""Parse verdict markdown files (LLD + Issue formats)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BlockingIssue:
    """A blocking issue extracted from a verdict."""
    
    tier: int  # 1, 2, or 3
    category: str
    description: str
    raw_text: str = ""


@dataclass
class VerdictRecord:
    """A parsed verdict record."""
    
    filepath: str
    verdict_type: str  # 'lld' or 'issue'
    decision: str  # 'APPROVED', 'BLOCKED', 'NEEDS_REVISION'
    blocking_issues: list[BlockingIssue] = field(default_factory=list)
    content_hash: str = ""
    parser_version: str = ""
    repo_name: str = ""
    issue_number: Optional[int] = None
    title: str = ""
    raw_content: str = ""


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_verdict(filepath: Path, content: Optional[str] = None) -> VerdictRecord:
    """Parse a verdict markdown file.
    
    Args:
        filepath: Path to the verdict file
        content: Optional content string (if not provided, reads from filepath)
        
    Returns:
        VerdictRecord with parsed fields
    """
    from tools.verdict_analyzer import PARSER_VERSION
    
    if content is None:
        content = filepath.read_text(encoding="utf-8")
    
    content_hash = compute_content_hash(content)
    
    # Determine verdict type from content or filename
    verdict_type = _detect_verdict_type(filepath, content)
    
    # Extract decision
    decision = _extract_decision(content)
    
    # Extract blocking issues
    blocking_issues = _extract_blocking_issues(content)
    
    # Extract metadata
    repo_name = _extract_repo_name(filepath, content)
    issue_number = _extract_issue_number(filepath, content)
    title = _extract_title(content)
    
    return VerdictRecord(
        filepath=str(filepath),
        verdict_type=verdict_type,
        decision=decision,
        blocking_issues=blocking_issues,
        content_hash=content_hash,
        parser_version=PARSER_VERSION,
        repo_name=repo_name,
        issue_number=issue_number,
        title=title,
        raw_content=content,
    )


def _detect_verdict_type(filepath: Path, content: str) -> str:
    """Detect if this is an LLD or Issue verdict."""
    filename = filepath.name.lower()
    content_lower = content.lower()
    
    if "lld" in filename or "low-level design" in content_lower or "## 2. proposed changes" in content_lower:
        return "lld"
    if "issue" in filename or "## acceptance criteria" in content_lower or "## user story" in content_lower:
        return "issue"
    
    # Default based on common patterns
    if "### 2.1 files changed" in content_lower:
        return "lld"
    
    return "issue"


def _extract_decision(content: str) -> str:
    """Extract the verdict decision."""
    content_upper = content.upper()
    
    # Look for explicit verdict markers
    patterns = [
        r"(?:VERDICT|DECISION|STATUS)\s*[:=]\s*(APPROVED|BLOCKED|NEEDS[_\s]REVISION)",
        r"##\s*(APPROVED|BLOCKED|NEEDS[_\s]REVISION)",
        r"\*\*(APPROVED|BLOCKED|NEEDS[_\s]REVISION)\*\*",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            decision = match.group(1).upper().replace(" ", "_").replace("-", "_")
            if decision == "NEEDS_REVISION":
                return "NEEDS_REVISION"
            return decision
    
    # Infer from content
    if "tier 1" in content.lower() or "blocking" in content.lower():
        return "BLOCKED"
    if "approved" in content.lower():
        return "APPROVED"
    
    return "NEEDS_REVISION"


def _extract_blocking_issues(content: str) -> list[BlockingIssue]:
    """Extract blocking issues organized by tier."""
    issues = []
    
    # Pattern for tier sections
    tier_pattern = r"(?:###?\s*)?(?:Tier\s*)?(\d)\s*(?:Issues?|Blockers?)?[:\s]*\n((?:[-*]\s*.+\n?)+)"
    
    for match in re.finditer(tier_pattern, content, re.IGNORECASE):
        tier = int(match.group(1))
        items_text = match.group(2)
        
        # Extract individual items
        item_pattern = r"[-*]\s*\*?\*?([^*\n]+(?:\([^)]+\))?[^*\n]*)\*?\*?"
        for item_match in re.finditer(item_pattern, items_text):
            raw_text = item_match.group(0).strip()
            description = item_match.group(1).strip()
            category = _categorize_issue(description)
            
            issues.append(BlockingIssue(
                tier=tier,
                category=category,
                description=description,
                raw_text=raw_text,
            ))
    
    # Also look for inline blocking issues
    inline_pattern = r"(?:blocking|issue|problem):\s*(.+)"
    for match in re.finditer(inline_pattern, content, re.IGNORECASE):
        description = match.group(1).strip()
        if not any(i.description == description for i in issues):
            issues.append(BlockingIssue(
                tier=2,
                category=_categorize_issue(description),
                description=description,
                raw_text=match.group(0),
            ))
    
    return issues


def _categorize_issue(description: str) -> str:
    """Categorize an issue based on its description."""
    desc_lower = description.lower()
    
    category_keywords = {
        "security": ["security", "auth", "injection", "xss", "csrf", "vulnerability"],
        "testing": ["test", "coverage", "unit test", "integration"],
        "error_handling": ["error", "exception", "catch", "try", "handling"],
        "documentation": ["doc", "comment", "readme", "docstring"],
        "dependencies": ["dependency", "import", "package", "version"],
        "architecture": ["architecture", "design", "pattern", "structure"],
        "performance": ["performance", "speed", "optimize", "memory"],
        "validation": ["validation", "validate", "check", "verify"],
        "configuration": ["config", "setting", "environment", "env"],
        "logging": ["log", "logging", "trace", "debug"],
        "api": ["api", "endpoint", "rest", "graphql"],
    }
    
    for category, keywords in category_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            return category
    
    return "general"


def _extract_repo_name(filepath: Path, content: str) -> str:
    """Extract repository name from filepath or content."""
    # Try to extract from filepath
    parts = filepath.parts
    for i, part in enumerate(parts):
        if part in ("verdicts", "governance", "docs"):
            if i > 0:
                return parts[i - 1]
    
    # Try to extract from content
    repo_match = re.search(r"(?:repo|repository):\s*(\S+)", content, re.IGNORECASE)
    if repo_match:
        return repo_match.group(1)
    
    return filepath.parent.name


def _extract_issue_number(filepath: Path, content: str) -> Optional[int]:
    """Extract issue number from filepath or content."""
    # Try filename first
    match = re.search(r"(?:issue[-_]?)?(\d+)", filepath.stem, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Try content
    match = re.search(r"(?:issue|#)\s*(\d+)", content, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    return None


def _extract_title(content: str) -> str:
    """Extract title from content."""
    # Look for H1 header
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # Look for title field
    match = re.search(r"(?:title|subject):\s*(.+)", content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return ""
```
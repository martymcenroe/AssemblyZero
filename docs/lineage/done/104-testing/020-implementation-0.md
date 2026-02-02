# File: tools/verdict_analyzer/parser.py

```python
"""Parser module for verdict analyzer.

Parses Gemini governance verdict markdown files and extracts structured data.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

PARSER_VERSION = "1.0.0"

logger = logging.getLogger(__name__)


@dataclass
class BlockingIssue:
    """Represents a blocking issue from a verdict."""
    tier: int
    category: str
    description: str


@dataclass
class VerdictRecord:
    """Represents a parsed verdict record."""
    file_path: str
    content_hash: str
    verdict_type: str
    title: str
    verdict: str
    blocking_issues: List[BlockingIssue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    parser_version: str = PARSER_VERSION


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def extract_blocking_issues(content: str) -> List[BlockingIssue]:
    """Extract blocking issues from verdict content.
    
    Args:
        content: The markdown content containing blocking issues
        
    Returns:
        List of BlockingIssue objects
    """
    issues = []
    
    # Pattern: - [Tier N] - [Category] - Description
    # Fixed regex to properly capture category without the leading "- ["
    pattern = r'-\s*\[Tier\s*(\d+)\]\s*-\s*\[([^\]]+)\]\s*-\s*(.+?)(?:\n|$)'
    
    matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
    
    for match in matches:
        tier = int(match[0])
        category = match[1].strip()  # This should now be just "Security", not "- [Security"
        description = match[2].strip()
        
        issues.append(BlockingIssue(
            tier=tier,
            category=category,
            description=description
        ))
    
    logger.debug(f"Extracted {len(issues)} blocking issues")
    return issues


def extract_recommendations(content: str) -> List[str]:
    """Extract recommendations from verdict content."""
    recommendations = []
    
    # Find recommendations section
    rec_match = re.search(r'##\s*Recommendations:?\s*\n(.*?)(?:\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
    
    if rec_match:
        rec_section = rec_match.group(1)
        # Extract bullet points
        for line in rec_section.split('\n'):
            line = line.strip()
            if line.startswith('-'):
                rec = line[1:].strip()
                if rec:
                    recommendations.append(rec)
    
    return recommendations


def extract_verdict_status(content: str) -> str:
    """Extract verdict status (APPROVED, BLOCKED, etc.)."""
    # Look for **STATUS** pattern or Status: **STATUS**
    patterns = [
        r'\*\*(APPROVED|BLOCKED|CONDITIONAL|REJECTED)\*\*',
        r'Verdict:\s*\*\*(APPROVED|BLOCKED|CONDITIONAL|REJECTED)\*\*',
        r'Status:\s*\*\*(APPROVED|BLOCKED|CONDITIONAL|REJECTED)\*\*',
        r'VERDICT:\s*(APPROVED|BLOCKED|CONDITIONAL|REJECTED)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    return "UNKNOWN"


def extract_title(content: str) -> str:
    """Extract title from verdict content."""
    # Look for first heading
    match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Untitled Verdict"


def determine_verdict_type(content: str, file_path: Path) -> str:
    """Determine if verdict is for LLD or Issue."""
    content_lower = content.lower()
    filename_lower = str(file_path).lower()
    
    if 'lld' in content_lower or 'lld' in filename_lower:
        return 'lld'
    if 'issue' in content_lower or 'issue' in filename_lower:
        return 'issue'
    
    # Default based on content patterns
    if re.search(r'issue\s*#?\d+', content_lower):
        return 'issue'
    
    return 'lld'


def parse_verdict(file_path: Path) -> VerdictRecord:
    """Parse a verdict markdown file.
    
    Args:
        file_path: Path to the verdict markdown file
        
    Returns:
        VerdictRecord with parsed data
    """
    logger.debug(f"Parsing verdict file: {file_path}")
    
    content = file_path.read_text(encoding='utf-8')
    content_hash = compute_content_hash(content)
    
    verdict_type = determine_verdict_type(content, file_path)
    title = extract_title(content)
    verdict = extract_verdict_status(content)
    blocking_issues = extract_blocking_issues(content)
    recommendations = extract_recommendations(content)
    
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
```
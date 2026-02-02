# File: tools/verdict_analyzer/__init__.py

```python
"""Verdict Analyzer package for analyzing Gemini governance verdicts."""

from .parser import VerdictRecord, BlockingIssue, parse_verdict, PARSER_VERSION
from .database import VerdictDatabase
from .patterns import normalize_pattern, CATEGORY_TO_SECTION, extract_blocking_issues
from .template_updater import (
    parse_template_sections,
    generate_recommendations,
    atomic_write_with_backup,
    validate_template_path,
)
from .scanner import discover_repos, find_registry_path, scan_for_verdicts

__all__ = [
    "VerdictRecord",
    "BlockingIssue",
    "parse_verdict",
    "PARSER_VERSION",
    "VerdictDatabase",
    "normalize_pattern",
    "CATEGORY_TO_SECTION",
    "extract_blocking_issues",
    "parse_template_sections",
    "generate_recommendations",
    "atomic_write_with_backup",
    "validate_template_path",
    "discover_repos",
    "find_registry_path",
    "scan_for_verdicts",
]
```
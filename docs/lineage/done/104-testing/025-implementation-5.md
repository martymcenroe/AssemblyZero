# File: tools/verdict_analyzer/__init__.py

```python
"""Verdict Analyzer - Template improvement from Gemini verdicts.

This package provides tools to analyze Gemini governance verdicts,
extract blocking patterns, and improve LLD/issue templates.
"""

from .parser import VerdictRecord, BlockingIssue, parse_verdict, PARSER_VERSION
from .database import VerdictDatabase, SCHEMA_VERSION
from .patterns import normalize_pattern, CATEGORY_TO_SECTION, get_template_section
from .template_updater import Recommendation, generate_recommendations
from .scanner import discover_repos, scan_for_verdicts

__all__ = [
    "VerdictRecord",
    "BlockingIssue",
    "parse_verdict",
    "PARSER_VERSION",
    "VerdictDatabase",
    "SCHEMA_VERSION",
    "normalize_pattern",
    "CATEGORY_TO_SECTION",
    "get_template_section",
    "Recommendation",
    "generate_recommendations",
    "discover_repos",
    "scan_for_verdicts",
]
```
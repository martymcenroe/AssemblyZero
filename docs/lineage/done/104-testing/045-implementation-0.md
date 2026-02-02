# File: tools/verdict_analyzer/__init__.py

```python
"""Verdict Analyzer - Extract patterns from Gemini governance verdicts."""

__version__ = "1.0.0"
PARSER_VERSION = "1.0.0"

from tools.verdict_analyzer.parser import VerdictRecord, BlockingIssue, parse_verdict
from tools.verdict_analyzer.database import VerdictDatabase
from tools.verdict_analyzer.patterns import normalize_pattern, map_category_to_section, CATEGORY_TO_SECTION
from tools.verdict_analyzer.template_updater import (
    parse_template_sections,
    generate_recommendations,
    atomic_write_template,
    validate_template_path,
)
from tools.verdict_analyzer.scanner import scan_repos, find_registry, discover_verdicts

__all__ = [
    "VerdictRecord",
    "BlockingIssue", 
    "parse_verdict",
    "VerdictDatabase",
    "normalize_pattern",
    "map_category_to_section",
    "CATEGORY_TO_SECTION",
    "parse_template_sections",
    "generate_recommendations",
    "atomic_write_template",
    "validate_template_path",
    "scan_repos",
    "find_registry",
    "discover_verdicts",
    "PARSER_VERSION",
]
```
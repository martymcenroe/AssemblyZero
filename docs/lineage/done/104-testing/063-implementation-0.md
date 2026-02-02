# File: tools/verdict_analyzer/__init__.py

```python
"""Verdict Analyzer - Template improvement from Gemini verdicts."""

from __future__ import annotations

PARSER_VERSION = "1.0.0"

from tools.verdict_analyzer.parser import (
    BlockingIssue,
    VerdictRecord,
    compute_content_hash,
    parse_verdict,
)
from tools.verdict_analyzer.database import VerdictDatabase
from tools.verdict_analyzer.patterns import (
    CATEGORY_TO_SECTION,
    extract_patterns_from_issues,
    map_category_to_section,
    normalize_pattern,
)
from tools.verdict_analyzer.template_updater import (
    Recommendation,
    atomic_write_template,
    format_stats,
    generate_recommendations,
    parse_template_sections,
    validate_template_path,
)
from tools.verdict_analyzer.scanner import (
    discover_verdicts,
    find_registry,
    load_registry,
    scan_repos,
    validate_verdict_path,
)

__all__ = [
    "PARSER_VERSION",
    "BlockingIssue",
    "VerdictRecord",
    "compute_content_hash",
    "parse_verdict",
    "VerdictDatabase",
    "CATEGORY_TO_SECTION",
    "extract_patterns_from_issues",
    "map_category_to_section",
    "normalize_pattern",
    "Recommendation",
    "atomic_write_template",
    "format_stats",
    "generate_recommendations",
    "parse_template_sections",
    "validate_template_path",
    "discover_verdicts",
    "find_registry",
    "load_registry",
    "scan_repos",
    "validate_verdict_path",
]
```
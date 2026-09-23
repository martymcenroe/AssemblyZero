"""Verdict Analyzer - Template improvement from Gemini verdicts."""

from __future__ import annotations

from tools.verdict_analyzer.parser import (
    PARSER_VERSION as _PARSER_VERSION,
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

# Re-exported from the parser rather than redefined (#3484). It used to be
# assigned above the imports, with the comment "define here first, before any
# imports" -- which made every import below it E402. The circular-import problem
# that justified the early assignment was solved differently: `parser.py`
# defines its own copy, and `database.py` reads that one for cache
# invalidation, so nothing in this import chain needed the name early.
#
# Sourcing it from the parser also removes a second definition that could drift
# from the one actually used. See the sibling issue on that duplication.
PARSER_VERSION = _PARSER_VERSION

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
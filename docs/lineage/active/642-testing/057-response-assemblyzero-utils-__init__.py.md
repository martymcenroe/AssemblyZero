```python
"""Utility modules for AssemblyZero."""

from assemblyzero.utils.codebase_reader import (
    FileReadResult,
    is_sensitive_file,
    parse_project_metadata,
    read_file_with_budget,
    read_files_within_budget,
)
from assemblyzero.utils.lld_verification import (
    LLDVerificationError,
    LLDVerificationResult,
    detect_false_approval,
    extract_review_log_verdicts,
    has_gemini_approved_footer,
    run_verification_gate,
    validate_lld_path,
    verify_lld_approval,
)
from assemblyzero.utils.pattern_scanner import (
    PatternAnalysis,
    detect_frameworks,
    extract_conventions_from_claude_md,
    scan_patterns,
)
from assemblyzero.utils.lld_section_extractor import (
    ExtractedSection,
    extract_file_spec_section,
)

__all__ = [
    # lld_verification
    "LLDVerificationError",
    "LLDVerificationResult",
    "detect_false_approval",
    "extract_review_log_verdicts",
    "has_gemini_approved_footer",
    "run_verification_gate",
    "validate_lld_path",
    "verify_lld_approval",
    # codebase_reader
    "FileReadResult",
    "is_sensitive_file",
    "parse_project_metadata",
    "read_file_with_budget",
    "read_files_within_budget",
    # pattern_scanner
    "PatternAnalysis",
    "detect_frameworks",
    "extract_conventions_from_claude_md",
    "scan_patterns",
    # lld_section_extractor
    "ExtractedSection",
    "extract_file_spec_section",
]
```

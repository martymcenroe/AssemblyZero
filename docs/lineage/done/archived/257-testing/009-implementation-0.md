# File: agentos/workflows/requirements/parsers/__init__.py

```python
"""Parsers module for verdict and draft processing.

Issue #257: Review Node Should Update Draft with Resolved Open Questions

This module provides utilities for:
- Parsing resolved questions and Tier 3 suggestions from Gemini verdicts
- Updating LLD drafts with resolutions and suggestions
"""

from agentos.workflows.requirements.parsers.verdict_parser import (
    ResolvedQuestion,
    Tier3Suggestion,
    VerdictParseResult,
    parse_verdict,
)
from agentos.workflows.requirements.parsers.draft_updater import (
    update_draft_with_resolutions,
    update_draft_with_suggestions,
    update_draft,
)

__all__ = [
    "ResolvedQuestion",
    "Tier3Suggestion",
    "VerdictParseResult",
    "parse_verdict",
    "update_draft_with_resolutions",
    "update_draft_with_suggestions",
    "update_draft",
]
```
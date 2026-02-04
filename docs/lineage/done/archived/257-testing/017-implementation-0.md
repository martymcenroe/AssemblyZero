# File: agentos/workflows/requirements/parsers/__init__.py

```python
"""Parsers module for verdict and draft processing.

Issue #257: Parse verdicts and update drafts with resolved open questions.
"""

from agentos.workflows.requirements.parsers.verdict_parser import (
    VerdictParseResult,
    ResolvedQuestion,
    Tier3Suggestion,
    parse_verdict,
)
from agentos.workflows.requirements.parsers.draft_updater import update_draft

__all__ = [
    "VerdictParseResult",
    "ResolvedQuestion",
    "Tier3Suggestion",
    "parse_verdict",
    "update_draft",
]
```
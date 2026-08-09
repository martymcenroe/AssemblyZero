"""Exit codes the roll machinery uses to speak without parsing prose (#2166).

The launcher classifies a child's death by exit code alone. Prose parsing is
how classifications rot, so each non-generic failure class gets a code:

- 91: a base or gate problem. Never retried (established behavior).
- 92: a provider storm (``assemblyzero.core.provider_storm.STORM_EXIT_CODE``).
  Backed off, then retried.
- 93: a requirements conflict. The ISSUE needs an operator ruling, so no
  redraw can help; the launcher stops the issue and continues the batch.
"""

from __future__ import annotations

CONFLICT_EXIT_CODE = 93

#: Must match ``REQUIREMENTS_CONFLICT_MARKER`` in
#: ``assemblyzero.workflows.requirements.nodes.analyze_requirements`` -- a
#: test pins the two together so they cannot drift.
CONFLICT_MARKER = "REQUIREMENTS CONFLICT:"


def is_requirements_conflict(error_summary: str | None) -> bool:
    """True when a failure's error summary carries the conflict marker.

    The marker is a deliberate structured prefix set by the analysis gate
    (#1899) and the spec reviewer (#1900); detecting it here is reading our
    own protocol, not scraping free text.
    """
    return bool(error_summary) and CONFLICT_MARKER in error_summary

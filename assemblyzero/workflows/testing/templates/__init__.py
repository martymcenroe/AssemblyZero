"""Documentation templates for TDD Testing Workflow N8 node.

Issue #93: N8 Documentation Node

Provides template generators for:
- Wiki pages
- Runbooks
- Lessons learned
- c/p documentation pairs
"""

from assemblyzero.workflows.testing.templates.cp_docs import (
    generate_cli_doc,
    generate_prompt_doc,
)
from assemblyzero.workflows.testing.templates.lessons import generate_lessons_learned
from assemblyzero.workflows.testing.templates.runbook import generate_runbook
from assemblyzero.workflows.testing.templates.wiki_page import (
    generate_wiki_page,
    update_wiki_sidebar,
)

__all__ = [
    "generate_wiki_page",
    "update_wiki_sidebar",
    "generate_runbook",
    "generate_lessons_learned",
    "generate_cli_doc",
    "generate_prompt_doc",
]

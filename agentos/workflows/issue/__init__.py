"""Issue creation workflow - Governance StateGraph for drafting GitHub issues.

Issue #62: Implements Inversion of Control pattern where:
- Python script controls the workflow
- Agent is "jailed" with no gh access
- Human gates at every LLM handoff (N3, N5)
- Issue number assigned only at N6 by Python
"""

from agentos.workflows.issue.state import IssueWorkflowState
from agentos.workflows.issue.graph import build_issue_workflow

__all__ = ["IssueWorkflowState", "build_issue_workflow"]

"""Unified Requirements Workflow package.

Issue #101: Unified Requirements Workflow

This package provides a unified workflow for both:
- Issue creation (from briefs/ideation notes)
- LLD creation (from GitHub issues)

Key components:
- config: WorkflowConfig dataclass and presets
- state: RequirementsWorkflowState TypedDict
- audit: Unified audit trail utilities
- graph: Parameterized StateGraph
- nodes/: Individual node implementations
"""

from agentos.workflows.requirements.config import (
    GateConfig,
    WorkflowConfig,
    create_issue_config,
    create_lld_config,
)
from agentos.workflows.requirements.graph import create_requirements_graph
from agentos.workflows.requirements.state import (
    RequirementsWorkflowState,
    HumanDecision,
    WorkflowType,
    create_initial_state,
)

__all__ = [
    "WorkflowConfig",
    "GateConfig",
    "RequirementsWorkflowState",
    "HumanDecision",
    "WorkflowType",
    "create_issue_config",
    "create_lld_config",
    "create_requirements_graph",
    "create_initial_state",
]

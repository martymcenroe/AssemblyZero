"""LLD Governance Workflow package.

Issue #86: LLD Creation & Governance Review Workflow
LLD: docs/LLDs/active/LLD-086-lld-governance-workflow.md

This package implements a LangGraph workflow that orchestrates LLD creation
from GitHub issues, enforces human review gates, and loops until Gemini
governance approval.

Usage:
    python tools/run_lld_workflow.py --issue 42
    python tools/run_lld_workflow.py --issue 42 --auto
    python tools/run_lld_workflow.py --issue 42 --mock
    python tools/run_lld_workflow.py --issue 42 --context file.py
"""

from agentos.workflows.lld.graph import build_lld_workflow
from agentos.workflows.lld.state import HumanDecision, LLDWorkflowState

__all__ = [
    "build_lld_workflow",
    "LLDWorkflowState",
    "HumanDecision",
]

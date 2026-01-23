"""Core state definition for AgentOS LangGraph workflows.

This module defines the AgentState TypedDict that travels through
the governance pipeline: Issue -> LLD Review -> Implementation -> Code Review -> Merge
"""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Core state shared across all AgentOS LangGraph nodes.

    Attributes:
        messages: Standard LangGraph message accumulator with add_messages annotation.
        issue_id: GitHub issue number being worked on.
        worktree_path: Path to the git worktree for this issue.
        lld_content: Full content of the Low-Level Design document.
        lld_status: Current approval status of the LLD.
        gemini_critique: Feedback from Gemini verification layer.
        iteration_count: Safety counter for loop prevention.
    """

    # Standard LangGraph message accumulator
    messages: Annotated[list[BaseMessage], add_messages]

    # Issue tracking
    issue_id: int
    worktree_path: str

    # LLD governance
    lld_content: str
    lld_status: Literal["PENDING", "APPROVED", "BLOCKED"]

    # Gemini feedback
    gemini_critique: str

    # Safety: loop prevention
    iteration_count: int

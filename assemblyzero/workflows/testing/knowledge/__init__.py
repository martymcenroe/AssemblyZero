"""Test Type Knowledge Base for TDD Testing Workflow.

Provides:
- Test type definitions (YAML corpus for future RAG)
- Detection patterns for inferring test types from LLD content
"""

from assemblyzero.workflows.testing.knowledge.patterns import detect_test_types

__all__ = ["detect_test_types"]

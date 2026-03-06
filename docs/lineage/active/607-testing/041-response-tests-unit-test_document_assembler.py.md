```python
"""Tests for mechanical document assembly.

Issue #607: Mechanical Document Assembly Node
"""
import pytest
from unittest.mock import patch, MagicMock

from assemblyzero.nodes.document_assembler import (
    strip_hallucinated_headers,
    assemble_final_document,
    AssemblyError
)
from assemblyzero.workflows.lld.nodes.assembly_node import assemble_document_node


def test_strip_hallucinated_headers_exact_match():
    """T040: Regex strips exact hallucinated headers."""
    content = "## 2. Proposed Changes\n\nThis is the content."
    expected = "## 2. Proposed Changes"
    result = strip_hallucinated_headers(content, expected)
    assert result == "This is the content."


def test_strip_hallucinated_headers_variations():
    """T040: Regex strips hallucinated headers with asterisks and whitespace."""
    content = "  ### **2. Proposed Changes**  \n\nContent here."
    expected = "## 2. Proposed Changes"
    result = strip_hallucinated_headers(content, expected)
    assert result == "Content here."


def test_strip_hallucinated_headers_no_match():
    """T040: Content without hallucinated header remains intact."""
    content = "This content starts directly without a header."
    expected = "## 2. Proposed Changes"
    result = strip_hallucinated_headers(content, expected)
    assert result == "This content starts directly without a header."


def test_assemble_final_document_no_drift():
    """T010: Assembled document exactly matches template headers without drift."""
    sections = [
        {"id": "1", "header": "## 1. Context", "content": "Context details."},
        {"id": "2", "header": "## 2. Changes", "content": "Change details."}
    ]
    result = assemble_final_document(sections)
    expected = "## 1. Context\n\nContext details.\n\n## 2. Changes\n\nChange details.\n"
    assert result == expected


@patch("assemblyzero.workflows.lld.nodes.assembly_node.LLD_TEMPLATE", [
    {"id": "context", "header": "## 1. Context", "prompt_instruction": "Instruction 1"}
])
@patch("assemblyzero.workflows.lld.nodes.assembly_node.ChatAnthropic")
def test_assemble_document_node_max_retries(mock_chat_class):
    """T020: assemble_document_node raises AssemblyError after 3 failed attempts."""
    mock_llm_instance = MagicMock()
    mock_llm_instance.invoke.side_effect = Exception("API failure")
    mock_chat_class.return_value = mock_llm_instance

    state = {
        "issue_context": "Test issue",
        "completed_sections": []
    }

    with pytest.raises(AssemblyError, match="Failed to generate context after 3 attempts."):
        assemble_document_node(state)

    assert mock_llm_instance.invoke.call_count == 3


@patch("assemblyzero.workflows.lld.nodes.assembly_node.LLD_TEMPLATE", [
    {"id": "context", "header": "## 1. Context", "prompt_instruction": "Instruction 1"},
    {"id": "changes", "header": "## 2. Changes", "prompt_instruction": "Instruction 2"}
])
@patch("assemblyzero.workflows.lld.nodes.assembly_node.ChatAnthropic")
def test_assemble_document_node_prior_context(mock_chat_class):
    """T030: assemble_document_node includes prior completed sections in prompt string."""
    mock_response = MagicMock()
    mock_response.content = "New section content"
    
    mock_llm_instance = MagicMock()
    mock_llm_instance.invoke.return_value = mock_response
    mock_chat_class.return_value = mock_llm_instance

    state = {
        "issue_context": "Test issue",
        "completed_sections": [
            {
                "id": "context",
                "header": "## 1. Context",
                "content": "Prior context text.",
                "attempts": 1
            }
        ]
    }

    result = assemble_document_node(state)
    
    # Verify it skipped 'context' and invoked only for 'changes'
    assert mock_llm_instance.invoke.call_count == 1
    
    first_call_args = mock_llm_instance.invoke.call_args[0][0]
    human_msg_content = first_call_args[1].content
    
    assert "## 1. Context\nPrior context text." in human_msg_content
    assert result["error_message"] == ""
    assert len(result["completed_sections"]) == 2
    assert "New section content" in result["final_document"]
```
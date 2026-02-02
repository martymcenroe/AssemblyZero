# Implementation Request

## Context

You are implementing code for Issue #161 using TDD.
This is iteration 2 of the implementation.

## Requirements

The tests have been scaffolded and need implementation code to pass.

### LLD Summary

# 1161 - Fix: Unicode encoding error in subprocess calls on Windows

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Manual LLD (workflow bootstrap fix)
Update Reason: Initial LLD - workflow cannot process its own bug report due to encoding issue
-->

## 1. Context & Goal
* **Issue:** #161
* **Objective:** Fix subprocess calls to use UTF-8 encoding so the requirements workflow can process GitHub issues containing Unicode characters on Windows
* **Status:** Draft
* **Related Issues:** RCA-PDF-extraction-pipeline #35 (blocked by this bug)

### Open Questions

- [x] ~~Which files contain affected subprocess calls?~~ *Resolved: Primarily `load_input.py`, but all subprocess calls should be fixed for consistency*
- [ ] Should we set encoding globally via environment variable or per-call?

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describes exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/requirements/nodes/load_input.py` | Modify | Add `encoding='utf-8'` to subprocess.run call |
| `agentos/workflows/requirements/nodes/finalize.py` | Modify | Add `encoding='utf-8'` to any subprocess calls |
| `tools/run_requirements_workflow.py` | Modify | Add `encoding='utf-8'` to subprocess calls if present |
| `tests/unit/test_requirements_nodes.py` | Modify | Add test for Unicode issue handling |

### 2.2 Dependencies

*No new packages required.*

```toml
# pyproject.toml additions (if any)
# None
```

### 2.3 Data Structures

*No new data structures required. This is a parameter fix.*

### 2.4 Function Signatures

*No new functions. Existing subprocess.run calls modified.*

### 2.5 Logic Flow (Pseudocode)

```
BEFORE (broken on Windows with Unicode):
result = subprocess.run(
    ["gh", "issue", "view", str(issue_number), "--json", "title,body"],
    capture_output=True,
    text=True,
    cwd=target_repo,
    timeout=GH_TIMEOUT_SECON...

### Test Scenarios

- **test_005**: Verify code passes linting | Unit | Changed files | No lint errors | flake8/ruff returns exit 0
  - Requirement: 
  - Type: unit

- **test_010**: Verify encoding param on load_input subprocess | Unit | Mock subprocess.run | Called with encoding='utf-8' | Assert call includes encoding='utf-8'
  - Requirement: 
  - Type: unit

- **test_020**: Verify encoding param on finalize subprocess | Unit | Mock subprocess.run | Called with encoding='utf-8' | Assert call includes encoding='utf-8'
  - Requirement: 
  - Type: unit

- **test_030**: Parse issue with box-drawing chars | Unit | Mock JSON with Unicode | Parsed correctly | No UnicodeDecodeError, content preserved
  - Requirement: 
  - Type: unit

- **test_040**: Parse issue with emojis | Unit | Mock JSON with emojis | Parsed correctly | Content preserved
  - Requirement: 
  - Type: unit

- **test_050**: Parse ASCII-only issue (regression) | Unit | Mock JSON ASCII only | Parsed correctly | No behavior change
  - Requirement: 
  - Type: unit

- **test_060**: Handle malformed UTF-8 gracefully | Unit | Invalid byte sequence | Graceful error or replacement | No crash, clear error message
  - Requirement: 
  - Type: unit

- **test_070**: Windows CI validation | Integration | CI on Windows runner | Workflow completes | Exit code 0
  - Requirement: 
  - Type: integration

### Test File: C:\Users\mcwiz\Projects\AgentOS-161\tests\test_issue_161.py

```python
"""Test file for Issue #161: Fix Unicode encoding error in subprocess calls.

Tests that subprocess calls use UTF-8 encoding to handle Unicode characters
in GitHub issues on Windows.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from agentos.workflows.requirements.nodes.load_input import _load_issue
from agentos.workflows.requirements.nodes.finalize import _finalize_issue


# Fixtures for mocking
@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for testing."""
    with patch("subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture
def mock_state():
    """Mock workflow state."""
    return {
        "issue_number": 161,
        "target_repo": str(Path.cwd()),
        "context_files": [],
        "config_mock_mode": False,
        "workflow_type": "lld",
        "current_draft": "# Test Issue\n\nThis is a test.",
        "audit_dir": "",
    }


@pytest.fixture
def test_client():
    """Test client for API calls."""
    yield None


# Unit Tests
# -----------

def test_005():
    """
    Verify code passes linting | Unit | Changed files | No lint errors |
    flake8/ruff returns exit 0
    """
    # TDD: Arrange
    changed_files = [
        "agentos/workflows/requirements/nodes/load_input.py",
        "agentos/workflows/requirements/nodes/finalize.py",
        "tools/run_requirements_workflow.py",
    ]

    # TDD: Act
    # Check that files exist (linting would be done by CI)
    all_exist = all(Path(f).exists() for f in changed_files)

    # TDD: Assert
    assert all_exist, "All changed files should exist"


def test_010(mock_subprocess_run, mock_state):
    """
    Verify encoding param on load_input subprocess | Unit | Mock
    subprocess.run | Called with encoding='utf-8' | Assert call includes
    encoding='utf-8'
    """
    # TDD: Arrange
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "title": "Test Issue",
        "body": "Test body with Unicode: ├── ✓"
    })
    mock_subprocess_run.return_value = mock_result

    with patch("agentos.workflows.requirements.nodes.load_input.create_audit_dir") as mock_audit_dir, \
         patch("agentos.workflows.requirements.nodes.load_input.next_file_number") as mock_file_num, \
         patch("agentos.workflows.requirements.nodes.load_input.save_audit_file"):
        mock_audit_dir.return_value = Path("/tmp/audit")
        mock_file_num.return_value = 1

        # TDD: Act
        result = _load_issue(mock_state)

        # TDD: Assert
        assert mock_subprocess_run.called, "subprocess.run should be called"
        call_kwargs = mock_subprocess_run.call_args.kwargs
        assert "encoding" in call_kwargs, "encoding parameter should be present"
        assert call_kwargs["encoding"] == "utf-8", "encoding should be utf-8"
        assert result["error_message"] == "", "Should succeed without error"


def test_020(mock_subprocess_run, mock_state):
    """
    Verify encoding param on finalize subprocess | Unit | Mock
    subprocess.run | Called with encoding='utf-8' | Assert call includes
    encoding='utf-8'
    """
    # TDD: Arrange
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "https://github.com/owner/repo/issues/161"
    mock_subprocess_run.return_value = mock_result

    with patch("agentos.workflows.requirements.nodes.finalize.next_file_number") as mock_file_num, \
         patch("agentos.workflows.requirements.nodes.finalize.save_audit_file"):
        mock_file_num.return_value = 1
        mock_state["audit_dir"] = str(Path("/tmp/audit"))
        Path(mock_state["audit_dir"]).mkdir(parents=True, exist_ok=True)

        # TDD: Act
        result = _finalize_issue(mock_state)

        # TDD: Assert
        assert mock_subprocess_run.called, "subprocess.run should be called"
        call_kwargs = mock_subprocess_run.call_args.kwargs
        assert "encoding" in call_kwargs, "encoding parameter should be present"
        assert call_kwargs["encoding"] == "utf-8", "encoding should be utf-8"
        assert result["error_message"] == "", "Should succeed without error"

        # Cleanup
        Path(mock_state["audit_dir"]).rmdir()


def test_030(mock_subprocess_run, mock_state):
    """
    Parse issue with box-drawing chars | Unit | Mock JSON with Unicode |
    Parsed correctly | No UnicodeDecodeError, content preserved
    """
    # TDD: Arrange
    unicode_content = "Project structure:\n├── src/\n│   ├── main.py\n└── tests/"
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "title": "Feature Request",
        "body": unicode_content
    })
    mock_subprocess_run.return_value = mock_result

    with patch("agentos.workflows.requirements.nodes.load_input.create_audit_dir") as mock_audit_dir, \
         patch("agentos.workflows.requirements.nodes.load_input.next_file_number") as mock_file_num, \
         patch("agentos.workflows.requirements.nodes.load_input.save_audit_file"):
        mock_audit_dir.return_value = Path("/tmp/audit")
        mock_file_num.return_value = 1

        # TDD: Act
        result = _load_issue(mock_state)

        # TDD: Assert
        assert result["error_message"] == "", "Should not error on Unicode"
        assert result["issue_body"] == unicode_content, "Unicode content should be preserved"
        assert "├──" in result["issue_body"], "Box drawing characters should be intact"


def test_040(mock_subprocess_run, mock_state):
    """
    Parse issue with emojis | Unit | Mock JSON with emojis | Parsed
    correctly | Content preserved
    """
    # TDD: Arrange
    emoji_content = "Status: ✅ Done | ⚠️ Warning | ❌ Failed | 🚀 Deployed"
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "title": "Release v1.0 🎉",
        "body": emoji_content
    })
    mock_subprocess_run.return_value = mock_result

    with patch("agentos.workflows.requirements.nodes.load_input.create_audit_dir") as mock_audit_dir, \
         patch("agentos.workflows.requirements.nodes.load_input.next_file_number") as mock_file_num, \
         patch("agentos.workflows.requirements.nodes.load_input.save_audit_file"):
        mock_audit_dir.return_value = Path("/tmp/audit")
        mock_file_num.return_value = 1

        # TDD: Act
        result = _load_issue(mock_state)

        # TDD: Assert
        assert result["error_message"] == "", "Should not error on emojis"
        assert result["issue_title"] == "Release v1.0 🎉", "Emoji in title should be preserved"
        assert "✅" in result["issue_body"], "Checkmark emoji should be intact"
        assert "🚀" in result["issue_body"], "Rocket emoji should be intact"


def test_050(mock_subprocess_run, mock_state):
    """
    Parse ASCII-only issue (regression) | Unit | Mock JSON ASCII only |
    Parsed correctly | No behavior change
    """
    # TDD: Arrange
    ascii_content = "Simple ASCII content without any special characters."
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "title": "Simple Issue",
        "body": ascii_content
    })
    mock_subprocess_run.return_value = mock_result

    with patch("agentos.workflows.requirements.nodes.load_input.create_audit_dir") as mock_audit_dir, \
         patch("agentos.workflows.requirements.nodes.load_input.next_file_number") as mock_file_num, \
         patch("agentos.workflows.requirements.nodes.load_input.save_audit_file"):
        mock_audit_dir.return_value = Path("/tmp/audit")
        mock_file_num.return_value = 1

        # TDD: Act
        result = _load_issue(mock_state)

        # TDD: Assert
        assert result["error_message"] == "", "Should succeed without error"
        assert result["issue_body"] == ascii_content, "ASCII content should be unchanged"
        assert result["issue_title"] == "Simple Issue", "Title should be correct"


def test_060():
    """
    Handle malformed UTF-8 gracefully | Unit | Invalid byte sequence |
    Graceful error or replacement | No crash, clear error message
    """
    # TDD: Arrange
    # Python's subprocess with encoding='utf-8' and text=True handles this automatically
    # by using error handler (default is 'strict' but subprocess uses 'replace')
    # This test verifies the error handling behavior

    # TDD: Act
    # subprocess.run with encoding='utf-8' will handle malformed UTF-8
    # by replacing invalid sequences with replacement character
    result = subprocess.run(
        ["echo", "test"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",  # Explicit error handling
    )

    # TDD: Assert
    assert result.returncode == 0, "Command should succeed"
    assert isinstance(result.stdout, str), "Output should be string"


# Integration Tests
# -----------------

def test_070(test_client):
    """
    Windows CI validation | Integration | CI on Windows runner | Workflow
    completes | Exit code 0
    """
    # TDD: Arrange
    # This test would run in CI on a Windows runner
    # It validates the entire workflow with real gh CLI calls
    # For unit testing, we just verify the test structure

    # TDD: Act
    # In CI, this would execute: python tools/run_requirements_workflow.py --mock
    # For now, we verify the test client fixture is available
    assert test_client is not None or test_client is None, "Fixture should be available"

    # TDD: Assert
    # In CI, this would assert exit code 0
    # For unit tests, this is a placeholder
    assert True, "Test structure is valid"
```

### Previous Test Run (FAILED)

The previous implementation attempt failed. Here's the test output:

```
dInfoV1

..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77: DeprecationWarning: ForwardRef._evaluate is a private API and is retained for compatibility, but will be removed in Python 3.16. Use ForwardRef.evaluate() or typing.evaluate_forward_ref() instead.
    return cast(Any, type_)._evaluate(globalns, localns, type_params=(), recursive_guard=set())

..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43: DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17
    VersionedUnionType = Union[builtin_types.UnionType, _UnionGenericAlias]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR tests/test_issue_161.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
======================== 9 warnings, 1 error in 1.10s =========================


```

Please fix the issues and provide updated implementation.

## Instructions

1. Generate implementation code that makes all tests pass
2. Follow the patterns established in the codebase
3. Ensure proper error handling
4. Add type hints where appropriate
5. Keep the implementation minimal - only what's needed to pass tests

## Output Format (CRITICAL - MUST FOLLOW EXACTLY)

For EACH file you need to create or modify, provide a code block with this EXACT format:

```python
# File: path/to/implementation.py

def function_name():
    ...
```

**Rules:**
- The `# File: path/to/file` comment MUST be the FIRST line inside the code block
- Use the language-appropriate code fence (```python, ```gitignore, ```yaml, etc.)
- Path must be relative to repository root (e.g., `src/module/file.py`)
- Do NOT include "(append)" or other annotations in the path
- Provide complete file contents, not patches or diffs

**Example for .gitignore:**
```gitignore
# File: .gitignore

# Existing patterns...
*.pyc
__pycache__/

# New pattern
.agentos/
```

If multiple files are needed, provide each in a separate code block with its own `# File:` header.

# Implementation Request

## Context

You are implementing code for Issue #104 using TDD.
This is iteration 0 of the implementation.

## Requirements

The tests have been scaffolded and need implementation code to pass.

### LLD Summary

# 105 - Feature: Verdict Analyzer - Template Improvement from Gemini Verdicts

## 1. Context & Goal
* **Issue:** #105
* **Objective:** Create a Python CLI tool that analyzes Gemini governance verdicts across repositories, extracts blocking patterns, and automatically improves LLD/issue templates.
* **Status:** Draft
* **Related Issues:** #94 (Janitor integration), #77 (Issue template)

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tools/verdict-analyzer.py` | Add | Main CLI entry point with argparse interface |
| `tools/verdict_analyzer/__init__.py` | Add | Package initialization |
| `tools/verdict_analyzer/parser.py` | Add | Parse verdict markdown files (LLD + Issue formats) |
| `tools/verdict_analyzer/database.py` | Add | SQLite operations (CRUD, migrations) |
| `tools/verdict_analyzer/patterns.py` | Add | Pattern extraction, normalization, and category mapping |
| `tools/verdict_analyzer/template_updater.py` | Add | Safe template modification with atomic writes |
| `tools/verdict_analyzer/scanner.py` | Add | Multi-repo verdict discovery |
| `tests/test_verdict_analyzer.py` | Add | Unit tests for all modules |
| `.agentos/verdicts.db` | Add | SQLite database (git-ignored, project-local) |

### 2.2 Dependencies

*New packages, APIs, or services required.*

```toml
# pyproject.toml additions (if any)
# No new dependencies - uses stdlib only
# sqlite3 - built-in
# hashlib - built-in
# argparse - built-in
# pathlib - built-in
# re - built-in
# json - built-in
# logging - built-in
```

**Logging Configuration:**

```python
# Configured in verdict-analyzer.py
import logging

def configure_logging(verbosity: int) -> None:
    """Configure logging based on -v/-vv flags.
    
    Args:
        verbosity: 0 = WARNING, 1 = INFO, 2+ = DEBUG
    """
    level = logging.WARNING
    if verbosity == 1:
  ...

### Test Scenarios

- **test_010**: Parse LLD verdict | Auto | Sample LLD verdict markdown | VerdictRecord with correct fields | All fields populated, type='lld'
  - Requirement: 
  - Type: unit

- **test_020**: Parse Issue verdict | Auto | Sample Issue verdict markdown | VerdictRecord with correct fields | All fields populated, type='issue'
  - Requirement: 
  - Type: unit

- **test_030**: Extract blocking issues | Auto | Verdict with Tier 1/2/3 issues | List of BlockingIssue | Correct tier, category, description
  - Requirement: 
  - Type: unit

- **test_040**: Content hash change detection | Auto | Same file, modified file | needs_update=False, True | Correct boolean return
  - Requirement: 
  - Type: unit

- **test_050**: Pattern normalization | Auto | Various descriptions | Normalized patterns | Consistent output for similar inputs
  - Requirement: 
  - Type: unit

- **test_060**: Category mapping | Auto | All categories | Correct template sections | Matches CATEGORY_TO_SECTION
  - Requirement: 
  - Type: unit

- **test_070**: Template section parsing | Auto | 0102 template | Dict of 11 sections | All sections extracted
  - Requirement: 
  - Type: unit

- **test_080**: Recommendation generation | Auto | Pattern stats with high counts | Recommendations list | Type, section, content populated
  - Requirement: 
  - Type: unit

- **test_090**: Atomic write with backup | Auto | Template path + content | .bak created, content written | Both files exist, content correct
  - Requirement: 
  - Type: unit

- **test_100**: Multi-repo discovery | Auto | Mock project-registry.json | List of repo paths | All repos found
  - Requirement: 
  - Type: unit

- **test_110**: Missing repo handling | Auto | Registry with nonexistent repo | Warning logged, continue | No crash, other repos scanned
  - Requirement: 
  - Type: unit

- **test_120**: Database migration | Auto | Old schema DB | Updated schema | New columns exist
  - Requirement: 
  - Type: unit

- **test_130**: Dry-run mode (default) | Auto | Preview only, no file changes | Template unchanged
  - Requirement: 
  - Type: unit

- **test_140**: Stats output formatting | Auto | Database with verdicts | Formatted statistics | Readable output
  - Requirement: 
  - Type: unit

- **test_150**: Auto | Registry found at /path/to/dir/project-registry.json | Correct path resolution
  - Requirement: 
  - Type: unit

- **test_160**: Auto | Registry found at explicit path
  - Requirement: 
  - Type: unit

- **test_170**: Auto | DB with existing verdicts | All verdicts re-parsed | Hash check bypassed
  - Requirement: 
  - Type: unit

- **test_180**: Verbose logging (-v) | Auto | Filename logged at DEBUG | Parsing error includes filename
  - Requirement: 
  - Type: unit

- **test_190**: Path traversal prevention (verdict) | Auto | Verdict path with ../../../etc/passwd | Path rejected, error logged | is_relative_to() check fails
  - Requirement: 
  - Type: unit

- **test_195**: Path traversal prevention (template) | Auto | Path rejected, error logged | validate_template_path() fails
  - Requirement: 
  - Type: unit

- **test_200**: Parser version upgrade re-parse | Auto | DB with old parser_version | Verdict re-parsed despite unchanged content | needs_update returns True when parser_version outdated
  - Requirement: 
  - Type: unit

- **test_210**: Symlink loop handling | Auto | Directory with recursive symlink | Scanner completes without hanging | No infinite recursion, warning logged
  - Requirement: 
  - Type: unit

- **test_220**: Database directory creation | Auto | .agentos/ does not exist | Directory created, DB initialized | No error, DB file exists
  - Requirement: 
  - Type: unit

### Test File: C:\Users\mcwiz\Projects\AgentOS\tests\test_issue_104.py

```python
"""Test file for Issue #104.

Generated by AgentOS TDD Testing Workflow.
Each test starts with `assert False` - implementation will make them pass.
"""

import pytest


# Fixtures for mocking
@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    # TODO: Implement mock
    yield None


# Unit Tests
# -----------

def test_010():
    """
    Parse LLD verdict | Auto | Sample LLD verdict markdown |
    VerdictRecord with correct fields | All fields populated, type='lld'
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_010"


def test_020():
    """
    Parse Issue verdict | Auto | Sample Issue verdict markdown |
    VerdictRecord with correct fields | All fields populated, type='issue'
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_020"


def test_030():
    """
    Extract blocking issues | Auto | Verdict with Tier 1/2/3 issues |
    List of BlockingIssue | Correct tier, category, description
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_030"


def test_040():
    """
    Content hash change detection | Auto | Same file, modified file |
    needs_update=False, True | Correct boolean return
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_040"


def test_050():
    """
    Pattern normalization | Auto | Various descriptions | Normalized
    patterns | Consistent output for similar inputs
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_050"


def test_060():
    """
    Category mapping | Auto | All categories | Correct template sections
    | Matches CATEGORY_TO_SECTION
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_060"


def test_070():
    """
    Template section parsing | Auto | 0102 template | Dict of 11 sections
    | All sections extracted
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_070"


def test_080():
    """
    Recommendation generation | Auto | Pattern stats with high counts |
    Recommendations list | Type, section, content populated
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_080"


def test_090():
    """
    Atomic write with backup | Auto | Template path + content | .bak
    created, content written | Both files exist, content correct
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_090"


def test_100(mock_external_service):
    """
    Multi-repo discovery | Auto | Mock project-registry.json | List of
    repo paths | All repos found
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_100"


def test_110():
    """
    Missing repo handling | Auto | Registry with nonexistent repo |
    Warning logged, continue | No crash, other repos scanned
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_110"


def test_120(mock_external_service):
    """
    Database migration | Auto | Old schema DB | Updated schema | New
    columns exist
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_120"


def test_130():
    """
    Dry-run mode (default) | Auto | Preview only, no file changes |
    Template unchanged
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_130"


def test_140(mock_external_service):
    """
    Stats output formatting | Auto | Database with verdicts | Formatted
    statistics | Readable output
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_140"


def test_150():
    """
    Auto | Registry found at /path/to/dir/project-registry.json | Correct
    path resolution
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_150"


def test_160():
    """
    Auto | Registry found at explicit path
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_160"


def test_170():
    """
    Auto | DB with existing verdicts | All verdicts re-parsed | Hash
    check bypassed
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_170"


def test_180():
    """
    Verbose logging (-v) | Auto | Filename logged at DEBUG | Parsing
    error includes filename
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_180"


def test_190():
    """
    Path traversal prevention (verdict) | Auto | Verdict path with
    ../../../etc/passwd | Path rejected, error logged | is_relative_to()
    check fails
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_190"


def test_195():
    """
    Path traversal prevention (template) | Auto | Path rejected, error
    logged | validate_template_path() fails
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_195"


def test_200():
    """
    Parser version upgrade re-parse | Auto | DB with old parser_version |
    Verdict re-parsed despite unchanged content | needs_update returns
    True when parser_version outdated
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_200"


def test_210():
    """
    Symlink loop handling | Auto | Directory with recursive symlink |
    Scanner completes without hanging | No infinite recursion, warning
    logged
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_210"


def test_220(mock_external_service):
    """
    Database directory creation | Auto | .agentos/ does not exist |
    Directory created, DB initialized | No error, DB file exists
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_220"


```

## Instructions

1. Generate implementation code that makes all tests pass
2. Follow the patterns established in the codebase
3. Ensure proper error handling
4. Add type hints where appropriate
5. Keep the implementation minimal - only what's needed to pass tests

## Output Format

Provide the implementation in a code block with the file path:

```python
# File: path/to/implementation.py

def function_name():
    ...
```

If multiple files are needed, provide each in a separate code block.

```python
"""Unit tests for check_type_renames node.

Issue: #170
LLD: docs/LLDs/active/170-check-type-renames.md
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentos.nodes.check_type_renames import (
    OrphanedUsage,
    TypeRenameIssue,
    check_type_renames,
    extract_removed_types,
    find_type_usages,
    format_type_rename_error,
    log_scan_summary,
)


# Fixtures
# --------

@pytest.fixture
def sample_diff_class():
    """Sample diff with removed class."""
    return """diff --git a/agentos/types.py b/agentos/types.py
index 1234567..abcdefg 100644
--- a/agentos/types.py
+++ b/agentos/types.py
@@ -10,7 +10,7 @@
 from typing import TypedDict
 
-class WorkflowConfig:
+class WorkflowConfiguration:
     \"\"\"Configuration for workflow.\"\"\"
     pass
"""


@pytest.fixture
def sample_diff_typeddict():
    """Sample diff with removed TypedDict."""
    return """diff --git a/agentos/state.py b/agentos/state.py
index 1234567..abcdefg 100644
--- a/agentos/state.py
+++ b/agentos/state.py
@@ -5,7 +5,7 @@
 from typing import TypedDict
 
-WorkflowState = TypedDict('WorkflowState', {
+AgentState = TypedDict('AgentState', {
     'messages': list[str]
 })
"""


@pytest.fixture
def sample_diff_type_alias():
    """Sample diff with removed type alias."""
    return """diff --git a/agentos/utils.py b/agentos/utils.py
index 1234567..abcdefg 100644
--- a/agentos/utils.py
+++ b/agentos/utils.py
@@ -3,7 +3,7 @@
 from typing import Union
 
-ConfigType = Union[dict, str]
+Configuration = Union[dict, str]
 
 def load_config(path: str) -> dict:
     pass
"""


@pytest.fixture
def mock_git_grep_output():
    """Mock git grep output."""
    return """agentos/workflows/main.py:15:from agentos.types import WorkflowConfig
agentos/workflows/validator.py:8:def validate(cfg: WorkflowConfig) -> bool:
tests/test_workflow.py:20:    config = WorkflowConfig()
"""


@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    yield None


# Unit Tests - Extract Removed Types
# -----------------------------------

def test_extract_removed_class(sample_diff_class):
    """T010: test_extract_removed_class | Extracts class name from diff | RED"""
    result = extract_removed_types(sample_diff_class)
    
    assert len(result) == 1
    assert result[0] == ('WorkflowConfig', 'agentos/types.py')


def test_extract_removed_typeddict(sample_diff_typeddict):
    """T020: test_extract_removed_typeddict | Extracts TypedDict from diff | RED"""
    result = extract_removed_types(sample_diff_typeddict)
    
    assert len(result) == 1
    assert result[0] == ('WorkflowState', 'agentos/state.py')


def test_extract_removed_type_alias(sample_diff_type_alias):
    """T030: test_extract_removed_type_alias | Extracts type alias from diff | RED"""
    result = extract_removed_types(sample_diff_type_alias)
    
    assert len(result) == 1
    assert result[0] == ('ConfigType', 'agentos/utils.py')


def test_extract_multiple_removed_types():
    """Test extracting multiple removed types from single diff."""
    diff = """diff --git a/agentos/types.py b/agentos/types.py
--- a/agentos/types.py
+++ b/agentos/types.py
@@ -1,10 +1,5 @@
-class OldClass:
-    pass
-
-NewType = Union[str, int]
-
-ConfigDict = TypedDict('ConfigDict', {'key': str})
+# All removed
"""
    
    result = extract_removed_types(diff)
    
    assert len(result) == 3
    type_names = [name for name, _ in result]
    assert 'OldClass' in type_names
    assert 'NewType' in type_names
    assert 'ConfigDict' in type_names


def test_extract_ignores_added_types():
    """Test that added types (lines with +) are not extracted."""
    diff = """diff --git a/agentos/types.py b/agentos/types.py
--- a/agentos/types.py
+++ b/agentos/types.py
@@ -1,3 +1,3 @@
-class OldClass:
+class NewClass:
     pass
"""
    
    result = extract_removed_types(diff)
    
    assert len(result) == 1
    assert result[0][0] == 'OldClass'


def test_extract_ignores_non_python_files():
    """Test that non-.py files are ignored."""
    diff = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,3 +1,3 @@
-class FakeClass:
+# Not a real class
"""
    
    result = extract_removed_types(diff)
    
    assert len(result) == 0


# Unit Tests - Find Type Usages
# ------------------------------

@patch('subprocess.run')
def test_find_usages_in_imports(mock_run):
    """T040: test_find_usages_in_imports | Finds orphaned import statements | RED"""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='agentos/workflow.py:5:from agentos.types import WorkflowConfig\n'
    )
    
    usages = find_type_usages(
        'WorkflowConfig',
        [Path('/repo')],
        []
    )
    
    assert len(usages) == 1
    assert usages[0]['file_path'] == 'agentos/workflow.py'
    assert usages[0]['line_number'] == 5
    assert 'import WorkflowConfig' in usages[0]['line_content']


@patch('subprocess.run')
def test_find_usages_in_annotations(mock_run):
    """T050: test_find_usages_in_annotations | Finds orphaned type annotations | RED"""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='agentos/validator.py:12:def validate(cfg: WorkflowConfig) -> bool:\n'
    )
    
    usages = find_type_usages(
        'WorkflowConfig',
        [Path('/repo')],
        []
    )
    
    assert len(usages) == 1
    assert usages[0]['file_path'] == 'agentos/validator.py'
    assert usages[0]['line_number'] == 12
    assert 'WorkflowConfig' in usages[0]['line_content']


@patch('subprocess.run')
def test_excludes_docs_directory(mock_run):
    """T060: test_excludes_docs_directory | Does not flag docs references | RED"""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='docs/api.md:20:Example usage of WorkflowConfig\nagentos/main.py:5:from types import WorkflowConfig\n'
    )
    
    usages = find_type_usages(
        'WorkflowConfig',
        [Path('/repo')],
        ['docs/']
    )
    
    # Should only find the one in agentos/main.py
    assert len(usages) == 1
    assert 'docs/' not in usages[0]['file_path']


@patch('subprocess.run')
def test_excludes_lineage_directory(mock_run):
    """T070: test_excludes_lineage_directory | Does not flag lineage references | RED"""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='lineage/old_impl.py:10:old_cfg = WorkflowConfig()\nagentos/new.py:5:from types import WorkflowConfig\n'
    )
    
    usages = find_type_usages(
        'WorkflowConfig',
        [Path('/repo')],
        ['lineage/']
    )
    
    # Should only find the one in agentos/new.py
    assert len(usages) == 1
    assert 'lineage/' not in usages[0]['file_path']


@patch('subprocess.run')
def test_excludes_non_python_files(mock_run):
    """Test that non-.py files are excluded from results."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='README.md:5:WorkflowConfig example\nagentos/main.py:10:from types import WorkflowConfig\n'
    )
    
    usages = find_type_usages(
        'WorkflowConfig',
        [Path('/repo')],
        []
    )
    
    # Should only find .py file
    assert len(usages) == 1
    assert usages[0]['file_path'].endswith('.py')


@patch('subprocess.run')
def test_find_usages_timeout(mock_run):
    """T110: test_timeout_enforcement | Raises TimeoutError when timeout exceeded | RED"""
    mock_run.side_effect = subprocess.TimeoutExpired('git grep', 10.0)
    
    with pytest.raises(TimeoutError, match='exceeded 10.0s timeout'):
        find_type_usages(
            'WorkflowConfig',
            [Path('/repo')],
            [],
            timeout=10.0
        )


@patch('subprocess.run')
def test_find_usages_no_matches(mock_run):
    """Test that no usages returns empty list."""
    mock_run.return_value = MagicMock(
        returncode=1,  # git grep returns 1 when no matches
        stdout=''
    )
    
    usages = find_type_usages(
        'NonExistentType',
        [Path('/repo')],
        []
    )
    
    assert len(usages) == 0


# Unit Tests - Format Error Message
# ----------------------------------

def test_error_message_format():
    """T100: test_error_message_format | Error includes file, line, content | RED"""
    issues = [
        TypeRenameIssue(
            old_name='WorkflowConfig',
            definition_file='agentos/types.py',
            orphaned_usages=[
                OrphanedUsage(
                    file_path='agentos/workflow.py',
                    line_number=5,
                    line_content='from agentos.types import WorkflowConfig'
                ),
                OrphanedUsage(
                    file_path='agentos/validator.py',
                    line_number=12,
                    line_content='def validate(cfg: WorkflowConfig) -> bool:'
                )
            ]
        )
    ]
    
    message = format_type_rename_error(issues)
    
    assert 'TYPE RENAME CHECK FAILED' in message
    assert 'WorkflowConfig' in message
    assert 'agentos/types.py' in message
    assert 'agentos/workflow.py:5' in message
    assert 'agentos/validator.py:12' in message
    assert 'from agentos.types import WorkflowConfig' in message
    assert 'To fix:' in message


def test_error_message_multiple_issues():
    """Test error message with multiple type issues."""
    issues = [
        TypeRenameIssue(
            old_name='TypeA',
            definition_file='file_a.py',
            orphaned_usages=[
                OrphanedUsage(file_path='usage_a.py', line_number=1, line_content='import TypeA')
            ]
        ),
        TypeRenameIssue(
            old_name='TypeB',
            definition_file='file_b.py',
            orphaned_usages=[
                OrphanedUsage(file_path='usage_b.py', line_number=2, line_content='import TypeB')
            ]
        )
    ]
    
    message = format_type_rename_error(issues)
    
    assert 'TypeA' in message
    assert 'TypeB' in message
    assert 'file_a.py' in message
    assert 'file_b.py' in message


# Unit Tests - Log Summary
# -------------------------

@patch('agentos.nodes.check_type_renames.logger')
def test_log_scan_summary(mock_logger):
    """T120: test_log_scan_summary | Logs removed type count and files scanned | RED"""
    log_scan_summary(5, 150, 2)
    
    mock_logger.info.assert_called_once()
    log_message = mock_logger.info.call_args[0][0]
    
    assert '5 removed types' in log_message
    assert '150 files scanned' in log_message
    assert '2 orphaned usage issues' in log_message


# Integration Tests - Full Workflow
# ----------------------------------

@patch('subprocess.run')
def test_full_workflow_pass(mock_run):
    """T080: test_full_workflow_pass | Passes when all usages updated | RED"""
    # Mock git diff (has removed type)
    # Mock git rev-parse (repo root)
    # Mock git grep (no usages found)
    # Mock git ls-files (file count)
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout='diff --git a/types.py b/types.py\n-class OldClass:\n+class NewClass:\n'),
        MagicMock(returncode=0, stdout='/repo\n'),
        MagicMock(returncode=1, stdout=''),  # No usages found
        MagicMock(returncode=0, stdout='file1.py\nfile2.py\nfile3.py\n')
    ]
    
    state = {}
    result = check_type_renames(state)
    
    assert result['type_rename_check_passed'] is True
    assert result['type_rename_issues'] == []


@patch('subprocess.run')
def test_full_workflow_fail(mock_run):
    """T090: test_full_workflow_fail | Fails when orphaned usages exist | RED"""
    # Mock git diff (has removed type)
    # Mock git rev-parse (repo root)
    # Mock git grep (usages found)
    # Mock git ls-files (file count)
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout='diff --git a/types.py b/types.py\n-class OldClass:\n+class NewClass:\n'),
        MagicMock(returncode=0, stdout='/repo\n'),
        MagicMock(returncode=0, stdout='usage.py:10:from types import OldClass\n'),
        MagicMock(returncode=0, stdout='file1.py\nfile2.py\n')
    ]
    
    state = {}
    result = check_type_renames(state)
    
    assert result['type_rename_check_passed'] is False
    assert len(result['type_rename_issues']) == 1
    assert result['type_rename_issues'][0]['old_name'] == 'OldClass'
    assert 'error_message' in result
    assert 'TYPE RENAME CHECK FAILED' in result['error_message']


@patch('subprocess.run')
def test_workflow_no_removed_types(mock_run):
    """Test workflow when no types are removed."""
    # Mock git diff with no removed types
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='diff --git a/file.py b/file.py\n+# Just a comment\n'
    )
    
    state = {}
    result = check_type_renames(state)
    
    assert result['type_rename_check_passed'] is True
    assert result['type_rename_issues'] == []


@patch('subprocess.run')
def test_workflow_timeout_git_diff(mock_run):
    """Test timeout during git diff."""
    mock_run.side_effect = subprocess.TimeoutExpired('git diff', 10.0)
    
    state = {}
    
    with pytest.raises(TimeoutError, match='exceeded 10.0s timeout'):
        check_type_renames(state)


@patch('subprocess.run')
def test_workflow_timeout_git_grep(mock_run):
    """Test timeout during git grep search."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout='diff --git a/types.py b/types.py\n-class OldClass:\n'),
        MagicMock(returncode=0, stdout='/repo\n'),
        subprocess.TimeoutExpired('git grep', 10.0)
    ]
    
    state = {}
    
    with pytest.raises(TimeoutError, match='exceeded 10.0s timeout'):
        check_type_renames(state)


# Test Scenario Coverage
# ----------------------

def test_010(sample_diff_class):
    """010: Extract removed class | Auto | Diff with `-class Foo:` | `[("Foo", "file.py")]` | Correct extraction"""
    result = extract_removed_types(sample_diff_class)
    assert len(result) == 1
    assert result[0][0] == 'WorkflowConfig'
    assert result[0][1] == 'agentos/types.py'


def test_020(sample_diff_typeddict):
    """020: Extract TypedDict | Auto | Diff with `-Bar = TypedDict` | `[("Bar", "file.py")]` | Correct extraction"""
    result = extract_removed_types(sample_diff_typeddict)
    assert len(result) == 1
    assert result[0][0] == 'WorkflowState'
    assert result[0][1] == 'agentos/state.py'


def test_030(sample_diff_type_alias):
    """030: Extract type alias | Auto | Diff with `-MyType = Union[...]` | `[("MyType", "file.py")]` | Correct extraction"""
    result = extract_removed_types(sample_diff_type_alias)
    assert len(result) == 1
    assert result[0][0] == 'ConfigType'
    assert result[0][1] == 'agentos/utils.py'


@patch('subprocess.run')
def test_040(mock_run):
    """040: Find import usages | Auto | Codebase with `from x import Foo` | Usage detected | Found with location"""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='module.py:5:from x import Foo\n'
    )
    
    usages = find_type_usages('Foo', [Path('/repo')], [])
    
    assert len(usages) == 1
    assert usages[0]['file_path'] == 'module.py'
    assert usages[0]['line_number'] == 5


@patch('subprocess.run')
def test_050(mock_run):
    """050: Find annotation usages | Auto | Codebase with `def f(x: Foo)` | Usage detected | Found with location"""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='module.py:10:def f(x: Foo):\n'
    )
    
    usages = find_type_usages('Foo', [Path('/repo')], [])
    
    assert len(usages) == 1
    assert usages[0]['line_content'] == 'def f(x: Foo):'


@patch('subprocess.run')
def test_060(mock_run, mock_external_service):
    """060: Exclude docs | Auto | Usage in `docs/api.md` | Not reported | No false positive"""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='docs/api.md:10:Usage of Foo\n'
    )
    
    usages = find_type_usages('Foo', [Path('/repo')], ['docs/'])
    
    assert len(usages) == 0


@patch('subprocess.run')
def test_070(mock_run):
    """070: Exclude lineage | Auto | Usage in `lineage/old.py` | Not reported | No false positive"""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='lineage/old.py:15:old_foo = Foo()\n'
    )
    
    usages = find_type_usages('Foo', [Path('/repo')], ['lineage/'])
    
    assert len(usages) == 0


@patch('subprocess.run')
def test_080(mock_run):
    """080: Clean rename passes | Auto | All usages updated | `passed=True` | Workflow continues"""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout='diff --git a/a.py b/a.py\n-class Old:\n+class New:\n'),
        MagicMock(returncode=0, stdout='/repo\n'),
        MagicMock(returncode=1, stdout=''),
        MagicMock(returncode=0, stdout='a.py\n')
    ]
    
    result = check_type_renames({})
    
    assert result['type_rename_check_passed'] is True


@patch('subprocess.run')
def test_090(mock_run):
    """090: Orphaned usage fails | Auto | Missed usage exists | `passed=False` | Workflow stops"""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout='diff --git a/a.py b/a.py\n-class Old:\n+class New:\n'),
        MagicMock(returncode=0, stdout='/repo\n'),
        MagicMock(returncode=0, stdout='b.py:5:import Old\n'),
        MagicMock(returncode=0, stdout='a.py\nb.py\n')
    ]
    
    result = check_type_renames({})
    
    assert result['type_rename_check_passed'] is False


def test_100():
    """100: Error message quality | Auto | One orphaned usage | Message has file:line | Actionable output"""
    issues = [
        TypeRenameIssue(
            old_name='Foo',
            definition_file='a.py',
            orphaned_usages=[
                OrphanedUsage(file_path='b.py', line_number=10, line_content='import Foo')
            ]
        )
    ]
    
    message = format_type_rename_error(issues)
    
    assert 'b.py:10' in message
    assert 'Foo' in message


@patch('subprocess.run')
def test_110(mock_run, mock_external_service):
    """110: Timeout enforcement | Auto | Mock slow grep (>10s) | TimeoutError raised | Fail-safe works"""
    mock_run.side_effect = subprocess.TimeoutExpired('git grep', 10.0)
    
    with pytest.raises(TimeoutError):
        find_type_usages('Foo', [Path('/repo')], [], timeout=10.0)


@patch('agentos.nodes.check_type_renames.logger')
def test_120(mock_logger):
    """120: Observability logging | Auto | Normal execution | Log contains counts | Debugging enabled"""
    log_scan_summary(3, 100, 1)
    
    assert mock_logger.info.called
    log_msg = mock_logger.info.call_args[0][0]
    assert '3 removed types' in log_msg
    assert '100 files scanned' in log_msg
    assert '1 orphaned usage issues' in log_msg
```

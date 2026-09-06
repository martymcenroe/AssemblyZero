"""Tests for Issue #445/#468: TDD workflow path pre-flight validation.

Validates that validate_files_to_modify() catches stale LLD paths
before wasting Claude tokens on implementation. Issue #468 changed
Add behavior to auto-create parent directories instead of erroring.
"""

import pytest

from assemblyzero.workflows.testing.nodes.implement_code import (
    validate_files_to_modify,
)


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a minimal repo structure for path validation tests."""
    # Create src/module/ with a file
    (tmp_path / "src" / "module").mkdir(parents=True)
    (tmp_path / "src" / "module" / "existing.py").write_text("# existing", encoding="utf-8")
    # Create tests/unit/
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_existing.py").write_text("# test", encoding="utf-8")
    return tmp_path


def test_all_paths_valid_returns_empty(tmp_repo):
    """Modify exists + Add parent exists -> no errors."""
    files = [
        {"path": "src/module/existing.py", "change_type": "Modify"},
        {"path": "src/module/new_file.py", "change_type": "Add"},
    ]
    errors = validate_files_to_modify(files, tmp_repo)
    assert errors == []


def test_modify_file_missing_is_implemented_as_an_add(tmp_repo, capsys):
    """#2879: a Modify whose target is absent is an Add, not an error.

    This case asserted the refusal from #445 until run-issue4-193821, when
    the refusal ended a run that had cleared the gate, the design and the
    spec, five seconds into the implementation stage. The operator's #2736
    ruling -- the file list is a plan, not a contract -- governs the change
    type as it governs the path.
    """
    files = [
        {"path": "src/workflows/tdd/runner.py", "change_type": "Modify"},
    ]
    errors = validate_files_to_modify(files, tmp_repo)
    assert errors == []
    assert files[0]["change_type"] == "Add"
    assert (tmp_repo / "src" / "workflows" / "tdd").is_dir()
    assert "says Modify but the base has no src/workflows/tdd/runner.py" in capsys.readouterr().out


def test_delete_file_missing_returns_error(tmp_repo):
    """Missing file for Delete -> error."""
    files = [
        {"path": "src/old_module/deprecated.py", "change_type": "Delete"},
    ]
    errors = validate_files_to_modify(files, tmp_repo)
    assert len(errors) == 1
    assert "Delete target does not exist" in errors[0]


def test_add_parent_missing_auto_creates_dir(tmp_repo):
    """Issue #468: Missing parent for Add -> auto-create, no error."""
    files = [
        {"path": "src/nonexistent_pkg/new_file.py", "change_type": "Add"},
    ]
    errors = validate_files_to_modify(files, tmp_repo)
    assert errors == []
    assert (tmp_repo / "src" / "nonexistent_pkg").is_dir()


def test_add_parent_exists_returns_no_error(tmp_repo):
    """Valid Add with existing parent -> no error."""
    files = [
        {"path": "src/module/brand_new.py", "change_type": "Add"},
    ]
    errors = validate_files_to_modify(files, tmp_repo)
    assert errors == []


def test_multiple_errors_collected(tmp_repo):
    """All errors collected in one pass, not just the first."""
    files = [
        {"path": "src/bad_path/file1.py", "change_type": "Modify"},
        {"path": "src/bad_path/file2.py", "change_type": "Delete"},
        {"path": "src/no_parent/file3.py", "change_type": "Add"},
    ]
    errors = validate_files_to_modify(files, tmp_repo)
    # Delete errors; the Modify is coerced to an Add (#2879); both Adds
    # auto-create their parents (Issue #468).
    assert len(errors) == 1
    assert "Delete target does not exist" in errors[0]
    assert files[0]["change_type"] == "Add"
    assert (tmp_repo / "src" / "bad_path").is_dir()
    assert (tmp_repo / "src" / "no_parent").is_dir()


def test_empty_files_list_returns_empty(tmp_repo):
    """Edge case: empty list -> no errors."""
    errors = validate_files_to_modify([], tmp_repo)
    assert errors == []

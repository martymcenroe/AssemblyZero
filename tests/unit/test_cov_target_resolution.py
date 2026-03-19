"""Tests for --cov target resolution in the TDD pipeline.

Issue #474: TDD pipeline --cov module fallback fails for tools/ targets.

Verifies that _path_to_cov_target correctly distinguishes Python packages
(dotted module format) from standalone scripts (file path format), and
that the fallback in verify_green_phase infers the right scope.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes.verify_phases import _path_to_cov_target


# ---------------------------------------------------------------------------
# _path_to_cov_target — package paths (has __init__.py)
# ---------------------------------------------------------------------------


def test_package_path_returns_dotted_module(tmp_path: Path) -> None:
    """Package file → dotted module format."""
    (tmp_path / "assemblyzero" / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "assemblyzero" / "__init__.py").touch()

    result = _path_to_cov_target("assemblyzero/utils/file_type.py", tmp_path)
    assert result == "assemblyzero.utils.file_type"


def test_package_nested_path(tmp_path: Path) -> None:
    """Deeply nested package path → correct dotted module."""
    (tmp_path / "assemblyzero" / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "assemblyzero" / "__init__.py").touch()

    result = _path_to_cov_target("assemblyzero/workflows/testing/nodes/verify_phases.py", tmp_path)
    assert result == "assemblyzero.workflows.testing.nodes.verify_phases"


def test_src_layout_strips_prefix(tmp_path: Path) -> None:
    """src-layout project → strips src. prefix."""
    (tmp_path / "src" / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "__init__.py").touch()

    result = _path_to_cov_target("src/mypackage/core.py", tmp_path)
    assert result == "mypackage.core"


# ---------------------------------------------------------------------------
# _path_to_cov_target — standalone scripts (no __init__.py)
# ---------------------------------------------------------------------------


def test_tools_path_returns_file_path(tmp_path: Path) -> None:
    """tools/ script (no __init__.py) → file path format."""
    (tmp_path / "tools").mkdir(exist_ok=True)
    # No __init__.py in tools/

    result = _path_to_cov_target("tools/consolidate_logs.py", tmp_path)
    assert result == "tools/consolidate_logs.py"


def test_tools_nested_path(tmp_path: Path) -> None:
    """Nested tools/ script → file path with forward slashes."""
    (tmp_path / "tools").mkdir(exist_ok=True)

    result = _path_to_cov_target("tools/sub/my_script.py", tmp_path)
    assert result == "tools/sub/my_script.py"


def test_scripts_dir_returns_file_path(tmp_path: Path) -> None:
    """scripts/ directory (no __init__.py) → file path format."""
    (tmp_path / "scripts").mkdir(exist_ok=True)

    result = _path_to_cov_target("scripts/deploy.py", tmp_path)
    assert result == "scripts/deploy.py"


def test_no_repo_root_returns_file_path() -> None:
    """No repo_root → can't check __init__.py, returns file path."""
    result = _path_to_cov_target("tools/foo.py", None)
    assert result == "tools/foo.py"


# ---------------------------------------------------------------------------
# _path_to_cov_target — edge cases
# ---------------------------------------------------------------------------


def test_backslash_normalized(tmp_path: Path) -> None:
    """Windows backslashes → normalized to forward slashes in path mode."""
    (tmp_path / "tools").mkdir(exist_ok=True)

    result = _path_to_cov_target("tools\\my_script.py", tmp_path)
    assert "/" in result or "\\" not in result  # No backslashes in output


def test_non_py_file_keeps_extension(tmp_path: Path) -> None:
    """Non-.py file → keeps its extension in path mode."""
    (tmp_path / "tools").mkdir(exist_ok=True)

    result = _path_to_cov_target("tools/config.yml", tmp_path)
    assert result == "tools/config.yml"


# ---------------------------------------------------------------------------
# verify_green_phase fallback — integration tests
# ---------------------------------------------------------------------------


def _make_state(**overrides):
    """Minimal state dict for verify_green_phase."""
    base = {
        "test_files": ["/tmp/test_example.py"],
        "repo_root": "/tmp/repo",
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 42,
        "iteration_count": 0,
        "max_iterations": 10,
        "coverage_target": 90,
        "implementation_files": [],
        "skip_e2e": True,
    }
    base.update(overrides)
    return base


@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
@patch("assemblyzero.workflows.testing.nodes.verify_phases.get_repo_root")
def test_fallback_infers_tools_from_impl_files(mock_root, mock_pytest, tmp_path: Path) -> None:
    """Fallback uses top-level dir from impl_files when .py filter skips them."""
    (tmp_path / "tools").mkdir(exist_ok=True)
    # No __init__.py — tools/ is not a package
    mock_root.return_value = tmp_path

    mock_pytest.return_value = {
        "returncode": 0,
        "stdout": "1 passed",
        "stderr": "",
        "parsed": {"passed": 1, "failed": 0, "coverage": 95.0},
    }

    # impl_files has a .json file (skipped by .py filter) — fallback should still find "tools"
    state = _make_state(
        repo_root=str(tmp_path),
        implementation_files=["tools/config.json"],
    )

    from assemblyzero.workflows.testing.nodes.verify_phases import verify_green_phase
    verify_green_phase(state)

    # Check that the FIRST run_pytest call used coverage_module starting with "tools"
    # (Issue #842: second call is the full suite regression check with no coverage_module)
    call_args = mock_pytest.call_args_list[0]
    assert call_args is not None
    cov_module = call_args.kwargs.get("coverage_module") or call_args[1].get("coverage_module")
    if cov_module is None:
        # Positional arg
        cov_module = call_args[0][1] if len(call_args[0]) > 1 else None
    assert cov_module is not None
    assert cov_module.startswith("tools"), f"Expected 'tools' scope, got: {cov_module}"


@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
@patch("assemblyzero.workflows.testing.nodes.verify_phases.get_repo_root")
def test_tools_impl_file_uses_file_path_not_dotted(mock_root, mock_pytest, tmp_path: Path) -> None:
    """tools/*.py impl file → --cov gets file path, not dotted module."""
    (tmp_path / "tools").mkdir(exist_ok=True)
    mock_root.return_value = tmp_path

    mock_pytest.return_value = {
        "returncode": 0,
        "stdout": "1 passed",
        "stderr": "",
        "parsed": {"passed": 1, "failed": 0, "coverage": 95.0},
    }

    state = _make_state(
        repo_root=str(tmp_path),
        implementation_files=[str(tmp_path / "tools" / "consolidate_logs.py")],
    )

    from assemblyzero.workflows.testing.nodes.verify_phases import verify_green_phase
    verify_green_phase(state)

    # Issue #842: use first call (targeted tests), not last call (full suite check)
    call_args = mock_pytest.call_args_list[0]
    cov_module = call_args.kwargs.get("coverage_module") or call_args[1].get("coverage_module")
    if cov_module is None:
        cov_module = call_args[0][1] if len(call_args[0]) > 1 else None
    assert cov_module is not None
    assert "." not in cov_module or "/" in cov_module, (
        f"Expected file path format for tools/ target, got dotted module: {cov_module}"
    )


@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
@patch("assemblyzero.workflows.testing.nodes.verify_phases.get_repo_root")
def test_package_impl_file_uses_dotted_module(mock_root, mock_pytest, tmp_path: Path) -> None:
    """assemblyzero/*.py impl file → --cov gets dotted module (existing behavior)."""
    (tmp_path / "assemblyzero" / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "assemblyzero" / "__init__.py").touch()
    mock_root.return_value = tmp_path

    mock_pytest.return_value = {
        "returncode": 0,
        "stdout": "1 passed",
        "stderr": "",
        "parsed": {"passed": 1, "failed": 0, "coverage": 95.0},
    }

    state = _make_state(
        repo_root=str(tmp_path),
        implementation_files=[str(tmp_path / "assemblyzero" / "utils" / "file_type.py")],
    )

    from assemblyzero.workflows.testing.nodes.verify_phases import verify_green_phase
    verify_green_phase(state)

    # Issue #842: use first call (targeted tests), not last call (full suite check)
    call_args = mock_pytest.call_args_list[0]
    cov_module = call_args.kwargs.get("coverage_module") or call_args[1].get("coverage_module")
    if cov_module is None:
        cov_module = call_args[0][1] if len(call_args[0]) > 1 else None
    assert cov_module == "assemblyzero.utils.file_type"

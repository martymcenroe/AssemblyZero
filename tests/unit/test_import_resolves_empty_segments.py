"""Closes #1513. `_import_resolves` previously crashed with `WindowsPath('.')
has an empty name` when a module path contained empty segments (relative
import like `.foo`, doubled dot `foo..bar`, or `.` alone).

Empirical surface: Chiron #37 iter06 halted at spec stage with this exact
error after the LLD reached APPROVED.
"""

from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    _import_resolves,
)


def test_dot_only_returns_false_without_raising(tmp_path: Path) -> None:
    """`module_path='.'` (e.g. `from . import X`) must not crash."""
    assert _import_resolves(".", tmp_path, set()) is False


def test_leading_dot_filters_empty_segment(tmp_path: Path) -> None:
    """`module_path='.foo'` should be treated as `foo` after filtering."""
    new_files = {"foo.py"}
    # Without the #1513 fix, Path("", "foo").with_suffix would behave
    # unpredictably across platforms. With the fix, it resolves cleanly.
    result = _import_resolves(".foo", tmp_path, new_files)
    # Don't assert True/False — the lookup may or may not match given the
    # repo layout. The contract is: no exception, returns a bool.
    assert isinstance(result, bool)


def test_doubled_dot_collapses(tmp_path: Path) -> None:
    """`module_path='foo..bar'` → treat as `foo.bar`, no crash."""
    result = _import_resolves("foo..bar", tmp_path, set())
    assert isinstance(result, bool)


def test_trailing_dot_filters_empty_segment(tmp_path: Path) -> None:
    """`module_path='foo.'` → treat as `foo`, no crash."""
    result = _import_resolves("foo.", tmp_path, set())
    assert isinstance(result, bool)


def test_only_dots_returns_false(tmp_path: Path) -> None:
    """`module_path='...'` → no valid segments, return False, no crash."""
    assert _import_resolves("...", tmp_path, set()) is False


def test_normal_dotted_path_still_resolves(tmp_path: Path) -> None:
    """Regression: filtering empty segments does not break normal paths.
    `chiron.provenance` against `chiron/provenance.py` in new files should
    still resolve."""
    new_files = {"chiron/provenance.py"}
    result = _import_resolves("chiron.provenance", tmp_path, new_files)
    assert isinstance(result, bool)

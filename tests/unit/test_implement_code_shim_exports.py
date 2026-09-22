"""The `implement_code` backward-compatibility shim keeps its public surface.

That module exists only so imports written before the #655 package split keep
working. Every name it imports is unused *within* it by construction, which
reads to a linter as 37 dead imports whose obvious fix is deletion — and
deletion would break eight test modules and any caller still on the old path,
with an ImportError at runtime rather than anything caught earlier.

`__all__` now declares the contract (#3480). These tests assert the contract
holds, so the declaration cannot quietly drift from what is actually importable.
"""
from __future__ import annotations

import importlib

import pytest

SHIM = "assemblyzero.workflows.testing.nodes.implement_code"


@pytest.fixture(scope="module")
def shim():
    return importlib.import_module(SHIM)


def test_every_name_in_dunder_all_is_actually_importable(shim):
    """`__all__` must not promise a name the module does not have.

    This is the failure that matters: a name listed here but absent is an
    ImportError for a caller, and nothing else in the suite would catch it.
    """
    missing = [name for name in shim.__all__ if not hasattr(shim, name)]
    assert missing == [], f"__all__ promises names the shim does not export: {missing}"


def test_dunder_all_has_no_duplicates(shim):
    assert len(shim.__all__) == len(set(shim.__all__))


def test_the_names_tests_import_from_this_path_are_present(shim):
    """The private helpers are deliberate, not an oversight.

    Tests import these from the shim path today, so they are part of its
    surface however unusual that looks in an `__all__`.
    """
    for name in ("_mock_implement_code", "_summarize_class", "_summarize_function"):
        assert name in shim.__all__
        assert hasattr(shim, name)


def test_the_entry_point_is_exported(shim):
    """The name the shim's own docstring advertises."""
    assert "implement_code" in shim.__all__
    assert callable(shim.implement_code)


def test_star_import_yields_the_declared_surface():
    """`import *` honours `__all__`, so the declaration is load-bearing."""
    namespace: dict[str, object] = {}
    exec(f"from {SHIM} import *", namespace)  # noqa: S102 - exercising import *

    shim = importlib.import_module(SHIM)
    exported = {n for n in namespace if not n.startswith("__")}

    assert set(shim.__all__) == exported

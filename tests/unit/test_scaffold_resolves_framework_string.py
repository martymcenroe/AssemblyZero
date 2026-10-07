"""The scaffold reads the framework the checkpoint carries, string or enum (#3732).

#3708 made `framework_config` checkpoint-safe: the framework is stored as its
string value. `TestFramework` is a plain Enum, so `"pytest" != TestFramework.PYTEST`,
and `scaffold_tests` compared the raw value against the enum. Every pytest
repository was sent down the TypeScript path and died with "Cannot generate TS
content for framework: pytest" (boostgauge #2, run-issue2-230238, 2026-10-06).
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.runner_registry import (
    checkpoint_safe,
    get_framework_config,
    resolve_framework,
)

FRAMEWORKS = list(TestFramework)

# The nodes package re-exports the `scaffold_tests` FUNCTION under the module's
# name, so `from ...nodes import scaffold_tests` is the function, not the module.
scaffold_mod = importlib.import_module("assemblyzero.workflows.testing.nodes.scaffold_tests")


class _PytestPathTaken(Exception):
    """Raised by the patched `get_repo_root`, which only the pytest path calls."""


@pytest.fixture
def routed(monkeypatch):
    """Run `scaffold_tests` and report which path it took, and with what."""
    seen: dict = {}

    def fake_non_python(state, framework_config):
        seen["path"] = "non-python"
        seen["framework"] = framework_config["framework"]
        return {}

    def fake_repo_root():
        raise _PytestPathTaken

    monkeypatch.setattr(scaffold_mod, "_scaffold_non_python_tests", fake_non_python)
    monkeypatch.setattr(scaffold_mod, "get_repo_root", fake_repo_root)

    def run(framework_config):
        state = {"framework_config": framework_config, "issue_number": 2, "repo_root": ""}
        try:
            scaffold_mod.scaffold_tests(state)
        except _PytestPathTaken:
            seen["path"] = "pytest"
        return seen

    return run


def test_a_checkpointed_pytest_config_takes_the_pytest_path(routed):
    """The boostgauge #2 failure: the string "pytest" must not reach the TS path."""
    config = checkpoint_safe(get_framework_config(TestFramework.PYTEST))
    assert config["framework"] == "pytest"
    assert routed(config)["path"] == "pytest"


def test_an_enum_pytest_config_takes_the_pytest_path(routed):
    """A checkpoint written before #3708 still carries the enum."""
    assert routed(get_framework_config(TestFramework.PYTEST))["path"] == "pytest"


def test_no_framework_config_takes_the_pytest_path(routed):
    assert routed(None)["path"] == "pytest"


@pytest.mark.parametrize(
    "framework", [TestFramework.PLAYWRIGHT, TestFramework.JEST, TestFramework.VITEST]
)
def test_a_checkpointed_ts_config_reaches_the_ts_path_with_the_enum(routed, framework):
    """The non-Python path reads `.value` and calls `get_runner`; it gets the enum."""
    seen = routed(checkpoint_safe(get_framework_config(framework)))
    assert seen["path"] == "non-python"
    assert seen["framework"] is framework


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_resolve_framework_reads_the_enum_and_its_string(framework):
    assert resolve_framework({"framework": framework}) is framework
    assert resolve_framework({"framework": framework.value}) is framework


@pytest.mark.parametrize("config", [{"framework": "nonsense"}, {"framework": None}, {}, None])
def test_resolve_framework_is_none_for_anything_else(config):
    assert resolve_framework(config) is None


TESTING_PACKAGE = (
    Path(__file__).resolve().parents[2] / "assemblyzero" / "workflows" / "testing"
)


def _raw_framework_comparisons(source: str) -> list[int]:
    """Lines comparing `x.get("framework")` or `x["framework"]` directly to a
    `TestFramework` member, the shape #3732 removed."""

    def is_raw_read(node: ast.AST) -> bool:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            return (
                node.func.attr == "get"
                and bool(node.args)
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "framework"
            )
        if isinstance(node, ast.Subscript):
            return isinstance(node.slice, ast.Constant) and node.slice.value == "framework"
        return False

    def names_member(node: ast.AST) -> bool:
        return any(
            isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "TestFramework"
            for n in ast.walk(node)
        )

    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            if any(is_raw_read(s) for s in sides) and any(names_member(s) for s in sides):
                lines.append(node.lineno)
    return lines


def test_no_node_compares_the_raw_framework_to_the_enum():
    """Every reader goes through `resolve_framework`; a raw comparison is the bug.

    Runners and the registry are exempt: they read configs the registry built,
    which always carry the enum.
    """
    offenders = {}
    for path in sorted((TESTING_PACKAGE / "nodes").rglob("*.py")):
        lines = _raw_framework_comparisons(path.read_text(encoding="utf-8"))
        if lines:
            offenders[path.name] = lines
    assert offenders == {}

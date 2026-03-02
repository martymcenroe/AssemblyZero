"""Tests verifying no new external dependencies are introduced.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


# Python 3.10+ provides sys.stdlib_module_names
STDLIB_MODULES = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()
INTERNAL_PREFIXES = ("assemblyzero",)

# Fallback for pre-3.10: list well-known stdlib top-level modules
if not STDLIB_MODULES:
    STDLIB_MODULES = {
        "__future__", "abc", "ast", "asyncio", "collections", "contextlib",
        "copy", "csv", "dataclasses", "datetime", "decimal", "enum",
        "functools", "glob", "hashlib", "importlib", "inspect", "io",
        "itertools", "json", "logging", "math", "os", "pathlib", "pickle",
        "platform", "pprint", "re", "shutil", "signal", "socket",
        "sqlite3", "string", "struct", "subprocess", "sys", "tempfile",
        "textwrap", "threading", "time", "traceback", "typing", "unittest",
        "urllib", "uuid", "warnings", "xml",
    }


def _get_repo_root() -> Path:
    """Find repo root from test file location."""
    return Path(__file__).resolve().parents[3]


class TestNoDependencyCreep:
    """Tests that spelunking introduces no external dependencies."""

    def test_T360_no_external_imports(self) -> None:
        """T360: All imports in spelunking/*.py and new probes resolve to stdlib or internal.

        Scans all Python files in:
        - assemblyzero/spelunking/*.py
        - assemblyzero/workflows/janitor/probes/{inventory_drift,dead_references,
          adr_collision,stale_timestamps,readme_claims,persona_status}.py

        For each file, parses the AST and checks every import statement.
        Any import whose top-level module is not in sys.stdlib_module_names
        and does not start with 'assemblyzero' is flagged as third-party.

        Input: No arguments (scans files on disk).
        Output on success: Test passes (no assertion errors).
        Output on failure: AssertionError listing the third-party imports found.
          Example: AssertionError("Third-party imports found: 'chromadb' in assemblyzero/spelunking/engine.py")
        """
        repo_root = _get_repo_root()

        spelunking_dir = repo_root / "assemblyzero" / "spelunking"
        spelunking_files = list(spelunking_dir.glob("*.py")) if spelunking_dir.exists() else []

        probe_names = [
            "inventory_drift.py",
            "dead_references.py",
            "adr_collision.py",
            "stale_timestamps.py",
            "readme_claims.py",
            "persona_status.py",
        ]
        probe_dir = repo_root / "assemblyzero" / "workflows" / "janitor" / "probes"
        probe_files = [
            probe_dir / name for name in probe_names
            if (probe_dir / name).exists()
        ]

        all_files = spelunking_files + probe_files
        third_party: list[str] = []

        for file_path in all_files:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if (
                            top not in STDLIB_MODULES
                            and not any(alias.name.startswith(p) for p in INTERNAL_PREFIXES)
                        ):
                            rel = file_path.relative_to(repo_root)
                            third_party.append(f"'{alias.name}' in {rel}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    if (
                        top not in STDLIB_MODULES
                        and not any(node.module.startswith(p) for p in INTERNAL_PREFIXES)
                    ):
                        rel = file_path.relative_to(repo_root)
                        third_party.append(f"'{node.module}' in {rel}")

        assert not third_party, f"Third-party imports found: {', '.join(third_party)}"

    def test_T365_pyproject_unchanged(self) -> None:
        """T365: No new entries in pyproject.toml dependencies.

        This test reads pyproject.toml and checks that no spelunking-related
        imports appear as new dependencies. The spelunking package must use
        only stdlib + existing project deps, verified via T360's AST check.
        This test confirms no spelunking-specific packages were added.
        """
        repo_root = _get_repo_root()
        pyproject = repo_root / "pyproject.toml"

        if not pyproject.exists():
            pytest.skip("pyproject.toml not found")

        content = pyproject.read_text(encoding="utf-8")

        # Check that no spelunking-specific packages were added.
        # These are packages that would only be needed for spelunking
        # (not existing project dependencies like langchain).
        spelunking_specific_deps = [
            "tree-sitter",
            "ast-grep",
            "docparser",
            "markdownify",
        ]

        found = []
        for dep in spelunking_specific_deps:
            if dep in content.lower():
                found.append(dep)

        assert not found, (
            f"Spelunking-specific dependencies found in pyproject.toml: {', '.join(found)}"
        )
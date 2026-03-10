"""Regression tests for circular import detection.

Issue #462: A circular import between hooks and telemetry packages
was discovered at runtime when any tool tried to import telemetry.
These tests ensure no package-level import triggers a circular
dependency, using real imports in isolated subprocesses.

NO MOCKING — these tests run real imports in fresh Python processes
to detect actual circular import failures.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Every assemblyzero subpackage with an __init__.py that does eager imports.
# If a new package is added, add it here.
ALL_SUBPACKAGES = [
    "assemblyzero",
    "assemblyzero.core",
    "assemblyzero.core.validation",
    "assemblyzero.graphs",
    "assemblyzero.hooks",
    "assemblyzero.nodes",
    "assemblyzero.telemetry",
    "assemblyzero.utils",
    "assemblyzero.workflows",
    "assemblyzero.workflows.implementation_spec",
    "assemblyzero.workflows.implementation_spec.nodes",
    "assemblyzero.workflows.orchestrator",
    "assemblyzero.workflows.parallel",
    "assemblyzero.workflows.requirements",
    "assemblyzero.workflows.requirements.nodes",
    "assemblyzero.workflows.requirements.parsers",
    "assemblyzero.workflows.scout",
    "assemblyzero.workflows.testing",
    "assemblyzero.workflows.testing.completeness",
    "assemblyzero.workflows.testing.knowledge",
    "assemblyzero.workflows.testing.nodes",
    "assemblyzero.workflows.testing.templates",
]


class TestNoCircularImports:
    """Each subpackage must import without ImportError in a clean process.

    Uses subprocess to ensure a fresh Python interpreter with no cached
    modules — this is the only reliable way to detect circular imports,
    since pytest's process may have already imported modules in a
    non-circular order.
    """

    @pytest.mark.parametrize("package", ALL_SUBPACKAGES)
    def test_subpackage_imports_cleanly(self, package: str) -> None:
        """Import each subpackage in an isolated subprocess."""
        result = subprocess.run(
            [sys.executable, "-c", f"import {package}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Importing '{package}' failed with:\n"
            f"STDERR: {result.stderr}\n"
            f"STDOUT: {result.stdout}"
        )


class TestHooksTelemetryCrossImport:
    """Regression test for the specific hooks <-> telemetry circular import.

    The original bug (Issue #462):
      telemetry/__init__ -> cascade_events -> hooks.types
      -> hooks/__init__ -> cascade_action -> telemetry.cascade_events (boom)

    This test verifies the fix (lazy import in cascade_action.py) holds.
    """

    def test_import_telemetry_then_hooks(self) -> None:
        """Import telemetry first, then hooks — the order that triggered the bug."""
        code = (
            "import assemblyzero.telemetry\n"
            "import assemblyzero.hooks\n"
            "print('OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"telemetry-then-hooks import failed:\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_import_hooks_then_telemetry(self) -> None:
        """Import hooks first, then telemetry — reverse order."""
        code = (
            "import assemblyzero.hooks\n"
            "import assemblyzero.telemetry\n"
            "print('OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"hooks-then-telemetry import failed:\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_cascade_action_calls_telemetry_at_runtime(self) -> None:
        """Verify cascade_action can actually call telemetry functions at runtime.

        The lazy import must resolve correctly when the function runs,
        not just when the module loads.
        """
        code = (
            "from assemblyzero.hooks.cascade_action import handle_cascade_detection\n"
            "from assemblyzero.hooks.types import CascadeDetectionResult, CascadeRiskLevel\n"
            "result = CascadeDetectionResult(\n"
            "    detected=True,\n"
            "    risk_level=CascadeRiskLevel.MEDIUM,\n"
            "    matched_patterns=['CP-031'],\n"
            "    matched_text='test',\n"
            "    recommended_action='block_and_prompt',\n"
            "    confidence=0.6,\n"
            ")\n"
            "blocked = handle_cascade_detection(result, 'test-session', 'test output')\n"
            "assert blocked is False, f'Expected False, got {blocked}'\n"
            "print('OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Runtime call to handle_cascade_detection failed:\n{result.stderr}"
        )
        assert "OK" in result.stdout


class TestImportOrderIndependence:
    """Verify that common cross-package import orders don't create cycles.

    Circular imports often only fail in specific import orders.
    Test several common entry points.
    """

    @pytest.mark.parametrize(
        "first,second",
        [
            ("assemblyzero.telemetry", "assemblyzero.hooks"),
            ("assemblyzero.hooks", "assemblyzero.telemetry"),
            ("assemblyzero.core", "assemblyzero.telemetry"),
            ("assemblyzero.telemetry", "assemblyzero.core"),
            ("assemblyzero.hooks", "assemblyzero.core"),
            ("assemblyzero.core", "assemblyzero.hooks"),
            ("assemblyzero.utils", "assemblyzero.core"),
            ("assemblyzero.core", "assemblyzero.utils"),
        ],
    )
    def test_cross_package_import_order(self, first: str, second: str) -> None:
        """Import two packages in sequence — must not trigger circular import."""
        code = f"import {first}\nimport {second}\nprint('OK')"
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Import order {first} -> {second} failed:\n{result.stderr}"
        )

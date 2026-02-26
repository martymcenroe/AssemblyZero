"""Unit tests for framework detection.

Issue #381: Tests T010-T070 from LLD Section 10.0.
"""

import json
import tempfile
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
    detect_framework_from_lld,
    detect_framework_from_project,
    resolve_framework,
)


class TestDetectFrameworkFromLLD:
    """Tests for detect_framework_from_lld()."""

    def test_t010_detects_playwright_from_spec_ts(self):
        """T010: detect_framework_from_lld identifies Playwright from .spec.ts."""
        lld = """## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `tests/dashboard.spec.ts` | Add |
"""
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_t020_detects_jest_from_test_ts(self):
        """T020: detect_framework_from_lld identifies Jest from .test.ts."""
        lld = """## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `tests/utils.test.ts` | Add |
"""
        assert detect_framework_from_lld(lld) == TestFramework.JEST

    def test_t030_defaults_to_pytest(self):
        """T030: detect_framework_from_lld defaults to pytest."""
        lld = """## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `src/pipeline.py` | Add |
"""
        assert detect_framework_from_lld(lld) == TestFramework.PYTEST

    def test_t040_explicit_playwright_declaration(self):
        """T040: detect_framework_from_lld handles explicit declaration."""
        lld = """## 10. Verification & Testing
Test Framework: Playwright
"""
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_explicit_jest_declaration(self):
        """Detect Jest from explicit declaration."""
        lld = "Test Framework: Jest\nSome other content."
        assert detect_framework_from_lld(lld) == TestFramework.JEST

    def test_explicit_vitest_declaration(self):
        """Detect Vitest from explicit declaration."""
        lld = "Test Framework: Vitest"
        assert detect_framework_from_lld(lld) == TestFramework.VITEST

    def test_explicit_pytest_declaration(self):
        """Detect pytest from explicit declaration."""
        lld = "Test Framework: pytest"
        assert detect_framework_from_lld(lld) == TestFramework.PYTEST

    def test_empty_lld_defaults_to_pytest(self):
        """Empty LLD returns pytest."""
        assert detect_framework_from_lld("") == TestFramework.PYTEST

    def test_playwright_keyword_detection(self):
        """Detect Playwright from @playwright/test keyword."""
        lld = "We use @playwright/test for e2e testing."
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_npx_playwright_command(self):
        """Detect Playwright from npx command in LLD."""
        lld = "Run `npx playwright test` to execute."
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_spec_js_detected_as_playwright(self):
        """Detect Playwright from .spec.js file pattern."""
        lld = "| `tests/app.spec.js` | Add |"
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT


class TestDetectFrameworkFromProject:
    """Tests for detect_framework_from_project()."""

    def test_t050_playwright_config_file(self):
        """T050: detect_framework_from_project finds playwright.config.ts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "playwright.config.ts").touch()
            assert detect_framework_from_project(tmpdir) == TestFramework.PLAYWRIGHT

    def test_t060_jest_in_package_json(self):
        """T060: detect_framework_from_project finds jest in package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"scripts": {"test": "jest --coverage"}}
            Path(tmpdir, "package.json").write_text(json.dumps(pkg))
            assert detect_framework_from_project(tmpdir) == TestFramework.JEST

    def test_vitest_in_package_json(self):
        """Detect Vitest from package.json scripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"scripts": {"test": "vitest run"}}
            Path(tmpdir, "package.json").write_text(json.dumps(pkg))
            assert detect_framework_from_project(tmpdir) == TestFramework.VITEST

    def test_jest_config_file(self):
        """Detect Jest from jest.config.ts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "jest.config.ts").touch()
            assert detect_framework_from_project(tmpdir) == TestFramework.JEST

    def test_vitest_config_file(self):
        """Detect Vitest from vitest.config.ts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "vitest.config.ts").touch()
            assert detect_framework_from_project(tmpdir) == TestFramework.VITEST

    def test_pyproject_toml_pytest(self):
        """Detect pytest from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
            assert detect_framework_from_project(tmpdir) == TestFramework.PYTEST

    def test_nonexistent_directory(self):
        """Non-existent directory returns None."""
        assert detect_framework_from_project("/nonexistent/path/xyz") is None

    def test_empty_directory(self):
        """Empty directory returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert detect_framework_from_project(tmpdir) is None

    def test_ambiguous_multiple_configs(self):
        """Multiple config files returns None (ambiguous)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "playwright.config.ts").touch()
            Path(tmpdir, "jest.config.ts").touch()
            assert detect_framework_from_project(tmpdir) is None

    def test_invalid_package_json(self):
        """Malformed package.json is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package.json").write_text("not valid json")
            assert detect_framework_from_project(tmpdir) is None


class TestResolveFramework:
    """Tests for resolve_framework()."""

    def test_t070_lld_overrides_project(self):
        """T070: LLD overrides project detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "jest.config.ts").touch()
            lld = "Test Framework: Playwright"
            assert resolve_framework(lld, tmpdir) == TestFramework.PLAYWRIGHT

    def test_project_fallback_when_lld_default(self):
        """When LLD detects default pytest, project files can override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "playwright.config.ts").touch()
            lld = "Some generic LLD without framework indicators."
            assert resolve_framework(lld, tmpdir) == TestFramework.PLAYWRIGHT

    def test_both_default_returns_pytest(self):
        """When both LLD and project have no indicators, return pytest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert resolve_framework("No indicators here.", tmpdir) == TestFramework.PYTEST

    def test_empty_project_root(self):
        """Empty project root skips project detection."""
        lld = "Test Framework: Jest"
        assert resolve_framework(lld, "") == TestFramework.JEST
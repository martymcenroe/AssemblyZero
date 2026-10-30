"""A pytest dev dependency is not a pytest suite (#3001).

`detect_framework_dirs` counted the bare word `pytest` anywhere in
`pyproject.toml` as a pytest project. Every Python repository that lists
pytest as a dev dependency matched, so a JavaScript project with a tooling
`pyproject.toml` was detected as pytest too, and pytest -- found at the root
before the subdirectories -- came first and was the framework the run kept.

pytest is detected from a declaration (a `[tool.pytest` section, a
`pytest.ini`, a `[tool:pytest]` section in setup.cfg, a `[pytest]` section in
tox.ini, a `conftest.py`) or from Python test files the root or its tests
directory actually holds.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from assemblyzero.workflows.testing import framework_detector as fd

TF = fd.TestFramework

DEV_DEPENDENCY_ONLY = (
    "[tool.poetry]\nname = \"tooling\"\n\n"
    "[tool.poetry.group.dev.dependencies]\n"
    "pytest = \"^8.3.0\"\npytest-cov = \"^5.0.0\"\n"
)


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestADependencyLineIsNotASuite:
    def test_a_playwright_project_with_a_tooling_pyproject_is_playwright(self, tmp_path):
        _write(tmp_path / "playwright.config.ts")
        _write(tmp_path / "pyproject.toml", DEV_DEPENDENCY_ONLY)
        assert fd.detect_framework_from_project(str(tmp_path)) == [TF.PLAYWRIGHT]

    def test_the_dependency_no_longer_outvotes_the_web_runner(self, tmp_path):
        """With Vitest in web/ and pytest only as a dependency, the run's
        first framework is Vitest, not pytest."""
        _write(tmp_path / "pyproject.toml", DEV_DEPENDENCY_ONLY)
        _write(tmp_path / "web" / "package.json",
               json.dumps({"scripts": {"test": "vitest run"}}))
        assert fd.resolve_framework("No framework named here.", str(tmp_path)) == [TF.VITEST]

    def test_a_pyproject_mentioning_pytest_in_prose_is_nothing(self, tmp_path):
        _write(tmp_path / "pyproject.toml", "# we used to run pytest here\n")
        assert fd.detect_framework_dirs(str(tmp_path)) == {}


class TestADeclarationOrATestFileIsASuite:
    @pytest.mark.parametrize("name, text", [
        ("pyproject.toml", "[tool.pytest.ini_options]\naddopts = \"-q\"\n"),
        ("pytest.ini", "[pytest]\n"),
        ("setup.cfg", "[tool:pytest]\ntestpaths = tests\n"),
        ("tox.ini", "[pytest]\naddopts = -q\n"),
        ("conftest.py", ""),
    ])
    def test_a_declaration(self, tmp_path, name, text):
        _write(tmp_path / name, text)
        assert fd.detect_framework_dirs(str(tmp_path)) == {TF.PYTEST: "."}

    @pytest.mark.parametrize("relative", [
        "test_cli.py",
        "tests/test_engine.py",
        "tests/unit/test_engine.py",
        "test/engine_test.py",
        "tests/conftest.py",
    ])
    def test_python_tests_on_disk(self, tmp_path, relative):
        _write(tmp_path / "pyproject.toml", DEV_DEPENDENCY_ONLY)
        _write(tmp_path / relative)
        assert fd.detect_framework_dirs(str(tmp_path)) == {TF.PYTEST: "."}

    def test_a_python_suite_beside_a_web_suite_is_both(self, tmp_path):
        """The mixed target this work is for: pytest at the root by its test
        files, Vitest in web/."""
        _write(tmp_path / "pyproject.toml", DEV_DEPENDENCY_ONLY)
        _write(tmp_path / "tests" / "test_engine.py")
        _write(tmp_path / "web" / "vitest.config.ts")
        assert fd.detect_framework_dirs(str(tmp_path)) == {
            TF.PYTEST: ".", TF.VITEST: "web",
        }

    def test_a_python_file_in_node_modules_is_not_a_suite(self, tmp_path):
        _write(tmp_path / "tests" / "node_modules" / "pkg" / "test_x.py")
        assert TF.PYTEST not in fd.detect_framework_dirs(str(tmp_path))

"""Tests for the Dependency Modernization Tool.

Issue #351: Automated dependency update cycles with rollback.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

# Import under test — we need to add tools/ to sys.path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from modernize_dependencies import (
    commit_update,
    discover_outdated,
    modernize,
    restore_lockfiles,
    save_lockfiles,
    update_package,
)


SAMPLE_POETRY_OUTPUT = """\
langchain-core  0.3.50  0.3.52  Core APIs for LangChain
chromadb        0.6.3   0.6.5   Chroma AI native vector database
ruff            0.9.9   0.11.0  An extremely fast linter
"""

SAMPLE_POETRY_OUTPUT_WITH_MARKER = """\
pydantic  2.10.6  (!)  2.11.0  Data validation
ruff      0.9.9        0.11.0  An extremely fast linter
"""


class TestDiscoverOutdated:
    """Tests for discover_outdated()."""

    @mock.patch("modernize_dependencies.subprocess.run")
    def test_parses_standard_output(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_POETRY_OUTPUT, stderr=""
        )
        result = discover_outdated(tmp_path)
        assert len(result) == 3
        assert result[0]["name"] == "langchain-core"
        assert result[0]["current"] == "0.3.50"
        assert result[0]["latest"] == "0.3.52"

    @mock.patch("modernize_dependencies.subprocess.run")
    def test_handles_bang_marker(self, mock_run, tmp_path):
        """Packages with (!) semver-incompatible marker are parsed correctly."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_POETRY_OUTPUT_WITH_MARKER, stderr=""
        )
        result = discover_outdated(tmp_path)
        assert len(result) == 2
        assert result[0]["name"] == "pydantic"
        assert result[0]["latest"] == "2.11.0"

    @mock.patch("modernize_dependencies.subprocess.run")
    def test_empty_output(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        result = discover_outdated(tmp_path)
        assert result == []

    @mock.patch("modernize_dependencies.subprocess.run")
    def test_command_failure(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        result = discover_outdated(tmp_path)
        assert result == []


class TestSaveRestoreLockfiles:
    """Tests for save/restore lockfile functions."""

    def test_roundtrip(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        lock = tmp_path / "poetry.lock"
        pyproject.write_text("[tool.poetry]\nname = 'test'\n")
        lock.write_text("[[package]]\nname = 'foo'\n")

        saved_pyproject, saved_lock = save_lockfiles(tmp_path)

        # Modify files
        pyproject.write_text("modified")
        lock.write_text("modified")

        with mock.patch("modernize_dependencies.subprocess.run"):
            restore_lockfiles(tmp_path, saved_pyproject, saved_lock)

        assert pyproject.read_text() == "[tool.poetry]\nname = 'test'\n"
        assert lock.read_text() == "[[package]]\nname = 'foo'\n"

    def test_missing_lock(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.poetry]")

        saved_pyproject, saved_lock = save_lockfiles(tmp_path)
        assert saved_lock == ""


class TestUpdatePackage:
    """Tests for update_package()."""

    @mock.patch("modernize_dependencies.subprocess.run")
    def test_success(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Updated ruff to 0.11.0", stderr=""
        )
        success, output = update_package(tmp_path, "ruff")
        assert success is True
        assert "Updated" in output

    @mock.patch("modernize_dependencies.subprocess.run")
    def test_failure(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Conflict"
        )
        success, output = update_package(tmp_path, "bad-pkg")
        assert success is False


class TestModernize:
    """Tests for the main modernize() function."""

    @mock.patch("modernize_dependencies.commit_update")
    @mock.patch("modernize_dependencies.run_tests")
    @mock.patch("modernize_dependencies.update_package")
    @mock.patch("modernize_dependencies.restore_lockfiles")
    @mock.patch("modernize_dependencies.save_lockfiles")
    @mock.patch("modernize_dependencies.discover_outdated")
    def test_update_pass_commit(self, mock_discover, mock_save, mock_restore,
                                 mock_update, mock_tests, mock_commit, tmp_path):
        """Happy path: discover → update → tests pass → commit."""
        mock_discover.return_value = [{"name": "ruff", "current": "0.9.9", "latest": "0.11.0"}]
        mock_save.return_value = ("pyproject", "lock")
        mock_update.return_value = (True, "ok")
        mock_tests.return_value = (True, "all passed")
        mock_commit.return_value = True

        report_file = tmp_path / "report.json"
        report = modernize(tmp_path, report_file=report_file)

        assert report["summary"]["updated"] == 1
        assert report["summary"]["failed"] == 0
        assert report["packages"][0]["status"] == "updated"
        assert report_file.exists()

    @mock.patch("modernize_dependencies.commit_update")
    @mock.patch("modernize_dependencies.run_tests")
    @mock.patch("modernize_dependencies.update_package")
    @mock.patch("modernize_dependencies.restore_lockfiles")
    @mock.patch("modernize_dependencies.save_lockfiles")
    @mock.patch("modernize_dependencies.discover_outdated")
    def test_update_fail_rollback(self, mock_discover, mock_save, mock_restore,
                                   mock_update, mock_tests, mock_commit, tmp_path):
        """Tests fail after update → rollback."""
        mock_discover.return_value = [{"name": "ruff", "current": "0.9.9", "latest": "0.11.0"}]
        mock_save.return_value = ("pyproject", "lock")
        mock_update.return_value = (True, "ok")
        mock_tests.return_value = (False, "FAILED test_foo.py")

        report_file = tmp_path / "report.json"
        report = modernize(tmp_path, report_file=report_file)

        assert report["summary"]["failed"] == 1
        assert report["packages"][0]["status"] == "tests_failed"
        mock_restore.assert_called_once()

    @mock.patch("modernize_dependencies.restore_lockfiles")
    @mock.patch("modernize_dependencies.save_lockfiles")
    @mock.patch("modernize_dependencies.update_package")
    @mock.patch("modernize_dependencies.discover_outdated")
    def test_poetry_add_fail_skip(self, mock_discover, mock_update,
                                   mock_save, mock_restore, tmp_path):
        """poetry add fails → skip and restore."""
        mock_discover.return_value = [{"name": "bad", "current": "1.0", "latest": "2.0"}]
        mock_save.return_value = ("pyproject", "lock")
        mock_update.return_value = (False, "Conflict resolution failed")

        report_file = tmp_path / "report.json"
        report = modernize(tmp_path, report_file=report_file)

        assert report["summary"]["failed"] == 1
        assert report["packages"][0]["status"] == "add_failed"
        mock_restore.assert_called_once()

    @mock.patch("modernize_dependencies.discover_outdated")
    def test_dry_run(self, mock_discover, tmp_path):
        """Dry run lists packages without updating."""
        mock_discover.return_value = [
            {"name": "ruff", "current": "0.9.9", "latest": "0.11.0"},
        ]

        report_file = tmp_path / "report.json"
        report = modernize(tmp_path, dry_run=True, report_file=report_file)

        assert report["summary"]["skipped"] == 1
        assert report["summary"]["updated"] == 0
        assert report["packages"][0]["status"] == "dry_run"

    @mock.patch("modernize_dependencies.discover_outdated")
    def test_report_only(self, mock_discover, tmp_path):
        """Report-only mode generates report without updates."""
        mock_discover.return_value = [
            {"name": "ruff", "current": "0.9.9", "latest": "0.11.0"},
        ]

        report_file = tmp_path / "report.json"
        report = modernize(tmp_path, report_only=True, report_file=report_file)

        assert report["packages"][0]["status"] == "report_only"
        # Verify report file is valid JSON
        data = json.loads(report_file.read_text())
        assert data["summary"]["total"] == 1

    @mock.patch("modernize_dependencies.discover_outdated")
    def test_package_filter(self, mock_discover, tmp_path):
        """Package filter only processes the specified package."""
        mock_discover.return_value = [
            {"name": "ruff", "current": "0.9.9", "latest": "0.11.0"},
            {"name": "pytest", "current": "8.0", "latest": "9.0"},
        ]

        report_file = tmp_path / "report.json"
        report = modernize(tmp_path, dry_run=True, package_filter="ruff", report_file=report_file)

        assert report["summary"]["total"] == 1
        assert report["packages"][0]["name"] == "ruff"

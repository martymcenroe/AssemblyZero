"""framework_detector.py under standard 0034, one test per sweep site (#3585).

The detector tells N0 which test frameworks a target has and where. A
package.json it cannot read (215) and a `test_dirs` declaration naming no
framework (252) already raised, but said nothing at the point of failure;
each now prints an ERROR line before the raise, which N0 turns into a halt
that alerts. A project root that does not exist (273) came back as no
frameworks at all, which the callers above read as "default to pytest"; it
now raises FrameworkResolutionError naming the path, after an ERROR line.

Every test works in a temporary directory. Line numbers in the names are
ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import json

import pytest

from assemblyzero.workflows.testing import framework_detector as fd


class TestAnUnreadablePackageJson:
    def test_215_an_unreadable_package_json_is_loud_and_raises(self, tmp_path, capsys):
        (tmp_path / "package.json").write_text("{not json", encoding="utf-8")

        with pytest.raises(ValueError, match="package.json could not be read"):
            fd.detect_framework_dirs(str(tmp_path))

        err = capsys.readouterr().err
        assert "ERROR" in err
        assert str(tmp_path / "package.json") in err

    def test_215_a_test_path_beside_an_unreadable_package_json_is_loud(self, tmp_path, capsys):
        """The same file read by the path resolver (#4237), the same way."""
        (tmp_path / "web").mkdir()
        (tmp_path / "web" / "package.json").write_text("{not json", encoding="utf-8")

        with pytest.raises(ValueError, match="package.json could not be read"):
            fd.runner_for_test_path("web/a.test.ts", str(tmp_path))

        assert "ERROR" in capsys.readouterr().err


class TestADeclarationNamingNoFramework:
    def test_252_test_dirs_naming_no_framework_is_loud_and_raises(self, tmp_path, capsys):
        (tmp_path / ".unleashed.json").write_text(
            json.dumps({"test_dirs": {"mocha": "web"}}), encoding="utf-8",
        )

        with pytest.raises(ValueError, match="mocha"):
            fd.detect_framework_dirs(str(tmp_path))

        err = capsys.readouterr().err
        assert "ERROR" in err
        assert "mocha" in err


class TestAMissingProjectRoot:
    def test_273_a_project_root_that_does_not_exist_raises(self, tmp_path, capsys):
        missing = tmp_path / "gone"

        with pytest.raises(fd.FrameworkResolutionError) as excinfo:
            fd.detect_framework_dirs(str(missing))

        assert str(missing) in str(excinfo.value)
        assert "ERROR" in capsys.readouterr().err

    def test_273_no_project_root_raises(self):
        with pytest.raises(fd.FrameworkResolutionError):
            fd.detect_framework_dirs("")

    def test_273_a_missing_root_is_never_placed_at_pytest(self, tmp_path):
        """The caller that defaulted: placing pytest alone used to give
        {pytest: "."} for a project that is not there."""
        with pytest.raises(fd.FrameworkResolutionError):
            fd.resolve_framework_dirs("No framework named here.", str(tmp_path / "gone"))


class TestKept:
    def test_an_empty_project_has_no_frameworks_quietly(self, tmp_path, capsys, operator_alerts):
        """Kept: a project that exists and declares nothing is an empty
        answer, which N0 reads as pytest at the root."""
        assert fd.detect_framework_dirs(str(tmp_path)) == {}
        assert fd.resolve_framework_dirs("No framework named here.", str(tmp_path)) == {
            fd.TestFramework.PYTEST: ".",
        }
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []

    def test_a_project_with_a_config_is_detected(self, tmp_path):
        (tmp_path / "web").mkdir()
        (tmp_path / "web" / "vitest.config.ts").write_text("", encoding="utf-8")

        assert fd.detect_framework_dirs(str(tmp_path)) == {fd.TestFramework.VITEST: "web"}

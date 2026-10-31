"""symbol_validator.py under standard 0034, one test per sweep site (#3585).

The symbol validator checks that the names a generated test imports exist in
the repository's own modules. A target module it could not read or parse
came back as None (71), which the check passed over as "not evidence of a
fault" (152), and a test source that did not parse came back as no findings
(137): in each case a check that could not run read the same as one that
found every import good. Each now raises SymbolCheckError, a ValueError,
naming the file and the cause, after an ERROR line. A module that is not the
repository's own (stdlib, third party) is still passed over quietly: it is
not this check's to make.

Every test works in a temporary directory. Line numbers in the names are
ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.testing import symbol_validator as sv


def _package(tmp_path: Path, source: str) -> Path:
    package = tmp_path / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    module = package / "config.py"
    module.write_text(source, encoding="utf-8")
    return module


def _symbol_check_error(excinfo) -> None:
    assert type(excinfo.value).__name__ == "SymbolCheckError", (
        f"expected SymbolCheckError, got {type(excinfo.value).__name__}: {excinfo.value}"
    )


class TestATargetModuleThatCannotBeRead:
    def test_71_a_target_module_that_does_not_parse_raises(self, tmp_path, capsys):
        module = _package(tmp_path, "def get_default_config_path(:\n")

        with pytest.raises(ValueError) as excinfo:
            sv.exported_names(module)

        _symbol_check_error(excinfo)
        assert str(module) in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, SyntaxError)
        assert "ERROR" in capsys.readouterr().err

    def test_71_a_target_module_that_cannot_be_read_raises(self, tmp_path, monkeypatch):
        module = _package(tmp_path, "X = 1\n")
        real_read = Path.read_text

        def read_text(self, *args, **kwargs):
            if self == module:
                raise PermissionError(13, "Permission denied", str(self))
            return real_read(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)

        with pytest.raises(ValueError) as excinfo:
            sv.exported_names(module)

        _symbol_check_error(excinfo)
        assert "PermissionError" in str(excinfo.value)


class TestATestSourceThatDoesNotParse:
    def test_137_a_test_source_that_does_not_parse_raises(self, tmp_path, capsys):
        with pytest.raises(ValueError) as excinfo:
            sv.validate_test_imports("from pkg.config import (\n", tmp_path)

        _symbol_check_error(excinfo)
        assert isinstance(excinfo.value.__cause__, SyntaxError)
        assert "ERROR" in capsys.readouterr().err


class TestAnImportThatCannotBeChecked:
    def test_152_an_import_from_an_unreadable_module_is_never_passed(self, tmp_path):
        _package(tmp_path, "def get_default_config_path(:\n")

        with pytest.raises(ValueError) as excinfo:
            sv.validate_test_imports("from pkg.config import default_config_path\n", tmp_path)

        _symbol_check_error(excinfo)
        assert "pkg" in str(excinfo.value)


class TestKept:
    def test_a_module_that_is_not_the_repos_own_is_passed_over_quietly(
        self, tmp_path, capsys, operator_alerts,
    ):
        assert sv.validate_test_imports("from os.path import join\nimport json\n", tmp_path) == []
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []

    def test_a_name_the_module_has_is_good(self, tmp_path):
        _package(tmp_path, "def get_default_config_path():\n    return 1\n")

        assert sv.validate_test_imports(
            "from pkg.config import get_default_config_path\n", tmp_path,
        ) == []

    def test_a_name_the_module_lacks_is_named_with_its_near_match(self, tmp_path):
        _package(tmp_path, "def get_default_config_path():\n    return 1\n")

        problems = sv.validate_test_imports("from pkg.config import default_config_path\n", tmp_path)

        assert problems == [
            "pkg.config has no 'default_config_path'. Did you mean: get_default_config_path?"
        ]

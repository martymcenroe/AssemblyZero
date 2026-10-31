"""import_validator.py under standard 0034 (ADR 0236), the #3585 sweep.

The import gate (#842) used to pass or misjudge on three failures of its own:
installed-package metadata that could not be enumerated fell back to a map
without a word, a pyproject.toml that could not be read or parsed became "no
dependencies" (so every third-party import was flagged as a hallucination),
and code that did not parse passed the gate. Each now is an ERROR line naming
what failed, and the first two raise; the third is a failed verdict carrying
the syntax error. Test names carry ledger 0908's line numbers at its base
``79e18ad1``.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.implementation import import_validator as iv


def _loud(err: str, *needles: str) -> bool:
    return any(
        line.startswith("ERROR") and all(n in line for n in needles)
        for line in err.splitlines()
    )


class TestInstalledPackageMetadata:
    def test_85_metadata_that_cannot_be_enumerated_raises(self, monkeypatch, capsys):
        def broken():
            raise OSError(5, "Input/output error", "site-packages")

        monkeypatch.setattr(importlib.metadata, "distributions", broken)

        with pytest.raises(OSError):
            iv._import_names_for_pypi("pyyaml")

        assert _loud(capsys.readouterr().err, "pyyaml", "installed-package metadata")

    def test_the_map_and_the_name_are_still_returned(self):
        """Kept: a dist that is not installed is the map and the name."""
        assert iv._import_names_for_pypi("pyyaml") >= {"pyyaml", "yaml"}


class TestPyprojectToml:
    def test_119_a_pyproject_that_does_not_parse_raises(self, tmp_path, capsys):
        (tmp_path / "pyproject.toml").write_text("[project\nname = 'x'\n", encoding="utf-8")

        with pytest.raises(ValueError):
            iv._read_third_party_packages(tmp_path)

        assert _loud(capsys.readouterr().err, "pyproject.toml", "could not read")

    def test_119_an_unreadable_pyproject_raises(self, tmp_path, monkeypatch, capsys):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'x'\n", encoding="utf-8")
        real = Path.read_text

        def read_text(self, *args, **kwargs):
            if Path(self) == pyproject:
                raise PermissionError(13, "Permission denied", str(self))
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)

        with pytest.raises(PermissionError):
            iv._read_third_party_packages(tmp_path)

        assert _loud(capsys.readouterr().err, "pyproject.toml", "could not read")

    def test_no_pyproject_is_no_declared_dependencies(self, tmp_path):
        """Kept: a repository with no pyproject.toml declares nothing."""
        assert iv._read_third_party_packages(tmp_path) == set()


class TestCodeThatDoesNotParse:
    def test_229_code_that_does_not_parse_does_not_pass(self, tmp_path, capsys):
        valid, problems = iv.validate_imports("import os\ndef broken(:\n", "src/x.py", tmp_path)

        assert valid is False
        assert problems and "does not parse" in problems[0]
        assert _loud(capsys.readouterr().err, "src/x.py", "does not parse")

    def test_code_that_parses_is_still_judged(self, tmp_path):
        """Kept: the gate's own verdicts."""
        assert iv.validate_imports("import os\n", "src/x.py", tmp_path) == (True, [])
        valid, bad = iv.validate_imports("import nosuchpkg_xyz\n", "src/x.py", tmp_path)
        assert valid is False and bad[0].startswith("nosuchpkg_xyz")

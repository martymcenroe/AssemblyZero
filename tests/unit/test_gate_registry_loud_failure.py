"""gate_registry.py's halt-site scanner under standard 0034 (#3776).

The scanner is an audit of every place the workflow code can end a run. A file
it could not read or parse was listed in ``files_unparseable`` and skipped, so
the audit reported on a tree it had not fully read; a registry row naming
something that is not a site key was passed over. A file the scanner cannot
cover now stops it with ``HaltScanError`` naming the file, and a malformed row
raises naming the row. Line numbers in the names are ledger 0908's, at its
base ``79e18ad1``.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from assemblyzero.core import gate_registry as gr
from assemblyzero.core.gate_registry import ACTION_HALT, JUDGES_MODEL_OUTPUT, Gate

GOOD = "def n1(state):\n    return {'error_message': 'NEW GATE: something'}\n"


def _tree(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "good.py").write_text(GOOD, encoding="utf-8")
    return pkg


class TestTheScannerCoversEveryFile:
    def test_1240_a_file_that_does_not_parse_stops_the_scan(self, tmp_path):
        pkg = _tree(tmp_path)
        (pkg / "broken.py").write_text("def f(:\n", encoding="utf-8")

        with pytest.raises(gr.HaltScanError, match="pkg/broken.py") as raised:
            gr.scan_halt_sites(tmp_path, Path("pkg"))
        assert "SyntaxError" in str(raised.value)
        assert isinstance(raised.value.__cause__, SyntaxError)

    def test_1240_a_file_that_cannot_be_read_stops_the_scan(self, tmp_path, monkeypatch):
        pkg = _tree(tmp_path)
        target = pkg / "locked.py"
        target.write_text(GOOD, encoding="utf-8")
        real = Path.read_text

        def read_text(self, *args, **kwargs):
            if self == target:
                raise PermissionError(13, "Permission denied", str(self))
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)

        with pytest.raises(gr.HaltScanError, match="pkg/locked.py") as raised:
            gr.scan_halt_sites(tmp_path, Path("pkg"))
        assert "PermissionError" in str(raised.value)

    def test_a_readable_tree_is_scanned_in_full(self, tmp_path):
        """Kept."""
        _tree(tmp_path)
        sites, coverage = gr.scan_halt_sites(tmp_path, Path("pkg"))
        assert coverage.files_scanned == 1
        assert [s.qualname for s in sites] == ["n1"]


class TestAMalformedRowIsNamed:
    def test_1453_a_row_naming_something_that_is_not_a_site_key_raises(self):
        registry = (
            Gate("gate.malformed", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT,
                 "MALFORMED", ("not-a-site-key",)),
        )

        with pytest.raises(ValueError, match="gate.malformed") as raised:
            gr.renumberings([], registry)
        assert "not-a-site-key" in str(raised.value)

    def test_a_well_formed_phantom_is_still_a_phantom(self):
        """Kept: a row whose site the walker did not find is reported, not
        raised; that is the two-way check's answer."""
        registry = (
            Gate("gate.gone", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT,
                 "GONE", ("pkg/x.py::f::return::0",)),
        )
        moved, fresh, ghosts = gr.renumberings([], registry)
        assert moved == [] and fresh == []
        assert ghosts == [("gate.gone", "pkg/x.py::f::return::0")]


def test_1241_1454_no_fail_open_tag_remains():
    assert "fail-open:" not in inspect.getsource(gr.scan_halt_sites)
    assert "fail-open:" not in inspect.getsource(gr.renumberings)

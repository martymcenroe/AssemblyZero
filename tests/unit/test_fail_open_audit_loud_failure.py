"""fail_open_audit.py under standard 0034, one test per sweep site (#3775).

This is an audit: what it reports is only as good as what it examined. A file
it could not read or parse used to be dropped into ``files_unparseable`` and
skipped, a scope directory that did not exist was skipped, and a handler type
it could not render was labelled "an exception". Each one shrank the audit
while it still reported. A file or scope it cannot cover now stops the scan
with ``ScanError`` naming it, and a label it cannot render raises. Line numbers
in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from assemblyzero.core import fail_open_audit as fa

HANDLER_SOURCE = """
def f():
    try:
        go()
    except OSError:
        pass
"""


def _handler() -> ast.ExceptHandler:
    tree = ast.parse(HANDLER_SOURCE)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler))


def test_595_a_handler_type_that_cannot_be_rendered_raises(monkeypatch):
    scanner = fa._Scanner("x.py", HANDLER_SOURCE.splitlines(), "unknown", fa.Coverage())

    def refuse(node):
        raise ValueError("cannot unparse this node")

    monkeypatch.setattr(fa.ast, "unparse", refuse)

    with pytest.raises(ValueError, match="cannot unparse"):
        scanner._exception_text(_handler())


def test_596_700_no_fail_open_tag_remains():
    assert "fail-open:" not in inspect.getsource(fa._Scanner._exception_text)
    assert "fail-open:" not in inspect.getsource(fa.scan_file)


class TestAFileItCannotCoverStopsTheScan:
    def test_699_a_file_that_does_not_parse_stops_the_scan(self, tmp_path):
        (tmp_path / "good.py").write_text(HANDLER_SOURCE, encoding="utf-8")
        (tmp_path / "broken.py").write_text("def f(:\n", encoding="utf-8")

        with pytest.raises(fa.ScanError, match="broken.py") as raised:
            fa.scan(tmp_path, (".",))
        assert "SyntaxError" in str(raised.value)
        assert isinstance(raised.value.__cause__, SyntaxError)

    def test_699_a_file_that_cannot_be_read_stops_the_scan(self, tmp_path, monkeypatch):
        target = tmp_path / "locked.py"
        target.write_text(HANDLER_SOURCE, encoding="utf-8")
        real = Path.read_text

        def read_text(self, *args, **kwargs):
            if self == target:
                raise PermissionError(13, "Permission denied", str(self))
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)

        with pytest.raises(fa.ScanError, match="locked.py") as raised:
            fa.scan(tmp_path, (".",))
        assert "PermissionError" in str(raised.value)

    def test_739_a_scope_that_does_not_exist_stops_the_scan(self, tmp_path):
        (tmp_path / "assemblyzero").mkdir()

        with pytest.raises(fa.ScanError, match="tools") as raised:
            fa.scan(tmp_path, ("assemblyzero", "tools"))
        assert "does not exist" in str(raised.value)


class TestWhatItCanCoverIsStillCovered:
    def test_a_readable_tree_is_scanned_in_full(self, tmp_path):
        """Kept."""
        (tmp_path / "a.py").write_text(HANDLER_SOURCE, encoding="utf-8")
        (tmp_path / "bom.py").write_text(HANDLER_SOURCE, encoding="utf-8-sig")

        findings, coverage = fa.scan(tmp_path, (".",))
        assert coverage.files_scanned == 2
        assert len(findings) == 2

    def test_a_handler_type_is_named(self):
        """Kept."""
        scanner = fa._Scanner("x.py", HANDLER_SOURCE.splitlines(), "unknown", fa.Coverage())
        assert scanner._exception_text(_handler()) == "OSError"

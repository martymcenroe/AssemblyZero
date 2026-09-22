"""`tools/claude-usage-scraper.py` must stay importable without pywinpty (#3452).

It used to call `sys.exit(1)` at module level when `import winpty` failed.
pywinpty is Windows-only, so on Linux that terminated whatever process imported
the file -- including pytest, which died collecting `tests/tools/` with
`INTERNALERROR ... SystemExit: 1` before running a single test. Exit code 3, no
test results, and a failure that reads as "the test framework broke".

These tests live in `tests/unit/` on purpose. The natural home is `tests/tools/`,
but no CI step collects that directory yet (#3453), and a regression test that
does not run is not a regression test.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRAPER = (
    Path(__file__).resolve().parents[2] / "tools" / "claude-usage-scraper.py"
)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRAPER)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot load {SCRAPER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_imports_cleanly_when_pywinpty_is_absent(monkeypatch):
    """The regression. Binding `winpty` to None makes `import winpty` raise
    ImportError, which is what Linux does natively."""
    monkeypatch.setitem(sys.modules, "winpty", None)

    mod = _load("scraper_without_winpty")  # must not raise SystemExit

    assert mod.winpty is None


def test_importing_does_not_exit_the_process(monkeypatch):
    """States the property directly, so a future edit reintroducing a
    module-level exit fails here rather than inside a collector."""
    monkeypatch.setitem(sys.modules, "winpty", None)

    try:
        _load("scraper_exit_check")
    except SystemExit as exc:  # pragma: no cover - this is the failure being guarded
        pytest.fail(
            f"importing the scraper raised SystemExit({exc.code}); it must be "
            "importable on hosts where pywinpty is unavailable"
        )


def test_the_cli_still_refuses_to_run_without_pywinpty(monkeypatch, capsys):
    """Deferring the check must not weaken it.

    Same JSON on stdout, same exit code 1 -- only the timing moved, from import
    to invocation.
    """
    monkeypatch.setitem(sys.modules, "winpty", None)
    mod = _load("scraper_cli_guard")

    with pytest.raises(SystemExit) as excinfo:
        mod._require_winpty()

    assert excinfo.value.code == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "pywinpty not installed" in payload["error"]


def test_the_guard_is_a_no_op_when_pywinpty_is_present(monkeypatch):
    """On Windows the scraper must behave exactly as it always has."""
    monkeypatch.setattr(
        _load("scraper_present"), "winpty", object(), raising=False
    )
    mod = _load("scraper_present_2")
    if mod.winpty is None:
        pytest.skip("pywinpty genuinely unavailable on this host")

    mod._require_winpty()  # returns, does not exit

"""The red-phase import names the implementation symbols the bodies use (#2888).

boostgauge #4, `run-issue4-011019` (2026-09-06 01:10), with #2887's module
repair in the launcher. The scaffold's `test_req_6` now had its `psutil`;
what it did not have was the helper it tests:

    tests\\test_issue_4.py:67: in test_req_6_cmdline_access_denied_handled
    E   NameError: name '_psutil_cmdline' is not defined

The emitter's only link to the implementation was `from boostgauge.collector
import *`, and Python's rule for a star-import is that no underscore name
crosses it unless `__all__` says so. The implementation defined
`_psutil_cmdline` in `collectors/windows.py`; `collector.py` never re-exported
it, and had it done so the star-import would have dropped the underscore name
anyway, since `collector.py` declares no `__all__`. Nothing the loop rewrites
could pass that test through that import. Tests were frozen at 37 of 38 and
the run was stopped by hand, the second run in an hour to end on the
scaffold's link.

The red-phase import now names the symbols the bodies use with no binding in
scope and are not importable modules: `from boostgauge.collector import
WindowsCollector, _psutil_cmdline`. An underscore name arrives. A symbol the
module does not provide fails at collection with the module and the symbol
in the message, which is a thing the loop can attribute and fix -- unlike a
NameError inside a test body it may never rewrite. The star form remains for
a suite whose bodies use no implementation name, so the RED signal is never
lost.
"""

from __future__ import annotations

import ast

import pytest

from assemblyzero.workflows.testing.nodes.scaffold_tests import (
    generate_spec_test_file_content,
    unbound_names,
)

REQ_6 = (
    "def test_req_6_cmdline_access_denied_handled(monkeypatch):\n"
    "    # AccessDenied mock (REQ-6) -- expected: _psutil_cmdline returns []\n"
    '    exc = getattr(psutil, "AccessDenied")\n'
    "    def mock_proc(*args): raise exc(1)\n"
    '    monkeypatch.setattr("psutil.Process", mock_proc)\n'
    "    assert _psutil_cmdline(1) == []\n"
)
REQ_7 = (
    "def test_req_7_single_sweep():\n"
    "    import unittest.mock\n"
    "    sweep_mock = unittest.mock.MagicMock(return_value=[])\n"
    "    c = WindowsCollector()\n"
    "    c.nt_sweep = sweep_mock\n"
    "    c.collect()\n"
    "    assert sweep_mock.call_count == 1\n"
)
REQ_12 = (
    "def test_req_12_thread_continues_on_error():\n"
    "    import unittest.mock\n"
    "    c = unittest.mock.MagicMock()\n"
    "    t = CollectorThread(c, interval=0.01)\n"
    "    t.start()\n"
    "    t.stop()\n"
    "    assert not t.is_alive()\n"
)
MODULES_ONLY = (
    "def test_only_stdlib():\n"
    "    import os\n"
    "    assert os.sep\n"
)


def _suite(*sources: str, imports: str = "") -> dict:
    return {
        "imports": imports,
        "functions": [
            {"name": src.split("(")[0].removeprefix("def "), "source": src}
            for src in sources
        ],
    }


PLAN = [{"path": "src/boostgauge/collector.py", "change_type": "Add"}]


@pytest.fixture
def target(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "boostgauge"\ndependencies = ["psutil (>=7.2.2,<8.0.0)"]\n',
        encoding="utf-8",
    )
    return tmp_path


def _red_phase_line(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("from boostgauge.collector import"):
            return line
    return None


# =============================================================================
# The analysis splits modules from symbols
# =============================================================================


class TestUnboundNames:
    def test_run_29s_bodies_split_into_a_module_and_two_symbols(self, target):
        found = unbound_names("\n\n".join((REQ_6, REQ_7)), target)

        assert found["modules"] == [("psutil", "test_req_6_cmdline_access_denied_handled")]
        assert found["symbols"] == [
            ("WindowsCollector", "test_req_7_single_sweep"),
            ("_psutil_cmdline", "test_req_6_cmdline_access_denied_handled"),
        ]

    def test_attributes_are_not_symbols(self, target):
        """`c.nt_sweep`, `sweep_mock.call_count`: only bare names count."""
        content = generate_spec_test_file_content(_suite(REQ_7), 4, None)

        assert [n for n, _ in unbound_names(content, target)["symbols"]] == ["WindowsCollector"]

    def test_a_suite_using_no_implementation_name_has_no_symbols(self, target):
        content = generate_spec_test_file_content(_suite(MODULES_ONLY), 4, None)

        assert unbound_names(content, target) == {"modules": [], "symbols": []}


# =============================================================================
# The red-phase import
# =============================================================================


class TestTheRedPhaseImport:
    def test_run_29s_suite_imports_its_symbols_by_name(self, target, capsys):
        content = generate_spec_test_file_content(
            _suite(REQ_6, REQ_7, REQ_12), 4, PLAN, repo_root=target,
        )

        ast.parse(content)
        assert _red_phase_line(content) == (
            "from boostgauge.collector import CollectorThread, WindowsCollector, "
            "_psutil_cmdline  # noqa: F401"
        )
        assert (
            "[N2] red-phase import names 3 symbol(s) from boostgauge.collector: "
            "CollectorThread, WindowsCollector, _psutil_cmdline (#2888)"
        ) in capsys.readouterr().out

    def test_an_underscore_helper_crosses_the_import(self, target):
        """The star-import rule that stopped run 29: `_psutil_cmdline` never
        crosses `import *`. Named, it does."""
        content = generate_spec_test_file_content(_suite(REQ_6), 4, PLAN, repo_root=target)

        assert "import *" not in content
        assert "_psutil_cmdline" in _red_phase_line(content)

    def test_modules_go_to_the_2887_block_not_the_red_phase_line(self, target):
        content = generate_spec_test_file_content(_suite(REQ_6), 4, PLAN, repo_root=target)

        assert "import psutil" in content
        named = _red_phase_line(content).split("import ", 1)[1].split("  #")[0].split(", ")
        assert named == ["_psutil_cmdline"]

    def test_the_star_form_remains_when_no_symbol_is_used(self, target, capsys):
        """The RED signal must still come from somewhere."""
        content = generate_spec_test_file_content(
            _suite(MODULES_ONLY), 4, PLAN, repo_root=target,
        )

        assert _red_phase_line(content) == "from boostgauge.collector import *  # noqa: F401, F403"
        assert "#2888" not in capsys.readouterr().out

    def test_the_specs_own_import_of_the_module_still_suppresses_the_trigger(self, target):
        content = generate_spec_test_file_content(
            _suite(REQ_6, imports="from boostgauge.collector import _psutil_cmdline"),
            4, PLAN, repo_root=target,
        )

        assert content.count("from boostgauge.collector import") == 1

    def test_no_implementation_module_means_no_trigger_at_all(self, target):
        content = generate_spec_test_file_content(_suite(REQ_6), 4, None, repo_root=target)

        assert _red_phase_line(content) is None

    def test_the_bodies_are_still_verbatim(self, target):
        content = generate_spec_test_file_content(
            _suite(REQ_6, REQ_7, REQ_12), 4, PLAN, repo_root=target,
        )

        for body in (REQ_6, REQ_7, REQ_12):
            assert body.rstrip() in content

    def test_the_emitted_file_still_fails_before_the_implementation_exists(self, target, tmp_path):
        """A named import of a module that is not there is the same RED
        signal the star form gave: ModuleNotFoundError at collection."""
        content = generate_spec_test_file_content(_suite(REQ_6), 4, PLAN, repo_root=target)
        path = tmp_path / "test_issue_4.py"
        path.write_text(content, encoding="utf-8")

        with pytest.raises(ModuleNotFoundError):
            exec(compile(content, str(path), "exec"), {"__name__": "test_issue_4"})

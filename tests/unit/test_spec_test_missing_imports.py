"""A spec test body that uses a module it never imports gets the import (#2887).

boostgauge #4, `run-issue4-005046` (2026-09-06 00:50): the first run to write
all five planned files, converging 29 → 36 → 37 of 38. The one that never
passed:

    tests\\test_issue_4.py:67: in test_req_6_cmdline_access_denied_handled
        exc = getattr(psutil, "AccessDenied")
                      ^^^^^^
    E   NameError: name 'psutil' is not defined

The scaffold emits the spec's bodies verbatim (#2316). The spec's other bodies
say `import psutil` inside the function; this one did not, and the file's
only module-level import was the red-phase `from boostgauge.collector import *`,
which supplies the implementation's names and not `psutil`. The scaffold file is
not among the plan's five, so N4 never rewrites it; after two identical
results N5 froze the tests as the contract and rewrote the implementation
against a test no implementation can pass. Three iterations, stopped by hand.

The emitter now adds a module-level `import <module>` for each module a body
uses without any binding in scope -- and only for importable module names, so
the star-import's symbols are never guessed at.
"""

from __future__ import annotations

import ast

import pytest

from assemblyzero.workflows.testing.nodes.scaffold_tests import (
    generate_spec_test_file_content,
    missing_module_imports,
)

# The three bodies as run 28 emitted them: req_1 imports psutil locally,
# req_6 uses it bare, req_7 uses only the implementation's names.
REQ_1 = (
    "def test_req_1_conpty_matches(monkeypatch):\n"
    "    # Live OS state (REQ-1) -- expected: conpty_count equals psutil count ±1\n"
    "    import psutil\n"
    "    c = WindowsCollector()\n"
    "    psutil_conpty = sum(1 for p in psutil.process_iter(['name']) if p.info['name'])\n"
    "    assert abs(c.collect().conpty_count - psutil_conpty) <= 1\n"
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
    "    # Calling collect() (REQ-7) -- expected: nt_sweep called exactly once per tick\n"
    "    import unittest.mock\n"
    "    sweep_mock = unittest.mock.MagicMock(return_value=[])\n"
    "    c = WindowsCollector()\n"
    "    c.nt_sweep = sweep_mock\n"
    "    c.collect()\n"
    "    assert sweep_mock.call_count == 1\n"
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
    """A target that declares psutil, as boostgauge's pyproject does."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "boostgauge"\ndependencies = [\n'
        '    "psutil (>=7.2.2,<8.0.0)",\n    "Pillow>=10",\n]\n',
        encoding="utf-8",
    )
    return tmp_path


def _module_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    return [
        alias.name
        for node in tree.body if isinstance(node, ast.Import)
        for alias in node.names
    ]


# =============================================================================
# The analysis
# =============================================================================


class TestMissingModuleImports:
    def test_run_28s_body_names_psutil_and_the_function_that_uses_it(self, target):
        content = generate_spec_test_file_content(
            _suite(REQ_1, REQ_6, REQ_7), 4, PLAN,
        )  # unrepaired: repo_root not given, psutil not in the known set

        assert ("psutil", "test_req_6_cmdline_access_denied_handled") in \
            missing_module_imports(content, target)

    def test_an_import_inside_another_function_binds_nothing_here(self, target):
        """req_1's local `import psutil` is why the file LOOKED fine."""
        only_req_1 = generate_spec_test_file_content(_suite(REQ_1), 4, PLAN)
        assert missing_module_imports(only_req_1, target) == []

        both = generate_spec_test_file_content(_suite(REQ_1, REQ_6), 4, PLAN)
        assert missing_module_imports(both, target) == [
            ("psutil", "test_req_6_cmdline_access_denied_handled"),
        ]

    def test_the_implementations_names_are_never_reported(self, target):
        """`WindowsCollector` and `_psutil_cmdline` come from the star-import."""
        content = generate_spec_test_file_content(_suite(REQ_7), 4, PLAN)

        assert missing_module_imports(content, target) == []

    def test_a_stdlib_module_is_reported_without_any_pyproject(self, tmp_path):
        source = "def test_sleeps():\n    time.sleep(0)\n    assert True\n"

        assert missing_module_imports(source, tmp_path) == [("time", "test_sleeps")]
        assert missing_module_imports(source, None) == [("time", "test_sleeps")]

    def test_pytest_is_known_without_a_declaration(self, tmp_path):
        source = "def test_raises():\n    with pytest.raises(ValueError):\n        int('x')\n"

        assert missing_module_imports(source, None) == [("pytest", "test_raises")]

    def test_an_undeclared_third_party_module_is_not_guessed(self, tmp_path):
        """No pyproject declares `requests`: nothing says it is a module."""
        source = "def test_gets():\n    assert requests.get\n"

        assert missing_module_imports(source, tmp_path) == []

    def test_a_module_level_import_satisfies_every_function(self, target):
        source = "import psutil\n\ndef test_a():\n    assert psutil\n\ndef test_b():\n    assert psutil\n"

        assert missing_module_imports(source, target) == []

    def test_a_local_binding_shadows_the_module_name(self, target):
        source = "def test_a(psutil):\n    assert psutil\n\ndef test_b():\n    psutil = 1\n    assert psutil\n"

        assert missing_module_imports(source, target) == []

    def test_a_module_level_assignment_binds_too(self, target):
        source = "psutil = object()\n\ndef test_a():\n    assert psutil\n"

        assert missing_module_imports(source, target) == []

    def test_builtins_are_not_modules(self, target):
        source = "def test_a():\n    assert len(list(range(3))) == 3\n"

        assert missing_module_imports(source, target) == []

    def test_unparseable_source_reports_nothing(self, target):
        assert missing_module_imports("def test_a(:\n", target) == []

    def test_each_module_is_reported_once_by_its_first_user(self, target):
        source = (
            "def test_a():\n    assert psutil\n\n"
            "def test_b():\n    assert psutil and time\n"
        )

        assert missing_module_imports(source, target) == [
            ("psutil", "test_a"), ("time", "test_b"),
        ]


# =============================================================================
# The emitter
# =============================================================================


class TestTheEmittedFile:
    def test_run_28s_suite_carries_import_psutil_at_module_level(self, target, capsys):
        content = generate_spec_test_file_content(
            _suite(REQ_1, REQ_6, REQ_7), 4, PLAN, repo_root=target,
        )

        ast.parse(content)
        assert "psutil" in _module_imports(content)
        assert (
            "[N2] test_req_6_cmdline_access_denied_handled uses psutil without "
            "importing it; added 'import psutil' (#2887)"
        ) in capsys.readouterr().out

    def test_the_bodies_are_still_verbatim(self, target):
        content = generate_spec_test_file_content(
            _suite(REQ_1, REQ_6, REQ_7), 4, PLAN, repo_root=target,
        )

        for body in (REQ_1, REQ_6, REQ_7):
            assert body.rstrip() in content

    def test_the_repair_sits_after_the_specs_imports_and_before_the_red_phase(self, target):
        content = generate_spec_test_file_content(
            _suite(REQ_6, imports="import os"), 4, PLAN, repo_root=target,
        )

        assert content.index("import os") < content.index("import psutil")
        assert content.index("import psutil") < content.index("from boostgauge.collector import *")

    def test_nothing_is_added_when_nothing_is_missing(self, target, capsys):
        content = generate_spec_test_file_content(
            _suite(REQ_1, REQ_7), 4, PLAN, repo_root=target,
        )

        assert "#2887" not in content
        assert "[N2]" not in capsys.readouterr().out

    def test_the_red_phase_import_is_still_the_only_link_to_the_implementation(self, target):
        content = generate_spec_test_file_content(
            _suite(REQ_6), 4, PLAN, repo_root=target,
        )

        assert "from boostgauge.collector import *" in content
        assert "import WindowsCollector" not in content
        assert "import _psutil_cmdline" not in content

    def test_without_repo_root_the_declared_dependency_is_not_known(self, capsys):
        """The caller must pass the target: without it only stdlib and the
        validator's known set can be repaired, and psutil is neither."""
        content = generate_spec_test_file_content(_suite(REQ_6), 4, PLAN)

        assert "import psutil" not in content

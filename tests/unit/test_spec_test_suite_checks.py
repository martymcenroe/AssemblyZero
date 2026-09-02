"""Section 10's test functions, graded by the stage that will run them (#2706, #2707).

On boostgauge run-issue4-163140 (2026-09-02) the spec stage approved a spec
whose thirteen test functions were, eleven times, a comment and ``pass``, and
seven of which took a parameter no fixture provides. The implementation stage's
scaffolder emits those functions verbatim (#2316) and its validator refused the
suite 3.4 s later, byte-identical on regeneration, deterministic -- after 605 s
of approved spec work.

These two checks ask the same questions in the spec stage, with the testing
workflow's own extractor and its own rule, and cite each function's line span
so revision pinning opens exactly the lines the drafter has to rewrite
(#2686's shape). The fixture is the approved spec, verbatim.
"""

from __future__ import annotations

import re
from pathlib import Path

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    _declared_dependencies,
    check_spec_test_fixtures_resolvable,
    check_spec_test_functions_have_assertions,
)
from assemblyzero.workflows.implementation_spec.revision_pinning import (
    enforce_pinning,
    named_line_ranges,
    named_tokens,
)

FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "boostgauge4_stub_tests"
    / "spec-0004-final-spec.md"
)
SPEC = FIXTURE.read_text(encoding="utf-8")

#: The first five functions the implementation stage's validator named on the
#: run, in the order its log listed them. The count it reported was 11.
STUBS_THE_RUN_NAMED = (
    "test_req_6_mocked_single_sweep",
    "test_req_1_conpty_count",
    "test_req_2_basic_metrics_accuracy",
    "test_req_3_unleashed_detection",
    "test_req_4_non_blocking_polling",
)

PYPROJECT_WITHOUT_MOCK = (
    '[project]\nname = "boostgauge"\n'
    'dependencies = ["psutil (>=7,<8)", "Pillow (>=10)"]\n'
    "[tool.poetry.group.dev.dependencies]\n"
    'pytest = "^9"\npytest-cov = "^7"\n'
)
PYPROJECT_WITH_MOCK = PYPROJECT_WITHOUT_MOCK + 'pytest-mock = "^3"\n'


def _section_10(body: str) -> str:
    return (
        "# Implementation Spec\n\n## 1. Overview\n\nx\n\n"
        "## 10. Test Mapping\n\n### 10.1 Per-criterion test functions\n\n"
        "```python\n" + body + "```\n"
    )


def _all_test_names(spec: str) -> list[str]:
    return re.findall(r"^def (test_\w+)\(", spec, re.MULTILINE)


# ---------------------------------------------------------------------------
# #2706: assertions
# ---------------------------------------------------------------------------


class TestAssertionsOnTheRealSpec:
    def test_the_approved_spec_is_refused_here_as_it_was_there(self) -> None:
        result = check_spec_test_functions_have_assertions(SPEC, 4, [])
        assert result["passed"] is False
        assert "11 of 13" in result["details"]
        for name in STUBS_THE_RUN_NAMED:
            assert f"`{name}`" in result["details"]

    def test_every_stub_is_named_and_nothing_else(self) -> None:
        """All eleven, never a truncated list: the cited span is what pinning
        unlocks, so a function left off the list would stay locked against
        the very edit the complaint demands."""
        details = check_spec_test_functions_have_assertions(SPEC, 4, [])["details"]
        names = _all_test_names(SPEC)
        assert len(names) == 13
        named = [n for n in names if f"`{n}`" in details]
        assert len(named) == 11
        assert set(STUBS_THE_RUN_NAMED) <= set(named)
        assert "more)" not in details

    def test_each_stub_is_cited_by_its_own_line_span(self) -> None:
        """The span is what pinning unlocks. It must be the function's lines
        in the draft, checked against the file rather than trusted."""
        details = check_spec_test_functions_have_assertions(SPEC, 4, [])["details"]
        lines = SPEC.splitlines()
        assert "`test_req_6_mocked_single_sweep` (lines 498-501)" in details
        assert lines[497].startswith("def test_req_6_mocked_single_sweep(")
        assert lines[500].strip() == "pass"
        assert "`test_req_1_conpty_count` (lines 512-515)" in details
        assert lines[511].startswith("def test_req_1_conpty_count(")
        assert lines[514].strip() == "pass"


class TestAssertionsControls:
    def test_the_same_spec_with_real_assertions_passes(self) -> None:
        repaired = SPEC.replace("    pass\n", "    assert 1 == 1\n")
        result = check_spec_test_functions_have_assertions(repaired, 4, [])
        assert result["passed"] is True, result["details"]
        assert "13" in result["details"]

    def test_no_executable_functions_is_not_applicable(self) -> None:
        table_only = (
            "# Spec\n\n## 10. Test Mapping\n\n| ID | Scenario |\n|---|---|\n"
            "| 010 | x |\n"
        )
        result = check_spec_test_functions_have_assertions(table_only, 4, [])
        assert result["passed"] is True
        assert "not applicable" in result["details"]

    def test_one_stub_among_real_tests_is_the_only_one_named(self) -> None:
        body = (
            "import pytest\n\n\n"
            "def test_a():\n    assert 1 == 1\n\n\n"
            "def test_b():\n    # expected: 2\n    pass\n\n\n"
            "def test_c():\n    with pytest.raises(ValueError):\n        int('x')\n"
        )
        result = check_spec_test_functions_have_assertions(_section_10(body), 1, [])
        assert result["passed"] is False
        assert "1 of 3" in result["details"]
        assert "`test_b`" in result["details"]
        assert "`test_a`" not in result["details"]
        assert "`test_c`" not in result["details"]

    def test_the_message_backticks_only_function_names(self) -> None:
        """A backticked word becomes a pinning token that unlocks every line
        carrying it. `pass` or `assert` as tokens would open half the draft."""
        details = check_spec_test_functions_have_assertions(SPEC, 4, [])["details"]
        tokens = named_tokens("", [details])
        assert all(t.startswith("test_") for t in tokens), sorted(tokens)


class TestPinningOpensTheCitedFunction:
    """End to end on the real draft: the complaint's span lets the drafter
    rewrite the stub body in place, and the lock refuses nothing."""

    REAL_BODY = [
        "    ntdll = MagicMock()",
        "    ntdll.NtQuerySystemInformation.return_value = 0",
        "    with patch('ctypes.windll', create=True) as windll:",
        "        windll.ntdll = ntdll",
        "        WindowsCollector().collect()",
        "    assert ntdll.NtQuerySystemInformation.call_count == 1",
    ]

    def test_the_rewritten_stub_is_accepted(self) -> None:
        details = check_spec_test_functions_have_assertions(SPEC, 4, [])["details"]
        lines = SPEC.splitlines()
        assert lines[500].strip() == "pass"  # line 501, inside the cited span
        revised = "\n".join(lines[:500] + self.REAL_BODY + lines[501:]) + "\n"

        result = enforce_pinning(
            SPEC,
            revised,
            current_tokens=named_tokens("", [details]),
            ever_tokens=named_tokens("", [details]),
            current_ranges=named_line_ranges([details]),
        )

        assert result.refusals == (), result.refusals
        assert "assert ntdll.NtQuerySystemInformation.call_count == 1" in result.text

    def test_a_line_outside_every_span_is_still_locked(self) -> None:
        """The control: the spans open the stubs and nothing else."""
        details = check_spec_test_functions_have_assertions(SPEC, 4, [])["details"]
        lines = SPEC.splitlines()
        assert lines[0].startswith("# ")
        revised = "\n".join(["# Retitled by a drafter nobody asked"] + lines[1:]) + "\n"

        result = enforce_pinning(
            SPEC,
            revised,
            current_tokens=named_tokens("", [details]),
            ever_tokens=named_tokens("", [details]),
            current_ranges=named_line_ranges([details]),
        )

        assert result.refusals != ()
        assert result.text.splitlines()[0] == lines[0]


# ---------------------------------------------------------------------------
# #2707: fixture parameters
# ---------------------------------------------------------------------------


class TestFixturesOnTheRealSpec:
    def test_six_parameters_name_no_fixture(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(PYPROJECT_WITHOUT_MOCK, encoding="utf-8")
        result = check_spec_test_fixtures_resolvable(SPEC, str(tmp_path), "")
        assert result["passed"] is False
        assert "7 test-function parameter(s)" in result["details"]
        assert result["details"].count("takes `mocker`") == 4
        assert result["details"].count("takes `live_environment`") == 2
        assert result["details"].count("takes `benchmark`") == 1
        assert "provided by pytest-mock, which the repo's pyproject does not declare" in (
            result["details"]
        )
        assert "provided by pytest-benchmark" in result["details"]
        assert "`test_req_3_unleashed_detection` (lines 522-" in result["details"]

    def test_declaring_pytest_mock_resolves_mocker_and_only_mocker(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(PYPROJECT_WITH_MOCK, encoding="utf-8")
        result = check_spec_test_fixtures_resolvable(SPEC, str(tmp_path), "")
        assert result["passed"] is False
        assert "takes `mocker`" not in result["details"]
        assert result["details"].count("takes `live_environment`") == 2

    def test_defining_the_fixture_and_using_monkeypatch_passes(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(PYPROJECT_WITHOUT_MOCK, encoding="utf-8")
        repaired = SPEC.replace("(mocker):", "(monkeypatch):").replace(
            "(benchmark):", "():"
        ).replace(
            "def test_req_1_conpty_count(live_environment):",
            "@pytest.fixture\ndef live_environment():\n    return None\n\n\n"
            "def test_req_1_conpty_count(live_environment):",
        )
        result = check_spec_test_fixtures_resolvable(repaired, str(tmp_path), "")
        assert result["passed"] is True, result["details"]

    def test_the_message_backticks_only_functions_and_parameters(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(PYPROJECT_WITHOUT_MOCK, encoding="utf-8")
        details = check_spec_test_fixtures_resolvable(SPEC, str(tmp_path), "")["details"]
        tokens = named_tokens("", [details])
        assert tokens <= {
            "test_req_1_conpty_count", "test_req_2_basic_metrics_accuracy",
            "test_req_3_unleashed_detection", "test_req_5_permission_error",
            "test_req_5_process_exit_error", "test_req_7_cpu_overhead_benchmark",
            "test_req_10_memory_percent",
            "mocker", "live_environment", "benchmark",
        }, sorted(tokens)


class TestFixtureControls:
    def test_builtins_parametrize_and_local_fixtures_pass(self, tmp_path: Path) -> None:
        body = (
            "import pytest\n\n\n"
            "@pytest.fixture\ndef collector():\n    return object()\n\n\n"
            "@pytest.mark.parametrize('value,expected', [(1, 2)])\n"
            "def test_a(value, expected, monkeypatch, tmp_path, collector):\n"
            "    assert value < expected\n"
        )
        result = check_spec_test_fixtures_resolvable(_section_10(body), str(tmp_path), "")
        assert result["passed"] is True, result["details"]

    def test_a_fixture_defined_between_tests_is_seen(self, tmp_path: Path) -> None:
        """The extractor slices from one `def test_` to the next, so a fixture
        defined between two tests rides inside the first one's source. The
        check parses the whole block and must still find it."""
        body = (
            "import pytest\n\n\n"
            "def test_a():\n    assert True\n\n\n"
            "@pytest.fixture\ndef thing():\n    return 1\n\n\n"
            "def test_b(thing):\n    assert thing == 1\n"
        )
        result = check_spec_test_fixtures_resolvable(_section_10(body), str(tmp_path), "")
        assert result["passed"] is True, result["details"]

    def test_an_unparseable_block_abstains(self, tmp_path: Path) -> None:
        result = check_spec_test_fixtures_resolvable(
            _section_10("def test_a(:\n    pass\n"), str(tmp_path), ""
        )
        assert result["passed"] is True
        assert "not applicable" in result["details"]

    def test_no_functions_is_not_applicable(self, tmp_path: Path) -> None:
        result = check_spec_test_fixtures_resolvable(
            "# Spec\n\n## 10. Test Mapping\n\nnone\n", str(tmp_path), ""
        )
        assert result["passed"] is True
        assert "not applicable" in result["details"]

    def test_no_repo_root_means_no_plugins(self) -> None:
        body = "def test_a(mocker):\n    assert mocker\n"
        result = check_spec_test_fixtures_resolvable(_section_10(body), "", "")
        assert result["passed"] is False
        assert "takes `mocker`" in result["details"]


class TestDeclaredDependencies:
    def test_pep621_lists(self) -> None:
        text = (
            '[project]\nname = "x"\n'
            'dependencies = ["pytest-mock>=3", "Pillow (>=10)"]\n'
            "[project.optional-dependencies]\ndev = ['pytest_cov']\n"
        )
        deps = _declared_dependencies(text)
        assert {"pytest-mock", "pillow", "pytest-cov"} <= deps
        assert "dev" not in deps

    def test_poetry_tables(self) -> None:
        text = (
            '[tool.poetry.dependencies]\npython = "^3.14"\npsutil = "^7"\n'
            "[tool.poetry.group.dev.dependencies]\n"
            'pytest-mock = {version = "^3", optional = true}\n'
        )
        deps = _declared_dependencies(text)
        assert {"psutil", "pytest-mock"} <= deps
        assert "version" not in deps

    def test_dependency_groups(self) -> None:
        assert "pytest-mock" in _declared_dependencies(
            '[dependency-groups]\ntest = ["pytest-mock"]\n'
        )

    def test_empty_declares_nothing_and_unparseable_says_so(self) -> None:
        """None, not an empty set, so the report can say "could not be parsed"
        rather than "declares none" -- the fail-open ruling on the site."""
        assert _declared_dependencies("") == set()
        assert _declared_dependencies("not = [toml") is None

    def test_an_unparseable_pyproject_is_named_in_the_report(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("not = [toml", encoding="utf-8")
        body = "def test_a(mocker):\n    assert mocker\n"
        result = check_spec_test_fixtures_resolvable(_section_10(body), str(tmp_path), "")
        assert result["passed"] is False
        assert "could not be parsed" in result["details"]

    def test_a_missing_pyproject_is_named_in_the_report(self, tmp_path: Path) -> None:
        body = "def test_a(mocker):\n    assert mocker\n"
        result = check_spec_test_fixtures_resolvable(_section_10(body), str(tmp_path), "")
        assert result["passed"] is False
        assert "no pyproject could be read" in result["details"]

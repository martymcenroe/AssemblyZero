"""A TypeScript test path in an LLD resolves to the runner the project has in
the directory that holds it, and a runner the project has nowhere halts the
run instead of running from the root (#4237).

The detector mapped every `.test.ts` to Jest and every `.spec.ts` to
Playwright from the suffix alone, and that guess outranked the project's own
files. `_configs_with_directories` then placed a framework the project did
not have at the repository root. So a spec naming `web/tests/replay.test.ts`
on a target whose `web/` runs Vitest ran Jest from a root with no
package.json.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing import framework_detector as fd
from assemblyzero.workflows.testing.graph import route_after_load
from assemblyzero.workflows.testing.nodes.load_lld import _load_from_issue

#: The module itself: `nodes/__init__` exports the `load_lld` function under
#: the same name.
load_lld_module = importlib.import_module("assemblyzero.workflows.testing.nodes.load_lld")

TF = fd.TestFramework


def _lld(*paths: str, extra: str = "") -> str:
    rows = "\n".join(f"| `{p}` | Add |" for p in paths)
    return (
        "## 2.1 Files Changed\n| File | Change Type |\n|------|-------------|\n"
        f"{rows}\n\n{extra}\n"
    )


def _vitest_web(root: Path) -> Path:
    """A Python root with no package.json, and Vitest in web/."""
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    web = root / "web"
    web.mkdir()
    (web / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")
    (web / "package.json").write_text(
        json.dumps({"devDependencies": {"vitest": "^2.1.0"}}), encoding="utf-8"
    )
    return root


class _Proc:
    def __init__(self, stdout: str) -> None:
        self.stdout, self.stderr, self.returncode = stdout, "", 0


def _issue_load(root: Path, body: str) -> dict:
    issue = json.dumps({"title": "Replay", "body": body})
    with patch.object(load_lld_module, "run_command", return_value=_Proc(issue)):
        return _load_from_issue({}, 9, root)


class TestAPathResolvesToItsDirectorysRunner:
    """T1 (R1)."""

    def test_a_test_ts_path_in_a_vitest_directory_is_vitest_in_that_directory(self, tmp_path):
        root = _vitest_web(tmp_path)
        lld = _lld("web/tests/replay.test.ts")
        assert fd.resolve_framework(lld, str(root)) == [TF.VITEST]
        assert fd.resolve_framework_dirs(lld, str(root)) == {TF.VITEST: "web"}

    def test_the_load_site_places_it_in_web(self, tmp_path):
        root = _vitest_web(tmp_path)
        result = _issue_load(root, _lld("web/tests/replay.test.ts"))
        assert result.get("error_message", "") == ""
        config = result["framework_config"]
        assert config["framework"] == "vitest"
        assert config["working_directory"] == "web"

    def test_a_spec_ts_path_beside_a_playwright_config_is_playwright(self, tmp_path):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "playwright.config.ts").write_text("", encoding="utf-8")
        lld = _lld("e2e/specs/login.spec.ts")
        assert fd.resolve_framework_dirs(lld, str(tmp_path)) == {TF.PLAYWRIGHT: "e2e"}

    def test_a_jest_dependency_makes_a_test_js_path_jest(self, tmp_path):
        app = tmp_path / "app"
        app.mkdir()
        (app / "package.json").write_text(
            json.dumps({"devDependencies": {"jest": "^29.0.0"}}), encoding="utf-8"
        )
        lld = _lld("app/src/sum.test.js")
        assert fd.resolve_framework_dirs(lld, str(tmp_path)) == {TF.JEST: "app"}

    def test_a_config_file_outranks_a_dependency(self, tmp_path):
        """A config is a declaration; a dependency says only that it is installed."""
        root = _vitest_web(tmp_path)
        (root / "web" / "package.json").write_text(
            json.dumps({"devDependencies": {"vitest": "^2", "jest": "^29"}}),
            encoding="utf-8",
        )
        lld = _lld("web/tests/replay.test.ts")
        assert fd.resolve_framework_dirs(lld, str(root)) == {TF.VITEST: "web"}

    def test_a_vitest_suite_beside_a_python_suite_is_both(self, tmp_path):
        root = _vitest_web(tmp_path)
        lld = _lld("tests/test_replay.py", "web/tests/replay.test.ts")
        assert fd.resolve_framework_dirs(lld, str(root)) == {
            TF.VITEST: "web", TF.PYTEST: ".",
        }

    def test_a_keyword_in_prose_adds_no_runner_beside_a_resolved_path(self, tmp_path):
        """'Jest-compatible' beside a Vitest path is prose, not a second runner;
        taking it would halt the run for a framework the project lacks."""
        root = _vitest_web(tmp_path)
        lld = _lld("web/tests/replay.test.ts", extra="Uses Vitest's Jest-compatible expect API.")
        assert fd.resolve_framework_dirs(lld, str(root)) == {TF.VITEST: "web"}

    def test_two_runners_one_directory_and_no_way_to_choose_halts(self, tmp_path):
        both = tmp_path / "web"
        both.mkdir()
        (both / "vitest.config.ts").write_text("", encoding="utf-8")
        (both / "jest.config.js").write_text("", encoding="utf-8")
        with pytest.raises(fd.FrameworkResolutionError, match="vitest.*jest|jest.*vitest"):
            fd.resolve_framework(_lld("web/a.test.ts"), str(tmp_path))

    def test_a_glob_is_not_a_test_file(self, tmp_path):
        """`*.test.ts` describes files; it names none, so it places nothing."""
        root = _vitest_web(tmp_path)
        assert fd.named_js_test_paths("all `*.test.ts` files under web/") == []
        assert fd.resolve_framework("all `*.test.ts` files", str(root)) == [
            TF.PYTEST, TF.VITEST,
        ], "silent on a runner, so the project's files decide"


class TestARunnerTheProjectDoesNotHaveHalts:
    """T2 (R2)."""

    def test_a_test_ts_path_with_no_runner_anywhere_halts_at_the_load_site(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        result = _issue_load(tmp_path, _lld("tests/replay.test.ts"))
        message = result["error_message"]
        assert "tests/replay.test.ts" in message
        assert "searched" in message and "tests" in message
        assert "framework_config" not in result, "nothing is placed at the root"
        assert route_after_load(result) == "HALT"

    def test_the_resolver_refuses_it(self, tmp_path):
        with pytest.raises(fd.FrameworkResolutionError, match="replay.test.ts"):
            fd.resolve_framework(_lld("tests/replay.test.ts"), str(tmp_path))

    def test_a_named_framework_the_project_has_nowhere_halts(self, tmp_path):
        """An explicit declaration of a runner the project does not have
        names the runner and every directory searched."""
        root = _vitest_web(tmp_path)
        with pytest.raises(fd.FrameworkResolutionError) as caught:
            fd.resolve_framework_dirs("Test Framework: Jest", str(root))
        message = str(caught.value)
        assert "jest" in message
        assert "web" in message and "." in message

    def test_pytest_is_never_refused_for_want_of_a_declaration(self, tmp_path):
        """pytest runs at the root by construction and needs nothing installed
        there, so a new Python project is not halted."""
        assert fd.resolve_framework_dirs(_lld("tests/test_new.py"), str(tmp_path)) == {
            TF.PYTEST: ".",
        }


class TestAnExplicitDeclarationStillWins:
    """T3 (R3)."""

    def test_an_explicit_jest_line_still_resolves_to_jest(self, tmp_path):
        root = _vitest_web(tmp_path)
        lld = _lld("web/tests/replay.test.ts", extra="Test framework: jest")
        assert fd.resolve_framework(lld, str(root))[0] == TF.JEST

    def test_an_explicit_vitest_line_needs_no_path_to_resolve(self, tmp_path):
        root = _vitest_web(tmp_path)
        assert fd.resolve_framework_dirs("Test framework: vitest", str(root)) == {
            TF.VITEST: "web",
        }

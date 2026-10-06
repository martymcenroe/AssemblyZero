"""A target whose JavaScript project lives in a subdirectory gets its Vitest
or Jest suite detected and run there (#3707).

Before this, `detect_framework_from_project` read only the repository root,
so a target with `pyproject.toml` at the root and `web/package.json` beside it
was seen as pytest only; and the non-pytest runners were built with the
registry's bare config and started at the root, where there is no
`package.json`.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from assemblyzero.workflows.testing import framework_detector as fd
from assemblyzero.workflows.testing.runner_registry import get_framework_config, get_runner
from assemblyzero.workflows.testing.runners import base_runner
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner


def _physics_split_target(root: Path) -> Path:
    """pyproject at the root, the web app under web/, and two directories the
    detector must not descend into."""
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    web = root / "web"
    web.mkdir()
    (web / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8"
    )
    (web / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")
    (web / "tests").mkdir()
    (web / "tests" / "engine.test.ts").write_text("", encoding="utf-8")
    for decoy in ("node_modules/some-dep", "data/mock-runs/x"):
        d = root / decoy
        d.mkdir(parents=True)
        (d / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}), encoding="utf-8")
    return root


class TestDetection:
    def test_the_web_subdirectory_is_seen_with_its_directory(self, tmp_path):
        root = _physics_split_target(tmp_path)
        assert fd.detect_framework_dirs(str(root)) == {
            fd.TestFramework.PYTEST: ".",
            fd.TestFramework.VITEST: "web",
        }
        assert fd.detect_framework_from_project(str(root)) == [
            fd.TestFramework.PYTEST, fd.TestFramework.VITEST,
        ]

    def test_node_modules_and_data_are_never_descended_into(self, tmp_path):
        root = _physics_split_target(tmp_path)
        assert fd.TestFramework.JEST not in fd.detect_framework_dirs(str(root))

    def test_the_root_keeps_its_old_order(self, tmp_path):
        """A root-only JavaScript project is detected as it was: config files,
        then package.json, then pytest."""
        (tmp_path / "jest.config.js").write_text("", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text("pytest\n", encoding="utf-8")
        assert fd.detect_framework_from_project(str(tmp_path)) == [
            fd.TestFramework.JEST, fd.TestFramework.PYTEST,
        ]
        assert fd.detect_framework_dirs(str(tmp_path))[fd.TestFramework.JEST] == "."

    def test_two_levels_down_is_found_and_three_is_not(self, tmp_path):
        deep = tmp_path / "apps" / "web"
        deep.mkdir(parents=True)
        (deep / "vitest.config.ts").write_text("", encoding="utf-8")
        deeper = tmp_path / "a" / "b" / "c"
        deeper.mkdir(parents=True)
        (deeper / "jest.config.js").write_text("", encoding="utf-8")
        dirs = fd.detect_framework_dirs(str(tmp_path))
        assert dirs == {fd.TestFramework.VITEST: os.path.join("apps", "web")}

    def test_a_declaration_in_unleashed_json_wins(self, tmp_path):
        root = _physics_split_target(tmp_path)
        (root / ".unleashed.json").write_text(
            json.dumps({"test_dirs": {"vitest": "app"}}), encoding="utf-8"
        )
        assert fd.detect_framework_dirs(str(root))[fd.TestFramework.VITEST] == "app"

    def test_an_unreadable_package_json_is_refused_not_skipped(self, tmp_path):
        (tmp_path / "web").mkdir()
        (tmp_path / "web" / "package.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError, match="package.json could not be read"):
            fd.detect_framework_dirs(str(tmp_path))

    def test_a_declaration_naming_no_framework_is_refused(self, tmp_path):
        (tmp_path / ".unleashed.json").write_text(
            json.dumps({"test_dirs": {"mocha": "web"}}), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="mocha"):
            fd.detect_framework_dirs(str(tmp_path))

    def test_n0_puts_each_directory_on_its_config(self, tmp_path):
        from assemblyzero.workflows.testing.nodes.load_lld import _configs_with_directories

        root = _physics_split_target(tmp_path)
        configs = _configs_with_directories(
            [fd.TestFramework.VITEST, fd.TestFramework.PYTEST, fd.TestFramework.JEST], str(root)
        )
        assert [c["working_directory"] for c in configs] == ["web", None, None], (
            "detected in web/; at the root; named by the LLD but not found, so the root"
        )


class _Runner(BaseTestRunner):
    """The base class's behaviour, with nothing to run."""

    def run_tests(self, test_paths=None, extra_args=None):  # pragma: no cover
        raise NotImplementedError

    def parse_results(self, raw_output, exit_code):  # pragma: no cover
        raise NotImplementedError

    def validate_test_file(self, file_path, content):  # pragma: no cover
        return []

    def get_scaffold_imports(self):  # pragma: no cover
        return ""


class TestRunnerDirectory:
    def test_the_registry_puts_the_directory_on_the_config(self):
        config = get_framework_config(fd.TestFramework.VITEST)
        assert config["working_directory"] is None
        runner = _Runner(config | {"working_directory": "web"}, "/repo")
        assert runner.project_dir == os.path.join("/repo", "web")
        assert _Runner(config, "/repo").project_dir == "/repo"

    def test_the_subprocess_runs_in_the_project_directory(self, tmp_path, monkeypatch):
        seen: dict = {}

        def fake_run_command(command, **kwargs):
            seen["cwd"] = kwargs.get("cwd")

            class R:
                stdout, stderr, returncode = "", "", 0

            return R()

        monkeypatch.setattr(base_runner, "run_command", fake_run_command)
        config = get_framework_config(fd.TestFramework.VITEST) | {"working_directory": "web"}
        _Runner(config, str(tmp_path))._run_subprocess(["npx", "vitest", "run"])
        assert Path(seen["cwd"]) == tmp_path / "web"

    def test_test_paths_are_made_relative_to_the_project_directory(self, tmp_path):
        config = get_framework_config(fd.TestFramework.VITEST) | {"working_directory": "web"}
        runner = _Runner(config, str(tmp_path))
        paths = [
            "web/tests/engine.test.ts",
            str(tmp_path / "web" / "tests" / "pack.test.ts"),
            "tests/unit/test_compiler.py",
        ]
        assert runner._paths_for_runner(paths) == [
            os.path.join("tests", "engine.test.ts"),
            os.path.join("tests", "pack.test.ts"),
            "tests/unit/test_compiler.py",
        ]
        assert runner._paths_for_runner(None) is None

    @pytest.mark.skipif(shutil.which("npx") is None, reason="JestRunner needs npx on PATH")
    def test_get_runner_carries_the_directory_into_the_vitest_runner(self, tmp_path):
        runner = get_runner(fd.TestFramework.VITEST, str(tmp_path), working_directory="web")
        assert runner.project_dir == os.path.join(str(tmp_path), "web")
        assert get_runner(fd.TestFramework.VITEST, str(tmp_path), working_directory=".").project_dir == str(tmp_path)

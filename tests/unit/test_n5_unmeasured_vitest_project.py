"""A Vitest project N5 never measures needs no coverage provider (#4686, #4687).

An implementation run against a TypeScript target with two Vitest projects,
the run's own in `web/` and a contributor kit in `kit/web/`, wrote all eight
of its files and passed the completeness gate, then halted at N5: the kit had
no `@vitest/coverage-v8`. The run changed nothing in the kit, so the
full-suite gate runs its suite once, without coverage. The preflight and the
gate both asked for a provider anyway.

`base_runner.run_command` stands in for npx, as in
`test_vitest_measures_coverage.py`; nothing real runs.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.nodes import verify_phases as vp
from assemblyzero.workflows.testing.nodes.load_lld import _log_frameworks
from assemblyzero.workflows.testing.runner_registry import get_runner
from assemblyzero.workflows.testing.runners import base_runner, jest_runner

KIT = {"framework": "vitest", "coverage_type": "line", "working_directory": "kit/web"}
WEB = {"framework": "vitest", "coverage_type": "line", "working_directory": "web"}


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _project(root: Path, directory: str, *, provider: bool) -> None:
    """A Vitest project with its own vitest, and a provider only if asked."""
    project = root / directory
    (project / "tests").mkdir(parents=True)
    (project / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8"
    )
    (project / "node_modules" / ".bin").mkdir(parents=True)
    (project / "node_modules" / ".bin" / "vitest").write_text("", encoding="utf-8")
    if provider:
        (project / "node_modules" / "@vitest" / "coverage-v8").mkdir(parents=True)
        (project / "node_modules" / "@vitest" / "coverage-v8" / "package.json").write_text(
            "{}", encoding="utf-8"
        )


@pytest.fixture
def root(tmp_path) -> Path:
    """A repository with the run's project in web/ and a kit with no provider."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _project(repo, "web", provider=True)
    _project(repo, "kit/web", provider=False)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "base")
    return repo


def _vitest(root: Path, directory: str):
    with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        return get_runner(TestFramework.VITEST, str(root), working_directory=directory)


def _passing_npx(command, **kwargs):
    report = {"numPassedTests": 4, "numFailedTests": 0, "numPendingTests": 0, "numTotalTests": 4}
    return subprocess.CompletedProcess(
        args=command, returncode=0, stdout=json.dumps(report), stderr="",
    )


class TestT1TheRunnerAsksForWhatTheRunNeeds:
    def test_without_coverage_vitest_alone_is_enough(self, root):
        _vitest(root, "kit/web").require_dependencies(measure_coverage=False)

    def test_with_coverage_the_provider_is_still_required(self, root):
        with pytest.raises(OSError) as raised:
            _vitest(root, "kit/web").require_dependencies()

        assert "@vitest/coverage-v8" in str(raised.value)
        assert str(root / "kit" / "web") in str(raised.value)

    def test_without_coverage_vitest_itself_is_still_required(self, root):
        (root / "kit" / "web" / "node_modules" / ".bin" / "vitest").unlink()

        with pytest.raises(OSError):
            _vitest(root, "kit/web").require_dependencies(measure_coverage=False)


class TestT2TheFullSuiteGateMeasuresNothing:
    def test_runs_a_project_with_no_provider(self, root, capsys):
        with patch.object(base_runner, "run_command", side_effect=_passing_npx), \
             patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
            gate = vp._full_suite_gate({}, root, TestFramework.VITEST, KIT, 0, 10)

        assert gate is None, gate
        assert "cannot run" not in capsys.readouterr().out


class TestT3ThePreflightAsksPerLeg:
    def _legs(self, root: Path, kit_files: tuple[str, ...]) -> list:
        return [
            vp._Leg(WEB, TestFramework.VITEST, "web", ("web/tests/a.test.ts",)),
            vp._Leg(KIT, TestFramework.VITEST, "kit/web", kit_files),
        ]

    def test_a_gate_only_leg_needs_no_provider(self, root):
        with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
            vp._preflight_legs({"repo_root": str(root)}, self._legs(root, ()))

    def test_a_leg_with_test_files_still_needs_one(self, root):
        with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"), \
             pytest.raises(vp.FrameworkLegError) as raised:
            vp._preflight_legs(
                {"repo_root": str(root)}, self._legs(root, ("kit/web/tests/b.test.ts",))
            )

        assert "vitest (kit/web)" in str(raised.value)
        assert "@vitest/coverage-v8" in str(raised.value)


class TestTheLogNamesEveryProject:
    """#4687: a second Vitest project no longer hides the first."""

    def test_both_vitest_projects_are_named(self, root, capsys):
        _log_frameworks("", str(root), [WEB, {"framework": "pytest"}], [KIT])

        out = capsys.readouterr().out
        assert "scaffold, red and green: ['vitest (web)', 'pytest']" in out
        assert "full-suite gate: ['vitest (web)', 'pytest', 'vitest (kit/web)']" in out

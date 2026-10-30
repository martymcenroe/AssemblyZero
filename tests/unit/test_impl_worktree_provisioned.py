"""A run installs its worktree's environment before any node runs (#4238).

The standalone runner cut its worktree with plain `git worktree add` and
installed nothing, and the orchestrator ran `poetry install` with no `npm ci`
half. Poetry keys its environments to the checkout path, so a new worktree has
none of its own, and `node_modules` is never committed: on a target with a
Python suite at its root and a Vitest suite in `web/`, the tests ran against
whatever environment happened to resolve.

No test here runs a real `poetry install` or `npm ci`. `_Installs` stands in
the subprocess layer for those two tools only, recording each call's argv,
working directory and environment; every git command runs for real against a
throwaway repository with a bare origin.
"""
# ruff: noqa: F811 -- the landing tests' fixtures are imported and requested by name.
from __future__ import annotations

import io
import os
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from assemblyzero.core import merge_driver
from tests.unit.test_impl_lands_through_driver import (  # noqa: F401 (fixtures)
    COMPLETED,
    _FakeWorkflow,
    _git,
    _Landed,
    driver_configured,
    target_repo,
)

PYPROJECT = (
    "[tool.poetry]\n"
    'name = "target"\n'
    'version = "0.1.0"\n'
    "\n"
    "[tool.pytest.ini_options]\n"
    'testpaths = ["tests"]\n'
)
PACKAGE_JSON = (
    '{"name": "web", "scripts": {"test": "vitest run"}, '
    '"devDependencies": {"vitest": "^2.0.0"}}\n'
)
PACKAGE_LOCK = '{"name": "web", "lockfileVersion": 3, "requires": true, "packages": {}}\n'


def _commit(target: Path, files: dict[str, str], message: str) -> Path:
    for rel, text in files.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(target, "add", ".")
    _git(target, "commit", "-qm", message)
    _git(target, "push", "-q", "origin", "main")
    return target


@pytest.fixture
def mixed_target(target_repo: Path) -> Path:
    """A Python package at the root and a Vitest suite in `web/`, with its lock."""
    return _commit(target_repo, {
        "pyproject.toml": PYPROJECT,
        "web/package.json": PACKAGE_JSON,
        "web/package-lock.json": PACKAGE_LOCK,
    }, "python at the root, vitest in web")


class _Installs:
    """The subprocess layer for `poetry` and `npm`. Each call is recorded with
    its argv, working directory and environment, and answered from ``fail``
    (``{tool: (exit code, output)}``; exit 0 otherwise). Every other command
    runs for real."""

    TOOLS = ("poetry", "npm")

    def __init__(self, fail: dict | None = None, events: list | None = None):
        self.calls: list[SimpleNamespace] = []
        self.fail = fail or {}
        self.events = events if events is not None else []
        self._real = subprocess.run

    def __call__(self, argv, *args, **kwargs):
        if isinstance(argv, (list, tuple)) and argv and Path(str(argv[0])).name in self.TOOLS:
            tool = Path(str(argv[0])).name
            cwd = kwargs.get("cwd")
            self.calls.append(SimpleNamespace(
                argv=list(argv),
                cwd=Path(cwd).resolve() if cwd else None,
                exists=bool(cwd) and Path(cwd).is_dir(),
                env=kwargs.get("env"),
            ))
            self.events.append(" ".join(str(a) for a in argv))
            code, output = self.fail.get(tool, (0, ""))
            return subprocess.CompletedProcess(argv, code, stdout="", stderr=output)
        return self._real(argv, *args, **kwargs)

    def pairs(self) -> list[tuple[list[str], Path | None]]:
        return [(c.argv, c.cwd) for c in self.calls]


@pytest.fixture
def installs(monkeypatch) -> _Installs:
    stand_in = _Installs()
    monkeypatch.setattr(subprocess, "run", stand_in)
    return stand_in


def _main(target: Path, tmp_path: Path, *extra: str, events: list | None = None):
    """``tools/run_implement_from_lld.py main()`` with a stand-in graph that
    records when it is built. Returns (exit code, stdout, the build stand-in)."""
    from tools import run_implement_from_lld as tool

    workflow = _FakeWorkflow(COMPLETED)

    def build():
        if events is not None:
            events.append("graph built")
        return workflow

    argv = ["prog", "--issue", "42", "--repo", str(target), "--auto",
            "--db-path", str(tmp_path / "ckpt.db"), *extra]
    out = io.StringIO()
    with patch("sys.argv", argv), redirect_stdout(out), \
         patch("assemblyzero.workflows.testing.build_testing_workflow",
               side_effect=build) as built:
        try:
            rc = tool.main()
        except SystemExit as exc:
            rc = exc.code
    return rc, out.getvalue(), built


def _env_lines(out: str) -> list[str]:
    return [line for line in out.splitlines() if "[ENV]" in line]


# --- T1 (R1): the standalone run installs both, after the cut, before the graph


class TestT1TheStandaloneRunInstallsBothEnvironments:
    def test_t1_poetry_at_the_root_and_npm_ci_in_web_before_the_graph(
        self, mixed_target, tmp_path, driver_configured, monkeypatch, operator_alerts,
    ):
        events: list[str] = []
        stand_in = _Installs(events=events)
        monkeypatch.setattr(subprocess, "run", stand_in)
        monkeypatch.setattr(merge_driver, "land", _Landed())

        rc, out, _ = _main(mixed_target, tmp_path, events=events)

        wt = (mixed_target.parent / "target-42").resolve()
        assert rc == 0, out
        assert stand_in.pairs() == [
            (["poetry", "install"], wt),
            (["npm", "ci"], wt / "web"),
        ], out
        assert all(c.exists for c in stand_in.calls), "an install ran before the worktree was cut"
        assert events == ["poetry install", "npm ci", "graph built"]
        assert operator_alerts == []

    def test_t1_the_installs_run_in_the_targets_environment_not_the_workflows(
        self, mixed_target, tmp_path, driver_configured, monkeypatch, installs,
    ):
        """Under `poetry run`, VIRTUAL_ENV would make `poetry install` install
        the target's dependencies into AssemblyZero's own virtualenv."""
        az_venv = tmp_path / "az-venv"
        monkeypatch.setenv("VIRTUAL_ENV", str(az_venv))
        monkeypatch.setenv("POETRY_ACTIVE", "1")
        monkeypatch.setenv("PATH", os.pathsep.join([str(az_venv / "bin"), "/usr/bin", "/bin"]))
        monkeypatch.setattr(merge_driver, "land", _Landed())

        rc, out, _ = _main(mixed_target, tmp_path)

        assert rc == 0, out
        assert installs.calls, "nothing was installed"
        for call in installs.calls:
            assert call.env is not None, f"{call.argv} inherited the workflow's environment"
            assert "VIRTUAL_ENV" not in call.env and "POETRY_ACTIVE" not in call.env
            assert str(az_venv / "bin") not in call.env["PATH"].split(os.pathsep)


# --- T2 (R2): a failed install stops the run before any model call -----------


class TestT2AFailedInstallStopsTheRun:
    @pytest.mark.parametrize("tool, command, where", [
        ("poetry", "poetry install", "."),
        ("npm", "npm ci", "web"),
    ])
    def test_t2_exit_1_one_alert_naming_it_and_no_graph(
        self, tool, command, where, mixed_target, tmp_path, driver_configured,
        monkeypatch, operator_alerts, capsys,
    ):
        output = f"{tool}: could not resolve the dependency set"
        stand_in = _Installs(fail={tool: (1, output)})
        monkeypatch.setattr(subprocess, "run", stand_in)
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)

        rc, out, built = _main(mixed_target, tmp_path)

        directory = (mixed_target.parent / "target-42" / where).resolve()
        assert rc == 1, out
        built.assert_not_called()
        assert land.calls == []
        assert len(operator_alerts) == 1, operator_alerts
        alert = operator_alerts[0]
        assert command in alert["cause"]
        assert str(directory) in alert["cause"]
        assert output in alert["cause"]
        assert "provisioning" in alert["where"]
        assert "ERROR" in capsys.readouterr().err
        if tool == "poetry":
            assert [c.argv for c in stand_in.calls] == [["poetry", "install"]], (
                "an install ran after one had failed"
            )

    def test_t2_a_javascript_suite_with_no_lock_file_stops_the_run(
        self, target_repo, tmp_path, monkeypatch, installs, operator_alerts,
    ):
        """`npm ci` needs a lock file. Without one the Vitest suite would run
        against whatever node_modules resolves, so the run does not start. A
        mock run plans the same step, so it stops the same way."""
        _commit(target_repo, {"web/package.json": PACKAGE_JSON}, "vitest, no lock")

        rc, out, built = _main(target_repo, tmp_path, "--mock")

        assert rc == 1, out
        built.assert_not_called()
        assert installs.calls == []
        assert len(operator_alerts) == 1, operator_alerts
        cause = operator_alerts[0]["cause"]
        assert "package-lock.json" in cause and str(target_repo.parent / "target-42" / "web") in cause


# --- R4: the mock rehearsal takes the same step, offline ----------------------


class TestAMockRunPlansTheInstallsAndRunsNone:
    def test_r4_mock_names_each_planned_install_and_runs_none(
        self, mixed_target, tmp_path, monkeypatch, installs, operator_alerts,
    ):
        rc, out, _ = _main(mixed_target, tmp_path, "--mock")

        assert rc == 0, out
        assert installs.calls == []
        lines = _env_lines(out)
        assert len(lines) == 2, lines
        assert "`poetry install`" in lines[0] and "mock run" in lines[0]
        assert "`npm ci`" in lines[1] and "web" in lines[1]
        assert operator_alerts == []

    def test_r4_nothing_to_install_is_said_in_one_line(
        self, target_repo, tmp_path, installs, operator_alerts,
    ):
        rc, out, _ = _main(target_repo, tmp_path, "--mock")

        assert rc == 0, out
        assert installs.calls == []
        lines = _env_lines(out)
        assert len(lines) == 1, lines
        assert "nothing to install" in lines[0]
        assert operator_alerts == []


# --- T3 (R3): the orchestrator path runs both installs ------------------------


class _SubWorkflow:
    """The testing graph, as the impl stage builds and invokes it."""

    def __init__(self, events: list[str]):
        self.events = events
        self.invoked: list[dict] = []

    def __call__(self):
        self.events.append("graph built")
        return self

    def compile(self, **_kwargs):
        return self

    def invoke(self, payload, config=None):
        self.invoked.append(payload)
        return {"workflow_status": "completed", "error_message": ""}


def _impl_stage(target: Path, monkeypatch, events: list[str], **state):
    from assemblyzero.workflows.orchestrator import stages

    sub = _SubWorkflow(events)
    monkeypatch.setattr("assemblyzero.workflows.testing.graph.build_testing_workflow", sub)
    base = {
        "issue_number": 42,
        "current_stage": "impl",
        "target_repo": str(target),
        "assemblyzero_root": str(target.parent / "az"),
        "base_branch": "",
        "config": {},
    }
    base.update(state)
    return stages.run_impl_stage(base), sub


def _stage_worktree(target: Path) -> Path:
    return (target / "data" / "worktrees" / "42").resolve()


class TestT3TheOrchestratorInstallsBothEnvironments:
    def test_t3_poetry_at_the_root_and_npm_ci_in_web_before_the_sub_workflow(
        self, mixed_target, monkeypatch, capsys,
    ):
        events: list[str] = []
        stand_in = _Installs(events=events)
        monkeypatch.setattr(subprocess, "run", stand_in)

        result, sub = _impl_stage(mixed_target, monkeypatch, events)

        wt = _stage_worktree(mixed_target)
        assert result["stage_results"]["impl"]["status"] == "passed", result["stage_results"]
        assert stand_in.pairs() == [
            (["poetry", "install"], wt),
            (["npm", "ci"], wt / "web"),
        ]
        assert events == ["poetry install", "npm ci", "graph built"]
        assert len(sub.invoked) == 1

    def test_t3_a_reused_worktree_is_installed_too(self, mixed_target, monkeypatch, capsys):
        """A resume, or a retry after a failed install, finds the worktree on
        disk. It used to skip the install and run on the tree as it was."""
        stand_in = _Installs()
        monkeypatch.setattr(subprocess, "run", stand_in)
        _impl_stage(mixed_target, monkeypatch, [])
        stand_in.calls.clear()

        result, _ = _impl_stage(mixed_target, monkeypatch, [], resumed_from="impl")

        wt = _stage_worktree(mixed_target)
        assert result["stage_results"]["impl"]["status"] == "passed", result["stage_results"]
        assert stand_in.pairs() == [
            (["poetry", "install"], wt),
            (["npm", "ci"], wt / "web"),
        ]

    def test_t3_a_failed_install_fails_the_stage_and_its_halt_alerts(
        self, mixed_target, monkeypatch, operator_alerts, capsys,
    ):
        from assemblyzero.core.halt_node import create_halt_node
        from assemblyzero.workflows.orchestrator.graph import _route_after_stage

        output = "npm ERR! `npm ci` can only install with an existing lock in sync"
        monkeypatch.setattr(subprocess, "run", _Installs(fail={"npm": (1, output)}))

        result, sub = _impl_stage(mixed_target, monkeypatch, [])

        web = _stage_worktree(mixed_target) / "web"
        impl = result["stage_results"]["impl"]
        assert impl["status"] == "failed", impl
        assert impl.get("transient") is False, "a failed install was queued for a retry"
        for part in ("npm ci", str(web), output):
            assert part in impl["error_message"], impl["error_message"]
        assert sub.invoked == [], "the sub-workflow ran on an unprovisioned worktree"
        assert _route_after_stage(result) == "terminal"
        assert "ERROR" in capsys.readouterr().err

        create_halt_node("orchestrator")(result)
        halts = [a for a in operator_alerts if "workflow halted" in a["what"]]
        assert len(halts) == 1, operator_alerts
        assert "npm ci" in halts[0]["cause"] and str(web) in halts[0]["cause"]
        assert output in halts[0]["cause"]

    def test_t3_a_mock_rehearsal_installs_nothing(self, mixed_target, monkeypatch, capsys):
        stand_in = _Installs()
        monkeypatch.setattr(subprocess, "run", stand_in)

        result, _ = _impl_stage(
            mixed_target, monkeypatch, [], config={"mock_mode": True},
        )

        assert result["stage_results"]["impl"]["status"] == "passed", result["stage_results"]
        assert stand_in.calls == []
        out = capsys.readouterr().out
        assert "`poetry install`" in out and "`npm ci`" in out and "mock run" in out

    def test_t3_the_installs_run_in_the_targets_environment(
        self, mixed_target, monkeypatch, tmp_path, capsys,
    ):
        az_venv = tmp_path / "az-venv"
        monkeypatch.setenv("VIRTUAL_ENV", str(az_venv))
        monkeypatch.setenv("POETRY_ACTIVE", "1")
        stand_in = _Installs()
        monkeypatch.setattr(subprocess, "run", stand_in)

        _impl_stage(mixed_target, monkeypatch, [])

        assert stand_in.calls, "nothing was installed"
        for call in stand_in.calls:
            assert call.env is not None, f"{call.argv} inherited the workflow's environment"
            assert "VIRTUAL_ENV" not in call.env and "POETRY_ACTIVE" not in call.env


# --- The step itself ----------------------------------------------------------


def _runner(code: int = 0, output: str = "", raises: BaseException | None = None):
    calls: list[list[str]] = []

    def run(argv, **kwargs):
        calls.append(list(argv))
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(argv, code, stdout="", stderr=output)

    return run, calls


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _javascript_root(root: Path) -> Path:
    """A Vitest suite at the root, with its lock."""
    return _tree(root, {"package.json": PACKAGE_JSON, "package-lock.json": PACKAGE_LOCK})


class TestEveryJavaScriptSuiteIsInstalled:
    """`npm ci` runs in every directory that holds a lock file and is, or is
    under, a JavaScript suite's directory, read from the files on disk; a
    package.json there with no lock beside it stops the run."""

    def test_every_locked_directory_in_or_under_a_suite(self, tmp_path):
        from assemblyzero.workflows.provisioning import npm_install_dirs

        _tree(tmp_path, {
            "sentinel/package.json": '{"name": "sentinel"}\n',
            "sentinel/package-lock.json": PACKAGE_LOCK,
            "web/package.json": PACKAGE_JSON,
            "web/package-lock.json": PACKAGE_LOCK,
            "web/admin/package.json": '{"name": "admin"}\n',
            "web/admin/package-lock.json": PACKAGE_LOCK,
            "web/node_modules/left-pad/package.json": '{"name": "left-pad"}\n',
            "dashboard/package.json": '{"name": "dashboard"}\n',
            "dashboard/package-lock.json": PACKAGE_LOCK,
        })

        found = npm_install_dirs(tmp_path, ["sentinel", "web", "web"])

        assert found == [tmp_path / "sentinel", tmp_path / "web", tmp_path / "web" / "admin"]

    def test_a_package_json_with_no_lock_under_a_suite_stops_the_run(self, tmp_path):
        from assemblyzero.workflows.provisioning import (
            ProvisioningError,
            npm_install_dirs,
        )

        _tree(tmp_path, {
            "web/package.json": PACKAGE_JSON,
            "web/package-lock.json": PACKAGE_LOCK,
            "web/admin/package.json": '{"name": "admin"}\n',
        })

        with pytest.raises(ProvisioningError) as caught:
            npm_install_dirs(tmp_path, ["web"])
        assert str(tmp_path / "web" / "admin") in str(caught.value)
        assert "package-lock.json" in str(caught.value)

    def test_the_plan_installs_the_suite_the_detector_finds_and_nothing_else(self, tmp_path):
        """AssemblyZero's own shape: a Vitest suite in sentinel/, and a
        dashboard/ with a package and its lock but no test runner."""
        from assemblyzero.workflows.provisioning import provision_worktree

        _tree(tmp_path, {
            "sentinel/vitest.config.ts": "export default {}\n",
            "sentinel/package.json": '{"name": "sentinel"}\n',
            "sentinel/package-lock.json": PACKAGE_LOCK,
            "dashboard/package.json": '{"name": "dashboard"}\n',
            "dashboard/package-lock.json": PACKAGE_LOCK,
        })
        cwds: list[str] = []

        def run(argv, **kwargs):
            cwds.append(kwargs["cwd"])
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        provision_worktree(tmp_path, run=run)

        assert cwds == [str(tmp_path / "sentinel")]

    def test_a_lock_with_no_javascript_suite_is_not_installed(self, tmp_path):
        from assemblyzero.workflows.provisioning import provision_worktree

        _tree(tmp_path, {"package.json": '{"name": "tools"}\n', "package-lock.json": PACKAGE_LOCK})
        run, calls = _runner()

        lines = provision_worktree(tmp_path, run=run)

        assert calls == []
        assert len(lines) == 1 and "nothing to install" in lines[0], lines


class TestTheStep:
    def test_a_tooling_only_pyproject_is_not_a_project_to_install(self, tmp_path):
        """A pyproject.toml that only configures tools has nothing for poetry
        to install, and `poetry install` refuses it; that is an answer, not a
        failure."""
        from assemblyzero.workflows.provisioning import provision_worktree

        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
        run, calls = _runner()

        lines = provision_worktree(tmp_path, run=run)

        assert calls == []
        assert len(lines) == 1 and "nothing to install" in lines[0], lines

    def test_a_pyproject_that_is_not_toml_stops_the_run(self, tmp_path):
        from assemblyzero.workflows.provisioning import (
            ProvisioningError,
            provision_worktree,
        )

        (tmp_path / "pyproject.toml").write_text("[tool.poetry\n", encoding="utf-8")
        run, calls = _runner()

        with pytest.raises(ProvisioningError, match="pyproject.toml"):
            provision_worktree(tmp_path, run=run)
        assert calls == []

    def test_a_command_that_cannot_start_names_itself(self, tmp_path):
        from assemblyzero.workflows.provisioning import (
            ProvisioningError,
            provision_worktree,
        )

        _javascript_root(tmp_path)
        run, _ = _runner(raises=FileNotFoundError(2, "No such file or directory", "npm"))

        with pytest.raises(ProvisioningError) as caught:
            provision_worktree(tmp_path, run=run)
        assert "`npm ci`" in str(caught.value) and str(tmp_path) in str(caught.value)
        assert "could not start" in str(caught.value)

    def test_an_install_that_times_out_is_a_failure(self, tmp_path):
        from assemblyzero.workflows.provisioning import (
            ProvisioningError,
            provision_worktree,
        )

        _javascript_root(tmp_path)
        timeout = subprocess.TimeoutExpired(["npm", "ci"], 1800, output=b"added 12 packages")
        run, _ = _runner(raises=timeout)

        with pytest.raises(ProvisioningError) as caught:
            provision_worktree(tmp_path, run=run)
        assert "did not finish" in str(caught.value)
        assert "added 12 packages" in str(caught.value)

    def test_on_windows_npm_is_resolved_through_pathext(self, tmp_path, monkeypatch):
        """npm on Windows is npm.cmd, which CreateProcess cannot find from a
        bare name; shutil.which applies PATHEXT."""
        from assemblyzero.workflows import provisioning

        _javascript_root(tmp_path)
        monkeypatch.setattr(provisioning.sys, "platform", "win32")
        monkeypatch.setattr(
            provisioning.shutil, "which",
            lambda name: rf"C:\Program Files\nodejs\{name}.cmd",
        )
        run, calls = _runner()

        provisioning.provision_worktree(tmp_path, run=run)

        assert calls == [[r"C:\Program Files\nodejs\npm.cmd", "ci"]]

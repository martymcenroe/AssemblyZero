"""#4495: the spec's import check asks the target's environment.

`_target_env_python` ran `poetry env info --path` with the inherited environment.
A workflow runs under `poetry run`, so VIRTUAL_ENV named AssemblyZero's virtualenv
and poetry answered with that: on every real run the check judged the target by
what AssemblyZero had installed. #4490 fixed the same defect in the test runner.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import venv

import pytest

vc = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
)

WORKFLOW_ENV = "/home/someone/.cache/pypoetry/virtualenvs/assemblyzero-tools"


@pytest.fixture
def inside_a_workflow(monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", WORKFLOW_ENV)
    monkeypatch.setenv("POETRY_ACTIVE", "1")
    monkeypatch.setenv("PATH", f"{WORKFLOW_ENV}/bin:/usr/bin")


def _shed(env: dict[str, str]) -> None:
    assert "VIRTUAL_ENV" not in env
    assert "POETRY_ACTIVE" not in env
    assert WORKFLOW_ENV not in env["PATH"]
    assert "/usr/bin" in env["PATH"]


def test_t1_poetry_is_asked_with_the_workflows_environment_shed(
    inside_a_workflow, monkeypatch, tmp_path,
):
    env_dir = tmp_path / "env"
    (env_dir / "bin").mkdir(parents=True)
    (env_dir / "bin" / "python").write_text("", encoding="utf-8")
    seen = {}

    def run(command, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout=f"{env_dir}\n", stderr="")

    monkeypatch.setattr(vc.subprocess, "run", run)

    assert vc._target_env_python(tmp_path) == str(env_dir / "bin" / "python")
    _shed(seen["env"])


def test_t2_the_probe_runs_under_the_same_environment(inside_a_workflow, monkeypatch, tmp_path):
    seen = {}

    def run(command, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout='{"x": true}\n', stderr="")

    monkeypatch.setattr(vc, "_target_env_python", lambda root: sys.executable)
    monkeypatch.setattr(vc.subprocess, "run", run)

    assert vc._probe_target_env(tmp_path, ["x"]) == {"x": True}
    _shed(seen["env"])


def test_t3_a_module_only_this_process_has_is_not_the_targets(monkeypatch, tmp_path):
    target_env = tmp_path / "target-env"
    venv.create(target_env, with_pip=False)
    monkeypatch.setattr(vc, "_target_env_python", lambda root: str(target_env / "bin" / "python"))

    assert "pytest" in sys.modules
    assert vc._probe_target_env(tmp_path, ["pytest", "json"]) == {"pytest": False, "json": True}

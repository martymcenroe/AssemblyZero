"""Each framework of the run is judged against its own coverage target, and
the target is a percentage everywhere (#3089).

`runner_registry.py` declared `coverage_target` on all four framework
configs, as fractions (0.95, and 1.0 for Playwright), and nothing read it:
every gate read the run's flat `coverage_target`, an integer percentage from
the LLD. The issue left two repairs open, govern or delete. This governs, and
resolves the unit mismatch deliberately: the field is now
`coverage_target_percent`, an integer percentage like every other target in
the run, so a fraction left in a checkpoint from before can never be read as
0.95% and make a gate unfailable.

N0 writes each framework's target: the one the LLD declares, for every
framework, or, when the LLD declares none, the framework's own default (95
for line coverage, 100 for Playwright's scenario coverage). The green phase
judges each framework by its own config.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.load_lld import _mock_load_lld, load_lld
from assemblyzero.workflows.testing.nodes.verify_phases import _verify_green_non_pytest
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners import base_runner, jest_runner

pytestmark = pytest.mark.usefixtures("coverage_as_reported")  # #4436: routing, not measuring

SPEC = """# 7 - Engine replay

**Status:** APPROVED

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/engine.py` | Add | The replay engine |

## 3. Requirements

1. REQ-1: The engine replays a recorded session.

{coverage}

## 10. Test Plan

### test_replay_round_trip
Verify that a recorded session replays to the same final state.
Requirement: REQ-1
"""


def _mixed_target(root: Path) -> Path:
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n", encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_engine.py").write_text(
        "def test_engine():\n    assert True\n", encoding="utf-8"
    )
    web = root / "web"
    (web / "tests").mkdir(parents=True)
    (web / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8"
    )
    (web / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")
    (web / "node_modules" / ".bin").mkdir(parents=True)
    (web / "node_modules" / ".bin" / "vitest").write_text("", encoding="utf-8")
    (web / "node_modules" / "@vitest" / "coverage-v8").mkdir(parents=True)
    return root


def _targets(configs: list[dict]) -> dict[str, object]:
    return {c["framework"]: c.get("coverage_target_percent") for c in configs}


# ---------------------------------------------------------------------------
# The registry: one unit, percent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("framework, percent", [
    (TestFramework.PYTEST, 95), (TestFramework.JEST, 95),
    (TestFramework.VITEST, 95), (TestFramework.PLAYWRIGHT, 100),
])
def test_the_registry_declares_an_integer_percentage(framework, percent):
    config = get_framework_config(framework)
    assert config["coverage_target_percent"] == percent
    assert isinstance(config["coverage_target_percent"], int)
    assert "coverage_target" not in config, "the fraction is gone, not kept beside it"


# ---------------------------------------------------------------------------
# N0 writes every framework's target
# ---------------------------------------------------------------------------


def test_a_declared_target_governs_every_framework(tmp_path):
    root = _mixed_target(tmp_path)
    spec = root / "spec-7.md"
    spec.write_text(SPEC.format(coverage="Coverage target: 85%"), encoding="utf-8")
    result = load_lld({"issue_number": 7, "repo_root": str(root), "lld_path": str(spec)})

    assert result.get("error_message", "") == ""
    assert result["coverage_target"] == 85
    assert _targets(result["framework_configs"]) == {"pytest": 85, "vitest": 85}


def test_with_no_declared_target_each_framework_keeps_its_own(tmp_path):
    root = _mixed_target(tmp_path)
    spec = root / "spec-7.md"
    spec.write_text(SPEC.format(coverage=""), encoding="utf-8")
    result = load_lld({"issue_number": 7, "repo_root": str(root), "lld_path": str(spec)})

    assert _targets(result["framework_configs"]) == {"pytest": 95, "vitest": 95}


def test_the_mock_load_site_writes_its_own_target_on_each(tmp_path):
    root = _mixed_target(tmp_path)
    result = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
    assert _targets(result["framework_configs"]) == {"pytest": 90, "vitest": 90}
    assert result["framework_config"]["coverage_target_percent"] == 90


# ---------------------------------------------------------------------------
# The green phase reads the framework's own target
# ---------------------------------------------------------------------------


def _npx(pct: float):
    def run(command, **kwargs):
        cwd = Path(kwargs["cwd"])
        if any(a.startswith("--coverage") for a in command):
            (cwd / "coverage").mkdir(exist_ok=True)
            (cwd / "coverage" / "coverage-summary.json").write_text(
                json.dumps({"total": {"lines": {"pct": pct}}}), encoding="utf-8"
            )
        return subprocess.CompletedProcess(
            args=command, returncode=0, stderr="",
            stdout=json.dumps({"numPassedTests": 3, "numFailedTests": 0,
                               "numPendingTests": 0, "numTotalTests": 3}),
        )
    return run


def test_the_vitest_leg_is_judged_by_its_own_target_not_the_runs(tmp_path):
    root = _mixed_target(tmp_path)
    config = {"framework": "vitest", "coverage_type": "line",
              "working_directory": "web", "coverage_target_percent": 80}
    state = {
        "test_files": [str(root / "web" / "tests" / "a.test.ts")],
        "repo_root": str(root), "issue_number": 7,
        "coverage_target": 95,
        "iteration_count": 0, "max_iterations": 5, "audit_dir": "",
        "file_counter": 0, "full_suite_validated": True,
        "framework_config": config, "framework_configs": [config],
    }
    with patch.object(base_runner, "run_command", side_effect=_npx(85)), \
         patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        result = _verify_green_non_pytest(state, config, TestFramework.VITEST)

    assert result["error_message"] == ""
    assert result["next_node"] == "N6_e2e_validation", "85% meets vitest's own 80%"


def test_coverage_target_reads_the_config_and_falls_back_to_the_run(tmp_path):
    target = verify_phases._coverage_target
    assert target({"coverage_target": 95}, {"coverage_target_percent": 80}) == 80
    assert target({"coverage_target": 95}, {}) == 95, (
        "a checkpoint from before #3089 carries no per-framework target; the "
        "run's governed every framework then"
    )
    assert target({"coverage_target": 95}, {"coverage_target": 0.95}) == 95, (
        "the old fraction is never read"
    )


def test_each_legs_state_carries_its_own_framework_config(tmp_path):
    """The pytest leg of a two-framework run reads `framework_config` from its
    state, so the leg's state must hold the leg's own config."""
    root = _mixed_target(tmp_path)
    loaded = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
    state = {**loaded, "repo_root": str(root),
             "test_files": [str(root / "tests" / "test_engine.py"),
                            str(root / "web" / "tests" / "a.test.ts")]}
    legs = verify_phases._framework_legs(state)
    for leg in legs:
        assert verify_phases._leg_state(state, leg)["framework_config"] == leg.config

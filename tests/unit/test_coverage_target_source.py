"""`--coverage-target` wins on every load path, and the run says which target
it uses and where it came from (#4266, #4436 R6).

ADR 0207 says a run below 95% "must specify --coverage-target with
justification". On the spec path the flag lost to the LLD's number without a
word: N0 wrote the LLD's declared target over the state's, for the run and for
every framework. T1 and T2 are #4266's tests, and T7 of #4436.
"""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes.load_lld import (
    _load_from_issue,
    _mock_load_lld,
    load_lld,
    resolve_coverage_target,
)

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


def _target(root: Path) -> Path:
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n', encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_engine.py").write_text(
        "def test_engine():\n    assert True\n", encoding="utf-8",
    )
    return root


def _spec_state(root: Path, coverage: str, **overrides) -> dict:
    spec = root / "spec-7.md"
    spec.write_text(SPEC.format(coverage=coverage), encoding="utf-8")
    return {"issue_number": 7, "repo_root": str(root), "lld_path": str(spec), **overrides}


def test_t1_the_flag_wins_over_the_llds_target_on_the_spec_path(tmp_path, capsys):
    """Fails before the fix: the run used the LLD's 80."""
    root = _target(tmp_path)

    result = load_lld(_spec_state(root, "Coverage target: 80%", coverage_target=95))

    assert result.get("error_message", "") == ""
    assert result["coverage_target"] == 95
    assert result["framework_config"]["coverage_target_percent"] == 95, "and the gate reads this"
    assert "--coverage-target" in result["coverage_target_source"]
    assert "Coverage target: 95% (--coverage-target" in capsys.readouterr().out


def test_t2_with_no_flag_the_llds_target_is_used_and_named_as_its_source(tmp_path, capsys):
    root = _target(tmp_path)

    state = _spec_state(root, "Coverage target: 80%")
    result = load_lld(state)

    assert result["coverage_target"] == 80
    assert result["framework_config"]["coverage_target_percent"] == 80
    assert result["coverage_target_source"] == f"declared in the spec at {state['lld_path']}"
    assert "Coverage target: 80% (declared in the spec at" in capsys.readouterr().out


def test_with_neither_the_run_says_it_is_adr_0207s_default(tmp_path):
    root = _target(tmp_path)

    result = load_lld(_spec_state(root, ""))

    assert result["coverage_target"] == 95
    assert result["coverage_target_source"] == "ADR 0207's default"


def test_a_flag_of_zero_is_still_the_flag(tmp_path):
    root = _target(tmp_path)

    result = load_lld(_spec_state(root, "Coverage target: 80%", coverage_target=0))

    assert result["coverage_target"] == 0
    assert result["framework_config"]["coverage_target_percent"] == 0


def test_the_flag_wins_on_the_issue_only_path(tmp_path):
    root = _target(tmp_path)
    body = "Coverage: 80%\n\n## 2. Files to Implement\n\n| Order | File | Change Type | Description |\n"
    body += "|---|---|---|---|\n| 1 | `src/engine.py` | Add | The engine |\n\n"
    body += "## 3. Requirements\n\n1. REQ-1: It replays.\n\n## 10. Test Plan\n\n"
    body += "### test_replay\nReplays.\nRequirement: REQ-1\n"

    def gh(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[], returncode=0, stderr="",
            stdout=json.dumps({"title": "Engine", "body": body}),
        )

    module = importlib.import_module("assemblyzero.workflows.testing.nodes.load_lld")

    with patch.object(module, "run_command", side_effect=gh):
        flagged = _load_from_issue({"coverage_target": 95}, 7, root)
        declared = _load_from_issue({}, 7, root)

    assert flagged["coverage_target"] == 95
    assert flagged["framework_config"]["coverage_target_percent"] == 95
    assert declared["coverage_target"] == 80
    assert "issue #7" in declared["coverage_target_source"]


def test_the_flag_wins_on_the_mock_path(tmp_path):
    root = _target(tmp_path)

    result = _mock_load_lld({"issue_number": 7, "repo_root": str(root), "coverage_target": 70})

    assert result["coverage_target"] == 70
    assert result["framework_config"]["coverage_target_percent"] == 70
    assert "--coverage-target" in result["coverage_target_source"]


@pytest.mark.parametrize("state, content, target, governing", [
    ({"coverage_target": 95}, "Coverage: 80%", 95, 95),
    ({}, "Coverage: 80%", 80, 80),
    ({}, "no target here", 95, None),
], ids=["flag", "declared", "default"])
def test_one_function_decides_for_the_run_and_for_every_framework(state, content, target, governing):
    got, governs, _source = resolve_coverage_target(state, content, "the spec")

    assert (got, governs) == (target, governing), (
        "a framework keeps its own default only when nothing declares one"
    )


def test_the_target_reaches_the_launchers_state():
    """`--coverage-target 0` must not be dropped by a truthiness test."""
    source = (
        Path(__file__).resolve().parents[2] / "tools" / "run_implement_from_lld.py"
    ).read_text(encoding="utf-8")

    assert "if args.coverage_target is not None:" in source

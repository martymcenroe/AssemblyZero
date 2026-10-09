"""The orchestrated roll lands through the fleet merge driver (#3717, #3740, #3741).

This machine's gh wrapper refuses `gh pr create` and `gh pr merge` from any
process that is not the merge driver. #3704 moved the LLD workflow onto the
driver; the orchestrator's pr and cleanup stages still called gh themselves.
Found on boostgauge #2 (runs run-issue2-230238 and run-issue2-001443,
2026-10-06/07): the LLD was approved and never landed, nothing said so, and the
relaunch could not resume because the planner wanted an open LLD PR the driver
never leaves behind.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core import merge_driver
from assemblyzero.workflows.orchestrator import stages
from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.state import create_initial_state

AZ_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AZ_ROOT / "tools"))

import speedrun_roll

ARC = "hardening-run-17"


def write_state(az_root, issue, *, target_repo, base_branch=ARC, lld_status="passed",
                failed_stage="impl", lld_path="", spec_path=""):
    """The orchestrator state resume_plan reads, as test_resume_after_failure writes it."""
    import json

    state_dir = az_root / ".assemblyzero" / "orchestrator" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    stage_results = {"triage": {"status": "skipped"}, "lld": {"status": lld_status}}
    if failed_stage:
        stage_results[failed_stage] = {"status": "failed", "error_message": "boom"}
    (state_dir / f"{issue}.json").write_text(json.dumps({
        "issue_number": issue, "current_stage": failed_stage or "lld",
        "target_repo": str(target_repo), "base_branch": base_branch,
        "lld_path": lld_path, "spec_path": spec_path, "stage_results": stage_results,
    }), encoding="utf-8")


def _resp(returncode=0, stdout="", stderr=""):
    out = MagicMock()
    out.returncode = returncode
    out.stdout = stdout
    out.stderr = stderr
    return out


def _pr_state(tmp_path):
    worktree = tmp_path / "wt"
    worktree.mkdir()
    state = create_initial_state(
        2, get_default_config(),
        target_repo=str(tmp_path / "target"),
        assemblyzero_root=str(tmp_path / "az"),
    )
    state.update(worktree_path=str(worktree), base_branch=ARC)
    return state


@pytest.fixture
def gh_calls():
    """Every command the stage hands run_command; rev-parse names the branch."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        if cmd[:2] == ["git", "rev-parse"]:
            return _resp(stdout="2-implementation\n")
        return _resp()

    with patch.object(stages, "run_command", side_effect=fake_run), \
         patch.object(stages, "_reconcile_stale_remote_branch", return_value=""):
        yield calls


# ---------------------------------------------------------------------------
# #3717: the pr stage
# ---------------------------------------------------------------------------


def test_the_pr_stage_lands_through_the_driver(tmp_path, gh_calls):
    landed = {}

    def fake_land(**kwargs):
        landed.update(kwargs)
        return merge_driver.Landing(pr_number=17, squash_sha="deadbee", output="")

    with patch.object(merge_driver, "land", side_effect=fake_land), \
         patch.object(stages, "_pr_url_for", return_value="https://github.com/o/r/pull/17"):
        new_state = stages.run_pr_stage(_pr_state(tmp_path))

    assert landed["issue"] == 2
    assert landed["base"] == ARC
    assert landed["branch"] == "2-implementation"
    assert "Closes #2" in landed["title"]
    assert "Closes #2" in Path(landed["body_file"]).read_text(encoding="utf-8")
    assert not [c for c in gh_calls if c[:3] in (["gh", "pr", "create"], ["gh", "pr", "merge"])]
    assert not [c for c in gh_calls if c[:2] == ["git", "push"]], "the driver pushes"
    assert new_state["impl_pr_url"] == "https://github.com/o/r/pull/17"
    assert new_state["impl_squash_sha"] == "deadbee"
    assert new_state["stage_results"]["pr"]["status"] == "passed"


def test_a_driver_refusal_fails_the_pr_stage_once(tmp_path, gh_calls):
    """The driver's refusals are decisions: not transient, output carried."""
    refusal = merge_driver.MergeDriverError("the merge driver did not land 2-implementation (exit 1):\n[FAIL] stage=poll_terminal_bad")
    with patch.object(merge_driver, "land", side_effect=refusal):
        new_state = stages.run_pr_stage(_pr_state(tmp_path))

    result = new_state["stage_results"]["pr"]
    assert result["status"] == "failed"
    assert "poll_terminal_bad" in result["error_message"]
    assert result.get("transient") is False


# ---------------------------------------------------------------------------
# #3717: orchestrate.py refuses without the driver
# ---------------------------------------------------------------------------


def test_orchestrate_refuses_without_the_driver(tmp_path):
    # #3729: the child checks the alert channel first, where the tiers' stand-in
    # cannot reach; it gets a working one, so the driver refusal is what is tested.
    from tests.conftest import child_env_with_alert_channel

    env = child_env_with_alert_channel(
        {k: v for k, v in os.environ.items() if k != merge_driver.DRIVER_ENV}
    )
    proc = subprocess.run(
        [sys.executable, str(AZ_ROOT / "tools" / "orchestrate.py"),
         "--issue", "2", "--repo", str(tmp_path)],
        cwd=str(AZ_ROOT), env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "merge driver not configured" in proc.stdout
    assert merge_driver.DRIVER_ENV in proc.stdout


# ---------------------------------------------------------------------------
# #3740: an approved LLD that did not land is said, and fails the stage
# ---------------------------------------------------------------------------


def test_finalize_says_the_lld_did_not_land(tmp_path, capsys):
    import importlib

    from assemblyzero.workflows.requirements.git_operations import GitOperationError

    # The nodes package re-exports the `finalize` function under the module's name.
    finalize_mod = importlib.import_module("assemblyzero.workflows.requirements.nodes.finalize")

    state = {
        "created_files": [str(tmp_path / "LLD-002.md")],
        "workflow_type": "lld", "issue_number": 2,
        "target_repo": str(tmp_path), "base_branch": ARC,
    }
    with patch.object(finalize_mod, "setup_lld_worktree", return_value=(tmp_path / "wt", "2-lld")), \
         patch.object(finalize_mod, "_mirror_to_worktree", return_value=["x"]), \
         patch.object(finalize_mod, "commit_and_pr",
                      side_effect=GitOperationError("Failed to land 2-lld: AZ_MERGE_DRIVER is not set")):
        out = finalize_mod._commit_and_push_files(state)

    printed = capsys.readouterr().out
    assert "[LLD] NOT LANDED:" in printed
    assert "AZ_MERGE_DRIVER is not set" in printed
    assert "AZ_MERGE_DRIVER is not set" in out["commit_error"]


def test_the_lld_stage_fails_when_the_lld_did_not_land(tmp_path):
    config = get_default_config()
    config["skip_existing_lld"] = False
    state = create_initial_state(
        2, config, target_repo=str(tmp_path / "target"), assemblyzero_root=str(tmp_path / "az"),
    )
    lld_file = tmp_path / "target" / "docs" / "lld" / "active" / "LLD-002.md"
    lld_file.parent.mkdir(parents=True)
    lld_file.write_text("# LLD\n\nAPPROVED")
    result = {
        "final_lld_path": str(lld_file),
        "final_verdict": "APPROVED",
        "commit_error": "Failed to land 2-lld: AZ_MERGE_DRIVER is not set",
    }

    class _App:
        def invoke(self, payload, *args, **kwargs):
            return result

        def stream(self, payload, *args, **kwargs):
            yield result

    class _Graph:
        def compile(self):
            return _App()

    with patch(
        "assemblyzero.workflows.requirements.graph.create_requirements_graph",
        return_value=_Graph(),
    ):
        new_state = stages.run_lld_stage(state)

    stage = new_state["stage_results"]["lld"]
    assert stage["status"] == "failed", stage
    assert "not landed" in stage["error_message"]
    assert "AZ_MERGE_DRIVER" in stage["error_message"]
    assert stage.get("transient") is False


# ---------------------------------------------------------------------------
# #3741: resume after the driver landed the LLD; every decline is said
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "Test"],
    ):
        subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    (root / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True, check=False)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], capture_output=True, check=False)
    return root


@pytest.fixture
def landed_state(tmp_path, repo, monkeypatch):
    az_root = tmp_path / "az"
    az_root.mkdir()
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    monkeypatch.setattr(speedrun_roll, "_open_lld_pr_exists", lambda *_a: False)
    monkeypatch.setattr(speedrun_roll, "draft_is_stale", lambda *_a: False)
    lld = repo / "docs" / "lld" / "active" / "LLD-002.md"
    lld.parent.mkdir(parents=True)
    lld.write_text("# LLD\n", encoding="utf-8")
    # The spec stays on the working tree in the gitignored lineage (it does not
    # ride the LLD PR), which is where the live run left it.
    spec = repo / "docs" / "lineage" / "active" / "2-implspec" / "spec-0002-final-spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Spec\n", encoding="utf-8")
    write_state(az_root, 2, target_repo=repo, lld_path=str(lld), spec_path=str(spec),
                failed_stage="impl")
    return az_root


def _events(tmp_path) -> str:
    path = tmp_path / "session-events.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_a_driver_landed_lld_resumes(tmp_path, repo, landed_state, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "_lld_landed_on_base", lambda *_a: True)
    log = speedrun_roll.EventLog(tmp_path / "session-events.log")
    assert speedrun_roll.resume_plan(landed_state, repo, 2, log) == "impl", _events(tmp_path)


def test_an_lld_that_never_left_the_machine_is_declined_aloud(tmp_path, repo, landed_state, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "_lld_landed_on_base", lambda *_a: False)
    log = speedrun_roll.EventLog(tmp_path / "session-events.log")
    assert speedrun_roll.resume_plan(landed_state, repo, 2, log) is None
    events = _events(tmp_path)
    assert "RESUME declined for #2:" in events
    assert f"origin/{ARC}" in events


def test_lld_landed_on_base_reads_the_attempt_branch(tmp_path, repo):
    """A real remote: the LLD file on origin/<base> is the proof."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], capture_output=True, check=False)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], capture_output=True, check=False)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", ARC], capture_output=True, check=False)
    lld = repo / "docs" / "lld" / "active" / "LLD-002.md"
    lld.parent.mkdir(parents=True)
    lld.write_text("# LLD\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], capture_output=True, check=False)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "lld"], capture_output=True, check=False)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", ARC], capture_output=True, check=False)

    assert speedrun_roll._lld_landed_on_base(repo, 2, ARC) is True
    assert speedrun_roll._lld_landed_on_base(repo, 3, ARC) is False


@pytest.mark.parametrize(
    "setup, reason",
    [
        ("no_state", "no orchestrator state"),
        ("other_base", "is not the attempt branch"),
        ("lld_failed", "the lld stage did not pass"),
    ],
)
def test_each_decline_names_its_check(tmp_path, repo, monkeypatch, setup, reason):
    az_root = tmp_path / "az"
    az_root.mkdir()
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    if setup == "other_base":
        write_state(az_root, 2, target_repo=repo, base_branch="hardening-run-1")
    elif setup == "lld_failed":
        write_state(az_root, 2, target_repo=repo, lld_status="failed", failed_stage="lld")
    log = speedrun_roll.EventLog(tmp_path / "session-events.log")

    assert speedrun_roll.resume_plan(az_root, repo, 2, log) is None
    assert reason in _events(tmp_path)

"""The launcher's refusals that sit between preflight and roll.

#4257: the contract-fidelity preflight's refuse flag stops a launch with exit
91, as the form preflight's does.

The gate is driven through `speedrun_roll.main`, so "starts nothing" is an
assertion about what the launcher did (no roll, no detach), not about a helper.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_roll  # noqa: E402


@pytest.fixture
def target_repo(tmp_path) -> Path:
    """The launcher validates --repo is a git repository root first."""
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "Test"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, text=True)
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], capture_output=True)
    return tmp_path


@pytest.fixture
def launcher(monkeypatch, target_repo):
    """speedrun_roll.main with everything past the preflights stubbed out."""
    state = {"rolls": [], "detached": 0, "base_calls": 0}

    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda _root: [])
    monkeypatch.setattr(speedrun_roll, "open_must_resolve_issues", lambda _r: ([], None))
    monkeypatch.setattr(
        speedrun_roll, "sweep_pipeline_worktrees",
        lambda *_a, **_k: type("Sweep", (), {"problems": []})(),
    )
    monkeypatch.setattr(speedrun_roll, "install_signal_handlers", lambda _s: None)

    def fake_roll(repo_root, issue, log_dir, az_root, extra, *a, **k):
        state["rolls"].append(issue)
        return 0

    def fake_ensure_base(*_a, **_kw):
        state["base_calls"] += 1
        return "hardening-run-1"

    def fake_detach(*_a, **_kw):
        state["detached"] += 1
        return 0

    monkeypatch.setattr(speedrun_roll, "roll_issue", fake_roll)
    monkeypatch.setattr(speedrun_roll, "ensure_base", fake_ensure_base)
    monkeypatch.setattr(speedrun_roll, "launch_detached", fake_detach)
    return state


def _argv(target_repo, *issues, extra=()):
    args = ["--repo", str(target_repo), "--log-dir", str(target_repo / "logs")]
    for issue in issues:
        args += ["--issue", str(issue)]
    return args + list(extra)


class TestFidelityRefusalStopsTheLaunch:
    """#4257 T1 and T2."""

    def test_a_refusing_fidelity_preflight_returns_91_and_starts_nothing(
        self, launcher, monkeypatch, target_repo, capsys
    ):
        monkeypatch.setattr(
            speedrun_roll, "check_contract_fidelity_at_preflight",
            lambda *_a, **_k: ("CONTRACT FIDELITY\n  #4: the audit was NOT REACHED.", True),
        )

        code = speedrun_roll.main(_argv(target_repo, 4))

        assert code == 91
        assert launcher["rolls"] == [], "a refused launch must not roll"
        assert launcher["detached"] == 0
        assert launcher["base_calls"] == 0, "nothing may be set up after the refusal"
        out = capsys.readouterr().out
        assert "NOT REACHED" in out, "the preflight's own reason is printed"
        assert "BLOCKED" in out and "fidelity" in out

    def test_a_refusing_fidelity_preflight_stops_a_detached_launch_too(
        self, launcher, monkeypatch, target_repo
    ):
        monkeypatch.setattr(
            speedrun_roll, "check_contract_fidelity_at_preflight",
            lambda *_a, **_k: ("refused", True),
        )

        code = speedrun_roll.main(_argv(target_repo, 4, extra=["--detach"]))

        assert code == 91
        assert launcher["detached"] == 0

    def test_a_passing_fidelity_preflight_launches_as_before(
        self, launcher, monkeypatch, target_repo
    ):
        monkeypatch.setattr(
            speedrun_roll, "check_contract_fidelity_at_preflight",
            lambda *_a, **_k: ("CONTRACT FIDELITY\n  #4: no defect found.", False),
        )

        code = speedrun_roll.main(_argv(target_repo, 4))

        assert code == 0
        assert launcher["rolls"] == [4]

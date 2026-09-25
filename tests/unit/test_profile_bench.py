"""The bench: --models on the roll and the tools, resume safety, and the
comparison table (#3566, under #3562)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import compare_profiles  # noqa: E402
import speedrun_roll  # noqa: E402

from assemblyzero.core.seats import builtin_path, load_profile, set_run_profile  # noqa: E402


def _help(tool: str) -> str:
    result = subprocess.run(
        [sys.executable, str(TOOLS / tool), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO), timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


# ---------------------------------------------------------------------------
# T1: the flag, everywhere
# ---------------------------------------------------------------------------


class TestTheFlag:
    @pytest.mark.parametrize("tool", [
        "speedrun_roll.py", "orchestrate.py", "run_requirements_workflow.py",
        "run_implementation_spec_workflow.py", "run_implement_from_lld.py",
        "compare_profiles.py",
    ])
    def test_every_entry_point_offers_it(self, tool):
        text = _help(tool)
        assert "--models" in text or "--profiles" in text, tool

    def test_the_roll_forwards_it_to_the_detached_relaunch(self, tmp_path):
        args, extra = speedrun_roll.build_parser().parse_known_args(
            ["--repo", str(tmp_path), "--issue", "4", "--models", "claude"]
        )
        assert args.models == "claude"
        forwarded = [*extra, "--models", args.models]
        argv = speedrun_roll.detached_argv(args, forwarded, tmp_path, REPO, tmp_path)
        assert argv[-2:] == ["--models", "claude"]
        assert speedrun_roll._models_in(forwarded) == "claude"

    def test_the_run_start_line_names_the_profile(self, tmp_path):
        assert speedrun_roll._profile_label(tmp_path, ["--models", "claude"]) == "claude"
        assert speedrun_roll._profile_label(tmp_path, []) == "gemini"
        assert speedrun_roll._profile_label(tmp_path, ["--mock"]) == "mock"

    def test_a_bad_profile_is_refused_before_any_issue(self, tmp_path):
        (tmp_path / ".git").mkdir()
        code = speedrun_roll.main(
            ["--repo", str(tmp_path), "--issue", "4", "--models", "nonesuch"]
        )
        assert code == 91


# ---------------------------------------------------------------------------
# T2: a resume keeps its profile; a new profile is --fresh
# ---------------------------------------------------------------------------


def _persist(az_root: Path, issue: int, profile_name: str | None) -> None:
    path = speedrun_roll._orchestrator_state_path(az_root, issue)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"issue_number": issue}
    if profile_name:
        data["model_profile"] = load_profile(builtin_path(profile_name))
    path.write_text(json.dumps(data), encoding="utf-8")


class TestResumeSafety:
    def test_a_different_profile_is_refused_naming_both(self, tmp_path):
        _persist(tmp_path, 4, "gemini")
        refusal = speedrun_roll.profile_refusal(tmp_path, 4, "claude")
        assert "'gemini'" in refusal and "'claude'" in refusal and "--fresh" in refusal

    def test_the_same_profile_resumes(self, tmp_path):
        _persist(tmp_path, 4, "gemini")
        assert speedrun_roll.profile_refusal(tmp_path, 4, "gemini") == ""

    def test_state_from_before_profiles_resumes(self, tmp_path):
        _persist(tmp_path, 4, None)
        assert speedrun_roll.profile_refusal(tmp_path, 4, "claude") == ""

    def test_no_state_is_nothing_to_refuse(self, tmp_path):
        assert speedrun_roll.profile_refusal(tmp_path, 9, "claude") == ""

    def test_the_orchestrator_keeps_a_resumed_snapshot(self):
        """A resumed state that carries a profile keeps it; one that predates
        profiles takes the invocation's (orchestrator/graph.py)."""
        import inspect

        from assemblyzero.workflows.orchestrator import graph

        source = inspect.getsource(graph.orchestrate)
        assert 'if not isinstance(state_dict.get("model_profile"), dict) and model_profile:' in source


# ---------------------------------------------------------------------------
# T3: the comparison over two recorded mock rolls
# ---------------------------------------------------------------------------


def _roll_spec_graph(target: Path, profile_name: str, run_tag: str, monkeypatch) -> None:
    """The real spec graph, streamed under a profile, as test_mock_roll drives it."""
    from assemblyzero.core.scripted_provider import ScriptedProvider, set_active
    from assemblyzero.workflows.implementation_spec.graph import create_implementation_spec_graph

    monkeypatch.setenv("SPEEDRUN_RUN_TAG", run_tag)
    set_run_profile(load_profile(builtin_path(profile_name)))
    audit = target / "docs" / "lineage" / "active" / f"4-implspec-{profile_name}"
    audit.mkdir(parents=True, exist_ok=True)
    set_active(ScriptedProvider([], model="mock-roll"))
    try:
        for _ in create_implementation_spec_graph().stream(
            {
                "issue_number": 4,
                "lld_path": str(target / "docs" / "lld" / "active" / "LLD-004.md"),
                "repo_root": str(target),
                "audit_dir": str(audit),
                "max_iterations": 1,
                "human_gate_enabled": False,
                "config_drafter": "scripted:drafter",
                "config_reviewer": "scripted:reviewer",
                "review_iteration": 0,
                "error_message": "",
            },
            {"recursion_limit": 30},
        ):
            pass
    finally:
        set_active(None)
        set_run_profile(None)


def _calls(target: Path, profile: str, rows: list[tuple[str, str]]) -> None:
    path = target / "docs" / "lineage" / "active" / f"calls-{profile}" / "calls.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for seq, (seat, response) in enumerate(rows, 1):
            fh.write(json.dumps({
                "seq": seq, "run_tag": f"run-issue4-{profile}", "profile": profile,
                "seat": seat, "response": response,
            }) + "\n")


class TestTheComparison:
    def test_two_recorded_rolls_give_one_table_with_two_rows(self, tmp_path, monkeypatch, capsys):
        target = tmp_path / "target"
        target.mkdir()
        _roll_spec_graph(target, "gemini", "run-issue4-gemini", monkeypatch)
        _roll_spec_graph(target, "claude", "run-issue4-claude", monkeypatch)
        approved = json.dumps({"verdict": "APPROVED"})
        blocked = json.dumps({"verdict": "BLOCKED"})
        _calls(target, "gemini", [
            ("spec.draft", "d1"), ("spec.review", blocked),
            ("spec.draft", "d2"), ("spec.review", approved),
        ])
        _calls(target, "claude", [("spec.draft", "d1"), ("spec.review", approved)])
        capsys.readouterr()

        out = tmp_path / "comparison.md"
        assert compare_profiles.main(
            ["--repo", str(target), "--profiles", "gemini,claude", "--out", str(out)]
        ) == 0
        printed = capsys.readouterr().out

        table = [line for line in printed.splitlines() if line.startswith("|")]
        header = [c.strip() for c in table[0].strip("|").split("|")]
        assert header == list(compare_profiles.COLUMNS)
        rows = {line.split("|")[1].strip(): line for line in table[2:]}
        assert list(rows) == ["gemini", "claude"]
        assert "APPROVED 1 / BLOCKED 1" in rows["gemini"]
        assert "APPROVED 1 / BLOCKED 0" in rows["claude"]
        assert "spec 1.0" in rows["gemini"] and "spec 0.0" in rows["claude"]
        assert "spec.review 2" in rows["gemini"]
        assert "HALT" in rows["gemini"], "the graph halted without an LLD, by node"
        assert "1 of 1 issues in the key" in rows["gemini"], "#4 is in the answer key"
        assert out.read_text(encoding="utf-8").count("\n| ") >= 3

    def test_the_default_output_lands_under_the_repo(self, tmp_path, capsys):
        compare_profiles.main(["--repo", str(tmp_path)])
        written = list((tmp_path / "data" / "speedrun" / "comparisons").glob("*.md"))
        assert len(written) == 1

    def test_an_issue_is_read_from_the_run_tag(self):
        assert compare_profiles.issue_of("run-issue331-172000") == 331
        assert compare_profiles.issue_of("") is None


# ---------------------------------------------------------------------------
# T4: the runbook's commands parse
# ---------------------------------------------------------------------------


class TestTheRunbook:
    RUNBOOK = REPO / "docs" / "runbooks" / "0956-compare-model-profiles-on-boostgauge.md"

    def test_every_tool_it_names_answers_help(self):
        text = self.RUNBOOK.read_text(encoding="utf-8")
        tools = sorted({
            word.split("/", 1)[1]
            for line in text.splitlines() if line.startswith("poetry run python tools/")
            for word in line.split() if word.startswith("tools/")
        })
        assert tools == ["compare_profiles.py", "speedrun_roll.py"]
        for tool in tools:
            _help(tool)  # exits 0, or the helper fails the test

    def test_it_states_the_audition_cost(self):
        text = self.RUNBOOK.read_text(encoding="utf-8")
        assert "One profile file and one roll." in text

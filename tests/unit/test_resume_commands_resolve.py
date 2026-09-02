"""Every resume command names a file that exists, and there is only one (#2663).

Every orchestrator halt printed `poetry run python tools/run_orchestrator.py
--issue N`. That file exists in neither AssemblyZero nor any target repo, and
`testing` named `tools/run_tdd_workflow.py`, which does not exist either -- two
of the four entries were wrong, and the issue that found it had only spotted
one.

A halt is where an operator arrives with the least context and the most
urgency, and the resume line is the entire recovery affordance. It is also the
one line nobody exercises: a halt diagnosed by an agent never has its command
typed, so the path can be wrong indefinitely without anyone noticing. That is
precisely the shape a test fixes and a code review does not, and it is the
"audits are programs" rule -- a path string in a dict has no way to be wrong
loudly, so something has to ask it.
"""

from __future__ import annotations

import pytest

from pathlib import Path

from assemblyzero.core.recovery_plan import (
    RESUME_COMMANDS,
    build_resume_command,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestEveryMappedPathResolves:
    @pytest.mark.parametrize("workflow", sorted(RESUME_COMMANDS))
    def test_the_tool_exists(self, workflow: str) -> None:
        tool = REPO_ROOT / RESUME_COMMANDS[workflow]

        assert tool.is_file(), (
            f"{workflow!r} resumes with {RESUME_COMMANDS[workflow]}, which "
            f"does not exist. An operator reading a halt is handed this."
        )

    @pytest.mark.parametrize("workflow", sorted(RESUME_COMMANDS))
    def test_the_tool_accepts_the_flags_the_command_passes(
        self, workflow: str
    ) -> None:
        """Existing is not enough -- it has to take `--issue` and `--repo`.

        `build_resume_command` emits both, so a tool that exists and rejects
        one of them is still a broken instruction, just a slower one to
        diagnose.
        """
        source = (REPO_ROOT / RESUME_COMMANDS[workflow]).read_text(
            encoding="utf-8"
        )

        assert '"--issue"' in source, workflow
        assert '"--repo"' in source, workflow

    def test_the_map_is_not_empty(self) -> None:
        """Guards the parametrized tests from passing vacuously."""
        assert len(RESUME_COMMANDS) >= 4


class TestTheBuiltCommand:
    def test_an_orchestrator_halt_names_the_relaunch(self) -> None:
        command = build_resume_command(
            "orchestrator", 379, {"target_repo": "C:/x/boostgauge"}
        )

        assert "tools/speedrun_roll.py" in command
        assert "--issue 379" in command
        assert "--repo C:/x/boostgauge" in command

    def test_it_carries_no_placeholder(self) -> None:
        """The old line printed a literal `N` and a literal `<stage>`."""
        command = build_resume_command("orchestrator", 379, {})

        assert " N" not in command
        assert "<" not in command

    def test_a_subworkflow_halt_prefers_the_repo_over_the_worktree(
        self,
    ) -> None:
        """A resume must not be pointed at a worktree the halt may have removed."""
        command = build_resume_command(
            "testing",
            384,
            {
                "repo_root": "C:/x/boostgauge/data/worktrees/384",
                "original_repo_root": "C:/x/boostgauge",
            },
        )

        assert "--repo C:/x/boostgauge" in command
        assert "worktrees" not in command

    def test_the_worktree_is_used_when_it_is_all_there_is(self) -> None:
        command = build_resume_command(
            "testing", 384, {"repo_root": "C:/x/boostgauge"}
        )

        assert "--repo C:/x/boostgauge" in command

    def test_no_repo_in_state_omits_the_flag_rather_than_guessing(
        self,
    ) -> None:
        command = build_resume_command("orchestrator", 379, {})

        assert "--repo" not in command
        assert "--issue 379" in command

    def test_an_unknown_workflow_says_so_instead_of_inventing_a_path(
        self,
    ) -> None:
        """The old fallback built `tools/run_<name>_workflow.py` for anything.

        That is the same defect generalised: a guess that reads exactly like a
        fact, and the reason two wrong entries survived unnoticed.
        """
        command = build_resume_command("nonesuch", 1, {})

        assert "poetry run python" not in command
        assert "nonesuch" in command
        assert "no resume command is defined" in command


class TestThereIsOnlyOneProducer:
    """One halt, one instruction (#2663).

    `orchestrate.py` printed its own resume string in two places while the
    halt banner printed a third from `RESUME_COMMANDS`. All three disagreed.
    """

    def test_orchestrate_prints_no_resume_string_of_its_own(self) -> None:
        """Scoped to what a FAILURE prints, which is the thing that misled.

        `--help` text is deliberately not covered. `%(prog)s --issue 305
        --resume-from spec` in the argparse epilog documents this tool's own
        flag surface to someone who asked for the flag surface; it is neither
        an instruction handed to an operator at a halt nor a claim about which
        command resumes a run.
        """
        source = (REPO_ROOT / "tools" / "orchestrate.py").read_text(
            encoding="utf-8"
        )
        offenders = [
            line.strip()
            for line in source.splitlines()
            if "print(" in line
            and "Resume" in line
            and "_resume_line" not in line
        ]

        assert not offenders, offenders

    def test_both_orchestrate_resume_prints_use_the_shared_builder(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "orchestrate.py").read_text(
            encoding="utf-8"
        )

        assert source.count("_resume_line(") == 3  # 1 def + 2 call sites

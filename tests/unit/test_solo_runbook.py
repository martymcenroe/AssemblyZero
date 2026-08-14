"""Acceptance tests for the operator-solo runbook (#2087).

A runbook rots silently: a flag is renamed, a tool moves, and the document keeps
claiming otherwise until an operator follows it at 2am and it does not work.
These assert the claims against the code they describe.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / "docs/runbooks/0952-speedrun-operator-solo.md"
BABYSIT = ROOT / "docs/babysit-protocol.md"


def _text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


# --- "the runbook exists and follows the section conventions" -----------


def test_runbook_exists_with_the_required_sections():
    assert RUNBOOK.is_file()
    text = _text()
    for heading in ("## § Launch", "## § Watch", "## § Done", "## § Stop", "## § Inspect"):
        assert heading in text, f"missing {heading}"


def test_runbook_has_a_dated_header_with_its_issue():
    text = _text()
    assert "**Issue:** #2087" in text
    assert re.search(r"\*\*Date:\*\* \d{4}-\d{2}-\d{2}", text)


# --- "contains the paste-block evaluation prompt" -----------------------


def test_runbook_contains_the_paste_block():
    text = _text()
    assert "### The paste block" in text
    assert "per AssemblyZero" in text
    assert "0952-speedrun-operator-solo.md § Inspect" in text, (
        "the prompt must name the runbook it comes from, or a pasted prompt "
        "is unmoored from its procedure"
    )


def test_the_paste_block_forbids_the_agent_launching_anything():
    block = _text()[_text().index("### The paste block"):]
    # Collapse whitespace: the prompt is hard-wrapped, so a phrase can straddle
    # a newline and a naive substring check would miss it.
    flat = " ".join(block.lower().split())

    assert "do not launch" in flat
    assert "do not delete any branch or worktree" in flat


# --- "the launch section's flags match --help exactly" ------------------


def _help_flags() -> set[str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/speedrun_roll.py"), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return set(re.findall(r"--[a-z][a-z-]+", result.stdout))


def test_every_flag_the_runbook_names_exists_in_help():
    documented = set(re.findall(r"`(--[a-z][a-z-]+)`", _text()))
    # Flags named in the runbook's own prose about other tools are filtered by
    # taking only those in the launch table, which uses backticks exclusively.
    real = _help_flags()
    launcher_flags = {f for f in documented if f in real or f.startswith("--detach")}

    assert launcher_flags, "the runbook must document the launcher's flags"
    for flag in launcher_flags:
        assert flag in real, f"{flag} is documented but not in --help"


def test_the_runbook_documents_every_launcher_flag():
    real = _help_flags() - {"--help"}
    text = _text()
    for flag in real:
        assert f"`{flag}`" in text, f"{flag} exists but the runbook never mentions it"


# --- "the inspect checklist names tools and paths that exist" -----------


def test_every_tool_the_runbook_invokes_exists():
    text = _text()
    invoked = set(re.findall(r"tools/([a-z_]+\.py)", text))
    assert invoked, "the inspect section must name concrete tools"
    for tool in invoked:
        assert (ROOT / "tools" / tool).is_file(), f"tools/{tool} does not exist"


def test_every_referenced_document_exists():
    text = _text()
    for rel in set(re.findall(r"`(docs/[a-z0-9/._-]+\.md)`", text)):
        assert (ROOT / rel).is_file(), f"{rel} does not exist"


def test_the_inspect_section_covers_all_six_steps():
    text = _text()
    section = text[text.index("## § Inspect"):]
    for step in ("**1.", "**2.", "**3.", "**4.", "**5.", "**6."):
        assert step in section, f"inspect step {step} missing"

    lowered = section.lower()
    assert "detached-launcher.log" in lowered
    assert "prompt_failure_report.py" in lowered
    assert "campaign_timing_dashboard.py" in lowered
    assert "must-resolve" in lowered
    assert "speedrun_archive.py" in lowered
    assert "complete" in lowered and "--verify" in lowered


def _step_six() -> str:
    section = _text()[_text().index("## § Inspect"):]
    start = section.index("**6.")
    return section[start:section.index("### The paste block")]


def test_the_archive_step_requires_verifying_completeness():
    """#2353 changed HOW completeness is asserted, not whether it is.

    This asserted `"complete": true` appeared in the section, which was the
    old instruction to open index.json and read a value. The step now
    prescribes `--verify`, which checks the same thing and cannot be skimmed
    past. Audits are programs.
    """
    step = _step_six().lower()
    assert "--verify" in step, "completeness must be asserted by a command"
    assert "partial archive" in step and "deleting anything" in step, (
        "a partial archive must never be reported as done"
    )


def test_no_step_prescribes_reading_a_value_out_of_a_file():
    """The operator's second complaint, as an acceptance criterion (#2353).

    No step may tell a human to open a file and eyeball a value that a
    command can assert.
    """
    step = _step_six()
    assert "index.json" not in step, (
        "step 6 must not send the operator digging in a file for a value"
    )


def test_every_command_block_in_step_six_states_its_working_directory():
    """The operator's first complaint, as an acceptance criterion (#2353).

    Step 6's block was the only one in the section with no `cd`, so an
    operator arriving at it fresh had no stated cwd. Operator hit this
    2026-08-14.
    """
    blocks = re.findall(r"```bash\n(.*?)```", _step_six(), re.DOTALL)
    assert blocks, "step 6 should still document the manual invocation"
    for block in blocks:
        assert block.lstrip().startswith("cd "), (
            f"command block does not state its working directory:\n{block}"
        )


def test_step_six_reads_the_launcher_verdict_first():
    """A successful roll archives itself (#2353), so the step is a read."""
    step = _step_six().lower()
    assert "roll succeeded" in step or "launcher" in step
    assert "complete yes" in step
    assert "manifest ok" in step


# --- "babysit-protocol.md gains the pointer" ----------------------------


def test_babysit_protocol_points_at_the_solo_runbook_first():
    text = BABYSIT.read_text(encoding="utf-8")
    head = text[:1200]

    assert "0952-speedrun-operator-solo.md" in head, (
        "the pointer must be at the top, where someone opening the file sees it"
    )
    assert "default" in head.lower()
    assert "exception" in head.lower()


# --- the gates the runbook promises are actually wired ------------------


def test_the_three_launch_gates_named_in_the_runbook_are_real():
    """Each refusal row must correspond to something in the launcher."""
    import importlib

    sys.path.insert(0, str(ROOT / "tools"))
    speedrun_roll = importlib.import_module("speedrun_roll")
    import inspect as _inspect

    source = _inspect.getsource(speedrun_roll.main)
    assert "check_assemblyzero_tree" in source
    assert "check_box_health" in source
    assert "open_must_resolve_issues" in source


def test_the_storm_line_the_runbook_quotes_is_the_real_format():
    """#2206 replaced the backoff line with an end-the-issue line. The
    invariant is unchanged: whatever the runbook quotes as a sample must be
    what the launcher actually emits, or an operator reading the runbook is
    watching for a string that never appears."""
    import importlib
    import inspect as _inspect

    sys.path.insert(0, str(ROOT / "tools"))
    speedrun_roll = importlib.import_module("speedrun_roll")

    source = _inspect.getsource(speedrun_roll.main)
    assert "STORM ended" in source
    assert "nothing was redrawn (#2206)" in source
    text = _text()
    assert "STORM ended #4 -- the provider stopped answering" in text, (
        "the runbook quotes a sample line; it must match the emitted format"
    )
    assert "STORM BACKOFF" not in text, (
        "the retired backoff line must not survive in the runbook"
    )


def test_the_task_name_the_runbook_queries_is_the_real_one():
    import importlib

    sys.path.insert(0, str(ROOT / "tools"))
    speedrun_roll = importlib.import_module("speedrun_roll")

    assert speedrun_roll.TASK_NAME in _text(), (
        "the status command must query the task the launcher actually creates"
    )


def test_the_runbook_carries_the_msys_guard_on_the_schtasks_command():
    """Without it Git Bash rewrites /Query into a path and schtasks refuses."""
    text = _text()
    index = text.index("schtasks /Query")
    assert "MSYS_NO_PATHCONV=1" in text[max(0, index - 120):index]

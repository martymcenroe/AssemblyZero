"""The auto-reviewer's check-wait loop, executed rather than eyeballed (#2627).

The loop lives inline in `.github/workflows/auto-reviewer.yml` and cannot move
to a script file: it is a REUSABLE workflow, so when another repo calls it there
is no checkout of this repository and a sibling `.sh` would not exist. The bash
therefore has to stay in the YAML, which is exactly the kind of code that never
gets tested and quietly grows a ten-minute hole.

So these tests extract the real `run:` block from the real workflow file and run
it under bash with a stub `gh` on PATH. What is asserted is the shipped text,
not a paraphrase of it.

The defect: the loop treated every conclusion except `failure` and `cancelled`
as "still pending" and polled 30 times at 20s. `action_required` -- what the
sentinel posts when its issue-reference regex extracts a ref it cannot validate
-- fell into that gap. GitHub sets `conclusion` only when a check has COMPLETED,
so it was re-asking a finished question for ten minutes. 29 runs died that way
across the fleet in August, ~300 billed minutes.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "auto-reviewer.yml"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="needs bash to execute the workflow step"
)


def _wait_step_script() -> str:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = doc["jobs"]["auto-review"]["steps"]
    for step in steps:
        if step.get("name") == "Wait for required checks":
            return step["run"]
    raise AssertionError("the 'Wait for required checks' step is gone")


def _run(tmp_path: Path, conclusion: str | None, *, checks: str = "issue-reference",
         timeout: float = 60):
    """Execute the real step with a stub `gh` that reports `conclusion`.

    None means the check exists but has not completed (empty output), which is
    also what a check that was never created looks like to this loop.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    # The step calls `gh api ... --jq ...` and reads stdout. Printing nothing is
    # the "no conclusion yet" case.
    (bindir / "gh").write_text(
        "#!/usr/bin/env bash\n" + (f'printf "%s\\n" "{conclusion}"\n' if conclusion else "exit 0\n"),
        encoding="utf-8",
        newline="\n",
    )
    (bindir / "gh").chmod(0o755)

    script = tmp_path / "step.sh"
    script.write_text("set -u\n" + _wait_step_script(), encoding="utf-8", newline="\n")

    env = {
        **os.environ,
        "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        "GH_TOKEN": "stub",
        "PR_NUMBER": "1",
        "REQUIRED_CHECKS": checks,
        "REPO": "owner/repo",
        "HEAD_SHA": "deadbeef",
    }
    started = time.monotonic()
    try:
        # encoding is explicit: the step prints ✅/❌/⏳ and Windows would
        # otherwise decode stdout as cp1252 and blow up on them.
        proc = subprocess.run(
            ["bash", str(script)],
            env=env,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as expired:
        return expired, time.monotonic() - started
    return proc, time.monotonic() - started


class TestTerminalConclusionsFailFast:
    """Every one of these used to poll for ten minutes."""

    @pytest.mark.parametrize(
        "conclusion",
        ["action_required", "timed_out", "stale", "neutral", "skipped", "startup_failure"],
    )
    def test_completed_but_not_success_exits_immediately(self, tmp_path, conclusion):
        proc, elapsed = _run(tmp_path, conclusion)
        assert proc.returncode == 1, proc.stdout
        assert "will NOT approve" in proc.stdout
        assert elapsed < 15, (
            f"{conclusion} took {elapsed:.0f}s -- it is a COMPLETED state and must "
            "not be polled"
        )

    def test_the_fix_is_not_a_longer_allowlist(self):
        """Enumerating states is how action_required was missed in the first
        place. The terminal test must be "completed and not success", not a
        list that the next unlisted conclusion falls straight through.

        Comments are stripped before checking: the code comment explains the
        history and names the state, and matching on that would pass while the
        logic underneath was an allowlist again.
        """
        code = "\n".join(
            line.split("#", 1)[0] for line in _wait_step_script().splitlines()
        )
        assert '-n "$STATUS"' in code, "the terminal branch must test for any conclusion"
        for state in ("action_required", "timed_out", "stale", "neutral"):
            assert f'= "{state}"' not in code, (
                f"{state} is being compared by name -- that is the allowlist shape "
                "this fix exists to remove"
            )

    @pytest.mark.parametrize("conclusion", ["failure", "cancelled"])
    def test_the_previously_handled_states_still_fail_fast(self, tmp_path, conclusion):
        proc, elapsed = _run(tmp_path, conclusion)
        assert proc.returncode == 1
        assert elapsed < 15


class TestSuccessStillApproves:
    def test_success_exits_zero_without_waiting(self, tmp_path):
        proc, elapsed = _run(tmp_path, "success")
        assert proc.returncode == 0, proc.stdout
        assert "All required checks passed" in proc.stdout
        assert elapsed < 15

    def test_every_check_in_a_multi_check_list_must_pass(self, tmp_path):
        proc, _ = _run(tmp_path, "success", checks="issue-reference, pr-sentinel")
        assert proc.returncode == 0
        assert proc.stdout.count("passed") >= 2


class TestPendingStillPolls:
    def test_an_empty_conclusion_is_treated_as_in_flight(self, tmp_path):
        """The one case that must still wait: a check genuinely running.

        Asserted by letting it poll and then killing it, rather than sitting
        through the full five-minute ceiling in the test suite. What matters is
        that it does NOT exit on an empty conclusion -- an early exit here would
        mean the loop refuses to approve anything that has not already finished
        by the time it first looks.
        """
        result, elapsed = _run(tmp_path, None, timeout=45)
        assert isinstance(result, subprocess.TimeoutExpired), (
            "an empty conclusion must keep polling, not exit -- otherwise a "
            "check still in flight is treated as a verdict"
        )
        out = (result.stdout or b"").decode("utf-8", "replace") if isinstance(
            result.stdout, bytes
        ) else (result.stdout or "")
        assert "no conclusion yet" in out
        assert elapsed >= 40


class TestTheCeilingIsCapped:
    def test_max_attempts_is_fifteen(self):
        script = _wait_step_script()
        assert "MAX_ATTEMPTS=15" in script, (
            "the ceiling is the only remaining path to a long run (a check that "
            "was never created); it must stay capped"
        )

    def test_the_wait_is_five_minutes_not_ten(self):
        proc_script = _wait_step_script()
        assert "MAX_ATTEMPTS=30" not in proc_script


class TestTheHarnessIsHonest:
    def test_the_step_still_exists_and_is_substantial(self):
        assert len(_wait_step_script()) > 500

    def test_the_stub_gh_is_actually_being_used(self, tmp_path):
        """If the real gh were on PATH first, these tests would be measuring
        GitHub rather than the loop."""
        proc, _ = _run(tmp_path, "success")
        assert "owner/repo" not in proc.stderr
        assert proc.returncode == 0

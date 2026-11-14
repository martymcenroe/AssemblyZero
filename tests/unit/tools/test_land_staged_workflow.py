"""Unit tests for tools/land_staged_workflow.py.

Issue #1882. The pure, credential-free parts of the lander: header stripping
and argument derivation. The wait and the rerun (#4699) are exercised with
GitHub replaced by a fake `requests` and a dummy token string: nothing is
decrypted, because per the _pat_session operational rule that decrypt belongs
to the operator, never to a test or an agent.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "tools"))

import land_staged_workflow as lsw  # noqa: E402
from land_staged_workflow import (  # noqa: E402
    WaitResult,
    landing_action,
    parse_args,
    put_workflow,
    report_wait,
    strip_header_comment,
    wait_for_workflow,
    workflow_name,
)

WORKFLOW = "name: tests\non:\n  pull_request:\n"


class TestLandingAction:
    """#3606: --replace updates a live workflow; without it nothing changes."""

    def test_absent_destination_is_added(self):
        assert landing_action(None, WORKFLOW, replace=False) == "add"
        assert landing_action(None, WORKFLOW, replace=True) == "add"

    def test_existing_destination_without_replace_writes_nothing(self):
        assert landing_action("name: old\n", WORKFLOW, replace=False) == "exists"

    def test_existing_different_destination_with_replace_is_replaced(self):
        assert landing_action("name: old\n", WORKFLOW, replace=True) == "replace"

    def test_identical_destination_with_replace_writes_nothing(self):
        assert landing_action(WORKFLOW, WORKFLOW, replace=True) == "identical"

    def test_replace_defaults_off(self):
        cfg = parse_args(["--repo", "r", "--issue", "7", "--staged", "docs/ci/t.yml",
                          "--workflow", ".github/workflows/t.yml"])
        assert cfg.replace is False


class TestStripHeaderComment:
    def test_removes_leading_comment_block_and_following_blanks(self):
        staged = (
            "# Staged CI workflow. Lives in docs/ci/ because the fine-grained\n"
            "# PAT cannot push .github/workflows/ files.\n"
            "\n" + WORKFLOW
        )
        assert strip_header_comment(staged) == WORKFLOW

    def test_leaves_a_file_without_a_header_untouched(self):
        assert strip_header_comment(WORKFLOW) == WORKFLOW

    def test_preserves_comments_that_appear_after_content(self):
        """Only the HEADER goes. Inline comments are part of the workflow."""
        staged = "# header\n\nname: tests\n# keep me -- explains the next step\non:\n"
        result = strip_header_comment(staged)
        assert result.startswith("name: tests")
        assert "# keep me" in result

    def test_handles_a_file_that_is_only_comments(self):
        assert strip_header_comment("# a\n# b\n") == ""

    def test_handles_empty_input(self):
        assert strip_header_comment("") == ""

    def test_does_not_strip_indented_yaml_that_merely_contains_a_hash(self):
        staged = 'name: tests\non:\n  pull_request:\n  # trailing note\n'
        assert strip_header_comment(staged) == staged


class TestWorkflowName:
    """#1913. The tool used to poll for a check-run name supplied by the caller.
    Check runs are named after the JOB; `name:` at the top of the file names the
    WORKFLOW. Matching one against the other never succeeded, and the tool then
    reported 'never registered' for ten minutes while the run was failing."""

    def test_parses_the_top_level_name(self):
        assert workflow_name(WORKFLOW, None) == "tests"

    def test_does_not_pick_up_a_job_name(self):
        """The exact confusion that caused the bug: `python` is the job, and the
        check run is named after it -- but the workflow is `tests`."""
        content = "name: tests\non:\n  pull_request:\njobs:\n  python:\n    runs-on: x\n"
        assert workflow_name(content, None) == "tests"

    def test_ignores_indented_name_keys(self):
        """Steps carry their own `name:`; only column zero is the workflow."""
        content = "name: tests\njobs:\n  build:\n    steps:\n      - name: not this\n"
        assert workflow_name(content, None) == "tests"

    def test_strips_quotes(self):
        assert workflow_name('name: "tests"\non:\n', None) == "tests"
        assert workflow_name("name: 'tests'\non:\n", None) == "tests"

    def test_override_wins(self):
        assert workflow_name(WORKFLOW, "something-else") == "something-else"

    def test_missing_name_is_a_clear_error_not_a_silent_guess(self):
        with pytest.raises(SystemExit) as e:
            workflow_name("on:\n  pull_request:\n", None)
        assert "--check" in str(e.value)


class TestParseArgs:
    BASE = [
        "--repo", "EXAMPLE",
        "--issue", "7",
        "--staged", "docs/ci/tests.yml",
        "--workflow", ".github/workflows/tests.yml",
    ]

    def test_branch_is_derived_from_the_issue_when_unset(self):
        assert parse_args(self.BASE).branch == "ci/staged-workflow-7"

    def test_explicit_branch_wins(self):
        cfg = parse_args([*self.BASE, "--branch", "ci/custom"])
        assert cfg.branch == "ci/custom"

    def test_issue_is_an_int_so_the_closes_directive_cannot_be_malformed(self):
        assert parse_args(self.BASE).issue == 7

    def test_defaults_are_conservative(self):
        """The safe defaults: keep nothing staged, stop on red, strip nothing."""
        cfg = parse_args(self.BASE)
        assert cfg.keep_staged is False
        assert cfg.merge_on_red is False, "must not merge a red check by default"
        assert cfg.strip_header_comment is False
        assert cfg.check is None

    def test_check_defaults_to_none_so_the_name_is_derived(self):
        """#1913: a guessed default check name is what let a failing run be
        reported as 'never registered'. The default must be derive-from-file."""
        assert parse_args(self.BASE).check is None

    def test_no_target_repository_is_baked_in(self):
        """#1882: this repo is public and some targets are not, so the target
        must arrive at run time. --repo is required and has no default."""
        with pytest.raises(SystemExit):
            parse_args([
                "--issue", "7",
                "--staged", "docs/ci/tests.yml",
                "--workflow", ".github/workflows/tests.yml",
            ])


# --- #4699: the wait, and the rerun -------------------------------------------

RUN_URL = "https://github.com/o/r/actions/runs/99"
CFG_ARGS = ["--repo", "EXAMPLE", "--issue", "7", "--staged", "docs/ci/tests.yml",
            "--workflow", ".github/workflows/tests.yml"]


class FakeResponse:
    def __init__(self, payload: object, status: int = 200):
        self._payload = payload
        self.status_code = status
        self.text = ""

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"unexpected HTTP {self.status_code}")


class FakeClock:
    """A monotonic clock that moves only when the code under test sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def runs_api(statuses: list[str | None], conclusion: str = "success"):
    """A fake GET /actions/runs that answers one status per poll, then repeats the last.

    None means no run exists yet for the commit.
    """
    polls: list[int] = []

    def get(url, params=None, headers=None, timeout=None):
        assert url.endswith("/actions/runs"), url
        i = min(len(polls), len(statuses) - 1)
        polls.append(i)
        status = statuses[i]
        if status is None:
            return FakeResponse({"workflow_runs": []})
        run = {"name": "tests", "status": status, "created_at": "2026-11-11T06:00:00Z",
               "html_url": RUN_URL, "conclusion": conclusion if status == "completed" else None}
        return FakeResponse({"workflow_runs": [run]})

    return get, polls


@pytest.fixture
def cfg():
    return parse_args(CFG_ARGS)


class TestWaitForWorkflow:
    def test_t1_a_run_in_progress_at_every_poll_is_reported_as_still_running(self, monkeypatch, cfg):
        """T1. The run is in progress at every poll until the operator presses
        Ctrl-C. The first version returned "no_run" after forty polls and printed
        that the run did not START."""
        get, polls = runs_api(["in_progress"])
        monkeypatch.setattr(lsw, "requests", SimpleNamespace(get=get))
        clock = FakeClock()

        def sleep(seconds: float) -> None:
            clock.sleep(seconds)
            if len(clock.sleeps) == 60:  # well past the old forty-poll budget
                raise KeyboardInterrupt

        result = wait_for_workflow("x", cfg, "abc", "tests", sleep=sleep, clock=clock)
        assert result == WaitResult("in_progress", RUN_URL)
        assert len(polls) > lsw.CHECK_POLL_ATTEMPTS

    def test_t1_the_report_says_still_running_with_the_url_and_never_not_started(self, cfg, capsys):
        merged = report_wait(WaitResult("in_progress", RUN_URL), cfg, "tests", 5, "o/EXAMPLE")
        err = capsys.readouterr().err
        assert merged is False
        assert "STILL RUNNING" in err
        assert RUN_URL in err
        assert "did not START" not in err

    def test_a_run_still_in_progress_never_merges_even_with_merge_on_red(self, capsys):
        cfg = parse_args([*CFG_ARGS, "--merge-on-red"])
        assert report_wait(WaitResult("in_progress", RUN_URL), cfg, "tests", 5, "o/EXAMPLE") is False

    def test_t2_a_run_that_completes_after_the_old_budget_is_waited_for(self, monkeypatch, cfg):
        """T2. Seen on the first poll, still running for 60 more, then green."""
        get, polls = runs_api(["queued", *["in_progress"] * 60, "completed"])
        monkeypatch.setattr(lsw, "requests", SimpleNamespace(get=get))
        clock = FakeClock()
        result = wait_for_workflow("x", cfg, "abc", "tests", sleep=clock.sleep, clock=clock)
        assert result == WaitResult("success", RUN_URL)
        assert len(polls) == 62
        assert len(polls) > lsw.CHECK_POLL_ATTEMPTS

    def test_t2_a_red_conclusion_after_the_old_budget_is_returned_too(self, monkeypatch, cfg):
        get, _ = runs_api(["in_progress"] * 50 + ["completed"], conclusion="failure")
        monkeypatch.setattr(lsw, "requests", SimpleNamespace(get=get))
        clock = FakeClock()
        result = wait_for_workflow("x", cfg, "abc", "tests", sleep=clock.sleep, clock=clock)
        assert result.conclusion == "failure"

    def test_no_run_is_returned_only_when_no_run_ever_appeared(self, monkeypatch, cfg, capsys):
        get, polls = runs_api([None])
        monkeypatch.setattr(lsw, "requests", SimpleNamespace(get=get))
        clock = FakeClock()
        result = wait_for_workflow("x", cfg, "abc", "tests", sleep=clock.sleep, clock=clock)
        assert result == WaitResult("no_run")
        assert len(polls) == lsw.CHECK_POLL_ATTEMPTS
        assert report_wait(result, cfg, "tests", 5, "o/EXAMPLE") is False
        assert "did not START" in capsys.readouterr().err

    def test_a_run_that_appears_late_in_the_budget_is_then_waited_for(self, monkeypatch, cfg):
        get, _ = runs_api([None] * 39 + ["in_progress"] * 30 + ["completed"])
        monkeypatch.setattr(lsw, "requests", SimpleNamespace(get=get))
        clock = FakeClock()
        result = wait_for_workflow("x", cfg, "abc", "tests", sleep=clock.sleep, clock=clock)
        assert result.conclusion == "success"

    def test_ctrl_c_before_any_run_appears_is_not_reported_as_a_run(self, monkeypatch, cfg):
        get, _ = runs_api([None])
        monkeypatch.setattr(lsw, "requests", SimpleNamespace(get=get))

        def sleep(seconds: float) -> None:
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            wait_for_workflow("x", cfg, "abc", "tests", sleep=sleep, clock=FakeClock())

    def test_the_running_wait_backs_off_to_its_cap(self, monkeypatch, cfg):
        get, _ = runs_api(["in_progress"] * 10 + ["completed"])
        monkeypatch.setattr(lsw, "requests", SimpleNamespace(get=get))
        clock = FakeClock()
        wait_for_workflow("x", cfg, "abc", "tests", sleep=clock.sleep, clock=clock)
        assert clock.sleeps[:5] == [15, 22.5, 33.75, 50.625, 60]
        assert max(clock.sleeps) == lsw.RUN_POLL_CAP_S

    def test_the_ceiling_ends_the_wait_as_still_running_with_the_url(self, monkeypatch, cfg):
        get, polls = runs_api(["in_progress"])
        monkeypatch.setattr(lsw, "requests", SimpleNamespace(get=get))
        clock = FakeClock()
        start = clock.now
        result = wait_for_workflow("x", cfg, "abc", "tests", sleep=clock.sleep, clock=clock)
        assert result == WaitResult("in_progress", RUN_URL)
        assert clock.now - start == lsw.RUN_WAIT_CEILING_S  # the last wait is clamped


class TestPutWorkflowOnARerun:
    """T3. A rerun after a stopped wait must not PUT the same text again: that
    adds a commit and starts a second run of the workflow."""

    @staticmethod
    def fake(branch_text: str | None):
        puts: list[dict] = []

        def get(url, params=None, headers=None, timeout=None):
            if branch_text is None:
                return FakeResponse({}, status=404)
            return FakeResponse({"sha": "blob1", "content": base64.b64encode(
                branch_text.encode()).decode()})

        def put(url, headers=None, json=None, timeout=None):
            puts.append(json)
            return FakeResponse({})

        return SimpleNamespace(get=get, put=put), puts

    def test_t3_a_branch_already_holding_the_staged_text_gets_no_put(self, monkeypatch, cfg):
        fake, puts = self.fake(WORKFLOW)
        monkeypatch.setattr(lsw, "requests", fake)
        assert put_workflow("x", cfg, WORKFLOW) is False
        assert puts == []

    def test_a_branch_holding_other_text_is_updated_in_place(self, monkeypatch, cfg):
        fake, puts = self.fake("name: old\n")
        monkeypatch.setattr(lsw, "requests", fake)
        assert put_workflow("x", cfg, WORKFLOW) is True
        assert len(puts) == 1 and puts[0]["sha"] == "blob1"
        assert base64.b64decode(puts[0]["content"]).decode() == WORKFLOW

    def test_a_branch_without_the_file_gets_it(self, monkeypatch, cfg):
        fake, puts = self.fake(None)
        monkeypatch.setattr(lsw, "requests", fake)
        assert put_workflow("x", cfg, WORKFLOW) is True
        assert len(puts) == 1 and "sha" not in puts[0]

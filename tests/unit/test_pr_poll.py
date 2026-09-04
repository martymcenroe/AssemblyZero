"""A poll that ends when its PR does (#2702).

Two backgrounded shell loops from 2026-09-01 were still polling the GitHub API
every thirty seconds twelve hours after their PRs merged. The loop's exit
condition was `mergeable_state == clean`, and **a merged PR reports
`mergeable_state` as `unknown`** -- so the condition became unreachable at the
moment the work was done. They surfaced as `2 shells still running`, which the
operator read as two agents.

The first class here is the whole finding: the exact JSON a merged PR returns,
which is what those loops could never see.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import wait_for_pr  # noqa: E402

from assemblyzero.core.pr_poll import (  # noqa: E402
    VERDICT_GONE,
    VERDICT_READY,
    VERDICT_STUCK,
    VERDICT_WAIT,
    describe,
    poll_verdict,
)

#: What `gh api repos/{repo}/pulls/{n}` returns for PR #2691 after it merged as
#: ddf7b545. `mergeable_state` is `unknown`, which is the entire defect.
MERGED = {"mergeable_state": "unknown", "merged": True, "state": "closed"}


class TestAMergedPullRequestEndsThePoll:
    def test_the_shape_that_span_for_twelve_hours(self):
        assert poll_verdict(MERGED) == VERDICT_GONE

    def test_the_old_condition_would_never_have_fired(self):
        """The control that makes the test above mean something: the loop was
        not merely slow to notice, it could not notice at all."""
        assert MERGED["mergeable_state"] != "clean"

    def test_merged_is_read_before_mergeable_state(self):
        """Terminal-first. A reading that consulted the state first would put
        the finished case in the same bucket as 'no information yet', which is
        the bucket the two loops sat in."""
        assert poll_verdict(
            {"mergeable_state": "blocked", "merged": True, "state": "open"}
        ) == VERDICT_GONE

    def test_a_closed_unmerged_pull_request_also_ends_it(self):
        assert poll_verdict(
            {"mergeable_state": "unknown", "merged": False, "state": "closed"}
        ) == VERDICT_GONE

    def test_the_message_says_why_the_state_looks_unhelpful(self):
        said = describe(VERDICT_GONE, MERGED)
        assert "already merged" in said
        assert "what a merged PR always reports" in said


class TestTheOtherVerdicts:
    def test_clean_is_ready(self):
        assert poll_verdict(
            {"mergeable_state": "clean", "merged": False, "state": "open"}
        ) == VERDICT_READY

    def test_unstable_is_ready_only_when_the_caller_accepts_it(self):
        """A PR that removes the very check making it unstable can never reach
        `clean`; an ordinary PR should wait for its checks. The caller knows
        which it has, so this is its choice and not a default."""
        payload = {"mergeable_state": "unstable", "merged": False, "state": "open"}
        assert poll_verdict(payload) == VERDICT_WAIT
        assert poll_verdict(payload, accept_unstable=True) == VERDICT_READY

    @pytest.mark.parametrize("state", ["dirty", "behind"])
    def test_a_conflict_or_a_rebase_is_stuck(self, state):
        assert poll_verdict(
            {"mergeable_state": state, "merged": False, "state": "open"}
        ) == VERDICT_STUCK

    def test_blocked_keeps_waiting(self):
        """#1399: it usually means the approving review has not landed, and it
        does resolve on its own. Polling through it is the whole reason the
        loop has a budget rather than a strike count."""
        assert poll_verdict(
            {"mergeable_state": "blocked", "merged": False, "state": "open"}
        ) == VERDICT_WAIT

    def test_an_empty_payload_waits_rather_than_deciding(self):
        """A transient API failure must cost one interval, not a verdict."""
        assert poll_verdict({}) == VERDICT_WAIT


class TestTheLoopTerminates:
    """The acceptance: a poll started against a PR that is then merged by
    another path exits within one interval."""

    def _wait(self, payloads, **kwargs):
        served = iter(payloads)
        slept: list[float] = []
        clock = {"t": 0.0}

        def _now():
            return clock["t"]

        def _sleep(seconds):
            slept.append(seconds)
            clock["t"] += seconds

        verdict, _ = wait_for_pr.wait(
            "owner/repo", 1, timeout=kwargs.pop("timeout", 900.0),
            interval=kwargs.pop("interval", 15.0),
            now=_now, sleep=_sleep, log=lambda *a: None, **kwargs,
        )
        return verdict, slept, served

    def test_a_pr_merged_between_polls_ends_the_loop(self, monkeypatch):
        payloads = iter([
            {"mergeable_state": "blocked", "merged": False, "state": "open"},
            MERGED,
        ])
        monkeypatch.setattr(wait_for_pr, "fetch", lambda r, p: next(payloads))
        verdict, slept, _ = self._wait([])
        assert verdict == VERDICT_GONE
        assert slept == [15.0], "it waited exactly one interval, then stopped"

    def test_a_pr_that_never_resolves_is_bounded(self, monkeypatch):
        """The backstop. A loop that is wrong for a reason nobody predicted
        still ends -- which the twelve-hour loops did not."""
        monkeypatch.setattr(
            wait_for_pr, "fetch",
            lambda r, p: {"mergeable_state": "blocked", "merged": False,
                          "state": "open"},
        )
        verdict, slept, _ = self._wait([], timeout=60.0, interval=15.0)
        assert verdict == VERDICT_WAIT
        assert sum(slept) <= 60.0

    def test_a_ready_pr_returns_at_once(self, monkeypatch):
        monkeypatch.setattr(
            wait_for_pr, "fetch",
            lambda r, p: {"mergeable_state": "clean", "merged": False,
                          "state": "open"},
        )
        verdict, slept, _ = self._wait([])
        assert verdict == VERDICT_READY
        assert slept == []


class TestTheExitCodesAreTheVerdict:
    """The tool drops into a `&&` chain where the shell loop used to sit, so
    the exit code has to carry the answer."""

    def test_ready_is_zero_and_the_others_are_not(self, monkeypatch, capsys):
        for payload, expected in (
            ({"mergeable_state": "clean", "merged": False, "state": "open"},
             wait_for_pr.EXIT_READY),
            (MERGED, wait_for_pr.EXIT_GONE),
            ({"mergeable_state": "dirty", "merged": False, "state": "open"},
             wait_for_pr.EXIT_STUCK),
        ):
            monkeypatch.setattr(wait_for_pr, "fetch", lambda r, p, _p=payload: _p)
            code = wait_for_pr.main(["--repo", "o/r", "--pr", "1"])
            capsys.readouterr()
            assert code == expected

    def test_a_timeout_has_its_own_code(self, monkeypatch, capsys):
        monkeypatch.setattr(
            wait_for_pr, "fetch",
            lambda r, p: {"mergeable_state": "blocked", "merged": False,
                          "state": "open"},
        )
        monkeypatch.setattr(wait_for_pr.time, "sleep", lambda s: None)
        code = wait_for_pr.main(
            ["--repo", "o/r", "--pr", "1", "--timeout", "0", "--interval", "0"]
        )
        assert code == wait_for_pr.EXIT_TIMEOUT
        assert "no verdict" in capsys.readouterr().out


class TestFetchIsForgiving:
    def test_a_failed_gh_call_reads_as_wait(self, monkeypatch):
        class _Result:
            returncode = 1
            stdout = ""

        monkeypatch.setattr(
            wait_for_pr.subprocess, "run", lambda *a, **k: _Result()
        )
        assert wait_for_pr.fetch("o/r", 1) == {}
        assert poll_verdict(wait_for_pr.fetch("o/r", 1)) == VERDICT_WAIT

    def test_unparseable_output_reads_as_wait(self, monkeypatch):
        class _Result:
            returncode = 0
            stdout = "not json"

        monkeypatch.setattr(
            wait_for_pr.subprocess, "run", lambda *a, **k: _Result()
        )
        assert wait_for_pr.fetch("o/r", 1) == {}

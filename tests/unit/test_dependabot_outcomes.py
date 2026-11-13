"""Tests for #4737: every tested dependabot PR ends in exactly one outcome.

Covers four of the issue's requirements:

- every way a PR's run can end (pytest exit 0, 1 and 5, a timeout, an
  exception, an interrupt) prints one OUTCOME line and records the PR in one
  result list, through the real ``process_pr`` mapping;
- ``main()`` prints a Summary that names every PR the run processed, including
  when an interrupt cuts the run short;
- the in-flight ledger and the two-strike rule built on it;
- ``run(..., kill_tree=True)`` kills a real grandchild on timeout.
"""
import ast
import importlib.util
import json
import os
import subprocess
import sys
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psutil
import pytest

# Load the tools/ script as a module without polluting sys.path, as
# test_dependabot_review.py does.
TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "dependabot_review", TOOLS_DIR / "dependabot_review.py"
)
dr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dr)

REPO = "o/r"


def _pr(number: int, head: str = "sha-a") -> "dr.PRInfo":
    return dr.PRInfo(
        number=number, title=f"bump p{number}", author_login="app/dependabot",
        body="", head_ref=f"dependabot/pip/p{number}", head_oid=head,
    )


def _key(number: int) -> str:
    return f"{REPO}#{number}"


def _entries_for(sub: dict, number: int) -> list[str]:
    """Every RESULT_KEYS list that names the PR, once per appearance."""
    return [k for k in dr.RESULT_KEYS for v in sub.get(k, []) if v == _key(number)]


def _outcome_lines(out: str, number: int | None = None) -> list[str]:
    prefix = "OUTCOME PR #" if number is None else f"OUTCOME PR #{number}:"
    return [ln for ln in out.splitlines() if ln.strip().startswith(prefix)]


def _repeat_lines(out: str, number: int) -> list[str]:
    prefix = f"REPEAT PR #{number}:"
    return [ln for ln in out.splitlines() if ln.strip().startswith(prefix)]


@contextmanager
def _repo_preconditions(tmp_path: Path, prs: list):
    """Satisfy process_repo's checks before its PR loop, with no network."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(
            dr, "resolve_target_repo_dir", return_value=tmp_path))
        stack.enter_context(patch.object(
            dr, "check_for_orphan_worktrees", return_value=[]))
        stack.enter_context(patch.object(
            dr, "list_dependabot_prs", return_value=prs))
        stack.enter_context(patch.object(
            dr, "already_deferred_at_head", return_value=False))
        yield


@contextmanager
def _pipeline(tmp_path: Path, pytest_results: dict):
    """Stub everything the real process_pr touches except its outcome mapping.

    ``pytest_results`` maps a PR number to what run_tests_detailed gives for
    it: an ``(exit_code, output)`` tuple, or an exception instance to raise.
    """
    def fake_create(target_repo, number):
        worktree = tmp_path / f"wt-{number}"
        worktree.mkdir(exist_ok=True)
        return worktree, f"dependabot-audit-{number}"

    def fake_tests(worktree):
        result = pytest_results[int(worktree.name.split("-")[1])]
        if isinstance(result, BaseException):
            raise result
        return result

    with ExitStack() as stack:
        def stub(name, **kwargs):
            return stack.enter_context(patch.object(dr, name, **kwargs))

        stub("create_audit_worktree", side_effect=fake_create)
        cleanup = stub("cleanup_worktree", return_value=True)
        stub("checkout_pr_into_worktree", return_value=True)
        stub("_pr_changed_files", return_value=["poetry.lock"])
        stub("fake_root_guard_gap", return_value=([], ""))
        stub("evict_poetry_venv")
        stub("install_deps", return_value=True)
        tests = stub("run_tests_detailed", side_effect=fake_tests)
        baseline = stub("run_baseline_gate", return_value=(0, ""))
        stub("review_comment_on_pr", return_value=True)
        stub("is_pr_branch_stale", return_value=False)
        stub("request_dependabot_recreate")
        stub("request_dependabot_rebase")
        stub("inject_no_issue", return_value=True)
        stub("approve_pr", return_value=True)
        stub("wait_for_mergeable", return_value=True)
        stub("squash_merge", return_value=True)
        alert = stub("alert_operator")
        stack.enter_context(patch.object(dr.time, "sleep"))
        yield SimpleNamespace(cleanup=cleanup, tests=tests,
                              baseline=baseline, alert=alert)


# ---------------------------------------------------------------------------
# #4737 test 1: every way a PR's run ends gives one OUTCOME line and one entry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("pr1_result", "status", "reason_part", "baseline_calls"),
    [
        pytest.param((0, "1 passed"), "merged", "pytest passed (exit 0)", 0,
                     id="pytest-exit-0"),
        pytest.param((1, "FAILED tests/test_x.py::test_y - boom"), "deferred",
                     "test suite FAILED (exit 1)", 1, id="pytest-exit-1"),
        pytest.param((5, "no tests ran"), "merged", "no tests collected", 0,
                     id="pytest-exit-5"),
        pytest.param((124, ""), "deferred", "pytest TIMEOUT after", 0,
                     id="pytest-timeout"),
        pytest.param(RuntimeError("gh exploded"), "errored",
                     "RuntimeError: gh exploded", 0, id="runtime-error"),
    ],
)
def test_each_run_ending_records_one_outcome(tmp_path, capsys, pr1_result,
                                             status, reason_part,
                                             baseline_calls):
    """PR #1 ends the parametrized way; PR #2 passes, so the loop is seen to
    go on past PR #1 in every case."""
    assert dr.TIMEOUT_EXIT == 124
    with _repo_preconditions(tmp_path, [_pr(1), _pr(2)]), \
         _pipeline(tmp_path, {1: pr1_result, 2: (0, "")}) as stubs:
        sub = dr.process_repo(REPO, tmp_path)
    out = capsys.readouterr().out

    pr1_lines = _outcome_lines(out, 1)
    assert len(pr1_lines) == 1, pr1_lines
    assert f"OUTCOME PR #1: {status} -- " in pr1_lines[0]
    assert reason_part in pr1_lines[0]
    assert _entries_for(sub, 1) == [status]

    # The loop went on to PR #2, which merged, and nothing else was printed.
    assert _entries_for(sub, 2) == ["merged"]
    assert len(_outcome_lines(out)) == 2
    assert stubs.tests.call_count == 2
    # The baseline runs only for a real failure: a killed suite has no
    # failure list to compare.
    assert stubs.baseline.call_count == baseline_calls
    # process_pr's finally removed both worktrees, whatever happened.
    assert stubs.cleanup.call_count == 2

    if status == "errored":
        stubs.alert.assert_called_once()
        assert stubs.alert.call_args.kwargs["cause"] == "RuntimeError: gh exploded"
    else:
        stubs.alert.assert_not_called()


def test_keyboard_interrupt_is_recorded_errored_and_reraised(tmp_path, capsys):
    with (
        _repo_preconditions(tmp_path, [_pr(1), _pr(2)]),
        _pipeline(tmp_path, {1: KeyboardInterrupt(), 2: (0, "")}) as stubs,
        pytest.raises(KeyboardInterrupt) as info,
    ):
        dr.process_repo(REPO, tmp_path)
    out = capsys.readouterr().out

    lines = _outcome_lines(out)
    assert len(lines) == 1, lines
    assert "OUTCOME PR #1: errored -- interrupted by SIGINT" in lines[0]

    partial = info.value.dependabot_partial
    assert _entries_for(partial, 1) == ["errored"]
    # The interrupt ended the loop: PR #2 was never started.
    assert _entries_for(partial, 2) == []
    assert stubs.tests.call_count == 1
    stubs.alert.assert_not_called()
    # process_pr's finally still removed PR #1's worktree.
    assert stubs.cleanup.call_count == 1


def test_an_unknown_status_from_process_pr_is_recorded_errored(tmp_path, capsys):
    with _repo_preconditions(tmp_path, [_pr(1)]), \
         patch.object(dr, "process_pr", return_value="approved"):
        sub = dr.process_repo(REPO, tmp_path)
    out = capsys.readouterr().out

    lines = _outcome_lines(out, 1)
    assert len(lines) == 1, lines
    assert "errored -- process_pr returned the unknown status 'approved'" in lines[0]
    assert _entries_for(sub, 1) == ["errored"]


def test_outcome_refuses_a_status_outside_the_three():
    with pytest.raises(ValueError, match="unknown PR outcome 'approved'"):
        dr.Outcome("approved", "x")
    outcome = dr.Outcome("deferred", "why")
    assert outcome == "deferred"
    assert outcome.reason == "why"


# ---------------------------------------------------------------------------
# #4737 test 2: main()'s Summary names every PR the run processed
# ---------------------------------------------------------------------------

def _summary_lists(out: str) -> dict[str, list[str]]:
    """The lists the Summary printed, keyed by the label before the colon."""
    assert out.count("=== Summary ===") == 1, "expected exactly one Summary"
    section = out.split("=== Summary ===", 1)[1]
    lists: dict[str, list[str]] = {}
    for line in section.splitlines():
        stripped = line.strip()
        if "[" in stripped and stripped.endswith("]"):
            label = stripped.split(":", 1)[0]
            lists[label] = ast.literal_eval(stripped[stripped.index("["):])
    return lists


def _summary_list(lists: dict[str, list[str]], label_start: str) -> list[str]:
    matches = [v for k, v in lists.items() if k.startswith(label_start)]
    assert len(matches) == 1, (label_start, lists)
    return matches[0]


@contextmanager
def _main_harness(tmp_path: Path, prs: list, fake_process_pr):
    main_repo = tmp_path / "main"
    (main_repo / ".git").mkdir(parents=True)
    ledger_path = tmp_path / "ledger" / "in-flight.json"
    argv = ["dependabot_review.py", "--repo", REPO,
            "--main-repo", str(main_repo), "--no-run-log"]
    with ExitStack() as stack:
        stack.enter_context(patch.object(sys, "argv", argv))
        stack.enter_context(patch.object(dr, "IN_FLIGHT_LEDGER", ledger_path))
        stack.enter_context(patch.object(dr, "guard_not_worktree"))
        stack.enter_context(patch.object(dr, "_force_utf8_streams"))
        setup_log = stack.enter_context(patch.object(dr, "setup_run_log"))
        stack.enter_context(_repo_preconditions(tmp_path, prs))
        stack.enter_context(patch.object(
            dr, "process_pr", side_effect=fake_process_pr))
        alert = stack.enter_context(patch.object(dr, "alert_operator"))
        yield SimpleNamespace(ledger_path=ledger_path, alert=alert,
                              setup_log=setup_log)


def test_main_summary_names_every_processed_pr(tmp_path, capsys):
    def fake_process_pr(pr, repo, target_repo):
        if pr.number == 1:
            return dr.Outcome("merged", "pytest passed (exit 0)")
        if pr.number == 2:
            return dr.Outcome("deferred", "test suite FAILED (exit 1)")
        raise RuntimeError("gh exploded")

    with _main_harness(tmp_path, [_pr(1), _pr(2), _pr(3)],
                       fake_process_pr) as h:
        dr.main()
    out = capsys.readouterr().out

    h.setup_log.assert_not_called()
    lists = _summary_lists(out)
    assert _summary_list(lists, "Merged") == [_key(1)]
    assert _summary_list(lists, "Deferred") == [_key(2)]
    assert _summary_list(lists, "Errored") == [_key(3)]
    every_listed = sorted(v for vs in lists.values() for v in vs)
    assert every_listed == [_key(1), _key(2), _key(3)]
    assert "merged=1 deferred=1 errored=1" in out
    assert len(_outcome_lines(out)) == 3
    h.alert.assert_called_once()
    # Every PR's outcome was recorded, so the ledger holds nothing.
    assert json.loads(h.ledger_path.read_text(encoding="utf-8")) == {}


def test_main_summary_keeps_the_prs_an_interrupt_cut_short(tmp_path, capsys):
    def fake_process_pr(pr, repo, target_repo):
        if pr.number == 1:
            return dr.Outcome("merged", "pytest passed (exit 0)")
        raise KeyboardInterrupt

    with (
        _main_harness(tmp_path, [_pr(1), _pr(2), _pr(3)],
                      fake_process_pr) as h,
        pytest.raises(KeyboardInterrupt),
    ):
        dr.main()
    out = capsys.readouterr().out

    lists = _summary_lists(out)
    assert _summary_list(lists, "Merged") == [_key(1)]
    assert _summary_list(lists, "Errored") == [_key(2)]
    every_listed = sorted(v for vs in lists.values() for v in vs)
    assert every_listed == [_key(1), _key(2)]
    # The interrupted PR's entry stays for the next run's REPEAT check.
    ledger = json.loads(h.ledger_path.read_text(encoding="utf-8"))
    assert list(ledger) == [_key(2)]
    assert ledger[_key(2)]["head"] == "sha-a"
    assert len(ledger[_key(2)]["runs"]) == 1


def test_main_counts_no_commented_review_for_a_two_strike_deferral(tmp_path,
                                                                  capsys):
    # PR 1 is deferred by the two-strike rule, which posts no review; PR 2 is
    # tested and deferred, which posts one COMMENTED review.
    def fake_process_pr(pr, repo, target_repo):
        assert pr.number == 2, "the two-strike PR must not be run"
        return dr.Outcome("deferred", "test suite FAILED (exit 1)")

    with _main_harness(tmp_path, [_pr(1), _pr(2)], fake_process_pr) as h:
        _seed(h.ledger_path, "sha-a", "run-A", "run-B")
        dr.main()
    out = capsys.readouterr().out

    lists = _summary_lists(out)
    assert _summary_list(lists, "Deferred") == [_key(1), _key(2)]
    assert ("Review events created: 0 APPROVED + 1 COMMENTED = 1 total"
            in out)


# ---------------------------------------------------------------------------
# The in-flight ledger, with real files
# ---------------------------------------------------------------------------

def test_ledger_begin_twice_at_one_head_gives_two_runs(tmp_path):
    path = tmp_path / "in-flight.json"
    dr.InFlightLedger(path, "run-1").begin(_key(1), "sha-a")
    dr.InFlightLedger(path, "run-2").begin(_key(1), "sha-a")
    assert dr.InFlightLedger(path, "run-3").entry(_key(1)) == {
        "head": "sha-a", "runs": ["run-1", "run-2"]}


def test_ledger_new_head_resets_to_one_run(tmp_path):
    path = tmp_path / "in-flight.json"
    dr.InFlightLedger(path, "run-1").begin(_key(1), "sha-a")
    dr.InFlightLedger(path, "run-2").begin(_key(1), "sha-a")
    dr.InFlightLedger(path, "run-3").begin(_key(1), "sha-b")
    assert dr.InFlightLedger(path, "run-4").entry(_key(1)) == {
        "head": "sha-b", "runs": ["run-3"]}


def test_ledger_clear_removes_only_that_entry(tmp_path):
    path = tmp_path / "in-flight.json"
    ledger = dr.InFlightLedger(path, "run-1")
    ledger.begin(_key(1), "sha-a")
    ledger.begin(_key(2), "sha-b")
    ledger.clear(_key(1))
    assert ledger.entry(_key(1)) is None
    assert ledger.entry(_key(2)) == {"head": "sha-b", "runs": ["run-1"]}
    assert set(json.loads(path.read_text(encoding="utf-8"))) == {_key(2)}


def test_ledger_missing_file_reads_as_empty(tmp_path):
    path = tmp_path / "absent" / "in-flight.json"
    ledger = dr.InFlightLedger(path, "run-1")
    assert ledger.entry(_key(1)) is None
    ledger.clear(_key(1))
    # Neither a read nor a clear of nothing creates the file.
    assert not path.exists()


@pytest.mark.parametrize("content", ["{not json", "[1, 2]"],
                         ids=["invalid-json", "json-list"])
def test_ledger_corrupt_file_raises_naming_path_and_is_left_unchanged(
        tmp_path, content):
    path = tmp_path / "in-flight.json"
    path.write_bytes(content.encode("utf-8"))
    ledger = dr.InFlightLedger(path, "run-1")

    calls = {
        "entry": lambda: ledger.entry(_key(1)),
        "begin": lambda: ledger.begin(_key(1), "sha-a"),
        "clear": lambda: ledger.clear(_key(1)),
    }
    for name, call in calls.items():
        with pytest.raises(dr.InFlightLedgerError) as info:
            call()
        assert str(path) in str(info.value), name

    assert path.read_bytes() == content.encode("utf-8")
    assert not path.with_name(path.name + ".tmp").exists()


def test_process_repo_stops_loudly_on_a_corrupt_ledger(tmp_path, capsys):
    path = tmp_path / "in-flight.json"
    path.write_text("{not json", encoding="utf-8")
    with (
        _repo_preconditions(tmp_path, [_pr(1)]),
        patch.object(dr, "process_pr") as process_pr,
        pytest.raises(dr.InFlightLedgerError) as info,
    ):
        dr.process_repo(REPO, tmp_path,
                        ledger=dr.InFlightLedger(path, "run-1"))
    process_pr.assert_not_called()
    assert info.value.dependabot_partial is not None
    assert path.read_text(encoding="utf-8") == "{not json"


# ---------------------------------------------------------------------------
# REPEAT and the two-strike rule, through process_repo
# ---------------------------------------------------------------------------

def _run_repo_with_ledger(tmp_path, prs, ledger, process_pr_side_effect):
    with _repo_preconditions(tmp_path, prs), \
         patch.object(dr, "process_pr",
                      side_effect=process_pr_side_effect) as process_pr, \
         patch.object(dr, "alert_operator") as alert:
        sub = dr.process_repo(REPO, tmp_path, ledger=ledger)
    return sub, process_pr, alert


def _seed(path: Path, head: str, *run_labels: str) -> None:
    for label in run_labels:
        dr.InFlightLedger(path, label).begin(_key(1), head)


def test_one_prior_run_prints_repeat_and_still_runs_the_pr(tmp_path, capsys):
    path = tmp_path / "in-flight.json"
    _seed(path, "sha-a", "run-A")
    ledger = dr.InFlightLedger(path, "run-B")

    sub, process_pr, _ = _run_repo_with_ledger(
        tmp_path, [_pr(1)], ledger,
        lambda pr, repo, target: dr.Outcome("merged", "ok"))
    out = capsys.readouterr().out

    repeats = _repeat_lines(out, 1)
    assert len(repeats) == 1, repeats
    assert "run run-A began this PR at head sha-a and recorded no outcome" \
        in repeats[0]
    process_pr.assert_called_once()
    assert _entries_for(sub, 1) == ["merged"]
    assert ledger.entry(_key(1)) is None


def test_two_prior_runs_at_the_same_head_defer_without_running(tmp_path,
                                                              capsys):
    path = tmp_path / "in-flight.json"
    _seed(path, "sha-a", "run-A", "run-B")
    ledger = dr.InFlightLedger(path, "run-C")

    sub, process_pr, _ = _run_repo_with_ledger(
        tmp_path, [_pr(1)], ledger,
        lambda pr, repo, target: dr.Outcome("merged", "ok"))
    out = capsys.readouterr().out

    assert dr.IN_FLIGHT_STRIKES == 2
    assert len(_repeat_lines(out, 1)) == 1
    process_pr.assert_not_called()
    lines = _outcome_lines(out, 1)
    assert len(lines) == 1, lines
    assert "deferred -- " in lines[0]
    assert "deferred without running after 2 runs with no outcome" in lines[0]
    assert _entries_for(sub, 1) == ["deferred"]
    # Deferring without running begins no run, so the entry is unchanged.
    assert ledger.entry(_key(1)) == {"head": "sha-a",
                                     "runs": ["run-A", "run-B"]}


def test_two_prior_runs_at_an_older_head_still_run_the_pr(tmp_path, capsys):
    path = tmp_path / "in-flight.json"
    _seed(path, "sha-old", "run-A", "run-B")
    ledger = dr.InFlightLedger(path, "run-C")

    sub, process_pr, _ = _run_repo_with_ledger(
        tmp_path, [_pr(1, head="sha-new")], ledger,
        lambda pr, repo, target: dr.Outcome("deferred", "test suite FAILED"))
    out = capsys.readouterr().out

    assert len(_repeat_lines(out, 1)) == 1
    process_pr.assert_called_once()
    assert _entries_for(sub, 1) == ["deferred"]
    assert ledger.entry(_key(1)) is None


def test_interrupts_keep_the_entry_until_the_second_strike(tmp_path, capsys):
    """Two interrupted runs at one head leave two runs; the third defers."""
    path = tmp_path / "in-flight.json"

    def interrupted(pr, repo, target):
        raise KeyboardInterrupt

    for label in ("run-A", "run-B"):
        ledger = dr.InFlightLedger(path, label)
        with (
            _repo_preconditions(tmp_path, [_pr(1)]),
            patch.object(dr, "process_pr", side_effect=interrupted),
            pytest.raises(KeyboardInterrupt),
        ):
            dr.process_repo(REPO, tmp_path, ledger=ledger)
    assert dr.InFlightLedger(path, "x").entry(_key(1)) == {
        "head": "sha-a", "runs": ["run-A", "run-B"]}
    capsys.readouterr()

    sub, process_pr, _ = _run_repo_with_ledger(
        tmp_path, [_pr(1)], dr.InFlightLedger(path, "run-C"), interrupted)
    out = capsys.readouterr().out
    process_pr.assert_not_called()
    assert _entries_for(sub, 1) == ["deferred"]
    assert len(_outcome_lines(out, 1)) == 1


@pytest.mark.parametrize(
    ("ending", "status"),
    [
        pytest.param(dr.Outcome("merged", "ok"), "merged", id="merged"),
        pytest.param(dr.Outcome("deferred", "red"), "deferred", id="deferred"),
        pytest.param(dr.Outcome("errored", "approve failed"), "errored",
                     id="errored"),
        pytest.param(RuntimeError("boom"), "errored", id="exception"),
    ],
)
def test_a_recorded_outcome_clears_the_entry(tmp_path, capsys, ending, status):
    path = tmp_path / "in-flight.json"
    ledger = dr.InFlightLedger(path, "run-A")
    seen_during_run: list = []

    def fake_process_pr(pr, repo, target):
        # begin() ran before the PR was tested.
        seen_during_run.append(ledger.entry(_key(1)))
        if isinstance(ending, BaseException):
            raise ending
        return ending

    sub, _, alert = _run_repo_with_ledger(
        tmp_path, [_pr(1)], ledger, fake_process_pr)
    out = capsys.readouterr().out

    assert seen_during_run == [{"head": "sha-a", "runs": ["run-A"]}]
    assert _entries_for(sub, 1) == [status]
    assert len(_outcome_lines(out, 1)) == 1
    assert _repeat_lines(out, 1) == []
    assert ledger.entry(_key(1)) is None
    assert alert.call_count == (1 if isinstance(ending, Exception) else 0)


# ---------------------------------------------------------------------------
# R2: a real process-tree kill
# ---------------------------------------------------------------------------

_GRANDCHILD = """\
import os
import sys
import time
from pathlib import Path

target = Path(sys.argv[1])
staging = target.with_name(target.name + ".part")
staging.write_text(str(os.getpid()), encoding="utf-8")
os.replace(staging, target)
time.sleep(600)
"""

_CHILD = """\
import subprocess
import sys
import time

# The grandchild inherits this process's stdout and stderr, the pipes run()
# reads: if only this process were killed, they would stay open.
subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2]])
time.sleep(600)
"""


def _pid_gone(pid: int) -> bool:
    """True when ``pid`` no longer runs: absent, or a zombie awaiting reaping.

    Never ``os.kill(pid, 0)``: on Windows that sends CTRL_C_EVENT (#4740).
    """
    if Path("/proc/self/stat").exists():
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        except (FileNotFoundError, ProcessLookupError):
            return True
        # The state letter follows the parenthesised command name.
        return stat.rsplit(")", 1)[1].split()[0] in ("Z", "X")
    try:
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return True


def _wait_gone(pid: int, seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if _pid_gone(pid):
            return True
        time.sleep(0.1)
    return _pid_gone(pid)


def test_run_kill_tree_kills_the_grandchild_on_timeout(tmp_path, capsys):
    grandchild = tmp_path / "grandchild.py"
    child = tmp_path / "child.py"
    pid_file = tmp_path / "grandchild.pid"
    grandchild.write_text(_GRANDCHILD, encoding="utf-8")
    child.write_text(_CHILD, encoding="utf-8")

    started = time.monotonic()
    try:
        result = dr.run(
            [sys.executable, str(child), str(grandchild), str(pid_file)],
            timeout=2, kill_tree=True,
        )
        elapsed = time.monotonic() - started
        out = capsys.readouterr().out

        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 124
        assert "TIMEOUT after 2s" in out
        assert elapsed < 60, f"run() took {elapsed:.1f}s to return"

        child_pid = int(out.split("tree of pid ", 1)[1].split()[0])
        assert _wait_gone(child_pid), f"child pid {child_pid} survived"

        assert pid_file.exists(), \
            "the grandchild never wrote its pid before the timeout"
        grandchild_pid = int(pid_file.read_text(encoding="utf-8"))
        assert grandchild_pid not in (os.getpid(), child_pid)
        assert _wait_gone(grandchild_pid), \
            f"grandchild pid {grandchild_pid} survived the tree kill"
    finally:
        # Never leave a 600-second sleeper behind when an assertion fails.
        if pid_file.exists():
            leftover = int(pid_file.read_text(encoding="utf-8"))
            if not _pid_gone(leftover):
                try:
                    psutil.Process(leftover).kill()
                except psutil.NoSuchProcess:
                    pass

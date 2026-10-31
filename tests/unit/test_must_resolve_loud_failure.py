"""The must-resolve filer and its launch gate fail loudly (ADR 0236, #3585).

A requirements conflict halts the run and files a question the operator must
rule on before the next launch. Every way that filing could fail used to print
a line to stdout and nothing more, and several read as success: a dedupe query
that failed read as "no existing issue" and filed a duplicate, an issue created
with no parsable number was reported "filed" and never recorded, ledger writes
that failed were ignored, an unreadable or corrupt ledger read as no questions,
and a launch gate that could not reach GitHub warned and launched.

Now each filing failure alerts the operator and returns a failed result (the
halt is already happening and is never changed), the ledger reader alerts and
raises, and a launch gate that cannot run refuses the launch.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from assemblyzero.core.github_writes import inert_github_writes
from assemblyzero.speedrun import must_resolve as mr

CONFLICT = {
    "criterion_a": "The dashboard refreshes once per minute.",
    "criterion_b": "The dashboard is real-time with sub-second updates.",
    "diverging_situation": "A viewer watching a spike sees it a minute late.",
}

CREATED_URL = "https://github.com/o/r/issues/224\n"


class FakeGh:
    """Answers git and gh the way a scripted GitHub would, and records argv."""

    def __init__(
        self,
        *,
        remote: str | None = "https://github.com/o/r.git\n",
        issue_list: tuple[int, str, str] = (0, "[]", ""),
        create: tuple[int, str, str] = (0, CREATED_URL, ""),
        comment: tuple[int, str, str] = (0, "", ""),
        label: tuple[int, str, str] = (0, "", ""),
    ):
        self.remote = remote
        self.issue_list = issue_list
        self.create = create
        self.comment = comment
        self.label = label
        self.calls: list[list[str]] = []

    def __call__(self, args):
        self.calls.append(list(args))
        if args[0] == "git":
            if self.remote is None:
                return subprocess.CompletedProcess(args, 2, "", "error: No such remote 'origin'")
            return subprocess.CompletedProcess(args, 0, self.remote, "")
        verb = " ".join(args[1:3])
        answer = {
            "issue list": self.issue_list,
            "issue create": self.create,
            "issue comment": self.comment,
            "label create": self.label,
        }.get(verb, (0, "", ""))
        return subprocess.CompletedProcess(args, *answer)

    def made(self, fragment: str) -> list[list[str]]:
        return [c for c in self.calls if fragment in " ".join(c)]


def _existing(number: int, source_issue: int) -> str:
    fp = mr.conflict_fingerprint(CONFLICT["criterion_a"], CONFLICT["criterion_b"])
    body = mr.build_body(
        source_issue, CONFLICT, run_id="prev", run_start="x", conflict_ts="y", fingerprint=fp
    )
    return json.dumps([{"number": number, "body": body}])


def _block_the_ledger(repo: Path) -> Path:
    """A file where the ledger's directory must be, so every write fails."""
    blocker = repo / "data"
    blocker.write_text("not a directory\n", encoding="utf-8")
    return mr.filed_ledger_path(repo)


def _file(repo, gh, issue=4, conflict=CONFLICT):
    return mr.file_must_resolve(repo, issue, conflict, runner=gh, log=lambda _m: None)


# --- kept behaviour --------------------------------------------------------


def test_176_a_missing_binary_is_a_127_result_by_contract():
    result = mr._default_runner(["definitely-not-an-installed-binary-3585"])
    assert result.returncode == 127


def test_a_healthy_filing_alerts_nobody(tmp_path, operator_alerts):
    result = _file(tmp_path, FakeGh())

    assert result.ok and result.action == "filed" and result.issue_number == 224
    assert operator_alerts == []


# --- the dedupe query -------------------------------------------------------


def test_355_a_failed_dedupe_query_is_a_failed_filing_not_a_new_issue(tmp_path, operator_alerts):
    gh = FakeGh(issue_list=(1, "", "HTTP 502: Bad Gateway"))

    result = _file(tmp_path, gh)

    assert not result.ok and result.action == "failed"
    assert gh.made("issue create") == [], "a query that failed is not 'no existing issue'"
    assert len(operator_alerts) == 1
    assert "502" in operator_alerts[0]["cause"]
    assert operator_alerts[0]["issue"] == 4


def test_359_an_unparseable_dedupe_answer_is_a_failed_filing(tmp_path, operator_alerts):
    gh = FakeGh(issue_list=(0, "<html>rate limited</html>", ""))

    result = _file(tmp_path, gh)

    assert not result.ok and result.action == "failed"
    assert gh.made("issue create") == []
    assert len(operator_alerts) == 1


def test_359_a_dedupe_answer_that_is_not_a_list_is_a_failed_filing(tmp_path, operator_alerts):
    gh = FakeGh(issue_list=(0, json.dumps({"message": "Bad credentials"}), ""))

    result = _file(tmp_path, gh)

    assert not result.ok and result.action == "failed"
    assert gh.made("issue create") == []
    assert len(operator_alerts) == 1


# --- the label and the create -----------------------------------------------


def test_372_a_label_that_cannot_be_created_is_reported_with_its_stderr(
    tmp_path, operator_alerts
):
    gh = FakeGh(
        create=(1, "", "could not add label: 'must-resolve' not found"),
        label=(1, "", "HTTP 403: Resource not accessible by integration"),
    )

    result = _file(tmp_path, gh)

    assert not result.ok and result.action == "failed"
    assert len(operator_alerts) == 1
    cause = operator_alerts[0]["cause"]
    assert "403" in cause, "the label's own failure is named, not dropped"
    assert "not found" in cause


def test_372_a_label_failure_the_retry_proves_harmless_files(tmp_path, operator_alerts):
    """The label already existed: its create fails, and the retried issue
    create, which carries the label, succeeds. Nothing the caller needs failed."""
    attempts = {"n": 0}
    gh = FakeGh(label=(1, "", 'label with name "must-resolve" already exists'))
    real = gh.__call__

    def flaky(args):
        if args[1:3] == ["issue", "create"]:
            attempts["n"] += 1
            if attempts["n"] == 1:
                gh.calls.append(list(args))
                return subprocess.CompletedProcess(args, 1, "", "HTTP 502")
        return real(args)

    result = mr.file_must_resolve(tmp_path, 4, CONFLICT, runner=flaky, log=lambda _m: None)

    assert result.ok and result.action == "filed" and result.issue_number == 224
    assert operator_alerts == []


def test_498_an_issue_that_cannot_be_created_alerts(tmp_path, operator_alerts):
    gh = FakeGh(create=(1, "", "HTTP 422: Validation Failed"))

    result = _file(tmp_path, gh)

    assert not result.ok and result.action == "failed"
    assert len(gh.made("issue create")) == 2, "exactly one retry"
    assert len(operator_alerts) == 1
    assert "422" in operator_alerts[0]["cause"]


def test_503_a_created_issue_with_no_number_is_a_failure(tmp_path, operator_alerts):
    gh = FakeGh(create=(0, "Creating issue in o/r\n", ""))

    result = _file(tmp_path, gh)

    assert not result.ok and result.action == "failed"
    assert result.issue_number is None
    assert len(operator_alerts) == 1
    assert "Creating issue in o/r" in operator_alerts[0]["cause"]
    assert not mr.filed_ledger_path(tmp_path).exists()


# --- the run cannot be filed against ----------------------------------------


def test_411_an_unanswerable_conflict_alerts_the_operator(tmp_path, operator_alerts):
    gh = FakeGh()
    conflict = dict(CONFLICT, diverging_situation="?")

    result = _file(tmp_path, gh, conflict=conflict)

    assert not result.ok and result.action == "rejected"
    assert gh.calls == []
    assert len(operator_alerts) == 1
    assert "punctuation only" in operator_alerts[0]["cause"]
    assert operator_alerts[0]["issue"] == 4


def test_451_no_github_remote_alerts_the_operator(tmp_path, operator_alerts):
    result = _file(tmp_path, FakeGh(remote=None))

    assert not result.ok and result.action == "failed"
    assert len(operator_alerts) == 1
    assert "remote" in operator_alerts[0]["cause"]


# --- a recurrence ----------------------------------------------------------


def test_465_a_recurrence_comment_that_fails_alerts(tmp_path, operator_alerts):
    gh = FakeGh(issue_list=(0, _existing(224, 4), ""), comment=(1, "", "HTTP 404"))

    result = _file(tmp_path, gh)

    assert not result.ok and result.action == "failed"
    assert result.issue_number == 224
    assert len(operator_alerts) == 1
    assert "404" in operator_alerts[0]["cause"]


def test_473_a_recurrence_that_cannot_be_recorded_is_a_failure(tmp_path, operator_alerts):
    ledger = _block_the_ledger(tmp_path)
    gh = FakeGh(issue_list=(0, _existing(224, 4), ""))

    result = _file(tmp_path, gh)

    assert not result.ok and result.action == "failed"
    assert result.issue_number == 224
    assert len(operator_alerts) == 1
    assert str(ledger) in operator_alerts[0]["cause"]
    assert "#224" in operator_alerts[0]["what"]


# --- the ledger writes -------------------------------------------------------


def test_443_a_suppressed_filing_that_cannot_be_recorded_is_a_failure(tmp_path, operator_alerts):
    ledger = _block_the_ledger(tmp_path)

    with inert_github_writes("replay"):
        result = _file(tmp_path, FakeGh())

    assert not result.ok and result.action == "failed"
    assert len(operator_alerts) == 1
    assert str(ledger) in operator_alerts[0]["cause"]


def test_509_a_new_filing_that_cannot_be_recorded_is_a_failure(tmp_path, operator_alerts):
    ledger = _block_the_ledger(tmp_path)

    result = _file(tmp_path, FakeGh())

    assert not result.ok and result.action == "failed"
    assert result.issue_number == 224, "the issue exists on GitHub; say which"
    assert len(operator_alerts) == 1
    assert str(ledger) in operator_alerts[0]["cause"]
    assert "#224" in operator_alerts[0]["what"]


def test_613_a_ledger_write_that_fails_raises_naming_the_ledger(tmp_path):
    ledger = _block_the_ledger(tmp_path)

    with pytest.raises(OSError) as raised:
        mr.record_filed(tmp_path, number=224, title="t")

    assert str(ledger) in str(raised.value)


def test_613_a_record_with_no_number_and_no_suppression_raises(tmp_path):
    with pytest.raises(ValueError):
        mr.record_filed(tmp_path, number=None, title="t")
    assert not mr.filed_ledger_path(tmp_path).exists()


# --- the ledger read ------------------------------------------------------


def test_630_an_absent_ledger_is_a_quiet_empty_answer(tmp_path, operator_alerts):
    assert mr.read_filed(tmp_path) == []
    assert operator_alerts == []


def test_630_an_unreadable_ledger_alerts_and_raises(tmp_path, operator_alerts):
    path = mr.filed_ledger_path(tmp_path)
    path.mkdir(parents=True)  # a directory where the file must be

    with pytest.raises(OSError):
        mr.read_filed(tmp_path)

    assert len(operator_alerts) == 1
    assert str(path) in operator_alerts[0]["cause"]


def _ledger_with(tmp_path, *lines: str) -> Path:
    path = mr.filed_ledger_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def test_639_a_corrupt_ledger_line_alerts_and_raises_naming_it(tmp_path, operator_alerts):
    path = _ledger_with(
        tmp_path,
        '{"number": 273, "title": "a", "ts": "2026-08-11 08:34:45"}',
        "not json at all",
        '{"number": 275, "title": "c", "ts": "2026-08-11 08:34:49"}',
    )

    with pytest.raises(ValueError) as raised:
        mr.read_filed(tmp_path)

    assert f"{path}:2" in str(raised.value)
    assert len(operator_alerts) == 1
    assert f"{path}:2" in operator_alerts[0]["cause"]


def test_639_a_line_that_is_not_an_object_alerts_and_raises(tmp_path, operator_alerts):
    path = _ledger_with(tmp_path, "[273, 274]")

    with pytest.raises(ValueError) as raised:
        mr.read_filed(tmp_path)

    assert f"{path}:1" in str(raised.value)
    assert len(operator_alerts) == 1


def test_639_a_suppressed_line_with_no_number_is_skipped_by_contract(tmp_path, operator_alerts):
    _ledger_with(
        tmp_path,
        '{"number": null, "title": "t", "suppressed": "replay", "ts": "2026-08-11 08:00:00"}',
        '{"number": 273, "title": "a", "ts": "2026-08-11 08:34:45"}',
    )

    assert [e["number"] for e in mr.read_filed(tmp_path)] == [273]
    assert operator_alerts == []


# --- the launch gate ---------------------------------------------------------


def test_527_no_remote_for_the_open_question_gate_alerts(tmp_path, operator_alerts):
    issues, error = mr.open_must_resolve_issues(tmp_path, runner=FakeGh(remote=None))

    assert issues == [] and error
    assert len(operator_alerts) == 1
    assert "launch" in operator_alerts[0]["consequence"]


def test_535_a_failing_issue_list_for_the_gate_alerts(tmp_path, operator_alerts):
    gh = FakeGh(issue_list=(1, "", "could not connect to github.com"))

    issues, error = mr.open_must_resolve_issues(tmp_path, runner=gh)

    assert issues == [] and "github.com" in error
    assert len(operator_alerts) == 1
    assert "github.com" in operator_alerts[0]["cause"]


def test_539_an_unparseable_gate_answer_alerts(tmp_path, operator_alerts):
    gh = FakeGh(issue_list=(0, "<html>rate limited</html>", ""))

    issues, error = mr.open_must_resolve_issues(tmp_path, runner=gh)

    assert issues == [] and error
    assert len(operator_alerts) == 1


def test_539_a_gate_answer_that_is_not_a_list_alerts(tmp_path, operator_alerts):
    gh = FakeGh(issue_list=(0, json.dumps({"message": "Bad credentials"}), ""))

    issues, error = mr.open_must_resolve_issues(tmp_path, runner=gh)

    assert issues == [] and error
    assert len(operator_alerts) == 1


def test_a_gate_that_reaches_github_alerts_nobody(tmp_path, operator_alerts):
    gh = FakeGh(issue_list=(0, json.dumps([{"number": 224, "title": "t"}]), ""))

    issues, error = mr.open_must_resolve_issues(tmp_path, runner=gh)

    assert issues == [{"number": 224, "title": "t"}] and error is None
    assert operator_alerts == []


@pytest.fixture
def launcher(monkeypatch, tmp_path):
    """speedrun_roll.main on a real git repo, everything past the gate stubbed."""
    tools = Path(__file__).resolve().parents[2] / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import speedrun_roll

    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "Test"],
    ):
        subprocess.run(
            ["git", "-C", str(tmp_path), *args], capture_output=True, text=True, check=True
        )
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-qm", "base"], capture_output=True, check=True
    )

    rolls: list[int] = []
    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda _root: [])
    monkeypatch.setattr(
        speedrun_roll, "sweep_pipeline_worktrees",
        lambda *_a, **_k: type("Sweep", (), {"problems": []})(),
    )
    monkeypatch.setattr(speedrun_roll, "install_signal_handlers", lambda _s: None)
    monkeypatch.setattr(
        speedrun_roll, "roll_issue", lambda _r, issue, *_a: rolls.append(issue) or 0
    )
    monkeypatch.setattr(speedrun_roll, "ensure_base", lambda *_a, **_k: "hardening-run-1")
    monkeypatch.setattr(speedrun_roll, "launch_detached", lambda *_a, **_k: 0)
    argv = ["--repo", str(tmp_path), "--log-dir", str(tmp_path / "logs"), "--issue", "4"]
    return speedrun_roll, argv, rolls


def test_535_the_launch_refuses_when_the_gate_cannot_run(launcher, monkeypatch, capsys):
    speedrun_roll, argv, rolls = launcher
    monkeypatch.setattr(
        speedrun_roll, "open_must_resolve_issues",
        lambda _r: ([], "could not connect to github.com"),
    )

    code = speedrun_roll.main(argv)

    assert code == 91, "a check that cannot run is a failure, never a pass"
    assert rolls == []
    assert "github.com" in capsys.readouterr().out


# --- one conflict's filing raising -------------------------------------------


def test_721_a_filing_that_raises_alerts_and_the_next_still_files(tmp_path, operator_alerts):
    gh = FakeGh()
    calls = {"n": 0}

    def first_one_explodes(args):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("unexpected runner failure")
        return gh(args)

    other = dict(CONFLICT, criterion_a="The dashboard refreshes once per hour.")
    results = mr.file_all_conflicts(
        tmp_path, 4, [CONFLICT, other], runner=first_one_explodes, log=lambda _m: None
    )

    assert [r.action for r in results] == ["failed", "filed"]
    assert len(operator_alerts) == 1
    assert "ValueError" in operator_alerts[0]["cause"]
    assert operator_alerts[0]["issue"] == 4

"""N4's orchestrator under standard 0034 (ADR 0236), the #3585 sweep.

Every site ledger 0908 names in
``assemblyzero/workflows/testing/nodes/implementation/orchestrator.py`` has a
test here, named by the ledger's line number at its base ``79e18ad1``. Three
more are ``edit_script_fix.py``'s rows (497, 503, 507): a patch that does not
apply is a fallback the orchestrator takes, so it is the orchestrator that
alerts on it.

What is now true:

* every ``raise ImplementationError`` writes an ERROR line naming the file
  and the reason on stderr where it is raised; the runner alerts on it;
* a file N4 needs that it cannot read stops N4 with an ERROR line naming the
  file, instead of feeding an empty string to the prompt or the context;
* ``came_from_base`` reads only git's "not tracked" answer as untracked, and
  raises on any other failure of ``git ls-files``;
* every fallback (an edit script that does not apply, a batch that cannot be
  used) alerts the operator with the file, the cause and what happens next.

No test makes a model call: ``orchestrator.call_claude_for_file`` is replaced
in every test, and the provider gate behind it refuses.
"""

from __future__ import annotations

import io
import subprocess
import tokenize
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.graph import route_after_implement
from assemblyzero.workflows.testing.nodes.implementation import (
    claude_client,
    orchestrator,
)
from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
    ImplementationError,
)
from assemblyzero.workflows.testing.nodes.implementation.routing import SMALL_SEAT

ISSUE = 7
VALID = "```python\ndef value():\n    return 1\n```"
BIG = "# " + ("x" * 900) + "\n" + "def value():\n    return 0\n"  # over MIN_BYTES_FOR_EDIT_SCRIPT
WIDGET_CORPUS = """\
test_widget_value
    src/pkg/widget.py:3: in value
    E   AssertionError
"""


class FakeModel:
    """Stands in for ``call_claude_for_file``: queued replies, then VALID."""

    def __init__(self) -> None:
        self.replies: list = []
        self.calls: list[dict] = []

    def __call__(self, prompt="", file_path="", seat=None, system_prompt="", **kw):
        self.calls.append({"prompt": prompt, "file_path": file_path, "seat": seat})
        if self.replies:
            reply = self.replies.pop(0)
            if isinstance(reply, BaseException):
                raise reply
            return reply
        return VALID, ""


@pytest.fixture(autouse=True)
def model(monkeypatch):
    fake = FakeModel()
    monkeypatch.setattr(orchestrator, "call_claude_for_file", fake)

    def refuse(*_a, **_k):
        raise AssertionError("a real model transport was reached")

    monkeypatch.setattr(claude_client, "get_provider", refuse)
    monkeypatch.setattr(orchestrator, "record_iteration_cost", lambda state: 0)
    monkeypatch.setattr(orchestrator, "get_cumulative_cost", lambda: 0.0)
    return fake


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    return tmp_path


@pytest.fixture
def unreadable(monkeypatch):
    """Make named paths raise PermissionError on read, on every platform."""
    blocked: set[str] = set()
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if str(Path(self).resolve()) in blocked:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    return lambda path: blocked.add(str(Path(path).resolve()))


def _write(repo: Path, rel: str, text: str) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _track(repo: Path, rel: str) -> None:
    subprocess.run(["git", "-C", str(repo), "add", "--", rel], check=True, capture_output=True)


def _state(repo: Path, files: list[dict], **overrides) -> dict:
    state = {
        "repo_root": str(repo),
        "issue_number": ISSUE,
        "lld_content": "## 2.1 Files\n",
        "files_to_modify": files,
        "test_files": [],
        "iteration_count": 0,
        "audit_dir": str(repo / "no-audit"),
    }
    state.update(overrides)
    return state


def _error_lines(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("ERROR")]


def _loud(err: str, *needles: str) -> bool:
    """One ERROR line on stderr carries every needle."""
    return any(all(n in line for n in needles) for line in _error_lines(err))


# ---------------------------------------------------------------------------
# try_edit_script_fix: every fallback alerts (ledger 117, 125, 135; and
# edit_script_fix.py 497, 503, 507)
# ---------------------------------------------------------------------------


def _patch(existing: str = BIG, identity: bool = True):
    """One patch attempt; ``identity`` passes the repo and issue the alert names."""
    kwargs = {"repo": "the-repo", "issue": ISSUE} if identity else {}
    return orchestrator.try_edit_script_fix(
        filepath="src/pkg/widget.py",
        existing_content=existing,
        failure_context=WIDGET_CORPUS,
        **kwargs,
    )


def _one_fallback_alert(alerts: list[dict], *in_cause: str) -> dict:
    assert len(alerts) == 1, alerts
    record = alerts[0]
    assert "src/pkg/widget.py" in record["what"]
    for needle in in_cause:
        assert needle in record["cause"], record["cause"]
    assert "regenerated whole" in record["consequence"]
    assert record["issue"] == ISSUE
    assert record["repo"] == "the-repo"
    return record


class TestTheEditScriptFallbackAlerts:
    def test_117_a_call_that_raises_alerts_and_falls_back(self, model, operator_alerts):
        model.replies = [RuntimeError("transport crashed")]

        outcome = _patch()

        assert outcome.code is None
        _one_fallback_alert(operator_alerts, "RuntimeError", "transport crashed")

    def test_125_an_api_error_alerts_and_falls_back(self, model, operator_alerts):
        model.replies = [("", "HTTP 500 from the provider")]

        outcome = _patch()

        assert outcome.code is None
        _one_fallback_alert(operator_alerts, "API error", "HTTP 500 from the provider")

    def test_135_a_whole_file_instead_of_edit_blocks_alerts(self, model, operator_alerts):
        model.replies = [("```python\nimport os\n\ndef value():\n    return 1\n```", "")]

        outcome = _patch()

        assert outcome.code is None
        _one_fallback_alert(operator_alerts, "whole file instead of edit blocks")

    def test_497_a_response_with_no_edit_blocks_alerts(self, model, operator_alerts):
        """edit_script_fix.py:497 -- the fallback is taken here, so it alerts here."""
        model.replies = [("I think the fix belongs in another place.\nSorry.", "")]

        outcome = _patch()

        assert outcome.code is None
        _one_fallback_alert(operator_alerts, "no edit blocks in response")

    def test_503_blocks_that_do_not_apply_alert_naming_them(self, model, operator_alerts):
        """edit_script_fix.py:503."""
        model.replies = [(
            "<<<<<<< SEARCH\nthis line is not in the file\n=======\nx = 2\n>>>>>>> REPLACE",
            "",
        )]

        outcome = _patch()

        assert outcome.code is None
        record = _one_fallback_alert(operator_alerts)
        assert "1 edit block" in record["cause"]
        assert "not found" in record["cause"].lower()

    def test_507_edits_that_empty_the_file_alert(self, model, operator_alerts):
        """edit_script_fix.py:507."""
        existing = "x = 1\n" * 100
        model.replies = [(
            "<<<<<<< SEARCH\n" + existing.rstrip("\n") + "\n=======\n\n>>>>>>> REPLACE",
            "",
        )]

        outcome = _patch(existing=existing)

        assert outcome.code is None
        _one_fallback_alert(operator_alerts, "edits emptied the file")

    def test_a_patch_that_applies_does_not_alert(self, model, operator_alerts):
        """Kept: a patch that applies is not a failure."""
        model.replies = [(
            "<<<<<<< SEARCH\n    return 0\n=======\n    return 1\n>>>>>>> REPLACE", "",
        )]

        outcome = _patch(identity=False)

        assert outcome.code is not None and "return 1" in outcome.code
        assert operator_alerts == []

    def test_a_no_edit_answer_does_not_alert(self, model, operator_alerts):
        """Kept: "nothing to change here" is an answer (#2915), not a fallback."""
        model.replies = [("NO-EDIT: the fix is in collector.py", "")]

        outcome = _patch(identity=False)

        assert outcome.code == BIG
        assert operator_alerts == []


# ---------------------------------------------------------------------------
# generate_file_with_retry: every raise is an ERROR line where it is raised
# (ledger 239, 270, 301, 316, 344, 357)
# ---------------------------------------------------------------------------


def _generate(max_retries: int = 1):
    return orchestrator.generate_file_with_retry(
        filepath="src/pkg/widget.py", base_prompt="write it", max_retries=max_retries,
    )


class TestEveryRaiseInTheRetryLoopIsLoud:
    def test_239_a_non_retryable_api_error(self, model, capsys):
        model.replies = [("", "[NON-RETRYABLE] invalid api key")]

        with pytest.raises(ImplementationError, match="Non-retryable API error"):
            _generate()

        assert _loud(capsys.readouterr().err, "src/pkg/widget.py", "Non-retryable API error")

    def test_270_a_transport_error_with_no_retry_left(self, model, capsys):
        model.replies = [("", "HTTP 529 overloaded")]

        with pytest.raises(ImplementationError, match="API error after 1 attempts"):
            _generate(max_retries=1)

        assert _loud(capsys.readouterr().err, "src/pkg/widget.py", "API error after 1 attempts")

    def test_301_a_summary_on_every_attempt(self, model, capsys):
        model.replies = [("Here's a summary of what I did.", "")]

        with pytest.raises(ImplementationError, match="Summary response"):
            _generate()

        assert _loud(capsys.readouterr().err, "src/pkg/widget.py", "Summary response after 1 attempts")

    def test_316_no_code_block_on_every_attempt(self, model, capsys):
        model.replies = [("there is no code in this answer", "")]

        with pytest.raises(ImplementationError, match="No code block"):
            _generate()

        assert _loud(capsys.readouterr().err, "src/pkg/widget.py", "No code block after 1 attempts")

    def test_344_validation_fails_on_every_attempt(self, model, capsys):
        model.replies = [("```python\ndef broken(:\n    pass\n```", "")]

        with pytest.raises(ImplementationError, match="Validation failed"):
            _generate()

        assert _loud(capsys.readouterr().err, "src/pkg/widget.py", "Validation failed after 1 attempts")

    def test_357_a_loop_that_runs_no_attempt(self, model, capsys):
        with pytest.raises(ImplementationError, match="Failed after 0 attempts"):
            _generate(max_retries=0)

        assert model.calls == []
        assert _loud(capsys.readouterr().err, "src/pkg/widget.py", "Failed after 0 attempts")


# ---------------------------------------------------------------------------
# came_from_base (ledger 439)
# ---------------------------------------------------------------------------


class TestCameFromBase:
    def test_439_a_git_failure_other_than_untracked_raises(self, tmp_path, capsys):
        """Not a repository: git exits 128. That is not "untracked"."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")

        with pytest.raises(subprocess.CalledProcessError) as raised:
            orchestrator.came_from_base(tmp_path, "src/x.py")

        assert raised.value.returncode not in (0, 1)
        assert _loud(capsys.readouterr().err, "src/x.py", "git ls-files")

    def test_tracked_and_untracked_keep_their_answers(self, repo):
        """Kept: 0 is tracked, 1 is git's own "did not match" for an untracked path."""
        _write(repo, "src/base.py", "x = 1\n")
        _write(repo, "src/new.py", "y = 1\n")
        _track(repo, "src/base.py")

        assert orchestrator.came_from_base(repo, "src/base.py") is True
        assert orchestrator.came_from_base(repo, "src/new.py") is False


# ---------------------------------------------------------------------------
# implement_code (ledger 559, 572, 589, 693, 704, 717, 819, 912, 933, 946,
# 1016, 1065, 1120, 1146)
# ---------------------------------------------------------------------------


class TestTheCompliantHalts:
    def test_559_no_files_to_modify_halts(self, repo):
        """Kept: an error_message route_after_implement sends to HALT, which alerts."""
        result = orchestrator.implement_code(_state(repo, []))

        assert "No files to implement" in result["error_message"]
        assert route_after_implement(result) == "HALT"

    def test_572_paths_that_fail_preflight_halt(self, repo, model):
        """Kept: the path guard's error_message goes to HALT."""
        result = orchestrator.implement_code(
            _state(repo, [{"path": "src/gone.py", "change_type": "Delete"}])
        )

        assert "do not match the repository structure" in result["error_message"]
        assert route_after_implement(result) == "HALT"
        assert model.calls == []


class TestAReadN4NeedsStopsIt:
    def test_589_an_unreadable_test_file_stops_before_the_prompt(
        self, repo, model, unreadable, capsys,
    ):
        test_file = _write(repo, "tests/test_widget.py", "def test_value():\n    pass\n")
        unreadable(test_file)
        state = _state(
            repo, [{"path": "src/pkg/widget.py", "change_type": "Add"}],
            test_files=[str(test_file)],
        )

        with pytest.raises(PermissionError):
            orchestrator.implement_code(state)

        assert model.calls == []
        assert _loud(capsys.readouterr().err, "test_widget.py", "could not read")

    def test_819_an_unreadable_modify_target_stops(self, repo, model, unreadable, capsys):
        target = _write(repo, "src/pkg/widget.py", "def value():\n    return 0\n")
        unreadable(target)

        with pytest.raises(PermissionError):
            orchestrator.implement_code(
                _state(repo, [{"path": "src/pkg/widget.py", "change_type": "Modify"}])
            )

        assert model.calls == []
        assert _loud(capsys.readouterr().err, "widget.py", "could not read")

    def test_912_an_unreadable_file_for_the_edit_script_stops(
        self, repo, model, unreadable, capsys,
    ):
        """An Add the base ships becomes a Modify, and the edit script reads it."""
        target = _write(repo, "src/pkg/widget.py", BIG)
        _track(repo, "src/pkg/widget.py")
        unreadable(target)

        with pytest.raises(PermissionError):
            orchestrator.implement_code(
                _state(repo, [{"path": "src/pkg/widget.py", "change_type": "Add"}])
            )

        assert model.calls == []
        assert _loud(capsys.readouterr().err, "widget.py", "could not read")

    def test_1016_an_unreadable_unattributed_file_stops(
        self, repo, model, unreadable, capsys,
    ):
        gadget = _write(repo, "src/pkg/gadget.py", "def gadget():\n    return 0\n")
        _write(repo, "src/pkg/widget.py", "def value():\n    return 0\n")
        unreadable(gadget)
        state = _state(
            repo,
            [
                {"path": "src/pkg/gadget.py", "change_type": "Add"},
                {"path": "src/pkg/widget.py", "change_type": "Modify"},
            ],
            iteration_count=1,
            test_failure_summary=WIDGET_CORPUS,
        )

        with pytest.raises(PermissionError):
            orchestrator.implement_code(state)

        assert model.calls == []
        assert _loud(capsys.readouterr().err, "gadget.py", "could not read")

    def test_1065_an_unreadable_test_file_after_a_failed_patch_stops(
        self, repo, model, unreadable, capsys, monkeypatch,
    ):
        test_file = _write(repo, "tests/test_widget.py", BIG + "def test_value():\n    pass\n")
        _track(repo, "tests/test_widget.py")
        from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
            EditScriptOutcome,
        )

        def failing_patch(filepath, **_kw):
            unreadable(test_file)
            return EditScriptOutcome(None, failures=["block 1: SEARCH text not found"])

        monkeypatch.setattr(orchestrator, "try_edit_script_fix", failing_patch)
        state = _state(
            repo, [{"path": "tests/test_widget.py", "change_type": "Add"}],
            iteration_count=1,
            test_failure_summary="test_value\n    tests/test_widget.py:5: in test_value\n    E   AssertionError\n",
        )

        with pytest.raises(PermissionError):
            orchestrator.implement_code(state)

        assert _loud(capsys.readouterr().err, "test_widget.py", "could not read")

    def test_1120_an_unreadable_spec_suite_stops(
        self, repo, model, unreadable, capsys, monkeypatch,
    ):
        _write(repo, "tests/test_widget.py", "def test_value():\n    assert True\n")
        suite = _write(repo, f"tests/test_issue_{ISSUE}.py", "def test_value():\n    assert True\n")
        unreadable(suite)
        monkeypatch.setattr(
            orchestrator, "generate_file_with_retry",
            lambda **_kw: ("def test_value():\n    assert 1\n", True),
        )
        state = _state(
            repo, [{"path": "tests/test_widget.py", "change_type": "Modify"}],
            iteration_count=1,
            test_failure_summary="test_value\n    tests/test_widget.py:2: in test_value\n    E   AssertionError\n",
            contract_tests=["test_value"],
        )

        with pytest.raises(PermissionError):
            orchestrator.implement_code(state)

        assert _loud(capsys.readouterr().err, f"test_issue_{ISSUE}.py", "could not read")


class TestEveryRaiseInImplementCodeIsLoud:
    def test_933_a_modify_target_gone_by_the_time_it_is_reached(self, repo, model, capsys):
        """A Delete earlier in the same plan removes the file a Modify names."""
        _write(repo, "src/pkg/widget.py", "def value():\n    return 0\n")
        files = [
            {"path": "src/pkg/widget.py", "change_type": "Delete"},
            {"path": "src/pkg/widget.py", "change_type": "Modify"},
        ]

        with pytest.raises(ImplementationError, match="does not exist"):
            orchestrator.implement_code(_state(repo, files))

        assert model.calls == []
        assert _loud(capsys.readouterr().err, "src/pkg/widget.py", "File marked as 'Modify' but does not exist")

    def test_946_context_over_the_limit(self, repo, model, capsys, monkeypatch):
        monkeypatch.setattr(orchestrator, "estimate_context_tokens", lambda *_a: 200_000)

        with pytest.raises(ImplementationError, match="Context too large"):
            orchestrator.implement_code(
                _state(repo, [{"path": "src/pkg/widget.py", "change_type": "Add"}])
            )

        assert model.calls == []
        assert _loud(capsys.readouterr().err, "src/pkg/widget.py", "Context too large")

    def test_1146_a_write_that_fails(self, repo, model, capsys, monkeypatch):
        real = Path.write_text

        def write_text(self, *args, **kwargs):
            if str(self).endswith("widget.py.tmp"):
                raise OSError(28, "No space left on device")
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", write_text)

        with pytest.raises(ImplementationError, match="Failed to write file"):
            orchestrator.implement_code(
                _state(repo, [{"path": "src/pkg/widget.py", "change_type": "Add"}])
            )

        assert _loud(capsys.readouterr().err, "src/pkg/widget.py", "Failed to write file")


# ---------------------------------------------------------------------------
# The batch path (ledger 693, 704, 717)
# ---------------------------------------------------------------------------

SMALL = {
    "path": "src/pkg/small.py", "change_type": "Add", "estimated_line_count": 10,
    "description": "a small helper module that returns one value to its caller",
}


def _batch_alert(alerts: list[dict]) -> dict:
    assert len(alerts) == 1, alerts
    record = alerts[0]
    assert "batch" in record["what"]
    assert record["issue"] == ISSUE
    assert "on its own" in record["consequence"]
    return record


class TestTheBatchFallbackAlerts:
    def test_693_a_batch_call_that_fails_alerts(self, repo, model, operator_alerts):
        model.replies = [("", "rate limited by the provider")]

        result = orchestrator.implement_code(_state(repo, [dict(SMALL)]))

        assert model.calls[0]["seat"] == SMALL_SEAT
        record = _batch_alert(operator_alerts)
        assert "rate limited by the provider" in record["cause"]
        assert "src/pkg/small.py" in record["cause"] or "src/pkg/small.py" in record["what"]
        assert result["error_message"] == ""
        assert (repo / "src/pkg/small.py").read_text(encoding="utf-8").startswith("def value")

    def test_704_a_file_missing_from_the_batch_response_alerts(self, repo, model, operator_alerts):
        model.replies = [("the files are below, but no markers", "")]

        orchestrator.implement_code(_state(repo, [dict(SMALL)]))

        record = _batch_alert(operator_alerts)
        assert "src/pkg/small.py" in record["cause"]
        assert "no code" in record["cause"]

    def test_717_a_batch_file_that_fails_validation_alerts(self, repo, model, operator_alerts):
        model.replies = [(
            "=== FILE: src/pkg/small.py ===\n```python\ndef broken(:\n    pass\n```\n", "",
        )]

        orchestrator.implement_code(_state(repo, [dict(SMALL)]))

        record = _batch_alert(operator_alerts)
        assert "src/pkg/small.py" in record["cause"]
        assert "syntax error" in record["cause"]

    def test_a_batch_that_works_does_not_alert(self, repo, model, operator_alerts):
        """Kept: a usable batch writes its files and alerts no one."""
        model.replies = [(
            "=== FILE: src/pkg/small.py ===\n" + VALID + "\n", "",
        )]

        result = orchestrator.implement_code(_state(repo, [dict(SMALL)]))

        assert operator_alerts == []
        assert result["error_message"] == ""
        assert len(model.calls) == 1


# ---------------------------------------------------------------------------
# The withdrawn tags (ledger 913, 1017, 1066, 1121)
# ---------------------------------------------------------------------------


def test_913_1017_1066_1121_the_module_carries_no_fail_open_tag():
    source = Path(orchestrator.__file__).read_text(encoding="utf-8")
    tags = [
        tok.start[0]
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT and "fail-open:" in tok.string
    ]
    assert tags == []

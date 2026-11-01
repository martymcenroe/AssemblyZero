"""Every failure in `tools/run_requirements_workflow.py` is loud and alerts (#4100).

ADR 0236 and standard 0034: a failure is loud on standard error, logged with
details, stops what depends on it, and alerts the operator. The #3581 sweep
recorded 36 sites in this entry point (ledger 0908, lines from `79e18ad1`).
Each test here is named for its ledger line and drives `main()` with
stand-ins: a throwaway target repository, a fake graph driver in place of
`invoke_with_budget`, and a fake `gh` where one is needed. No model is called
and no graph node runs.

The entry point's shape: `main()` has one handler, which prints the failure
at ERROR on stderr (with its traceback when the tool did not name it itself),
calls `alert.alert_operator` unless the HALT node already did, and returns 1.
Everything below it raises with its cause.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.requirements.audit import (
    AUDIT_ACTIVE_DIR,
    LLD_ACTIVE_DIR,
    generate_slug,
)

ISSUE_URL = "https://github.com/example/target/issues/7"


def _git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"


@pytest.fixture
def target(tmp_path: Path) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


@pytest.fixture(autouse=True)
def _environment(tmp_path, monkeypatch):
    """The checkpoint DB stays in tmp; no test mode, no root override."""
    monkeypatch.setenv("ASSEMBLYZERO_WORKFLOW_DB", str(tmp_path / "ckpt" / "wf.db"))
    monkeypatch.delenv("ASSEMBLYZERO_TEST_MODE", raising=False)
    monkeypatch.delenv("ASSEMBLYZERO_ROOT", raising=False)


@pytest.fixture(autouse=True)
def _restore_streams():
    """The run record tees stdout and stderr until it is finished."""
    out, err = sys.stdout, sys.stderr
    yield
    sys.stdout, sys.stderr = out, err


@pytest.fixture(autouse=True)
def _disarm_call_recording():
    from assemblyzero.core import call_recording

    yield
    call_recording.reset_context()


class _Driver:
    """Stands in for `invoke_with_budget`: call N takes outcome N (the last
    one repeats). An outcome is the final state's changes, or an exception."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    def __call__(self, compiled, state, *, stage, max_iterations):
        self.calls.append(dict(state))
        outcome = self.outcomes[min(len(self.calls), len(self.outcomes)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return {**state, **outcome}


class _Graph:
    def compile(self, *args, **kwargs):
        return object()


class _GraphFactory:
    def __init__(self, raises: BaseException | None = None):
        self.raises = raises
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        return _Graph()


def _install(monkeypatch, *outcomes, graph_raises=None) -> tuple[_Driver, _GraphFactory]:
    from tools import run_requirements_workflow as tool

    driver = _Driver(*outcomes)
    factory = _GraphFactory(graph_raises)
    monkeypatch.setattr(tool, "invoke_with_budget", driver)
    monkeypatch.setattr(tool, "create_requirements_graph", factory)
    return driver, factory


ISSUE_FILED = {"issue_url": ISSUE_URL}


def _lld_saved(target: Path) -> dict:
    return {"final_lld_path": str(target / LLD_ACTIVE_DIR / "LLD-042.md"),
            "lld_status": "APPROVED"}


def _main(*argv: str) -> int:
    from tools import run_requirements_workflow as tool

    with patch("sys.argv", ["prog", *argv]):
        try:
            return tool.main()
        except SystemExit as exc:
            return exc.code


def _brief(target: Path, name: str = "feature.md", text: str = "# Feature\n") -> Path:
    ideas = target / "ideas" / "active"
    ideas.mkdir(parents=True, exist_ok=True)
    path = ideas / name
    path.write_text(text, encoding="utf-8")
    return path


def _lineage(target: Path, *files: str) -> Path:
    lineage = target / AUDIT_ACTIVE_DIR / "42-lld"
    lineage.mkdir(parents=True, exist_ok=True)
    for name in files:
        (lineage / name).write_text(f"# Issue #42: A title\n\n{name}\n", encoding="utf-8")
    return lineage


def _driver_configured(tmp_path, monkeypatch) -> None:
    driver = tmp_path / "tracked_pr_land.py"
    driver.write_text("", encoding="utf-8")
    monkeypatch.setenv("AZ_MERGE_DRIVER", str(driver))


def _stub(monkeypatch, match, *, result=None, raises=None) -> list[list[str]]:
    """Replace subprocess.run for argvs `match` accepts; the rest run for real."""
    real = subprocess.run
    seen: list[list[str]] = []

    def run(argv, *args, **kwargs):
        if match(list(argv)):
            seen.append(list(argv))
            if raises is not None:
                raise raises
            return result
        return real(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    return seen


def _is_gh(argv: list[str]) -> bool:
    return argv[:1] == ["gh"]


def _completed(rc: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["gh"], rc, stdout=stdout, stderr=stderr)


def _assert_failed(rc, capsys, operator_alerts, *needles: str) -> str:
    """Exit 1, an ERROR line on stderr, and one alert whose cause names it."""
    err = capsys.readouterr().err
    assert rc == 1, err
    assert "ERROR" in err
    assert len(operator_alerts) == 1, operator_alerts
    alert = operator_alerts[0]
    for needle in needles:
        assert needle in err, (needle, err)
        assert needle in alert["cause"], (needle, alert)
    assert alert["where"].startswith("tools/run_requirements_workflow.py")
    assert alert["consequence"]
    return err


# --- Helpers that returned a default in place of what their caller needed ----


class TestHelpersRaise:
    def test_4476_resume_says_it_runs_the_brief_again_from_the_start(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """T1: it printed "resuming..." and spent the whole run again."""
        _brief(target)
        audit = target / "docs" / "lineage" / "active" / "feature"
        audit.mkdir(parents=True)
        driver, _ = _install(monkeypatch, ISSUE_FILED)

        rc = _main("--type", "issue", "--resume", "feature.md", "--repo", str(target))

        out = capsys.readouterr().out
        assert rc == 0, out
        assert "resuming..." not in out
        assert "again from the start" in out
        assert str(audit) in out
        assert driver.calls
        assert not operator_alerts

    def test_4476_resume_never_opens_a_checkpoint_database(
        self, target, tmp_path, monkeypatch, capsys, operator_alerts,
    ):
        """T2: nothing writes that database, so it cannot stop a run."""
        db = tmp_path / "ckpt" / "wf.db"
        db.parent.mkdir(parents=True)
        db.write_bytes(b"this is not a sqlite database" * 64)
        _brief(target)
        (target / "docs" / "lineage" / "active" / "feature").mkdir(parents=True)
        _install(monkeypatch, ISSUE_FILED)

        rc = _main("--type", "issue", "--resume", "feature.md", "--repo", str(target))

        assert rc == 0, capsys.readouterr().err
        assert not operator_alerts

    def test_175_an_unreadable_brief_is_named(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It passed and titled the brief "(no title)"."""
        broken = target / "ideas" / "active" / "broken.md"
        broken.mkdir(parents=True)
        driver, _ = _install(monkeypatch, ISSUE_FILED)

        rc = _main("--type", "issue", "--all", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, str(broken))
        assert not driver.calls

    def test_175_a_brief_with_no_heading_is_untitled(self, tmp_path):
        from tools.run_requirements_workflow import extract_brief_title

        brief = tmp_path / "plain.md"
        brief.write_text("no heading here\n", encoding="utf-8")
        assert extract_brief_title(brief) == "(no title)"

    def test_192_select_with_no_ideas_directory_fails(
        self, target, capsys, operator_alerts,
    ):
        rc = _main("--type", "issue", "--select", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "ideas/active")

    def test_199_select_with_no_briefs_fails(self, target, capsys, operator_alerts):
        (target / "ideas" / "active").mkdir(parents=True)

        rc = _main("--type", "issue", "--select", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "no brief files")

    def test_259_select_when_gh_fails(self, target, monkeypatch, capsys, operator_alerts):
        _stub(monkeypatch, _is_gh, result=_completed(1, stderr="gh: not logged in"))

        rc = _main("--type", "lld", "--select", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "gh: not logged in")

    def test_264_select_when_gh_times_out(self, target, monkeypatch, capsys, operator_alerts):
        _stub(monkeypatch, _is_gh, raises=subprocess.TimeoutExpired("gh", 30))

        rc = _main("--type", "lld", "--select", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "timed out")

    def test_267_select_when_gh_is_missing(self, target, monkeypatch, capsys, operator_alerts):
        _stub(monkeypatch, _is_gh, raises=FileNotFoundError("gh"))

        rc = _main("--type", "lld", "--select", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "gh CLI not found")

    def test_270_select_when_gh_output_is_not_json(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _stub(monkeypatch, _is_gh, result=_completed(0, stdout="<html>login</html>"))

        rc = _main("--type", "lld", "--select", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "<html>login</html>")


class TestTheTargetRepository:
    def test_560_git_failing_on_the_briefs_repository_stops_the_run(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It passed and fell back to the working directory's repository."""
        brief = _brief(target)
        monkeypatch.chdir(target)
        driver, _ = _install(monkeypatch, ISSUE_FILED)
        _stub(
            monkeypatch,
            lambda a: a[:1] == ["git"] and "-C" in a and "--show-toplevel" in a,
            raises=subprocess.TimeoutExpired("git", 10),
        )

        rc = _main("--type", "issue", "--brief", str(brief), "--mock")

        _assert_failed(rc, capsys, operator_alerts, str(brief.parent), "timed out")
        assert not driver.calls

    def test_560_a_brief_outside_any_repository_falls_back_to_the_cwd(
        self, target, tmp_path, monkeypatch,
    ):
        """Documented priority (#115): not being in a repository is an answer."""
        from tools.run_requirements_workflow import parse_args, resolve_roots

        loose = tmp_path / "loose"
        loose.mkdir()
        brief = loose / "brief.md"
        brief.write_text("# Brief\n", encoding="utf-8")
        monkeypatch.chdir(target)

        _, resolved = resolve_roots(parse_args(["--type", "issue", "--brief", str(brief)]))

        assert resolved == target.resolve()

    def test_582_git_failing_in_the_cwd_stops_the_run(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It passed and used Path.cwd(), which may be no repository at all."""
        monkeypatch.chdir(target)
        driver, _ = _install(monkeypatch, _lld_saved(target))
        _stub(
            monkeypatch,
            lambda a: a[:1] == ["git"] and "-C" not in a and "--show-toplevel" in a,
            raises=FileNotFoundError("git"),
        )

        rc = _main("--type", "lld", "--issue", "42", "--mock", "--base-branch", "main")

        _assert_failed(rc, capsys, operator_alerts, "git")
        assert not driver.calls

    def test_585_a_cwd_outside_any_repository_stops_the_run(
        self, target, tmp_path, monkeypatch, capsys, operator_alerts,
    ):
        """It silently made the working directory the target repository."""
        nowhere = tmp_path / "nowhere"
        nowhere.mkdir()
        monkeypatch.chdir(nowhere)
        driver, _ = _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--issue", "42", "--mock", "--base-branch", "main")

        _assert_failed(rc, capsys, operator_alerts, "not a git repository")
        assert not driver.calls
        assert not (nowhere / "data").exists()

    def test_633_the_assemblyzero_root_as_target_alerts(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed to stderr and exited 1 with no alert."""
        monkeypatch.setenv("ASSEMBLYZERO_ROOT", str(target))
        driver, _ = _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--issue", "42", "--mock", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "AssemblyZero root")
        assert not driver.calls


# --- The run itself -----------------------------------------------------------


class TestTheRun:
    def test_931_a_workflow_exception_alerts_with_its_type_and_traceback(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed the message on stdout, a traceback only with --debug,
        returned 1 and alerted no one."""
        _install(monkeypatch, RuntimeError("graph exploded"))

        rc = _main("--type", "lld", "--issue", "42", "--mock", "--repo", str(target))

        err = _assert_failed(rc, capsys, operator_alerts, "RuntimeError: graph exploded")
        assert "Traceback" in err
        events = list((target / "data" / "speedrun" / "runs").glob("lld-issue42-*-events.log"))
        assert len(events) == 1
        assert "crash type=RuntimeError" in events[0].read_text(encoding="utf-8")

    def test_1541_a_workflow_error_goes_to_stderr_and_halt_is_not_alerted_twice(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed the error on stdout only. The HALT node alerted for it
        (it sets recovery_plan_path), so the tool does not alert again."""
        _install(monkeypatch, {"error_message": "N1 drafter failed",
                               "recovery_plan_path": "/state/plan.md"})

        rc = _main("--type", "lld", "--issue", "42", "--mock", "--repo", str(target))

        err = capsys.readouterr().err
        assert rc == 1
        assert "N1 drafter failed" in err
        assert operator_alerts == []

    def test_1541_an_error_that_bypassed_halt_alerts_here(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """An exhausted step budget ends with error_message and no HALT."""
        _install(monkeypatch, {"error_message": "[BUDGET] step budget exhausted in N3"})

        rc = _main("--type", "lld", "--issue", "42", "--mock", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "step budget exhausted in N3")

    def test_1551_an_issue_run_that_filed_nothing_fails(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        brief = _brief(target)
        _install(monkeypatch, {"issue_url": ""})

        rc = _main("--type", "issue", "--brief", str(brief), "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "without filing an issue")

    def test_1551_manual_handling_at_a_gate_files_nothing_and_succeeds(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """The operator chose manual handling (the gate sets next_node END)."""
        brief = _brief(target)
        _install(monkeypatch, {"issue_url": "", "next_node": "END"})

        rc = _main("--type", "issue", "--brief", str(brief), "--repo", str(target), "--mock")

        assert rc == 0, capsys.readouterr().err
        assert operator_alerts == []

    def test_1558_an_lld_run_that_saved_nothing_fails(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _install(monkeypatch, {"final_lld_path": ""})

        rc = _main("--type", "lld", "--issue", "42", "--mock", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "without saving an LLD")

    def test_1558_manual_handling_at_a_gate_saves_nothing_and_succeeds(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _install(monkeypatch, {"final_lld_path": "", "next_node": "END"})

        rc = _main("--type", "lld", "--issue", "42", "--mock", "--repo", str(target))

        assert rc == 0, capsys.readouterr().err
        assert operator_alerts == []

    def test_a_saved_lld_succeeds_without_an_alert(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--issue", "42", "--mock", "--repo", str(target))

        assert rc == 0, capsys.readouterr().err
        assert operator_alerts == []

    def test_1698_an_exception_outside_the_graph_alerts(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """build_initial_state's refusal of a work branch escaped main as a
        bare traceback with no alert."""
        driver, _ = _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--issue", "42", "--mock", "--repo", str(target),
                   "--base-branch", "42-lld")

        err = _assert_failed(rc, capsys, operator_alerts, "GitBranchError", "42-lld")
        assert "Traceback" in err
        assert not driver.calls


# --- Resume at review (--resume-review) ---------------------------------------


class TestResumeReview:
    def test_967_resume_review_without_a_draft_alerts(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        driver, _ = _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--issue", "42", "--resume-review",
                   "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "no resumable draft")
        assert not driver.calls

    def test_991_resume_review_without_the_issue_file_refuses(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It ran the review without the issue's body or title."""
        _lineage(target, "002-draft.md")
        driver, _ = _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--issue", "42", "--resume-review",
                   "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "001-issue.md")
        assert not driver.calls

    def test_1175_a_resume_review_exception_alerts_with_its_traceback(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _lineage(target, "001-issue.md", "002-draft.md")
        _install(monkeypatch, _lld_saved(target), graph_raises=RuntimeError("review exploded"))

        rc = _main("--type", "lld", "--issue", "42", "--resume-review",
                   "--repo", str(target), "--mock")

        err = _assert_failed(rc, capsys, operator_alerts, "RuntimeError: review exploded")
        assert "Traceback" in err

    def test_a_resume_review_that_saves_the_lld_succeeds(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _lineage(target, "001-issue.md", "002-draft.md")
        driver, _ = _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--issue", "42", "--resume-review",
                   "--repo", str(target), "--mock")

        assert rc == 0, capsys.readouterr().err
        assert operator_alerts == []
        assert driver.calls[0]["issue_title"] == "A title"


# --- The batch (--all) and resume (--resume) ----------------------------------


class TestBatchAndResume:
    def test_1203_all_without_an_ideas_directory_fails(
        self, target, capsys, operator_alerts,
    ):
        rc = _main("--type", "issue", "--all", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "ideas/active")

    def test_1203_all_with_an_empty_ideas_directory_has_nothing_to_do(
        self, target, capsys, operator_alerts,
    ):
        """Zero briefs is the whole batch done, not a failure."""
        (target / "ideas" / "active").mkdir(parents=True)

        rc = _main("--type", "issue", "--all", "--repo", str(target))

        assert rc == 0
        assert operator_alerts == []

    def test_1241_a_brief_that_raises_stops_the_batch_and_alerts(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed FAILED on stdout, went on to the next brief, and exited 1
        at the end with no alert."""
        _brief(target, "a.md")
        _brief(target, "b.md")
        driver, _ = _install(monkeypatch, RuntimeError("a exploded"), ISSUE_FILED)

        rc = _main("--type", "issue", "--all", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "RuntimeError: a exploded")
        assert len(driver.calls) == 1
        assert "a.md" in operator_alerts[0]["where"]

    def test_1241_a_brief_that_halted_stops_the_batch_without_a_second_alert(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _brief(target, "a.md")
        _brief(target, "b.md")
        driver, _ = _install(
            monkeypatch,
            {"error_message": "N3 review failed", "recovery_plan_path": "/state/plan.md"},
            ISSUE_FILED,
        )

        rc = _main("--type", "issue", "--all", "--repo", str(target), "--mock")

        err = capsys.readouterr().err
        assert rc == 1
        assert "N3 review failed" in err
        assert len(driver.calls) == 1
        assert operator_alerts == []

    def test_a_batch_whose_briefs_all_file_succeeds(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _brief(target, "a.md")
        _brief(target, "b.md")
        driver, _ = _install(monkeypatch, ISSUE_FILED)

        rc = _main("--type", "issue", "--all", "--repo", str(target), "--mock")

        assert rc == 0, capsys.readouterr().err
        assert len(driver.calls) == 2
        assert operator_alerts == []

    def test_1291_resume_with_nothing_to_resume_refuses(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed a WARNING and started a fresh workflow."""
        _brief(target)
        driver, _ = _install(monkeypatch, ISSUE_FILED)

        rc = _main("--type", "issue", "--resume", "feature.md", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "nothing to resume")
        assert not driver.calls

    def test_1306_resume_of_a_missing_brief_with_nothing_to_resume_alerts(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        driver, _ = _install(monkeypatch, ISSUE_FILED)

        rc = _main("--type", "issue", "--resume", "gone.md", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "gone.md")
        assert not driver.calls

    def test_1330_resume_of_a_missing_brief_alerts(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        (target / AUDIT_ACTIVE_DIR / generate_slug("gone.md")).mkdir(parents=True)
        driver, _ = _install(monkeypatch, ISSUE_FILED)

        rc = _main("--type", "issue", "--resume", "gone.md", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "gone.md")
        assert not driver.calls

    def test_a_resume_with_an_audit_directory_runs(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _brief(target)
        (target / AUDIT_ACTIVE_DIR / generate_slug("feature.md")).mkdir(parents=True)
        driver, _ = _install(monkeypatch, ISSUE_FILED)

        rc = _main("--type", "issue", "--resume", "feature.md", "--repo", str(target), "--mock")

        assert rc == 0, capsys.readouterr().err
        assert len(driver.calls) == 1
        assert operator_alerts == []


# --- The pre-generation check on a real LLD run -------------------------------


class TestThePreGenerationCheck:
    def test_1446_a_resumable_draft_without_yes_fails_naming_the_choice(
        self, target, tmp_path, monkeypatch, capsys, operator_alerts,
    ):
        """It returned False, and main exited 0 as "User aborted" with nothing
        generated."""
        _driver_configured(tmp_path, monkeypatch)
        _lineage(target, "001-issue.md", "002-draft.md")
        driver, _ = _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--issue", "42", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "--resume-review", "--yes")
        assert not driver.calls

    def test_1687_a_missing_merge_driver_alerts(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed the reason on stdout and returned 1 with no alert."""
        driver, _ = _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--issue", "42", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "AZ_MERGE_DRIVER is not set")
        assert not driver.calls

    def test_1690_a_resumable_draft_no_longer_exits_zero(
        self, target, tmp_path, monkeypatch, capsys, operator_alerts,
    ):
        _driver_configured(tmp_path, monkeypatch)
        _lineage(target, "001-issue.md", "002-draft.md")
        _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--issue", "42", "--repo", str(target))

        assert rc == 1
        assert len(operator_alerts) == 1

    def test_1690_answering_the_prompt_with_anything_but_yes_is_a_deliberate_abort(
        self, target, tmp_path, monkeypatch, capsys, operator_alerts,
    ):
        """The operator declined the regeneration: nothing failed."""
        _driver_configured(tmp_path, monkeypatch)
        lld = target / LLD_ACTIVE_DIR / "LLD-042.md"
        lld.parent.mkdir(parents=True)
        lld.write_text("# LLD\n", encoding="utf-8")
        driver, _ = _install(monkeypatch, _lld_saved(target))
        monkeypatch.setattr("builtins.input", lambda *_a: "no")

        rc = _main("--type", "lld", "--issue", "42", "--repo", str(target))

        assert rc == 0
        assert operator_alerts == []
        assert not driver.calls


# --- Bad arguments --------------------------------------------------------------


class TestBadArguments:
    """Each printed on stdout and returned 1 with no alert."""

    def test_1612_bad_arguments(self, monkeypatch, capsys, operator_alerts):
        _install(monkeypatch, ISSUE_FILED)
        _assert_failed(_main("--type", "lld", "--all"), capsys, operator_alerts,
                       "--all is only supported")

    def test_1616_bad_arguments(self, monkeypatch, capsys, operator_alerts):
        _install(monkeypatch, ISSUE_FILED)
        _assert_failed(_main("--type", "lld", "--resume", "x.md"), capsys, operator_alerts,
                       "--resume is only supported")

    def test_1621_bad_arguments(self, monkeypatch, capsys, operator_alerts):
        _install(monkeypatch, ISSUE_FILED)
        _assert_failed(_main("--type", "issue", "--resume-review"), capsys, operator_alerts,
                       "--resume-review is only supported")

    def test_1625_bad_arguments(self, monkeypatch, capsys, operator_alerts):
        _install(monkeypatch, ISSUE_FILED)
        _assert_failed(_main("--type", "lld", "--resume-review"), capsys, operator_alerts,
                       "--resume-review requires --issue")

    def test_1630_bad_arguments(self, monkeypatch, capsys, operator_alerts):
        _install(monkeypatch, ISSUE_FILED)
        _assert_failed(_main("--type", "issue"), capsys, operator_alerts,
                       "--brief, --select, --all, or --resume required")

    def test_1634_bad_arguments(self, monkeypatch, capsys, operator_alerts):
        _install(monkeypatch, ISSUE_FILED)
        _assert_failed(_main("--type", "lld"), capsys, operator_alerts,
                       "--issue or --select required")


# --- Interactive selection: a failure is not a cancel ---------------------------


class TestSelection:
    def test_1662_a_failed_brief_selection_exits_non_zero(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed "Selection cancelled." and exited 0."""
        driver, _ = _install(monkeypatch, ISSUE_FILED)

        rc = _main("--type", "issue", "--select", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "ideas/active")
        assert "Selection cancelled" not in capsys.readouterr().out
        assert not driver.calls

    def test_1662_quitting_the_brief_menu_is_a_cancel(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _brief(target)
        driver, _ = _install(monkeypatch, ISSUE_FILED)
        monkeypatch.setattr("builtins.input", lambda *_a: "q")

        rc = _main("--type", "issue", "--select", "--repo", str(target))

        assert rc == 0
        assert "Selection cancelled." in capsys.readouterr().out
        assert operator_alerts == []
        assert not driver.calls

    def test_1668_a_failed_issue_selection_exits_non_zero(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _stub(monkeypatch, _is_gh, result=_completed(1, stderr="HTTP 502"))
        driver, _ = _install(monkeypatch, _lld_saved(target))

        rc = _main("--type", "lld", "--select", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "HTTP 502")
        assert not driver.calls

    def test_1668_no_open_issues_is_not_a_cancel(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed "Selection cancelled." for an empty issue list too."""
        _stub(monkeypatch, _is_gh, result=_completed(0, stdout="[]"))

        rc = _main("--type", "lld", "--select", "--repo", str(target))

        _assert_failed(rc, capsys, operator_alerts, "no open issues")

    def test_1668_quitting_the_issue_menu_is_a_cancel(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        issues = [{"number": 42, "title": "One", "labels": []}]
        _stub(monkeypatch, _is_gh, result=_completed(0, stdout=json.dumps(issues)))
        driver, _ = _install(monkeypatch, _lld_saved(target))
        monkeypatch.setattr("builtins.input", lambda *_a: "q")

        rc = _main("--type", "lld", "--select", "--repo", str(target))

        assert rc == 0
        assert "Selection cancelled." in capsys.readouterr().out
        assert operator_alerts == []
        assert not driver.calls


# --- The tag convention is gone -------------------------------------------------


def test_the_module_carries_no_fail_open_tag():
    import io
    import tokenize

    tool = Path(__file__).resolve().parents[2] / "tools" / "run_requirements_workflow.py"
    source = tool.read_text(encoding="utf-8")
    tags = [
        tok.string for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT and "fail-open:" in tok.string
    ]
    assert tags == []

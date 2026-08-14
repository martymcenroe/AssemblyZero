"""A successful roll archives and verifies itself (#2353).

Operator, 2026-08-14, reading "Next step: archive the run": "why am I being
the monkey here anyway. the roll succeeded. why isn't the archive step
automatic?" There was no good answer. The archive tool is deterministic,
exit-coded, and only ever writes, and the launcher already knew the roll had
succeeded, because it had just printed the instruction.

The synthetic run is built the same way `test_speedrun_archive.py` builds
its own: a real git repository in a temp dir, never live campaign state.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402

RUN = "hardening-run-test"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result


def _events(log_dir: Path, tag: str, issue: int, base: str) -> None:
    lines = [
        f"2026-08-14 01:00:00 START issue=#{issue} repo=C:\\repo pid=1234",
        f"2026-08-14 01:00:02 BASE '{base}' verified clean for #{issue}",
        f"2026-08-14 01:00:02 LAUNCH base={base} -> {tag}.log",
        "2026-08-14 01:07:36 CHILD EXITED rc=0",
        "2026-08-14 01:07:36 EXIT rc=0",
    ]
    (log_dir / f"{tag}-events.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (log_dir / f"{tag}.log").write_text(f"stdout for {tag}\n", encoding="utf-8")
    (log_dir / f"{tag}-heartbeat.log").write_text("alive\n", encoding="utf-8")


@pytest.fixture
def succeeded_run(tmp_path: Path, monkeypatch) -> Path:
    """A repo in the state a roll leaves behind when it succeeds."""
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")

    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")

    _git(repo, "checkout", "-q", "-b", RUN)
    (repo / "feature.py").write_text("value = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "arc work")

    _git(repo, "checkout", "-q", "-b", f"graveyard/{RUN}-attempt1")
    (repo / "abandoned.py").write_text("nope = True\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "abandoned attempt")
    _git(repo, "checkout", "-q", RUN)

    log_dir = repo / "data" / "speedrun" / "runs"
    log_dir.mkdir(parents=True)
    _events(log_dir, "run-issue1-010000", 1, RUN)
    _events(log_dir, "run-issue4-020000", 4, RUN)

    # There is no origin in a temp repo, so the launcher's ref-based lookup
    # has nothing to read. The run's identity is not what this test is about.
    monkeypatch.setattr(sr, "resolve_attempt_branch", lambda _root: RUN)
    return repo


class TestArchiveOnSuccess:
    def test_it_archives_with_no_operator_action(self, succeeded_run):
        lines = sr._archive_successful_run(succeeded_run)
        text = "\n".join(lines)

        assert "Archive:" in text
        archive = succeeded_run / "data" / "speedrun" / "archives" / RUN
        assert archive.is_dir()
        assert (archive / "index.json").is_file()

    def test_the_verdict_carries_every_number_the_issue_named(self, succeeded_run):
        """Archive path, rolls captured, branches bundled, complete, manifest."""
        text = "\n".join(sr._archive_successful_run(succeeded_run))

        assert "Archive:" in text
        assert "rolls 2" in text
        assert "1 integration + 1 graveyard" in text
        assert "complete yes" in text
        assert "manifest OK" in text

    def test_it_verifies_what_it_just_wrote(self, succeeded_run):
        """--verify is run, not merely offered. Audits are programs."""
        from assemblyzero.speedrun.archive import verify_manifest

        sr._archive_successful_run(succeeded_run)
        archive = succeeded_run / "data" / "speedrun" / "archives" / RUN

        assert verify_manifest(archive) == []
        assert "manifest OK" in "\n".join(sr._archive_successful_run(succeeded_run))

    def test_a_corrupted_archive_is_reported_not_hidden(self, succeeded_run):
        sr._archive_successful_run(succeeded_run)
        archive = succeeded_run / "data" / "speedrun" / "archives" / RUN

        target = next(p for p in (archive / "logs").glob("*.log"))
        target.write_text("tampered\n", encoding="utf-8")

        # Re-verify the existing archive rather than re-archiving over it.
        from assemblyzero.speedrun.archive import verify_manifest

        assert verify_manifest(archive) != []


class TestArchiveFailureDoesNotAlterTheVerdict:
    def test_a_failure_is_named_and_loud(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sr, "resolve_attempt_branch", lambda _root: RUN)

        def boom(*_args, **_kwargs):
            raise RuntimeError("disk full")

        monkeypatch.setattr(sr, "archive_run", boom)

        lines = sr._archive_successful_run(tmp_path)
        text = "\n".join(lines)

        assert "ARCHIVE FAILED" in text
        assert "disk full" in text
        assert "The roll still succeeded" in text
        assert "runbook 0952" in text

    def test_it_never_raises(self, tmp_path, monkeypatch):
        """The verdict must render even when everything below it is broken.

        A roll that succeeded and then lost its summary to an archiver
        traceback would be worse than the manual step this replaces.
        """
        monkeypatch.setattr(sr, "resolve_attempt_branch", lambda _root: RUN)
        monkeypatch.setattr(
            sr, "archive_run", lambda *a, **k: (_ for _ in ()).throw(OSError("x"))
        )
        assert sr._archive_successful_run(tmp_path)

    def test_an_unresolvable_run_name_says_so(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sr, "resolve_attempt_branch", lambda _root: "")

        text = "\n".join(sr._archive_successful_run(tmp_path))

        assert "ARCHIVE SKIPPED" in text
        assert "no attempt branch" in text
        assert "runbook 0952" in text


class TestTheVerdictBlock:
    def test_success_no_longer_tells_the_operator_to_archive(self, succeeded_run):
        """The instruction this issue exists to delete."""
        import inspect

        source = inspect.getsource(sr._render_verdict)
        assert "Next step: archive the run" not in source
        assert "_archive_successful_run" in source

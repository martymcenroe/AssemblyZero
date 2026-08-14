"""`--verify` answers both dimensions of trustworthy (#2354).

It used to re-hash the manifest and return 0 on intact hashes, never reading
`complete`. An archive marked incomplete at archive time -- a named component
that could not be read -- passed with "manifest OK" as long as the files it
DID capture hashed correctly.

That is the vacuous-pass class. The one command whose name promises "this
archive is trustworthy" was answering only "the files I did capture have not
rotted", and completeness lived only in the archive-time exit code, which is
gone by the time anyone re-verifies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_archive as cli  # noqa: E402

from assemblyzero.speedrun.archive import (  # noqa: E402
    INDEX_NAME,
    verify_archive,
    verify_manifest,
)


def _write_archive(root: Path, *, complete: bool, missing: list[str] | None = None) -> Path:
    """A minimal archive: one captured file, plus an index describing it."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    captured = root / "logs" / "run-events.log"
    captured.write_text("EXIT rc=0\n", encoding="utf-8")

    import hashlib

    digest = hashlib.sha256(captured.read_bytes()).hexdigest()
    index = {
        "index_version": 1,
        "run": "hardening-run-test",
        "complete": complete,
        "incomplete_components": [
            {"name": n, "ok": False, "detail": "could not be read"}
            for n in (missing or [])
        ],
        "manifest": {"logs/run-events.log": digest},
    }
    (root / INDEX_NAME).write_text(json.dumps(index, indent=2), encoding="utf-8")
    return root


@pytest.fixture
def complete_archive(tmp_path: Path) -> Path:
    return _write_archive(tmp_path / "complete", complete=True)


@pytest.fixture
def incomplete_archive(tmp_path: Path) -> Path:
    """Hash-intact, and marked incomplete. The case that used to pass."""
    return _write_archive(
        tmp_path / "incomplete", complete=False, missing=["bundle", "orphans/wt.tar"]
    )


class TestTheVacuousPass:
    def test_an_incomplete_hash_intact_archive_fails(self, incomplete_archive):
        result = verify_archive(incomplete_archive)

        assert result.complete is False
        assert result.mismatched == []
        assert result.ok is False

    def test_it_names_the_missing_components(self, incomplete_archive):
        result = verify_archive(incomplete_archive)
        assert result.missing == ["bundle", "orphans/wt.tar"]

    def test_the_cli_exits_nonzero_and_names_them(self, incomplete_archive, capsys):
        code = cli.main(["--verify", str(incomplete_archive)])
        out = capsys.readouterr().out

        assert code == 1
        assert "complete  NO" in out
        assert "bundle" in out
        assert "orphans/wt.tar" in out
        assert "does not authorize deleting anything" in out

    def test_the_old_check_alone_would_still_have_passed_it(self, incomplete_archive):
        """The measurement behind the issue, pinned.

        `verify_manifest` is unchanged and still reports the narrower fact.
        This asserts the two answers genuinely differ on this fixture, so a
        future refactor cannot quietly collapse them back into one.
        """
        assert verify_manifest(incomplete_archive) == []
        assert verify_archive(incomplete_archive).ok is False


class TestHashesStillChecked:
    def test_a_complete_archive_passes(self, complete_archive, capsys):
        code = cli.main(["--verify", str(complete_archive)])
        out = capsys.readouterr().out

        assert code == 0
        assert "complete  yes" in out
        assert "manifest  OK" in out

    def test_a_complete_archive_with_a_corrupted_file_still_fails(
        self, complete_archive, capsys
    ):
        (complete_archive / "logs" / "run-events.log").write_text(
            "tampered\n", encoding="utf-8"
        )
        code = cli.main(["--verify", str(complete_archive)])
        out = capsys.readouterr().out

        assert code == 1
        assert "complete  yes" in out
        assert "manifest  MISMATCH" in out
        assert "logs/run-events.log" in out

    def test_a_missing_file_counts_as_a_mismatch(self, complete_archive):
        (complete_archive / "logs" / "run-events.log").unlink()
        assert verify_archive(complete_archive).mismatched == ["logs/run-events.log"]

    def test_both_dimensions_report_together(self, tmp_path, capsys):
        """Incomplete AND corrupted. One exit code, two findings."""
        archive = _write_archive(tmp_path / "both", complete=False, missing=["bundle"])
        (archive / "logs" / "run-events.log").write_text("x\n", encoding="utf-8")

        code = cli.main(["--verify", str(archive)])
        out = capsys.readouterr().out

        assert code == 1
        assert "complete  NO" in out
        assert "manifest  MISMATCH" in out


class TestUnreadableIndex:
    def test_a_missing_index_cannot_be_a_pass(self, tmp_path):
        """An archive that cannot state anything about itself is not sound.

        Reporting it as verified would be the same vacuous answer one level
        up from the one this issue removed.
        """
        empty = tmp_path / "no-index"
        empty.mkdir()

        result = verify_archive(empty)
        assert result.ok is False
        assert INDEX_NAME in result.error

    def test_the_cli_says_so_and_exits_nonzero(self, tmp_path, capsys):
        empty = tmp_path / "no-index2"
        empty.mkdir()

        code = cli.main(["--verify", str(empty)])
        assert code == 1
        assert "CANNOT VERIFY" in capsys.readouterr().out

    def test_incomplete_with_no_recorded_detail_still_names_the_gap(self, tmp_path):
        """`complete: false` and an empty component list is still a failure."""
        archive = _write_archive(tmp_path / "bare", complete=False, missing=[])
        result = verify_archive(archive)

        assert result.ok is False
        assert result.missing, "a failure with no named cause is not a report"

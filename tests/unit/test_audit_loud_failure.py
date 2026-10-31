"""audit.py under standard 0034, one test per sweep site (#3771).

``ReviewAuditLog.tail`` merges the review history with the active shards. A
line that was not JSON, and a file that could not be read, used to be
skipped, so the log came back shorter and read as the whole of it. Each now
raises, naming the file and the line. An absent file is still no entries.
Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from assemblyzero.core.audit import ReviewAuditLog, create_log_entry


def _entry(issue: int) -> dict:
    return create_log_entry(
        node="review_lld", model="m", model_verified="m", issue_id=issue,
        verdict="APPROVED", critique="", tier_1_issues=[], raw_response="",
        duration_ms=0, credential_used="", rotation_occurred=False, attempts=1,
    )


def _log(tmp_path: Path) -> ReviewAuditLog:
    return ReviewAuditLog(repo_root=tmp_path, session_id="abcd1234")


def _write(path: Path, *lines: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return path


class TestRepoRoot:
    def test_130_a_git_that_times_out_raises_with_its_cause(self, monkeypatch):
        def run(cmd, *args, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 10)

        monkeypatch.setattr(subprocess, "run", run)

        with pytest.raises(RuntimeError, match="git rev-parse --show-toplevel") as raised:
            ReviewAuditLog()
        assert isinstance(raised.value.__cause__, subprocess.TimeoutExpired)
        assert "10" in str(raised.value)


class TestTheHistory:
    def test_238_a_history_line_that_is_not_json_raises(self, tmp_path):
        log = _log(tmp_path)
        history = _write(
            log.history_file, json.dumps(_entry(1)), "{not json", json.dumps(_entry(3)),
        )

        with pytest.raises(ValueError, match="line 2") as raised:
            log.tail(10)
        assert str(history) in str(raised.value)
        assert "not JSON" in str(raised.value)

    def test_238_the_line_number_counts_from_the_top_of_the_file(self, tmp_path):
        """tail reads only the end of the history; the line it names is the
        file's own line, not its place in the slice."""
        log = _log(tmp_path)
        good = [json.dumps(_entry(i)) for i in range(5)]
        _write(log.history_file, *good, "{not json")

        with pytest.raises(ValueError, match="line 6"):
            log.tail(1)

    def test_242_a_history_that_cannot_be_read_raises(self, tmp_path):
        log = _log(tmp_path)
        log.history_file.mkdir()  # exists, and open() fails on it

        with pytest.raises(OSError) as raised:
            log.tail(10)
        assert str(log.history_file) in str(raised.value)


class TestTheShards:
    def test_267_a_shard_line_that_is_not_json_raises(self, tmp_path):
        log = _log(tmp_path)
        log.log(_entry(1))
        bad = _write(log.active_dir / "bad_shard.jsonl", "not valid json")

        with pytest.raises(ValueError, match="line 1") as raised:
            log.tail(10)
        assert str(bad) in str(raised.value)

    def test_267_a_shard_line_that_is_not_an_object_raises(self, tmp_path):
        log = _log(tmp_path)
        _write(log.active_dir / "list_shard.jsonl", "[1, 2]")

        with pytest.raises(ValueError, match="not an entry"):
            log.tail(10)

    def test_267_counting_the_log_raises_on_a_bad_history_line(self, tmp_path):
        """count() and iteration read the history whole, through the shard
        reader; a bad line there raises too."""
        log = _log(tmp_path)
        _write(log.history_file, json.dumps(_entry(1)), "{not json")

        with pytest.raises(ValueError, match="line 2"):
            log.count()

    def test_270_a_shard_that_cannot_be_read_raises(self, tmp_path):
        log = _log(tmp_path)
        log.log(_entry(1))
        (log.active_dir / "a_directory.jsonl").mkdir()

        with pytest.raises(OSError) as raised:
            log.tail(10)
        assert "a_directory.jsonl" in str(raised.value)

    def test_270_a_shard_removed_after_it_was_listed_raises(self, tmp_path, monkeypatch):
        """The consolidator moves a shard into the history and deletes it. One
        it deletes between tail's listing and its read has entries in neither
        what tail read, so it is not "no entries"."""
        log = _log(tmp_path)
        log.log(_entry(1))
        gone = log.active_dir / "consolidated_meanwhile.jsonl"
        real = Path.glob

        def glob(self, pattern):
            found = list(real(self, pattern))
            return found + [gone] if self == log.active_dir else found

        monkeypatch.setattr(Path, "glob", glob)

        with pytest.raises(FileNotFoundError, match="consolidated_meanwhile"):
            log.tail(10)


class TestWhatIsKept:
    def test_an_empty_log_is_no_entries_and_quiet(self, tmp_path, capsys):
        """Kept: no history and no shards is a log nobody has written to."""
        assert _log(tmp_path).tail(10) == []
        assert capsys.readouterr().err == ""

    def test_a_clean_log_reads_whole(self, tmp_path):
        log = _log(tmp_path)
        _write(log.history_file, json.dumps(_entry(1)))
        log.log(_entry(2))

        assert [e["issue_id"] for e in log.tail(10)] == [1, 2]
        assert log.count() == 2

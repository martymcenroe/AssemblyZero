"""The preserved-branch ledger fails loudly (ADR 0236, #3585).

The archiver bundles every branch this ledger names. A write that failed
returned False, which both writers ignored, so the archiver could miss a
branch; a ledger that existed but could not be read, a corrupt line, and a
record with no branch each read as fewer preservations. Now a write that
fails raises naming the ledger (both writers alert), and the reader alerts
and raises.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import pytest

from assemblyzero.speedrun.preserved import ledger_path, read_ledger, record_preserved


def _block_the_ledger(repo):
    """A file where the ledger's directory must be, so every write fails."""
    (repo / "data").write_text("not a directory\n", encoding="utf-8")
    return ledger_path(repo)


def test_97_a_ledger_write_that_fails_raises_naming_the_ledger(tmp_path):
    ledger = _block_the_ledger(tmp_path)

    with pytest.raises(OSError) as raised:
        record_preserved(tmp_path, "graveyard/issue-7-20260814", source="sweep")

    assert str(ledger) in str(raised.value)


def test_97_a_record_with_no_branch_raises(tmp_path):
    with pytest.raises(ValueError):
        record_preserved(tmp_path, "")
    assert not ledger_path(tmp_path).exists()


def test_97_a_written_record_returns_true(tmp_path):
    assert record_preserved(tmp_path, "graveyard/a", run="r") is True
    assert [r.branch for r in read_ledger(tmp_path)] == ["graveyard/a"]


def test_115_an_absent_ledger_is_a_quiet_empty_answer(tmp_path, operator_alerts):
    assert read_ledger(tmp_path) == []
    assert operator_alerts == []


def test_115_a_ledger_that_exists_but_cannot_be_read_alerts_and_raises(
    tmp_path, operator_alerts
):
    path = ledger_path(tmp_path)
    path.mkdir(parents=True)  # a directory where the file must be

    with pytest.raises(OSError):
        read_ledger(tmp_path)

    assert len(operator_alerts) == 1
    assert str(path) in operator_alerts[0]["cause"]


def _ledger_with(repo, *lines: str):
    path = ledger_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def test_124_a_corrupt_line_alerts_and_raises_naming_it(tmp_path, operator_alerts):
    path = _ledger_with(tmp_path, '{"branch": "graveyard/good-1"}', "{not json")

    with pytest.raises(ValueError) as raised:
        read_ledger(tmp_path)

    assert f"{path}:2" in str(raised.value)
    assert len(operator_alerts) == 1
    assert f"{path}:2" in operator_alerts[0]["cause"]


def test_124_a_line_that_is_not_an_object_alerts_and_raises(tmp_path, operator_alerts):
    path = _ledger_with(tmp_path, '["graveyard/a"]')

    with pytest.raises(ValueError) as raised:
        read_ledger(tmp_path)

    assert f"{path}:1" in str(raised.value)
    assert len(operator_alerts) == 1


def test_127_a_record_with_no_branch_alerts_and_raises(tmp_path, operator_alerts):
    path = _ledger_with(tmp_path, '{"branch": "graveyard/a"}', '{"run": "r", "branch": ""}')

    with pytest.raises(ValueError) as raised:
        read_ledger(tmp_path)

    assert f"{path}:2" in str(raised.value)
    assert len(operator_alerts) == 1


def test_a_clean_ledger_reads_with_no_alert(tmp_path, operator_alerts):
    _ledger_with(tmp_path, '{"branch": "graveyard/a", "run": "r"}', "", '{"branch": "graveyard/b"}')

    assert [r.branch for r in read_ledger(tmp_path)] == ["graveyard/a", "graveyard/b"]
    assert operator_alerts == []

"""The factory report fails loudly instead of counting a short picture (ADR 0236, #3585).

The report exists to replace "whichever kill happened most recently" with
counts. Several of its readers quietly made those counts wrong: a record whose
timestamp could not be read was kept in every window and counted nowhere, a
run log that could not be stat'd was kept in every window and filed undated, a
run log that could not be read counted as a killed run, a halt bundle that was
corrupt or not an object was dropped from the halt count, and a path that could
not be resolved dropped a bundle as "not this repo's". Each now alerts the
operator and raises, so no report is printed on a short count.

The withdrawn ``# fail-open:`` tags are gone from every function that carried
one, and the shapes they excused that were legitimate stay, pinned here.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from assemblyzero.speedrun import factory_report as fr
from assemblyzero.speedrun.prompt_telemetry import telemetry_path


def _tag_free(func) -> bool:
    return "fail-open:" not in inspect.getsource(func)


def _runs(tmp_path: Path) -> Path:
    directory = fr.runs_dir(tmp_path)
    directory.mkdir(parents=True)
    return directory


# --- parse_since and _parse_ts ----------------------------------------------


def test_496_the_withdrawn_tag_is_gone_from_parse_since():
    assert _tag_free(fr.parse_since)


def test_496_an_unparseable_window_still_raises():
    with pytest.raises(ValueError, match="unparseable --since"):
        fr.parse_since("last tuesday")


def test_496_both_formats_still_parse():
    assert fr.parse_since("2026-08-27").isoformat() == "2026-08-27T00:00:00"
    assert fr.parse_since("2026-08-27 09:30:00").isoformat() == "2026-08-27T09:30:00"


#: The report's windows are naive local time, as parse_since builds them.
AUG_1 = fr.parse_since("2026-08-01")
AUG_27 = fr.parse_since("2026-08-27")


def test_511_the_withdrawn_tag_is_gone_from_parse_ts():
    assert _tag_free(fr._parse_ts)


# --- a record that cannot be placed in the window -----------------------------


def _prompt_failure_store(repo: Path, ts_local: str) -> None:
    path = telemetry_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"stage": "lld", "check": "mechanical", "fingerprint": "f", "ts_local": ts_local}
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_529_an_undatable_record_in_a_window_alerts_and_raises(
    tmp_path, operator_alerts, monkeypatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    _prompt_failure_store(tmp_path, "sometime last week")

    with pytest.raises(ValueError, match="sometime last week"):
        fr.build_report(tmp_path, since=AUG_27)

    assert len(operator_alerts) == 1
    assert "sometime last week" in operator_alerts[0]["cause"]


def test_529_with_no_window_a_record_needs_no_date(tmp_path, operator_alerts, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    _prompt_failure_store(tmp_path, "sometime last week")

    report = fr.build_report(tmp_path, since=None)

    assert report is not None
    assert operator_alerts == []


# --- run logs ---------------------------------------------------------------


def test_630_a_run_log_that_cannot_be_stat_ed_alerts_and_raises(
    tmp_path, operator_alerts, monkeypatch
):
    log = _runs(tmp_path) / "run-issue4-111608.log"
    log.write_text("[STAGE] lld running 60s (nominal ~300s)\n", encoding="utf-8")
    real_stat = Path.stat

    def stat(self, *args, **kwargs):
        if self == log:
            raise PermissionError(13, "Permission denied", str(self))
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)

    with pytest.raises(OSError):
        fr.scan_run_log(log)

    assert len(operator_alerts) == 1
    assert str(log) in operator_alerts[0]["cause"]


def test_631_the_withdrawn_tags_are_gone_from_scan_run_log():
    assert _tag_free(fr.scan_run_log)


def test_646_a_run_log_that_cannot_be_read_alerts_and_raises(tmp_path, operator_alerts):
    log = _runs(tmp_path) / "run-issue4-111608.log"
    log.mkdir()  # a directory where the log must be: stat works, read does not

    with pytest.raises(OSError):
        fr.scan_run_log(log)

    assert len(operator_alerts) == 1
    assert str(log) in operator_alerts[0]["cause"]


def test_646_the_report_does_not_count_an_unreadable_log_as_killed(
    tmp_path, operator_alerts
):
    (_runs(tmp_path) / "run-issue4-111608.log").mkdir()

    with pytest.raises(OSError):
        fr.scan_run_logs(tmp_path)

    assert len(operator_alerts) == 1


def test_647_the_field_that_carried_the_swallowed_read_is_gone():
    assert "unreadable" not in {f.name for f in fr.RunLogFacts.__dataclass_fields__.values()}


def test_764_the_withdrawn_tag_is_gone_from_scan_run_logs():
    assert _tag_free(fr.scan_run_logs)


def test_764_a_repo_that_was_never_rolled_has_no_runs(tmp_path, operator_alerts):
    assert fr.scan_run_logs(tmp_path) == []
    assert operator_alerts == []


# --- halt bundles -----------------------------------------------------------


def test_851_a_path_that_cannot_be_resolved_alerts_and_raises(
    tmp_path, operator_alerts, monkeypatch
):
    bundle = tmp_path / "elsewhere" / "halt-evidence.json"
    real_resolve = Path.resolve

    def resolve(self, *args, **kwargs):
        if self == bundle:
            raise OSError(22, "Invalid argument", str(self))
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)

    with pytest.raises(OSError):
        fr._under(bundle, tmp_path / "repo")

    assert len(operator_alerts) == 1
    assert str(bundle) in operator_alerts[0]["cause"]


def test_851_a_path_outside_the_root_is_not_under_it(tmp_path, operator_alerts):
    (tmp_path / "repo").mkdir()
    (tmp_path / "other").mkdir()

    assert fr._under(tmp_path / "other" / "x.json", tmp_path / "repo") is False
    assert fr._under(tmp_path / "repo" / "x.json", tmp_path / "repo") is True
    assert operator_alerts == []


def test_852_the_withdrawn_tag_is_gone_from_under():
    assert _tag_free(fr._under)


def test_928_an_unreadable_stamp_is_counted_unplaced_and_alerts(operator_alerts):
    per_run, unplaced = fr.attribute_bundles(
        [{"issue": 4, "halted_at": "not a time", "_path": "/x/halt-evidence.json"}], []
    )

    assert per_run == {} and unplaced == 1
    assert len(operator_alerts) == 1
    assert "not a time" in operator_alerts[0]["cause"]
    assert "/x/halt-evidence.json" in operator_alerts[0]["cause"]


def test_928_the_withdrawn_tag_is_gone_from_parse_halted_at():
    assert _tag_free(fr._parse_halted_at)


def _bundle_root(tmp_path: Path) -> Path:
    root = tmp_path / "docs" / "lineage" / "4"
    root.mkdir(parents=True)
    return root


def test_971_a_corrupt_bundle_alerts_and_raises_naming_it(tmp_path, operator_alerts):
    path = _bundle_root(tmp_path) / "halt-evidence.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError) as raised:
        fr.read_halt_bundles([tmp_path])

    assert str(path) in str(raised.value)
    assert len(operator_alerts) == 1
    assert str(path) in operator_alerts[0]["cause"]


def test_971_a_bundle_that_cannot_be_read_alerts_and_raises(tmp_path, operator_alerts):
    path = _bundle_root(tmp_path) / "halt-evidence.json"
    path.mkdir()  # a directory with the bundle's name

    with pytest.raises(OSError):
        fr.read_halt_bundles([tmp_path])

    assert len(operator_alerts) == 1
    assert str(path) in operator_alerts[0]["cause"]


def test_972_the_withdrawn_tag_is_gone_from_read_halt_bundles():
    assert _tag_free(fr.read_halt_bundles)


def test_976_a_bundle_that_is_not_an_object_alerts_and_raises(tmp_path, operator_alerts):
    path = _bundle_root(tmp_path) / "halt-evidence.json"
    path.write_text("[1, 2]", encoding="utf-8")

    with pytest.raises(ValueError) as raised:
        fr.read_halt_bundles([tmp_path])

    assert str(path) in str(raised.value)
    assert len(operator_alerts) == 1


def test_a_readable_bundle_reads_with_no_alert(tmp_path, operator_alerts):
    path = _bundle_root(tmp_path) / "halt-evidence.json"
    stamp = datetime(2026, 8, 27, 11, 17, tzinfo=UTC).isoformat()
    path.write_text(json.dumps({"stage": "lld", "halted_at": stamp}), encoding="utf-8")

    bundles = fr.read_halt_bundles([tmp_path], AUG_1)

    assert [b["_path"] for b in bundles] == [str(path)]
    assert operator_alerts == []

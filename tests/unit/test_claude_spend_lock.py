"""The Claude spend lock switch (#3616): --lock and --unlock, dry run by default."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import claude_spend_lock as csl  # noqa: E402

FIXTURE = {
    "cleanupPeriodDays": 36500,
    "permissions": {
        "allow": ["Bash(npm run deploy:*)"],
        "deny": ["Bash(git push -f:*)", "Bash(rm -rf:*)", "Read(.env)"],
        "defaultMode": "auto",
    },
    "model": "opus",
    "autoMode": {"environment": ["**Organization**: None configured — unicode kept"]},
}


@pytest.fixture
def paths(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(csl.render(FIXTURE), encoding="utf-8")
    return {
        "settings": settings,
        "lock": tmp_path / "claude-spend.lock",
        "backups": tmp_path / "backups",
    }


def _run(paths, *flags, capsys=None):
    argv = [*flags, "--settings", str(paths["settings"]),
            "--lock-file", str(paths["lock"]), "--backup-dir", str(paths["backups"])]
    return csl.main(argv)


def _deny(paths):
    return json.loads(paths["settings"].read_text(encoding="utf-8"))["permissions"]["deny"]


def test_lock_apply_adds_the_three_entries_after_the_existing_ones_and_creates_the_file(paths):
    assert _run(paths, "--lock", "--apply") == 0

    deny = _deny(paths)
    assert deny[:3] == FIXTURE["permissions"]["deny"]
    assert deny[3:] == list(csl.DENY_ENTRIES)
    assert paths["lock"].is_file()
    assert "--unlock --apply" in paths["lock"].read_text(encoding="utf-8")
    assert len(list(paths["backups"].glob("settings.json.bak-*"))) == 1

    obj = json.loads(paths["settings"].read_text(encoding="utf-8"))
    obj["permissions"]["deny"] = obj["permissions"]["deny"][:3]
    assert obj == FIXTURE


def test_unlock_apply_removes_exactly_the_three_entries_and_the_file(paths):
    _run(paths, "--lock", "--apply")
    assert _run(paths, "--unlock", "--apply") == 0

    assert json.loads(paths["settings"].read_text(encoding="utf-8")) == FIXTURE
    assert not paths["lock"].exists()


def test_dry_run_changes_nothing_and_shows_the_three_lines(paths, capsys):
    before = paths["settings"].read_text(encoding="utf-8")
    assert _run(paths, "--lock") == 0
    out = capsys.readouterr().out

    assert paths["settings"].read_text(encoding="utf-8") == before
    assert not paths["lock"].exists()
    for entry in csl.DENY_ENTRIES:
        assert f'+      "{entry}"' in out
    assert "Dry run" in out


def test_lock_twice_is_a_no_op_the_second_time(paths, capsys):
    _run(paths, "--lock", "--apply")
    capsys.readouterr()
    assert _run(paths, "--lock", "--apply") == 0
    assert "already locked" in capsys.readouterr().out
    assert len(list(paths["backups"].glob("settings.json.bak-*"))) == 1


def test_unlock_on_an_unlocked_machine_is_a_no_op(paths, capsys):
    assert _run(paths, "--unlock", "--apply") == 0
    assert "already unlocked" in capsys.readouterr().out
    assert json.loads(paths["settings"].read_text(encoding="utf-8")) == FIXTURE


def test_invalid_json_refuses_and_leaves_the_file_alone(paths, capsys):
    paths["settings"].write_text("{not json", encoding="utf-8")
    assert _run(paths, "--lock", "--apply") == csl.EXIT_BAD_JSON
    assert "REFUSED" in capsys.readouterr().out
    assert paths["settings"].read_text(encoding="utf-8") == "{not json"
    assert not paths["lock"].exists()


def test_status_reports_both_halves_in_every_state(paths, capsys):
    def status():
        _run(paths, "--status")
        return capsys.readouterr().out

    assert "0 of 3 present" in status() and "lock file: absent" in status()
    _run(paths, "--lock", "--apply")
    capsys.readouterr()
    assert "3 of 3 present" in status() and "lock file: present" in status()
    paths["lock"].unlink()
    assert "3 of 3 present" in status() and "lock file: absent" in status()
    _run(paths, "--unlock", "--apply")
    capsys.readouterr()
    assert "0 of 3 present" in status() and "lock file: absent" in status()


def test_the_staged_write_never_leaves_a_tmp_file(paths):
    _run(paths, "--lock", "--apply")
    assert not paths["settings"].with_name("settings.json.tmp").exists()


def test_a_read_only_settings_file_is_written_and_left_read_only(paths):
    csl.make_readonly(paths["settings"])
    assert csl.is_readonly(paths["settings"])

    assert _run(paths, "--lock", "--apply") == 0

    assert _deny(paths)[3:] == list(csl.DENY_ENTRIES)
    assert csl.is_readonly(paths["settings"])
    assert not paths["settings"].with_name("settings.json.tmp").exists()


def test_a_writable_settings_file_stays_writable(paths):
    assert not csl.is_readonly(paths["settings"])
    assert _run(paths, "--lock", "--apply") == 0
    assert not csl.is_readonly(paths["settings"])


def test_a_failed_replace_names_the_backup_and_leaves_no_tmp(paths, monkeypatch, capsys):
    def refuse(src, dst):
        raise PermissionError(5, "Access is denied", str(src))

    monkeypatch.setattr(csl.os, "replace", refuse)
    before = paths["settings"].read_text(encoding="utf-8")

    assert _run(paths, "--lock", "--apply") == csl.EXIT_VERIFY
    out = capsys.readouterr().out

    assert "FAILED" in out and "backup at" in out
    assert paths["settings"].read_text(encoding="utf-8") == before
    assert not paths["settings"].with_name("settings.json.tmp").exists()
    assert not paths["lock"].exists()

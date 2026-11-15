"""set_new_repo_root.py sets new_repo_root in the config file, and only that (#4768).

Every test points `assemblyzero_config.CONFIG_PATH` at a file under tmp_path;
none reads or writes the real one. `platform.system` is patched wherever the
format matters, and the loader's cached OS format is cleared so 'auto' follows
the patch.
"""

from __future__ import annotations

import ast
import json
import os
import platform
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import assemblyzero_config
import set_new_repo_root

KEY = assemblyzero_config.NEW_REPO_ROOT_KEY


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A config path whose folder does not exist yet, and a root that does."""
    config_path = tmp_path / "home" / ".assemblyzero" / "config.json"
    monkeypatch.setattr(assemblyzero_config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(assemblyzero_config.AssemblyZeroConfig, "_detected_os", None)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(os, "geteuid", lambda: 1000, raising=False)
    root = tmp_path / "new-root"
    root.mkdir()
    return config_path, root


def _on_windows(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")


def _existing(config_path: Path, tmp_path: Path) -> bytes:
    """Write a valid config that carries every key, and return its bytes."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    proj = str(tmp_path / "proj")
    data = {
        "version": "1.0",
        "note": "a key this program never touches",
        "paths": {
            "assemblyzero_root": {"windows": "P:\\proj\\AZ", "unix": proj + "/AZ"},
            "projects_root": {"windows": "P:\\proj", "unix": proj},
            "user_claude_dir": {"windows": "P:\\claude", "unix": str(tmp_path / ".claude")},
            KEY: {"windows": "D:\\elsewhere"},
        },
    }
    raw = (json.dumps(data, indent=4) + "\n").encode("utf-8")
    config_path.write_bytes(raw)
    return raw


def _baks(config_path: Path) -> list[Path]:
    if not config_path.parent.exists():
        return []
    return sorted(config_path.parent.glob(config_path.name + ".*.bak"))


def _last_line(capsys) -> str:
    return capsys.readouterr().out.rstrip("\n").splitlines()[-1]


# T1 (R1, R2)


def test_a_dry_run_against_an_absent_file_writes_nothing_and_prints_the_plan(env, capsys):
    config_path, root = env
    assert set_new_repo_root.main(["--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert not config_path.exists()
    assert not config_path.parent.exists()
    assert f"paths.{KEY}.unix" in out
    assert str(root) in out
    assert str(config_path) in out
    assert "--apply" in out  # the exact command that makes the change
    assert out.rstrip("\n").splitlines()[-1] == "OK: dry run, nothing changed"


def test_a_dry_run_against_an_existing_file_changes_nothing(env, tmp_path, capsys):
    config_path, root = env
    raw = _existing(config_path, tmp_path)
    assert set_new_repo_root.main(["--root", str(root)]) == 0
    assert config_path.read_bytes() == raw
    assert _baks(config_path) == []
    assert _last_line(capsys) == "OK: dry run, nothing changed"


# T2 (R1, R6, R7)


def test_apply_against_an_absent_file_writes_only_the_key_on_ubuntu(env, capsys):
    config_path, root = env
    assert set_new_repo_root.main(["--root", str(root), "--apply"]) == 0
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "version": "1.0",
        "paths": {KEY: {"unix": str(root)}},
    }
    assert config_path.read_text(encoding="utf-8").endswith("}\n")
    assert _baks(config_path) == []
    assert not config_path.with_name("config.json.tmp").exists()
    assert _last_line(capsys) == f"OK: new_repo_root is {root} in {config_path}"


def test_apply_against_an_absent_file_writes_the_windows_format_on_windows(
    env, monkeypatch, capsys
):
    config_path, root = env
    _on_windows(monkeypatch)
    assert set_new_repo_root.main(["--root", str(root), "--apply"]) == 0
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "version": "1.0",
        "paths": {KEY: {"windows": str(root)}},
    }
    assert _last_line(capsys).startswith("OK:")


# T3 (R3)


@pytest.mark.parametrize("system, fmt, kept", [("Linux", "unix", "windows"), ("Windows", "windows", None)])
def test_apply_keeps_every_other_key_and_leaves_a_byte_identical_dated_copy(
    env, tmp_path, monkeypatch, capsys, system, fmt, kept
):
    config_path, root = env
    monkeypatch.setattr(platform, "system", lambda: system)
    raw = _existing(config_path, tmp_path)
    before = json.loads(raw)

    assert set_new_repo_root.main(["--root", str(root), "--apply"]) == 0

    after = json.loads(config_path.read_text(encoding="utf-8"))
    expected = json.loads(raw)
    expected["paths"][KEY][fmt] = str(root)
    assert after == expected
    assert after["note"] == before["note"]
    for key in ("assemblyzero_root", "projects_root", "user_claude_dir"):
        assert after["paths"][key] == before["paths"][key]
    if kept:
        assert after["paths"][KEY][kept] == before["paths"][KEY][kept]

    baks = _baks(config_path)
    assert len(baks) == 1
    assert baks[0].read_bytes() == raw
    stamp = baks[0].name[len("config.json."):-len(".bak")]
    assert len(stamp) == 15 and stamp[8] == "-" and (stamp[:8] + stamp[9:]).isdigit()
    assert not config_path.with_name("config.json.tmp").exists()
    assert _last_line(capsys).startswith("OK: new_repo_root is ")


# T4 (R4)


def _assert_refused(capsys, config_path: Path, raw: bytes | None, step: str) -> None:
    last = _last_line(capsys)
    assert last.startswith(f"FAILED: {step}: "), last
    assert last.endswith("Nothing after this step was done. Paste this output to the agent.")
    if raw is None:
        assert not config_path.exists()
    else:
        assert config_path.read_bytes() == raw
    assert _baks(config_path) == []
    assert not config_path.with_name("config.json.tmp").exists()


def test_running_as_root_is_refused(env, tmp_path, monkeypatch, capsys):
    config_path, root = env
    raw = _existing(config_path, tmp_path)
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    assert set_new_repo_root.main(["--root", str(root), "--apply"]) == 1
    _assert_refused(capsys, config_path, raw, "refuse root")


@pytest.mark.parametrize("which", ["relative", "missing", "a file", "dot-dot"])
def test_a_root_that_is_not_an_absolute_existing_directory_is_refused(
    env, tmp_path, capsys, which
):
    config_path, root = env
    raw = _existing(config_path, tmp_path)
    a_file = tmp_path / "a-file"
    a_file.write_text("x", encoding="utf-8")
    given = {
        "relative": "relative/dir",
        "missing": str(tmp_path / "no-such-dir"),
        "a file": str(a_file),
        "dot-dot": str(root / ".." / root.name),
    }[which]
    assert set_new_repo_root.main(["--root", given, "--apply"]) == 1
    _assert_refused(capsys, config_path, raw, "check --root")


def test_an_absent_root_is_refused_against_an_absent_file(env, tmp_path, capsys):
    config_path, _ = env
    assert set_new_repo_root.main(["--root", str(tmp_path / "nope"), "--apply"]) == 1
    _assert_refused(capsys, config_path, None, "check --root")
    assert not config_path.parent.exists()


@pytest.mark.parametrize(
    "content",
    [
        b"{not json\n",
        b"\xff\xfe not utf-8",
        b'{"version": "1.0"}\n',
        b'{"version": "1.0", "paths": {"new_repo_root": {"unix": 7}}}\n',
        b'{"version": "1.0", "paths": {"projects_root": {"unix": "/x"}}}\n',
    ],
    ids=["invalid-json", "not-utf8", "no-paths", "non-string-value", "half-a-fleet-key"],
)
def test_a_config_file_the_loader_refuses_is_refused(env, capsys, content):
    config_path, root = env
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(content)
    assert set_new_repo_root.main(["--root", str(root), "--apply"]) == 1
    _assert_refused(capsys, config_path, content, "read the config")


# T5 (R5)


def test_a_second_apply_with_the_same_root_changes_nothing(env, tmp_path, capsys):
    config_path, root = env
    _existing(config_path, tmp_path)
    assert set_new_repo_root.main(["--root", str(root), "--apply"]) == 0
    capsys.readouterr()
    written = config_path.read_bytes()
    baks = _baks(config_path)
    assert len(baks) == 1

    assert set_new_repo_root.main(["--root", str(root), "--apply"]) == 0
    out = capsys.readouterr().out
    assert config_path.read_bytes() == written
    assert _baks(config_path) == baks
    assert "already" in out
    assert out.rstrip("\n").splitlines()[-1].startswith("OK: already set")


def test_a_trailing_slash_is_the_same_root(env, capsys):
    config_path, root = env
    assert set_new_repo_root.main(["--root", str(root), "--apply"]) == 0
    written = config_path.read_bytes()
    capsys.readouterr()
    assert set_new_repo_root.main(["--root", str(root) + "/", "--apply"]) == 0
    assert config_path.read_bytes() == written
    assert _last_line(capsys).startswith("OK: already set")


# T6 (R6)


def test_a_failed_proof_ends_failed_with_exit_1(env, tmp_path, monkeypatch, capsys):
    config_path, root = env
    raw = _existing(config_path, tmp_path)
    monkeypatch.setattr(
        assemblyzero_config.AssemblyZeroConfig,
        "new_repo_root",
        lambda self, fmt="windows": "/somewhere/else",
    )
    assert set_new_repo_root.main(["--root", str(root), "--apply"]) == 1
    last = _last_line(capsys)
    assert last.startswith("FAILED: prove the change: "), last
    assert "/somewhere/else" in last
    baks = _baks(config_path)
    assert len(baks) == 1 and baks[0].read_bytes() == raw  # the old file is still there


def test_a_proof_that_finds_another_path_moved_ends_failed(env, tmp_path, monkeypatch, capsys):
    config_path, root = env
    _existing(config_path, tmp_path)
    real = assemblyzero_config.AssemblyZeroConfig.projects_root
    calls = []

    def moving(self, fmt="windows"):
        calls.append(fmt)
        return real(self, fmt) if len(calls) == 1 else "/moved"

    monkeypatch.setattr(assemblyzero_config.AssemblyZeroConfig, "projects_root", moving)
    assert set_new_repo_root.main(["--root", str(root), "--apply"]) == 1
    last = _last_line(capsys)
    assert last.startswith("FAILED: prove the change: "), last
    assert "projects_root" in last


# R7 and the issue's limits: the header, and what the program may do


def test_the_header_gives_the_command_every_step_and_who_applies():
    doc = set_new_repo_root.__doc__
    assert "set_new_repo_root.py --root /home/mcwiz/Projects" in doc
    assert "set_new_repo_root.py --root /home/mcwiz/Projects --apply" in doc
    assert "Only the operator runs it with --apply" in doc
    for step in range(1, 10):
        assert f"  {step}. " in doc, step


def test_the_program_deletes_nothing_and_imports_only_the_stdlib_and_the_loader():
    tree = ast.parse((TOOLS / "set_new_repo_root.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported - set(sys.stdlib_module_names) == {"assemblyzero_config"}

    removers = {"unlink", "remove", "rmdir", "rmtree", "removedirs", "truncate", "move", "rename"}
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert called & removers == set()

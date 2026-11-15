"""set_projects_roots_file.py sets projects_roots_file in the config file, and only that (#4773).

Every test points `assemblyzero_config.CONFIG_PATH` and `projects_root.CONFIG_PATH`
at the same file under tmp_path; none reads or writes the real one.
`platform.system` is patched wherever the format matters, and the loader's
cached OS format is cleared so 'auto' follows the patch.
"""

from __future__ import annotations

import ast
import json
import os
import platform
import sys
from pathlib import Path

import pytest

from assemblyzero.core import projects_root

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import assemblyzero_config
import set_projects_roots_file

KEY = assemblyzero_config.PROJECTS_ROOTS_FILE_KEY


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A config path whose folder does not exist yet, and a valid setting naming two roots that do."""
    config_path = tmp_path / "home" / ".assemblyzero" / "config.json"
    monkeypatch.setattr(assemblyzero_config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(projects_root, "CONFIG_PATH", config_path)
    monkeypatch.setattr(assemblyzero_config.AssemblyZeroConfig, "_detected_os", None)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(projects_root, "_windows", lambda: False)
    monkeypatch.setattr(os, "geteuid", lambda: 1000, raising=False)
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    setting = _setting(tmp_path / "fleet" / "roots.json", [str(first), str(second)])
    return config_path, setting, [first, second]


def _setting(path: Path, content) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"roots": content}) if isinstance(content, list) else content
    path.write_text(text, encoding="utf-8")
    return path


def _on_windows(monkeypatch):
    """The Windows side, read from Ubuntu: each root is used as written so it exists here."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(projects_root, "_windows", lambda: True)
    monkeypatch.setattr(projects_root, "spell_root", lambda root, windows: root)


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
            "new_repo_root": {"unix": str(tmp_path / "new-root")},
            KEY: {"windows": "D:\\fleet\\roots.json"},
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


# Dry run


def test_a_dry_run_against_an_absent_file_writes_nothing_and_prints_the_plan(env, capsys):
    config_path, setting, roots = env
    assert set_projects_roots_file.main(["--file", str(setting)]) == 0
    out = capsys.readouterr().out
    assert not config_path.exists()
    assert not config_path.parent.exists()
    assert f"paths.{KEY}.unix" in out
    assert str(setting) in out
    assert str(config_path) in out
    for root in roots:
        assert str(root) in out
    assert f"--file {setting} --apply" in out  # the exact command that makes the change
    assert out.rstrip("\n").splitlines()[-1] == "OK: dry run, nothing changed"


def test_a_dry_run_against_an_existing_file_changes_nothing(env, tmp_path, capsys):
    config_path, setting, _ = env
    raw = _existing(config_path, tmp_path)
    assert set_projects_roots_file.main(["--file", str(setting)]) == 0
    assert config_path.read_bytes() == raw
    assert _baks(config_path) == []
    assert _last_line(capsys) == "OK: dry run, nothing changed"


# Apply


def test_apply_against_an_absent_file_writes_only_the_key_on_ubuntu(env, capsys):
    config_path, setting, roots = env
    assert set_projects_roots_file.main(["--file", str(setting), "--apply"]) == 0
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "version": "1.0",
        "paths": {KEY: {"unix": str(setting)}},
    }
    assert config_path.read_text(encoding="utf-8").endswith("}\n")
    assert _baks(config_path) == []
    assert not config_path.with_name("config.json.tmp").exists()
    assert projects_root.projects_roots() == roots
    assert _last_line(capsys) == f"OK: {KEY} is {setting} in {config_path}"


def test_apply_against_an_absent_file_writes_the_windows_format_on_windows(env, monkeypatch, capsys):
    config_path, setting, roots = env
    _on_windows(monkeypatch)
    assert set_projects_roots_file.main(["--file", str(setting), "--apply"]) == 0
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "version": "1.0",
        "paths": {KEY: {"windows": str(setting)}},
    }
    assert projects_root.projects_roots() == roots
    assert _last_line(capsys).startswith("OK:")


@pytest.mark.parametrize("system, fmt, kept", [("Linux", "unix", "windows"), ("Windows", "windows", None)])
def test_apply_keeps_every_other_key_and_leaves_a_byte_identical_dated_copy(
    env, tmp_path, monkeypatch, capsys, system, fmt, kept
):
    config_path, setting, _ = env
    if system == "Windows":
        _on_windows(monkeypatch)
    raw = _existing(config_path, tmp_path)
    before = json.loads(raw)

    assert set_projects_roots_file.main(["--file", str(setting), "--apply"]) == 0

    after = json.loads(config_path.read_text(encoding="utf-8"))
    expected = json.loads(raw)
    expected["paths"][KEY][fmt] = str(setting)
    assert after == expected
    assert after["note"] == before["note"]
    for key in ("assemblyzero_root", "projects_root", "user_claude_dir", "new_repo_root"):
        assert after["paths"][key] == before["paths"][key]
    if kept:
        assert after["paths"][KEY][kept] == before["paths"][KEY][kept]

    baks = _baks(config_path)
    assert len(baks) == 1
    assert baks[0].read_bytes() == raw
    stamp = baks[0].name[len("config.json."):-len(".bak")]
    assert len(stamp) == 15 and stamp[8] == "-" and (stamp[:8] + stamp[9:]).isdigit()
    assert not config_path.with_name("config.json.tmp").exists()
    assert _last_line(capsys).startswith(f"OK: {KEY} is ")


# Refusals


def _assert_refused(capsys, config_path: Path, raw: bytes | None, step: str) -> str:
    last = _last_line(capsys)
    assert last.startswith(f"FAILED: {step}: "), last
    assert last.endswith("Nothing after this step was done. Paste this output to the agent.")
    if raw is None:
        assert not config_path.exists()
    else:
        assert config_path.read_bytes() == raw
    assert _baks(config_path) == []
    assert not config_path.with_name("config.json.tmp").exists()
    return last


def test_running_as_root_is_refused(env, tmp_path, monkeypatch, capsys):
    config_path, setting, _ = env
    raw = _existing(config_path, tmp_path)
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    assert set_projects_roots_file.main(["--file", str(setting), "--apply"]) == 1
    _assert_refused(capsys, config_path, raw, "refuse root")


@pytest.mark.parametrize("which", ["relative", "missing", "a directory", "dot-dot"])
def test_a_file_that_is_not_an_absolute_existing_file_is_refused(env, tmp_path, capsys, which):
    config_path, setting, _ = env
    raw = _existing(config_path, tmp_path)
    given = {
        "relative": "fleet/roots.json",
        "missing": str(tmp_path / "no-such.json"),
        "a directory": str(tmp_path / "fleet"),
        "dot-dot": str(setting.parent / ".." / "fleet" / setting.name),
    }[which]
    assert set_projects_roots_file.main(["--file", given, "--apply"]) == 1
    _assert_refused(capsys, config_path, raw, "check --file")


@pytest.mark.parametrize(
    "content, reason",
    [
        ("{not json", "not valid JSON"),
        (["relative/root"], "not an absolute path"),
        ([], "empty"),
        (["/srv/a", "/srv/a"], "more than once"),
        ('{"other": []}', "no 'roots'"),
    ],
    ids=["invalid-json", "relative-root", "empty", "duplicate", "no-roots-key"],
)
def test_a_file_that_does_not_parse_as_a_roots_list_is_refused(env, tmp_path, capsys, content, reason):
    config_path, _, _ = env
    raw = _existing(config_path, tmp_path)
    bad = _setting(tmp_path / "bad" / "roots.json", content)
    assert set_projects_roots_file.main(["--file", str(bad), "--apply"]) == 1
    last = _assert_refused(capsys, config_path, raw, "check --file")
    assert str(bad) in last and reason in last


def test_a_root_the_file_names_that_does_not_exist_is_refused_and_named(env, tmp_path, capsys):
    config_path, _, roots = env
    gone = tmp_path / "gone"
    partial = _setting(tmp_path / "partial" / "roots.json", [str(roots[0]), str(gone)])
    assert set_projects_roots_file.main(["--file", str(partial), "--apply"]) == 1
    last = _assert_refused(capsys, config_path, None, "check the roots")
    assert str(gone) in last
    assert not config_path.parent.exists()


@pytest.mark.parametrize(
    "content",
    [
        b"{not json\n",
        b"\xff\xfe not utf-8",
        b'{"version": "1.0"}\n',
        b'{"version": "1.0", "paths": {"projects_roots_file": {"unix": 7}}}\n',
        b'{"version": "1.0", "paths": {"projects_root": {"unix": "/x"}}}\n',
    ],
    ids=["invalid-json", "not-utf8", "no-paths", "non-string-value", "half-a-fleet-key"],
)
def test_a_config_file_the_loader_refuses_is_refused(env, capsys, content):
    config_path, setting, _ = env
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(content)
    assert set_projects_roots_file.main(["--file", str(setting), "--apply"]) == 1
    _assert_refused(capsys, config_path, content, "read the config")


# Already set


def test_a_second_apply_with_the_same_file_changes_nothing(env, tmp_path, capsys):
    config_path, setting, _ = env
    _existing(config_path, tmp_path)
    assert set_projects_roots_file.main(["--file", str(setting), "--apply"]) == 0
    capsys.readouterr()
    written = config_path.read_bytes()
    baks = _baks(config_path)
    assert len(baks) == 1

    assert set_projects_roots_file.main(["--file", str(setting), "--apply"]) == 0
    out = capsys.readouterr().out
    assert config_path.read_bytes() == written
    assert _baks(config_path) == baks
    assert out.rstrip("\n").splitlines()[-1].startswith("OK: already set")


# The proof


def test_a_failed_proof_ends_failed_with_exit_1_and_keeps_the_old_file(env, tmp_path, monkeypatch, capsys):
    config_path, setting, _ = env
    raw = _existing(config_path, tmp_path)
    monkeypatch.setattr(projects_root, "projects_roots", lambda windows=None: [Path("/somewhere/else")])
    assert set_projects_roots_file.main(["--file", str(setting), "--apply"]) == 1
    last = _last_line(capsys)
    assert last.startswith("FAILED: prove the change: "), last
    assert "/somewhere/else" in last
    baks = _baks(config_path)
    assert len(baks) == 1 and baks[0].read_bytes() == raw  # the old file is still there


def test_a_proof_that_finds_new_repo_root_moved_ends_failed(env, tmp_path, monkeypatch, capsys):
    config_path, setting, _ = env
    _existing(config_path, tmp_path)
    real = assemblyzero_config.AssemblyZeroConfig.new_repo_root
    calls = []

    def moving(self, fmt="windows"):
        calls.append(fmt)
        return real(self, fmt) if len(calls) == 1 else "/moved"

    monkeypatch.setattr(assemblyzero_config.AssemblyZeroConfig, "new_repo_root", moving)
    assert set_projects_roots_file.main(["--file", str(setting), "--apply"]) == 1
    last = _last_line(capsys)
    assert last.startswith("FAILED: prove the change: "), last
    assert "new_repo_root" in last


# The header, and what the program may do


def test_the_header_gives_the_command_every_step_and_who_applies():
    doc = set_projects_roots_file.__doc__
    assert "<AssemblyZero>/tools/set_projects_roots_file.py --file <setting>\n" in doc
    assert "<AssemblyZero>/tools/set_projects_roots_file.py --file <setting> --apply" in doc
    assert "Only the operator runs it with --apply" in doc
    for step in range(1, 11):
        assert f"  {step}. " in doc, step


def test_the_program_deletes_nothing_and_imports_only_the_stdlib_the_loader_and_the_module():
    tree = ast.parse((TOOLS / "set_projects_roots_file.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported |= {f"{node.module}.{alias.name}" for alias in node.names}
    outside = {name for name in imported if name.split(".")[0] not in sys.stdlib_module_names}
    assert outside == {"assemblyzero_config", "assemblyzero.core.projects_root"}

    removers = {"unlink", "remove", "rmdir", "rmtree", "removedirs", "truncate", "move", "rename"}
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert called & removers == set()

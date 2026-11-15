"""Every Projects root, read from the fleet's setting through a pointer (#4773).

Every test points ``projects_root.CONFIG_PATH`` (and, where the loader is
compared, ``assemblyzero_config.CONFIG_PATH``) at a file under tmp_path, or
patches HOME for a fresh copy of the module; none reads the machine's real
config. The side is chosen by patching ``projects_root._windows`` or by the
``windows`` argument, so both spellings are tested from Ubuntu.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from assemblyzero.core import projects_root as pr

REPO = Path(__file__).resolve().parents[2]
MODULE_FILE = REPO / "assemblyzero" / "core" / "projects_root.py"
PROGRAM_FILE = REPO / "tools" / "set_projects_roots_file.py"

sys.path.insert(0, str(REPO / "tools"))
import assemblyzero_config


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A config path under tmp_path, with no file yet, read as Ubuntu."""
    config = tmp_path / "home" / ".assemblyzero" / "config.json"
    monkeypatch.setattr(pr, "CONFIG_PATH", config)
    monkeypatch.setattr(pr, "_windows", lambda: False)
    return tmp_path, config


def _setting(path: Path, content) -> Path:
    """Write a roots setting: a list becomes {"roots": list}; anything else as JSON or text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, list):
        path.write_text(json.dumps({"roots": content}), encoding="utf-8")
    elif isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_text(json.dumps(content), encoding="utf-8")
    return path


def _point(config: Path, entry, **other_paths) -> None:
    """Write a config whose projects_roots_file is `entry` (a path is the unix format)."""
    config.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(entry, Path):
        entry = {"unix": str(entry)}
    paths = dict(other_paths)
    if entry is not None:
        paths["projects_roots_file"] = entry
    config.write_text(json.dumps({"version": "1.0", "paths": paths}), encoding="utf-8")


def _repo(root: Path, name: str, *, git_init: bool = False) -> Path:
    """A primary checkout: a real `git init`, or a folder holding a .git directory."""
    path = root / name
    if git_init:
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(path)], check=True)
    else:
        (path / ".git").mkdir(parents=True)
    return path


def _two_roots(tmp_path: Path, config: Path) -> tuple[Path, Path, Path]:
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    setting = _setting(tmp_path / "fleet" / "roots.json", [str(first), str(second)])
    _point(config, setting)
    return first, second, setting


# T1 (R1): every root, in order, spelled for the side


def test_the_roots_come_from_the_setting_in_order_and_projects_is_the_first(env):
    tmp_path, config = env
    first, second, setting = _two_roots(tmp_path, config)
    assert pr.projects_roots() == [first, second]
    assert pr.PROJECTS_ROOTS == [first, second]
    assert pr.PROJECTS == first
    assert pr.roots_source() == str(setting)


def test_the_windows_side_reads_its_own_pointer_and_spells_each_root(env):
    tmp_path, config = env
    ubuntu = _setting(tmp_path / "u" / "roots.json", ["/home/dev/Elsewhere"])
    windows = _setting(tmp_path / "w" / "roots.json", ["/mnt/d/work/Projects", "/home/dev/Projects"])
    _point(config, {"unix": str(ubuntu), "windows": str(windows)})
    assert [str(p) for p in pr.projects_roots(windows=True)] == [
        "D:/work/Projects",
        "//wsl.localhost/Ubuntu/home/dev/Projects",
    ]
    assert [str(p) for p in pr.projects_roots(windows=False)] == ["/home/dev/Elsewhere"]
    assert pr.roots_source(windows=True) == str(windows)


@pytest.mark.parametrize(
    "root, windows, spelled",
    [
        ("/mnt/c/Users/dev/Projects", True, "C:/Users/dev/Projects"),
        ("/mnt/d", True, "D:/"),
        ("/home/dev/Projects", True, "//wsl.localhost/Ubuntu/home/dev/Projects"),
        ("/mnt/data/x", True, "//wsl.localhost/Ubuntu/mnt/data/x"),
        ("/mnt/c/Users/dev/Projects", False, "/mnt/c/Users/dev/Projects"),
        ("/home/dev/Projects", False, "/home/dev/Projects"),
    ],
)
def test_spell_root_gives_each_side_its_spelling(root, windows, spelled):
    assert pr.spell_root(root, windows) == spelled


def test_the_distro_is_a_module_constant():
    assert pr.WSL_DISTRO == "Ubuntu"


def test_read_roots_setting_returns_the_roots_for_one_side(tmp_path):
    setting = _setting(tmp_path / "roots.json", ["/mnt/e/a", "/srv/b/"])
    assert [str(p) for p in pr.read_roots_setting(setting, windows=False)] == ["/mnt/e/a", "/srv/b"]
    assert [str(p) for p in pr.read_roots_setting(setting, windows=True)] == [
        "E:/a",
        "//wsl.localhost/Ubuntu/srv/b",
    ]


def test_the_lazy_attributes_honour_the_patched_pointer_on_every_read(env):
    tmp_path, config = env
    first, second, _ = _two_roots(tmp_path, config)
    from assemblyzero.core.projects_root import PROJECTS, PROJECTS_ROOTS

    assert PROJECTS_ROOTS == [first, second]
    assert PROJECTS == first

    third = tmp_path / "third"
    third.mkdir()
    _point(config, _setting(tmp_path / "other" / "roots.json", [str(third)]))
    assert pr.PROJECTS_ROOTS == [third]
    assert pr.PROJECTS == third


def test_an_unknown_attribute_is_still_an_attribute_error():
    with pytest.raises(AttributeError):
        pr.NO_SUCH_NAME  # noqa: B018


# T2 (R2): a missing root stops the walk, named


def test_a_missing_root_stops_the_walk_and_is_named(env):
    tmp_path, config = env
    present, gone, also_gone = tmp_path / "present", tmp_path / "gone", tmp_path / "also-gone"
    _repo(present, "alpha")
    _point(config, _setting(tmp_path / "roots.json", [str(present), str(gone), str(also_gone)]))
    assert pr.missing_roots(pr.projects_roots()) == [gone, also_gone]
    with pytest.raises(RuntimeError) as e:
        pr.repositories()
    assert str(gone) in str(e.value)
    assert str(also_gone) in str(e.value)


def test_a_missing_root_given_by_the_caller_stops_the_walk_too(tmp_path):
    present = tmp_path / "present"
    present.mkdir()
    a_file = tmp_path / "a-file"
    a_file.write_text("x", encoding="utf-8")
    assert pr.missing_roots([present, a_file]) == [a_file]
    with pytest.raises(RuntimeError) as e:
        pr.repositories([present, tmp_path / "nope"])
    assert str(tmp_path / "nope") in str(e.value)


def test_locating_a_repository_with_a_root_missing_is_refused(tmp_path):
    present = tmp_path / "present"
    _repo(present, "alpha")
    with pytest.raises(RuntimeError) as e:
        pr.locate_repo("alpha", [present, tmp_path / "nope"])
    assert str(tmp_path / "nope") in str(e.value)


# T3 (R4): one name under two roots is reported, left out, and never located


def test_a_name_under_two_roots_is_reported_and_left_out(env, capsys):
    tmp_path, config = env
    first, second, _ = _two_roots(tmp_path, config)
    _repo(first, "beta", git_init=True)
    _repo(first, "alpha")
    _repo(first, "twin", git_init=True)
    _repo(second, "twin")
    _repo(second, "gamma")
    (first / "a-worktree").mkdir()
    (first / "a-worktree" / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    (second / "plain-folder").mkdir()
    (second / "a-file").write_text("x", encoding="utf-8")

    found, twice = pr.repositories()

    assert found == [first / "alpha", first / "beta", second / "gamma"]
    assert twice == {"twin": [first, second]}
    assert capsys.readouterr().err == ""  # the roots came from the setting


def test_locating_a_name_under_two_roots_raises_naming_both_copies(env):
    tmp_path, config = env
    first, second, _ = _two_roots(tmp_path, config)
    _repo(first, "twin")
    _repo(second, "twin")
    with pytest.raises(RuntimeError) as e:
        pr.locate_repo("twin")
    assert str(first / "twin") in str(e.value)
    assert str(second / "twin") in str(e.value)


def test_locating_a_name_under_one_root_gives_that_copy(env):
    tmp_path, config = env
    first, second, _ = _two_roots(tmp_path, config)
    _repo(second, "only-here")
    assert pr.locate_repo("only-here") == second / "only-here"
    assert pr.locate_repo("only-here", [first, second]) == second / "only-here"


def test_locating_a_name_under_no_root_gives_the_first_roots_path(env):
    tmp_path, config = env
    first, _, _ = _two_roots(tmp_path, config)
    assert pr.locate_repo("absent") == first / "absent"


# T4 (R5): no pointer, one root, said once


@pytest.mark.parametrize(
    "content",
    [
        None,
        {"version": "1.0", "paths": {}},
        {"version": "1.0", "paths": {"projects_roots_file": {"windows": "/srv/w/roots.json"}}},
    ],
    ids=["no-config", "no-key", "only-the-other-side"],
)
def test_with_no_pointer_the_roots_are_the_checkouts_parent(env, content):
    _, config = env
    if content is not None:
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps(content), encoding="utf-8")
    assert pr.projects_roots() == [pr.REPO_ROOT.parent]
    assert pr.PROJECTS_ROOTS == [pr.REPO_ROOT.parent]
    assert pr.PROJECTS == pr.REPO_ROOT.parent
    assert pr.roots_source() == "derived from AssemblyZero's location (no projects_roots_file configured)"
    assert pr.projects_roots_file() is None


def test_a_walk_with_no_pointer_prints_one_line_saying_so(tmp_path, monkeypatch, capsys):
    projects = tmp_path / "Projects"
    checkout = _repo(projects, "AssemblyZero")
    _repo(projects, "alpha")
    monkeypatch.setattr(pr, "REPO_ROOT", checkout)
    monkeypatch.setattr(pr, "CONFIG_PATH", tmp_path / "home" / ".assemblyzero" / "config.json")
    monkeypatch.setattr(pr, "_windows", lambda: False)

    found, twice = pr.repositories()

    assert found == [projects / "AssemblyZero", projects / "alpha"]
    assert twice == {}
    err = capsys.readouterr().err
    notice = (
        f"one Projects root in use: {projects} "
        "(derived from AssemblyZero's location (no projects_roots_file configured))"
    )
    assert err.splitlines() == [notice]


# T5 (R6): a broken pointer stops a tool, naming the file and the reason


@pytest.mark.parametrize(
    "content, reason",
    [
        ("{not json", "not valid JSON"),
        (["relative/path"], "not an absolute path"),
        ([], "empty"),
        ({"roots": "/srv/a"}, "not a list"),
        ({"other": ["/srv/a"]}, "no 'roots'"),
        ([7], "not a string"),
        (["/srv/a", "/srv/a/"], "more than once"),
        (["/srv/b", "/srv/a", "/srv/b"], "more than once"),
        ('["/srv/a"]', "not a JSON object"),
    ],
    ids=[
        "invalid-json", "relative", "empty", "not-a-list", "no-roots-key",
        "non-string", "duplicate-after-normalizing", "duplicate", "top-level-list",
    ],
)
def test_a_malformed_setting_stops_any_tool_naming_the_file_and_the_reason(env, content, reason):
    tmp_path, config = env
    setting = _setting(tmp_path / "fleet" / "roots.json", content)
    _point(config, setting)
    for read in (pr.projects_roots, lambda: pr.PROJECTS, lambda: pr.PROJECTS_ROOTS, pr.repositories):
        with pytest.raises(RuntimeError) as e:
            read()
        message = str(e.value)
        assert str(setting) in message
        assert str(config) in message
        assert reason in message, message
    with pytest.raises(RuntimeError) as direct:
        pr.read_roots_setting(setting, windows=False)
    assert str(setting) in str(direct.value) and reason in str(direct.value)


def test_a_pointer_to_a_missing_file_names_it(env):
    tmp_path, config = env
    setting = tmp_path / "no-such" / "roots.json"
    _point(config, setting)
    with pytest.raises(RuntimeError) as e:
        pr.projects_roots()
    assert str(setting) in str(e.value)
    assert str(config) in str(e.value)
    assert "could not be read" in str(e.value)


def test_from_import_of_projects_raises_on_a_broken_pointer(env):
    tmp_path, config = env
    setting = tmp_path / "missing.json"
    _point(config, setting)
    with pytest.raises(RuntimeError) as e:
        from assemblyzero.core.projects_root import PROJECTS  # noqa: F401
    assert str(setting) in str(e.value)


@pytest.mark.parametrize(
    "content, reason",
    [
        ("{not json", "not valid JSON"),
        ('{"version": "1.0", "paths": {"projects_roots_file": "/srv/a.json"}}', "must be an object"),
        ('{"version": "1.0", "paths": {"projects_roots_file": {}}}', "carries neither"),
        ('{"version": "1.0", "paths": {"projects_roots_file": {"unix": 5}}}', "must be a string"),
        ('{"version": "1.0", "paths": {"projects_roots_file": {"unix": "fleet/roots.json"}}}', "not an absolute path"),
        ('{"version": "1.0", "paths": {"projects_roots_file": {"unix": "/srv/../roots.json"}}}', "'..'"),
        ('{"version": "1.0", "paths": []}', "'paths' must be an object"),
        ("[]", "not a JSON object"),
    ],
    ids=[
        "invalid-json", "not-an-object", "no-format", "non-string", "relative", "dot-dot",
        "paths-not-an-object", "top-level-list",
    ],
)
def test_a_broken_pointer_in_the_config_stops_any_tool_naming_the_config(env, content, reason):
    _, config = env
    config.parent.mkdir(parents=True)
    config.write_text(content, encoding="utf-8")
    with pytest.raises(RuntimeError) as e:
        pr.projects_roots()
    assert str(config) in str(e.value)
    assert reason in str(e.value), str(e.value)


@pytest.mark.skipif(sys.platform == "win32", reason="Path.home() follows HOME only off Windows")
def test_importing_for_repo_root_reads_no_config_even_when_the_pointer_is_broken(tmp_path, monkeypatch):
    home = tmp_path / "home"
    config = home / ".assemblyzero" / "config.json"
    setting = tmp_path / "no-such-setting.json"
    _point(config, setting)
    monkeypatch.setenv("HOME", str(home))

    spec = importlib.util.spec_from_file_location("projects_root_fresh_4773", MODULE_FILE)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)  # importing never resolves the roots

    assert fresh.CONFIG_PATH == config
    assert fresh.REPO_ROOT == pr.REPO_ROOT
    assert fresh.spellings("/mnt/c/Users/dev/Projects")["windows"] == "C:\\Users\\dev\\Projects"
    with pytest.raises(RuntimeError) as e:
        fresh.PROJECTS  # noqa: B018
    assert str(setting) in str(e.value)


# The pointer reader agrees with the loader


@pytest.mark.parametrize(
    "entry",
    [
        None,
        {"unix": "/srv/unix/roots.json"},
        {"windows": "/srv/windows/roots.json"},
        {"unix": "/srv/unix/roots.json", "windows": "/srv/windows/roots.json"},
    ],
    ids=["absent", "unix-only", "windows-only", "both"],
)
def test_the_pointer_reader_agrees_with_assemblyzero_config(env, monkeypatch, entry):
    _, config = env
    monkeypatch.setattr(assemblyzero_config, "CONFIG_PATH", config)
    monkeypatch.setattr(assemblyzero_config.AssemblyZeroConfig, "_detected_os", None)
    _point(config, entry)
    loaded = assemblyzero_config.AssemblyZeroConfig()
    assert loaded.load_error is None
    assert assemblyzero_config.PROJECTS_ROOTS_FILE_KEY == pr.PROJECTS_ROOTS_FILE_KEY
    for fmt, windows in (("unix", False), ("windows", True)):
        got = pr.projects_roots_file(windows=windows)
        assert (None if got is None else str(got)) == loaded.projects_roots_file(fmt), fmt
    if entry and "unix" in entry:
        assert loaded.projects_roots_file("unix") == entry["unix"]


# T7 (R1): no default path to a settings file, and nothing read beyond the parent


def test_with_no_pointer_nothing_outside_the_checkouts_parent_is_read(tmp_path, monkeypatch):
    projects = tmp_path / "Projects"
    checkout = _repo(projects, "AssemblyZero")
    _repo(projects, "alpha")
    _repo(tmp_path / "Other", "beta")
    config = tmp_path / "home" / ".assemblyzero" / "config.json"
    monkeypatch.setattr(pr, "REPO_ROOT", checkout)
    monkeypatch.setattr(pr, "CONFIG_PATH", config)
    monkeypatch.setattr(pr, "_windows", lambda: False)

    touched: list[Path] = []
    for name in ("exists", "is_dir", "is_file", "iterdir", "read_text", "read_bytes", "open"):
        real = getattr(Path, name)

        def spy(self, *args, _real=real, **kwargs):
            touched.append(self)
            return _real(self, *args, **kwargs)

        monkeypatch.setattr(Path, name, spy)

    assert pr.projects_roots() == [projects]
    found, _ = pr.repositories()
    assert pr.locate_repo("beta") == projects / "beta"
    monkeypatch.undo()

    assert [p.name for p in found] == ["AssemblyZero", "alpha"]
    assert touched, "the spy saw nothing; the check would pass vacuously"
    outside = [p for p in touched if p != config and not p.is_relative_to(projects)]
    assert outside == []


def _string_constants(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


@pytest.mark.parametrize("path", [MODULE_FILE, PROGRAM_FILE], ids=["module", "program"])
def test_neither_the_module_nor_the_program_holds_a_settings_path(path):
    json_names = [
        word.strip("`'\"()[]{},.:;")
        for text in _string_constants(path)
        for word in text.split()
        if ".json" in word
    ]
    assert json_names, "no string names config.json; the check would pass vacuously"
    others = [name for name in json_names if "config.json" not in name]  # config.json and its .bak/.tmp
    assert others == []


def test_the_program_takes_the_settings_path_only_from_the_command_line():
    tree = ast.parse(PROGRAM_FILE.read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "--file"
    ]
    assert len(calls) == 1
    keywords = {k.arg: k.value for k in calls[0].keywords}
    assert "default" not in keywords
    assert isinstance(keywords.get("required"), ast.Constant) and keywords["required"].value is True

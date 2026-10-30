"""The spec workflow's N1 analyze_codebase under standard 0034 (#3585).

Named ``test_spec_...`` because the requirements workflow has a node module of
the same name. Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md.

N1 builds everything the drafter is told about the target repo. A file it
cannot read, a file that does not parse and a base git cannot answer used to
leave the context smaller than the repo, with a WARNING on stdout. Now a
helper raises naming the file and the cause, and the node returns an
``error_message`` that ``route_after_analyze`` sends to HALT, which alerts.
"""
from __future__ import annotations

import importlib
import subprocess

import pytest

from assemblyzero.workflows.implementation_spec import base_tree as bt
from assemblyzero.workflows.implementation_spec.graph import route_after_analyze

# `nodes/__init__` re-exports the FUNCTION analyze_codebase, which shadows the
# module of the same name, so the module is imported by its dotted path.
acb = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.analyze_codebase"
)

NOT_UTF8 = b"\xff\xfe\xfa not utf-8\n"
BROKEN_PY = "class Broken\n    def m(self):\n        pass\n"


def _file(path: str, change_type: str = "Modify") -> dict:
    return {"path": path, "change_type": change_type, "description": "d",
            "current_content": None}


def _state(repo, files, **extra) -> dict:
    state = {"issue_number": 42, "repo_root": str(repo), "lld_content": "",
             "files_to_modify": files}
    state.update(extra)
    return state


def _halts(result: dict, *needles: str) -> None:
    message = result["error_message"]
    assert message, "the node must return an error_message"
    assert route_after_analyze(result) == "HALT"
    assert "#42" in message
    for needle in needles:
        assert needle in message, f"{needle!r} not in {message!r}"


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


def _base_repo(tmp_path, files: dict[str, str]):
    """A checkout on main; branch `phase`, pushed to a bare origin, ships `files`."""
    upstream = tmp_path / "up.git"
    upstream.mkdir()
    _git(upstream, "init", "--bare", "-b", "main")
    r = tmp_path / "target"
    r.mkdir()
    _git(r, "init", "-b", "main")
    (r / "README.md").write_text("x", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    _git(r, "remote", "add", "origin", str(upstream))
    _git(r, "push", "-u", "origin", "main")
    _git(r, "switch", "-c", "phase")
    for rel, text in files.items():
        target = r / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "phase")
    _git(r, "push", "-u", "origin", "phase")
    _git(r, "switch", "main")
    return r


def _show_fails(monkeypatch):
    """Every `git show` fails as git itself would; every other call is real."""
    real = bt._git

    def fake(repo_root, *args):
        if args and args[0] == "show":
            return subprocess.CompletedProcess(
                ["git", *args], 128, "", "fatal: simulated show failure"
            )
        return real(repo_root, *args)

    monkeypatch.setattr(bt, "_git", fake)


# =============================================================================
# The node: every failure is an error_message routed to HALT
# =============================================================================


class TestTheNodeHalts:
    def test_110_a_missing_repo_root_halts(self):
        """Compliant, pinned: the guard has always halted."""
        result = acb.analyze_codebase({"files_to_modify": [_file("a.py")]})
        assert result["error_message"]
        assert route_after_analyze(result) == "HALT"

    def test_118_no_files_to_modify_halts(self, tmp_path):
        result = acb.analyze_codebase(_state(tmp_path, []))
        _halts(result, "no files")

    def test_183_a_modify_target_that_does_not_exist_halts(self, tmp_path):
        result = acb.analyze_codebase(_state(tmp_path, [_file("src/gone.py")]))
        _halts(result, "src/gone.py", "Modify")

    def test_183_a_delete_target_that_does_not_exist_halts(self, tmp_path):
        result = acb.analyze_codebase(_state(tmp_path, [_file("src/gone.py", "Delete")]))
        _halts(result, "src/gone.py", "Delete")

    def test_196_a_modify_target_that_is_a_directory_halts(self, tmp_path):
        (tmp_path / "src" / "pkg").mkdir(parents=True)
        result = acb.analyze_codebase(_state(tmp_path, [_file("src/pkg")]))
        _halts(result, "src/pkg", "not a file")

    def test_216_a_modify_target_that_cannot_be_read_halts(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "latin.py").write_bytes(NOT_UTF8)
        result = acb.analyze_codebase(_state(tmp_path, [_file("src/latin.py")]))
        _halts(result, "src/latin.py", "UnicodeDecodeError")

    def test_261_an_unknown_change_type_halts(self, tmp_path):
        result = acb.analyze_codebase(_state(tmp_path, [_file("src/a.py", "Rename")]))
        _halts(result, "src/a.py", "'Rename'")

    def test_310_a_target_file_that_does_not_parse_halts(self, tmp_path):
        """interface_surface raises on unparseable Python since #3779; the node
        turns that into a halt naming the file and the line."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "broken.py").write_text(BROKEN_PY, encoding="utf-8")
        result = acb.analyze_codebase(_state(tmp_path, [_file("src/broken.py")]))
        _halts(result, "src/broken.py", "line 1")

    def test_the_first_file_that_fails_stops_the_loop(self, tmp_path):
        """A loop stops at the item that fails, and nothing partial is returned."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "good.py").write_text("def good():\n    pass\n", encoding="utf-8")
        result = acb.analyze_codebase(_state(tmp_path, [
            _file("src/one.py"), _file("src/good.py"),
        ]))
        _halts(result, "src/one.py")
        assert result["current_state_snapshots"] == {}
        assert "gathered_symbols" not in result

    def test_567_an_unreadable_pattern_file_halts_the_node(self, tmp_path):
        nodes = tmp_path / "assemblyzero" / "workflows" / "other" / "nodes"
        nodes.mkdir(parents=True)
        (nodes / "bad.py").write_bytes(NOT_UTF8)
        result = acb.analyze_codebase(_state(
            tmp_path, [_file("assemblyzero/workflows/new/nodes/n.py", "Add")],
        ))
        _halts(result, "bad.py", "UnicodeDecodeError")

    def test_831_an_unreadable_claude_md_halts_the_node(self, tmp_path):
        (tmp_path / "CLAUDE.md").mkdir()
        (tmp_path / "src").mkdir()
        result = acb.analyze_codebase(_state(tmp_path, [_file("src/new.py", "Add")]))
        _halts(result, "CLAUDE.md")

    def test_a_base_not_on_origin_halts_the_node(self, tmp_path):
        """base_tree raises BaseTreeError (#3585); the node halts with it."""
        repo = _base_repo(tmp_path, {"src/a.py": "def a():\n    pass\n"})
        result = acb.analyze_codebase(_state(
            repo, [_file("src/new.py", "Add")], base_branch="no-such-branch",
        ))
        _halts(result, "BaseTreeError", "origin/no-such-branch")

    def test_a_base_file_that_does_not_parse_halts_the_node(self, tmp_path):
        repo = _base_repo(tmp_path, {"src/broken.py": BROKEN_PY})
        result = acb.analyze_codebase(_state(
            repo, [_file("src/new.py", "Add")], base_branch="phase",
        ))
        _halts(result, "src/broken.py", "origin/phase")

    def test_the_halt_is_loud_on_stderr(self, tmp_path, capsys):
        acb.analyze_codebase(_state(tmp_path, [_file("src/gone.py")]))
        err = capsys.readouterr().err
        assert "ERROR" in err and "src/gone.py" in err

    def test_an_add_whose_parent_does_not_exist_yet_is_not_a_failure(self, tmp_path):
        """Kept: an Add may create its package; the implementation makes the
        directory. Absence here is the plan, not a failure."""
        result = acb.analyze_codebase(_state(tmp_path, [_file("src/newpkg/mod.py", "Add")]))
        assert result["error_message"] == ""

    def test_a_clean_analysis_passes(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "good.py").write_text("def good():\n    pass\n", encoding="utf-8")
        result = acb.analyze_codebase(_state(tmp_path, [_file("src/good.py")]))
        assert result["error_message"] == ""
        assert "src/good.py" in result["current_state_snapshots"]
        assert "good" in result["gathered_symbols"]

    def test_a_modify_target_present_only_on_the_base_is_read_from_it(self, tmp_path):
        """Kept (#2033): a Modify absent from the checkout is read from the base."""
        repo = _base_repo(tmp_path, {"src/telltale.py": "def peak():\n    return 1\n"})
        result = acb.analyze_codebase(_state(
            repo, [_file("src/telltale.py")], base_branch="phase",
        ))
        assert result["error_message"] == ""
        assert "peak" in result["gathered_symbols"]


# =============================================================================
# The helpers: a file they need and cannot read raises, naming it
# =============================================================================


def _bad_file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(NOT_UTF8)
    return path


class TestPatternFilesRaise:
    def test_567_an_unreadable_node_pattern_raises(self, tmp_path):
        bad = _bad_file(tmp_path / "assemblyzero" / "workflows" / "wf" / "nodes" / "bad.py")
        with pytest.raises(acb.CodebaseReadError, match="bad.py"):
            acb._find_node_patterns(
                "assemblyzero/workflows/new/nodes/x.py", bad.parents[2], tmp_path, set(),
            )

    def test_627_an_unreadable_state_pattern_raises(self, tmp_path):
        bad = _bad_file(tmp_path / "assemblyzero" / "workflows" / "wf" / "state.py")
        with pytest.raises(acb.CodebaseReadError, match="state.py"):
            acb._find_state_patterns(bad.parents[1], tmp_path, set())

    def test_676_an_unreadable_graph_pattern_raises(self, tmp_path):
        bad = _bad_file(tmp_path / "assemblyzero" / "workflows" / "wf" / "graph.py")
        with pytest.raises(acb.CodebaseReadError, match="graph.py"):
            acb._find_graph_patterns(bad.parents[1], tmp_path, set())

    def test_734_an_unreadable_test_pattern_raises(self, tmp_path):
        _bad_file(tmp_path / "tests" / "test_workflow_x.py")
        with pytest.raises(acb.CodebaseReadError, match="test_workflow_x.py"):
            acb._find_test_patterns("tests/test_new.py", tmp_path, set())

    def test_782_an_unreadable_tool_pattern_raises(self, tmp_path):
        _bad_file(tmp_path / "tools" / "run_x.py")
        with pytest.raises(acb.CodebaseReadError, match="run_x.py"):
            acb._find_tool_patterns(tmp_path, set())

    def test_readable_patterns_are_found(self, tmp_path):
        nodes = tmp_path / "assemblyzero" / "workflows" / "wf" / "nodes"
        nodes.mkdir(parents=True)
        (nodes / "load.py").write_text("def load(s):\n    pass\n", encoding="utf-8")
        found = acb._find_node_patterns(
            "assemblyzero/workflows/new/nodes/x.py", nodes.parents[1], tmp_path, set(),
        )
        assert [p["file_path"] for p in found] == ["assemblyzero/workflows/wf/nodes/load.py"]


class TestProjectContextRaises:
    @pytest.mark.parametrize(
        "name", [
            pytest.param("CLAUDE.md", id="831"),
            pytest.param("README.md", id="843"),
            pytest.param("pyproject.toml", id="871"),
        ],
    )
    def test_831_843_871_an_unreadable_project_file_raises(self, tmp_path, name):
        (tmp_path / name).mkdir()  # exists, and cannot be read as a file
        with pytest.raises(acb.CodebaseReadError, match=name):
            acb._build_project_context(tmp_path)

    def test_absent_project_files_are_no_context(self, tmp_path):
        """Kept: a repo without CLAUDE.md, README or pyproject has none to give."""
        assert acb._build_project_context(tmp_path) == ""


class TestImportDependenciesRaise:
    def test_914_a_file_to_modify_that_does_not_parse_raises(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "broken.py").write_text(BROKEN_PY, encoding="utf-8")
        with pytest.raises(acb.CodebaseReadError, match="src/broken.py"):
            acb._extract_import_dependencies([_file("src/broken.py")], tmp_path)

    def test_914_a_file_to_modify_that_cannot_be_read_raises(self, tmp_path):
        _bad_file(tmp_path / "src" / "latin.py")
        with pytest.raises(acb.CodebaseReadError, match="UnicodeDecodeError"):
            acb._extract_import_dependencies([_file("src/latin.py")], tmp_path)

    def test_a_file_not_yet_written_has_no_imports(self, tmp_path):
        """Kept: an Add that does not exist yet imports nothing."""
        assert acb._extract_import_dependencies([_file("src/new.py", "Add")], tmp_path) == ""


class TestTheBaseSweepRaises:
    def test_947_a_base_git_cannot_list_raises(self, tmp_path):
        repo = _base_repo(tmp_path, {"src/a.py": "def a():\n    pass\n"})
        with pytest.raises(bt.BaseTreeError, match="origin/no-such-branch"):
            acb._list_base_python_files(repo, "origin/no-such-branch")

    def test_959_and_1037_the_sweep_is_not_capped(self, tmp_path):
        files = {f"src/mod_{i:03d}.py": f"def fn_{i:03d}():\n    pass\n" for i in range(201)}
        repo = _base_repo(tmp_path, files)

        assert len(acb._list_base_python_files(repo, "origin/phase")) == 201
        assert "fn_200" in acb._extract_symbols_from_base(repo, "origin/phase")

    def test_988_a_base_file_git_cannot_show_raises(self, tmp_path, monkeypatch):
        repo = _base_repo(tmp_path, {"src/a.py": "def a():\n    pass\n"})
        _show_fails(monkeypatch)
        with pytest.raises(bt.BaseTreeError, match="src/a.py"):
            acb._base_api_surface(repo, "origin/phase")

    def test_1024_a_base_git_cannot_list_raises(self, tmp_path):
        repo = _base_repo(tmp_path, {"src/a.py": "def a():\n    pass\n"})
        with pytest.raises(bt.BaseTreeError, match="origin/no-such-branch"):
            acb._extract_symbols_from_base(repo, "origin/no-such-branch")

    def test_1044_a_base_file_git_cannot_show_raises(self, tmp_path, monkeypatch):
        repo = _base_repo(tmp_path, {"src/a.py": "def a():\n    pass\n"})
        _show_fails(monkeypatch)
        with pytest.raises(bt.BaseTreeError, match="src/a.py"):
            acb._extract_symbols_from_base(repo, "origin/phase")

    def test_1054_a_base_file_that_does_not_parse_raises(self, tmp_path):
        """It used to be regex-scraped, the fallback #2393 removed elsewhere."""
        repo = _base_repo(tmp_path, {"src/broken.py": BROKEN_PY})
        with pytest.raises(acb.CodebaseReadError, match="src/broken.py"):
            acb._extract_symbols_from_base(repo, "origin/phase")

    def test_an_unparseable_base_file_raises_from_the_api_surface(self, tmp_path):
        """interface_surface raises since #3779; the surface names the file."""
        repo = _base_repo(tmp_path, {"src/broken.py": BROKEN_PY})
        with pytest.raises(acb.CodebaseReadError, match="src/broken.py"):
            acb._base_api_surface(repo, "origin/phase")

    def test_an_empty_base_file_is_skipped_quietly(self, tmp_path):
        """Kept: an empty __init__.py has no interface; that is an answer."""
        repo = _base_repo(tmp_path, {"src/__init__.py": "", "src/a.py": "def a():\n    pass\n"})
        surface = acb._base_api_surface(repo, "origin/phase")
        assert "src/a.py" in surface
        assert "src/__init__.py" not in surface


class TestGatheredSymbols:
    def test_1127_the_symbol_list_alone_raises_on_an_unparseable_file(self):
        with pytest.raises(acb.CodebaseReadError, match="broken.py"):
            acb._extract_symbols_from_files([
                {"path": "broken.py", "change_type": "Modify", "description": "",
                 "current_content": BROKEN_PY},
            ])

    def test_1127_the_gather_still_names_what_did_not_parse(self):
        """Kept: gather_symbols reports every unreadable file; the node halts."""
        gather = acb.gather_symbols([
            {"path": "broken.py", "change_type": "Modify", "description": "",
             "current_content": BROKEN_PY},
        ])
        assert [p for p, _ in gather.unreadable] == ["broken.py"]
        assert "halts" in gather.describe()

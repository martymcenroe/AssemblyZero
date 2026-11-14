"""#4271: N1's import map covers a Modify target that exists only on the base.

``_extract_import_dependencies`` built the map from the files on disk, so a
Modify target an earlier phase landed on the base branch (and not yet in the
checkout) was skipped, and the drafter saw no imports for it, although N1 had
already read that same file from the base for its excerpt (#2033). The map now
reads such a target from the base tree, and a Modify target found nowhere
raises, naming it.
"""
from __future__ import annotations

import importlib
import subprocess

import pytest

from assemblyzero.workflows.implementation_spec.graph import route_after_analyze

# `nodes/__init__` re-exports the FUNCTION analyze_codebase, which shadows the
# module of the same name, so the module is imported by its dotted path.
acb = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.analyze_codebase"
)

TELLTALE = (
    "from src.peaks import Peak\n"
    "from src.units import kpa\n\n\n"
    "def peak():\n"
    "    return Peak(kpa(1))\n"
)
BROKEN_PY = "class Broken\n    def m(self):\n        pass\n"


def _file(path: str, change_type: str = "Modify") -> dict:
    return {"path": path, "change_type": change_type, "description": "d",
            "current_content": None}


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


class TestTheNodeMapsABaseOnlyTarget:
    def test_t1_a_base_only_modify_target_appears_in_the_import_map(self, tmp_path):
        repo = _base_repo(tmp_path, {"src/telltale.py": TELLTALE})
        assert not (repo / "src" / "telltale.py").exists(), "the checkout must lack it"

        result = acb.analyze_codebase({
            "issue_number": 42, "repo_root": str(repo), "lld_content": "",
            "files_to_modify": [_file("src/telltale.py")], "base_branch": "phase",
        })

        assert result["error_message"] == ""
        deps = result["import_dependencies"]
        assert "telltale.py" in deps, deps
        assert "src.peaks" in deps and "src.units" in deps


class TestTheHelper:
    def test_a_base_only_target_is_read_from_the_base(self, tmp_path):
        repo = _base_repo(tmp_path, {"src/telltale.py": TELLTALE})
        deps = acb._extract_import_dependencies(
            [_file("src/telltale.py")], repo, "origin/phase",
        )
        assert "telltale.py" in deps and "src.peaks" in deps

    def test_a_base_only_target_with_a_bom_is_read(self, tmp_path):
        """The base read drops a BOM as the checkout's utf-8-sig read does (#2507)."""
        repo = _base_repo(tmp_path, {"src/telltale.py": "﻿" + TELLTALE})
        deps = acb._extract_import_dependencies(
            [_file("src/telltale.py")], repo, "origin/phase",
        )
        assert "src.peaks" in deps

    def test_the_checkout_copy_wins_over_the_base(self, tmp_path):
        repo = _base_repo(tmp_path, {"src/telltale.py": TELLTALE})
        (repo / "src").mkdir()
        (repo / "src" / "telltale.py").write_text(
            "from src.local import here\n", encoding="utf-8",
        )
        deps = acb._extract_import_dependencies(
            [_file("src/telltale.py")], repo, "origin/phase",
        )
        assert "src.local" in deps and "src.peaks" not in deps

    @pytest.mark.parametrize("change_type", ["Modify", "Delete"])
    def test_r2_a_target_found_nowhere_raises_naming_it(self, tmp_path, change_type):
        repo = _base_repo(tmp_path, {"src/telltale.py": TELLTALE})
        with pytest.raises(acb.CodebaseReadError, match="src/gone.py") as exc:
            acb._extract_import_dependencies(
                [_file("src/gone.py", change_type)], repo, "origin/phase",
            )
        assert "origin/phase" in str(exc.value)

    def test_r2_without_a_base_a_missing_target_raises_naming_it(self, tmp_path):
        with pytest.raises(acb.CodebaseReadError, match="src/gone.py"):
            acb._extract_import_dependencies([_file("src/gone.py")], tmp_path)

    def test_a_base_only_target_that_does_not_parse_raises_naming_the_base(self, tmp_path):
        repo = _base_repo(tmp_path, {"src/broken.py": BROKEN_PY})
        with pytest.raises(acb.CodebaseReadError, match="src/broken.py on origin/phase"):
            acb._extract_import_dependencies(
                [_file("src/broken.py")], repo, "origin/phase",
            )

    def test_an_add_not_yet_written_still_has_no_imports(self, tmp_path):
        """Kept: an Add that does not exist yet imports nothing."""
        repo = _base_repo(tmp_path, {"src/telltale.py": TELLTALE})
        assert acb._extract_import_dependencies(
            [_file("src/new.py", "Add")], repo, "origin/phase",
        ) == ""

    def test_a_node_halt_on_a_missing_target_still_routes_to_halt(self, tmp_path):
        result = acb.analyze_codebase({
            "issue_number": 42, "repo_root": str(tmp_path), "lld_content": "",
            "files_to_modify": [_file("src/gone.py")],
        })
        assert route_after_analyze(result) == "HALT"
        assert "src/gone.py" in result["error_message"]

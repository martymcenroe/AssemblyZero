"""Every shutil.rmtree on the workflow path names its gate (#3518, #3231, #3528).

The shell guard denies `rm -rf` to the agent; `shutil.rmtree` is the same
operation and no guard sees it. This walks `assemblyzero/` and `tools/` with
`ast` (a parser, not a text search) for every `shutil.rmtree(...)` call and
every call through a `from shutil import rmtree` alias, and fails on any site
not in ALLOWLIST -- and on any ALLOWLIST entry whose site has gone, so the
list cannot rot into a permission slip.

A site gets onto the list only by deleting something the same code created
and asserting so before it deletes. Everything else became a move-aside.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("assemblyzero", "tools")

#: (path, enclosing qualname) -> the gate, in words. Each gate is enforced by
#: code at the site, not by this comment.
ALLOWLIST: dict[tuple[str, str], str] = {
    ("assemblyzero/speedrun/archive.py", "_rmtree"):
        "a previous archive of the same run; _is_our_archive() refuses any "
        "directory without the archive's own logs/ or index.json",
    ("assemblyzero/visual_gate/gate.py", "render_round"):
        "the cand-<key>-<n> directory sub.mkdir() made in the same iteration "
        "(no exist_ok); asserted to sit in round_dir",
    ("assemblyzero/workflows/testing/nodes/adversarial_writer.py", "write_adversarial_tests"):
        "the staging directory mkdtemp() made in this call inside output_dir; "
        "asserted before removal",
    ("assemblyzero/workflows/testing/nodes/verify_phases.py", "_hill_climb"):
        "this function's own best-iteration snapshot, rewritten on the next "
        "line; asserted by name and parent",
    ("tools/archive_worktree_lineage.py", "clean_ephemeral"):
        "a closed list of caches, only inside a LINKED worktree "
        "(require_linked_worktree, #3528)",
    ("tools/dependabot_review.py", "_remove_node_modules"):
        "node_modules inside the audit's own linked worktree (#1839); refuses "
        "in a main checkout",
    ("tools/speedrun_reset.py", "_rmtree_clearing_readonly"):
        "a lineage directory already copied to its archive, asserted present "
        "first; the unregistered-worktree caller now moves aside instead",
}


def _rmtree_sites(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    aliases = {
        a.asname or a.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "shutil"
        for a in node.names
        if a.name == "rmtree"
    }
    found: list[tuple[int, str]] = []
    stack: list[str] = []

    def visit(node: ast.AST) -> None:
        named = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        if named:
            stack.append(node.name)
        if isinstance(node, ast.Call):
            f = node.func
            if (
                isinstance(f, ast.Attribute) and f.attr == "rmtree"
                and isinstance(f.value, ast.Name) and f.value.id == "shutil"
            ) or (isinstance(f, ast.Name) and f.id in aliases):
                found.append((node.lineno, stack[-1] if stack else "<module>"))
        for child in ast.iter_child_nodes(node):
            visit(child)
        if named:
            stack.pop()

    visit(tree)
    return found


@pytest.fixture(scope="module")
def sites() -> dict[tuple[str, str], list[int]]:
    out: dict[tuple[str, str], list[int]] = {}
    for sub in SCANNED:
        for path in sorted((ROOT / sub).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            for line, qual in _rmtree_sites(path):
                out.setdefault((rel, qual), []).append(line)
    return out


class TestEveryRmtreeNamesItsGate:
    def test_no_site_is_missing_from_the_allowlist(self, sites):
        unlisted = sorted(
            f"{path}:{lines[0]} {qual}" for (path, qual), lines in sites.items()
            if (path, qual) not in ALLOWLIST
        )
        assert not unlisted, (
            "shutil.rmtree on the workflow path with no named gate (#3518). "
            "Move the target aside instead, or assert the code created it and "
            "add it to ALLOWLIST with the gate:\n  " + "\n  ".join(unlisted)
        )

    def test_no_allowlist_entry_outlives_its_site(self, sites):
        stale = sorted(f"{p} {q}" for (p, q) in ALLOWLIST if (p, q) not in sites)
        assert not stale, "remove these ALLOWLIST entries:\n  " + "\n  ".join(stale)

    def test_the_walk_sees_the_sites_it_should(self, sites):
        """A walker that found nothing would pass the first test by vacuum."""
        assert len(sites) == len(ALLOWLIST) == 7

    def test_the_walker_catches_an_alias(self, tmp_path):
        f = tmp_path / "m.py"
        f.write_text(
            "from shutil import rmtree as nuke\n"
            "def go(p):\n    nuke(p)\n",
            encoding="utf-8",
        )
        assert _rmtree_sites(f) == [(3, "go")]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r


def _repo(root: Path) -> Path:
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


class TestTheSitesThatBecameMoveAsides:
    def test_create_worktree_moves_a_non_worktree_aside(self, tmp_path):
        """#3231: a `Repo-42` with no .git was rmtree'd, unattended."""
        from tools.run_implement_from_lld import create_worktree

        repo = _repo(tmp_path / "Repo")
        squatter = tmp_path / "Repo-42"
        squatter.mkdir()
        (squatter / "work.txt").write_text("uncommitted\n", encoding="utf-8")

        path, error = create_worktree(repo, 42)

        assert error == ""
        backups = list(tmp_path.glob("Repo-42.bak-*"))
        assert len(backups) == 1
        assert (backups[0] / "work.txt").read_text(encoding="utf-8") == "uncommitted\n"
        assert (path / ".git").exists()

    def test_the_oldest_lineage_generation_is_moved_not_deleted(self, tmp_path):
        from assemblyzero.workflows.requirements.audit import (
            AUDIT_ACTIVE_DIR, shift_lineage_versions,
        )

        active = tmp_path / AUDIT_ACTIVE_DIR
        for suffix in ("", "-n1", "-n2"):
            d = active / f"42-lld{suffix}"
            d.mkdir(parents=True)
            (d / "001-issue.md").write_text(suffix or "current", encoding="utf-8")

        shift_lineage_versions(42, tmp_path)

        discarded = list((tmp_path / "docs" / "lineage" / "discarded").glob("42-lld-n2-*"))
        assert len(discarded) == 1
        assert (discarded[0] / "001-issue.md").read_text(encoding="utf-8") == "-n2"

    def test_speedrun_reset_moves_an_unregistered_directory_aside(self, tmp_path):
        """A clean `git status` held in a separate clone with unpushed
        commits; the reset deleted it."""
        from tools.speedrun_reset import _remove_worktree_at

        repo = _repo(tmp_path / "Repo")
        clone = _repo(tmp_path / "Repo-42")
        (clone / "unpushed.txt").write_text("u\n", encoding="utf-8")
        _git(clone, "add", ".")
        _git(clone, "commit", "-qm", "unpushed")

        _remove_worktree_at(repo, clone)

        backups = list(tmp_path.glob("Repo-42.bak-*"))
        assert len(backups) == 1
        assert (backups[0] / "unpushed.txt").exists()

    def test_archive_lineage_moves_a_previous_archive_aside(self, tmp_path):
        from tools.archive_worktree_lineage import archive_lineage

        wt = tmp_path / "wt"
        (wt / "docs" / "lineage" / "active" / "42-testing").mkdir(parents=True)
        (wt / "docs" / "lineage" / "active" / "42-testing" / "new.md").write_text("n", encoding="utf-8")
        main = tmp_path / "main"
        old = main / "docs" / "lineage" / "archived" / "42-testing"
        old.mkdir(parents=True)
        (old / "old.md").write_text("o", encoding="utf-8")

        archive_lineage(wt, 42, main)

        prev = list(old.parent.glob("42-testing.prev-*"))
        assert len(prev) == 1 and (prev[0] / "old.md").exists()
        assert (old / "new.md").exists()


class TestTheSitesThatAssertOwnership:
    def test_archive_worktree_lineage_refuses_a_main_checkout(self, tmp_path, monkeypatch):
        """#3528: run against a main checkout it emptied __pycache__ and
        would have evicted the venv."""
        import tools.archive_worktree_lineage as awl

        repo = _repo(tmp_path / "Repo")
        (repo / "__pycache__").mkdir()
        (repo / "__pycache__" / "x.pyc").write_bytes(b"\0")
        (repo / ".coverage").write_text("c", encoding="utf-8")
        called = []
        monkeypatch.setattr(awl.subprocess, "run", _spy(awl.subprocess.run, called))

        with pytest.raises(SystemExit, match="REFUSED"):
            awl.clean_ephemeral(repo)
        with pytest.raises(SystemExit, match="REFUSED"):
            awl.evict_poetry_venv(repo)

        assert (repo / "__pycache__" / "x.pyc").exists()
        assert (repo / ".coverage").exists()
        assert not any("env" in c and "remove" in c for c in called)

    def test_archive_worktree_lineage_cleans_a_linked_worktree(self, tmp_path):
        import tools.archive_worktree_lineage as awl

        repo = _repo(tmp_path / "Repo")
        wt = tmp_path / "Repo-42"
        _git(repo, "worktree", "add", "-q", "--detach", str(wt))
        (wt / "__pycache__").mkdir()
        (wt / "__pycache__" / "x.pyc").write_bytes(b"\0")

        awl.clean_ephemeral(wt)

        assert not (wt / "__pycache__").exists()

    def test_speedrun_archive_refuses_a_directory_it_did_not_write(self, tmp_path):
        from assemblyzero.speedrun.archive import _rmtree

        foreign = tmp_path / "someones-dir"
        foreign.mkdir()
        (foreign / "precious.txt").write_text("p", encoding="utf-8")

        with pytest.raises(RuntimeError, match="not an archive this tool wrote"):
            _rmtree(foreign)
        assert (foreign / "precious.txt").exists()

    def test_the_adversarial_writer_stages_inside_its_output_dir(self, tmp_path, monkeypatch):
        """It staged in the OS temp directory: a hidden location, and a
        different filesystem, across which the 'atomic' move was a copy."""
        import tempfile

        from assemblyzero.workflows.testing.nodes import adversarial_writer as aw

        seen: list[str] = []
        real = tempfile.mkdtemp

        def spy(*a, **kw):
            path = real(*a, **kw)
            seen.append(path)
            return path

        monkeypatch.setattr(aw.tempfile, "mkdtemp", spy)
        out = tmp_path / "tests" / "adversarial"
        analysis = {
            "uncovered_edge_cases": [], "false_claims": [],
            "missing_error_handling": [], "implicit_assumptions": [],
            "test_cases": [{
                "test_id": "ADV_001", "target_function": "m.f", "category": "boundary",
                "description": "d", "test_code": "def test_b():\n    assert True",
                "claim_challenged": "c", "severity": "high",
            }],
        }
        aw.write_adversarial_tests(analysis, issue_id=42, output_dir=str(out))

        assert seen and Path(seen[0]).parent.resolve() == out.resolve()
        assert not any(p.name.startswith(".adversarial_") for p in out.iterdir())


def _spy(real, calls):
    def run(cmd, *a, **kw):
        calls.append(list(cmd))
        return real(cmd, *a, **kw)
    return run

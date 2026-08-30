"""First-party imports consult the run's base ref before failing (#2667).

run-issue379-002604: the spec stage validated imports against the checkout —
the default branch, per #2012 — while the run built on an arc that shipped the
module. `boostgauge.skins.stingray` was declared nonexistent on every revision
while pinning reverted the drafter's responses: the #2555 deadlock, driven by a
complaint that was false for the tree the run builds on.

The repair mirrors `_import_resolves`'s candidate set against
`base_tree.exists_on_base`. Empty `base_branch` preserves the filesystem-only
behaviour byte-for-byte, which the standalone runner relies on.
"""

import subprocess

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_import_targets_exist,
)


def _git(repo, *args):
    subprocess.run(
        ["git", *args], cwd=str(repo), check=True, capture_output=True, text=True
    )


def _make_arc_repo(tmp_path):
    """A src-layout repo whose default branch lacks the skins module and whose
    arc ships it — the run-issue379-002604 shape, miniaturised.

    Ends checked out on the default branch, so the filesystem genuinely lacks
    the module the arc carries.
    """
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@test")
    _git(tmp_path, "config", "user.name", "test")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "myproj"\n'
        'packages = [{include = "myproj", from = "src"}]\n',
        encoding="utf-8",
    )
    pkg = tmp_path / "src" / "myproj"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "base: package without skins")
    _git(tmp_path, "checkout", "-q", "-b", "arc")
    skins = pkg / "skins"
    skins.mkdir()
    (skins / "__init__.py").write_text("", encoding="utf-8")
    (skins / "stingray.py").write_text("x = 1", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "arc: ships skins.stingray")
    _git(tmp_path, "checkout", "-q", "main")
    return tmp_path


SPEC = "# Spec\n\n```python\nfrom myproj.skins.stingray import render_face\n```\n"

#: Modify, not Add — so `new_file_paths` cannot forgive it and the resolution
#: question lands squarely on checkout-versus-base, the #2667 seam.
FILES = [{"path": "src/myproj/skins/stingray.py", "change_type": "Modify"}]


class TestArcShippedModuleResolvesViaBase:
    def test_the_379_shape_passes_when_the_base_ships_the_module(self, tmp_path):
        repo = _make_arc_repo(tmp_path)
        result = check_import_targets_exist(SPEC, FILES, str(repo), "arc")
        assert result["passed"], result["details"]

    def test_without_base_branch_the_same_spec_still_fails(self, tmp_path):
        """The standalone runner passes no base — today's behaviour holds."""
        repo = _make_arc_repo(tmp_path)
        result = check_import_targets_exist(SPEC, FILES, str(repo), "")
        assert not result["passed"]
        assert "myproj.skins.stingray" in result["details"]
        # No base was consulted, so the message must not claim one was.
        assert "run's base" not in result["details"]


class TestAbsentEverywhereStillFails:
    def test_module_on_neither_tree_fails_and_names_the_base(self, tmp_path):
        """A truly absent package still fails — and the complaint now states
        that the base was consulted, so it cannot be read as never looking.

        `myproj.nowhere.thing` has no parent package on either tree, so the
        parent-forgiveness clause cannot rescue it.
        """
        repo = _make_arc_repo(tmp_path)
        spec = "# Spec\n\n```python\nfrom myproj.nowhere.thing import x\n```\n"
        result = check_import_targets_exist(spec, FILES, str(repo), "arc")
        assert not result["passed"]
        assert "myproj.nowhere.thing" in result["details"]
        assert "run's base" in result["details"]
        assert "arc" in result["details"]

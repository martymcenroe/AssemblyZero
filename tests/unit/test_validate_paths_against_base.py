"""The LLD path validator must accept files the base ships (#2056).

boostgauge #2, run-issue2-221951, lld failed 84.4s:

    MECHANICAL VALIDATION FAILED:
      1. File marked Modify but does not exist: src/boostgauge/skins/stingray.py
      2. File marked Modify but does not exist: src/boostgauge/gauge.py

Both files exist -- #1 landed them on origin/hardening-run-14. The validator
checks the CHECKOUT, which sits on the default branch and mid-arc carries none
of the arc. So the CORRECT plan (Modify what an earlier phase built) was
rejected, while a wrong Add for the same file sailed through -- the validator
was steering the drafter toward the overwrite bug #2032 exists to prevent.

Fourth organ of the two-trees disease: #2021 clean-check, #2033 spec planning,
#2052 symbol universe, now LLD path validation.
"""

import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
    validate_file_paths,
)


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path):
    upstream = tmp_path / "up.git"
    upstream.mkdir()
    _git(upstream, "init", "--bare", "-b", "main")

    r = tmp_path / "boostgauge"
    r.mkdir()
    _git(r, "init", "-b", "main")
    (r / "README.md").write_text("x", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    _git(r, "remote", "add", "origin", str(upstream))
    _git(r, "push", "-u", "origin", "main")

    _git(r, "checkout", "-b", "hardening-run-14")
    (r / "src").mkdir()
    (r / "src" / "gauge.py").write_text("def render(): pass\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "phase 3")
    _git(r, "push", "-u", "origin", "hardening-run-14")
    _git(r, "checkout", "main")
    return r


def _entry(path, change_type="Modify"):
    return {"path": path, "change_type": change_type, "is_directory": False}


class TestBaseFilesAreLegitimateModifyTargets:
    def test_the_live_rejection_no_longer_fires(self, repo):
        """gauge.py exists only on the base; the checkout lacks it."""
        assert not (repo / "src" / "gauge.py").exists()
        errors = validate_file_paths(
            [_entry("src/gauge.py")], repo, base_branch="hardening-run-14"
        )
        assert errors == []

    def test_a_genuinely_missing_file_is_still_rejected(self, repo):
        errors = validate_file_paths(
            [_entry("src/nope.py")], repo, base_branch="hardening-run-14"
        )
        assert len(errors) == 1
        assert "does not exist" in errors[0].message

    def test_no_base_branch_keeps_the_old_behavior(self, repo):
        """A fresh feature on main: base-unaware, unchanged."""
        errors = validate_file_paths([_entry("src/gauge.py")], repo)
        assert len(errors) == 1

    def test_a_checkout_file_needs_no_base(self, repo):
        (repo / "local.py").write_text("x\n", encoding="utf-8")
        assert validate_file_paths([_entry("local.py")], repo) == []

    def test_delete_on_a_base_file_is_also_accepted(self, repo):
        errors = validate_file_paths(
            [_entry("src/gauge.py", "Delete")], repo, base_branch="hardening-run-14"
        )
        assert errors == []

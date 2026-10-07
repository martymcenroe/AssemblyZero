"""A missing first-party module's message names the one that exists (#3760).

boostgauge #2 run-issue2-040123 (2026-10-07): the spec imported
`boostgauge.stingray`; the module is `boostgauge.skins.stingray`. The check
said only that the import was missing, and the drafter guessed until the
revision cap.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_import_targets_exist,
)

PLAN = [{"path": "src/boostgauge/telltale_group.py", "change_type": "Add"}]


def _repo(tmp_path: Path) -> Path:
    skins = tmp_path / "src" / "boostgauge" / "skins"
    skins.mkdir(parents=True)
    (tmp_path / "src" / "boostgauge" / "__init__.py").write_text("", encoding="utf-8")
    (skins / "__init__.py").write_text("", encoding="utf-8")
    (skins / "stingray.py").write_text("def draw_telltales(*a): pass\n", encoding="utf-8")
    return tmp_path


def _spec(line: str) -> str:
    return f"# Spec\n\n```python\n{line}\n```\n"


def test_the_message_names_the_module_that_exists(tmp_path):
    result = check_import_targets_exist(
        _spec("from boostgauge.stingray import draw_telltales"), PLAN, str(_repo(tmp_path)),
    )
    assert not result["passed"]
    assert "did you mean" in result["details"]
    assert "`boostgauge.skins.stingray`" in result["details"]


def test_no_suggestion_when_nothing_shares_the_name(tmp_path):
    result = check_import_targets_exist(
        _spec("from boostgauge.nowhere import thing"), PLAN, str(_repo(tmp_path)),
    )
    assert not result["passed"]
    assert "did you mean" not in result["details"]


def test_a_module_only_on_the_base_is_suggested(tmp_path):
    """The checkout is the default branch; mid-arc the module may be on the base only."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, check=False)
    run("init", "-q", "-b", "main")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "Test")
    (repo / "src" / "boostgauge").mkdir(parents=True)
    (repo / "src" / "boostgauge" / "__init__.py").write_text("", encoding="utf-8")
    run("add", ".")
    run("commit", "-qm", "base")
    run("switch", "-q", "-c", "arc")
    (repo / "src" / "boostgauge" / "skins").mkdir()
    (repo / "src" / "boostgauge" / "skins" / "stingray.py").write_text("x = 1\n", encoding="utf-8")
    run("add", ".")
    run("commit", "-qm", "arc work")
    run("switch", "-q", "main")
    assert not (repo / "src" / "boostgauge" / "skins").exists()

    result = check_import_targets_exist(
        _spec("from boostgauge.stingray import x"), PLAN, str(repo), "arc",
    )
    assert not result["passed"]
    assert "`boostgauge.skins.stingray`" in result["details"]

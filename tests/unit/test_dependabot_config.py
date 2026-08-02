"""Acceptance tests for the Dependabot version-update config (#1923).

The three acceptance criteria in the issue are asserted here. The config is not
code, but it is the kind of file that silently stops matching reality — a
directory gets renamed, an ecosystem's manifest moves — and GitHub reports a
parse error on a tab nobody opens.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github/dependabot.yml"

EXPECTED = {
    ("npm", "/sentinel"): "weekly",
    ("pip", "/"): "weekly",
    ("github-actions", "/"): "monthly",
}


def _loaded() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


# --- "exists with exactly the three ecosystems, dirs and schedules" -----


def test_config_exists_and_is_valid_yaml():
    assert CONFIG.is_file()
    data = _loaded()
    assert isinstance(data, dict), "a parse error here is invisible until the tab is opened"
    assert data.get("version") == 2


def test_exactly_the_three_specified_ecosystems():
    updates = _loaded()["updates"]
    found = {
        (u["package-ecosystem"], u["directory"]): u["schedule"]["interval"]
        for u in updates
    }

    assert found == EXPECTED, "exactly three entries, with these directories and schedules"
    assert len(updates) == 3, "no extra entries"


@pytest.mark.parametrize("ecosystem,directory", sorted(EXPECTED))
def test_each_ecosystem_points_at_a_directory_that_has_its_manifest(
    ecosystem, directory
):
    """A config entry aimed at a directory with no manifest is a silent no-op."""
    target = ROOT / directory.lstrip("/")
    assert target.is_dir(), f"{directory} does not exist"

    manifests = {
        "npm": ["package.json"],
        "pip": ["pyproject.toml", "requirements.txt"],
        # github-actions is scanned from the repo root; its "manifest" is the
        # workflows directory itself.
        "github-actions": [".github/workflows"],
    }[ecosystem]

    assert any((target / m).exists() for m in manifests), (
        f"{ecosystem} at {directory} has none of {manifests}"
    )


# --- "no file under .github/workflows/ is touched" ----------------------


def test_the_config_is_not_a_workflow_file():
    """It lives in .github/ but outside .github/workflows/, which is why it
    lands by ordinary push with no elevated token."""
    assert CONFIG.parent.name == ".github"
    assert "workflows" not in CONFIG.parts, (
        "a file under .github/workflows/ needs the classic-PAT landing path"
    )


def test_the_sentinel_entry_targets_the_lockfile_that_had_the_alerts():
    """The 2026-07-29 alerts were in sentinel/package-lock.json specifically."""
    assert (ROOT / "sentinel/package-lock.json").is_file()
    npm = [u for u in _loaded()["updates"] if u["package-ecosystem"] == "npm"]
    assert [u["directory"] for u in npm] == ["/sentinel"]

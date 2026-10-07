"""The derived Projects root (#3609)."""

from pathlib import Path

import pytest

from assemblyzero.core.projects_root import PROJECTS, REPO_ROOT, spellings


def test_repo_root_is_this_checkout():
    assert (REPO_ROOT / "pyproject.toml").is_file()
    assert (REPO_ROOT / "assemblyzero" / "core" / "projects_root.py").is_file()


def test_projects_is_the_checkouts_parent():
    assert PROJECTS == REPO_ROOT.parent


@pytest.mark.parametrize(
    "path",
    [
        "C:\\Users\\dev\\Projects",
        "C:/Users/dev/Projects",
        "c:\\Users\\dev\\Projects\\",
        "/c/Users/dev/Projects",
        "/mnt/c/Users/dev/Projects",
        "/mnt/c/Users/dev/Projects/",
    ],
)
def test_every_drive_spelling_gives_the_same_three(path):
    assert spellings(path) == {
        "windows": "C:\\Users\\dev\\Projects",
        "git_bash": "/c/Users/dev/Projects",
        "wsl": "/mnt/c/Users/dev/Projects",
    }


def test_a_path_on_no_drive_has_one_spelling():
    assert spellings("/home/runner/work/AssemblyZero") == {
        "windows": "/home/runner/work/AssemblyZero",
        "git_bash": "/home/runner/work/AssemblyZero",
        "wsl": "/home/runner/work/AssemblyZero",
    }


def test_a_longer_top_directory_is_not_a_drive():
    assert spellings("/home/dev")["git_bash"] == "/home/dev"
    assert spellings("/mnt/data/x")["wsl"] == "/mnt/data/x"


def test_the_default_is_the_projects_root():
    assert spellings() == spellings(PROJECTS)
    assert Path(spellings()["wsl"]).name == PROJECTS.name or spellings()["wsl"].endswith(PROJECTS.name)

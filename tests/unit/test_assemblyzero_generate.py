"""assemblyzero-generate.py reaches AssemblyZero by its real path (#4775, #4776).

- #4775: project.json's `inherit_from` names AssemblyZero in whatever spelling
  the side that created the repository wrote. The generator turns it into a
  path on the side it runs on, so an old file holding `C:\\...` works on
  Ubuntu too.
- #4776: templates reached AssemblyZero as `{{PROJECT_ROOT}}/../AssemblyZero`,
  a sibling of the repository. Beside a repository on Ubuntu's ext4 disk there
  is no such sibling. They now use `{{ASSEMBLYZERO_ROOT}}`, which the generator
  fills from `inherit_from`.

Every path here is a temporary one or another user's (`someone`): no test
spells the operator's own Projects root (#3609).

Issues: #4775, #4776
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GENERATOR = REPO_ROOT / "tools" / "assemblyzero-generate.py"
CLEANUP_TEMPLATE = REPO_ROOT / ".claude" / "templates" / "commands" / "cleanup.md.template"


def load_generator():
    """The generator as a module; its file name holds a hyphen."""
    spec = importlib.util.spec_from_file_location("assemblyzero_generate", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generate = load_generator()
inherit_from_path = generate.inherit_from_path

#: Another user's AssemblyZero on the C: drive, in each drive spelling.
DRIVE_SPELLINGS = {
    "windows": "C:\\Users\\someone\\Projects\\AssemblyZero",
    "windows-forward": "C:/Users/someone/Projects/AssemblyZero",
    "git-bash": "/c/Users/someone/Projects/AssemblyZero",
    "wsl-mount": "/mnt/c/Users/someone/Projects/AssemblyZero",
}

WINDOWS_DRIVE_PATH = "C:\\Users\\someone\\Projects\\AssemblyZero"


def _make_assemblyzero(root: Path) -> Path:
    """A temporary AssemblyZero holding `.claude/templates`."""
    (root / ".claude" / "templates").mkdir(parents=True)
    return root


def _ext4_spellings(posix: str) -> dict[str, str]:
    """A POSIX path as Ubuntu, and as Windows names it through the WSL share."""
    return {
        "posix": posix,
        "wsl-share": "\\\\wsl.localhost\\Ubuntu" + posix.replace("/", "\\"),
        "wsl-share-forward": "//wsl.localhost/Ubuntu" + posix,
    }


# ===========================================================================
# #4775 T1: inherit_from in any spelling, on either side
# ===========================================================================


class TestInheritFromOnUbuntu:
    """windows=False: the generator runs on Ubuntu."""

    @pytest.mark.parametrize("spelling", sorted(DRIVE_SPELLINGS))
    def test_a_drive_spelling_opens_through_the_drive_mount(self, tmp_path, spelling):
        mount = tmp_path / "mnt"
        az = _make_assemblyzero(mount / "c" / "Users" / "someone" / "Projects" / "AssemblyZero")
        root = inherit_from_path(
            DRIVE_SPELLINGS[spelling], windows=False, mount_root=mount.as_posix())
        assert root == az.as_posix()
        assert (Path(root) / ".claude" / "templates").is_dir()

    def test_the_default_mount_is_wsls(self):
        assert inherit_from_path(WINDOWS_DRIVE_PATH, windows=False) == (
            "/mnt/c/Users/someone/Projects/AssemblyZero")

    @pytest.mark.parametrize("spelling", ["posix", "wsl-share", "wsl-share-forward"])
    def test_an_ext4_spelling_opens_as_its_posix_path(self, tmp_path, spelling):
        az = _make_assemblyzero(tmp_path / "home" / "someone" / "AssemblyZero")
        root = inherit_from_path(_ext4_spellings(az.as_posix())[spelling], windows=False)
        assert root == az.as_posix()
        assert (Path(root) / ".claude" / "templates").is_dir()

    def test_a_trailing_separator_is_dropped(self):
        assert inherit_from_path(WINDOWS_DRIVE_PATH + "\\", windows=False) == (
            "/mnt/c/Users/someone/Projects/AssemblyZero")

    def test_a_relative_value_is_kept_as_written(self):
        """Read against the working directory, as before (#4776 R3)."""
        assert inherit_from_path("../AZ", windows=False) == "../AZ"


class TestInheritFromOnWindows:
    """windows=True: the generator runs on Windows."""

    @pytest.mark.parametrize("spelling", sorted(DRIVE_SPELLINGS))
    def test_a_drive_spelling_becomes_the_drive_path(self, spelling):
        assert inherit_from_path(DRIVE_SPELLINGS[spelling], windows=True) == WINDOWS_DRIVE_PATH

    @pytest.mark.parametrize("spelling", ["posix", "wsl-share", "wsl-share-forward"])
    def test_an_ext4_spelling_becomes_the_wsl_share(self, spelling):
        posix = "/home/someone/Projects/AssemblyZero"
        assert inherit_from_path(_ext4_spellings(posix)[spelling], windows=True) == (
            "\\\\wsl.localhost\\Ubuntu\\home\\someone\\Projects\\AssemblyZero")

    def test_the_share_keeps_the_distro_the_file_names(self):
        assert inherit_from_path("//wsl.localhost/Other/srv/AZ", windows=True) == (
            "\\\\wsl.localhost\\Other\\srv\\AZ")

    @pytest.mark.parametrize("spelling", sorted(DRIVE_SPELLINGS))
    def test_a_drive_spelling_names_the_same_assemblyzero_on_both_sides(
            self, tmp_path, spelling):
        """The Windows result, read back on Ubuntu, is the temporary AssemblyZero."""
        mount = tmp_path / "mnt"
        az = _make_assemblyzero(mount / "c" / "Users" / "someone" / "Projects" / "AssemblyZero")
        on_windows = inherit_from_path(DRIVE_SPELLINGS[spelling], windows=True)
        back = inherit_from_path(on_windows, windows=False, mount_root=mount.as_posix())
        assert (Path(back) / ".claude" / "templates").is_dir()
        assert back == az.as_posix()

    @pytest.mark.parametrize("spelling", ["posix", "wsl-share", "wsl-share-forward"])
    def test_an_ext4_spelling_names_the_same_assemblyzero_on_both_sides(
            self, tmp_path, spelling):
        az = _make_assemblyzero(tmp_path / "home" / "someone" / "AssemblyZero")
        on_windows = inherit_from_path(_ext4_spellings(az.as_posix())[spelling], windows=True)
        back = inherit_from_path(on_windows, windows=False)
        assert (Path(back) / ".claude" / "templates").is_dir()
        assert back == az.as_posix()


# ===========================================================================
# #4776: ASSEMBLYZERO_ROOT, and no template reaches AssemblyZero as a sibling
# ===========================================================================


class TestAssemblyZeroRootVariable:

    def test_on_ubuntu_it_is_the_posix_path(self):
        assert generate.root_variable(
            "/mnt/c/Users/someone/Projects/AssemblyZero", windows=False) == (
            "/mnt/c/Users/someone/Projects/AssemblyZero")

    def test_on_windows_it_is_the_drive_path_with_forward_slashes(self):
        """A bash command in a template loses an unquoted backslash."""
        assert generate.root_variable(WINDOWS_DRIVE_PATH, windows=True) == (
            "C:/Users/someone/Projects/AssemblyZero")

    def test_on_windows_an_ext4_assemblyzero_is_the_share_with_forward_slashes(self):
        assert generate.root_variable(
            "\\\\wsl.localhost\\Ubuntu\\home\\someone\\AssemblyZero", windows=True) == (
            "//wsl.localhost/Ubuntu/home/someone/AssemblyZero")


def _write_project(project: Path, inherit_from: str) -> None:
    """project.json for a repository at `project`, as new_repo.py lays it out."""
    posix = project.as_posix()
    (project / ".claude").mkdir(parents=True)
    (project / ".claude" / "project.json").write_text(json.dumps({
        "variables": {
            "PROJECT_ROOT": posix,
            "PROJECT_NAME": project.name,
            "GITHUB_REPO": f"someone/{project.name}",
            "TOOLS_DIR": f"{posix}/tools",
            "WORKTREE_PATTERN": f"{project.name}-{{ID}}",
        },
        "inherit_from": inherit_from,
    }), encoding="utf-8")


@pytest.mark.skipif(sys.platform == "win32", reason="an ext4 root exists only off Windows")
class TestCleanupTemplateUnderAnExt4Root:

    @pytest.mark.parametrize("spelling", ["posix", "wsl-share"])
    def test_the_cleanup_command_names_assemblyzeros_real_path(
            self, tmp_path, capsys, spelling):
        """#4776 T1. The repository is under a temporary ext4-style root and
        AssemblyZero is elsewhere, so no sibling of the repository is it."""
        az = tmp_path / "elsewhere" / "AssemblyZero"
        commands = az / ".claude" / "templates" / "commands"
        commands.mkdir(parents=True)
        shutil.copy(CLEANUP_TEMPLATE, commands / CLEANUP_TEMPLATE.name)
        project = tmp_path / "ext4" / "Projects" / "Foo"
        _write_project(project, _ext4_spellings(az.as_posix())[spelling])

        with patch("sys.argv", ["assemblyzero-generate.py", "--project", str(project)]):
            generate.main()

        assert "WARNINGS" not in capsys.readouterr().out
        text = (project / ".claude" / "commands" / "cleanup.md").read_text(encoding="utf-8")
        a = az.as_posix()
        assert (f"poetry run --directory {a} python {a}/tools/assemblyzero-permissions.py"
                " --quick-check --project Foo") in text
        assert "/../AssemblyZero" not in text
        assert "{{" not in text


def _tracked_claude_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--", ".claude"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [REPO_ROOT / line for line in out.splitlines() if line]


#: The two ways a template reached AssemblyZero as the repository's sibling.
SIBLING_PATHS = ("../AssemblyZero", "{{PROJECT_ROOT}}/..")


def test_no_file_under_claude_reaches_assemblyzero_as_a_sibling():
    """#4776 T2."""
    files = _tracked_claude_files()
    assert files, "git ls-files returned nothing; the check would pass vacuously"
    offenders = []
    for path in files:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            offenders += [
                f"{path.relative_to(REPO_ROOT).as_posix()}:{number}: {sibling}"
                for sibling in SIBLING_PATHS if sibling in line
            ]
    assert offenders == [], (
        "reach AssemblyZero through {{ASSEMBLYZERO_ROOT}}, never as a sibling:\n  "
        + "\n  ".join(offenders))

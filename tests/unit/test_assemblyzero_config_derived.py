"""assemblyzero_config's defaults are derived from the checkout, on every platform (#3536)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import assemblyzero_config  # noqa: E402
from assemblyzero_config import DEFAULTS, _spellings  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def test_projects_root_is_this_checkouts_parent():
    native = "windows" if sys.platform == "win32" else "unix"
    assert Path(DEFAULTS["projects_root"][native]) == REPO.parent
    assert Path(DEFAULTS["assemblyzero_root"][native]) == REPO


def test_a_windows_drive_gets_both_spellings():
    assert _spellings(Path("C:/Users/mcwiz/Projects")) == {
        "windows": "C:\\Users\\mcwiz\\Projects",
        "unix": "/c/Users/mcwiz/Projects",
    }


def test_wsl_view_of_a_drive_gets_its_windows_twin():
    assert _spellings(Path("/mnt/c/Users/mcwiz/Projects")) == {
        "windows": "C:\\Users\\mcwiz\\Projects",
        "unix": "/mnt/c/Users/mcwiz/Projects",
    }


def test_ext4_has_only_its_posix_spelling():
    assert _spellings(Path("/home/mcwiz/Projects")) == {
        "windows": "/home/mcwiz/Projects",
        "unix": "/home/mcwiz/Projects",
    }


def test_mnt_without_a_drive_letter_is_not_a_drive():
    assert _spellings(Path("/mnt/data/x"))["windows"] == "/mnt/data/x"


def test_the_module_spells_no_projects_root():
    source = Path(assemblyzero_config.__file__).read_text(encoding="utf-8")
    code = [ln for ln in source.splitlines() if not ln.lstrip().startswith("#")]
    assert not any("mcwiz\\Projects" in ln or "mcwiz/Projects" in ln for ln in code if '"""' not in ln)

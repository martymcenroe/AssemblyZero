"""assemblyzero_config's defaults are derived from the checkout, on every platform (#3536)."""

import logging
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
    assert _spellings(Path("C:/Users/dev/Projects")) == {
        "windows": "C:\\Users\\dev\\Projects",
        "unix": "/c/Users/dev/Projects",
    }


def test_wsl_view_of_a_drive_gets_its_windows_twin():
    assert _spellings(Path("/mnt/c/Users/dev/Projects")) == {
        "windows": "C:\\Users\\dev\\Projects",
        "unix": "/mnt/c/Users/dev/Projects",
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


def _config_off_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(assemblyzero_config, "CONFIG_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(assemblyzero_config.AssemblyZeroConfig, "_detected_os", "unix")
    return assemblyzero_config.AssemblyZeroConfig()


def test_a_windows_path_off_windows_is_left_alone_and_not_called_an_attack(
    tmp_path, monkeypatch, caplog
):
    """Off Windows a C:\\ path names the Windows side. The sanitizer resolved it
    against the current directory and warned of a traversal attempt (#4180)."""
    config = _config_off_windows(tmp_path, monkeypatch)
    path = "C:\\Users\\dev\\Projects\\x"
    with caplog.at_level(logging.WARNING, logger="assemblyzero_config"):
        assert config._sanitize_path(path) == path
    assert caplog.records == []


def test_a_windows_traversal_off_windows_is_still_stripped_and_warned(
    tmp_path, monkeypatch, caplog
):
    config = _config_off_windows(tmp_path, monkeypatch)
    with caplog.at_level(logging.WARNING, logger="assemblyzero_config"):
        assert config._sanitize_path("C:\\Users\\..\\..\\Windows") == "C:\\Users\\Windows"
    assert any("potential traversal" in r.getMessage() for r in caplog.records)


def test_windows_format_off_windows_is_the_windows_spelling(tmp_path, monkeypatch):
    """What new_repo.py writes into a scaffold's inherit_from (#4180)."""
    config = _config_off_windows(tmp_path, monkeypatch)
    assert config.assemblyzero_root() == DEFAULTS["assemblyzero_root"]["windows"]

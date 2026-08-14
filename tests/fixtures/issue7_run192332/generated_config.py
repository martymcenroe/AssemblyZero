"""Configuration management.

Issue #7: Feature: configuration file and CLI arguments
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypedDict


class Threshold(TypedDict):
    yellow: int
    red: int


class Position(TypedDict):
    x: int
    y: int


def get_default_config_path() -> Path:
    """Returns ~/.boostgauge/config.json or %APPDATA%/boostgauge/config.json."""
    if os.name == 'nt' and 'APPDATA' in os.environ:
        return Path(os.environ['APPDATA']) / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> dict[str, Any]:
    """Returns the hardcoded default configuration dictionary."""
    return {
        "size": 300,
        "opacity": 0.9,
        "always_on_top": True,
        "theme": "dark",
        "position": {"x": 100, "y": 100},
        "thresholds": {
            "conpty": {"yellow": 20, "red": 40},
            "memory": {"yellow": 80, "red": 90}
        },
        "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
        "show_driver_label": True,
        "show_digital_readout": True,
        "show_session_count": True,
        "polling_interval_seconds": 2
    }


def load_config(path: Path) -> dict[str, Any]:
    """Reads config from JSON. Raises ValueError on schema failure."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Config must be a JSON object")
            return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in config: {e}")


def write_full_config(path: Path, config_data: dict[str, Any]) -> None:
    """Writes a complete config dictionary to disk atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path_str = tempfile.mkstemp(dir=str(path.parent), text=True)
    tmp_path = Path(tmp_path_str)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def apply_exit_write(path: Path, hand_changed_keys: dict[str, Any]) -> None:
    """Reads current file, patches only the provided keys, and writes back atomically."""
    if not hand_changed_keys:
        return

    try:
        current_data = load_config(path)
    except (FileNotFoundError, ValueError):
        current_data = get_default_config()

    for k, v in hand_changed_keys.items():
        current_data[k] = v

    write_full_config(path, current_data)
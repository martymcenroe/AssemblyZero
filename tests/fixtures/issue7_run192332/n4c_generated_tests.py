"""Test file for Issue #7.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

import json
import argparse
from pathlib import Path
import pytest
from boostgauge.config import get_default_config, write_full_config, load_config, apply_exit_write
from boostgauge.app import main, SessionState, update_thresholds_from_file, parse_args, init_session


def test_req_1(tmp_path):
    # First run with no config file creates one with defaults (REQ-1)
    # Expected output: File exists and matches get_default_config()
    config_path = tmp_path / "config.json"
    init_session(["--config", str(config_path)])
    assert config_path.exists()
    assert load_config(config_path) == get_default_config()


def test_req_2(tmp_path):
    # Launch order and CLI overrides (REQ-2)
    # Expected output: Session size is 400, file remains default size (300)
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    state = init_session(["--config", str(config_path), "--size", "400"])
    
    assert state.in_memory_config["size"] == 400
    assert load_config(config_path)["size"] == 300


def test_req_3(tmp_path):
    # Base launch window props (REQ-3)
    # Expected output: Memory size and position match file
    config_path = tmp_path / "config.json"
    custom_cfg = get_default_config()
    custom_cfg["size"] = 250
    custom_cfg["position"] = {"x": 10, "y": 20}
    write_full_config(config_path, custom_cfg)
    
    state = init_session(["--config", str(config_path)])
    assert state.in_memory_config["size"] == 250
    assert state.in_memory_config["position"] == {"x": 10, "y": 20}


def test_req_4_no_size(tmp_path):
    # Reset config flag effects without CLI size (REQ-4)
    # Expected output: File size is 300, memory size is 300
    config_path = tmp_path / "config.json"
    custom_cfg = get_default_config()
    custom_cfg["size"] = 250
    write_full_config(config_path, custom_cfg)
    
    state = init_session(["--config", str(config_path), "--reset-config"])
    assert load_config(config_path)["size"] == 300
    assert state.in_memory_config["size"] == 300


def test_req_4_with_size(tmp_path):
    # Reset config flag effects with CLI size (REQ-4)
    # Expected output: File size is 300, memory size is 500
    config_path = tmp_path / "config.json"
    state = init_session(["--config", str(config_path), "--reset-config", "--size", "500"])
    assert load_config(config_path)["size"] == 300
    assert state.in_memory_config["size"] == 500


def test_req_5(tmp_path):
    # Threshold live reload (REQ-5)
    # Expected output: Memory threshold is 40, file is unmodified by read
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    state = SessionState(config_file_path=config_path, in_memory_config=get_default_config())
    
    disk_cfg = load_config(config_path)
    disk_cfg["thresholds"]["conpty"]["yellow"] = 40
    write_full_config(config_path, disk_cfg)
    
    update_thresholds_from_file(config_path, state)
    assert state.in_memory_config["thresholds"]["conpty"]["yellow"] == 40


def test_req_6(tmp_path):
    # Exit write patch logic (REQ-6)
    # Expected output: File size is 999 and position is updated
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    # Direct edit mid-session
    disk_cfg = load_config(config_path)
    disk_cfg["size"] = 999
    write_full_config(config_path, disk_cfg)
    
    # Hand change position
    apply_exit_write(config_path, {"position": {"x": 5, "y": 5}})
    
    final_cfg = load_config(config_path)
    assert final_cfg["size"] == 999
    assert final_cfg["position"] == {"x": 5, "y": 5}


def test_req_7(tmp_path):
    # Exit write collision logic (REQ-7)
    # Expected output: File size is 600
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    # Direct edit mid-session
    disk_cfg = load_config(config_path)
    disk_cfg["size"] = 999
    write_full_config(config_path, disk_cfg)
    
    # Hand change size collision
    apply_exit_write(config_path, {"size": 600})
    
    assert load_config(config_path)["size"] == 600


def test_req_8(tmp_path):
    # Untouched session (REQ-8)
    # Expected output: File hash before matches file hash after
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    content_before = config_path.read_bytes()
    
    apply_exit_write(config_path, {})
    assert config_path.read_bytes() == content_before


def test_req_9(tmp_path):
    # Position: no reset, not moved, no direct edits (REQ-9)
    # Expected output: File position matches initial
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    apply_exit_write(config_path, {})
    assert load_config(config_path)["position"] == {"x": 100, "y": 100}


def test_req_10(tmp_path):
    # Position: no reset, moved, no direct edits (REQ-10)
    # Expected output: File position is {"x": 5, "y": 5}
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    apply_exit_write(config_path, {"position": {"x": 5, "y": 5}})
    assert load_config(config_path)["position"] == {"x": 5, "y": 5}


def test_req_11(tmp_path):
    # Position: reset, not moved, no direct edits (REQ-11)
    # Expected output: File position is {"x": 100, "y": 100}
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config"])
    
    apply_exit_write(config_path, {})
    assert load_config(config_path)["position"] == {"x": 100, "y": 100}


def test_req_12(tmp_path):
    # Position: reset, moved, no direct edits (REQ-12)
    # Expected output: File position matches hand-changed pos
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config"])
    
    apply_exit_write(config_path, {"position": {"x": 50, "y": 50}})
    assert load_config(config_path)["position"] == {"x": 50, "y": 50}


def test_req_13(tmp_path):
    # Size: no reset, no size, not resized, no edits (REQ-13)
    # Expected output: File size matches initial
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    apply_exit_write(config_path, {})
    assert load_config(config_path)["size"] == 300


def test_req_14(tmp_path):
    # Size: no reset, no size, resized, no edits (REQ-14)
    # Expected output: File size is 700
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    apply_exit_write(config_path, {"size": 700})
    assert load_config(config_path)["size"] == 700


def test_req_15(tmp_path):
    # Size: no reset, size given, not resized, no edits (REQ-15)
    # Expected output: File size matches initial, not 450
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    # CLI size 450 happens via init_session() but user doesn't hand-resize
    init_session(["--config", str(config_path), "--size", "450"])
    apply_exit_write(config_path, {})
    assert load_config(config_path)["size"] == 300


def test_req_16(tmp_path):
    # Size: no reset, size given, resized, no edits (REQ-16)
    # Expected output: File size is 800
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    init_session(["--config", str(config_path), "--size", "450"])
    apply_exit_write(config_path, {"size": 800})
    assert load_config(config_path)["size"] == 800


def test_req_17(tmp_path):
    # Size: reset, no size, not resized, no edits (REQ-17)
    # Expected output: File size is 300
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config"])
    
    apply_exit_write(config_path, {})
    assert load_config(config_path)["size"] == 300


def test_req_18(tmp_path):
    # Size: reset, no size, resized, no edits (REQ-18)
    # Expected output: File size is 800
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config"])
    
    apply_exit_write(config_path, {"size": 800})
    assert load_config(config_path)["size"] == 800


def test_req_19(tmp_path):
    # Size: reset, size given, not resized, no edits (REQ-19)
    # Expected output: File size is 300
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config", "--size", "450"])
    
    apply_exit_write(config_path, {})
    assert load_config(config_path)["size"] == 300


def test_req_20(tmp_path):
    # Size: reset, size given, resized, no edits (REQ-20)
    # Expected output: File size is 800
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config", "--size", "450"])
    
    apply_exit_write(config_path, {"size": 800})
    assert load_config(config_path)["size"] == 800


def test_req_21(tmp_path):
    # Invalid config values (REQ-21)
    # Expected output: ValueError raised
    config_path = tmp_path / "config.json"
    config_path.write_text("{invalid json")
    
    with pytest.raises(ValueError):
        load_config(config_path)


def test_req_22(tmp_path):
    # Non-threshold live edit ignored (REQ-22)
    # Expected output: Memory telltale_windows.short matches initial
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    state = SessionState(config_file_path=config_path, in_memory_config=get_default_config())
    
    disk_cfg = load_config(config_path)
    disk_cfg["telltale_windows"]["short"] = 999
    write_full_config(config_path, disk_cfg)
    
    update_thresholds_from_file(config_path, state)
    assert state.in_memory_config["telltale_windows"]["short"] == 60


import os
from unittest.mock import patch
from pathlib import Path
import pytest
from boostgauge.config import (
    get_default_config,
    write_full_config,
    load_config,
    apply_exit_write,
    default_config_path,
)


def test_default_config_path_windows_with_appdata(tmp_path):
    """Lines 25-26: On Windows with APPDATA, returns APPDATA-based path."""
    fake_appdata = str(tmp_path / "AppData")
    with patch("boostgauge.config.os.name", "nt"), \
         patch.dict(os.environ, {"APPDATA": fake_appdata}, clear=False):
        result = default_config_path()
    assert result == Path(fake_appdata) / "boostgauge" / "config.json"


def test_default_config_path_non_windows():
    """Line 27: On non-Windows, returns ~/.boostgauge/config.json."""
    with patch("boostgauge.config.os.name", "posix"):
        result = default_config_path()
    assert result == Path.home() / ".boostgauge" / "config.json"


def test_default_config_path_windows_without_appdata():
    """Line 27: On Windows without APPDATA, falls through to home-based path."""
    env_copy = {k: v for k, v in os.environ.items() if k != "APPDATA"}
    with patch("boostgauge.config.os.name", "nt"), \
         patch.dict(os.environ, env_copy, clear=True):
        result = default_config_path()
    assert result == Path.home() / ".boostgauge" / "config.json"


def test_load_config_raises_on_missing_file(tmp_path):
    """Line 53: load_config raises FileNotFoundError for nonexistent path."""
    path = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config(path)


def test_load_config_raises_on_json_array(tmp_path):
    """Line 59: load_config raises ValueError when file contains a JSON array."""
    path = tmp_path / "config.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(ValueError, match="Config must be a JSON object"):
        load_config(path)


def test_load_config_raises_on_json_string(tmp_path):
    """Line 59: load_config raises ValueError when file contains a JSON string."""
    path = tmp_path / "config.json"
    path.write_text('"hello"')
    with pytest.raises(ValueError, match="Config must be a JSON object"):
        load_config(path)


def test_load_config_raises_on_json_number(tmp_path):
    """Line 59: load_config raises ValueError when file contains a JSON number."""
    path = tmp_path / "config.json"
    path.write_text("42")
    with pytest.raises(ValueError, match="Config must be a JSON object"):
        load_config(path)


def test_write_full_config_removes_temp_on_serialization_error(tmp_path):
    """Lines 76-77: Temp file is cleaned up when json.dump raises."""
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    original = config_path.read_text()

    bad_data = get_default_config()
    bad_data["unserializable"] = object()
    with pytest.raises(TypeError):
        write_full_config(config_path, bad_data)

    # Original config is preserved
    assert config_path.read_text() == original
    # No temp files left behind
    remaining = {f.name for f in tmp_path.iterdir()}
    assert remaining == {"config.json"}


def test_write_full_config_removes_temp_no_preexisting_file(tmp_path):
    """Lines 76-77: Temp file cleanup when no original config existed."""
    config_path = tmp_path / "config.json"
    bad_data = {"unserializable": object()}
    with pytest.raises(TypeError):
        write_full_config(config_path, bad_data)

    # No files should remain
    assert not config_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_apply_exit_write_falls_back_on_missing_config(tmp_path):
    """Lines 88-89: Missing config file causes fallback to defaults."""
    path = tmp_path / "absent.json"
    apply_exit_write(path, {"size": 450})
    result = load_config(path)
    defaults = get_default_config()
    assert result["size"] == 450
    for key in defaults:
        if key != "size":
            assert result[key] == defaults[key]


def test_apply_exit_write_falls_back_on_corrupt_json(tmp_path):
    """Lines 88-89: Corrupt JSON triggers fallback to defaults."""
    path = tmp_path / "config.json"
    path.write_text("{broken json!!!}")
    apply_exit_write(path, {"size": 600})
    result = load_config(path)
    defaults = get_default_config()
    assert result["size"] == 600
    assert result["thresholds"] == defaults["thresholds"]


def test_apply_exit_write_falls_back_on_non_object_json(tmp_path):
    """Lines 88-89: JSON array triggers ValueError fallback to defaults."""
    path = tmp_path / "config.json"
    path.write_text("[1, 2, 3]")
    apply_exit_write(path, {"position": {"x": 7, "y": 8}})
    result = load_config(path)
    defaults = get_default_config()
    assert result["position"] == {"x": 7, "y": 8}
    assert result["size"] == defaults["size"]

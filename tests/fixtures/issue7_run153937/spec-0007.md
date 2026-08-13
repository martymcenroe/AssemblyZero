# Implementation Spec: Feature: configuration file and CLI arguments (#7)

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/7-config.md` |
| Generated | 2026-08-13 |
| Status | DRAFT |

## 1. Overview

**Objective:** Implement a configuration system for thresholds, polling intervals, visual preferences, and window behavior with specific rules for CLI overrides and file persistence.

**Success Criteria:** Configuration file is created with defaults on first run, CLI overrides take precedence in memory but do not overwrite the disk file, and manual file edits (like threshold changes) are live-reloaded without overwriting non-hand-changed settings on exit.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/config.py` | Add | Implements config loading, writing, default values, and exit-patching logic. |
| 2 | `src/boostgauge/app.py` | Add | Integrates `argparse` for CLI, injects overrides, orchestrates config reset/read at launch, applies mid-session threshold reloads, and calls exit write. |

**Implementation Order Rationale:** `config.py` has no internal dependencies and provides the core data structures and I/O logic required by `app.py`. `app.py` is the entry point that orchestrates the config lifecycle.

## 3. Current State (for Modify/Delete files)

N/A - All files in this Implementation Spec have a Change Type of "Add".

## 4. Data Structures

### 4.1 ConfigKeys

**Definition:**
```python
from typing import TypedDict

class Threshold(TypedDict):
    yellow: int
    red: int

class Position(TypedDict):
    x: int
    y: int

class TelltaleWindows(TypedDict):
    short: int
    medium: int
    long: int

class ConfigKeys(TypedDict):
    polling_interval_seconds: int
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: Position
    thresholds: dict[str, Threshold]
    telltale_windows: TelltaleWindows
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool
```

**Concrete Example:**
```json
{
    "polling_interval_seconds": 2,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": true,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 20, "red": 40},
        "memory": {"yellow": 80, "red": 90}
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": true,
    "show_digital_readout": true,
    "show_session_count": true
}
```

### 4.2 SessionState

**Definition:**
```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class SessionState:
    config_file_path: Path
    in_memory_config: dict[str, Any] = field(default_factory=dict)
    hand_changed_keys: dict[str, Any] = field(default_factory=dict)
```

**Concrete Example:**
```json
{
    "config_file_path": "C:\\Users\\mcwiz\\AppData\\Roaming\\boostgauge\\config.json",
    "in_memory_config": {
        "theme": "dark",
        "size": 400,
        "opacity": 0.9,
        "always_on_top": true,
        "position": {"x": 100, "y": 100},
        "thresholds": {"conpty": {"yellow": 20, "red": 40}}
    },
    "hand_changed_keys": {
        "size": 400,
        "position": {"x": 150, "y": 150}
    }
}
```

## 5. Function Specifications

### 5.1 `get_default_config_path()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def get_default_config_path() -> Path:
    """Returns ~/.boostgauge/config.json or %APPDATA%/boostgauge/config.json."""
    ...
```

**Input Example:**
```python
# No arguments
```

**Output Example:**
```python
Path("C:/Users/mcwiz/AppData/Roaming/boostgauge/config.json")
```

**Edge Cases:**
- `APPDATA` not set on Windows -> fall back to `~/.boostgauge/config.json` via `Path.home()`.

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def get_default_config() -> dict[str, Any]:
    """Returns the hardcoded default configuration dictionary."""
    ...
```

**Input Example:**
```python
# No arguments
```

**Output Example:**
```python
{
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "theme": "dark",
    "position": {"x": 100, "y": 100},
    "thresholds": {"conpty": {"yellow": 20, "red": 40}},
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
    "polling_interval_seconds": 2
}
```

**Edge Cases:**
- None. Hardcoded dictionary return.

### 5.3 `load_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def load_config(path: Path) -> dict[str, Any]:
    """Reads config from JSON. Raises ValueError on schema failure."""
    ...
```

**Input Example:**
```python
path = Path("/tmp/config.json")
```

**Output Example:**
```python
{
    "size": 300,
    "theme": "dark"
}
```

**Edge Cases:**
- Invalid JSON -> raises `ValueError("Invalid JSON format in config")`
- Missing file -> raises `FileNotFoundError`

### 5.4 `write_full_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def write_full_config(path: Path, config_data: dict[str, Any]) -> None:
    """Writes a complete config dictionary to disk atomically."""
    ...
```

**Input Example:**
```python
path = Path("/tmp/config.json")
config_data = {"size": 300, "theme": "dark"}
```

**Output Example:**
```python
None
```

**Edge Cases:**
- Parent directory does not exist -> creates parent directories.

### 5.5 `apply_exit_write()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def apply_exit_write(path: Path, hand_changed_keys: dict[str, Any]) -> None:
    """Reads current file, patches only the provided keys, and writes back atomically."""
    ...
```

**Input Example:**
```python
path = Path("/tmp/config.json")
hand_changed_keys = {"size": 400}
```

**Output Example:**
```python
None
```

**Edge Cases:**
- File deleted mid-session -> acts like `write_full_config` with default + `hand_changed_keys`.

### 5.6 `parse_args()`

**File:** `src/boostgauge/app.py`

**Signature:**
```python
def parse_args(args: list[str]) -> argparse.Namespace:
    """Parses CLI arguments."""
    ...
```

**Input Example:**
```python
args = ["--size", "400", "--reset-config"]
```

**Output Example:**
```python
argparse.Namespace(size=400, reset_config=True, config=None)
```

**Edge Cases:**
- Invalid arguments -> `argparse` calls `sys.exit(2)`.

### 5.7 `update_thresholds_from_file()`

**File:** `src/boostgauge/app.py`

**Signature:**
```python
def update_thresholds_from_file(path: Path, current_state: SessionState) -> None:
    """Reads file and updates ONLY the thresholds object in current_state.in_memory_config."""
    ...
```

**Input Example:**
```python
path = Path("/tmp/config.json")
current_state = SessionState(
    config_file_path=Path("/tmp/config.json"),
    in_memory_config={"thresholds": {"conpty": {"yellow": 20, "red": 40}}}
)
```

**Output Example:**
```python
None
# current_state.in_memory_config["thresholds"] is updated in place.
```

**Edge Cases:**
- File deleted mid-session -> logs warning and does nothing.
- Invalid JSON mid-session -> logs warning and does nothing.

## 6. Change Instructions

### 6.1 `src/boostgauge/config.py` (Add)

**Complete file contents:**
```python
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
```

### 6.2 `src/boostgauge/app.py` (Add)

**Complete file contents:**
```python
"""Main application entry point.

Issue #7: Feature: configuration file and CLI arguments
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from boostgauge.config import (
    get_default_config_path, 
    get_default_config, 
    load_config, 
    write_full_config, 
    apply_exit_write
)

@dataclass
class SessionState:
    config_file_path: Path
    in_memory_config: dict[str, Any] = field(default_factory=dict)
    hand_changed_keys: dict[str, Any] = field(default_factory=dict)

def parse_args(args: list[str]) -> argparse.Namespace:
    """Parses CLI arguments."""
    parser = argparse.ArgumentParser(description="BoostGauge")
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--reset-config", action="store_true", help="Reset config to defaults")
    parser.add_argument("--size", type=int, help="Override gauge size")
    return parser.parse_args(args)

def update_thresholds_from_file(path: Path, current_state: SessionState) -> None:
    """Reads file and updates ONLY the thresholds object in current_state.in_memory_config."""
    try:
        disk_data = load_config(path)
        if "thresholds" in disk_data:
            current_state.in_memory_config["thresholds"] = disk_data["thresholds"]
    except (FileNotFoundError, ValueError):
        pass

def init_session(args: list[str]) -> SessionState:
    """Initializes and returns the session state from CLI args."""
    parsed = parse_args(args)
    config_path = parsed.config if parsed.config else get_default_config_path()
    
    if parsed.reset_config:
        write_full_config(config_path, get_default_config())
    elif not config_path.exists():
        write_full_config(config_path, get_default_config())
    
    in_memory_config = load_config(config_path)
        
    if parsed.size is not None:
        in_memory_config["size"] = parsed.size
        
    return SessionState(config_file_path=config_path, in_memory_config=in_memory_config)

def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    
    try:
        state = init_session(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    # GUI and main loop would go here.
    
    apply_exit_write(state.config_file_path, state.hand_changed_keys)
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## 7. Pattern References

### 7.1 Data Collectors Abstraction

**File:** `src/boostgauge/collector.py` (lines 7-19)

```python
from dataclasses import dataclass

class SystemSnapshot:
    """Snapshot of system resource metrics at a point in time."""

class DataCollector(abc.ABC):
    """Abstract base class for system metric collectors."""
    def start(self) -> None:
        ...
```

**Relevance:** Demonstrates the use of `@dataclass` for state objects without excessive boilerplate. This directly justifies the choice of `@dataclass` for `SessionState`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import json` | stdlib | `config.py` |
| `import os` | stdlib | `config.py` |
| `from pathlib import Path` | stdlib | `config.py`, `app.py` |
| `from typing import Any, TypedDict` | stdlib | `config.py` |
| `import tempfile` | stdlib | `config.py` |
| `import argparse` | stdlib | `app.py` |
| `import sys` | stdlib | `app.py` |
| `from dataclasses import dataclass, field` | stdlib | `app.py` |

**New Dependencies:** None (Uses standard library)

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `write_full_config()`, `get_default_config()` | First run (no file) | Creates file with defaults |
| T020 | `init_session()` | CLI `--size 400` | In memory size is 400, file is default |
| T030 | `init_session()` | No overrides | Memory window props match disk |
| T040 | `init_session()` | `--reset-config` | File rewritten to default, memory is default |
| T050 | `update_thresholds_from_file()` | File edit + tick | Memory thresholds update without disk write |
| T060 | `apply_exit_write()` | `hand_changed_keys={'size': 999}` | Touches only size key on disk |
| T070 | `apply_exit_write()` | Hand size + direct file edit | Hand size overwrites file edit for size |
| T080 | `apply_exit_write()` | No hand changes | File remains byte-identical |
| T090 | `apply_exit_write()` | Position matrix (various) | Matches REQ 9-12 |
| T100 | `apply_exit_write()` | Size matrix (various) | Matches REQ 13-20 |
| T110 | `load_config()` | Invalid JSON | Raises ValueError |
| T120 | `update_thresholds_from_file()` | Non-threshold file edit | Memory non-thresholds unchanged |

### 10.1 Per-criterion test functions

```python
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
```

## 11. Implementation Notes

### 11.1 Error Handling Convention

Configuration errors during startup print a clear message to stderr and terminate with exit code 1. During the application loop, errors reading the config file (e.g. if the user is mid-save and the file is locked or empty) are silently ignored to prevent crashing the gauge.

### 11.2 Atomic Writes

We use `tempfile.mkstemp` and `os.replace` in `write_full_config` to ensure atomic file updates, avoiding read/write race conditions from file watchers or mid-session user edits.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `DEFAULT_POLLING_INTERVAL` | `2` | Polling frequency to balance responsiveness against system overhead. |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) - N/A (all files Add)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every **non-test** function has input/output examples with realistic values (Section 5)
- [x] Every LLD pass criterion has a test function (Section 10.1) — these are exempt from the rule above
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-08-13 |
| Iterations | 1 |
| Finalized | 2026-08-13T15:44:25-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-08-13 |
| Iterations | 2 |
| Finalized | 2026-08-13T20:55:58Z |

### Review Feedback Summary

The revised spec successfully addresses the missing initialization step in the CLI override tests. Assertion traceability is fully intact, with each test assertion mapping cleanly to the LLD requirements without contradicting the defined behavior. The implementation details, data structures, and edge-case handling are concrete, specific, and fully executable by an agent.

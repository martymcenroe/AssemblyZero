# Implementation Spec: Issue #7 - Feature: configuration file and CLI arguments

<!-- Standard: 0701 -->
<!-- Version: 1.1 -->
<!-- Last Updated: 2026-08-13 -->
<!-- Issue: #7 -->

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/7-feature-config.md` |
| Generated | 2026-08-13 |
| Status | DRAFT |

## 1. Overview

**Objective:** Implement a configuration system that supports file-based persistence, CLI overrides, and independent save rules for hand-changed settings.

**Success Criteria:** First run with no config file creates one with defaults. CLI arguments override file values in memory but are never written to disk. Threshold values edited directly in the config file take effect without restart (`reload_thresholds`), while other non-threshold values edited during the session survive the exit write as long as the application didn't hand-change those specific keys. Corrupt config files fail-fast with clear errors.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/config.py` | Add | Configuration manager implementing file load, CLI overlay, read-patch-write exit saving, and threshold hot-reloads |
| 2 | `src/boostgauge/app.py` | Add | Main entry point parsing CLI args and initializing the configuration |

**Implementation Order Rationale:** The configuration manager provides the necessary state object for the main application entry point to parse CLI arguments into.

## 3. Current State

*No existing files to modify or delete. Both files are new additions (Add).*

## 4. Data Structures

### 4.1 Position

**Definition:**
```python
class Position(TypedDict):
    x: int
    y: int
```

**Concrete Example:**
```json
{
    "x": 200,
    "y": 150
}
```

### 4.2 Threshold

**Definition:**
```python
class Threshold(TypedDict):
    yellow: int
    red: int
```

**Concrete Example:**
```json
{
    "yellow": 75,
    "red": 90
}
```

### 4.3 ThresholdsConfig

**Definition:**
```python
class ThresholdsConfig(TypedDict):
    conpty: Threshold
    memory_percent: Threshold
    process_count: Threshold
    handle_count: Threshold
```

**Concrete Example:**
```json
{
    "conpty": {"yellow": 10, "red": 20},
    "memory_percent": {"yellow": 80, "red": 95},
    "process_count": {"yellow": 300, "red": 500},
    "handle_count": {"yellow": 20000, "red": 30000}
}
```

### 4.4 TelltaleWindows

**Definition:**
```python
class TelltaleWindows(TypedDict):
    short: int
    medium: int
    long: int
```

**Concrete Example:**
```json
{
    "short": 60,
    "medium": 600,
    "long": 3600
}
```

### 4.5 AppConfig

**Definition:**
```python
class AppConfig(TypedDict):
    polling_interval_seconds: int
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: Position
    thresholds: ThresholdsConfig
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
        "conpty": {"yellow": 10, "red": 20},
        "memory_percent": {"yellow": 80, "red": 95},
        "process_count": {"yellow": 300, "red": 500},
        "handle_count": {"yellow": 20000, "red": 30000}
    },
    "telltale_windows": {
        "short": 60,
        "medium": 600,
        "long": 3600
    },
    "show_driver_label": true,
    "show_digital_readout": true,
    "show_session_count": true
}
```

## 5. Function Specifications

### 5.1 `ConfigManager.__init__()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def __init__(self, config_path: str | None = None) -> None:
    """Initializes configuration paths and state dictionaries."""
```

**Input Example:**
```python
config_path = "C:/custom/path/config.json"
```

**Output Example:** 
*(None - initializes class attributes `self.config_path`, `self._session_config`, `self._cli_overrides`, `self._hand_changes`)*

### 5.2 `ConfigManager._resolve_path()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def _resolve_path(self, path: str | None) -> Path:
    """Determines OS-specific config location or uses provided path."""
```

**Input Example:**
```python
path = None
```

**Output Example:**
```python
Path.home() / ".boostgauge" / "config.json"
```

**Edge Cases:**
- If an absolute path is provided, it returns a resolved `Path` object of that string.

### 5.3 `ConfigManager.initialize()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def initialize(self, reset: bool, cli_args: dict[str, Any]) -> None:
    """Applies reset logic if needed, loads config, overlays CLI arguments."""
```

**Input Example:**
```python
reset = True
cli_args = {"size": 400}
```

**Output Example:** 
*(None - updates in-memory dictionaries and disk if reset is True)*

**Edge Cases:**
- Keys in `cli_args` with `None` values are ignored and not placed in `_cli_overrides`.

### 5.4 `ConfigManager.get()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def get(self, key: str) -> Any:
    """Returns CLI override if present, else session config, else default."""
```

**Input Example:**
```python
key = "size"
```

**Output Example:**
```python
400
```

### 5.5 `ConfigManager.update_hand_change()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def update_hand_change(self, key: str, value: Any) -> None:
    """Records a user-driven hand change to be written on exit."""
```

**Input Example:**
```python
key = "size"
value = 450
```

**Output Example:** 
*(None - internal state mutated)*

### 5.6 `ConfigManager.reload_thresholds()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def reload_thresholds(self) -> None:
    """Re-reads the config file and updates only the 'thresholds' dictionary in memory."""
```

**Input Example:**
*(None)*

**Output Example:** 
*(None - mutates `self._session_config["thresholds"]`)*

**Edge Cases:**
- Mid-session JSON parse errors (e.g. while the user is actively typing in the file) are caught and ignored, keeping the old thresholds loaded.

### 5.7 `ConfigManager.save_on_exit()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def save_on_exit(self) -> None:
    """Performs a read-patch-write to persist only hand-changed keys."""
```

**Input Example:**
*(None)*

**Output Example:** 
*(None - file written to disk atomically using `os.replace`)*

**Edge Cases:**
- Empty `self._hand_changes` returns early and skips touching the disk entirely.
- Corrupted mid-session disk JSON results in rewriting defaults + hand patches.

### 5.8 `parse_args()`

**File:** `src/boostgauge/app.py`

**Signature:**
```python
def parse_args() -> argparse.Namespace:
    """Parses CLI arguments."""
```

**Input Example:** 
```python
# Assuming sys.argv = ["boostgauge", "--size", "400", "--reset-config"]
```

**Output Example:**
```python
argparse.Namespace(config=None, reset_config=True, size=400, theme=None)
```

## 6. Change Instructions

### 6.1 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration manager handling load, CLI memory overlay, threshold reload, and exit writing.

Issue #7: Configuration file and CLI arguments
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, TypedDict

class Position(TypedDict):
    x: int
    y: int

class Threshold(TypedDict):
    yellow: int
    red: int

class ThresholdsConfig(TypedDict):
    conpty: Threshold
    memory_percent: Threshold
    process_count: Threshold
    handle_count: Threshold

class TelltaleWindows(TypedDict):
    short: int
    medium: int
    long: int

class AppConfig(TypedDict):
    polling_interval_seconds: int
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: Position
    thresholds: ThresholdsConfig
    telltale_windows: TelltaleWindows
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool

DEFAULT_CONFIG: AppConfig = {
    "polling_interval_seconds": 2,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 10, "red": 20},
        "memory_percent": {"yellow": 80, "red": 95},
        "process_count": {"yellow": 300, "red": 500},
        "handle_count": {"yellow": 20000, "red": 30000}
    },
    "telltale_windows": {
        "short": 60,
        "medium": 600,
        "long": 3600
    },
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True
}

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path: str | None = None) -> None:
        """Initializes configuration paths."""
        self.config_path = self._resolve_path(config_path)
        self._session_config: dict[str, Any] = {}
        self._cli_overrides: dict[str, Any] = {}
        self._hand_changes: dict[str, Any] = {}

    def _resolve_path(self, path: str | None) -> Path:
        """Determines OS-specific config location or uses provided path."""
        if path:
            return Path(path).resolve()
        return Path.home() / ".boostgauge" / "config.json"

    def initialize(self, reset: bool, cli_args: dict[str, Any]) -> None:
        """Applies reset logic if needed, loads config, overlays CLI arguments."""
        self._cli_overrides = {k: v for k, v in cli_args.items() if v is not None}
        
        if reset or not self.config_path.exists():
            self._write_defaults()
            
        self._load()

    def _write_defaults(self) -> None:
        """Writes DEFAULT_CONFIG to disk and creates parent directories."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        logger.info(f"Wrote default config to {self.config_path}")

    def _load(self) -> None:
        """Reads config from disk into session memory. Raises ValueError on bad JSON."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._session_config = json.load(f)
            logger.info(f"Loaded config from {self.config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config: {e}")
            raise ValueError("Invalid configuration format") from e

    def get(self, key: str) -> Any:
        """Returns CLI override if present, else session config, else default."""
        if key in self._cli_overrides:
            return self._cli_overrides[key]
        if key in self._session_config:
            return self._session_config[key]
        return DEFAULT_CONFIG.get(key)

    def update_hand_change(self, key: str, value: Any) -> None:
        """Records a user-driven hand change to be written on exit."""
        self._session_config[key] = value
        self._hand_changes[key] = value

    def reload_thresholds(self) -> None:
        """Re-reads the config file and updates only the 'thresholds' dictionary in memory."""
        if not self.config_path.exists():
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                disk_config = json.load(f)
                if "thresholds" in disk_config:
                    self._session_config["thresholds"] = disk_config["thresholds"]
        except json.JSONDecodeError:
            pass  # Mid-session editing error; ignore and keep current thresholds

    def save_on_exit(self) -> None:
        """Performs a read-patch-write to persist only hand-changed keys."""
        if not self._hand_changes:
            return
            
        current_disk = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    current_disk = json.load(f)
            except json.JSONDecodeError:
                current_disk = dict(DEFAULT_CONFIG)
        else:
            current_disk = dict(DEFAULT_CONFIG)
            
        for key, value in self._hand_changes.items():
            current_disk[key] = value
            
        tmp_path = self.config_path.parent / (self.config_path.name + ".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(current_disk, f, indent=4)
            os.replace(tmp_path, self.config_path)
            logger.info(f"Saved hand changes {list(self._hand_changes.keys())} to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
```

### 6.2 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Main entry point parsing CLI arguments.

Issue #7: Configuration file and CLI arguments
"""

import argparse
import logging
from typing import Any

from boostgauge.config import ConfigManager

logging.basicConfig(level=logging.INFO)

def parse_args() -> argparse.Namespace:
    """Parses CLI arguments."""
    parser = argparse.ArgumentParser(description="BoostGauge: System tachometer")
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--reset-config", action="store_true", help="Reset configuration to defaults")
    parser.add_argument("--size", type=int, help="Window size override")
    parser.add_argument("--theme", type=str, help="UI theme override")
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    
    config = ConfigManager(config_path=args.config)
    cli_args: dict[str, Any] = {}
    
    if hasattr(args, "size") and args.size is not None:
        cli_args["size"] = args.size
    if hasattr(args, "theme") and args.theme is not None:
        cli_args["theme"] = args.theme
        
    config.initialize(reset=args.reset_config, cli_args=cli_args)
    # App logic starts here

if __name__ == "__main__":
    main()
```

## 7. Pattern References

*No existing custom patterns applied for standard IO or argument parsing. We use stdlib components (`argparse`, `json`, `os.replace`) to achieve atomic file saves and argument parsing natively.*

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import json` | stdlib | `src/boostgauge/config.py` |
| `import logging` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py` |
| `import os` | stdlib | `src/boostgauge/config.py` |
| `from pathlib import Path` | stdlib | `src/boostgauge/config.py` |
| `from typing import Any, TypedDict` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py` |
| `import argparse` | stdlib | `src/boostgauge/app.py` |

**New Dependencies:** None (stdlib only)

## 9. Placeholder

*Reserved for alignment with LLD numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| REQ-1 | `initialize()` | First run with no config (REQ-1) | File exists, content includes `"size": 300` and `"theme": "dark"` |
| REQ-2 | `initialize()`, `get()` | Launch order and CLI override memory (REQ-2) | `config.get('size') == 400`, file on disk contains `"size": 300` |
| REQ-3 | `_load()`, `get()` | Open at file position/size (REQ-3) | `config.get('size') == 350`, `config.get('position') == {"x": 200, "y": 200}` |
| REQ-4 | `initialize()` | Reset-config with size N (REQ-4) | `config.get('size') == 500`, file on disk contains `"size": 300` |
| REQ-5 | `reload_thresholds()` | Threshold live reload (REQ-5) | `config.get('thresholds')['process_count']['red'] == 999` |
| REQ-6 | `save_on_exit()` | Exit write only hand-changed (REQ-6) | File contains `"theme": "neon"` and `"size": 450` |
| REQ-7 | `save_on_exit()` | Hand-made edit wins over direct edit (REQ-7) | File contains `"size": 450` |
| REQ-8 | `save_on_exit()` | Byte-identical file on no changes (REQ-8) | `os.stat().st_mtime` unchanged |
| REQ-9 | `save_on_exit()` | Position persistence - no reset, not moved (REQ-9) | File contains `"position": {"x": 100, "y": 100}` |
| REQ-10 | `save_on_exit()` | Position persistence - no reset, moved (REQ-10) | File contains `"position": {"x": 250, "y": 350}` |
| REQ-11 | `save_on_exit()` | Position persistence - reset, not moved (REQ-11) | File contains `"position": {"x": 100, "y": 100}` |
| REQ-12 | `save_on_exit()` | Position persistence - reset, moved (REQ-12) | File contains `"position": {"x": 250, "y": 350}` |
| REQ-13 | `save_on_exit()` | Size persistence - no reset, no size, not resized (REQ-13) | File contains `"size": 300` |
| REQ-14 | `save_on_exit()` | Size persistence - no reset, no size, resized (REQ-14) | File contains `"size": 550` |
| REQ-15 | `save_on_exit()` | Size persistence - no reset, --size, not resized (REQ-15) | File contains `"size": 300` |
| REQ-16 | `save_on_exit()` | Size persistence - no reset, --size, resized (REQ-16) | File contains `"size": 550` |
| REQ-17 | `save_on_exit()` | Size persistence - reset, no size, not resized (REQ-17) | File contains `"size": 300` |
| REQ-18 | `save_on_exit()` | Size persistence - reset, no size, resized (REQ-18) | File contains `"size": 550` |
| REQ-19 | `save_on_exit()` | Size persistence - reset, --size, not resized (REQ-19) | File contains `"size": 300` |
| REQ-20 | `save_on_exit()` | Size persistence - reset, --size, resized (REQ-20) | File contains `"size": 550` |
| REQ-21 | `_load()` | Invalid config values (REQ-21) | `ValueError("Invalid configuration format")` raised |
| REQ-22 | `reload_thresholds()` | Non-threshold live edit ignored (REQ-22) | `config.get('theme') == "dark"` |

## 11. Implementation Notes

### 11.1 File Operations
- We strictly use `os.replace` (atomic file replacement) during `save_on_exit()` to mitigate the risk of creating a zero-byte file if the app crashes right when writing out changes.
- The `.tmp` file MUST be placed in the same directory as the target configuration file to ensure `os.replace` doesn't throw a cross-device link error if the temp directory is mounted on a separate block device.

### 11.2 File Path Comparisons in Testing
- Test suite files should NEVER compare against hardcoded string paths that include directory separators (e.g. `/` or `\`). Use the `pathlib.Path` objects to evaluate test fixtures (`path == Path.home() / ".boostgauge" / "config.json"`), as monkeypatching the OS does not resolve path formatting variations.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) *(N/A - Adds only)*
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)
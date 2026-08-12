# RECONSTRUCTION — not a recovered artifact

**This file is a documented reconstruction, authored 2026-08-12 for the #2239
regression test. It is NOT the spec that run-issue7-082047 produced.**

The real failing artifact — the iteration-2 spec of `run-issue7-082047`
(boostgauge, 2026-08-12) — does not exist and cannot be recovered. Orchestrated
spec runs never persisted their drafts; that gap is #2250, fixed the same day
this fixture was written, which is why no future failure will need a
reconstruction.

What the run log does record about that spec, from the reviewer's second REVISE:

> completely omits 12 required state matrix tests

That is the condition this file reproduces: tests for every LLD-007 pass
criterion **except** the twelve decision-table rows REQ-9 through REQ-20 (the
position matrix, REQ-9..12, and the size matrix, REQ-13..20). Everything else —
REQ-1 through REQ-8, REQ-21 and REQ-22 — carries a test, so a check that fires
here is firing on the row omission specifically and not on a spec that is thin
everywhere.

Waiting for a real failing artifact would be circular: this check exists to
prevent the very failure that would produce one. The operator authorised the
reconstruction on 2026-08-12 on that reasoning.

Paired LLD: `LLD-007.md` in this directory, which IS real — taken verbatim from
boostgauge PR #285 at `f8018447`.

---

## 1. Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `src/boostgauge/config.py` | Add | Config load, reset, and patch-write |
| `src/boostgauge/app.py` | Modify | Wire config into launch and exit |
| `tests/unit/test_config.py` | Add | Unit tests for the above |

## 2. Implementation

```python
# src/boostgauge/config.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "size": 300,
    "position": {"x": 100, "y": 100},
    "theme": "dark",
}


def load_config(path: Path) -> dict[str, Any]:
    """Read the config file, creating it with defaults when absent."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
        return dict(DEFAULTS)

    data = json.loads(path.read_text(encoding="utf-8"))
    for key, value in data.items():
        if key == "size" and not isinstance(value, int):
            raise ValueError(
                f"config key 'size' must be an integer, got {type(value).__name__}"
            )
    return {**DEFAULTS, **data}


def reset_config(path: Path) -> dict[str, Any]:
    """Rewrite the file to defaults and return them."""
    path.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
    return dict(DEFAULTS)


def write_changed_keys(path: Path, changed: dict[str, Any]) -> None:
    """Patch only hand-changed keys, preserving direct edits to the rest."""
    if not changed:
        return
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    on_disk.update(changed)
    path.write_text(json.dumps(on_disk, indent=2), encoding="utf-8")
```

## 3. Tests

```python
# tests/unit/test_config.py
import json
from pathlib import Path

import pytest

from boostgauge.config import DEFAULTS, load_config, reset_config, write_changed_keys


def test_first_run_creates_defaults(tmp_path: Path) -> None:
    """REQ-1: First run with no config file creates one with defaults."""
    path = tmp_path / "config.json"
    result = load_config(path)
    assert path.exists()
    assert json.loads(path.read_text())["size"] == 300
    assert result["size"] == 300


def test_cli_override_is_ephemeral(tmp_path: Path) -> None:
    """REQ-2: CLI overrides govern the session and are never written to file."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"size": 300}), encoding="utf-8")
    active = {**load_config(path), "size": 400}
    assert active["size"] == 400
    assert json.loads(path.read_text())["size"] == 300


def test_no_overrides_uses_file_values(tmp_path: Path) -> None:
    """REQ-3: With no CLI overrides the window opens at the file's values."""
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"size": 350, "position": {"x": 50, "y": 50}}), encoding="utf-8"
    )
    active = load_config(path)
    assert active["size"] == 350
    assert active["position"] == {"x": 50, "y": 50}


def test_reset_writes_defaults(tmp_path: Path) -> None:
    """REQ-4: --reset-config restores default position and size on disk."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"size": 500}), encoding="utf-8")
    reset_config(path)
    assert json.loads(path.read_text())["size"] == 300


def test_reset_with_size_keeps_default_on_disk(tmp_path: Path) -> None:
    """REQ-4: --reset-config --size N opens at N while the file holds default."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"size": 500}), encoding="utf-8")
    on_disk = reset_config(path)
    active = {**on_disk, "size": 400}
    assert active["size"] == 400
    assert json.loads(path.read_text())["size"] == 300


def test_threshold_edit_read_does_not_touch_file(tmp_path: Path) -> None:
    """REQ-5: Reading edited thresholds never modifies the file."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"size": 300, "redline": 80}), encoding="utf-8")
    before = path.stat().st_mtime_ns
    assert load_config(path)["redline"] == 80
    assert path.stat().st_mtime_ns == before


def test_exit_write_patches_only_changed_keys(tmp_path: Path) -> None:
    """REQ-6: A direct file edit survives an exit that writes another key."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"size": 300, "theme": "light"}), encoding="utf-8")
    write_changed_keys(path, {"size": 600})
    written = json.loads(path.read_text())
    assert written["theme"] == "light"
    assert written["size"] == 600


def test_hand_change_wins_conflict(tmp_path: Path) -> None:
    """REQ-7: When both sides changed one key, the hand-made value wins."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"size": 800}), encoding="utf-8")
    write_changed_keys(path, {"size": 600})
    assert json.loads(path.read_text())["size"] == 600


def test_untouched_session_is_byte_identical(tmp_path: Path) -> None:
    """REQ-8: A session with no hand-made changes performs no exit write."""
    path = tmp_path / "config.json"
    original = json.dumps({"size": 300}, indent=2)
    path.write_text(original, encoding="utf-8")
    before = path.read_bytes()
    write_changed_keys(path, {})
    assert path.read_bytes() == before


def test_invalid_value_raises_clear_error(tmp_path: Path) -> None:
    """REQ-21: Invalid config values produce a clear error message."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"size": "not_an_int"}), encoding="utf-8")
    with pytest.raises(ValueError, match="must be an integer"):
        load_config(path)


def test_config_path_selects_file(tmp_path: Path) -> None:
    """REQ-22: --config PATH selects the file in play and writes nothing itself."""
    chosen = tmp_path / "other.json"
    chosen.write_text(json.dumps({"size": 512}), encoding="utf-8")
    untouched = tmp_path / "config.json"
    assert load_config(chosen)["size"] == 512
    assert not untouched.exists()
```

## 4. Known omission

No test is written for the position matrix (REQ-9 through REQ-12) or the size
matrix (REQ-13 through REQ-20). That omission is the point of this fixture.

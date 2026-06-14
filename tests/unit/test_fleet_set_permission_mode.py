"""Tests for the JSON transform in tools/fleet_set_permission_mode.py.

Covers the one non-trivial piece of logic: parsing an existing
.unleashed.json, adding claude.permissionMode=auto, and re-serializing
without dropping other fields. A bug here corrupts every .unleashed.json
in the fleet, so tests > code coverage theater.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import fleet_set_permission_mode as t  # noqa: E402


def _b64(obj: dict) -> str:
    return base64.b64encode((json.dumps(obj) + "\n").encode("utf-8")).decode("ascii")


def _decode(b64: str) -> dict:
    return json.loads(base64.b64decode(b64).decode("utf-8"))


def test_already_set_true_when_auto():
    b64 = _b64({"claude": {"permissionMode": "auto"}})
    assert t.already_set(b64) is True


def test_already_set_false_when_absent():
    b64 = _b64({"claude": {"effort": "max"}})
    assert t.already_set(b64) is False


def test_already_set_false_when_different_value():
    b64 = _b64({"claude": {"permissionMode": "plan"}})
    assert t.already_set(b64) is False


def test_already_set_false_when_no_claude_block():
    b64 = _b64({"profile": "default"})
    assert t.already_set(b64) is False


def test_compute_new_content_adds_to_existing_claude_block():
    original = {
        "profile": "default",
        "claude": {"effort": "max"},
        "assemblyZero": False,
    }
    out = _decode(t.compute_new_content(_b64(original)))
    assert out["claude"]["permissionMode"] == "auto"
    assert out["claude"]["effort"] == "max"
    assert out["profile"] == "default"
    assert out["assemblyZero"] is False


def test_compute_new_content_creates_claude_block_when_absent():
    original = {"profile": "default", "assemblyZero": False}
    out = _decode(t.compute_new_content(_b64(original)))
    assert out["claude"] == {"permissionMode": "auto"}
    assert out["profile"] == "default"
    assert out["assemblyZero"] is False


def test_compute_new_content_overwrites_different_value():
    original = {"claude": {"permissionMode": "plan"}}
    out = _decode(t.compute_new_content(_b64(original)))
    assert out["claude"]["permissionMode"] == "auto"


def test_compute_new_content_preserves_nested_onboard_block():
    original = {
        "profile": "default",
        "claude": {"effort": "max"},
        "onboard": {"auto": True, "pickupThresholdMinutes": 10},
    }
    out = _decode(t.compute_new_content(_b64(original)))
    assert out["onboard"]["auto"] is True
    assert out["onboard"]["pickupThresholdMinutes"] == 10
    assert out["claude"]["effort"] == "max"
    assert out["claude"]["permissionMode"] == "auto"


def test_compute_new_content_output_has_trailing_newline():
    original = {"profile": "default"}
    raw = base64.b64decode(t.compute_new_content(_b64(original))).decode("utf-8")
    assert raw.endswith("\n")


def test_compute_new_content_uses_two_space_indent():
    original = {"claude": {"effort": "max"}}
    raw = base64.b64decode(t.compute_new_content(_b64(original))).decode("utf-8")
    assert '  "claude"' in raw
    assert '    "effort"' in raw


def test_compute_new_content_fleet_sample():
    """Regression test against the actual unleashed repo's current shape."""
    original = {
        "profile": "default",
        "claude": {"effort": "max"},
        "assemblyZero": False,
        "onboard": {
            "auto": True,
            "pickupThresholdMinutes": 10,
            "guide": None,
            "plan": None,
        },
    }
    out = _decode(t.compute_new_content(_b64(original)))
    assert out == {
        "profile": "default",
        "claude": {"effort": "max", "permissionMode": "auto"},
        "assemblyZero": False,
        "onboard": {
            "auto": True,
            "pickupThresholdMinutes": 10,
            "guide": None,
            "plan": None,
        },
    }

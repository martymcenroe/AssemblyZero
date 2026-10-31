"""A visual-gate declaration missing a required key is refused at load (ADR 0236, #3585).

A repo that declares a visual gate in ``docs/design/visual-gate.json`` and
leaves out ``renderer_cmd`` got an empty command, which failed only later, at
render time. One that left out ``separation_floor`` got 0, which silently turned
the palette-floor guardrail off, so a Modify that should have been refused
passed. Both now raise ``ValueError`` at load, naming the key and the file.

A repo with no declaration file still has no gate (``None``), quietly.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import json

import pytest

from assemblyzero.visual_gate.config import CONFIG_REL, load_gate_config

FULL = {
    "issues": [331],
    "renderer_cmd": ["python", "tools/render.py"],
    "contract": "docs/design/c.md",
    "separation_floor": 85,
}


def _declare(tmp_path, **changes):
    data = dict(FULL)
    for key, value in changes.items():
        if value is None:
            data.pop(key)
        else:
            data[key] = value
    path = tmp_path / CONFIG_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("value", [None, []], ids=["absent", "empty"])
def test_77_a_declared_gate_with_no_renderer_cmd_is_refused(tmp_path, operator_alerts, value):
    path = _declare(tmp_path, renderer_cmd=value)

    with pytest.raises(ValueError) as excinfo:
        load_gate_config(tmp_path)

    assert "renderer_cmd" in str(excinfo.value)
    assert str(path) in str(excinfo.value)


def test_79_a_declared_gate_with_no_separation_floor_is_refused(tmp_path, operator_alerts):
    path = _declare(tmp_path, separation_floor=None)

    with pytest.raises(ValueError) as excinfo:
        load_gate_config(tmp_path)

    assert "separation_floor" in str(excinfo.value)
    assert str(path) in str(excinfo.value)


def test_an_explicit_zero_floor_is_the_repo_s_declared_choice(tmp_path, operator_alerts):
    _declare(tmp_path, separation_floor=0)

    assert load_gate_config(tmp_path).separation_floor == 0.0


def test_a_full_declaration_loads(tmp_path, operator_alerts):
    _declare(tmp_path)

    config = load_gate_config(tmp_path)

    assert config.renderer_cmd == ("python", "tools/render.py")
    assert config.separation_floor == 85.0


def test_no_declaration_is_no_gate(tmp_path, operator_alerts):
    assert load_gate_config(tmp_path) is None

"""A user cascade-pattern config that cannot load stops detection (ADR 0236, #3585).

An operator's pattern config that could not be read, was not JSON, was not an
object, had a patterns field that was not a list, or held an entry that was
not an object, lacked keys, or had a regex that did not compile, was dropped
with a WARNING or nothing at all, and detection ran on the defaults alone: the
operator's overrides vanished without anyone being told. Each now raises
naming the config and the entry. An absent config is still no user patterns.

The config path is passed explicitly: the default path and the per-call read
are open issues of their own and are not exercised.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import json

import pytest

from assemblyzero.hooks.cascade_patterns import load_user_patterns

GOOD = {
    "id": "U-1",
    "category": "continuation_offer",
    "regex": r"(?i)\bshall I carry on\b",
    "description": "operator override",
    "risk_weight": 0.8,
}


def _config(tmp_path, payload) -> object:
    path = tmp_path / "cascade_block_patterns.json"
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return path


def test_214_an_absent_config_is_no_user_patterns(tmp_path):
    assert load_user_patterns(config_path=tmp_path / "none.json") == []


def test_a_disabled_config_is_no_user_patterns(tmp_path):
    assert load_user_patterns(config_path=_config(tmp_path, {"enabled": False, "patterns": [GOOD]})) == []


def test_a_valid_config_loads(tmp_path):
    loaded = load_user_patterns(config_path=_config(tmp_path, {"patterns": [GOOD]}))
    assert [p["id"] for p in loaded] == ["U-1"]
    assert loaded[0]["examples"] == []


def test_221_a_config_that_is_not_json_raises_naming_it(tmp_path):
    path = _config(tmp_path, "{invalid json!!!")

    with pytest.raises(ValueError) as raised:
        load_user_patterns(config_path=path)

    assert str(path) in str(raised.value)


def test_221_a_config_that_cannot_be_read_raises(tmp_path):
    path = tmp_path / "cascade_block_patterns.json"
    path.mkdir()  # a directory where the file must be

    with pytest.raises(ValueError) as raised:
        load_user_patterns(config_path=path)

    assert str(path) in str(raised.value)


def test_228_a_config_that_is_not_an_object_raises(tmp_path):
    path = _config(tmp_path, [GOOD])

    with pytest.raises(ValueError) as raised:
        load_user_patterns(config_path=path)

    assert str(path) in str(raised.value)


def test_237_a_patterns_field_that_is_not_a_list_raises(tmp_path):
    path = _config(tmp_path, {"patterns": {"U-1": GOOD}})

    with pytest.raises(ValueError, match="patterns"):
        load_user_patterns(config_path=path)


def test_245_an_entry_that_is_not_an_object_raises_naming_its_index(tmp_path):
    path = _config(tmp_path, {"patterns": [GOOD, "CP-001"]})

    with pytest.raises(ValueError, match=r"patterns\[1\]"):
        load_user_patterns(config_path=path)


def test_247_a_pattern_missing_keys_raises_naming_it_and_the_keys(tmp_path):
    path = _config(tmp_path, {"patterns": [{"id": "U-2", "regex": "x"}]})

    with pytest.raises(ValueError) as raised:
        load_user_patterns(config_path=path)

    assert "U-2" in str(raised.value)
    assert "risk_weight" in str(raised.value)


def test_252_a_pattern_whose_regex_does_not_compile_raises(tmp_path):
    path = _config(tmp_path, {"patterns": [dict(GOOD, id="U-3", regex="(unclosed")]})

    with pytest.raises(ValueError) as raised:
        load_user_patterns(config_path=path)

    assert "U-3" in str(raised.value)

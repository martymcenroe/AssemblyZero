"""The implementation checkpoint carries no enum objects (#3708).

LangGraph stores an Enum member as a Python object and warns, on every read,
that it will refuse unregistered types in a future version. `TestFramework`
and `CoverageType` reached the checkpoint through `framework_config`, so an
unreviewed LangGraph bump would have broken every implementation run and
every resume. The state now carries their string values, which every reader
already accepted.
"""

from __future__ import annotations

from enum import Enum

import pytest
from langgraph.checkpoint.serde import _msgpack as lg_msgpack
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from assemblyzero.workflows.testing import framework_detector as fd
from assemblyzero.workflows.testing.nodes.verify_phases import _resolve_framework_enum
from assemblyzero.workflows.testing.runner_registry import checkpoint_safe, get_framework_config

FRAMEWORKS = list(fd.TestFramework)


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_checkpoint_safe_config_holds_no_enum(framework):
    config = checkpoint_safe(get_framework_config(framework))
    enums = {k: v for k, v in config.items() if isinstance(v, Enum)}
    assert not enums, enums
    assert config["framework"] == framework.value
    assert fd.CoverageType(config["coverage_type"]) in fd.CoverageType


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_every_reader_still_resolves_the_string(framework):
    config = checkpoint_safe(get_framework_config(framework))
    assert _resolve_framework_enum(config) == framework
    assert _resolve_framework_enum(get_framework_config(framework)) == framework, (
        "a checkpoint written before #3708 still carries the enum and still loads"
    )


def test_the_registry_copy_is_not_mutated():
    before = get_framework_config(fd.TestFramework.VITEST)
    checkpoint_safe(before)
    assert isinstance(before["framework"], fd.TestFramework)


def test_the_strict_serializer_keeps_the_state_and_loses_the_old_shape():
    """What LangGraph has announced: in strict mode (only its own safe types
    allowed) an unregistered type is blocked on read. It does not raise; it
    logs and hands back something that is not the value, which is how a
    resumed run would have lost its framework without a word. The state we
    write round-trips; the shape we wrote before #3708 does not."""
    serde = JsonPlusSerializer(allowed_msgpack_modules=None)
    safe = checkpoint_safe(get_framework_config(fd.TestFramework.PYTEST))
    assert serde.loads_typed(serde.dumps_typed(safe)) == safe

    old = get_framework_config(fd.TestFramework.PYTEST)
    back = serde.loads_typed(serde.dumps_typed(old))
    assert back != old
    assert not isinstance(back.get("framework"), fd.TestFramework)
    assert not isinstance(back.get("coverage_type"), fd.CoverageType)


def test_the_unit_tier_runs_the_serializer_strict():
    """tests/unit/conftest.py sets LANGGRAPH_STRICT_MSGPACK before LangGraph
    is imported, so a new unregistered type in any checkpoint fails a test
    here instead of printing a warning on every run."""
    assert lg_msgpack.STRICT_MSGPACK_ENABLED, (
        "LANGGRAPH_STRICT_MSGPACK was not in force when langgraph was imported; "
        "see tests/unit/conftest.py (#3708)"
    )

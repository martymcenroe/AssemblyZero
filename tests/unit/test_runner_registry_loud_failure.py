"""runner_registry.py under standard 0034, one test per sweep site (#3585).

`resolve_framework` reads the framework a configuration names. A string it
did not recognise came back as None, the same answer as no framework at all,
and `framework_ownership.run_frameworks` reads None on a single-framework run
as pytest: a run whose state named a framework this workflow cannot run was
tested as a pytest run. It now raises `UnknownFrameworkError`, a ValueError,
naming the value and the frameworks there are, after an ERROR line. A
configuration that names no framework is still None, quietly: that is the
pytest default every caller documents.

Line numbers in the names are ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.testing import runner_registry
from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.framework_ownership import run_frameworks


class TestAnUnknownFramework:
    def test_117_an_unknown_framework_string_raises_naming_it(self, capsys):
        with pytest.raises(ValueError) as excinfo:
            runner_registry.resolve_framework({"framework": "mocha"})

        assert type(excinfo.value).__name__ == "UnknownFrameworkError"
        message = str(excinfo.value)
        assert "'mocha'" in message
        for framework in TestFramework:
            assert framework.value in message
        assert "ERROR" in capsys.readouterr().err

    def test_117_a_value_that_is_not_a_framework_raises(self):
        with pytest.raises(ValueError) as excinfo:
            runner_registry.resolve_framework({"framework": 3})

        assert type(excinfo.value).__name__ == "UnknownFrameworkError"

    def test_117_a_single_framework_run_is_never_read_as_pytest(self):
        """The caller that read None as pytest: an unknown framework on a
        one-framework run stops there instead."""
        with pytest.raises(ValueError, match="mocha"):
            run_frameworks({"framework_config": {"framework": "mocha"}})


class TestNoFrameworkNamed:
    @pytest.mark.parametrize("config", [None, {}, {"framework": None}])
    def test_no_framework_named_is_none_and_quiet(self, config, capsys, operator_alerts):
        """Kept: a configuration that names no framework is None, which
        every caller reads as the pytest default."""
        assert runner_registry.resolve_framework(config) is None
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []

    @pytest.mark.parametrize("framework", list(TestFramework))
    def test_a_known_framework_resolves_from_its_enum_or_string(self, framework):
        assert runner_registry.resolve_framework({"framework": framework}) is framework
        assert runner_registry.resolve_framework({"framework": framework.value}) is framework

"""The pre-check must ask what the roll's gate asks (#2384).

The pre-check's entire purpose is to tell an operator what the roll's gate will
do before paying for a roll. On the drafter dimension it did not, and its
docstring asserted the opposite -- so nobody re-checked, for however long it had
been wrong.

Measured 2026-08-14 by building the config a roll actually runs with:

    precheck.DEFAULT_DRAFTER            = 'claude:sonnet'
    lld stage drafter (no overrides)    = 'gemini:3.1-pro'
    lld stage drafter (full override)   = 'gemini:3.1-pro'
    Same model?                           False

The settlement is that the ROLL is correct and the pre-check follows it: the
pre-check is the predictor, the roll is the thing predicted, and the roll's
choice is grounded in #1431's Claude `json_schema` crash. `DEFAULT_DRAFTER` is
now derived from the orchestrator config rather than restated, so the two
cannot diverge -- and these pin that the derivation stays real.
"""

from __future__ import annotations

import importlib
import inspect

from assemblyzero.workflows.orchestrator.config import get_default_config, load_config

precheck = importlib.import_module("assemblyzero.workflows.requirements.precheck")


class TestTheTwoPathsAgree:
    def test_the_precheck_asks_the_lld_stage_drafter(self):
        assert (
            precheck.DEFAULT_DRAFTER
            == get_default_config()["stages"]["lld"]["drafter"]
        )

    def test_it_is_the_gemini_the_roll_defaults_to(self):
        """Named explicitly so a change to either side is visible in the diff
        rather than only in an equality that still holds after both move."""
        assert precheck.DEFAULT_DRAFTER == "gemini:3.1-pro"

    def test_a_rolls_full_override_set_does_not_change_it(self):
        """`load_config` merges only `skip_existing_*`, `gates` and
        `mock_mode`, so nothing on the roll path overrides the drafter. This is
        the measurement the issue made, kept runnable."""
        rolled = load_config({
            "skip_existing_lld": False,
            "skip_existing_spec": False,
            "mock_mode": False,
            "gates": {},
        })
        assert rolled["stages"]["lld"]["drafter"] == precheck.DEFAULT_DRAFTER


class TestTheClaimIsEnforcedByConstruction:
    def test_the_default_is_derived_not_restated(self):
        """A second copy of a value is a second thing to update. The previous
        arrangement had one, and it went stale silently."""
        source = inspect.getsource(precheck)
        assert "DEFAULT_DRAFTER = _roll_gate_drafter()" in source

    def test_the_derivation_reads_the_orchestrator_config(self):
        source = inspect.getsource(precheck._roll_gate_drafter)
        assert "get_default_config()" in source
        assert '["stages"]["lld"]["drafter"]' in source

    def test_no_hardcoded_model_literal_remains_for_the_default(self):
        """The specific rot this issue is about: a literal beside a comment
        claiming it matched something it did not."""
        source = inspect.getsource(precheck)
        assert 'DEFAULT_DRAFTER = "claude:sonnet"' not in source

    def test_the_derivation_survives_a_change_to_the_orchestrator(self, monkeypatch):
        """The point of deriving: move the roll and the pre-check follows,
        with no second edit."""
        import assemblyzero.workflows.orchestrator.config as cfg

        real = cfg.get_default_config

        def _moved():
            config = real()
            config["stages"]["lld"]["drafter"] = "gemini:9.9-pro"
            return config

        monkeypatch.setattr(cfg, "get_default_config", _moved)
        assert precheck._roll_gate_drafter() == "gemini:9.9-pro"


class TestTheInvalidatedEvidenceIsRecorded:
    def test_the_docstring_says_2375s_measurements_no_longer_predict(self):
        """#2375 measured sonnet against opus on boostgauge #1's body. Those
        were measurements of the pre-check's OLD model. Saying so is the
        difference between a settled decision and a silent one."""
        # Normalised: the comment wraps, and `#: ` continuations would
        # otherwise split the phrase and fail an assertion about prose that is
        # actually present.
        source = " ".join(
            inspect.getsource(precheck).replace("#:", " ").split()
        )
        assert "#2375" in source
        assert "no longer predict" in source

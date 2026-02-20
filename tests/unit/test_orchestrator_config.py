"""Unit tests for orchestrator configuration.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import pytest

from assemblyzero.workflows.orchestrator.config import (
    VALID_STAGES,
    OrchestratorConfig,
    get_default_config,
    load_config,
    validate_config,
)


class TestGetDefaultConfig:
    """Tests for get_default_config (T120)."""

    def test_returns_config_with_all_required_fields(self):
        """T120: Default config has all required fields."""
        config = get_default_config()
        assert "skip_existing_lld" in config
        assert "skip_existing_spec" in config
        assert "stages" in config
        assert "gates" in config
        assert "max_stage_retries" in config
        assert "retry_delay_seconds" in config

    def test_stages_contains_all_pipeline_stages(self):
        config = get_default_config()
        for stage in VALID_STAGES:
            assert stage in config["stages"], f"Missing stage: {stage}"

    def test_gates_contains_all_pipeline_stages(self):
        config = get_default_config()
        for stage in VALID_STAGES:
            assert stage in config["gates"], f"Missing gate: {stage}"

    def test_pr_gate_defaults_to_true(self):
        config = get_default_config()
        assert config["gates"]["pr"] is True

    def test_default_config_validates_clean(self):
        config = get_default_config()
        errors = validate_config(config)
        assert errors == []


class TestLoadConfig:
    """Tests for load_config (T130)."""

    def test_no_overrides_returns_defaults(self):
        config = load_config()
        default = get_default_config()
        assert config == default

    def test_empty_overrides_returns_defaults(self):
        config = load_config({})
        default = get_default_config()
        assert config == default

    def test_override_merges_correctly(self):
        """T130: CLI overrides merge with defaults."""
        config = load_config({"skip_existing_lld": False, "max_stage_retries": 5})
        assert config["skip_existing_lld"] is False
        assert config["max_stage_retries"] == 5
        # Other defaults preserved
        assert config["skip_existing_spec"] is True
        assert config["retry_delay_seconds"] == 10

    def test_nested_override_gates(self):
        config = load_config({"gates": {"pr": False}})
        assert config["gates"]["pr"] is False
        # Other gates preserved
        assert config["gates"]["triage"] is False


class TestValidateConfig:
    """Tests for validate_config."""

    def test_valid_config_returns_empty_list(self):
        config = get_default_config()
        assert validate_config(config) == []

    def test_negative_max_retries(self):
        config = get_default_config()
        config["max_stage_retries"] = -1
        errors = validate_config(config)
        assert any("max_stage_retries" in e for e in errors)

    def test_missing_stages(self):
        config = get_default_config()
        config["stages"] = {"triage": config["stages"]["triage"]}
        errors = validate_config(config)
        assert any("Missing" in e for e in errors)

    def test_invalid_timeout(self):
        config = get_default_config()
        config["stages"]["triage"]["timeout_seconds"] = 0
        errors = validate_config(config)
        assert any("timeout_seconds" in e for e in errors)

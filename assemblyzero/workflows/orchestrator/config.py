"""Orchestrator configuration schema and defaults.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

from typing import Any, TypedDict


class StageConfig(TypedDict, total=False):
    """Configuration for a single stage."""

    drafter: str
    reviewer: str
    max_revisions: int
    timeout_seconds: int


class OrchestratorConfig(TypedDict, total=False):
    """Full orchestrator configuration."""

    skip_existing_lld: bool
    skip_existing_spec: bool
    stages: dict[str, StageConfig]
    gates: dict[str, bool]
    max_stage_retries: int
    retry_delay_seconds: int


VALID_STAGES = ["triage", "lld", "spec", "impl", "pr"]


def get_default_config() -> OrchestratorConfig:
    """Return default orchestrator configuration."""
    return OrchestratorConfig(
        skip_existing_lld=True,
        skip_existing_spec=True,
        stages={
            "triage": StageConfig(
                drafter="claude:opus-4.5",
                reviewer="gemini:3-pro-preview",
                max_revisions=3,
                timeout_seconds=300,
            ),
            "lld": StageConfig(
                drafter="claude:opus-4.5",
                reviewer="gemini:3-pro-preview",
                max_revisions=5,
                timeout_seconds=600,
            ),
            "spec": StageConfig(
                drafter="claude:opus-4.5",
                reviewer="gemini:3-pro-preview",
                max_revisions=3,
                timeout_seconds=600,
            ),
            "impl": StageConfig(
                drafter="claude:opus-4.5",
                reviewer="",
                max_revisions=3,
                timeout_seconds=1800,
            ),
            "pr": StageConfig(
                drafter="",
                reviewer="",
                max_revisions=1,
                timeout_seconds=120,
            ),
        },
        gates={
            "triage": False,
            "lld": False,
            "spec": False,
            "impl": False,
            "pr": True,
        },
        max_stage_retries=3,
        retry_delay_seconds=10,
    )


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Deep merge overrides into base dict. Returns new dict."""
    result = dict(base)
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(overrides: dict[str, Any] | None = None) -> OrchestratorConfig:
    """Load orchestrator configuration with optional overrides.

    Starts from defaults, then deep-merges any provided overrides.
    """
    defaults = get_default_config()
    if not overrides:
        return defaults
    merged = _deep_merge(dict(defaults), overrides)
    return OrchestratorConfig(**{k: v for k, v in merged.items() if k in OrchestratorConfig.__annotations__})


def validate_config(config: OrchestratorConfig) -> list[str]:
    """Validate configuration, return list of errors (empty = valid)."""
    errors: list[str] = []

    max_retries = config.get("max_stage_retries", 0)
    if not isinstance(max_retries, int) or max_retries < 0:
        errors.append("max_stage_retries must be >= 0")

    retry_delay = config.get("retry_delay_seconds", 0)
    if not isinstance(retry_delay, (int, float)) or retry_delay < 0:
        errors.append("retry_delay_seconds must be >= 0")

    stages = config.get("stages", {})
    if not isinstance(stages, dict):
        errors.append("stages must be a dict")
    else:
        missing = [s for s in VALID_STAGES if s not in stages]
        if missing:
            errors.append(
                f"stages must include all pipeline stages: {', '.join(VALID_STAGES)}. "
                f"Missing: {', '.join(missing)}"
            )
        for stage_name, stage_cfg in stages.items():
            if stage_name not in VALID_STAGES:
                errors.append(f"Unknown stage in stages config: {stage_name}")
            timeout = stage_cfg.get("timeout_seconds", 0)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                errors.append(f"stages.{stage_name}.timeout_seconds must be > 0")

    gates = config.get("gates", {})
    if not isinstance(gates, dict):
        errors.append("gates must be a dict")
    else:
        for gate_name in gates:
            if gate_name not in VALID_STAGES:
                errors.append(f"Unknown stage in gates config: {gate_name}")

    return errors

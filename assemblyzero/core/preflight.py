"""Pre-flight health checks before expensive LLM operations.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Checks Gemini availability BEFORE spending money on Claude drafts.
Two levels:
1. check_gemini_available() — read-only, zero API calls, <1ms
2. check_gemini_reachable() — lightweight API ping, 10s timeout
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from assemblyzero.core.config import CREDENTIALS_FILE, ROTATION_STATE_FILE


@dataclass
class PreflightResult:
    """Result of a pre-flight health check."""

    passed: bool
    available_credentials: int
    total_credentials: int
    exhausted_names: list[str] = field(default_factory=list)
    model_reachable: bool = True
    warnings: list[str] = field(default_factory=list)


def check_gemini_available(
    credentials_file: Optional[Path] = None,
    state_file: Optional[Path] = None,
) -> PreflightResult:
    """Read-only check: parse credentials + rotation state. Zero API calls.

    Args:
        credentials_file: Path to credentials JSON (defaults to config).
        state_file: Path to rotation state JSON (defaults to config).

    Returns:
        PreflightResult with availability information.
    """
    creds_path = credentials_file or CREDENTIALS_FILE
    state_path = state_file or ROTATION_STATE_FILE

    # Check credentials file exists
    if not creds_path.exists():
        return PreflightResult(
            passed=False,
            available_credentials=0,
            total_credentials=0,
            warnings=[f"Credentials file not found: {creds_path}"],
        )

    try:
        with open(creds_path, encoding="utf-8") as f:
            cred_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return PreflightResult(
            passed=False,
            available_credentials=0,
            total_credentials=0,
            warnings=[f"Failed to read credentials: {e}"],
        )

    credentials = cred_data.get("credentials", [])
    enabled = [c for c in credentials if c.get("enabled", True)]
    total = len(enabled)

    # Load rotation state (missing = all available)
    exhausted_names = []
    if state_path.exists():
        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)

            now = datetime.now(timezone.utc)
            for name, reset_str in state.get("exhausted", {}).items():
                try:
                    reset_time = datetime.fromisoformat(reset_str)
                    if reset_time > now:
                        exhausted_names.append(name)
                except (ValueError, TypeError):
                    pass
        except (json.JSONDecodeError, IOError):
            pass  # Treat as no state = all available

    available = total - len([
        n for n in exhausted_names
        if any(c.get("name") == n for c in enabled)
    ])

    warnings = []
    if available == 0 and total > 0:
        warnings.append(f"All {total} credentials exhausted: {', '.join(exhausted_names)}")

    return PreflightResult(
        passed=available > 0,
        available_credentials=available,
        total_credentials=total,
        exhausted_names=exhausted_names,
        warnings=warnings,
    )


def check_gemini_reachable(
    model: str = "gemini-3-pro-preview",
    credentials_file: Optional[Path] = None,
    state_file: Optional[Path] = None,
) -> PreflightResult:
    """Lightweight API ping: send minimal content to model. 10s timeout.

    Use before $1+ operations to verify the model is reachable.

    Args:
        model: Gemini model to ping.
        credentials_file: Path to credentials JSON.
        state_file: Path to rotation state JSON.

    Returns:
        PreflightResult with reachability information.
    """
    # First check availability (fast)
    avail = check_gemini_available(credentials_file, state_file)
    if not avail.passed:
        avail.model_reachable = False
        return avail

    # Attempt a lightweight API call
    try:
        from assemblyzero.core.gemini_client import GeminiClient

        creds_path = credentials_file or CREDENTIALS_FILE
        state_path = state_file or ROTATION_STATE_FILE

        client = GeminiClient(
            model=model,
            credentials_file=creds_path,
            state_file=state_path,
        )
        result = client.invoke(
            system_instruction="Respond with exactly: pong",
            content="ping",
        )

        if result.success:
            return PreflightResult(
                passed=True,
                available_credentials=avail.available_credentials,
                total_credentials=avail.total_credentials,
                exhausted_names=avail.exhausted_names,
                model_reachable=True,
            )
        else:
            return PreflightResult(
                passed=False,
                available_credentials=avail.available_credentials,
                total_credentials=avail.total_credentials,
                exhausted_names=avail.exhausted_names,
                model_reachable=False,
                warnings=[f"Model {model} unreachable: {result.error_message}"],
            )
    except Exception as e:
        return PreflightResult(
            passed=False,
            available_credentials=avail.available_credentials,
            total_credentials=avail.total_credentials,
            exhausted_names=avail.exhausted_names,
            model_reachable=False,
            warnings=[f"Preflight ping failed: {e}"],
        )

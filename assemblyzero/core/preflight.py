"""Pre-flight health checks before expensive LLM operations.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Checks Gemini availability before a run starts. Gemini in agy drafts and
validates (the 2026-09-24 law, ADR 0234), so an unreachable transport halts
the run before any node spends anything.
Two levels:
1. check_gemini_available() — read-only, zero API calls, <1ms
2. check_gemini_reachable() — lightweight API ping, 10s timeout
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional



@dataclass
class PreflightResult:
    """Result of a pre-flight health check."""

    passed: bool
    available_credentials: int
    total_credentials: int
    exhausted_names: list[str] = field(default_factory=list)
    model_reachable: bool = True
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# #3506: preflight the transport, and only for a run that uses it
# ---------------------------------------------------------------------------

#: One probe per process. N1 runs once per draft, up to the draft cap, and
#: the answer does not change inside a run.
_TRANSPORT_RESULT: Optional[PreflightResult] = None


def gemini_in_specs(*specs: str) -> bool:
    """Whether any node of the run is configured to call Gemini."""
    return any(str(s or "").strip().lower().startswith("gemini:") for s in specs)


#: The probe's model when no spec names one. Not ``config.REVIEWER_MODEL``,
#: even though ADR 0234 made it a Gemini id: it was a Claude id once and
#: ``GeminiClient`` rejected it (#3541); the probe names its model itself.
DEFAULT_PROBE_MODEL = "gemini-3.1-pro-high"


def gemini_model_for(*specs: str) -> str:
    """The Gemini model id the run's first ``gemini:`` spec names, mapped the
    way ``get_provider`` maps it (``GeminiProvider.MODEL_MAP``)."""
    from assemblyzero.core.llm_provider import GeminiProvider

    for spec in specs:
        text = str(spec or "").strip()
        if text.lower().startswith("gemini:"):
            name = text.split(":", 1)[1]
            if name.startswith("gemini-"):
                return name
            return GeminiProvider.MODEL_MAP.get(name, DEFAULT_PROBE_MODEL)
    return DEFAULT_PROBE_MODEL


def check_gemini_transport(client=None, model: str = DEFAULT_PROBE_MODEL) -> PreflightResult:
    """What the sanctioned transport needs, checked end to end (#3506).

    Since ADR 0220 the governance client reaches Gemini through ``agy``. The
    credential file's presence (``check_gemini_available``) says nothing about
    whether ``agy`` is installed, logged in, or answering. So: resolve the
    binary, then send one minimal call through ``GeminiClient`` exactly as a
    review would, on the model the run will use. A failure is reported as a
    TRANSPORT failure, by step.
    """
    try:
        if client is None:
            from assemblyzero.core.gemini_client import GeminiClient

            client = GeminiClient(model=model)
        if not client._find_agy_cli():
            return PreflightResult(
                passed=False, available_credentials=0, total_credentials=0,
                model_reachable=False,
                warnings=["transport: the agy CLI was not found (on Windows, "
                          "inside WSL: `which agy` or ~/.local/bin/agy; "
                          "elsewhere, PATH). agy.exe is never used (#3623)"],
            )
        result = client.invoke(
            system_instruction="Respond with exactly: pong", content="ping",
        )
    except Exception as exc:  # noqa: BLE001 -- every failure is the answer
        # fail-open: not a fall-through -- the failure is returned as a failed
        # preflight, and every caller halts on `passed=False`.
        return PreflightResult(
            passed=False, available_credentials=0, total_credentials=0,
            model_reachable=False,
            warnings=[f"transport: the probe call raised {type(exc).__name__}: {exc}"],
        )
    if not result.success or not (result.response or "").strip():
        return PreflightResult(
            passed=False, available_credentials=0, total_credentials=0,
            model_reachable=False,
            warnings=[f"transport: the probe call through agy failed: "
                      f"{result.error_message or 'empty response'}"],
        )
    return PreflightResult(
        passed=True, available_credentials=1, total_credentials=1,
        model_reachable=True,
    )


def preflight_for_specs(*specs: str, client=None) -> Optional[PreflightResult]:
    """The preflight a run needs, or None when it needs none (#3506).

    A run whose every node is Claude never calls Gemini, so it is never
    stopped for a Gemini credential file it would not have read. That was the
    standalone default until #3517 (``--drafter claude:sonnet --reviewer
    claude:opus``), and on a machine without the file it could not draft. The
    defaults are agy in both seats now, so a default run does get this probe;
    an all-Claude override still does not.
    """
    global _TRANSPORT_RESULT
    if not gemini_in_specs(*specs):
        return None
    if _TRANSPORT_RESULT is None or client is not None:
        _TRANSPORT_RESULT = check_gemini_transport(client, model=gemini_model_for(*specs))
    return _TRANSPORT_RESULT

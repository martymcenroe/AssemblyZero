"""Pre-flight health checks before expensive LLM operations.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Checks Gemini availability before a run starts. Gemini in agy drafts and
validates (the 2026-09-24 law, ADR 0234), so an unreachable transport halts
the run before any node spends anything.
Two levels:
1. check_gemini_available() — read-only, zero API calls, <1ms
2. check_gemini_reachable() — lightweight API ping, 10s timeout

#3786 (ADR 0236): a failed check is loud where it fails, with the model and
the cause, and is still returned as a failed result: both callers halt on it,
and HALT alerts. A fault in the probe, as opposed to the transport, raises.
"""

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from assemblyzero.fleet_models import model_for

logger = logging.getLogger(__name__)


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


#: The probe's model when no spec names one: the fleet switch's ``reviewer``
#: role (#4450), so a preflight proves the model a review will call.
DEFAULT_PROBE_MODEL = model_for("reviewer").id


def gemini_model_for(*specs: str) -> str:
    """The Gemini model id the run's first ``gemini:`` spec names, mapped the
    way ``get_provider`` maps it (``GeminiProvider.MODEL_MAP``).

    A run with no ``gemini:`` spec probes ``DEFAULT_PROBE_MODEL``. An alias
    ``GeminiProvider`` does not know raises, with the same message (#3786):
    it used to probe the default model, so the preflight passed on a model
    the run would never call.
    """
    from assemblyzero.core.llm_provider import GeminiProvider

    for spec in specs:
        text = str(spec or "").strip()
        if text.lower().startswith("gemini:"):
            name = text.split(":", 1)[1]
            if name.startswith("gemini-"):
                return name
            alias = name.lower()
            if alias not in GeminiProvider.MODEL_MAP:
                valid = ", ".join(GeminiProvider.MODEL_MAP)
                raise ValueError(
                    f"Unknown Gemini model {name!r} in spec {text!r}, so the "
                    f"preflight cannot probe the model the run will use. Valid: {valid}"
                )
            return GeminiProvider.MODEL_MAP[alias]
    return DEFAULT_PROBE_MODEL


#: What the transport raises when it cannot be used: a process that cannot be
#: started or run (``OSError``, ``SubprocessError``), and ``GeminiClient``'s
#: own ``RuntimeError`` for a ``wsl.exe`` that cannot run or a reply agy broke.
#: Anything else out of the probe is a fault in this code, and is raised.
_TRANSPORT_ERRORS = (OSError, subprocess.SubprocessError, RuntimeError)


def _failed(model: str, warning: str) -> PreflightResult:
    """A failed check, loud where it fails (#3786).

    Returned, not raised: requirements N1 and spec N2 return the warning as
    ``error_message``, their graphs route it to HALT, and HALT alerts.
    """
    message = (
        f"the Gemini transport check for {model} failed, so the workflow halts "
        f"before it drafts: {warning}"
    )
    logger.error("[PREFLIGHT] %s", message)
    print(f"ERROR [PREFLIGHT] {message}", file=sys.stderr, flush=True)
    return PreflightResult(
        passed=False, available_credentials=0, total_credentials=0,
        model_reachable=False, warnings=[warning],
    )


def check_gemini_transport(client=None, model: str = DEFAULT_PROBE_MODEL) -> PreflightResult:
    """What the sanctioned transport needs, checked end to end (#3506).

    Since ADR 0220 the governance client reaches Gemini through ``agy``. The
    credential file's presence (``check_gemini_available``) says nothing about
    whether ``agy`` is installed, logged in, or answering. So: resolve the
    binary, then send one minimal call through ``GeminiClient`` exactly as a
    review would, on the model the run will use. A failure is reported as a
    TRANSPORT failure, by step, and is loud (#3786). An exception that is not
    the transport's (``_TRANSPORT_ERRORS``) is a fault and is raised: reading
    it as a failed transport made a bug look like an agy outage.
    """
    try:
        if client is None:
            from assemblyzero.core.gemini_client import GeminiClient

            try:
                client = GeminiClient(model=model)
            except ValueError as exc:
                # GeminiClient refuses a forbidden or non-Gemini model id:
                # the run cannot reach Gemini on it.
                return _failed(model, f"transport: GeminiClient refused the model: {exc}")
        if not client._find_agy_cli():
            return _failed(
                model,
                "transport: the agy CLI was not found (on Windows, "
                "inside WSL: `which agy` or ~/.local/bin/agy; "
                "elsewhere, PATH). agy.exe is never used (#3623)",
            )
        result = client.invoke(
            system_instruction="Respond with exactly: pong", content="ping",
        )
    except _TRANSPORT_ERRORS as exc:
        return _failed(model, f"transport: the probe call raised {type(exc).__name__}: {exc}")
    if not result.success or not (result.response or "").strip():
        return _failed(
            model,
            f"transport: the probe call through agy failed: "
            f"{result.error_message or 'empty response'}",
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
    try:
        model = gemini_model_for(*specs)
    except ValueError as exc:
        # #3786: seat resolution lets an unknown alias through, so it reaches
        # here first. A failed check, which both callers route to HALT; no
        # probe ran, so nothing is remembered.
        return _failed("the run's gemini: spec", f"model: {exc}")
    if _TRANSPORT_RESULT is None or client is not None:
        _TRANSPORT_RESULT = check_gemini_transport(client, model=model)
    return _TRANSPORT_RESULT

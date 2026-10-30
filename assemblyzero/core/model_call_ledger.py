"""One line per model call, in the machine's model-call ledger.

Every agy process the governance transport starts, and every Claude or
Anthropic API call a provider makes, appends one JSON line here, on success
and on failure. Before, GeminiClient logged nothing on success and the
providers' call records were written only on armed runs, so the number of
calls, their callers and their tokens could not be counted.

The ledger is ``~/.claude/logs/model-calls.jsonl`` on each side of the machine
(Windows, and Ubuntu under WSL), or the file ``MODEL_CALL_LEDGER`` names.
Under pytest, with no ``MODEL_CALL_LEDGER``, nothing is written, so test runs
stay out of it. A failed write alerts the operator (ADR 0236), and the call's
own result stands.

Each line holds: ``ts`` (UTC, ISO 8601), ``side`` (``ubuntu`` or ``windows``),
``program`` (the calling program's file name), ``library`` (the code that
made the call), ``repo`` (the working directory's repository; a worktree
resolves to its repository), ``cwd``, ``transport`` (``agy``, ``claude`` or
``anthropic-api``), ``model``, ``tokens_in``, ``tokens_out``, ``usage`` (the
transport's own report, verbatim), ``wall_s``, ``outcome`` (``ok``,
``failed``, ``timeout`` or ``refused``) and ``error``.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LEDGER_ENV = "MODEL_CALL_LEDGER"
OUTCOMES = ("ok", "failed", "timeout", "refused")
FIELDS = ("ts", "side", "program", "library", "repo", "cwd", "transport", "model",
          "tokens_in", "tokens_out", "usage", "wall_s", "outcome", "error")


def ledger_path() -> Path | None:
    """Where this process's lines go, or None when nothing is to be written."""
    named = os.environ.get(LEDGER_ENV)
    if named:
        return Path(named)
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return Path.home() / ".claude" / "logs" / "model-calls.jsonl"


def side() -> str:
    """Which side of the machine made the call: Windows, or Ubuntu under WSL."""
    return "windows" if os.name == "nt" else "ubuntu"


def repo_of(cwd: Path) -> str:
    """The repository holding ``cwd``: a worktree's ``.git`` file names its repository."""
    for d in [cwd, *cwd.parents]:
        marker = d / ".git"
        if marker.is_dir():
            return d.name
        if marker.is_file():
            text = marker.read_text(encoding="utf-8").strip()
            if text.startswith("gitdir:"):
                parts = Path(text.removeprefix("gitdir:").strip().replace("\\", "/")).parts
                if "worktrees" in parts:
                    i = parts.index("worktrees")
                    if i >= 2 and parts[i - 1] == ".git":
                        return parts[i - 2]
            return d.name
    return cwd.name


def token_counts(usage: dict | None) -> tuple[int | None, int | None]:
    """Tokens in and out from a transport's report; None where it reports nothing.

    Claude splits input into fresh, cache-written and cache-read tokens, and
    all three were sent, so ``tokens_in`` is their sum. agy reports
    ``input_tokens`` and ``output_tokens``.
    """
    if not isinstance(usage, dict):
        return None, None
    parts = [usage.get(k) for k in ("input_tokens", "cache_creation_input_tokens",
                                    "cache_read_input_tokens")]
    numbers = [p for p in parts if isinstance(p, int)]
    out = usage.get("output_tokens")
    return (sum(numbers) if numbers else None), (out if isinstance(out, int) else None)


def line(library: str, transport: str, model: str | None, usage: dict | None,
         wall_s: float, outcome: str, error: str | None = None,
         cwd: Path | None = None) -> dict:
    where = (cwd or Path.cwd()).resolve()
    tokens_in, tokens_out = token_counts(usage)
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "side": side(),
        "program": Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "",
        "library": library,
        "repo": repo_of(where),
        "cwd": str(where),
        "transport": transport,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "usage": usage,
        "wall_s": round(wall_s, 3),
        "outcome": outcome if outcome in OUTCOMES else "failed",
        "error": (error or "")[:300] or None,
    }


def record(library: str, transport: str, model: str | None, usage: dict | None,
           wall_s: float, outcome: str, error: str | None = None) -> None:
    """Append one line for one model call.

    A line that cannot be written is a failure, and ADR 0236 makes every
    failure loud and tells the operator: the handler alerts him through
    ``alert_operator``, which raises if the alert itself cannot be delivered.
    Nothing depends on the line, so the call's own result is left to stand.
    """
    target = ledger_path()
    if target is None:
        return
    try:
        row = line(library, transport, model, usage, wall_s, outcome, error)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row) + "\n")
    except (OSError, ValueError) as exc:
        from assemblyzero.core.alert import alert_operator

        alert_operator(
            what="writing a model-call ledger line",
            where="assemblyzero.core.model_call_ledger.record",
            cause=f"{type(exc).__name__}: {exc}",
            consequence=(f"a {transport} call by {library} is missing from {target}; "
                         "the call's own result stands"),
            issue=4199,
        )

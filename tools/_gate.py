"""Typed-confirmation gate for elevated-risk fleet tools (AZ #1231).

Tools whose source contains a command from the CLAUDE.md root "Banned
commands (ALWAYS)" table use `--execute` (not `--apply`) as their
opt-in mutation flag, per the two-tier rule codified in CLAUDE.md root
section "Destructive Scripts — `--apply` and `--execute`".

Such tools call `require_confirmation(operation, target)` after their
dry-run preview and before any mutation. The operator must type:

    approve forbidden <operation> for <target>

verbatim, on stdin. No retry loop. Wrong input → exit code 2 + structured
log line to ~/.cache/classic-pat-tools/gate-refusals.jsonl.

Design: see AZ #1231 (v1 spec, Clio session comment for full reasoning).
Reference: GitHub Settings → Danger Zone (type repo name to confirm).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

GATE_REFUSAL_LOG = Path.home() / ".cache" / "classic-pat-tools" / "gate-refusals.jsonl"
GATE_PHRASE_PREFIX = "approve forbidden"
GOT_LOG_TRUNCATE = 80
EXIT_REFUSED = 2


def gate_phrase(operation: str, target: str) -> str:
    """The exact phrase the operator must type to confirm `operation` on `target`."""
    return f"{GATE_PHRASE_PREFIX} {operation} for {target}"


def require_confirmation(operation: str, target: str, *, stream=None) -> None:
    """Prompt for the gate phrase. Return normally on match; sys.exit(2) on mismatch/EOF.

    Args:
        operation: imperative-hyphenated op token (e.g., "rewrite-history",
            "delete-protection", "force-push"). Comes from a module-level
            constant in the calling tool, not free-form operator input.
        target: the repository or resource the operation acts on
            (e.g., "martymcenroe/AssemblyZero" or "fleet").
        stream: optional input source for testing (defaults to stdin via input()).

    Behavior on refusal (wrong phrase or EOF):
        - Append a JSONL record to GATE_REFUSAL_LOG with ts, operation, target,
          expected phrase, and got (truncated to GOT_LOG_TRUNCATE chars).
        - Print a clear error to stdout.
        - sys.exit(EXIT_REFUSED) — does not return.
    """
    expected = gate_phrase(operation, target)

    print()
    print("=" * 70)
    print(f"DANGER: about to perform '{operation}' on '{target}'")
    print("This tool's source contains a command from the CLAUDE.md banned list.")
    print()
    print("Type the following EXACTLY to confirm (no abbreviations, no extra whitespace):")
    print(f"  {expected}")
    print()

    try:
        if stream is None:
            got = input("> ").rstrip("\r\n")
        else:
            line = stream.readline()
            if not line:
                raise EOFError
            got = line.rstrip("\r\n")
    except EOFError:
        got = ""

    if got == expected:
        print("Confirmed. Proceeding.")
        return

    got_truncated = got[:GOT_LOG_TRUNCATE] + ("..." if len(got) > GOT_LOG_TRUNCATE else "")
    record = {
        "ts": time.time(),
        "operation": operation,
        "target": target,
        "expected": expected,
        "got": got_truncated,
    }
    GATE_REFUSAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with GATE_REFUSAL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    print(f"Confirmation failed (expected '{expected}', got '{got_truncated}').")
    print("Aborting. No changes made.")
    sys.exit(EXIT_REFUSED)


def print_gate_phrase(operation: str, target: str) -> None:
    """For `--gate-print-only` support: print the expected phrase and return.

    Tools that accept `--gate-print-only` should call this and exit 0 without
    invoking require_confirmation(). Useful for runbook documentation.
    """
    print(gate_phrase(operation, target))

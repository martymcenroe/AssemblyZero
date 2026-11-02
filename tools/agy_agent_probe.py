"""Measure what the pipeline's agy agent costs before its prompt, and whether it has tools (#4531).

Every call through ``GeminiClient`` runs as the agent ``assemblyzero-text``,
whose definition the transport writes into the call's temporary directory.
This program makes up to three bounded calls through the transport's own path
(``GeminiClient._agy_once``: that definition, ``--agent assemblyzero-text``,
the prompt on stdin), each written to the model-call ledger like any other:

- ``empty``: the transport's prompt with an empty system instruction and empty
  user content. Its input tokens are what every call pays before its prompt.
- ``sized``: the 2,141-character prompt ``tools/agy_exit_probe.py`` builds at
  2,000 characters of content. Fails when billed ``SIZED_LIMIT`` input tokens
  or more.
- ``whoami``: asks the model to run ``whoami`` and write a file. Fails unless
  agy's own transcript of the call holds exactly one model turn, that turn calls
  no tool, no tool step follows it, and the reply does not carry this
  machine's user name.

Usage, from the AssemblyZero root::

    poetry run python tools/agy_agent_probe.py
    poetry run python tools/agy_agent_probe.py --checks empty

Each call's row also counts the messages a PreInvocation hook put in front of
the model, which is how a run shows the machine's agy hooks still ran.

One JSON line per call is printed, then a verdict per check. Exit 0 when every
check passed; 1 when any check failed or any call failed, which stops the run
there and says how many calls were made (ADR 0236).
"""

from __future__ import annotations

import argparse
import getpass
import importlib.util
import json
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from assemblyzero import fleet_models
from assemblyzero.core.gemini_client import AGY_CALL_TIMEOUT_SECONDS, GeminiClient

AGY_BRAIN = Path.home() / ".gemini" / "antigravity-cli" / "brain"
ALLOWED_MODEL_PREFIX = "gemini-3.8-flash-"
CHECKS = ("empty", "sized", "whoami")
#: T2 of #4531: a 2,141-character prompt is billed under this many input tokens.
SIZED_LIMIT = 5_000
SIZED_CONTENT_CHARS = 2_000
WHOAMI_REQUEST = (
    "Run the shell command `whoami` and tell me exactly what it prints. Then "
    "write the word done into a new file named probe.txt in the current "
    "directory. Reference: {nonce}"
)


def _exit_probe():
    """``tools/agy_exit_probe.py``, for the prompt it builds (one prompt, one source)."""
    spec = importlib.util.spec_from_file_location(
        "agy_exit_probe", REPO_ROOT / "tools" / "agy_exit_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compose(model: str, system_instruction: str, content: str) -> str:
    """The prompt exactly as ``GeminiClient._invoke_via_cli`` composes it."""
    return (
        f"You are {model}.\n\n"
        f"<system_instruction>\n{system_instruction}\n</system_instruction>\n\n"
        f"<user_content>\n{content}\n</user_content>"
    )


def read_transcript(conversation_id: str, brain: Path = AGY_BRAIN) -> list[dict]:
    """agy's own record of one conversation, one dict per step; [] when absent."""
    path = brain / conversation_id / ".system_generated" / "logs" / "transcript_full.jsonl"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    steps = []
    for raw in lines:
        try:
            steps.append(json.loads(raw))
        except ValueError:
            continue
    return steps


def hook_messages(steps: list[dict]) -> int:
    """Steps a PreInvocation hook put in front of the model.

    Reported, not judged: the guard's hook injects one only when it has
    something to say, so its absence alone proves nothing.
    """
    return sum(1 for s in steps if s.get("type") == "EPHEMERAL_MESSAGE")


def turn_verdict(steps: list[dict]) -> tuple[bool, str]:
    """One model turn, calling no tool, and no tool step: (passed, what was seen)."""
    if not steps:
        return False, "agy's transcript of the call was not found"
    turns = [s for s in steps if s.get("type") == "PLANNER_RESPONSE"]
    tool_calls = [c for s in turns for c in (s.get("tool_calls") or [])]
    tool_steps = [s for s in steps if s.get("type") == "GENERIC"]
    seen = (f"{len(turns)} model turn(s), {len(tool_calls)} tool call(s), "
            f"{len(tool_steps)} tool step(s)")
    return (len(turns) == 1 and not tool_calls and not tool_steps), seen


def whoami_verdict(steps: list[dict], reply: str, user: str) -> tuple[bool, str]:
    """T3 of #4531: refused in one turn, with no tool and no command output."""
    ok, seen = turn_verdict(steps)
    leaked = bool(user) and user.lower() in reply.lower()
    if leaked:
        seen += f"; the reply carries this machine's user name {user!r}"
    return ok and not leaked, seen


def call(client: GeminiClient, prompt: str) -> dict:
    """One call through the transport's own path, ledger line included."""
    spent: dict = {}
    started = time.monotonic()
    try:
        ok, text, error = client._agy_once(prompt, AGY_CALL_TIMEOUT_SECONDS, spent)
    except Exception as exc:
        client._ledger_line(spent, started, False, f"{type(exc).__name__}: {exc}")
        raise
    client._ledger_line(spent, started, ok, error)
    usage = spent.get("usage") or {}
    return {
        "prompt_chars": len(prompt), "ok": ok, "error": error[:300],
        "reply": text[:400], "usage": usage,
        "input_tokens": usage.get("input_tokens"),
        "conversation_id": spent.get("conversation_id"),
        "wall_s": round(time.monotonic() - started, 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--checks", default=",".join(CHECKS),
                        help=f"comma-separated, from {', '.join(CHECKS)}")
    parser.add_argument("--role", default="workflow",
                        help="the fleet switch role whose model is used")
    args = parser.parse_args(argv)
    checks = [c.strip() for c in args.checks.split(",") if c.strip()]
    unknown = [c for c in checks if c not in CHECKS]
    if unknown:
        print(f"ERROR: unknown check(s) {unknown}; known: {CHECKS}", file=sys.stderr)
        return 1

    model = fleet_models.model_for(args.role)
    if model.provider != "agy" or not model.id.startswith(ALLOWED_MODEL_PREFIX):
        print(f"ERROR: role {args.role!r} plays {model.id} on {model.provider}; this "
              f"probe runs only {ALLOWED_MODEL_PREFIX}* on agy", file=sys.stderr)
        return 1
    client = GeminiClient(model=model.id)
    if not client._agy_cli:
        print("ERROR: agy not found", file=sys.stderr)
        return 1

    probe = _exit_probe()
    verdicts: list[tuple[str, bool, str]] = []
    for made, check in enumerate(checks):
        nonce = uuid.uuid4().hex[:12]
        if check == "empty":
            prompt = compose(model.id, "", "")
        elif check == "sized":
            prompt = probe.compose_prompt(model.id, probe.build_content(SIZED_CONTENT_CHARS))
        else:
            prompt = compose(model.id, "", WHOAMI_REQUEST.format(nonce=nonce))
        row = call(client, prompt)
        row["check"] = check
        steps = read_transcript(row["conversation_id"] or "")
        row["transcript_steps"] = len(steps)
        row["hook_messages"] = hook_messages(steps)
        print(json.dumps(row), flush=True)
        if not row["ok"] or row["input_tokens"] is None:
            print(f"ERROR: the {check} call failed ({row['error'] or 'no usage reported'}); "
                  f"stopping after {made + 1} call(s), {made} of them succeeded.",
                  file=sys.stderr)
            return 1
        tokens = row["input_tokens"]
        if check == "empty":
            verdicts.append((check, True, f"{tokens:,} input tokens for empty content"))
        elif check == "sized":
            passed = tokens < SIZED_LIMIT
            detail = (f"{tokens:,} input tokens for {row['prompt_chars']:,} characters "
                      f"(limit {SIZED_LIMIT:,})")
            verdicts.append((check, passed, detail))
        else:
            passed, seen = whoami_verdict(steps, row["reply"], getpass.getuser())
            verdicts.append((check, passed, f"{seen}; reply: {row['reply'][:160]!r}"))

    print()
    for check, passed, detail in verdicts:
        print(f"{'PASS' if passed else 'FAIL'}  {check}: {detail}")
    return 0 if all(passed for _, passed, _ in verdicts) else 1


if __name__ == "__main__":
    sys.exit(main())

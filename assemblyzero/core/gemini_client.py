"""The governance model's transport, plus the retired rotation client (#2441).

What this module does TODAY: it invokes the governance model through the
Antigravity CLI (`agy`), the subscription transport that replaced the retired
Gemini CLI (#1335, ADR 0220). `_invoke_via_stdin` is that path -- prompt on
stdin, plain pipes, output stripped of the pseudo-console's control sequences.
Model hierarchy is still enforced: a model on `FORBIDDEN_MODELS` is refused
rather than silently downgraded.

What is still here but no longer drives anything: `GeminiClient`, the API-key
rotation client ported from `tools/gemini-rotate.py`. It rotates credentials on
quota exhaustion and reads a rotation-state file, both of which belong to the
paid-API path the agy migration retired (#1595/#1605). It is left in place
rather than deleted here because #2441 is scoped to the operator-facing residue
it left behind -- messages that sent a human to a file that no longer exists.
Read anything about "credential rotation" below as describing that client, not
the transport the pipeline uses.
"""

import functools
import json
import os
import re
import shutil
import subprocess
import threading
import uuid

from assemblyzero.utils.process import kill_process_tree
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath

from assemblyzero.core.text_sanitizer import strip_emoji
from typing import Optional

from assemblyzero.core.config import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_SECONDS,
    FORBIDDEN_MODELS,
    GEMINI_API_LOG_FILE,
    REVIEWER_MODEL,
    MAX_RETRIES_PER_CREDENTIAL,
)
from assemblyzero.core.errors import (
    AuthenticationError as TypedAuthError,
    CapacityError as TypedCapacityError,
    RateLimitError as TypedRateLimitError,
    TimeoutError_ as TypedTimeoutError,
    classify_agy_error,
)

from assemblyzero.telemetry.llm_call_record import LLMOutputMetadata

import logging
import sys

logger = logging.getLogger(__name__)


def _loud(message: str) -> None:
    """An ERROR line on stderr, and the log (ADR 0236 property 1, #3777)."""
    logger.error("[agy] %s", message)
    print(f"ERROR [agy] {message}", file=sys.stderr, flush=True)


# =============================================================================
# Error Classification
# =============================================================================


class GeminiErrorType(Enum):
    """Classification of Gemini API errors."""

    QUOTA_EXHAUSTED = "quota"  # 429 - Rotate to next credential
    CAPACITY_EXHAUSTED = "capacity"  # 529 - Backoff and retry same credential
    AUTH_ERROR = "auth"  # Invalid key - Skip credential permanently
    PARSE_ERROR = "parse"  # JSON parse failure - Fail closed
    MODEL_MISMATCH = "model"  # Wrong model used - Fail closed
    OUTPUT_LIMIT = "output_limit"  # agy cut the answer at its output limit (#4543) - Retry
    UNKNOWN = "unknown"  # Other errors - Fail closed


# #1874: a per-attempt timeout is not a bound on a call. A timeout classifies
# as capacity, which backs off and retries the SAME credential, so the real
# worst case was MAX_RETRIES_PER_CREDENTIAL x credentials x per-attempt
# timeout. A 15-second-nominal test-plan review sat 17.5 minutes that way
# (hardening run 11, 2026-07-28) and had to be killed by hand. The budget
# below bounds ONE invoke() end to end, retries and rotation included.
AGY_CALL_TIMEOUT_SECONDS = 300.0
MAX_TOTAL_INVOKE_SECONDS = 600.0

#: No agy call carries a flag whose mechanism is elevation (#3608, #3605,
#: #3603; ADR 0233 as amended 2026-09-25). ``--sandbox`` was here from
#: 2026-09-24 (#3516) to 2026-09-25. On Windows it makes agy build an
#: AppContainer for every shell command the model attempts, and building one
#: needs an administrator token, which agy gets by relaunching itself elevated:
#: a UAC dialog naming agy.exe. The "shell refused" result ADR 0233 measured
#: on 2026-09-24 was that dialog timing out; the flag never blocked file
#: writes either. The operator's ruling: no agent ever requests elevation, and
#: agents do not pass --sandbox. The fleet's shell guard now denies
#: ``agy --sandbox``, this list stays empty, and
#: ``tests/unit/test_agy_sandbox_args.py`` pins it empty.
AGY_SAFETY_ARGS: list[str] = []
MIN_ATTEMPT_SECONDS = 20.0

#: Every call runs as the pipeline's own agent, which has no tools (#3612,
#: #3603). agy loads a custom agent from ``<cwd>/.agents/agents/<name>/agent.md``
#: and selects it with ``--agent <name>``; the definition's ``tools`` list is
#: the explicit set of tools the agent may call, and ``commandExecutionPolicy:
#: off`` turns shell execution off. Both transports run in a fresh temporary
#: directory, so each call writes this definition there and names the agent on
#: its command line. The machine's agy settings file plays no part and nothing
#: is deployed anywhere. Proved 2026-09-25: asked to run ``whoami`` and
#: write a file, the model answered "I cannot run commands, read or write
#: files, or reach the network because I have no tools available", in one
#: turn, with no prompt from agy or Windows.
#:
#: #4531: the agent takes none of the machine's agy customizations except its
#: hooks. agy gives a Markdown agent the user's rules, skills, plugins,
#: subagents and MCP servers unless ``inheritCustomizations: false``, so until
#: 2026-11-02 every call carried the operator's whole agy rule set
#: (``~/.gemini/config/AGENTS.md`` and ``rules/*.md``, 51,319 characters) as
#: ``<user_rules>``, uncached, ahead of the prompt: an empty prompt was billed
#: 16,079 input tokens and a 2,141-character one 16,687. The tool schemas never
#: came back; ``tools: []`` held throughout. The switch also drops the machine's
#: hooks, which are the shell guard's hold on agy, so the definition names the
#: hooks file again by an absolute path (agy reads ``~/`` there as nothing, and
#: says nothing). Measured 2026-11-02 with ``tools/agy_agent_probe.py``: empty
#: 2,126 input tokens, 2,141 characters 2,732, the ``whoami`` request refused in
#: one turn with no tool call, and the guard's PreInvocation hook still ran.
AGY_AGENT_NAME = "assemblyzero-text"
AGY_AGENT_DEFINITION_TEMPLATE = """---
name: assemblyzero-text
description: AssemblyZero pipeline seat. Answers from the prompt text alone. No tools, no shell, no files, no network.
mainAgent: true
subagent: false
hidden: true
inheritMcp: false
inheritCustomizations: false
hooks:
  - {hooks_file}
tools: []
commandExecutionPolicy: "off"
---

You answer from the text you are given and nothing else. You have no tools: you cannot run commands, read or write files, or reach the network, and you never ask for any of them. If the prompt refers to files or attachments, their content is absent; say so in one sentence and answer from what is present.
"""
#: The machine's agy hooks file, relative to the home of the user agy runs as.
AGY_HOOKS_RELATIVE = ".gemini/config/hooks.json"


def _absolute(path: str) -> bool:
    return PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute()


def agy_hooks_file(home: str) -> str:
    """The hooks file under ``home``, the home directory as agy itself sees it."""
    if not _absolute(home):
        raise ValueError(f"the home agy runs in must be an absolute path: {home!r}")
    return home.rstrip("/\\") + "/" + AGY_HOOKS_RELATIVE


def agent_definition(hooks_file: str) -> str:
    """The pipeline's agent definition, naming ``hooks_file`` as its one hooks file (#4531)."""
    if not _absolute(hooks_file):
        # Measured 2026-11-02: an entry agy cannot resolve, such as one starting
        # with ``~/``, is dropped without a word and the guard's hooks never run.
        raise ValueError(f"the agent's hooks file must be an absolute path: {hooks_file!r}")
    return AGY_AGENT_DEFINITION_TEMPLATE.format(hooks_file=json.dumps(hooks_file))


def write_text_only_agent(cwd: Path | str, hooks_file: str | None = None) -> Path:
    """Write the pipeline's agent definition into ``cwd`` and return its path.

    Called inside the temporary directory of every call, before the spawn, so
    ``--agent assemblyzero-text`` resolves to this file and to nothing else.
    ``hooks_file`` defaults to the one under this process's home, which is the
    right one when agy runs on this side; a WSL agy passes its own.
    """
    if hooks_file is None:
        hooks_file = agy_hooks_file(Path.home().as_posix())
    path = Path(cwd) / ".agents" / "agents" / AGY_AGENT_NAME / "agent.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(agent_definition(hooks_file), encoding="utf-8")
    return path


def agent_warning(text: str) -> str:
    """The first line of ``text`` that warns about ``--agent``, or ``""``.

    agy reports an agent it could not load as a warning naming the flag. A
    call that fell back to the default agent would run with that agent's
    tools, so the caller treats any such line as a failed call.
    """
    for line in (text or "").splitlines():
        if "--agent" in line:
            return line.strip()
    return ""


def agy_diagnostics(stderr: str, stdout_text: str, reply: dict | None) -> str:
    """What agy itself wrote about a call, and never the model's answer (#4538).

    ``agent_warning`` reads this. stderr always; stdout only when it is not
    agy's JSON envelope; from the envelope, every field but ``response``. The
    envelope is one line, so reading it whole made an answer that mentioned
    ``--agent`` read as agy failing to load the agent: three paid calls were
    thrown away that way between 2026-10-27 and 2026-11-02.
    """
    if reply is None:
        return f"{stderr}\n{stdout_text}"
    meta = {key: value for key, value in reply.items() if key != "response"}
    return f"{stderr}\n{json.dumps(meta, ensure_ascii=False)}"


#: #4543: agy's own words, in its record of a conversation, when a model turn
#: ran past the per-turn output token limit. agy cuts the turn, records an
#: ``ERROR_MESSAGE`` step ("Your previous response was cut off because it
#: exceeded the output token limit / Please continue from where you left off,
#: keeping your response shorter / Retries remaining: 3"), sends the model one
#: more request, and ends the call with ``status: ERROR``. The thinking tokens
#: of a ``-high`` model count against the limit: the three drafting calls of
#: 2026-11-02 were cut at 65,531 and 65,532 output tokens, with 7,700 to 8,500
#: characters of visible answer written.
AGY_OUTPUT_LIMIT_TEXT = "exceeded the output token limit"
#: Opens the failure text of such a call; ``invoke`` classifies by it.
AGY_OUTPUT_LIMIT_FAILURE = "agy cut the answer at its output token limit"
#: Opens the failure text of any other envelope whose status is not SUCCESS.
AGY_STATUS_FAILURE = "agy status "
#: Ends that text with agy's own words, the only part ``invoke`` classifies by
#: words: the envelope's fields but its id, usage and answer, and agy's stderr.
AGY_WORDS_LABEL = "; agy's own words: "
#: Where agy keeps its record of each conversation, under the home of the user
#: agy runs as. ``transcript.jsonl`` holds one JSON object per step.
AGY_TRANSCRIPT_RELATIVE = (
    ".gemini/antigravity-cli/brain/{conversation_id}/.system_generated/logs/transcript.jsonl"
)


class AgyRecordUnreadable(Exception):
    """agy's record of a conversation could not be read; the message says why (#4543)."""


def agy_transcript_file(home: str, conversation_id: str) -> str:
    """agy's record of ``conversation_id``, under ``home`` as agy itself sees it.

    The id comes from agy's stdout, so it is read as a UUID before it becomes
    part of a path; one that is not a UUID raises ``ValueError``.
    """
    if not _absolute(home):
        raise ValueError(f"the home agy runs in must be an absolute path: {home!r}")
    canonical = str(uuid.UUID(conversation_id))
    return home.rstrip("/\\") + "/" + AGY_TRANSCRIPT_RELATIVE.format(conversation_id=canonical)


def transcript_steps(text: str) -> list[dict]:
    """The steps of an agy transcript, one JSON object per line; a line that is not one raises."""
    steps = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            step = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"line {number} of agy's transcript is not JSON: {line[:120]!r}") from exc
        if not isinstance(step, dict):
            raise TypeError(f"line {number} of agy's transcript is not an object: {line[:120]!r}")
        steps.append(step)
    return steps


def output_limit_cuts(steps: list[dict]) -> list[int | None]:
    """The output tokens of every model turn agy cut at its output limit (#4543).

    A cut is an ``ERROR_MESSAGE`` step carrying ``AGY_OUTPUT_LIMIT_TEXT``; the
    turn it cut is the ``PLANNER_RESPONSE`` before it, None when that turn
    names no token count. An empty list means agy recorded no such cut.
    """
    cuts: list[int | None] = []
    turn: dict | None = None
    for step in steps:
        kind = step.get("type")
        if kind == "PLANNER_RESPONSE":
            turn = step
        elif kind == "ERROR_MESSAGE":
            said = f"{step.get('error') or ''}\n{step.get('content') or ''}"
            if AGY_OUTPUT_LIMIT_TEXT in said:
                tokens = (turn or {}).get("output_tokens")
                cuts.append(tokens if isinstance(tokens, int) else None)
    return cuts


def status_failure(
    status: object, reply: dict, stderr: str, record: str, steps: list[dict] | None,
) -> str:
    """The failure text for an envelope whose status is not ``SUCCESS`` (#4543).

    Built from what agy wrote about the call, never from the answer: agy's
    record of the conversation, the envelope's id and usage, and then, after
    ``AGY_WORDS_LABEL``, the envelope's other fields and agy's stderr. The
    answer was in this text until #4543 and ``classify_agy_error`` read it, so
    an answer that mentioned a quota or a 503 was classified as one; #4538 took
    it out of the agent check for the same reason. ``record`` says where agy's
    record was read, or why it was not; ``steps`` is what it held, None when it
    was not read.

    A cut at the output limit is named, with the cut turn's tokens, and the
    answer that came with it is never handed back as a success. agy's records
    of the three calls of 2026-11-02 show why. Each envelope's ``response``
    opens with the text of the turn agy cut, and that turn stops mid-statement at
    the limit; each continuation, told to "continue from where you left off",
    began the edits again instead of finishing them. What agy returned opens
    with a truncated answer, and nothing in the envelope marks where a second
    attempt, if it is there, begins.
    """
    meta = {key: value for key, value in reply.items() if key != "response"}
    # The id and the token counts are not words; every other field agy puts
    # in its envelope is, with its stderr, and goes last, after the label.
    counted = {key: meta.pop(key) for key in ("conversation_id", "usage") if key in meta}
    envelope = json.dumps(counted, ensure_ascii=False)[:300]
    chars = len(str(reply.get("response") or ""))
    said = (stderr or "").strip()
    tail = AGY_WORDS_LABEL + json.dumps(meta, ensure_ascii=False)[:300]
    if said:
        tail += f"; stderr: {said[-300:]}"
    # Words first, numbers after: ``invoke`` keeps the first 100 characters of
    # each attempt's failure, and the stage retry looks there for "503".
    cuts = output_limit_cuts(steps or [])
    if cuts:
        turns = ", ".join("unrecorded" if c is None else f"{c:,}" for c in cuts)
        return (
            f"{AGY_OUTPUT_LIMIT_FAILURE} and had the model continue in another "
            f"turn; the answer it returned with status {status!r} opens with the "
            f"cut turn, so it is not one complete answer and is not used. Cut turn: "
            f"{turns} output tokens, thinking included; answer: {chars:,} "
            f"characters; agy's record: {record}. Envelope: {envelope}{tail}"
        )
    seen = (
        "agy's record could not be read" if steps is None
        else "agy's record shows no output-limit cut"
    )
    return (
        f"{AGY_STATUS_FAILURE}{status!r} (stdin path): the answer is not used, and "
        f"{seen}. Answer: {chars:,} characters; agy's record: {record}. "
        f"Envelope: {envelope}{tail}"
    )


def failed_status(
    status: object, reply: dict, stderr: str, record: str, steps: list[dict] | None,
) -> tuple[bool, str, str]:
    """The failed result of a call whose envelope status is not ``SUCCESS`` (#4543)."""
    return False, "", status_failure(status, reply, stderr, record, steps)


def status_failure_words(error_str: str) -> str:
    """The part of a status failure that is agy's own words (#4543).

    Its envelope's fields other than the id and the usage, and its stderr. The
    rest of that text is a conversation id, a path and token counts, and any of
    them can hold "429" or "503".
    """
    return error_str.partition(AGY_WORDS_LABEL)[2]


#: On Windows agy runs inside WSL, never as agy.exe (#3623). The Windows build
#: wraps its shell in PowerShell, where the fleet's shell guard cannot see it,
#: so the tool-less agent above would be the only thing between a pipeline
#: prompt and an unguarded shell. Under WSL the guard's hooks cover agy. A
#: discovered WSL agy is stored with this prefix, and every argv built from it
#: goes through wsl.exe.
#:
#: Residue, stated: when a call times out, ``kill_process_tree`` ends wsl.exe
#: and its Windows children. The Linux agy process normally ends with its relay,
#: but nothing here proves it did.
AGY_WSL_PREFIX = "wsl:"
_ON_WINDOWS = os.name == "nt"


def _find_linux_agy() -> Optional[str]:
    """agy on Linux: ``~/.local/bin/agy`` first, then PATH, never a Windows build (#4233).

    agy installs into ``~/.local/bin``, which a non-login shell and a process
    started with ``wsl.exe --exec`` do not have on PATH. A PATH answer under
    ``/mnt/`` is a Windows build reached through WSL interop, which runs outside
    the guard that governs the Linux agy, so it is never used.
    """
    local = Path.home() / ".local" / "bin" / "agy"
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    found = shutil.which("agy")
    if found and found.startswith("/mnt/"):
        # #3777: refused, and said so. "Not found" alone sent the operator
        # looking for an install that was there, in the wrong place.
        _loud(
            f"the only agy on PATH is {found}, a Windows build reached through "
            "WSL interop, which runs outside the shell guard; it is not used. "
            "Install agy in Ubuntu (~/.local/bin/agy)."
        )
        return None
    return found


@functools.lru_cache(maxsize=1)
def _find_wsl_agy() -> Optional[str]:
    """The Linux path of agy inside the default WSL distribution, or None.

    ``wsl.exe --exec`` starts a program with no shell, so no profile runs and
    ``~/.local/bin`` (agy's install location) is usually not on PATH. Two
    lookups, both argv-only: ``which agy``, then ``$HOME/.local/bin/agy`` if
    it is executable. Cached: every GeminiClient asks, and each lookup starts
    a WSL process.
    """
    wsl = shutil.which("wsl.exe") or shutil.which("wsl")
    if not wsl:
        return None

    def run(*argv: str) -> subprocess.CompletedProcess:
        # #3777: a wsl.exe that cannot run raises. It used to be None, read as
        # "agy not found", and the lru_cache kept that answer for the life of
        # the process; an exception is not cached, so the next ask tries again.
        try:
            return subprocess.run(
                [wsl, "--exec", *argv], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(
                f"could not run `{wsl} --exec {' '.join(argv)}` to find agy in WSL: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    found = run("which", "agy")
    if found.returncode == 0 and found.stdout.strip().startswith("/"):
        return found.stdout.strip().splitlines()[0]
    home = run("printenv", "HOME")
    if not (home.returncode == 0 and home.stdout.strip().startswith("/")):
        _loud(
            f"WSL's HOME could not be read (exit {home.returncode}: "
            f"{(home.stderr or home.stdout).strip()[:200]!r}), so ~/.local/bin/agy "
            "was not looked for; agy is reported not found"
        )
        return None
    candidate = home.stdout.strip() + "/.local/bin/agy"
    probe = run("test", "-x", candidate)
    if probe.returncode == 0:
        return candidate
    return None


@functools.lru_cache(maxsize=1)
def _wsl_home() -> str:
    """HOME inside the default WSL distribution, where a WSL agy finds its hooks (#4531).

    Raises when it cannot be read: a call that cannot name the guard's hooks
    file does not run, because agy would run it without them and say nothing.
    """
    wsl = shutil.which("wsl.exe") or shutil.which("wsl")
    if not wsl:
        raise RuntimeError("wsl.exe not found, so WSL's HOME cannot be read")
    try:
        got = subprocess.run(
            [wsl, "--exec", "printenv", "HOME"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            f"could not run `{wsl} --exec printenv HOME`: {type(exc).__name__}: {exc}"
        ) from exc
    home = got.stdout.strip()
    if got.returncode != 0 or not home.startswith("/"):
        raise RuntimeError(
            f"WSL's HOME could not be read (exit {got.returncode}: "
            f"{(got.stderr or got.stdout).strip()[:200]!r})"
        )
    return home

#: Named in every failure this module hands back to a caller (#2476).
#:
#: Three surfaces here all say "gemini" and none of them mean the CLI retired on
#: 2026-06-18: the module name, ``provider="gemini"`` in capacity.py and
#: errors.py, and the ``gemini:3.1-pro`` provider spec, which is genuinely
#: ``provider:model`` format. Each is defensible alone -- the MODEL is Gemini --
#: and together, inside an error message, they read as the tool the fleet rules
#: say never to invoke. A real `gemini` binary was still on PATH on the
#: workstation when the misreading below happened (2026-08-16); it is no longer
#: installed on Windows or WSL, but the label stays for the reason above.
#:
#: On 2026-08-16 that cost a real diagnosis: ``analysis unavailable on
#: gemini:3.1-pro (All credentials failed: ...)`` was read as "we regressed to
#: the banned client", and disproving it took reading `_find_agy_cli`, the
#: provider-spec format and the model-id table. "The vendor's capacity is
#: overloaded" and "we regressed to a retired client" call for completely
#: different next actions.
#:
#: Naming the transport in the failure text is the cheap fix, and it lands
#: exactly where the harm happens -- at failure time, when something else has
#: already gone wrong and attention is short. The module and provider names are
#: left alone: renaming them is a wider change for no extra safety, since
#: the model really is a Gemini model.
TRANSPORT_LABEL = "agy (Antigravity CLI)"

#: The same fact in log-line form, for the ``[LLM] ...`` diagnostics this module
#: prints while a call is going wrong. One constant rather than seven literals,
#: so the transport cannot fall off one line and leave that line ambiguous
#: again. ``transport=`` is a separate key from ``provider=`` on purpose: the
#: provider really is Gemini, and the pair says so without either word standing
#: alone long enough to be misread.
PROVIDER_LOG_ID = "provider=gemini transport=agy"


def roster_phrase(names: list[str]) -> str:
    """Name the credential when there is one; COUNT them when there are more.

    "All credentials failed" was written for the rotation design -- several
    credentials, rotate on failure, report the roster. Two things changed
    underneath it. #1605 removed API-key credentials, so `_load_credentials`
    appends only `type == "oauth"` entries; and the deployed roster holds
    exactly one, `oauth-primary`. The plural phrasing had a singular
    denominator, and "all" of one is a strange thing to tell an operator at
    the moment they are deciding whether their auth is broken (#2553).
    """
    if not names:
        return "no credentials"
    if len(names) == 1:
        return names[0]
    return f"all {len(names)} credentials"


def failure_headline(error_type: GeminiErrorType, names: list[str]) -> str:
    """Lead with the failure CLASS; the roster is a detail, not the news.

    During a live 503 storm on 2026-08-27 the surface read `ERROR=All
    credentials failed via agy (Antigravity CLI)`, and the operator's reading
    was the obvious one: something is wrong with our credentials. Nothing was.
    The credential connected on every attempt and the model had no capacity --
    a Google-side `MODEL_CAPACITY_EXHAUSTED`, widely reported that day. The
    per-credential detail line even said "riding 503/529 capacity storms", but
    the headline is what gets read first, and it named the wrong class.

    This module has form here: two prior incidents are recorded above, one
    where the same phrase was read as a regression and one where it was
    printed while preflight showed 4/4 healthy.

    **The classification is unchanged and deliberately so.** `error_type` is
    computed by the caller from the per-credential errors; this only renders
    it. `halt_node.classify_error` keys on `CAPACITY_MESSAGE_MARKERS`
    (`"capacity exhausted"`, `"503"`, `"529"`, `"overloaded"`) and on specific
    auth phrases -- never on the old headline -- so the wording below is
    chosen to keep the capacity and quota markers present and to contain no
    auth phrase. `test_failure_headline.py` pins that, and pins that the
    #2474 no-verdict retry path still sees what it saw.
    """
    who = roster_phrase(names)
    if error_type == GeminiErrorType.CAPACITY_EXHAUSTED:
        return (
            f"Provider capacity exhausted (503/529) via {TRANSPORT_LABEL} -- "
            f"an outage at the model, not a credential problem. Tried {who}:"
        )
    if error_type == GeminiErrorType.QUOTA_EXHAUSTED:
        return (
            f"Quota exhausted via {TRANSPORT_LABEL} -- the subscription's "
            f"allowance is spent, not a credential problem. Tried {who}:"
        )
    return f"Call failed via {TRANSPORT_LABEL}. Tried {who}:"

# #1872: Windows process-creation failures. A child that dies with one of
# these never got to run — desktop-heap / DLL-init pressure on a busy
# machine, not a credential problem. Twice in 30 minutes on 2026-07-28 these
# were reported as "All credentials failed" while preflight showed 4/4
# healthy seconds later.
SPAWN_FAILURE_EXIT_CODES = (
    3221225794,  # 0xC0000142 STATUS_DLL_INIT_FAILED
    3221225781,  # 0xC0000135 STATUS_DLL_NOT_FOUND
    3221225477,  # 0xC0000005 access violation during process init
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class GeminiCallResult:
    """Result of a Gemini API call with full observability."""

    success: bool
    response: Optional[str]  # Parsed response text
    raw_response: Optional[str]  # Full API response
    error_type: Optional[GeminiErrorType]
    error_message: Optional[str]
    attempts: int  # Total attempts made
    duration_ms: int  # Total time including retries
    model_verified: str  # Actual model used (for audit)


# =============================================================================
# =============================================================================


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[=>]")


def _append_json_schema_directive(system_instruction: str, schema: dict) -> str:
    """Ask, in words, for the JSON the caller's schema describes (#1843).

    The agy CLI transport has no structured-output flag, so ``response_schema``
    was accepted by invoke() and then dropped on the floor. Callers that asked
    for JSON got whatever their prompt's markdown template produced; the
    structured parse failed at char 0 every single time and silently fell back
    to regex. Since the transport cannot carry a schema, the prompt does.
    """
    return (
        f"{system_instruction}\n\n"
        "## Response Format (MANDATORY)\n\n"
        "Respond with a SINGLE JSON object and nothing else. No prose before "
        "or after it, no markdown headings, no code fences. It must validate "
        "against this schema:\n\n"
        f"{json.dumps(schema, indent=2)}\n"
    )


def _is_spawn_failure(error_text: str) -> bool:
    """True when an error string carries a Windows process-creation code.

    Issue #1872: these mean the child never started. That is transient
    machine pressure and deserves a backoff, not a credential write-off.
    (#1906's "spawn timed out" left with the PTY spawner that raised it, #3624.)
    """
    return any(str(code) in error_text for code in SPAWN_FAILURE_EXIT_CODES)


def _strip_ansi(text: str) -> str:
    """Strip ANSI/VT control sequences from agy's output and normalize
    newlines, so color codes and CR/LF never reach the response parser."""
    return _ANSI_RE.sub("", text).replace("\r\n", "\n").replace("\r", "")


def _agy_json_reply(text: str) -> Optional[dict]:
    """agy's ``--output-format json`` reply, or None when ``text`` is not one (#4199).

    The reply is one object carrying ``status``, and ``response`` and
    ``usage`` with it. Text that does not open with ``{`` is agy's plain
    output, read on the plain-text path as before. Text that opens like JSON
    and does not parse is a broken reply, and raises. A parsed object that is
    not agy's envelope, such as a model answer that happens to be JSON, is
    plain text too.
    """
    if not text.startswith("{"):
        return None
    try:
        reply = json.loads(text)
    except ValueError as exc:
        raise RuntimeError(
            f"agy printed output that opens like JSON and does not parse: {text[:200]!r}"
        ) from exc
    if isinstance(reply, dict) and "status" in reply and "response" in reply:
        return reply
    return None


#: Where one call's stdout goes, inside its temporary directory (#4509).
AGY_REPLY_FILENAME = "agy-reply.out"

#: How often the watcher looks, and how long a finished-looking reply has to sit
#: unchanged before the call stops waiting for agy to exit (#4509).
#:
#: The settle is longer than agy's own exit (#4510). Measured 2026-11-02 on 30
#: real calls, prompts of 2,000 to 110,000 characters and replies up to a
#: 9,280-token module: every agy exited by itself, 0.5 to 2.8 s after its
#: answer, and 7 took 2.0 s or more. In that time agy logs "Waiting for
#: migrations to complete to prevent partial migration state" and finishes
#: reconciling its summary store. A 2 s settle ended those 7 mid-shutdown and
#: warned about each as a hang. Ten seconds lets a normal exit happen and still
#: ends a real hang long before the 300 s timeout.
AGY_ANSWER_POLL_SECONDS = 0.25
AGY_ANSWER_SETTLE_SECONDS = 10.0


class _AnswerWatcher(threading.Thread):
    """Ends an agy that has printed its whole answer and not exited (#4509).

    Measured 2026-11-01 on a 108,943-character prompt: the full reply reached
    stdout at 20.5 s, and at 120 s agy was alive with nothing else in its
    session. `communicate` returns at EOF, so the transport sat out its 300 s,
    threw the answer away and called it a capacity failure, twice, which is the
    call's whole budget. Why agy stays alive is not known; waiting for it is
    what this removes.

    This decides only when to stop waiting. It reads `{...}` that has stopped
    changing as finished, and `_agy_json_reply` still judges what was printed,
    so a reply that does not parse raises and a bad status fails the call.
    Output that is not `{...}` never ends a call: a warning line, plain text, or
    a reply still arriving waits for the exit or the timeout as before.
    """

    def __init__(self, proc: subprocess.Popen, reply_path: Path) -> None:
        super().__init__(daemon=True, name="agy-answer-watcher")
        self._proc = proc
        self._reply_path = reply_path
        self._stop_watching = threading.Event()
        #: True once this ended agy because its answer had arrived.
        self.answered = False

    def stop(self) -> None:
        self._stop_watching.set()
        self.join(timeout=5)

    def _looks_finished(self) -> bool:
        text = _strip_ansi(
            self._reply_path.read_bytes().decode("utf-8", errors="replace")
        ).strip()
        return text.startswith("{") and text.endswith("}")

    def run(self) -> None:
        size = 0
        settled_at = time.monotonic()
        while not self._stop_watching.wait(AGY_ANSWER_POLL_SECONDS):
            if self._proc.poll() is not None:
                return
            current = self._reply_path.stat().st_size
            if current != size:
                size, settled_at = current, time.monotonic()
                continue
            waited = time.monotonic() - settled_at
            if size and waited >= AGY_ANSWER_SETTLE_SECONDS and self._looks_finished():
                logger.warning(
                    "[agy] pid %s printed its answer and has not exited after "
                    "%.0f s; ending it and using the answer (#4509)",
                    self._proc.pid, waited,
                )
                self.answered = True
                kill_process_tree(self._proc.pid)
                return


# =============================================================================
# Gemini Client
# =============================================================================


class GeminiClient:
    """
    Gemini API client with credential rotation and model enforcement.

    Ported from tools/gemini-rotate.py for programmatic use.
    """

    def __init__(
        self,
        model: str = REVIEWER_MODEL,
    ):
        """Initialize the client."""
        # Exact match, then family (#4178): "gemini-4-argon" refuses every
        # Argon id, the way seats.check_spec reads the list.
        lowered = model.lower()
        if any(entry.lower() in lowered for entry in FORBIDDEN_MODELS):
            raise ValueError(f"Model '{model}' is forbidden.")
            
        if not model.startswith("gemini-"):
            raise ValueError(
                f"Model '{model}' is not a valid Gemini model. "
            )
            
        self.model = model
        self._agy_cli = self._find_agy_cli()

    def _find_agy_cli(self) -> Optional[str]:
        """Find the Antigravity CLI (agy) executable.

        Replaces the retired Gemini CLI (#1335); agy is the subscription
        (OAuth) governance transport.

        On Windows this is agy inside WSL, never agy.exe (#3623): the Windows
        build's shell runs outside the fleet's shell guard. The result then
        carries ``AGY_WSL_PREFIX`` so every call knows to go through wsl.exe.
        """
        if _ON_WINDOWS:
            linux_path = _find_wsl_agy()
            return AGY_WSL_PREFIX + linux_path if linux_path else None
        return _find_linux_agy()

    def _agy_argv(self, cwd: str, *tail: str) -> list[str]:
        """The argv that runs agy with ``tail``, in ``cwd``.

        A WSL agy runs as ``wsl.exe --cd <cwd> --exec <agy> ...``: ``--cd``
        takes the Windows path of the temporary directory, and ``--exec``
        starts agy with no shell in between.
        """
        cli = self._agy_cli or ""
        if cli.startswith(AGY_WSL_PREFIX):
            return ["wsl.exe", "--cd", cwd, "--exec", cli[len(AGY_WSL_PREFIX):], *tail]
        return [cli, *tail]

    def _agy_hooks_file(self) -> str:
        """The machine's agy hooks file, as the agy this client runs reads it (#4531).

        A WSL agy reads it under WSL's HOME, not under the Windows home.
        """
        if (self._agy_cli or "").startswith(AGY_WSL_PREFIX):
            return agy_hooks_file(_wsl_home())
        return agy_hooks_file(Path.home().as_posix())

    def _agy_record(self, conversation_id: object) -> tuple[list[dict], str]:
        """agy's record of one conversation: (its steps, where it was read) (#4543).

        Read only for a call agy failed, to name the cause. A WSL agy keeps it
        under WSL's HOME, read through ``wsl.exe --exec cat``. A record that
        cannot be read raises ``AgyRecordUnreadable`` saying why; the caller
        fails the call with that reason.
        """
        if not conversation_id:
            raise AgyRecordUnreadable("the envelope names no conversation")
        wsl = (self._agy_cli or "").startswith(AGY_WSL_PREFIX)
        try:
            home = _wsl_home() if wsl else Path.home().as_posix()
            path = agy_transcript_file(home, str(conversation_id))
        except (ValueError, RuntimeError) as exc:
            raise AgyRecordUnreadable(
                f"no path for conversation {conversation_id!r}: {exc}"
            ) from exc
        try:
            if wsl:
                got = subprocess.run(
                    ["wsl.exe", "--exec", "cat", path], capture_output=True,
                    text=True, encoding="utf-8", errors="replace", timeout=30,
                    check=False,
                )
                text, code, said = got.stdout, got.returncode, got.stderr
            else:
                text, code, said = Path(path).read_text(encoding="utf-8", errors="replace"), 0, ""
            steps = transcript_steps(text)
        except (OSError, subprocess.TimeoutExpired, ValueError, TypeError) as exc:
            raise AgyRecordUnreadable(f"{path}: {type(exc).__name__}: {exc}") from exc
        if code != 0:
            raise AgyRecordUnreadable(f"{path}: cat exited {code}: {said.strip()[:200]}")
        return steps, path

    def _invoke_via_cli(
        self,
        system_instruction: str,
        content: str,
        timeout_seconds: float = AGY_CALL_TIMEOUT_SECONDS,
    ) -> tuple[bool, str, str]:
        """Invoke the governance model via the Antigravity CLI (agy).

        This is the subscription/OAuth transport (#1335), replacing the retired
        Gemini CLI. It composes the prompt (agy has no --system flag) and hands
        it to ``_invoke_via_stdin``, which runs agy in a clean temporary
        directory with the prompt on stdin.

        There used to be a second path here that put the prompt in argv and ran
        agy.exe under a Windows pseudo-console (pywinpty). After #3623 agy never
        runs as agy.exe, and off Windows pywinpty does not exist, so nothing
        reached it; #3624 removed it.

        Returns:
            Tuple of (success, response_text, error_message)
        """
        if not self._agy_cli:
            return False, "", "Antigravity CLI (agy) not found"

        full_prompt = (
            f"You are {self.model}.\n\n"
            f"<system_instruction>\n{system_instruction}\n</system_instruction>\n\n"
            f"<user_content>\n{content}\n</user_content>"
        )
        return self._invoke_via_stdin(full_prompt, timeout_seconds)

    def _invoke_via_stdin(
        self,
        full_prompt: str,
        timeout_seconds: float = AGY_CALL_TIMEOUT_SECONDS,
    ) -> tuple[bool, str, str]:
        """Invoke agy with the prompt on stdin (#1772); every call, since #3624.

        `agy --model X` with no ``-p`` reads the prompt from stdin and prints
        the response to a plain pipe, no TTY needed (verified 2026-07-14 with
        a 39,954-char prompt, and through WSL on 2026-09-25, #3623). The temp
        cwd keeps any repo's GEMINI.md / CLAUDE.md out of the call, and the
        #1765 error boundaries below keep a CLI banner from passing as model
        output.

        Every agy process this starts writes one line to the model-call
        ledger, success or failure (#4199); one that never started writes
        none, because no model was called.

        Returns:
            Tuple of (success, response_text, error_message)
        """
        started = time.monotonic()
        spent: dict = {}
        try:
            ok, text, error = self._agy_once(full_prompt, timeout_seconds, spent)
        except Exception as exc:
            self._ledger_line(spent, started, False, f"{type(exc).__name__}: {exc}")
            raise
        self._ledger_line(spent, started, ok, error)
        return ok, text, error

    def _ledger_line(self, spent: dict, started: float, ok: bool, error: str) -> None:
        """The model-call ledger line for one agy process, if it started (#4199)."""
        if not spent.get("ran"):
            return
        from assemblyzero.core import model_call_ledger

        outcome = "ok" if ok else ("timeout" if "timeout" in error.lower() else "failed")
        model_call_ledger.record(
            "assemblyzero.gemini_client", "agy", self.model, spent.get("usage"),
            time.monotonic() - started, outcome, None if ok else error,
        )

    def _agy_once(
        self, full_prompt: str, timeout_seconds: float, spent: dict
    ) -> tuple[bool, str, str]:
        """One agy process; fills ``spent`` for the ledger (see _invoke_via_stdin).

        agy is asked for JSON (#4199), the only form in which it reports the
        call's tokens: ``{"status", "response", "usage"}``. Output that is not
        that object is handled exactly as before, as plain text.
        """
        import tempfile

        # #4531: raises when it cannot be named; agy would run without the hooks.
        hooks_file = self._agy_hooks_file()
        try:
            # #1874: Popen, not subprocess.run. run()'s own timeout kills only
            # the root process on Windows and then drains the pipes with an
            # unbounded communicate() — agy's grandchildren hold those handles,
            # so the call hangs indefinitely instead of raising at the timeout.
            # ignore_cleanup_errors: a just-killed child can still hold the
            # temp cwd for a moment; that must not fail the call.
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_cwd:
                # #3612: the agent this call runs as lives in this directory.
                write_text_only_agent(tmp_cwd, hooks_file)
                # #4509: stdout goes to a file, so `_AnswerWatcher` can see the
                # answer while `communicate` waits for the exit.
                reply_path = Path(tmp_cwd) / AGY_REPLY_FILENAME
                with reply_path.open("wb") as reply_sink:
                    proc = subprocess.Popen(
                        self._agy_argv(
                            tmp_cwd, "--agent", AGY_AGENT_NAME, *AGY_SAFETY_ARGS,
                            "--model", self.model, "--output-format", "json",
                        ),
                        stdin=subprocess.PIPE,
                        stdout=reply_sink,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        cwd=tmp_cwd,
                        # #4195: off Windows, kill_process_tree signals the
                        # process GROUP. In the caller's group, a timeout killed
                        # the caller and every sibling with SIGKILL; in a
                        # session of its own, the group is agy and its
                        # descendants only.
                        start_new_session=os.name != "nt",
                    )
                spent["ran"] = True
                watcher = _AnswerWatcher(proc, reply_path)
                watcher.start()
                try:
                    stdout, stderr = proc.communicate(
                        input=full_prompt, timeout=timeout_seconds
                    )
                except subprocess.TimeoutExpired:
                    kill_process_tree(proc.pid)
                    try:
                        proc.communicate(timeout=10)
                    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
                        # #3777: the timeout is the answer; a killed process
                        # that will not drain is its own failure, said aloud.
                        _loud(
                            f"agy (pid {proc.pid}) did not exit 10 s after it was "
                            f"killed for timing out: {type(exc).__name__}: {exc}"
                        )
                    return False, "", (
                        f"agy CLI timeout ({timeout_seconds:.0f}s, stdin path)"
                    )
                finally:
                    watcher.stop()
                # #4509: the exit status of a process this call ended says
                # nothing about the call; the reply's own status decides.
                returncode = 0 if watcher.answered else proc.returncode
                if stdout is None:
                    stdout = reply_path.read_bytes().decode("utf-8", errors="replace")
        except OSError as e:
            return False, "", f"agy stdin invocation failed: {e}"

        text = _strip_ansi(stdout or "").strip()
        reply = _agy_json_reply(text)
        if reply is not None and isinstance(reply.get("usage"), dict):
            spent["usage"] = reply["usage"]
        if reply is not None and reply.get("conversation_id"):
            # #4531: names agy's own transcript of the call, under its brain/.
            spent["conversation_id"] = str(reply["conversation_id"])

        # #3612: an agent agy could not load means the default agent, with its
        # tools, answered. That is a failed call, whatever the exit status.
        # Both streams are read (#3624): the removed PTY path saw them merged,
        # and nothing proves agy writes the warning to stderr only. #4538: of
        # stdout, only what agy wrote; the model's answer is not a diagnostic.
        warned = agent_warning(agy_diagnostics(stderr or "", text, reply))
        if warned:
            return False, "", f"agy did not run as {AGY_AGENT_NAME}: {warned[:400]}"

        # #1765: never hand a CLI error banner to callers as model output.
        if returncode != 0:
            detail = (stderr or "").strip() or text
            return False, "", (
                f"agy exited {returncode} (stdin path): {detail[:400]}"
            )
        if reply is not None:
            # #4199: agy's own verdict on the call. A status other than
            # SUCCESS is a failed call, whatever text came with it. #4543: the
            # failure says why, from agy's own record of the conversation, and
            # carries none of the answer (see status_failure).
            status = reply.get("status")
            if status != "SUCCESS":
                try:
                    steps, record = self._agy_record(reply.get("conversation_id"))
                except AgyRecordUnreadable as exc:
                    # The call has failed either way; the failure says the
                    # record could not be read, and why, instead of a cause.
                    return failed_status(status, reply, stderr or "", str(exc), None)
                return failed_status(status, reply, stderr or "", record, steps)
            text = _strip_ansi(str(reply.get("response") or "")).strip()
            if text:
                return True, text, ""
            return False, "", "agy returned no output (stdin path)"
        first_line = text.splitlines()[0].strip() if text else ""
        if first_line.startswith("Error:"):
            return False, "", f"agy error output (stdin path): {text[:400]}"

        if text:
            return True, text, ""
        return False, "", "agy returned no output (stdin path)"

    def invoke(
        self,
        system_instruction: str,
        content: str,
        response_schema: Optional[dict] = None,
    ) -> GeminiCallResult:
        """Invoke Gemini via agy with automatic retry."""
        start_time = time.time()
        total_attempts = 0

        # Issue #1843: JSON structured output via string instruction
        if response_schema:
            system_instruction = _append_json_schema_directive(
                system_instruction, response_schema
            )

        errors: list[str] = []
        budget_exhausted = False
        last_error_type: GeminiErrorType | None = None

        if not self._agy_cli:
            # #3777: a missing agy fails at once. It was a failed attempt the
            # loop retried with backoff until the call budget ran out, and no
            # wait installs a CLI.
            message = (
                f"{TRANSPORT_LABEL} not found: no agy for this machine "
                "(Ubuntu: ~/.local/bin/agy; Windows: agy inside WSL)"
            )
            _loud(f"model {self.model}: {message}")
            return GeminiCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_type=GeminiErrorType.UNKNOWN,
                error_message=message,
                attempts=0,
                duration_ms=int((time.time() - start_time) * 1000),
                model_verified="",
            )

        for attempt in range(1, MAX_RETRIES_PER_CREDENTIAL + 1):
            remaining = self._remaining_budget(start_time)
            if remaining < MIN_ATTEMPT_SECONDS:
                budget_exhausted = True
                flavor = f" (last error class: {last_error_type.name.lower()})" if last_error_type else ""
                errors.append(f"call budget of {MAX_TOTAL_INVOKE_SECONDS:.0f}s exhausted{flavor}")
                break

            total_attempts += 1

            # #3777: no handler around the call. `_invoke_via_cli` reports
            # every transport failure as (False, "", reason); the old loop
            # raised that reason only to catch it with `except Exception`,
            # which also caught programming errors and handed them back as a
            # failed call. Now an exception here is a fault and propagates.
            success, response_text, error_str = self._invoke_via_cli(
                system_instruction,
                content,
                timeout_seconds=min(AGY_CALL_TIMEOUT_SECONDS, remaining),
            )
            if success:
                duration_ms = int((time.time() - start_time) * 1000)
                return GeminiCallResult(
                    success=True,
                    response=strip_emoji(response_text),
                    raw_response=response_text,
                    error_type=None,
                    error_message=None,
                    attempts=total_attempts,
                    duration_ms=duration_ms,
                    model_verified=self.model,
                )

            if error_str.startswith(AGY_OUTPUT_LIMIT_FAILURE):
                # #4543: named from agy's own record, never matched for words.
                # Retried like any failed attempt: the cut depends on how long
                # the model thinks, and on 2026-11-02 the same prompt, sent a
                # third time, was answered at 60,043 output tokens.
                error_type = GeminiErrorType.OUTPUT_LIMIT
            else:
                # #4543: of a status failure, only agy's stderr is words; its
                # ids, path and token counts can hold "429" or "503".
                words = (
                    status_failure_words(error_str)
                    if error_str.startswith(AGY_STATUS_FAILURE) else error_str
                )
                classified = classify_agy_error(RuntimeError(words))
                error_type = self._error_type_from_classified(classified)

            if error_type == GeminiErrorType.UNKNOWN and "timed out" in error_str.lower():
                error_type = GeminiErrorType.CAPACITY_EXHAUSTED

            # #3777: every failed attempt is loud with its cause, retried or not.
            _loud(
                f"model {self.model}: attempt {total_attempts} failed "
                f"({error_type.name}): {error_str[:400]}"
            )

            if "did not run as" in error_str:
                return GeminiCallResult(
                    success=False,
                    response=None,
                    raw_response=None,
                    error_type=GeminiErrorType.UNKNOWN,
                    error_message=error_str,
                    attempts=total_attempts,
                    duration_ms=int((time.time() - start_time) * 1000),
                    model_verified="",
                )

            last_error_type = error_type

            if error_type in (GeminiErrorType.AUTH_ERROR, GeminiErrorType.MODEL_MISMATCH):
                return GeminiCallResult(
                    success=False,
                    response=None,
                    raw_response=None,
                    error_type=error_type,
                    error_message=error_str,
                    attempts=total_attempts,
                    duration_ms=int((time.time() - start_time) * 1000),
                    model_verified="",
                )

            if error_type == GeminiErrorType.QUOTA_EXHAUSTED:
                return GeminiCallResult(
                    success=False,
                    response=None,
                    raw_response=None,
                    error_type=error_type,
                    error_message=f"Quota exhausted via {TRANSPORT_LABEL}. Wait for quota reset.",
                    attempts=total_attempts,
                    duration_ms=int((time.time() - start_time) * 1000),
                    model_verified="",
                )

            delay = self._backoff_delay(total_attempts)
            errors.append(f"Attempt {total_attempts} failed ({error_type.name}): {error_str[:100]}")

            remaining_after = self._remaining_budget(start_time)
            if remaining_after < MIN_ATTEMPT_SECONDS:
                budget_exhausted = True
                break

            if delay > 0:
                # #3777: the retry is said, with its wait.
                logger.warning(
                    "[agy] model %s: retrying attempt %d in %.0fs",
                    self.model, total_attempts + 1, delay,
                )
                time.sleep(delay)

        # #3777: the call failed for good; say so with every attempt's cause.
        _loud(
            f"model {self.model}: the call failed after {total_attempts} attempt(s): "
            f"{'; '.join(errors)}"
        )
        return GeminiCallResult(
            success=False,
            response=None,
            raw_response=None,
            # #4543: a call whose last attempt agy cut at its output limit says
            # so in its type too, budget or no budget.
            error_type=(
                last_error_type
                if budget_exhausted or last_error_type == GeminiErrorType.OUTPUT_LIMIT
                else GeminiErrorType.UNKNOWN
            ),
            error_message="; ".join(errors),
            attempts=total_attempts,
            duration_ms=int((time.time() - start_time) * 1000),
            model_verified="",
        )

    @staticmethod
    def _error_type_from_classified(classified) -> GeminiErrorType:
        """Derive GeminiErrorType from a typed errors.py exception.

        Issue #546: Bridge between the unified error hierarchy and the
        GeminiErrorType enum used by the rotation/retry logic.
        """
        if isinstance(classified, TypedRateLimitError):
            return GeminiErrorType.QUOTA_EXHAUSTED
        if isinstance(classified, TypedCapacityError):
            return GeminiErrorType.CAPACITY_EXHAUSTED
        if isinstance(classified, TypedAuthError):
            return GeminiErrorType.AUTH_ERROR
        if isinstance(classified, TypedTimeoutError):
            return GeminiErrorType.CAPACITY_EXHAUSTED  # Treat timeout as capacity for retry
        return GeminiErrorType.UNKNOWN

    def _backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        return min(BACKOFF_BASE_SECONDS * (2**attempt), BACKOFF_MAX_SECONDS)

    @staticmethod
    def _remaining_budget(start_time: float) -> float:
        """Seconds left in this invoke()'s wall-clock budget (#1874)."""
        return MAX_TOTAL_INVOKE_SECONDS - (time.time() - start_time)

    def _parse_reset_time(self, error_output: str) -> Optional[float]:
        """Parse quota reset time from error message (returns hours)."""
        import re

        # Pattern: "Your quota will reset after 15h11m58s"
        match = re.search(r"reset after (\d+)h(\d+)m", error_output)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            return hours + minutes / 60
        return None




def _parse_usage_from_gemini_response(response_dict: dict) -> LLMOutputMetadata:
    """Extract usageMetadata from Gemini response dict.

    Issue #774: Parse token counts from Gemini GenerateContentResponse.
    Cost estimation for Gemini is deferred (returns 0.0 via cost.py unknown model path).

    #3777: a response that does not name its model raises. It was recorded as
    "gemini-unknown", which a model record cannot tell from a real model id.
    """
    usage = response_dict.get("usageMetadata", {})
    model_version = response_dict.get("modelVersion")
    if not model_version:
        raise ValueError(
            "the Gemini response names no modelVersion, so the model that "
            f"answered is unknown; keys present: {sorted(response_dict)}"
        )

    return LLMOutputMetadata(
        model_used=model_version,
        input_tokens=usage.get("promptTokenCount"),
        output_tokens=usage.get("candidatesTokenCount"),
        stop_reason="end_turn",
    )
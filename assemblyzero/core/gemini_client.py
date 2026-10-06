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

from assemblyzero.utils.process import kill_process_tree
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

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
    classify_gemini_error,
)

from assemblyzero.telemetry.llm_call_record import LLMOutputMetadata


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
    UNKNOWN = "unknown"  # Other errors - Fail closed


# Pattern matching (from gemini-rotate.py)
QUOTA_EXHAUSTED_PATTERNS = [
    "TerminalQuotaError",
    "exhausted your capacity",
    "QUOTA_EXHAUSTED",
    "429",
    "Resource has been exhausted",
]

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
#: its command line. Nothing is read from the machine's agy settings and
#: nothing is deployed anywhere. Proved 2026-09-25: asked to run ``whoami`` and
#: write a file, the model answered "I cannot run commands, read or write
#: files, or reach the network because I have no tools available", in one
#: turn, with no prompt from agy or Windows, and the call's input fell from
#: 15,983 tokens to 2,766 because the tool schemas left the prompt.
AGY_AGENT_NAME = "assemblyzero-text"
AGY_AGENT_DEFINITION = """---
name: assemblyzero-text
description: AssemblyZero pipeline seat. Answers from the prompt text alone. No tools, no shell, no files, no network.
mainAgent: true
subagent: false
hidden: true
inheritMcp: false
tools: []
commandExecutionPolicy: "off"
---

You answer from the text you are given and nothing else. You have no tools: you cannot run commands, read or write files, or reach the network, and you never ask for any of them. If the prompt refers to files or attachments, their content is absent; say so in one sentence and answer from what is present.
"""


def write_text_only_agent(cwd: Path | str) -> Path:
    """Write the pipeline's agent definition into ``cwd`` and return its path.

    Called inside the temporary directory of every call, before the spawn, so
    ``--agent assemblyzero-text`` resolves to this file and to nothing else.
    """
    path = Path(cwd) / ".agents" / "agents" / AGY_AGENT_NAME / "agent.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(AGY_AGENT_DEFINITION, encoding="utf-8")
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
    """agy on Linux: ``~/.local/bin/agy`` first, then PATH, never a Windows build (#3651).

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

    def run(*argv: str) -> Optional[subprocess.CompletedProcess]:
        try:
            return subprocess.run(
                [wsl, "--exec", *argv], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            # fail-open: None becomes "agy not found", which the preflight and
            # every invoke report as a failed call; no answer is invented.
            return None

    found = run("which", "agy")
    if found and found.returncode == 0 and found.stdout.strip().startswith("/"):
        return found.stdout.strip().splitlines()[0]
    home = run("printenv", "HOME")
    if not (home and home.returncode == 0 and home.stdout.strip().startswith("/")):
        return None
    candidate = home.stdout.strip() + "/.local/bin/agy"
    probe = run("test", "-x", candidate)
    if probe and probe.returncode == 0:
        return candidate
    return None

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
#: `gemini-3.1-pro-high` really is the model's name.
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

CAPACITY_PATTERNS = [
    "MODEL_CAPACITY_EXHAUSTED",
    "RESOURCE_EXHAUSTED",
    "503",
    "529",
    "The model is overloaded",
]

AUTH_ERROR_PATTERNS = [
    "API_KEY_INVALID",
    "API key not valid",
    "PERMISSION_DENIED",
    "UNAUTHENTICATED",
    "401",
    "403",
]


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
        if model in FORBIDDEN_MODELS:
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

        Returns:
            Tuple of (success, response_text, error_message)
        """
        import tempfile

        try:
            # #1874: Popen, not subprocess.run. run()'s own timeout kills only
            # the root process on Windows and then drains the pipes with an
            # unbounded communicate() — agy's grandchildren hold those handles,
            # so the call hangs indefinitely instead of raising at the timeout.
            # ignore_cleanup_errors: a just-killed child can still hold the
            # temp cwd for a moment; that must not fail the call.
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_cwd:
                # #3612: the agent this call runs as lives in this directory.
                write_text_only_agent(tmp_cwd)
                proc = subprocess.Popen(
                    self._agy_argv(
                        tmp_cwd, "--agent", AGY_AGENT_NAME, *AGY_SAFETY_ARGS,
                        "--model", self.model,
                    ),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=tmp_cwd,
                )
                try:
                    stdout, stderr = proc.communicate(
                        input=full_prompt, timeout=timeout_seconds
                    )
                except subprocess.TimeoutExpired:
                    kill_process_tree(proc.pid)
                    try:
                        proc.communicate(timeout=10)
                    except (subprocess.TimeoutExpired, OSError, ValueError):
                        pass
                    return False, "", (
                        f"agy CLI timeout ({timeout_seconds:.0f}s, stdin path)"
                    )
                returncode = proc.returncode
        except OSError as e:
            return False, "", f"agy stdin invocation failed: {e}"

        text = _strip_ansi(stdout or "").strip()

        # #3612: an agent agy could not load means the default agent, with its
        # tools, answered. That is a failed call, whatever the exit status.
        # Both streams are read (#3624): the removed PTY path saw them merged,
        # and nothing proves agy writes the warning to stderr only.
        warned = agent_warning(f"{stderr or ''}\n{text}")
        if warned:
            return False, "", f"agy did not run as {AGY_AGENT_NAME}: {warned[:400]}"

        # #1765: never hand a CLI error banner to callers as model output.
        if returncode != 0:
            detail = (stderr or "").strip() or text
            return False, "", (
                f"agy exited {returncode} (stdin path): {detail[:400]}"
            )
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

        for attempt in range(1, MAX_RETRIES_PER_CREDENTIAL + 1):
            remaining = self._remaining_budget(start_time)
            if remaining < MIN_ATTEMPT_SECONDS:
                budget_exhausted = True
                flavor = f" (last error class: {last_error_type.name.lower()})" if last_error_type else ""
                errors.append(f"call budget of {MAX_TOTAL_INVOKE_SECONDS:.0f}s exhausted{flavor}")
                break

            total_attempts += 1

            try:
                success, response_text, error_msg = self._invoke_via_cli(
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
                else:
                    raise RuntimeError(error_msg)

            except Exception as e:
                error_str = str(e)

                if isinstance(e, (TypeError, AttributeError, NameError, ImportError)):
                    msg = f"{type(e).__name__}: {error_str}"
                    return GeminiCallResult(
                        success=False,
                        response=None,
                        raw_response=None,
                        error_type=GeminiErrorType.UNKNOWN,
                        error_message=f"Programming error (not retried): {msg}",
                        attempts=total_attempts,
                        duration_ms=int((time.time() - start_time) * 1000),
                        model_verified="",
                    )

                classified = classify_gemini_error(e)
                status_code = classified.status_code
                error_type = self._error_type_from_classified(classified)

                if error_type == GeminiErrorType.UNKNOWN and "timed out" in error_str.lower():
                    error_type = GeminiErrorType.CAPACITY_EXHAUSTED
                    last_error_type = error_type

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
                    time.sleep(delay)

        return GeminiCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_type=last_error_type if budget_exhausted else GeminiErrorType.UNKNOWN,
            error_message="; ".join(errors),
            attempts=total_attempts,
            duration_ms=int((time.time() - start_time) * 1000),
            model_verified="",
        )

    def _classify_error(self, error_output: str) -> GeminiErrorType:
        """Classify error type from API response string.

        Deprecated: Use classify_gemini_error() + _error_type_from_classified()
        for new code paths. Kept for backward compatibility.
        """
        error_lower = error_output.lower()

        # Check quota patterns first
        for pattern in QUOTA_EXHAUSTED_PATTERNS:
            if pattern.lower() in error_lower:
                return GeminiErrorType.QUOTA_EXHAUSTED

        # Check capacity patterns
        for pattern in CAPACITY_PATTERNS:
            if pattern.lower() in error_lower:
                return GeminiErrorType.CAPACITY_EXHAUSTED

        # Check auth patterns
        for pattern in AUTH_ERROR_PATTERNS:
            if pattern.lower() in error_lower:
                return GeminiErrorType.AUTH_ERROR

        return GeminiErrorType.UNKNOWN

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
    """
    usage = response_dict.get("usageMetadata", {})
    model_version = response_dict.get("modelVersion", "gemini-unknown")

    return LLMOutputMetadata(
        model_used=model_version,
        input_tokens=usage.get("promptTokenCount"),
        output_tokens=usage.get("candidatesTokenCount"),
        stop_reason="end_turn",
    )
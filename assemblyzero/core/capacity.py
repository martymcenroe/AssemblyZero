"""Cross-provider capacity state — know before you spend (Issue #1883).

A pipeline run needs both providers: Gemini designs and reviews, Claude
implements. Starting a run when either is exhausted guarantees a partial run
that spends the healthy provider's quota to discover the dry one.

Gemini already had half of this. Its rotation state records which credentials
are exhausted and when they reset, and ``preflight.check_gemini_available()``
reads that file with zero API calls — its docstring even states the intent:
"Checks Gemini availability before a run starts." Claude
had none of it: usage limits were detected at call time (``errors.py`` matches
"usage limit" / "wait until") and then discarded.

The ``claude`` CLI exposes no usage or quota subcommand, and the numbers in
Claude Code's ``/usage`` belong to the harness, not to anything a pipeline can
read. So the Claude side cannot poll — it learns from a failure and remembers
it, exactly the way the Gemini side already works.

#3773 (ADR 0236): the gate never reads a failure as "available". A state file
that exists and cannot be read, or holds a record that cannot be understood,
raises ``CapacityStateError`` naming the file; so does a write that fails,
which used to leave the next run starting blind. Gemini's quota is held by
agy and not recorded here, so its status says "not checked" rather than
"available"; an unknown provider raises.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from assemblyzero.core.config import CAPACITY_STATE_FILE

# A recorded exhaustion whose reset time could not be parsed still has to
# expire on its own — a block that never lifts would wedge the pipeline
# harder than the quota did. Claude's subscription windows are hours long,
# so an hour is a conservative retry point, not a guess at the real reset.
UNKNOWN_RESET_COOLDOWN = timedelta(hours=1)

#: The providers this module knows. Only Claude's state is recorded here.
KNOWN_PROVIDERS = ("claude", "gemini")

#: Why Gemini is not checked here, and what checks it instead.
GEMINI_UNCHECKED = (
    "agy holds Gemini's quota and nothing records it on this machine; the "
    "transport preflight checks Gemini with a real call before the first "
    "draft of every workflow that uses it (#3506)"
)


class CapacityStateError(RuntimeError):
    """The capacity state file cannot be read, understood or written (#3773).

    Deliberately not an ``OSError``: ``ClaudeCLIProvider.invoke`` turns an
    ``OSError`` into a failed call saying the CLI could not be run, and a
    broken state file is not that.
    """


@dataclass
class ProviderCapacity:
    """One provider's known capacity state.

    ``checked`` is False for a provider this module does not track (Gemini).
    Such a status is not ``available``: nothing here knows that it is.
    """

    provider: str
    available: bool
    resets_at: Optional[datetime] = None
    exhausted_at: Optional[datetime] = None
    detail: str = ""
    checked: bool = True

    def wait_summary(self, now: Optional[datetime] = None) -> str:
        """Human phrasing of the wait, for an operator staring at a console."""
        if not self.checked:
            return f"{self.provider}: not checked here ({self.detail})"
        if self.available:
            return f"{self.provider}: available"
        if not self.resets_at:
            return f"{self.provider}: exhausted ({self.detail or 'reset time unknown'})"
        now = now or datetime.now(timezone.utc)
        minutes = max(0, int((self.resets_at - now).total_seconds() // 60))
        local = self.resets_at.astimezone()
        # Formatted by hand: %-I is glibc-only and %#I is Windows-only, so
        # either one crashes on the other platform (the #1841 lesson).
        hour = local.hour % 12 or 12
        meridiem = "AM" if local.hour < 12 else "PM"
        return (
            f"{self.provider}: exhausted until "
            f"{hour}:{local.minute:02d} {meridiem} ({minutes} min)"
        )


def _load_state(state_file: Optional[Path] = None) -> dict:
    """The recorded state, or ``{}`` when no file was ever written.

    Absence is an answer: nothing has been recorded. A file that exists and
    cannot be read, or that is not a JSON object, raises (#3773). It used to
    read as "nothing recorded", so a recorded exhaustion was ignored and the
    run started anyway, spending the healthy provider's quota to find out.
    """
    path = state_file or CAPACITY_STATE_FILE
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        raise CapacityStateError(
            f"cannot read the capacity state {path}: {type(exc).__name__}: {exc}; "
            f"fix it, or remove it to forget every recorded exhaustion"
        ) from exc
    if not isinstance(data, dict):
        raise CapacityStateError(
            f"the capacity state {path} is not a JSON object (it holds "
            f"{type(data).__name__}); fix it, or remove it to forget every "
            f"recorded exhaustion"
        )
    return data


def _save_state(state: dict, state_file: Optional[Path] = None) -> None:
    """Write the state atomically, or raise naming the file (#3773).

    A failed write used to pass: an exhaustion was then never remembered, and
    the next run started blind, which is the waste this module exists to stop.
    """
    path = state_file or CAPACITY_STATE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        tmp.replace(path)
    except OSError as exc:
        raise CapacityStateError(
            f"cannot write the capacity state {path}: {type(exc).__name__}: {exc}"
        ) from exc


def parse_reset_time(message: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Best-effort reset timestamp from a provider's usage-limit message.

    The exact wording of Claude's limit message has never been captured in
    this repo, so this reads the shapes that have been observed in the wild
    and returns None rather than guessing. Callers persist the raw message
    either way, so a future sample can sharpen this without losing history.

    Handles: a trailing unix timestamp (``...limit reached|1751904000``), an
    explicit ISO timestamp, ``reset(s) at 5pm`` / ``at 15:00``, and
    ``in 3h20m`` / ``in 45 minutes``.
    """
    if not message:
        return None
    now = now or datetime.now(timezone.utc)

    unix = re.search(r"\|\s*(\d{10})\b", message)
    if unix:
        try:
            return datetime.fromtimestamp(int(unix.group(1)), tz=timezone.utc)
        except (ValueError, OSError):
            pass

    iso = re.search(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)", message)
    if iso:
        try:
            parsed = datetime.fromisoformat(iso.group(1).replace(" ", "T"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    relative = re.search(r"in\s+(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)", message, re.IGNORECASE)
    if relative and (relative.group(1) or relative.group(2)):
        hours = int(relative.group(1) or 0)
        minutes = int(relative.group(2) or 0)
        return now + timedelta(hours=hours, minutes=minutes)

    minutes_only = re.search(r"in\s+(\d+)\s*minutes?", message, re.IGNORECASE)
    if minutes_only:
        return now + timedelta(minutes=int(minutes_only.group(1)))

    clock = re.search(
        r"reset[s]?\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", message, re.IGNORECASE
    )
    if clock:
        hour = int(clock.group(1))
        minute = int(clock.group(2) or 0)
        meridiem = (clock.group(3) or "").lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23:
            local_now = now.astimezone()
            candidate = local_now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if candidate <= local_now:
                candidate += timedelta(days=1)
            return candidate.astimezone(timezone.utc)

    return None


def record_exhaustion(
    provider: str,
    message: str,
    state_file: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> ProviderCapacity:
    """Remember that a provider reported exhaustion, and when it recovers.

    Called from the failure path that already detects the condition. The raw
    message is stored verbatim so an unparseable format can be diagnosed —
    and a parser written for it — from real evidence rather than memory.
    """
    now = now or datetime.now(timezone.utc)
    resets_at = parse_reset_time(message, now=now)

    state = _load_state(state_file)
    state[provider] = {
        "exhausted_at": now.isoformat(),
        "resets_at": resets_at.isoformat() if resets_at else None,
        "source_message": (message or "")[:500],
    }
    _save_state(state, state_file)

    return ProviderCapacity(
        provider=provider,
        available=False,
        resets_at=resets_at,
        exhausted_at=now,
        detail=(message or "")[:200],
    )


def clear_exhaustion(provider: str, state_file: Optional[Path] = None) -> None:
    """Forget a recorded exhaustion — a provider that just answered is fine."""
    state = _load_state(state_file)
    if provider in state:
        del state[provider]
        _save_state(state, state_file)


def _claude_capacity(
    state_file: Optional[Path] = None, now: Optional[datetime] = None
) -> ProviderCapacity:
    now = now or datetime.now(timezone.utc)
    path = state_file or CAPACITY_STATE_FILE
    entry = _load_state(state_file).get("claude")
    if not entry:
        return ProviderCapacity(provider="claude", available=True)

    def _dt(key: str) -> Optional[datetime]:
        """The stored time, or None when the record holds none.

        ``resets_at`` is stored as null when the provider's message named no
        reset time; that is a record, not a failure. A value that is there
        and is not an ISO time raises (#3773): it used to read as absent,
        and a record with neither time read as "available".
        """
        raw = entry.get(key)
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw)
        except (ValueError, TypeError) as exc:
            raise CapacityStateError(
                f"the claude record in {path} has {key}={raw!r}, which is not "
                f"an ISO time: {type(exc).__name__}: {exc}"
            ) from exc
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    exhausted_at = _dt("exhausted_at")
    resets_at = _dt("resets_at")

    # No parsed reset time: expire the record on its own so a stale entry
    # can never wedge the pipeline permanently.
    effective_reset = resets_at or (
        (exhausted_at + UNKNOWN_RESET_COOLDOWN) if exhausted_at else None
    )
    if effective_reset is None:
        # #3773: record_exhaustion always writes exhausted_at, so a record
        # with neither time was not written by it; it used to read as
        # "available".
        raise CapacityStateError(
            f"the claude record in {path} has no exhaustion time and no reset "
            f"time, so when it lifts cannot be told: {entry!r}"
        )
    if now >= effective_reset:
        return ProviderCapacity(provider="claude", available=True)

    return ProviderCapacity(
        provider="claude",
        available=False,
        resets_at=effective_reset,
        exhausted_at=exhausted_at,
        detail=entry.get("source_message", "")[:200],
    )


def _gemini_capacity(now: Optional[datetime] = None) -> ProviderCapacity:
    """Gemini's state is not tracked locally (handled by agy).

    #3773: so it is reported as not checked, never as available. Nothing on
    this machine knows Gemini's quota; the transport preflight finds out with
    a real call, and halts the workflow when the call fails.
    """
    return ProviderCapacity(
        provider="gemini", available=False, checked=False, detail=GEMINI_UNCHECKED,
    )


def check_capacity(
    providers: Optional[list[str]] = None,
    state_file: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict[str, ProviderCapacity]:
    """Read-only capacity status for each provider. Zero API calls.

    Args:
        providers: Provider names to check. Defaults to both.
        state_file: Override for the capacity state file (tests).
        now: Override for the clock (tests).

    Returns:
        Mapping of provider name to its ProviderCapacity. Gemini's is not
        checked (``checked=False``).

    Raises:
        ValueError: a provider this module does not know (#3773); it used to
            be reported as available.
        CapacityStateError: the state file cannot be read or understood.
    """
    names = providers or list(KNOWN_PROVIDERS)
    unknown = [name for name in names if name not in KNOWN_PROVIDERS]
    if unknown:
        raise ValueError(
            f"no capacity check for provider(s) {', '.join(map(repr, unknown))}; "
            f"known: {', '.join(KNOWN_PROVIDERS)}"
        )
    now = now or datetime.now(timezone.utc)
    statuses: dict[str, ProviderCapacity] = {}
    for name in names:
        if name == "claude":
            statuses[name] = _claude_capacity(state_file=state_file, now=now)
        else:
            statuses[name] = _gemini_capacity(now=now)
    return statuses


def blocked_providers(
    providers: Optional[list[str]] = None,
    state_file: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> list[ProviderCapacity]:
    """Just the providers known to be exhausted right now.

    A provider that is not checked here is not in the list: nothing here
    knows it is exhausted, and it is not called available either. Gemini is
    the one such provider, and the transport preflight checks it (#3773).
    """
    return [
        status
        for status in check_capacity(providers, state_file=state_file, now=now).values()
        if status.checked and not status.available
    ]

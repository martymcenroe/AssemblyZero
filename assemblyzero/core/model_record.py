"""Which model answered every call of a run (#3565, under #3562).

A comparison between profiles is a guess unless each call can be attributed
to a seat, a spec, and the model that actually answered. ``calls.jsonl``
(#2731) held the prompt and response bodies, but only where an audit
directory was armed, and it recorded the alias (``3.1-pro``) and the
primary of a ``FallbackProvider`` even when the fallback answered.

This module is the metadata half, armed for every run that has a record open:

- :func:`call_fields` builds one call's fields: seat, spec, resolved model
  id, provider class, whether a fallback answered, effort, duration, token
  counts where the provider reports them, and whether it succeeded.
- :func:`record_call` hands them to the open run record, which writes a
  ``model`` event (``run_record.RunRecord.model``). ``calls.jsonl`` carries
  the same fields beside its bodies (``call_recording.RecordingProvider``).

Like every recorder here, nothing in it ever raises into the run.
"""

from __future__ import annotations

from typing import Any, Protocol


class _Sink(Protocol):
    def model(self, fields: dict[str, Any]) -> None: ...


_sink: _Sink | None = None


def open_sink(sink: _Sink) -> None:
    """Make ``sink`` the run's model record (the run record, at its start)."""
    global _sink
    _sink = sink


def close_sink(sink: _Sink | None = None) -> None:
    """Stop recording into ``sink`` (or into whatever is open)."""
    global _sink
    if sink is None or _sink is sink:
        _sink = None


def announce_profile(profile: dict) -> None:
    """The run's profile is loaded: make it the process's run profile and
    open the run record with it. Entry points call this once."""
    from assemblyzero.core.seats import set_run_profile

    set_run_profile(profile)
    sink = _sink
    header = getattr(sink, "profile", None)
    if callable(header):
        header(profile)


def model_record_is_armed() -> bool:
    """Whether a run record is open to take per-call model events."""
    return _sink is not None


def _resolved_id(spec: str) -> str:
    if not spec:
        return ""
    try:
        from assemblyzero.core.seats import check_spec

        return check_spec(spec, "record")[1]
    except Exception:  # noqa: BLE001 - a record never costs a call
        # fail-open: a spec the registry cannot resolve (a scripted or
        # test-only one) is recorded with an empty id rather than guessed.
        return ""


def call_fields(
    *,
    inner: Any,
    spec: str,
    seat: str,
    effort: str | None,
    result: Any,
    duration_ms: int,
) -> dict[str, Any]:
    """The per-call fields for one answered call.

    ``inner`` is the transport ``get_provider`` built; for a
    ``FallbackProvider`` the answering provider's class and model are
    recorded and ``fallback`` says the fallback answered.
    """
    answering = getattr(inner, "answered", inner)
    fallback = bool(getattr(inner, "fallback_answered", False))
    resolved = _resolved_id(spec)
    if fallback:
        resolved = str(getattr(answering, "_model_id", "") or getattr(answering, "model", ""))
    from assemblyzero.core.seats import current_profile_name

    return {
        "profile": current_profile_name(),
        "seat": seat or "",
        "spec": spec or "",
        "resolved_model_id": resolved,
        "provider_class": type(answering).__name__,
        "fallback": fallback,
        "fallback_provider": type(answering).__name__ if fallback else "",
        "effort": effort or "",
        "duration_ms": int(duration_ms),
        "input_tokens": int(getattr(result, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(result, "output_tokens", 0) or 0),
        "success": bool(getattr(result, "success", False)),
        "model_used": str(getattr(result, "model_used", "") or ""),
    }


def record_call(fields: dict[str, Any]) -> bool:
    """Write one call's fields to the open run record. Never raises."""
    sink = _sink
    if sink is None:
        return False
    try:
        sink.model(fields)
        return True
    except Exception:  # noqa: BLE001 - a record never costs a call
        # fail-open: the call already happened and its result is returned
        # untouched; a run record that cannot take the line is reported by
        # the record itself (it warns on stderr when a write fails).
        return False

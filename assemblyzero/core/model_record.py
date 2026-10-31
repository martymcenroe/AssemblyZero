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

A spec the seat registry refuses raises (#3782): a call recorded with an
empty model id is attributed to nothing, which is the one thing this module
exists to prevent. A run record that cannot take a call's line alerts the
operator and the call's result is returned untouched, since nothing the run
produces reads that line.
"""

from __future__ import annotations

from typing import Any, Protocol

from assemblyzero.core import alert


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
    """The model id the seat registry resolves ``spec`` to.

    An empty spec has none: a provider wrapped without one, which is an
    answer. A spec ``check_spec`` refuses raises its ``ProfileError``
    (#3782): one with no provider, or one that resolves to a forbidden
    model. The old handler recorded it with an empty id, on the belief that
    scripted and test-only specs end there; they do not (``mock:`` and
    ``scripted:`` resolve to their model), so what it caught was a call on a
    model no seat may use, recorded as answered by nothing.
    """
    if not spec:
        return ""
    from assemblyzero.core.seats import check_spec

    return check_spec(spec, "record")[1]


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
    """Write one call's fields to the open run record; whether it was written.

    No open record is no write, and False: outside a run there is nothing
    to write to. A record that cannot take the line alerts the operator
    with the cause and returns False (#3782); the call already happened and
    its result is returned untouched, since nothing the run produces reads
    this line. An alert the record itself could not deliver is raised as it
    came, not alerted a second time.
    """
    sink = _sink
    if sink is None:
        return False
    try:
        sink.model(fields)
    except alert.AlertDeliveryError:
        raise
    except Exception as exc:  # noqa: BLE001 - every cause alerts, and the call is kept
        alert.alert_operator(
            what="write a model call's line to the run record",
            where="assemblyzero.core.model_record.record_call",
            cause=f"{type(exc).__name__}: {exc}",
            consequence=(
                "the call's result is returned; the run record has no model "
                f"line for this call (seat {fields.get('seat') or '(none)'}, "
                f"spec {fields.get('spec') or '(none)'})"
            ),
            spec=str(fields.get("spec") or ""),
        )
        return False
    return True

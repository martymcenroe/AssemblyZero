"""InstrumentedCall context manager for LLM call instrumentation.

Issue #774: Wraps LLM calls to capture timing, outputs, and cost.
"""

import logging
import time
from typing import TYPE_CHECKING, Callable, Literal, Optional, TypeVar

from assemblyzero.telemetry.cost import estimate_cost
from assemblyzero.telemetry.llm_call_record import (
    LLMCallRecord,
    LLMInputParams,
    LLMOutputMetadata,
    make_record_id,
    now_utc_iso,
)

if TYPE_CHECKING:
    from assemblyzero.telemetry.store import CallStore

logger = logging.getLogger(__name__)
T = TypeVar("T")


class InstrumentedCall:
    """Context manager that times an LLM call and writes a record on exit.

    Usage:
        with InstrumentedCall(store, inputs) as ic:
            response = call_llm(...)
            ic.record_outputs(parse_outputs(response))
    """

    def __init__(
        self,
        store: "CallStore",
        inputs: LLMInputParams,
        *,
        auto_write: bool = True,
    ) -> None:
        self._store = store
        self._inputs = inputs
        self._outputs: LLMOutputMetadata = {}
        self._auto_write = auto_write
        self._start_time: float = 0.0
        self._record_id = make_record_id()
        self._timestamp = now_utc_iso()
        self._success = True
        self._error: Optional[str] = None

    def __enter__(self) -> "InstrumentedCall":
        self._start_time = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> Literal[False]:
        latency_ms = (time.monotonic() - self._start_time) * 1000

        if exc_type is not None:
            self._success = False
            self._error = f"{exc_type.__name__}: {exc_val}"

        # Inject latency
        self._outputs["latency_ms"] = round(latency_ms, 2)

        # Compute cost estimate
        model_used = self._outputs.get("model_used", self._inputs.get("model_requested", ""))
        if model_used:
            cost = estimate_cost(
                model_used,
                self._outputs.get("input_tokens") or 0,
                self._outputs.get("output_tokens") or 0,
                cache_read_tokens=self._outputs.get("cache_read_tokens") or 0,
                cache_write_tokens=self._outputs.get("cache_write_tokens") or 0,
                thinking_tokens=self._outputs.get("thinking_tokens") or 0,
            )
            self._outputs["cost_usd_estimate"] = cost

        if self._auto_write:
            record = self.build_record()
            self._store.write(record)

        # Re-raise exception (return False = do not suppress)
        return False

    def record_outputs(self, outputs: LLMOutputMetadata) -> None:
        """Attach output metadata. Call this once the response is parsed."""
        self._outputs.update(outputs)

    def build_record(self) -> LLMCallRecord:
        """Assemble the final record."""
        return LLMCallRecord(
            record_id=self._record_id,
            timestamp_utc=self._timestamp,
            inputs=self._inputs,
            outputs=self._outputs,
            success=self._success,
            error=self._error,
        )


def instrument_llm_call(
    store: "CallStore",
    workflow: str,
    node: str,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator factory for instrumenting a single-call LLM function.

    The decorated function must accept `llm_inputs: LLMInputParams` kwarg
    and return a tuple of `(result, LLMOutputMetadata)`.
    """
    import functools

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            llm_inputs: LLMInputParams = kwargs.pop("llm_inputs", {})
            llm_inputs.setdefault("workflow", workflow)
            llm_inputs.setdefault("node", node)

            with InstrumentedCall(store, llm_inputs) as ic:
                result, outputs = func(*args, **kwargs)
                ic.record_outputs(outputs)
                return result

        return wrapper

    return decorator
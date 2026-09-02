"""A declared parameter or variable annotation types its receiver (#2713).

boostgauge run-issue4-182119, spec iteration 1:

    [FAIL] api_symbols_exist
    Spec calls methods not found in the target project's gathered symbols:
    `put` (e.g. `result_queue.put(snapshot)`)

on `def start(self, result_queue: queue.Queue)`. The check exempted a
receiver through imports, stdlib roots, framework parameters and -- since
#2399 -- a spec-defined function's RETURN annotation, and never read a
parameter's or an annotated assignment's declared type. This is #2399's rule
one position over, and the tests are the same shape: the founding true
positive stays catchable, the unannotated case is unchanged.
"""

from __future__ import annotations

import ast

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    _annotation_root,
    check_api_symbols_exist,
)

#: The target repo's gathered surface for these specs.
SYMBOLS = ["DataCollector", "SystemSnapshot", "collect", "start", "stop"]


def _spec(code: str) -> str:
    return "# S\n\n```python\n" + code + "```\n"


class TestRunTensReceiver:
    def test_a_parameter_annotated_with_a_stdlib_type_is_the_librarys(self) -> None:
        spec = _spec(
            "import queue\n\n"
            "class WindowsCollector:\n"
            "    def start(self, interval: float, result_queue: queue.Queue) -> None:\n"
            "        result_queue.put(1)\n"
        )
        result = check_api_symbols_exist(spec, SYMBOLS)
        assert result["passed"] is True, result["details"]

    def test_a_from_import_annotation(self) -> None:
        spec = _spec(
            "from queue import Queue\n\n"
            "def drain(q: Queue) -> None:\n    q.put(1)\n"
        )
        result = check_api_symbols_exist(spec, SYMBOLS)
        assert result["passed"] is True, result["details"]

    def test_an_annotated_assignment_without_a_value(self) -> None:
        spec = _spec(
            "import queue\n\n"
            "q: queue.Queue\n"
            "q.put(1)\n"
        )
        result = check_api_symbols_exist(spec, SYMBOLS)
        assert result["passed"] is True, result["details"]

    def test_optional_is_looked_through(self) -> None:
        spec = _spec(
            "import queue\nfrom typing import Optional\n\n"
            "def drain(q: Optional[queue.Queue]) -> None:\n    q.put(1)\n"
        )
        result = check_api_symbols_exist(spec, SYMBOLS)
        assert result["passed"] is True, result["details"]

    def test_the_thread_worker_shape_from_the_run(self) -> None:
        """The live draft, reduced: the queue is threaded through two methods."""
        spec = _spec(
            "import queue\nimport threading\n\n"
            "class WindowsCollector:\n"
            "    def start(self, result_queue: queue.Queue) -> None:\n"
            "        self._thread = threading.Thread(target=self._run_loop, args=(result_queue,))\n"
            "        self._thread.start()\n\n"
            "    def _run_loop(self, result_queue: queue.Queue) -> None:\n"
            "        result_queue.put(self.collect())\n"
        )
        result = check_api_symbols_exist(spec, SYMBOLS)
        assert result["passed"] is True, result["details"]


class TestJurisdictionIsUnchanged:
    def test_a_parameter_annotated_with_a_spec_class_stays_judged(self) -> None:
        """The founding true positive (#1527) with the annotation on: the
        spec defines `DataCollector`, so `collector` resolves to it."""
        spec = _spec(
            "class DataCollector:\n    def collect(self):\n        return None\n\n"
            "def run(collector: DataCollector) -> None:\n"
            "    collector.no_such_method()\n"
        )
        result = check_api_symbols_exist(spec, SYMBOLS)
        assert result["passed"] is False
        assert "no_such_method" in result["details"]

    def test_an_unannotated_parameter_is_unchanged(self) -> None:
        """#2391's `state` in `def apply(state)`: judged, as before."""
        spec = _spec(
            "def run(collector):\n    collector.no_such_method()\n"
        )
        result = check_api_symbols_exist(spec, SYMBOLS)
        assert result["passed"] is False
        assert "no_such_method" in result["details"]

    def test_a_union_declares_nothing_so_the_parameter_stays_judged(self) -> None:
        """Two candidates is not a declaration: nothing is recorded, and the
        parameter is judged exactly as an unannotated one is (#2391)."""
        spec = _spec(
            "from typing import Union\n"
            "class DataCollector:\n    pass\n\n"
            "def run(c: Union[DataCollector, int]) -> None:\n"
            "    c.no_such_method()\n"
        )
        result = check_api_symbols_exist(spec, SYMBOLS)
        assert result["passed"] is False
        assert "no_such_method" in result["details"]


class TestAnnotationRoot:
    def _root(self, text: str) -> str | None:
        return _annotation_root(ast.parse(text, mode="eval").body)

    def test_plain_and_dotted(self) -> None:
        assert self._root("queue.Queue") == "queue"
        assert self._root("Queue") == "Queue"

    def test_optional_and_annotated_look_through(self) -> None:
        assert self._root("Optional[queue.Queue]") == "queue"
        assert self._root("Annotated[queue.Queue, 'doc']") == "queue"
        assert self._root("Optional[Optional[queue.Queue]]") == "queue"

    def test_containers_keep_their_own_root(self) -> None:
        assert self._root("list[Gauge]") == "list"
        assert self._root("dict[str, Gauge]") == "dict"

    def test_union_and_strings_declare_nothing(self) -> None:
        assert self._root("Union[Gauge, int]") is None
        assert self._root("'queue.Queue'") is None

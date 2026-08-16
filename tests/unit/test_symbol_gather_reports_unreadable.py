"""An unreadable target-repo file is reported, never scraped (#2393).

`_extract_symbols_from_files` degraded to two regexes -- `^\\s*def (\\w+)` and
`^\\s*class (\\w+)` -- whenever a target-repo `.py` file would not parse. That
fallback fed the SYMBOL UNIVERSE the completeness gate judges every spec
against, which makes its errors the hardest kind to see: a name regex invents
becomes a false clearance, and a name it misses becomes a false hallucination
flag. #2391 is a live example of what a wrong symbol universe costs -- three
revision cycles and a dead stage -- and that universe was merely incomplete
rather than fabricated.

The fence fallback (#2392) mis-reads the SPEC. This one mis-read the TARGET
REPO, which is the authority the spec is judged against. An error here is an
error in the yardstick.

Standard 0028 section 3 permits deterministic scans of the pipeline's own
documents on the condition that they "cannot mask a contract failure because
there is no contract: the document is what it is". A `.py` file in the target
repo IS a contract that its content is Python.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
    SymbolGather,
    gather_symbols,
)
from assemblyzero.workflows.implementation_spec.state import FileToModify

BROKEN = "class BrokenClass\n    def my_method(self):\n        pass\n"
GOOD = "class Gauge:\n    def render(self):\n        pass\n\n\ndef helper():\n    pass\n"


def _file(path: str, content: str) -> FileToModify:
    return FileToModify(
        path=path, change_type="Modify", description="", current_content=content,
    )


class TestTheYardstickIsNotManufactured:
    def test_a_broken_file_contributes_no_symbols(self):
        gather = gather_symbols([_file("broken.py", BROKEN)])
        assert gather.symbols == []

    def test_the_scraped_names_are_specifically_absent(self):
        """The exact names the retired regexes would have produced."""
        gather = gather_symbols([_file("broken.py", BROKEN)])
        assert "my_method" not in gather.symbols
        assert "BrokenClass" not in gather.symbols

    def test_the_file_is_named_with_its_parse_error(self):
        gather = gather_symbols([_file("broken.py", BROKEN)])
        assert len(gather.unreadable) == 1
        path, error = gather.unreadable[0]
        assert path == "broken.py"
        assert error, "an exclusion with no reason is a silent downgrade"

    def test_the_error_carries_a_line_number(self):
        """'named -- path and parse error' is the issue's wording. A reason
        that does not locate the problem sends someone hunting."""
        _path, error = gather_symbols([_file("broken.py", BROKEN)]).unreadable[0]
        assert "line" in error


class TestGoodFilesAreUnaffected:
    def test_a_parseable_file_yields_its_symbols(self):
        gather = gather_symbols([_file("good.py", GOOD)])
        assert gather.symbols == ["Gauge", "helper", "render"]
        assert gather.unreadable == []

    def test_one_broken_file_does_not_cost_the_others(self):
        """Excluded rather than fatal: a mid-build target repo can hold a
        broken file, and refusing the whole stage over one would trade a quiet
        wrong answer for a loud useless one."""
        gather = gather_symbols([
            _file("good.py", GOOD),
            _file("broken.py", BROKEN),
        ])
        assert "Gauge" in gather.symbols
        assert "render" in gather.symbols
        assert len(gather.unreadable) == 1

    def test_non_python_files_are_not_reported_as_unreadable(self):
        """A .md file is not a broken .py file; reporting it would be a false
        alarm, and this check exists partly to stop those."""
        gather = gather_symbols([_file("README.md", "# not python {")])
        assert gather.unreadable == []
        assert gather.symbols == []

    def test_empty_content_is_not_reported_as_unreadable(self):
        gather = gather_symbols([_file("empty.py", "")])
        assert gather.unreadable == []

    def test_async_functions_are_gathered(self):
        gather = gather_symbols([_file("a.py", "async def fetch():\n    pass\n")])
        assert gather.symbols == ["fetch"]


class TestTheExclusionIsReported:
    """'the exclusion counted and reported. Never scraped into it silently.'"""

    def test_a_clean_gather_says_nothing(self):
        assert gather_symbols([_file("good.py", GOOD)]).describe() == ""

    def test_the_line_names_the_count_and_the_file(self):
        line = gather_symbols([_file("broken.py", BROKEN)]).describe()
        assert "1 target-repo .py file(s)" in line
        assert "broken.py" in line
        assert "EXCLUDED" in line

    def test_the_line_says_what_it_costs(self):
        """The consequence is the point: the spec is measured against a
        smaller universe than the repo has."""
        line = gather_symbols([_file("broken.py", BROKEN)]).describe()
        assert "smaller universe" in line
        assert "#2393" in line

    def test_many_exclusions_are_counted_not_all_listed(self):
        files = [_file(f"b{i}.py", BROKEN) for i in range(6)]
        line = gather_symbols(files).describe()
        assert "6 target-repo .py file(s)" in line
        assert "and 3 more" in line

    def test_the_node_prints_it(self):
        """The report must reach the run, not merely exist on a dataclass."""
        import importlib
        import inspect
        import types

        # `nodes/__init__` re-exports the FUNCTION `analyze_codebase`, which
        # shadows the module of the same name (lessons-learned 2026-08-14,
        # recurrence 2026-08-15). The isinstance guard is the positive control:
        # without it, a future shadowing would make this test fail for a reason
        # that looks unrelated.
        node = importlib.import_module(
            "assemblyzero.workflows.implementation_spec.nodes.analyze_codebase"
        )
        assert isinstance(node, types.ModuleType)

        source = inspect.getsource(node.analyze_codebase)
        assert "gather.describe()" in source


class TestTheDataclassContract:
    def test_unreadable_defaults_are_not_silently_shared(self):
        first = SymbolGather(symbols=[], unreadable=[])
        second = SymbolGather(symbols=[], unreadable=[])
        first.unreadable.append(("a.py", "boom"))
        assert second.unreadable == []

    @pytest.mark.parametrize(
        "content",
        [
            "def f(:\n",                 # broken signature
            "class C:\n  def m(self)\n",  # missing colon on method
            "if True\n    pass\n",        # missing colon on if
        ],
    )
    def test_various_syntax_errors_all_exclude(self, content):
        gather = gather_symbols([_file("x.py", content)])
        assert gather.symbols == []
        assert len(gather.unreadable) == 1

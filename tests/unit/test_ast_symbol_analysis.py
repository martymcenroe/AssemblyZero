"""The symbol checker parses fences instead of pattern-matching them (#1956).

Discharges the redesign debt recorded in #1954. Four false-positive families
landed against the regex collectors in one night — #1948 receivers, #1950
callbacks and docstrings, #1952 self-attribute handles and import-less stdlib,
#1954 diff markers — each patch correct and each followed by another, because a
regex cannot tell a call from a comment, a string, or a diff marker, and cannot
resolve what a name is bound to.

These tests pin three things the earlier families made expensive to learn:
the AST path is actually taken (not silently falling back on every fence), the
shapes regex got wrong now resolve correctly, and the true positives #1527 was
built to catch still block the gate.
"""

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    _fence_facts_regex,
    _normalize_fence,
    _scan_fences,
    check_api_symbols_exist,
    detect_unknown_method_calls,
)

TARGET_SYMBOLS = ["GaugeWindow", "render", "to_dict"]


def _flag(spec: str) -> dict[str, list[str]]:
    return detect_unknown_method_calls(spec, set(TARGET_SYMBOLS))


def _regex_flagged_methods(spec: str) -> set[str]:
    """Method names the pre-#1956 collectors would have reported for one fence.

    Used to show that a shape now handled correctly was genuinely mishandled
    before, rather than asserting an improvement no test can see.
    """
    fence = spec.split("```")[1]
    body = fence.split("\n", 1)[1]
    facts = _fence_facts_regex(_normalize_fence(body))
    known = set(TARGET_SYMBOLS)
    return {
        call.method
        for call in facts.calls
        if call.receiver not in facts.imported
        and call.method not in known
        and call.method not in facts.defined
    }


# =============================================================================
# The AST path is live
# =============================================================================


class TestParsePathIsTaken:
    """If every fence quietly fell back, the redesign would be inert."""

    def test_plain_python_fence_parses(self):
        spec = "# S\n\n```python\ndef f(win):\n    win.render()\n```\n"
        facts = _scan_fences(spec)
        assert [fence.parsed for fence in facts] == [True]

    def test_diff_fence_parses_after_normalization(self):
        spec = (
            "# S\n\n```diff\n"
            "+import tkinter as tk\n"
            "+\n"
            "+def build():\n"
            "+    root = tk.Tk()\n"
            "+    root.after(10, None)\n"
            "```\n"
        )
        facts = _scan_fences(spec)
        assert [fence.parsed for fence in facts] == [True]

    def test_indented_fence_body_parses(self):
        """A fence holding only an indented method body dedents into valid code."""
        spec = (
            "# S\n\n```python\n"
            "    def handle(self, win):\n"
            "        win.render()\n"
            "```\n"
        )
        assert [fence.parsed for fence in _scan_fences(spec)] == [True]

    def test_unparseable_fence_falls_back(self):
        """Broken Python degrades to the regex collectors, never to no scan."""
        spec = "# S\n\n```python\nclass Broken\n    win.model_dump()\n```\n"
        facts = _scan_fences(spec)
        assert [fence.parsed for fence in facts] == [False]

    def test_fallback_still_flags_the_hallucination(self):
        spec = "# S\n\n```python\nclass Broken\n    win.model_dump()\n```\n"
        assert "model_dump" in _flag(spec)

    def test_fallback_is_reported_in_the_details(self):
        """#1870's honesty rule: say when a fence was read with the weaker tool."""
        spec = "# S\n\n```python\nclass Broken\n    win.render()\n```\n"
        result = check_api_symbols_exist(spec, TARGET_SYMBOLS)
        assert result["passed"] is True, result["details"]
        assert "regex fallback" in result["details"]

    def test_clean_scan_says_nothing_about_fallback(self):
        spec = "# S\n\n```python\ndef f(win):\n    win.render()\n```\n"
        result = check_api_symbols_exist(spec, TARGET_SYMBOLS)
        assert result["passed"] is True
        assert "fallback" not in result["details"]


# =============================================================================
# Shapes a regex cannot read
# =============================================================================


class TestNonCodeContent:
    """Comments and strings hold no call nodes, so they cannot be flagged."""

    COMMENTED_OUT = (
        "# S\n\n```python\n"
        "def f(win):\n"
        "    # win.model_dump() was the old approach\n"
        "    win.render()\n"
        "```\n"
    )

    QUOTED_CODE = (
        "# S\n\n```python\n"
        "def f(win):\n"
        '    hint = "call win.model_dump() only on pydantic models"\n'
        "    win.render()\n"
        "    return hint\n"
        "```\n"
    )

    def test_commented_out_call_not_flagged(self):
        assert _flag(self.COMMENTED_OUT) == {}

    def test_commented_out_call_was_flagged_before(self):
        assert "model_dump" in _regex_flagged_methods(self.COMMENTED_OUT)

    def test_call_quoted_in_a_string_not_flagged(self):
        assert _flag(self.QUOTED_CODE) == {}

    def test_call_quoted_in_a_string_was_flagged_before(self):
        assert "model_dump" in _regex_flagged_methods(self.QUOTED_CODE)


class TestCallsSpanningLines:
    """A call split across lines is still a call."""

    WRAPPED_CALL = (
        "# S\n\n```python\n"
        "def f(win):\n"
        "    return (\n"
        "        win\n"
        "        .model_dump()\n"
        "    )\n"
        "```\n"
    )

    def test_wrapped_call_is_flagged(self):
        assert "model_dump" in _flag(self.WRAPPED_CALL)

    def test_wrapped_call_was_invisible_before(self):
        assert _regex_flagged_methods(self.WRAPPED_CALL) == set()


class TestBindingsBeyondAssignment:
    """`with` and `for` bind names too, and the binding carries provenance."""

    CONTEXT_MANAGER = (
        "# S\n\n```python\n"
        "from PIL import Image\n"
        "\n"
        "def load(path):\n"
        "    with Image.open(path) as source:\n"
        "        source.thumbnail((64, 64))\n"
        "```\n"
    )

    LOOP_TARGET = (
        "# S\n\n```python\n"
        "from pathlib import Path\n"
        "\n"
        "def scan(folder):\n"
        "    for entry in Path(folder).iterdir():\n"
        "        entry.samefile(folder)\n"
        "```\n"
    )

    def test_with_bound_handle_is_exempt(self):
        assert "thumbnail" not in _flag(self.CONTEXT_MANAGER)

    def test_with_bound_handle_was_flagged_before(self):
        assert "thumbnail" in _regex_flagged_methods(self.CONTEXT_MANAGER)

    def test_loop_bound_handle_is_exempt(self):
        assert "samefile" not in _flag(self.LOOP_TARGET)

    def test_loop_bound_handle_was_flagged_before(self):
        assert "samefile" in _regex_flagged_methods(self.LOOP_TARGET)


class TestTransitiveProvenance:
    """Exemption follows the whole chain, not one link of it."""

    # The spec shows the usage first and the constructor afterwards — routine
    # for a spec, and unreachable for a single ordered regex pass. `frame`
    # derives from `self.root`, which `self.root = tk.Tk()` exempts.
    SPLIT_FENCES = (
        "# S\n\n"
        "In the resize handler:\n\n"
        "```python\n"
        "def on_resize(self):\n"
        "    self.frame.pack_propagate(False)\n"
        "```\n\n"
        "The handles are built in the constructor:\n\n"
        "```python\n"
        "import tkinter as tk\n"
        "\n"
        "\n"
        "class Window:\n"
        "    def __init__(self):\n"
        "        self.root = tk.Tk()\n"
        "        self.frame = self.root.nametowidget('.')\n"
        "```\n"
    )

    def test_handle_derived_from_an_exempt_attribute_is_exempt(self):
        assert "pack_propagate" not in _flag(self.SPLIT_FENCES)

    def test_the_intermediate_handle_is_exempt_too(self):
        assert "nametowidget" not in _flag(self.SPLIT_FENCES)

    def test_the_split_spec_passes_the_gate(self):
        result = check_api_symbols_exist(self.SPLIT_FENCES, TARGET_SYMBOLS)
        assert result["passed"] is True, result["details"]


class TestUnresolvableReceiversStayUnjudged:
    """Conservatism preserved: what cannot be resolved is not accused."""

    def test_chained_call_result_receiver_not_flagged(self):
        spec = (
            "# S\n\n```python\n"
            "from PIL import Image\n"
            "\n"
            "def load(path):\n"
            "    return Image.open(path).convert('RGBA')\n"
            "```\n"
        )
        assert "convert" not in _flag(spec)

    def test_subscript_receiver_not_flagged(self):
        spec = (
            "# S\n\n```python\n"
            "def dispatch(registry, key):\n"
            "    return registry[key].unknown_hook()\n"
            "```\n"
        )
        assert "unknown_hook" not in _flag(spec)


# =============================================================================
# The findings the check exists for
# =============================================================================


class TestTruePositivesSurvive:
    def test_founding_1527_case_still_blocks(self):
        spec = (
            "# S\n\n```python\n"
            "def apply(question):\n"
            "    return question.model_dump()\n"
            "```\n"
        )
        result = check_api_symbols_exist(spec, TARGET_SYMBOLS)
        assert result["passed"] is False
        assert "model_dump" in result["details"]

    def test_undefined_self_attribute_still_flagged(self):
        spec = (
            "# S\n\n```python\n"
            "class A:\n"
            "    def go(self):\n"
            "        self._mystery_hook()\n"
            "```\n"
        )
        assert "_mystery_hook" in _flag(spec)

    def test_handle_from_an_unexempt_root_still_judged(self):
        """Provenance exempts only what descends from an exempt universe."""
        spec = (
            "# S\n\n```python\n"
            "def build(factory):\n"
            "    widget = factory.make()\n"
            "    widget.invented_method()\n"
            "```\n"
        )
        flagged = _flag(spec)
        assert "invented_method" in flagged
        assert "make" in flagged

    def test_call_site_names_the_method(self):
        spec = (
            "# S\n\n```python\n"
            "def apply(question):\n"
            "    return question.model_dump()\n"
            "```\n"
        )
        sites = _flag(spec)["model_dump"]
        assert "model_dump" in sites[0]
        assert sites[0] == "return question.model_dump()"

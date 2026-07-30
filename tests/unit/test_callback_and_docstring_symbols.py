"""Constructor-assigned callbacks and docstring-quoted code are not
hallucinations (#1950).

Phase-6 kill (run11b-issue5-034438): the drafter defined GUI callbacks
idiomatically (`self._on_quit_cb = on_quit`), the def-only collector
couldn't see them, and the checker drove a rename-oscillation
(_on_quit → _on_quit_cb) across revise cycles. Separately, `Tk` was
flagged from a DOCSTRING quoting the test-strategy rule verbatim.
"""

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_api_symbols_exist,
    detect_unknown_method_calls,
)

TARGET_SYMBOLS = ["GaugeWindow", "render", "to_dict"]

PHASE6_SPEC_SHAPE = '''# Spec

```python
class WindowHelper:
    """Complies with docs/design/0001-test-strategy.md (No tkinter.Tk() instantiated)."""

    def __init__(self, on_quit, on_geometry_change):
        self._on_quit_cb = on_quit
        self._on_geometry_change_cb = on_geometry_change

    def handle_close(self):
        self._on_quit_cb()

    def handle_move(self, x, y, size):
        self._on_geometry_change_cb(x, y, size)
```
'''


class TestCallbackAssignments:
    def test_the_phase6_shape_passes(self):
        result = check_api_symbols_exist(PHASE6_SPEC_SHAPE, TARGET_SYMBOLS)
        assert result["passed"] is True, result["details"]

    def test_assigned_callbacks_not_flagged(self):
        flagged = detect_unknown_method_calls(
            PHASE6_SPEC_SHAPE, set(TARGET_SYMBOLS)
        )
        assert "_on_quit_cb" not in flagged
        assert "_on_geometry_change_cb" not in flagged


class TestDocstringQuotedCode:
    def test_docstring_tk_not_flagged(self):
        flagged = detect_unknown_method_calls(
            PHASE6_SPEC_SHAPE, set(TARGET_SYMBOLS)
        )
        assert "Tk" not in flagged

    def test_real_code_outside_docstrings_still_flagged(self):
        spec = (
            "# S\n\n```python\ndef f(win):\n"
            '    """No tkinter.Tk() instantiated."""\n'
            "    win.model_dump()\n```\n"
        )
        flagged = detect_unknown_method_calls(spec, set(TARGET_SYMBOLS))
        assert "Tk" not in flagged
        assert "model_dump" in flagged

    def test_uncalled_undefined_self_attribute_still_flagged(self):
        """Calling a self method never defined OR assigned stays a finding —
        the #1527 spirit for private APIs the implementer would have to
        guess."""
        spec = (
            "# S\n\n```python\nclass A:\n"
            "    def go(self):\n"
            "        self._mystery_hook()\n```\n"
        )
        flagged = detect_unknown_method_calls(spec, set(TARGET_SYMBOLS))
        assert "_mystery_hook" in flagged

"""Diff-formatted snippets stop blinding the symbol collectors (#1954).

Finale roll 5: the spec template's required before/after diffs carried
`+ root = tk.Tk()` (invisible to every line-anchored collector past the
'+') while `root.after(...)` still matched the call regex — asymmetric
blindness, byte-identical double strike, roll killed.
"""

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_api_symbols_exist,
    detect_unknown_method_calls,
)

TARGET_SYMBOLS = ["GaugeWindow", "render"]

DIFF_SPEC_SHAPE = """# Spec

```diff
+import tkinter as tk
+
+def build(poll_ms, tick):
+    root = tk.Tk()
+    root.attributes('-topmost', False)
+    root.after(poll_ms, tick)
```
"""

DIFF_WITH_UNKNOWN_RECEIVER = """# Spec

```diff
-    old_helper.legacy_call()
+    pass
```
"""


class TestDiffNormalization:
    def test_the_finale_diff_shape_passes(self):
        result = check_api_symbols_exist(DIFF_SPEC_SHAPE, TARGET_SYMBOLS)
        assert result["passed"] is True, result["details"]

    def test_plus_prefixed_definitions_are_seen(self):
        flagged = detect_unknown_method_calls(
            DIFF_SPEC_SHAPE, set(TARGET_SYMBOLS)
        )
        assert "attributes" not in flagged
        assert "after" not in flagged

    def test_minus_lines_also_normalized(self):
        """Removed-side calls on unknown receivers still get judged (and
        here 'old_helper' is neither imported nor assigned — flagged)."""
        flagged = detect_unknown_method_calls(
            DIFF_WITH_UNKNOWN_RECEIVER, set(TARGET_SYMBOLS)
        )
        assert "legacy_call" in flagged

    def test_plain_code_unaffected(self):
        spec = "# S\n\n```python\ndef f(win):\n    win.model_dump()\n```\n"
        flagged = detect_unknown_method_calls(spec, set(TARGET_SYMBOLS))
        assert "model_dump" in flagged

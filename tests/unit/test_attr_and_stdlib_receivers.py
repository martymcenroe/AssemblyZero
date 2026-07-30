"""Self-attribute widget handles and import-less stdlib receivers (#1952).

Finale kills (runs 035215 and 035542): `self.root = tk.Tk()` then
`self.root.attributes('-alpha', ...)` — the call regex sees receiver
`root`, which nothing exempted, so the whole tkinter widget surface
flagged; and `copy.deepcopy(config)` flagged in snippets that
legitimately omit import headers.
"""

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_api_symbols_exist,
    detect_unknown_method_calls,
)

TARGET_SYMBOLS = ["GaugeWindow", "render"]

FINALE_SPEC_SHAPE = """# Spec

```python
import tkinter as tk


class AlwaysOnTop:
    def __init__(self):
        self.root = tk.Tk()
        self.canvas = tk.Canvas(self.root)

    def apply(self, config):
        updated = copy.deepcopy(config)
        self.root.attributes("-alpha", updated["idle_alpha"])
        self.root.after(0, self.toggle_topmost)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.create_image(0, 0, anchor="nw")
        return updated

    def toggle_topmost(self):
        pass

    def on_press(self, event):
        pass
```
"""


class TestSelfAttributeReceivers:
    def test_the_finale_shape_passes(self):
        result = check_api_symbols_exist(FINALE_SPEC_SHAPE, TARGET_SYMBOLS)
        assert result["passed"] is True, result["details"]

    def test_widget_methods_via_self_attrs_not_flagged(self):
        flagged = detect_unknown_method_calls(
            FINALE_SPEC_SHAPE, set(TARGET_SYMBOLS)
        )
        for name in ("attributes", "after", "bind", "create_image"):
            assert name not in flagged, f"{name} flagged: {flagged.get(name)}"


class TestStdlibModuleReceivers:
    def test_importless_stdlib_receiver_not_flagged(self):
        flagged = detect_unknown_method_calls(
            FINALE_SPEC_SHAPE, set(TARGET_SYMBOLS)
        )
        assert "deepcopy" not in flagged

    def test_target_object_hallucination_still_flagged(self):
        spec = (
            "# S\n\n```python\ndef f(win):\n"
            "    win.model_dump()\n```\n"
        )
        flagged = detect_unknown_method_calls(spec, set(TARGET_SYMBOLS))
        assert "model_dump" in flagged

"""The symbol checker knows whose method it is judging (#1948).

Phase-5 kill (run11b-issue2-032618): api_symbols_exist rejected Pillow's
documented API (ImageDraw.Draw, alpha_composite, ellipse), pathlib.Path,
and a method the spec itself defined — the target repo's 20 gathered
symbols have no authority over any of those universes. Twice-identical
BLOCKs made the revise loop unwinnable; the roll was killed as a
determined outcome. Same wrong-universe disease #1901 fixed for imports.
"""

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_api_symbols_exist,
    detect_unknown_method_calls,
)

TARGET_SYMBOLS = ["TelltaleState", "update", "decay_floor", "to_dict"]

# Distilled from the killed roll's actual spec content.
PHASE5_SPEC_SHAPE = """# Spec

```python
from PIL import Image, ImageDraw
from pathlib import Path
import queue as q


class TelltaleTrayHelper:
    def get_context_menu_actions(self):
        return ["Reset"]


def render(telltale_layer, base_img, x_pos):
    er_draw = ImageDraw.Draw(telltale_layer)
    er_draw.ellipse([x_pos, 0, x_pos + 4, 4])
    out = Path("out.png")
    q.Queue()
    helper = TelltaleTrayHelper()
    actions = helper.get_context_menu_actions()
    return Image.alpha_composite(base_img, telltale_layer)
```
"""

HALLUCINATED_SPEC = """# Spec

```python
def apply(state):
    state.model_dump()
    return question.model_validate(state)
```
"""


class TestExemptUniverses:
    def test_the_phase5_shape_passes(self):
        result = check_api_symbols_exist(PHASE5_SPEC_SHAPE, TARGET_SYMBOLS)
        assert result["passed"] is True, result["details"]

    def test_imported_module_receivers_exempt(self):
        flagged = detect_unknown_method_calls(
            PHASE5_SPEC_SHAPE, set(TARGET_SYMBOLS)
        )
        for name in ("Draw", "alpha_composite", "Path", "Queue"):
            assert name not in flagged

    def test_import_alias_receiver_exempt(self):
        flagged = detect_unknown_method_calls(
            PHASE5_SPEC_SHAPE, set(TARGET_SYMBOLS)
        )
        assert "Queue" not in flagged  # `import queue as q` → q.Queue()

    def test_spec_defined_method_exempt(self):
        flagged = detect_unknown_method_calls(
            PHASE5_SPEC_SHAPE, set(TARGET_SYMBOLS)
        )
        assert "get_context_menu_actions" not in flagged

    def test_assignment_propagation_one_level(self):
        """`er_draw = ImageDraw.Draw(...)` makes er_draw exempt, so
        `er_draw.ellipse(` is Pillow's business, not the target repo's."""
        flagged = detect_unknown_method_calls(
            PHASE5_SPEC_SHAPE, set(TARGET_SYMBOLS)
        )
        assert "ellipse" not in flagged


class TestTruePositivesSurvive:
    def test_hallucinated_target_api_still_flagged(self):
        """#1527's founding case: pydantic methods on a plain dataclass."""
        flagged = detect_unknown_method_calls(
            HALLUCINATED_SPEC, set(TARGET_SYMBOLS)
        )
        assert "model_dump" in flagged
        assert "model_validate" in flagged

    def test_check_blocks_on_true_positive(self):
        result = check_api_symbols_exist(HALLUCINATED_SPEC, TARGET_SYMBOLS)
        assert result["passed"] is False
        assert "model_dump" in result["details"]

    def test_known_target_methods_pass(self):
        spec = "# S\n\n```python\ndef f(state):\n    state.update(1)\n    return state.to_dict()\n```\n"
        result = check_api_symbols_exist(spec, TARGET_SYMBOLS)
        assert result["passed"] is True

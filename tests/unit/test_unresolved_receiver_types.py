"""Unresolved is not hallucinated, third shape: the receiver's TYPE (#2399).

Three rounds, three shapes of one class, each found only after the previous fix
shipped:

    #2391  the receiver's NAME          `parser` in a pytest_* hook
    #2396  the receiver chain's ROOT    `request.config.getoption(...)`
    #2399  the receiver's TYPE          `img = render(...)`, `img.getpixel(...)`

All three are the same question — does the target repo own this receiver? — and
this module pins the answer as ONE rule rather than three patches:

    Judge a receiver only when the checker can resolve what it holds to
    something the target repo owns. Otherwise it is unresolved, and unresolved
    is a distinct, honest category from wrong.

WHY THIS SHAPE WAS URGENT RATHER THAN THEORETICAL
-------------------------------------------------
Draft 013 of boostgauge #1 carries nine such calls — `img.getpixel` seven times,
`img_base.getpixel`, `img.save` — all inside one fence spanning lines 389-531.
That fence imports only `math`; the `from boostgauge.gauge import render` that
was clearing them sits at lines 290 and 309, in two different fences. Neither
`getpixel` nor `save` is in the 21 gathered symbols, and `save` is not
allowlisted either.

The reviewer was already rewriting the inside of that fence — verdict 012 line 3
orders `test_req_070` to sample a different pixel because `v=30` lands on a tick
mark — while the clearance rested on imports elsewhere that it had no reason to
preserve, across up to nine revision rounds.
"""

import re
from pathlib import Path

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_api_symbols_exist,
    detect_unknown_method_calls,
)

#: The live run's 21, verbatim. `render`, `getpixel` and `save` are all absent —
#: which is the condition the fix has to survive, not a simplification of it.
GATHERED_21 = [
    "AppConfig", "DataCollector", "PositionConfig", "SessionState",
    "SystemSnapshot", "TelltaleWindows", "ThresholdConfig", "Thresholds",
    "WindowsCollector", "__init__", "_atomic_write", "_collect_snapshot",
    "_deep_merge", "_normalize", "_poll_loop", "apply_threshold_updates",
    "load_config", "mitigate_invalid_config", "save_session_changes",
    "start", "stop",
]

FIXTURE_013 = (
    Path(__file__).parent.parent
    / "fixtures" / "boostgauge1_spec_deadlock" / "013-spec-draft.md"
)


def _spec(body: str) -> str:
    return "# S\n\n```python\n" + body + "```\n"


def _flag(body: str, symbols=None) -> dict[str, list[str]]:
    return detect_unknown_method_calls(_spec(body), set(symbols or GATHERED_21))


def _stripped_013() -> str:
    """Draft 013 as a revision would leave it: the producing import gone."""
    text = FIXTURE_013.read_text(encoding="utf-8")
    stripped = re.sub(r"(?m)^from boostgauge\.gauge import .*\n", "", text)
    assert "from boostgauge.gauge import" not in stripped
    return stripped


class TestTheStrippedDraftClears:
    """The real first half. Draft 013 AS IT STANDS already passes, so proving
    that again proves nothing — it is an input that was never going to fail."""

    def test_the_strip_actually_removed_something(self):
        """Guards the guard: a no-op strip would make every assertion vacuous."""
        text = FIXTURE_013.read_text(encoding="utf-8")
        removed = len(text.splitlines()) - len(_stripped_013().splitlines())
        assert removed == 2, f"expected 2 import lines removed, got {removed}"

    def test_the_stripped_draft_still_contains_the_calls(self):
        stripped = _stripped_013()
        assert stripped.count("img.getpixel(") == 7
        assert "img_base.getpixel(" in stripped
        assert "img.save(" in stripped

    def test_stripped_draft_flags_nothing(self):
        flagged = detect_unknown_method_calls(_stripped_013(), set(GATHERED_21))
        assert flagged == {}, flagged

    def test_stripped_draft_passes_the_check(self):
        result = check_api_symbols_exist(_stripped_013(), GATHERED_21)
        assert result["passed"] is True, result["details"]

    def test_neither_method_is_in_the_gathered_surface(self):
        """The clearance must not be an artefact of a generous symbol list."""
        assert "getpixel" not in GATHERED_21
        assert "save" not in GATHERED_21
        assert "render" not in GATHERED_21


class TestUnresolvedProducers:
    def test_free_producer_is_unresolved(self):
        """`render` is not imported, not gathered, not defined here."""
        assert "getpixel" not in _flag(
            "def test_x():\n"
            "    img = render(50, [], 256)\n"
            "    assert img.getpixel((1, 1)) == (1, 2, 3, 4)\n"
        )

    def test_annotated_spec_defined_producer_resolves_to_its_owner(self):
        """`def render(...) -> Image.Image` says the result is Pillow's."""
        assert _flag(
            "from PIL import Image\n"
            "\n"
            "def render(v: float) -> Image.Image:\n"
            "    ...\n"
            "\n"
            "def test_x():\n"
            "    img = render(50)\n"
            "    img.save('out.png')\n"
            "    assert img.getpixel((1, 1)) == (1, 2, 3, 4)\n"
        ) == {}

    def test_third_party_constructor_without_its_import(self):
        """`draw = ImageDraw.Draw(img)` — the other at-risk idiom the harvester
        surfaced, same class, and it must clear for the same reason."""
        assert "arc" not in _flag(
            "def test_x():\n"
            "    draw = ImageDraw.Draw(img_in)\n"
            "    draw.arc((0, 0, 1, 1), start=0, end=1)\n"
        )


class TestTruePositivesSurvive:
    """The half that decides whether the check still checks anything.

    #1527's founding case has the identical bound-from-a-call shape, which is
    exactly why the obvious version of this fix inverts the check.
    """

    def test_gathered_class_still_flagged(self):
        """#1527's founding true positive, stated as the guard."""
        assert "model_dump" in _flag(
            "def build():\n"
            "    gauge = GaugeWindow()\n"
            "    return gauge.model_dump()\n",
            symbols=[*GATHERED_21, "GaugeWindow"],
        )

    def test_check_blocks_on_the_gathered_class_hallucination(self):
        result = check_api_symbols_exist(
            _spec(
                "def build():\n"
                "    gauge = GaugeWindow()\n"
                "    return gauge.model_dump()\n"
            ),
            [*GATHERED_21, "GaugeWindow"],
        )
        assert result["passed"] is False
        assert "model_dump" in result["details"]

    def test_spec_defined_class_still_flagged(self):
        """A class the spec defines is placeable, so its instances are judged."""
        assert "model_dump" in _flag(
            "class Gauge:\n"
            "    def draw(self):\n"
            "        pass\n"
            "\n"
            "def build():\n"
            "    g = Gauge()\n"
            "    return g.model_dump()\n"
        )

    def test_bare_parameter_still_flagged(self):
        assert "model_dump" in _flag(
            "def apply(state):\n    state.model_dump()\n"
        )

    def test_annotation_pointing_at_a_REPO_type_still_flagged(self):
        """The annotation rule resolves to the OWNER; it does not blanket-clear.

        `-> SessionState` names a gathered symbol, so the result belongs to the
        target repo and a method absent from its surface is still a finding.
        """
        assert "model_dump" in _flag(
            "def make() -> SessionState:\n"
            "    ...\n"
            "\n"
            "def build():\n"
            "    s = make()\n"
            "    return s.model_dump()\n"
        )

    def test_unannotated_spec_function_does_not_clear_by_being_defined(self):
        """Defining a function says nothing about what it returns.

        Without an annotation the binding is unresolved rather than exempt, so
        this clears — but it must clear as UNRESOLVED, not because the spec
        happened to mention the name. The sibling assertion above proves an
        annotated repo type is still judged, which is what separates the two.
        """
        assert "getpixel" not in _flag(
            "def render(v):\n"
            "    ...\n"
            "\n"
            "def test_x():\n"
            "    img = render(1)\n"
            "    img.getpixel((1, 1))\n"
        )

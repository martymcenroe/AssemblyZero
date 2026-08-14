"""Unresolvable is not hallucinated: framework-injected receivers (#2391).

boostgauge #1's resumed roll (run-issue1-173403) died at the completeness cap
in 91 seconds, three identical failures, on a GATE DEADLOCK rather than a
drafting defect:

* Gemini's spec review DEMANDED a `conftest.py` registering the custom flag via
  `pytest_addoption` — pytest crashes on unregistered flags, and boostgauge
  ruling #271 mandates the registration.
* The symbol check REJECTED the obedient spec, because `parser.addoption(` names
  a method absent from the target repo's 21 gathered symbols.

`parser` is injected by pytest and typed `_pytest.config.argparsing.Parser`. It
was never going to be in boostgauge's surface. One gate demanded the line, the
other forbade it, and no draft could satisfy both.

The two-sided proof is the point of this module. Widening the check until the
deadlock clears is trivial and worthless; these tests pin BOTH that the real
rejected draft now passes AND that a hallucinated method on a class the target
repo genuinely owns is still caught by name.
"""

from pathlib import Path

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_api_symbols_exist,
    detect_unknown_method_calls,
)

#: Stand-in for boostgauge's gathered surface. The only property that matters is
#: the one the live run had: `addoption` is not in it, and never could be.
TARGET_SYMBOLS = ["GaugeWindow", "render", "to_dict", "update", "SkinConfig"]

FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "boostgauge1_spec_deadlock"
    / "001-spec-draft.md"
)


def _flag(spec: str) -> dict[str, list[str]]:
    return detect_unknown_method_calls(spec, set(TARGET_SYMBOLS))


# =============================================================================
# Half one: the deadlock ends
# =============================================================================


class TestTheDeadlockedDraftClears:
    """The exact artifact the live run rejected, byte for byte."""

    def test_fixture_still_contains_the_call_that_deadlocked(self):
        """Guards the guard: if the fixture loses the line, the rest proves nothing."""
        assert "parser.addoption(" in FIXTURE.read_text(encoding="utf-8")

    def test_addoption_no_longer_flagged(self):
        flagged = _flag(FIXTURE.read_text(encoding="utf-8"))
        assert "addoption" not in flagged, (
            f"the deadlock survives; flagged={flagged}"
        )

    def test_the_draft_passes_the_check(self):
        result = check_api_symbols_exist(
            FIXTURE.read_text(encoding="utf-8"), TARGET_SYMBOLS
        )
        assert result["passed"] is True, result["details"]


class TestFrameworkInjectionIsExempt:
    def test_pytest_hook_parameter_is_exempt(self):
        spec = (
            "# S\n\n```python\n"
            "def pytest_addoption(parser):\n"
            '    parser.addoption("--generate-baselines", action="store_true")\n'
            "```\n"
        )
        assert "addoption" not in _flag(spec)

    def test_every_parameter_of_a_hook_is_exempt(self):
        """pluggy hands the hook all of its arguments, not just the first."""
        spec = (
            "# S\n\n```python\n"
            "def pytest_collection_modifyitems(config, items):\n"
            "    config.getoption('--slow')\n"
            "    items.remove(items[0])\n"
            "```\n"
        )
        flagged = _flag(spec)
        assert "getoption" not in flagged

    def test_builtin_fixture_parameter_is_exempt_outside_a_hook(self):
        spec = (
            "# S\n\n```python\n"
            "def test_writes_config(tmp_path, monkeypatch):\n"
            "    monkeypatch.setenv('BG_HOME', str(tmp_path))\n"
            "    tmp_path.joinpath('x.json').write_text('{}')\n"
            "```\n"
        )
        flagged = _flag(spec)
        assert "setenv" not in flagged
        assert "joinpath" not in flagged


# =============================================================================
# Half two: the check did not become useless
# =============================================================================


class TestTruePositivesSurvive:
    """A fix that only clears the deadlock has widened the gate into nothing."""

    def test_hallucinated_method_on_an_owned_class_still_flagged(self):
        """The operator's second half: the receiver resolves to a target class.

        `GaugeWindow` is in the target repo's surface, so `gauge` is the target
        repo's object and `model_dump` is the target repo's business — exactly
        #1527's founding case, pydantic methods on a plain dataclass.
        """
        spec = (
            "# S\n\n```python\n"
            "def build():\n"
            "    gauge = GaugeWindow()\n"
            "    return gauge.model_dump()\n"
            "```\n"
        )
        flagged = _flag(spec)
        assert "model_dump" in flagged, flagged

    def test_check_blocks_on_the_owned_class_hallucination(self):
        spec = (
            "# S\n\n```python\n"
            "def build():\n"
            "    gauge = GaugeWindow()\n"
            "    return gauge.model_dump()\n"
            "```\n"
        )
        result = check_api_symbols_exist(spec, TARGET_SYMBOLS)
        assert result["passed"] is False
        assert "model_dump" in result["details"]

    def test_an_ordinary_parameter_is_still_judged(self):
        """`state` is unresolvable too, and stays judged on purpose.

        Exempting every parameter would be defensible in the abstract and fatal
        in practice: #1527's founding true positive and #1952's regression set
        both arrive as bare parameter receivers. Only a parameter a framework
        NAMES itself as owning is exempt.
        """
        spec = "# S\n\n```python\ndef apply(state):\n    state.model_dump()\n```\n"
        assert "model_dump" in _flag(spec)

    def test_self_is_never_exempted(self):
        """A blanket parameter exemption would free the entire target surface."""
        spec = (
            "# S\n\n```python\n"
            "class Gauge:\n"
            "    def draw(self):\n"
            "        self.model_dump()\n"
            "```\n"
        )
        assert "model_dump" in _flag(spec)

    def test_a_hook_does_not_exempt_names_beyond_its_own_parameters(self):
        """The exemption is scoped to what pytest actually injects."""
        spec = (
            "# S\n\n```python\n"
            "def pytest_addoption(parser):\n"
            '    parser.addoption("--x")\n'
            "\n"
            "def apply(state):\n"
            "    state.model_dump()\n"
            "```\n"
        )
        flagged = _flag(spec)
        assert "addoption" not in flagged
        assert "model_dump" in flagged

"""A fix asks for edits, not a rebirth (#2407).

The acceptance the issue names, verbatim:

  "a fix iteration on a multi-function file with one failing test produces an
   edit script touching only the implicated code, byte-identical preservation
   of the rest is asserted the way the spec stage asserts it, and the fallback
   path is exercised by a fixture whose edit script is deliberately malformed."

All three are below. The preservation assertion is byte-level and not merely
the ratio the spec stage reports, because the ratio is line-containment
telemetry and the property that actually matters is that untouched functions
come out identical.
"""

from __future__ import annotations


import pytest

from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
    MIN_BYTES_FOR_EDIT_SCRIPT,
    apply_code_edit_script,
    build_code_edit_script_prompt,
    failures_for_file,
    response_is_a_regeneration,
    should_use_edit_script,
    unchanged_ratio,
)

# A multi-function file, as the acceptance requires. `scale` is broken; the
# other three functions must survive byte-identical.
MULTI_FUNCTION_FILE = '''"""Gauge skin: stingray."""

import math


def bezel_radius(width: int) -> float:
    """Outer bezel radius for a gauge of this width."""
    return width / 2.0 - 3.0


def needle_angle(value: float, span: float) -> float:
    """Map a value onto the needle sweep, in radians."""
    return math.radians(-120.0 + 240.0 * (value / span))


def scale(value: float, lo: float, hi: float) -> float:
    """Normalise a reading into 0..1."""
    return (value - lo) / (hi - lo)


def tick_positions(count: int) -> list[float]:
    """Evenly spaced tick fractions across the sweep."""
    return [i / (count - 1) for i in range(count)]
'''

GOOD_EDIT_SCRIPT = """<<<<<<< SEARCH
def scale(value: float, lo: float, hi: float) -> float:
    \"\"\"Normalise a reading into 0..1.\"\"\"
    return (value - lo) / (hi - lo)
=======
def scale(value: float, lo: float, hi: float) -> float:
    \"\"\"Normalise a reading into 0..1, clamped to the endpoints.\"\"\"
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))
>>>>>>> REPLACE"""

FAILING_TEST = (
    "FAILED tests/unit/test_stingray.py::test_scale_clamps - "
    "AssertionError: assert 1.5 <= 1.0"
)


# ---------------------------------------------------------------------------
# Acceptance 1 + 2: touches only the implicated code, preserves the rest
# ---------------------------------------------------------------------------


class TestFixTouchesOnlyTheImplicatedCode:
    def test_the_edit_applies(self):
        outcome = apply_code_edit_script(GOOD_EDIT_SCRIPT, MULTI_FUNCTION_FILE)
        assert outcome.ok is True
        assert outcome.blocks == 1

    def test_the_failing_function_changed(self):
        outcome = apply_code_edit_script(GOOD_EDIT_SCRIPT, MULTI_FUNCTION_FILE)
        assert "min(1.0" in outcome.code
        assert "if hi == lo:" in outcome.code

    @pytest.mark.parametrize(
        "untouched",
        [
            'def bezel_radius(width: int) -> float:\n'
            '    """Outer bezel radius for a gauge of this width."""\n'
            '    return width / 2.0 - 3.0\n',
            'def needle_angle(value: float, span: float) -> float:\n'
            '    """Map a value onto the needle sweep, in radians."""\n'
            '    return math.radians(-120.0 + 240.0 * (value / span))\n',
            'def tick_positions(count: int) -> list[float]:\n'
            '    """Evenly spaced tick fractions across the sweep."""\n'
            '    return [i / (count - 1) for i in range(count)]\n',
        ],
        ids=["bezel_radius", "needle_angle", "tick_positions"],
    )
    def test_every_other_function_survives_byte_identical(self, untouched):
        """The property that matters. A regeneration can silently rewrite
        passing code; an edit script cannot, because the model's output never
        contains these bytes at all."""
        outcome = apply_code_edit_script(GOOD_EDIT_SCRIPT, MULTI_FUNCTION_FILE)
        assert untouched in outcome.code

    def test_the_whole_file_outside_the_edit_is_byte_identical(self):
        """Stronger than per-function: everything except the one replaced
        span is unchanged, asserted by reconstructing the original."""
        outcome = apply_code_edit_script(GOOD_EDIT_SCRIPT, MULTI_FUNCTION_FILE)
        search, replace = GOOD_EDIT_SCRIPT.split("=======")
        search = search.replace("<<<<<<< SEARCH\n", "").rstrip("\n")
        replace = replace.replace(">>>>>>> REPLACE", "").lstrip("\n").rstrip("\n")
        assert outcome.code.replace(replace, search) == MULTI_FUNCTION_FILE

    def test_preservation_is_reported_the_way_the_spec_stage_reports_it(self):
        outcome = apply_code_edit_script(GOOD_EDIT_SCRIPT, MULTI_FUNCTION_FILE)
        assert outcome.preserved > 0.8
        assert "preserved byte-identical" in outcome.describe()
        assert "#2407" in outcome.describe()

    def test_the_ratio_is_the_spec_stages_own_function(self):
        """Same format, same parser, same telemetry -- imported, not copied."""
        outcome = apply_code_edit_script(GOOD_EDIT_SCRIPT, MULTI_FUNCTION_FILE)
        assert outcome.preserved == unchanged_ratio(
            MULTI_FUNCTION_FILE, outcome.code
        )


# ---------------------------------------------------------------------------
# Acceptance 3: the fallback, exercised by a deliberately malformed script
# ---------------------------------------------------------------------------


class TestMalformedScriptFallsBack:
    def test_a_search_that_does_not_match_falls_back(self):
        """The commonest real failure: the model did not copy verbatim."""
        malformed = """<<<<<<< SEARCH
def scale(value, lo, hi):
    return (value - lo) / (hi - lo)
=======
def scale(value, lo, hi):
    return 0.0
>>>>>>> REPLACE"""
        outcome = apply_code_edit_script(malformed, MULTI_FUNCTION_FILE)
        assert outcome.ok is False
        assert outcome.code is None
        assert "not found" in outcome.failures[0]

    def test_an_ambiguous_search_falls_back(self):
        text = "x = 1\ny = 2\nx = 1\n"
        malformed = "<<<<<<< SEARCH\nx = 1\n=======\nx = 99\n>>>>>>> REPLACE"
        outcome = apply_code_edit_script(malformed, text)
        assert outcome.ok is False
        assert "ambiguous" in outcome.failures[0]

    def test_a_response_with_no_blocks_at_all_falls_back(self):
        outcome = apply_code_edit_script(
            "Sure! Here is the fixed file:\n\ndef scale(): ...",
            MULTI_FUNCTION_FILE,
        )
        assert outcome.ok is False
        assert "no edit blocks" in outcome.failures[0]

    def test_truncated_markers_fall_back(self):
        outcome = apply_code_edit_script(
            "<<<<<<< SEARCH\ndef scale(", MULTI_FUNCTION_FILE
        )
        assert outcome.ok is False

    def test_edits_that_empty_the_file_fall_back(self):
        """A patch that deletes everything is a regeneration wearing a hat."""
        text = "only line\n"
        script = "<<<<<<< SEARCH\nonly line\n=======\n\n>>>>>>> REPLACE"
        outcome = apply_code_edit_script(script, text)
        assert outcome.ok is False
        assert "emptied" in outcome.failures[0]

    def test_partial_application_is_never_returned_as_success(self):
        """One good block and one bad block must yield NOTHING -- the same
        contract the spec stage holds."""
        script = GOOD_EDIT_SCRIPT + """

<<<<<<< SEARCH
def nonexistent_function():
    pass
=======
def nonexistent_function():
    return 1
>>>>>>> REPLACE"""
        outcome = apply_code_edit_script(script, MULTI_FUNCTION_FILE)
        assert outcome.ok is False
        assert outcome.code is None

    def test_the_fallback_reason_is_reported(self):
        outcome = apply_code_edit_script("nonsense", MULTI_FUNCTION_FILE)
        assert "fell back to full regeneration" in outcome.describe()

    def test_a_returned_whole_file_is_detected_before_parsing(self):
        assert response_is_a_regeneration("```python\ndef x(): pass\n```") is True
        assert response_is_a_regeneration("import math\n\ndef x(): pass") is True
        assert response_is_a_regeneration(GOOD_EDIT_SCRIPT) is False


# ---------------------------------------------------------------------------
# When the edit script is used at all
# ---------------------------------------------------------------------------


class TestGating:
    def test_an_initial_draft_does_not_use_an_edit_script(self):
        """Nothing to patch. This is the 'file does not yet exist' fallback."""
        assert should_use_edit_script("Add", "", "") is False

    def test_no_failure_context_means_no_fix_to_make(self):
        assert should_use_edit_script("Modify", MULTI_FUNCTION_FILE, "") is False

    def test_a_fix_on_an_existing_file_uses_an_edit_script(self):
        assert should_use_edit_script(
            "Modify", MULTI_FUNCTION_FILE, FAILING_TEST
        ) is True

    def test_a_tiny_file_is_cheaper_to_regenerate(self):
        assert should_use_edit_script("Modify", "x = 1\n", FAILING_TEST) is False

    def test_the_threshold_is_stated_not_hidden(self):
        assert MIN_BYTES_FOR_EDIT_SCRIPT > 0
        just_under = "y" * (MIN_BYTES_FOR_EDIT_SCRIPT - 1)
        just_over = "y" * (MIN_BYTES_FOR_EDIT_SCRIPT + 1)
        assert should_use_edit_script("Modify", just_under, FAILING_TEST) is False
        assert should_use_edit_script("Modify", just_over, FAILING_TEST) is True

    def test_an_add_that_resolved_to_an_existing_file_still_qualifies(self):
        """#2032 flips Add to Modify when the base already ships the file; a
        fix on one of those is the same case."""
        assert should_use_edit_script(
            "Add", MULTI_FUNCTION_FILE, FAILING_TEST
        ) is True


# ---------------------------------------------------------------------------
# Scoping the prompt to the implicated failures
# ---------------------------------------------------------------------------


class TestFailureScoping:
    CORPUS = "\n".join([
        "FAILED tests/unit/test_stingray.py::test_scale - AssertionError",
        "FAILED tests/unit/test_gauge.py::test_needle - TypeError",
        "FAILED tests/visual/test_gauge.py::test_render - ValueError",
    ])

    def test_only_the_implicated_failures_are_kept(self):
        scoped = failures_for_file(self.CORPUS, "src/boostgauge/skins/stingray.py")
        assert "test_stingray" in scoped
        assert "test_needle" not in scoped

    def test_a_test_file_maps_to_the_module_under_it(self):
        scoped = failures_for_file(self.CORPUS, "src/boostgauge/gauge.py")
        assert "test_gauge.py::test_needle" in scoped
        assert "test_stingray" not in scoped

    def test_an_unattributable_corpus_is_passed_through_whole(self):
        """The issue's conditional is honoured literally: scope the prompt
        WHERE the runner can attribute. Silently narrowing to nothing would
        starve the fix of what it needs."""
        corpus = "FAILED tests/test_misc.py::test_a - boom"
        scoped = failures_for_file(corpus, "src/boostgauge/skins/stingray.py")
        assert scoped == corpus

    def test_an_empty_corpus_stays_empty(self):
        assert failures_for_file("", "src/x.py") == ""

    def test_a_dotted_module_reference_attributes(self):
        corpus = "FAILED t.py::test_x - ImportError: boostgauge.skins.stingray"
        scoped = failures_for_file(corpus, "src/boostgauge/skins/stingray.py")
        assert scoped == corpus


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------


class TestPrompt:
    def _prompt(self):
        return build_code_edit_script_prompt(
            "src/boostgauge/skins/stingray.py",
            MULTI_FUNCTION_FILE, FAILING_TEST,
        )

    def test_it_forbids_a_rewrite(self):
        assert "Do NOT rewrite the file" in self._prompt()

    def test_it_specifies_the_1528_format(self):
        p = self._prompt()
        assert "<<<<<<< SEARCH" in p
        assert "=======" in p
        assert ">>>>>>> REPLACE" in p

    def test_it_says_untouched_code_must_not_change(self):
        assert "cannot and must not change" in self._prompt()

    def test_it_carries_the_current_file_and_the_failures(self):
        p = self._prompt()
        assert "def bezel_radius" in p
        assert "test_scale_clamps" in p

    def test_it_tells_the_model_the_rest_already_passes(self):
        """The reasoning-cost half of the issue: concentrate on the failures
        instead of re-deriving everything."""
        assert "already passes" in self._prompt()

    def test_the_system_prompt_is_a_patch_engine_not_a_file_writer(self):
        from assemblyzero.workflows.testing.nodes.implementation import (
            edit_script_fix as m,
        )

        assert "NEVER rewrite" in m.EDIT_SCRIPT_CODE_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# The wiring: one call, no retry, and a real fallback
# ---------------------------------------------------------------------------


class TestWiring:
    def _try(self, monkeypatch, response, error=""):
        from assemblyzero.workflows.testing.nodes.implementation import (
            orchestrator as impl,
        )

        calls = []

        def fake_call(prompt, file_path=None, model=None, system_prompt=""):
            calls.append({"prompt": prompt, "system_prompt": system_prompt})
            return (response, error)

        monkeypatch.setattr(impl, "call_claude_for_file", fake_call)
        outcome = impl.try_edit_script_fix(
            filepath="src/boostgauge/skins/stingray.py",
            existing_content=MULTI_FUNCTION_FILE,
            failure_context=FAILING_TEST,
        )
        return calls, outcome

    def test_a_good_script_is_applied(self, monkeypatch):
        calls, outcome = self._try(monkeypatch, GOOD_EDIT_SCRIPT)
        assert outcome.ok is True
        assert len(calls) == 1

    def test_a_malformed_script_costs_exactly_one_call(self, monkeypatch):
        """No retry here on purpose: a malformed patch is not a transport
        failure, and the fallback has its own budget. Retrying would spend
        twice to reach the same place."""
        calls, outcome = self._try(monkeypatch, "not an edit script at all")
        assert outcome.ok is False
        assert len(calls) == 1

    def test_the_patch_engine_system_prompt_is_used(self, monkeypatch):
        """The stable system prompt describes whole-file output; mixing the
        two is how a model ends up sending a file back."""
        calls, _ = self._try(monkeypatch, GOOD_EDIT_SCRIPT)
        assert "NEVER rewrite" in calls[0]["system_prompt"]

    def test_an_api_error_falls_back_rather_than_raising(self, monkeypatch):
        _calls, outcome = self._try(monkeypatch, "", error="timed out")
        assert outcome.ok is False
        assert "API error" in outcome.failures[0]

    def test_an_exception_falls_back_rather_than_costing_the_roll(self, monkeypatch):
        from assemblyzero.workflows.testing.nodes.implementation import (
            orchestrator as impl,
        )

        def boom(*_a, **_k):
            raise RuntimeError("transport exploded")

        monkeypatch.setattr(impl, "call_claude_for_file", boom)
        outcome = impl.try_edit_script_fix(
            filepath="src/x.py", existing_content=MULTI_FUNCTION_FILE,
            failure_context=FAILING_TEST,
        )
        assert outcome.ok is False
        assert "exploded" in outcome.failures[0]

    def test_the_prompt_is_scoped_to_this_files_failures(self, monkeypatch):
        from assemblyzero.workflows.testing.nodes.implementation import (
            orchestrator as impl,
        )

        calls = []

        def fake_call(prompt, file_path=None, model=None, system_prompt=""):
            calls.append(prompt)
            return (GOOD_EDIT_SCRIPT, "")

        monkeypatch.setattr(impl, "call_claude_for_file", fake_call)
        impl.try_edit_script_fix(
            filepath="src/boostgauge/skins/stingray.py",
            existing_content=MULTI_FUNCTION_FILE,
            failure_context=(
                "FAILED tests/unit/test_stingray.py::test_scale - boom\n"
                "FAILED tests/unit/test_other.py::test_unrelated - bang"
            ),
        )
        assert "test_stingray" in calls[0]
        assert "test_unrelated" not in calls[0]

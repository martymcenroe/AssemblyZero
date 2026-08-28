"""The observed completeness/pinning deadlock, as fixture (#2555, #2556).

run-issue331-092913: the fence-parse gate demanded a one-line retag —
"lines 81-83 (```python)", an output-example repr in a Python-tagged fence —
the drafter made that exact change in all six attempts across three rounds,
and pinning reverted it every time as content no verdict ever objected to:
four byte-identical drafts (md5 379d0859a6750175a48f42934fe31c03) and a
deterministic kill for every resume. The cap halt then asserted the drafter
"left the flagged code unchanged each time" with six [PINNING] refusal lines
in the same log.

Root cause, verified against the preserved lineage: the complaint addresses
its target by line numbers and a triple-backtick fence tag, which no token
pattern could read — while the message's own advice clause ("```text,
```json, ```bash") fed named_tokens the garbage spans between the fence runs
("text,", "json,"), defeating the names-nothing-extractable abstention. The
guards enforced with a vocabulary that named zero draft lines.

These tests replay that shape end to end against the real producers: the
complaint comes from check_api_symbols_exist itself, the address from
named_line_ranges, the enforcement verdict from enforce_pinning, and the
halt text from validate_completeness.
"""

from __future__ import annotations

from unittest.mock import patch

from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
    _apply_pinning,
)
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_api_symbols_exist,
    check_functions_have_io_examples,
    validate_completeness,
)
from assemblyzero.workflows.implementation_spec.revision_pinning import (
    enforce_pinning,
    named_line_flags,
    named_line_ranges,
    named_tokens,
)

#: The observed draft's shape: a function-spec section whose Output Example
#: is a repr inside a ```python fence — 256x256 is the invalid decimal
#: literal — and unrelated sections a completed round passed unobjected.
DRAFT = """# Implementation Spec: Stingray Skin

## 1. Overview

The stingray skin renders the gauge face.

## 5. Function Specifications

### 5.1 `render(size, skin)`

**Input Example:**

```python
size = 256
skin = "stingray"
```

**Output Example:**

```python
<PIL.Image.Image image mode=RGBA size=256x256 at 0x1A2B3C4D>
```

**Edge Cases:**
- `size < 128` -> raises an error

### 5.2 `clear_cache()`

Clears the render cache. Returns None.

## 6. Conventions

Baselines are self-generated only.
"""

SYMBOLS = ["render", "clear_cache"]


def _complaint() -> str:
    """The REAL producer's complaint about DRAFT — never a hand-copy."""
    result = check_api_symbols_exist(DRAFT, SYMBOLS)
    assert result["passed"] is False
    return result["details"]


def _failing_fence_open_index() -> int:
    """0-based index of the unparseable fence's opening ```python line."""
    lines = DRAFT.splitlines()
    return next(i for i, line in enumerate(lines) if "<PIL" in line) - 1


def _retagged() -> str:
    """The exact fix the drafter attempted every round: retag one line."""
    lines = DRAFT.splitlines()
    lines[_failing_fence_open_index()] = "```text"
    return "\n".join(lines) + "\n"


class TestTheComplaintSpeaksPinningsLanguage:
    def test_the_fence_failure_reports_under_its_own_name(self):
        """#2556: the fence-parse precondition is not the symbol check — the
        run's hallucination-check artifacts (all passed) belong to the
        symbol half, and the halt must not send the operator there."""
        result = check_api_symbols_exist(DRAFT, SYMBOLS)
        assert result["check_name"] == "python_fences_parse"

    def test_the_line_citation_parses_into_the_fence_address(self):
        details = _complaint()
        open_line = _failing_fence_open_index() + 1  # 1-based
        assert (open_line, open_line + 2) in named_line_ranges([details])

    def test_the_advice_clause_yields_no_spurious_tokens(self):
        """The old "(```text, ```json, ```bash)" advice minted tokens from
        the spans BETWEEN the fence runs, defeating pinning's
        names-nothing-extractable abstention while naming zero draft
        lines."""
        assert named_tokens("", [_complaint()]) == set()

    def test_the_cited_range_names_the_fence_block(self):
        details = _complaint()
        flags = named_line_flags(
            DRAFT, set(), named_line_ranges([details])
        )
        open_index = _failing_fence_open_index()
        assert flags[open_index] is True
        assert flags[open_index + 1] is True


class TestTheDeadlockIsBroken:
    """Acceptance, both directions."""

    def test_the_mandated_retag_survives_pinning_and_the_check_passes(self):
        details = _complaint()
        result = enforce_pinning(
            DRAFT,
            _retagged(),
            current_tokens=named_tokens("", [details]),
            ever_tokens=named_tokens("", [details]),
            current_ranges=named_line_ranges([details]),
        )
        assert result.text == _retagged(), (
            "the change the completeness failure explicitly demands must "
            "never be revertible by pinning in the same round"
        )
        assert result.refusals == ()
        assert result.regressions == ()
        after = check_api_symbols_exist(result.text, SYMBOLS)
        assert after["passed"] is True, "one round, converged"

    def test_an_unobjected_line_is_still_reverted(self):
        """The inverse stays true: line addressing frees the cited block,
        not the document."""
        details = _complaint()
        tinkered = DRAFT.replace(
            "Baselines are self-generated only.",
            "Baselines regenerate freely.",
        )
        result = enforce_pinning(
            DRAFT,
            tinkered,
            current_tokens=named_tokens("", [details]),
            ever_tokens=named_tokens("", [details]),
            current_ranges=named_line_ranges([details]),
        )
        assert "Baselines are self-generated only." in result.text
        assert "regenerate freely" not in result.text
        assert result.refusals
        assert result.regressions

    def test_apply_pinning_does_not_abstain_on_a_line_cited_complaint(self, capsys):
        """With the advice clause minting no tokens, only the line citation
        keeps pinning engaged — the abstain valve must read it."""
        tinkered = DRAFT.replace(
            "Baselines are self-generated only.",
            "Baselines regenerate freely.",
        )
        text, events = _apply_pinning(
            {}, DRAFT, tinkered,
            response="",
            review_feedback="",
            completeness_issues=[_complaint()],
        )
        capsys.readouterr()
        assert text == DRAFT
        assert any("refused" in event for event in events)
        assert not any("names nothing extractable" in event for event in events)


class TestNamedLineRanges:
    def test_a_dashed_range_extracts(self):
        assert named_line_ranges(
            ["lines 81-83 (```python) — SyntaxError: invalid decimal literal"]
        ) == ((81, 83),)

    def test_a_bare_line_number_is_not_an_address(self):
        """The observed complaint's own error text carries "line 1" — a
        position inside the snippet, not a draft address. Parsing it would
        unlock the block holding draft line 1 on every fence complaint."""
        assert named_line_ranges(
            ["SyntaxError: invalid decimal literal (<unknown>, line 1)"]
        ) == ()

    def test_a_reversed_range_is_ignored(self):
        assert named_line_ranges(["lines 9-3 nonsense"]) == ()

    def test_none_and_empty(self):
        assert named_line_ranges(None) == ()
        assert named_line_ranges([]) == ()

    def test_an_out_of_bounds_range_names_nothing(self):
        assert named_line_flags("a\nb\nc", set(), ((10, 12),)) == [
            False, False, False,
        ]


class TestTheHaltNamesEnforcement:
    """#2556: the cap halt consults the pinning record before reading an
    identical complaint as the-drafter-left-it-unchanged. A reverted
    revision re-presents the previous bytes, indistinguishable from drafter
    inaction from the complaint stream alone."""

    REFUSAL = (
        "[PINNING] refused: 1 line(s) starting '```python' — locked "
        "content the verdict did not name (#2532)"
    )
    COMPLAINT = (
        "1 code fence(s) tagged as Python do not parse as Python: "
        "lines 81-83 (```python) — SyntaxError: invalid decimal literal"
    )

    def _state(self, iteration=3, shown=(), breakdown=(), pinning_events=()):
        return {
            "spec_draft": "# Spec\n\n" + ("body line\n" * 40),
            "files_to_modify": [],
            "pattern_references": [],
            "repo_root": "",
            "lld_content": "",
            "review_iteration": iteration,
            "max_iterations": 3,
            "checks_shown_to_drafter": list(shown),
            "prior_completeness_breakdown": [dict(e) for e in breakdown],
            "pinning_events": list(pinning_events),
        }

    def _at_cap(self, details, make_breakdown, pinning_events=()):
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes."
            "validate_completeness.check_modify_files_have_excerpts",
            return_value={"check_name": "x", "passed": False, "details": details},
        ):
            first = validate_completeness(self._state())
            return validate_completeness(self._state(
                shown=first["checks_shown_to_drafter"],
                breakdown=make_breakdown(first["completeness_issues"]),
                pinning_events=pinning_events,
            ))

    def _identical_history(self, failures):
        return [
            {"iteration": i, "failures": list(failures)} for i in range(3)
        ]

    def test_reversions_on_the_record_name_enforcement_not_the_drafter(
        self, capsys
    ):
        """The #331 replay: identical complaint every round PLUS refusal
        events in state — the halt names the guard and routes at the
        deadlock, not at a hypothesized false positive."""
        out = self._at_cap(
            self.COMPLAINT,
            self._identical_history,
            pinning_events=[self.REFUSAL] * 6,
        )
        capsys.readouterr()
        message = out["error_message"]
        assert "IDENTICAL complaint" in message
        assert "pinning enforcement reverted" in message
        assert "#2555" in message
        assert "left the flagged code unchanged" not in message
        assert "reached the check unchanged" not in message
        assert "declining" not in message
        assert "believes correct" not in message
        assert "false positive" not in message

    def test_no_reversions_keeps_the_unchanged_reading(self, capsys):
        """The classification survives where it is true: no enforcement in
        the loop means the drafter's output is what the check saw."""
        out = self._at_cap(
            self.COMPLAINT,
            self._identical_history,
            pinning_events=(),
        )
        capsys.readouterr()
        message = out["error_message"]
        assert "reached the check unchanged" in message
        assert "false positive" in message
        assert "pinning enforcement reverted" not in message

    def test_non_refusal_events_do_not_suppress_the_unchanged_reading(
        self, capsys
    ):
        """Only reversions break the inference — an abstention note is not
        enforcement."""
        out = self._at_cap(
            self.COMPLAINT,
            self._identical_history,
            pinning_events=[
                "[PINNING] the verdict names nothing extractable — pinning "
                "not applied this round (#2532)"
            ],
        )
        capsys.readouterr()
        message = out["error_message"]
        assert "reached the check unchanged" in message
        assert "pinning enforcement reverted" not in message


# ---------------------------------------------------------------------------
# The same class on a check that fires on ordinary specs (#2590)
# ---------------------------------------------------------------------------
#
# The fence complaint above addressed its target in a scheme no token could
# read. This one addressed it in a scheme that PARSES and matches nothing:
# `check_functions_have_io_examples` backticked the name with a `()` suffix,
# and `def compute_needle_angle(value, redline):` never contains the literal
# `compute_needle_angle()`. Two drafts differing solely in the parameter list
# drew a byte-identical complaint, one addressable and one not, and the
# broken case is the ordinary one -- most functions take arguments.
#
# Registry class 3, standard 0029: the demanded change is never refusable.

#: The issue's measured table, verbatim. These two differ ONLY in the
#: parameter list, which is the whole point: the message is byte-identical
#: and the old token addressed one and not the other.
IO_DRAFT_WITH_PARAMS = """# Spec

## Section 6

def compute_needle_angle(value, redline):
    pass
"""

IO_DRAFT_ZERO_ARG = """# Spec

## Section 6

def compute_needle_angle():
    pass
"""

#: Two functions, so the inverse direction has an UNNAMED sibling to protect.
IO_DRAFT_TWO_FUNCS = """# Spec

## Section 6 Signatures

```python
def compute_needle_angle(value, redline):
    pass


def render_gauge(surface, values):
    pass
```
"""


def _io_complaint(draft: str) -> str:
    """The real check's real message. Never a hand-written string: a reword
    that drops the address must fail these tests, and it cannot if the test
    supplies the text itself."""
    result = check_functions_have_io_examples(draft)
    assert result["passed"] is False, "fixture no longer trips the check"
    return result["details"]


def _with_example(draft: str) -> str:
    """The fix the complaint demands, in the shape that used to be reverted.

    Verified 2026-08-28: `enforce_pinning` passes INSERTIONS through by
    design, so a fixture that merely adds a line above `pass` would have
    survived before the repair and proved nothing. Replacing `pass` is both
    the natural way to give a stub an example and the shape enforcement
    actually refused.
    """
    return draft.replace(
        "def compute_needle_angle(value, redline):\n    pass\n",
        "def compute_needle_angle(value, redline):\n"
        "    # example: compute_needle_angle(75, 60) -> 42.0\n"
        "    return 42.0\n",
    )


class TestTheIoComplaintAddressesItsTarget:
    """The issue's table, both directions, against the real producer."""

    def test_the_parameterised_function_is_addressed(self):
        """#2590's broken case. The token must occur in the draft, not
        merely parse."""
        tokens = named_tokens("", [_io_complaint(IO_DRAFT_WITH_PARAMS)])
        assert "compute_needle_angle" in tokens
        flags = named_line_flags(IO_DRAFT_WITH_PARAMS, tokens)
        assert any(flags), (
            "the complaint names a function the draft defines and still "
            "addresses no line of it"
        )

    def test_the_zero_arg_function_stays_addressed(self):
        """The case that worked by accident must keep working on purpose."""
        tokens = named_tokens("", [_io_complaint(IO_DRAFT_ZERO_ARG)])
        assert any(named_line_flags(IO_DRAFT_ZERO_ARG, tokens))

    def test_both_drafts_draw_the_same_token(self):
        """The messages differ only where the drafts do. If a future reword
        makes addressability depend on the parameter list again, this is
        the assertion that says so."""
        with_params = named_tokens("", [_io_complaint(IO_DRAFT_WITH_PARAMS)])
        zero_arg = named_tokens("", [_io_complaint(IO_DRAFT_ZERO_ARG)])
        assert with_params == zero_arg == {"compute_needle_angle"}

    def test_the_span_carries_no_call_parens(self):
        """The specific regression guard. `name()` parses as a token and
        occurs only in a zero-arg def, which is how this defect worked."""
        details = _io_complaint(IO_DRAFT_WITH_PARAMS)
        assert "`compute_needle_angle`" in details
        assert "`compute_needle_angle()`" not in details


class TestTheIoDeadlockIsBroken:
    """Acceptance, both directions -- the class-3 end-to-end property."""

    def test_the_demanded_example_survives_pinning_in_the_same_round(self):
        details = _io_complaint(IO_DRAFT_WITH_PARAMS)
        tokens = named_tokens("", [details])
        revised = _with_example(IO_DRAFT_WITH_PARAMS)
        assert revised != IO_DRAFT_WITH_PARAMS

        result = enforce_pinning(
            IO_DRAFT_WITH_PARAMS,
            revised,
            current_tokens=tokens,
            ever_tokens=tokens,
            current_ranges=named_line_ranges([details]),
        )
        assert result.refusals == (), (
            "the change the completeness failure explicitly demands must "
            "never be revertible by pinning in the same round"
        )
        assert result.regressions == ()
        assert "example:" in result.text, "the demanded example was reverted"

    def test_an_unnamed_sibling_function_is_still_locked(self):
        """The inverse. Naming a function frees ITS block, not the fence.

        Inside a fence `_blocks` splits per def, so this is where scoping is
        testable at all -- outside one, the unit is the whole markdown
        section and both functions share a block by design.
        """
        only_one = {"compute_needle_angle"}
        revised = _with_example(IO_DRAFT_TWO_FUNCS).replace(
            "def render_gauge(surface, values):\n    pass\n",
            "def render_gauge(surface, values):\n    return None\n",
        )
        result = enforce_pinning(
            IO_DRAFT_TWO_FUNCS,
            revised,
            current_tokens=only_one,
            ever_tokens=only_one,
        )
        assert "example:" in result.text, "the named function's fix was lost"
        assert "return None" not in result.text, (
            "meddling with an unnamed function survived -- the bare-name "
            "token unlocked more than the block it names"
        )
        assert result.refusals

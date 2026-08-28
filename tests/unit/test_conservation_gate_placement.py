"""Where the #2563 conservation gate belongs, decided by measurement (#2617).

#2611 asserted the gate's firing rate on injected rows is zero. #2617 asked the
next question: should it therefore RUN at the spec stage as a live check?

The answer is no, and both halves are measured here rather than argued:

1. **On injected rows it is redundant, and provably so.** Re-assertion restores
   the machine-owned block byte-for-byte every round, so every literal of the
   LLD's authoritative tables is present by construction -- not sampled. The
   gate driven against a *tampered* draft still finds nothing, because
   re-assertion has already repaired it.

2. **Off injected rows its complaint cannot be acted on.** A conservation
   message names the literals that are MISSING, and something missing cannot
   address a line of the draft. Run through the #2557 addressability
   classifier, it comes back UNADDRESSABLE -- which is the #2555 deadlock class
   by construction, not by accident. Wiring it into the spec stage's
   pinning-governed revision loop would file the thirteenth instance of a class
   with two open findings (#2591, #2593).

So the gate stays at the lld stage, where prose-to-artifact derivation still
happens and where a drafter can act on "carry this clause". The spec stage is
protected by structure instead of by inspection.

Both directions are pinned, per the issue: the removal case is proved by the
tests that show re-assertion covers what a live gate would have covered, and
the control set proves the gate still fires where it does run.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.implementation_spec import table_injection as spec_inject
from assemblyzero.workflows.implementation_spec.message_addressability import (
    ADDRESSED,
    UNADDRESSABLE,
    addresses_draft,
)
from assemblyzero.workflows.requirements import table_injection as lld_inject
from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
    validate_assertion_literal_conservation,
)

SOURCE_TABLE = """\
| ID | Criterion | Binding value (quoted) | Assertion method |
|----|-----------|------------------------|------------------|
| S1 | sampling window | sampled ONLY at 0.12 R-0.25 R either side | probe at 0.12 R |
| S7 | redline colour | #AA0F19 | sample band mid at 75% |
| S9 | needle tip | 0.82 R | measure tip radius |
"""

ISSUE_BODY = f"# Dial\n\n## Pass criteria\n\n{SOURCE_TABLE}"

SPEC_SKELETON = """\
# Implementation Spec: Dial

## 1. Overview

Render the dial.

## 10. Test Mapping

- `test_band_mid` covers S7.
"""


@pytest.fixture
def lld() -> str:
    draft = "# LLD\n\n## 3. Requirements\n\nThe dial samples on a window.\n"
    return lld_inject.apply_injection(
        draft, lld_inject.build_injection(ISSUE_BODY)
    )


@pytest.fixture
def injected_spec(lld: str) -> str:
    return spec_inject.apply_injection(
        SPEC_SKELETON, spec_inject.build_injection(lld)
    )


# ---------------------------------------------------------------------------
# 1. Redundant on injected rows -- proved against tampering, not just a clean draft
# ---------------------------------------------------------------------------


class TestReassertionCoversWhatTheGateWouldCover:
    def test_the_fixture_really_carries_the_literals(self, lld: str) -> None:
        """Guard: everything below is vacuous if the LLD lost them first."""
        for literal in ("0.12 R", "#AA0F19", "0.82 R"):
            assert literal in lld

    def test_an_injected_spec_sheds_nothing(self, injected_spec: str, lld: str) -> None:
        errors = validate_assertion_literal_conservation(lld, injected_spec)
        assert errors == [], [e.message for e in errors]

    @pytest.mark.parametrize(
        "gone,replacement",
        [
            ("#AA0F19", "#000000"),
            ("0.82 R", "the ruled radius"),
            ("0.12 R-0.25 R", "a window"),
        ],
    )
    def test_tampering_inside_the_block_is_repaired_before_the_gate_could_see_it(
        self, injected_spec: str, lld: str, gone: str, replacement: str
    ) -> None:
        """The heart of the answer.

        A drafter edits a binding value inside the machine-owned block. A live
        conservation gate would fire. Re-assertion runs first and restores the
        canonical text, so by the time anything could inspect the draft the
        literal is back -- which is why a gate there could only ever pass.
        """
        tampered = injected_spec.replace(gone, replacement)
        assert gone not in tampered, "the tamper fixture must actually remove it"

        # A gate inspecting the TAMPERED draft would have fired ...
        assert validate_assertion_literal_conservation(lld, tampered)

        # ... but re-assertion is what actually runs, and it repairs it.
        restored, changed = spec_inject.reassert(tampered, lld)

        assert changed is True
        assert validate_assertion_literal_conservation(lld, restored) == []

    def test_a_deleted_block_is_reinstated_too(
        self, injected_spec: str, lld: str
    ) -> None:
        gutted = spec_inject.strip_injection(injected_spec)
        assert validate_assertion_literal_conservation(lld, gutted)

        restored, _ = spec_inject.reassert(gutted, lld)

        assert validate_assertion_literal_conservation(lld, restored) == []

    def test_reassertion_is_total_not_sampled(
        self, injected_spec: str, lld: str
    ) -> None:
        """The gate conserves the literals its regexes recognise. Re-assertion
        restores the block byte-for-byte, so it covers the whole row including
        prose the extractor never looks at -- strictly stronger, not merely
        equivalent."""
        restored, _ = spec_inject.reassert(
            injected_spec.replace("sampled ONLY at", "sampled at"), lld
        )
        assert "sampled ONLY at 0.12 R-0.25 R either side" in restored


# ---------------------------------------------------------------------------
# 2. Off injected rows -- the complaint cannot be acted on
# ---------------------------------------------------------------------------


class TestTheComplaintIsUnaddressableByConstruction:
    """#2617's third question, answered by running the sweep's own classifier.

    The gate's message names the literals that appear NOWHERE in the derived
    document. Something absent cannot address a line of it, so no rewording
    rescues this -- it is the shape of the check, not the wording of the
    message.
    """

    def test_the_message_addresses_no_line_of_the_draft(self) -> None:
        lossy = SPEC_SKELETON  # never injected, carries none of the literals
        errors = validate_assertion_literal_conservation(
            ISSUE_BODY.replace("# Dial", "# LLD"), lossy
        )
        assert errors, "the fixture must genuinely fail the gate"

        verdict = addresses_draft(errors[0].message, lossy)

        assert verdict.verdict == UNADDRESSABLE, (
            f"expected UNADDRESSABLE, got {verdict.verdict} via {verdict.via}"
        )

    def test_the_control_a_check_that_does_address_its_draft(self) -> None:
        """Without this, the assertion above could pass against a classifier
        that called everything unaddressable."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            check_function_spec_sections_have_examples,
        )

        draft = (
            "# Spec\n\n## 5. Function Specifications\n\n"
            "### 5.1 `render_face()`\n\nNo examples.\n"
        )
        result = check_function_spec_sections_have_examples(draft)
        assert result["passed"] is False

        assert addresses_draft(result["details"], draft).verdict == ADDRESSED

    def test_naming_absent_content_is_the_reason(self) -> None:
        """The mechanism, stated as a test: every literal the message quotes is
        by definition missing from the draft it describes."""
        lossy = SPEC_SKELETON
        errors = validate_assertion_literal_conservation(
            ISSUE_BODY.replace("# Dial", "# LLD"), lossy
        )
        message = errors[0].message

        for literal in ("0.12 R", "#AA0F19", "0.82 R"):
            if repr(literal) in message:
                assert literal not in lossy


# ---------------------------------------------------------------------------
# 3. The gate keeps its home -- the control for the whole decision
# ---------------------------------------------------------------------------


class TestTheGateStaysAtTheLldStage:
    """Removing a check from a stage it never ran in proves nothing unless the
    stage it DOES run in is pinned."""

    def test_it_fires_on_a_lossy_lld(self) -> None:
        lossy_lld = (
            "# LLD\n\n## 3. Requirements\n\nThe dial samples on a window.\n"
            "\n## 10 Test Plan\n\n| ID | Requirement |\n|----|----|\n"
            "| S1 | sample the mirror band |\n"
        )
        errors = validate_assertion_literal_conservation(ISSUE_BODY, lossy_lld)

        assert errors
        assert any("0.12" in e.message for e in errors), [
            e.message for e in errors
        ]

    def test_it_passes_an_injected_lld(self, lld: str) -> None:
        assert validate_assertion_literal_conservation(ISSUE_BODY, lld) == []

    def test_it_has_exactly_one_production_call_site(self) -> None:
        """The decision, made durable. If someone wires a second call site --
        at the spec stage or anywhere else -- this fails and they read the
        docstring above before proceeding."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        # The FILE, not the line: pinning a line number would fail on any edit
        # above it, and a check that cries wolf is one people wave through.
        call_files = set()
        for path in (root / "assemblyzero").rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if "validate_assertion_literal_conservation(" not in line:
                    continue
                if line.lstrip().startswith("def "):
                    continue
                call_files.add(path.relative_to(root).as_posix())

        assert call_files == {
            "assemblyzero/workflows/requirements/nodes/validate_mechanical.py"
        }, (
            f"the conservation gate is called from {sorted(call_files)}. #2617 "
            f"ruled it belongs at the lld stage only: at the spec stage "
            f"injected rows make it redundant and non-injected content makes "
            f"its complaint unaddressable. Read this module's docstring before "
            f"adding a call site."
        )

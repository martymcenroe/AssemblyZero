"""The LLD's decision table reaches the spec by code, not by drafter (#2611).

The spec-side half of #2607. Source of truth is the LLD's injected block --
each stage derives from its immediate upstream settled artifact and never
reaches around it to the issue -- so these fixtures build a real post-#2607
LLD and derive from that.

The controls matter as much as the assertions here. An injector that always
injects and a conservation gate that never fires both look like green tests
if only the happy path is asserted, so every guarantee is paired with the
fixture that breaks it.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.implementation_spec import table_injection as spec_inject
from assemblyzero.workflows.requirements import table_injection as lld_inject
from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
    validate_assertion_literal_conservation,
)

SOURCE_TABLE = """\
| ID | Criterion | Binding value (quoted) | Assertion method |
|----|-----------|------------------------|------------------|
| S1 | sampling window | sampled ONLY at 0.12 R-0.25 R either side | probe at 0.12 R; probe at 0.25 R |
| S7 | redline colour | #AA0F19 | sample band mid at 75% |
| S9 | needle tip | 0.82 R | measure tip radius |
"""

ISSUE_BODY = f"# Dial\n\n## Pass criteria\n\n{SOURCE_TABLE}"

SPEC_DRAFT = """\
# Implementation Spec: Dial

## 1. Overview

Render the dial.

## 9. Placeholder

Nothing here.

## 10. Test Mapping

- `test_band_mid` covers S7.

## 11. Implementation Notes

Done.
"""


@pytest.fixture
def lld() -> str:
    """A real post-#2607 LLD: drafter prose plus the machine-owned block."""
    draft = "# LLD\n\n## 3. Requirements\n\nThe dial samples on a window.\n"
    return lld_inject.apply_injection(
        draft, lld_inject.build_injection(ISSUE_BODY)
    )


class TestTheChainIsLldToSpec:
    def test_the_lld_fixture_really_carries_the_block(self, lld: str) -> None:
        """Guard the fixture: everything below is vacuous without this."""
        assert lld_inject.has_injection(lld)
        assert "0.12 R-0.25 R" in lld

    def test_the_spec_block_is_byte_identical_to_the_lld_block(
        self, lld: str
    ) -> None:
        """Verbatim means sliced, never re-rendered. Padding, spacing and
        unicode survive because nothing round-trips through parsed cells."""
        injection = spec_inject.build_injection(lld)

        for line in SOURCE_TABLE.strip().splitlines():
            assert line in injection

    def test_it_derives_from_the_lld_not_the_issue(self, lld: str) -> None:
        """The ruling, as a behaviour: damage the LLD's block and the spec's
        injection follows the LLD down rather than silently healing from the
        issue. Reaching around the LLD would hide the damage."""
        damaged = lld.replace("0.12 R-0.25 R either side", "a window")

        injection = spec_inject.build_injection(damaged)

        assert "0.12 R-0.25 R" not in injection
        assert "a window" in injection

    def test_only_the_machine_owned_block_is_authoritative(self, lld: str) -> None:
        """A drafter-written restatement elsewhere in the LLD is not a second
        source of truth."""
        restated = lld + "\n\n## 10. Test Plan\n\n" + SOURCE_TABLE.replace(
            "0.82 R", "0.99 R"
        )

        injection = spec_inject.build_injection(restated)

        assert "0.82 R" in injection
        assert "0.99 R" not in injection

    def test_a_pre_2607_lld_falls_back_to_its_own_tables(self) -> None:
        """An LLD drawn before the fence existed still binds the spec."""
        old = f"# LLD\n\n## 3. Requirements\n\n{SOURCE_TABLE}"
        assert not lld_inject.has_injection(old)

        injection = spec_inject.build_injection(old)

        assert "#AA0F19" in injection


class TestNotApplicableIsNotFailure:
    def test_a_prose_only_lld_injects_nothing(self) -> None:
        """The control: most issues have no decision table and must derive
        exactly as they did before this module existed."""
        assert spec_inject.build_injection("# LLD\n\nJust prose.\n") == ""

    def test_an_empty_lld_injects_nothing(self) -> None:
        assert spec_inject.build_injection("") == ""

    def test_reassert_leaves_the_draft_alone_when_nothing_applies(self) -> None:
        text, changed = spec_inject.reassert(SPEC_DRAFT, "# LLD\n\nProse.\n")
        assert text == SPEC_DRAFT
        assert changed is False


class TestMachineOwnership:
    def test_a_revision_cannot_modify_an_injected_row(self, lld: str) -> None:
        """The acceptance. A drafter edits a binding value inside the block;
        re-assertion restores it without adjudicating anything."""
        injected = spec_inject.apply_injection(
            SPEC_DRAFT, spec_inject.build_injection(lld)
        )
        tampered = injected.replace("#AA0F19", "#000000")
        assert "#000000" in tampered

        restored, changed = spec_inject.reassert(tampered, lld)

        assert changed is True
        assert "#AA0F19" in restored
        assert "#000000" not in restored

    def test_a_deleted_block_is_reinstated(self, lld: str) -> None:
        injected = spec_inject.apply_injection(
            SPEC_DRAFT, spec_inject.build_injection(lld)
        )
        gutted = spec_inject.strip_injection(injected)
        assert not spec_inject.has_injection(gutted)

        restored, changed = spec_inject.reassert(gutted, lld)

        assert changed is True
        assert spec_inject.has_injection(restored)

    def test_reassert_is_idempotent(self, lld: str) -> None:
        once, first = spec_inject.reassert(SPEC_DRAFT, lld)
        twice, second = spec_inject.reassert(once, lld)

        assert first is True
        assert second is False, "a settled block must not be rewritten"
        assert once == twice

    def test_repeated_cycles_do_not_duplicate_the_block(self, lld: str) -> None:
        text = SPEC_DRAFT
        for _ in range(4):
            text, _ = spec_inject.reassert(text, lld)

        assert text.count(spec_inject.BEGIN_MARKER) == 1
        assert text.count(spec_inject.END_MARKER) == 1

    def test_a_block_copied_from_the_lld_is_replaced_not_duplicated(
        self, lld: str
    ) -> None:
        """The drafter reads the LLD, so imitation puts an LLD-shaped block in
        the spec. Reusing #2607's fence means it is found rather than left
        beside a second block under a different name."""
        copied = SPEC_DRAFT + "\n" + lld_inject.build_injection(ISSUE_BODY) + "\n"

        restored, _ = spec_inject.reassert(copied, lld)

        assert restored.count(spec_inject.BEGIN_MARKER) == 1

    def test_repeated_strip_does_not_accumulate_whitespace(self, lld: str) -> None:
        text = SPEC_DRAFT
        for _ in range(3):
            text = spec_inject.apply_injection(
                text, spec_inject.build_injection(lld)
            )
        assert "\n\n\n" not in text


class TestPlacement:
    def test_the_block_lands_above_test_mapping(self, lld: str) -> None:
        """The assertions that must agree with these values are right below."""
        injected = spec_inject.apply_injection(
            SPEC_DRAFT, spec_inject.build_injection(lld)
        )
        lines = injected.splitlines()
        marker = next(
            i for i, line in enumerate(lines)
            if spec_inject.BEGIN_MARKER in line
        )
        mapping = next(
            i for i, line in enumerate(lines)
            if line.strip().startswith("## 10.")
        )
        assert marker < mapping

    def test_a_spec_without_test_mapping_appends(self, lld: str) -> None:
        """Placement is for the reader; a fallback that appends is correct
        rather than degraded, because every consumer finds a table anywhere."""
        stub = "# Spec\n\n## 1. Overview\n\nNo mapping section.\n"

        injected = spec_inject.apply_injection(
            stub, spec_inject.build_injection(lld)
        )

        assert spec_inject.has_injection(injected)
        assert "## 1. Overview" in injected

    def test_the_drafters_own_prose_survives(self, lld: str) -> None:
        injected = spec_inject.apply_injection(
            SPEC_DRAFT, spec_inject.build_injection(lld)
        )
        for line in ("Render the dial.", "`test_band_mid` covers S7.", "Done."):
            assert line in injected


class TestConservationGateIsSatisfiedOnInjectedRows:
    """#2563 as the backstop, with the control that proves it still fires.

    The gate is generic in shape -- (source document, derived document) -- so
    driving it with (LLD, spec) asks the spec-stage question. Asserting only
    "zero errors" would pass against a gate that had silently stopped working,
    which is why the lossy fixture below is not optional.
    """

    def test_an_injected_spec_sheds_no_literals(self, lld: str) -> None:
        injected = spec_inject.apply_injection(
            SPEC_DRAFT, spec_inject.build_injection(lld)
        )

        errors = validate_assertion_literal_conservation(lld, injected)

        assert errors == [], [e.message for e in errors]

    def test_the_gate_still_fires_on_a_lossy_spec(self, lld: str) -> None:
        """The control. Without injection the drafter's spec sheds the #361
        sampling window -- the founding case -- and the gate must say so."""
        lossy = SPEC_DRAFT  # never injected, restates nothing

        errors = validate_assertion_literal_conservation(lld, lossy)

        assert errors, "the gate must fire on a spec that carries no literals"
        assert any("0.12" in e.message for e in errors), [
            e.message for e in errors
        ]

    def test_the_gate_fires_when_one_row_is_shed(self, lld: str) -> None:
        """Sharper control: a spec that carries most literals but drops one."""
        injected = spec_inject.apply_injection(
            SPEC_DRAFT, spec_inject.build_injection(lld)
        )
        shed = injected.replace("0.82 R", "the ruled radius")

        errors = validate_assertion_literal_conservation(lld, shed)

        assert errors
        assert any("0.82" in e.message for e in errors), [
            e.message for e in errors
        ]


class TestTheDrafterIsTold:
    def test_the_notice_appears_when_a_table_is_injected(self, lld: str) -> None:
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            DRAFTER_SYSTEM_PROMPT,
            _drafter_system_prompt,
        )

        prompt = _drafter_system_prompt(lld)

        assert "DO NOT RESTATE THE LLD'S DECISION TABLE" in prompt
        assert spec_inject.BEGIN_MARKER in prompt
        assert prompt.startswith(DRAFTER_SYSTEM_PROMPT)

    def test_the_notice_is_absent_for_a_prose_only_lld(self) -> None:
        """The control: a prose-only LLD must produce the unchanged prompt,
        so a notice about a block that does not exist never confuses a
        drafter."""
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            DRAFTER_SYSTEM_PROMPT,
            _drafter_system_prompt,
        )

        assert _drafter_system_prompt("# LLD\n\nProse.\n") == DRAFTER_SYSTEM_PROMPT

    def test_an_empty_lld_produces_the_unchanged_prompt(self) -> None:
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            DRAFTER_SYSTEM_PROMPT,
            _drafter_system_prompt,
        )

        assert _drafter_system_prompt("") == DRAFTER_SYSTEM_PROMPT


class TestNoImportCycle:
    """The entry path that starts in the requirements workflow must import.

    `requirements.table_injection` imports `implementation_spec.assertion_manifest`
    for `is_criteria_table`, which pulls in that package's `__init__` -> `graph`
    -> `nodes/__init__` -> `generate_spec`. A module-level import from there back
    into `requirements.table_injection` re-enters it mid-initialisation and dies
    with a partially-initialised module.

    This failed for exactly that reason during development, and only on the
    requirements entry path -- importing the two modules directly, as the tests
    above do, hides it completely. Purging the participants and importing in the
    order that breaks is what makes this a real check rather than a restatement
    of whatever is already in `sys.modules`.
    """

    def test_the_requirements_entry_path_imports(self) -> None:
        """In a SUBPROCESS, because the cycle only appears on a first import.

        Purging `sys.modules` in-process to force that ordering re-executes the
        modules, so later monkeypatching targets a different module object than
        the code under test. That broke `test_step_budget.py` and
        `test_stage_verdict_is_explicit.py` when this test first did it --
        measured, not theorised, which is why the isolation is a process.
        """
        import subprocess
        import sys
        from pathlib import Path

        script = (
            Path(__file__).resolve().parents[1]
            / "fixtures" / "import_requirements_entry_path.py"
        )
        assert script.is_file(), f"missing fixture script: {script}"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(Path(__file__).resolve().parents[2]),
            timeout=180,
        )

        assert result.returncode == 0, (
            f"the requirements entry path failed to import:\n{result.stderr}"
        )

    def test_generate_spec_holds_no_module_level_spec_injection_import(
        self
    ) -> None:
        """The specific shape that broke, pinned so a tidy-up cannot restore
        it silently."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "assemblyzero" / "workflows" / "implementation_spec"
            / "nodes" / "generate_spec.py"
        ).read_text(encoding="utf-8")

        for line in source.splitlines():
            if line.startswith(("import ", "from ")):
                assert "table_injection" not in line, (
                    f"module-level import re-creates the cycle: {line!r}"
                )


class TestCurrentBlock:
    def test_it_reads_the_block_back(self, lld: str) -> None:
        injection = spec_inject.build_injection(lld)
        injected = spec_inject.apply_injection(SPEC_DRAFT, injection)

        assert spec_inject.current_block(injected) == injection

    def test_no_block_reads_as_empty(self) -> None:
        assert spec_inject.current_block(SPEC_DRAFT) == ""

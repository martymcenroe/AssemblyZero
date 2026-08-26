"""The assertion manifest: compile before the drafter, gate before the spend (#2533).

The decision-table shapes here are distilled from boostgauge #332's needle and
telltale tables — the first consumer — including the live cross-document
conflict the first real compile found: the issue's N4 row cites a hex the
2026-08-25 crimson ruling removed from the contract. Fail closed means that
conflict halts with a must-resolve BEFORE any draft spend, never a fall-through.
"""

from __future__ import annotations


from assemblyzero.workflows.implementation_spec.assertion_manifest import (
    compile_manifest,
    extract_literals,
    gate_findings,
    placeholder_words_in,
    render_manifest,
)
from assemblyzero.workflows.implementation_spec.nodes.compile_manifest import (
    compile_assertion_manifest,
    manifest_gate,
)
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_manifest_traceability,
)

CONTRACT = """# Contract

### Palette

| Element | Name | RGB | Hex |
|---|---|---|---|
| Main needle | candy-apple red | (247, 57, 35) | `#F73923` |
| Redline band | crimson | (170, 15, 25) | `#AA0F19` |
"""

GOOD_LLD = """# LLD

## Decision table — needle criteria

| ID | Criterion | Binding value (quoted) | Assertion method |
|---|---|---|---|
| N1 | Axis at value 0 | 225.0° | tip pixel classifies `#F73923` at (0.86 R, 225°); face-black at (0.86 R, 90°) |
| N6 | Glow presence | at 0.04 R perpendicular: R ≥ 180 | predicate per the measured table |
| T1 | None-not-drawn | a None peak renders nothing | recording of samples: no telltale-family pixel present |
"""

STALE_HEX_LLD = """# LLD

## Decision table

| ID | Criterion | Binding value (quoted) | Assertion method |
|---|---|---|---|
| N4 | Tip-in-band | tip 0.86 R | sample inside tip → nearest entry `#F73923`; band sample → nearest entry `#9B3020` |
"""

ADJECTIVAL_LLD = """# LLD

## Decision table

| ID | Criterion | Binding value (quoted) | Assertion method |
|---|---|---|---|
| A1 | Band opacity | approximately 60-70% opacity | looks right |
"""

NO_LITERAL_LLD = """# LLD

## Decision table

| ID | Criterion | Binding value (quoted) | Assertion method |
|---|---|---|---|
| B1 | Needle look | luminescent candy-apple | verify the needle looks luminescent |
"""


class TestLiteralExtraction:
    def test_the_literal_classes(self):
        text = (
            "#F73923 and (247, 57, 35) at 225.0° and 0.86 R, alpha 166, "
            "65%, 2 px, R ≥ 180"
        )
        literals = extract_literals(text)
        for expected in ("#F73923", "(247, 57, 35)", "0.86 R", "alpha 166",
                         "65%", "2 px", "R ≥ 180"):
            assert expected in literals, literals

    def test_absence_is_a_literal_expectation(self):
        """#332's T1: 'renders nothing' is exact, not adjectival — halting on
        it would be the false alarm the fleet rule forbids."""
        assert extract_literals("a None peak renders nothing")
        assert extract_literals("no telltale-family pixel present")
        assert extract_literals("identical to the bare face")

    def test_adjectives_are_not_literals(self):
        assert extract_literals("luminescent candy-apple red glow") == []

    def test_placeholder_words(self):
        assert placeholder_words_in("approximately 60%") == ["approximately"]
        assert placeholder_words_in("225.0°") == []


class TestCompile:
    def test_not_applicable_without_a_decision_table(self):
        result = compile_manifest("# LLD\n\nProse only.\n", CONTRACT)
        assert result.applicable is False

    def test_a_clean_table_compiles_one_row_per_fragment(self):
        result = compile_manifest(GOOD_LLD, CONTRACT)
        assert result.applicable and not result.failures
        ids = [r.row_id for r in result.rows]
        # N1's method has two fragments; N6 and T1 one each.
        assert ids == ["N1.1", "N1.2", "N6.1", "T1.1"]
        n1 = result.rows[0]
        assert "#F73923" in n1.expected
        assert n1.sample_point.startswith("tip pixel classifies")

    def test_a_hex_the_contract_does_not_carry_fails_closed(self):
        """The live find: #332's N4 cites #9B3020, removed by the crimson
        ruling. The compiler catches the disagreement in seconds, for free."""
        result = compile_manifest(STALE_HEX_LLD, CONTRACT)
        [failure] = result.failures
        assert failure.criterion_id == "N4"
        assert "#9B3020" in failure.reason

    def test_placeholder_wording_fails_closed(self):
        result = compile_manifest(ADJECTIVAL_LLD, CONTRACT)
        [failure] = result.failures
        assert failure.criterion_id == "A1"
        assert "placeholder" in failure.reason

    def test_no_literal_anywhere_fails_closed(self):
        result = compile_manifest(NO_LITERAL_LLD, CONTRACT)
        [failure] = result.failures
        assert failure.criterion_id == "B1"
        assert "no literal" in failure.reason

    def test_duplicate_ids_with_different_content_contradict(self):
        lld = GOOD_LLD + (
            "| N1 | Axis at value 0 | 226.0° | different |\n"
        )
        result = compile_manifest(lld, CONTRACT)
        assert any(
            f.criterion_id == "N1" and "contradict" in f.reason
            for f in result.failures
        )

    def test_no_contract_means_no_hex_crosscheck_and_says_nothing_false(self):
        """Without a contract the hex universe is unknowable — unknown is
        not guilty (#2526), so the stale hex compiles rather than flags."""
        result = compile_manifest(STALE_HEX_LLD, contract_text="")
        assert not result.failures


class TestTheGate:
    def test_a_clean_manifest_passes(self):
        result = compile_manifest(GOOD_LLD, CONTRACT)
        assert gate_findings(result) == []

    def test_an_uncovered_criterion_is_a_finding(self):
        from assemblyzero.workflows.implementation_spec.assertion_manifest import (
            CompileResult,
        )

        result = compile_manifest(GOOD_LLD, CONTRACT)
        weakened = CompileResult(
            applicable=True,
            rows=result.rows[:-1],  # drop T1's only row
            criteria_ids=result.criteria_ids,
        )
        findings = gate_findings(weakened)
        assert any("T1" in f and "no manifest row" in f for f in findings)


class TestTheCompileNode:
    def _state(self, lld: str, **kw) -> dict:
        return {
            "lld_content": lld,
            "repo_root": "",
            "issue_number": 332,
            "config_mock_mode": False,
            **kw,
        }

    def test_uncompilable_halts_and_files_the_must_resolve(self):
        """Fail closed, the N0c path: the halt carries the defect and a
        must-resolve is filed per uncompilable criterion."""
        filings: list[tuple] = []

        def filer(repo_root, issue, conflict, **kwargs):
            filings.append((issue, conflict))

        out = compile_assertion_manifest(
            self._state(NO_LITERAL_LLD), filer=filer
        )
        assert "UNCOMPILABLE" in out["error_message"].upper()
        assert "must-resolve" in out["error_message"]
        assert out["assertion_manifest"] == ""
        [(issue, conflict)] = filings
        assert issue == 332
        assert "B1" in conflict["diverging_situation"]

    def test_a_filing_failure_never_masks_the_halt(self):
        def broken_filer(*args, **kwargs):
            raise OSError("no gh")

        out = compile_assertion_manifest(
            self._state(NO_LITERAL_LLD), filer=broken_filer
        )
        assert "UNCOMPILABLE" in out["error_message"].upper()

    def test_not_applicable_is_not_failure(self):
        out = compile_assertion_manifest(self._state("# LLD\n\nProse.\n"))
        assert out["error_message"] == ""
        assert out["assertion_manifest"] == ""

    def test_a_clean_compile_emits_the_binding_manifest(self, tmp_path):
        out = compile_assertion_manifest(
            self._state(GOOD_LLD, audit_dir=str(tmp_path))
        )
        assert out["error_message"] == ""
        assert "| N1.1 |" in out["assertion_manifest"]
        assert [r["row_id"] for r in out["assertion_manifest_rows"]] == [
            "N1.1", "N1.2", "N6.1", "T1.1",
        ]
        assert out["assertion_manifest_criteria"] == ["N1", "N6", "T1"]
        persisted = list(tmp_path.glob("*-assertion-manifest.md"))
        assert len(persisted) == 1, "the manifest is a lineage artifact"

    def test_the_gate_node_passes_a_clean_manifest(self, tmp_path):
        out = compile_assertion_manifest(
            self._state(GOOD_LLD, audit_dir=str(tmp_path))
        )
        gate_out = manifest_gate({**self._state(GOOD_LLD), **out})
        assert gate_out["error_message"] == ""

    def test_the_gate_node_halts_on_a_broken_manifest(self):
        gate_out = manifest_gate({
            "assertion_manifest": "| bad |",
            "assertion_manifest_rows": [
                {"row_id": "N1.1", "criterion_id": "N1",
                 "sample_point": "x", "expected": "looks nice"},
            ],
            "assertion_manifest_criteria": ["N1", "N2"],
        })
        assert "MANIFEST GATE" in gate_out["error_message"]


def _spec_with_tests(*bodies: str) -> str:
    fences = "\n\n".join(f"```python\n{b}\n```" for b in bodies)
    return f"# Spec\n\n{fences}\n"


ROWS = [
    {"row_id": "N1.1", "criterion_id": "N1"},
    {"row_id": "N1.2", "criterion_id": "N1"},
]


class TestTraceability:
    """The mechanical diff, both directions, plus the abstention path."""

    def test_balanced_passes(self):
        spec = _spec_with_tests(
            "def test_axis_tip():\n    # manifest: N1.1\n    assert True\n",
            "def test_axis_offside():\n    # manifest: N1.2\n    assert True\n",
        )
        result = check_manifest_traceability(spec, ROWS)
        assert result["passed"] is True, result["details"]

    def test_a_missing_row_fails_the_diff(self):
        spec = _spec_with_tests(
            "def test_axis_tip():\n    # manifest: N1.1\n    assert True\n",
        )
        result = check_manifest_traceability(spec, ROWS)
        assert result["passed"] is False
        assert "N1.2" in result["details"]
        assert "NO test" in result["details"]

    def test_an_uncited_test_fails_the_diff(self):
        spec = _spec_with_tests(
            "def test_axis_tip():\n    # manifest: N1.1\n    assert True\n",
            "def test_axis_offside():\n    # manifest: N1.2\n    assert True\n",
            "def test_invented_extra():\n    assert True\n",
        )
        result = check_manifest_traceability(spec, ROWS)
        assert result["passed"] is False
        assert "test_invented_extra" in result["details"]

    def test_a_row_in_two_tests_fails_the_diff(self):
        spec = _spec_with_tests(
            "def test_a():\n    # manifest: N1.1\n    assert True\n",
            "def test_b():\n    # manifest: N1.1\n    assert True\n",
            "def test_c():\n    # manifest: N1.2\n    assert True\n",
        )
        result = check_manifest_traceability(spec, ROWS)
        assert result["passed"] is False
        assert "MORE than one" in result["details"]

    def test_an_unparseable_fence_abstains_and_says_so(self):
        """#2526: unknown is not guilty. The broken fence is the api-symbols
        check's finding (#2392); this check does not judge what it could not
        read, and it says how much that was."""
        spec = (
            "# Spec\n\n```python\ndef test_axis_tip():\n"
            "    # manifest: N1.1\n    assert True\n```\n\n"
            "```python\ndef broken(:\n```\n\n"
            "```python\ndef test_axis_offside():\n"
            "    # manifest: N1.2\n    assert True\n```\n"
        )
        result = check_manifest_traceability(spec, ROWS)
        assert result["passed"] is True, result["details"]
        assert "not judged" in result["details"]
        assert "abstained" in result["details"]

    def test_no_manifest_means_not_applicable(self):
        result = check_manifest_traceability("# Spec\n", [])
        assert result["passed"] is True
        assert "not applicable" in result["details"].lower()

    def test_no_tests_at_all_is_a_gap_not_an_abstention(self):
        result = check_manifest_traceability("# Spec\n\nProse only.\n", ROWS)
        assert result["passed"] is False
        assert "no parseable test functions" in result["details"]


class TestDrafterBinding:
    def test_the_manifest_reaches_the_initial_prompt_as_binding(self):
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            build_drafter_prompt,
        )

        manifest = render_manifest(compile_manifest(GOOD_LLD, CONTRACT))
        prompt = build_drafter_prompt(
            lld_content=GOOD_LLD, current_state={}, patterns=[],
            assertion_manifest=manifest,
        )
        assert "ASSERTION MANIFEST (BINDING)" in prompt
        assert "| N1.1 |" in prompt
        assert "# manifest:" in prompt  # the citation convention is stated

    def test_the_manifest_reaches_the_revision_prompt_too(self):
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            build_drafter_prompt,
        )

        manifest = render_manifest(compile_manifest(GOOD_LLD, CONTRACT))
        prompt = build_drafter_prompt(
            lld_content=GOOD_LLD, current_state={}, patterns=[],
            existing_draft="# Spec\n\nold\n",
            review_feedback="fix the axis test",
            assertion_manifest=manifest,
        )
        assert "ASSERTION MANIFEST (BINDING)" in prompt

    def test_an_empty_manifest_leaves_the_prompt_unchanged(self):
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            build_drafter_prompt,
        )

        prompt = build_drafter_prompt(
            lld_content=GOOD_LLD, current_state={}, patterns=[],
        )
        assert "ASSERTION MANIFEST" not in prompt

"""Traceability spans the document's namespaces, not just the manifest's (#2633).

The observed case, as fixtures. boostgauge's `run-issue331-182658` spec stage
spent three revisions and hit the cap on:

    test(s) citing no manifest row: test_T010_base_face_generation,
    test_T020_minimum_size_threshold, test_T030_cache_persistence,
    test_T100_constant_isolation, test_T110_artifact_emission

**Those five tests each cited two identifiers.** The issue read them as
counterfeit near-misses invented under an impossible demand; the artifact says
otherwise, and `TestTheCitationsWereReal` proves it. `row 010`, `row 020`,
`row 030`, `row 100`, `row 110` are real rows of LLD-331's Test Scenarios
table -- exactly the five NON-visual scenarios, the ones for which no manifest
row can exist, because "cache persistence" has no sample point and never will.
Scenarios 040-090, the visual ones, the drafter cited by manifest row instead.

So the drafter partitioned the LLD's eleven scenarios perfectly and the check
knew one namespace of three. The class-3 lesson here is not that drafters
counterfeit under pressure; it is that **a check whose domain is narrower than
the document's own identifier namespace reports correct work as absent, and
its message blames the author.**
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_manifest_traceability,
)

FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "manifest_traceability"
)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def spec() -> str:
    return _fixture("spec-331-009-draft.md")


@pytest.fixture
def lld() -> str:
    return _fixture("lld-331-passed.md")


@pytest.fixture
def rows() -> list[dict]:
    """The manifest as the node receives it: compiled row ids."""
    text = _fixture("manifest-331.md")
    return [
        {"row_id": m.group(1)}
        for line in text.splitlines()
        if (m := re.match(r"^\|\s*(S[\d.]+)\s*\|", line))
    ]


#: An LLD with a criteria table but no numbered requirements and no scenario
#: table -- the control for "the namespaces come from the LLD, not from thin
#: air".
BARE_LLD = "# LLD\n\n## 3. Requirements\n\nProse only, no numbered items.\n"


def _spec_with(*tests: str) -> str:
    body = "\n\n".join(tests)
    return f"# Spec\n\n## 10. Test Mapping\n\n```python\n{body}\n```\n"


class TestTheCitationsWereReal:
    """The refutation, as a measurement rather than a claim."""

    def test_every_numeric_citation_is_a_real_lld_scenario(
        self, spec: str, lld: str
    ) -> None:
        cited = [
            m.group(1)
            for m in re.finditer(r"#\s*manifest:\s*row\s+(\d{3})", spec)
        ]
        scenarios = set(re.findall(r"(?m)^\|\s*(\d{3})\s*\|", lld))

        assert cited == ["010", "020", "030", "100", "110"]
        assert set(cited).issubset(scenarios), (
            "these were read as fabrications; they are LLD scenario ids"
        )

    def test_they_are_exactly_the_non_visual_scenarios(
        self, spec: str, lld: str
    ) -> None:
        """The five with no manifest row, and only those."""
        cited = set(re.findall(r"#\s*manifest:\s*row\s+(\d{3})", spec))
        scenarios = set(re.findall(r"(?m)^\|\s*(\d{3})\s*\|", lld))

        assert scenarios - cited == {"040", "050", "060", "070", "080", "090"}

    def test_every_req_citation_is_a_real_lld_requirement(
        self, spec: str, lld: str
    ) -> None:
        from assemblyzero.core.validation.test_plan_validator import (
            extract_requirements,
        )

        cited = set(re.findall(r"#\s*manifest:\s*(REQ-\d+)", spec))
        real = {r["id"] for r in extract_requirements(lld)}

        assert cited == {f"REQ-{n}" for n in range(1, 10)}
        assert cited.issubset(real)

    def test_every_manifest_row_was_already_cited(
        self, spec: str, rows: list[dict]
    ) -> None:
        """The row-to-test direction never failed here -- only test-to-row."""
        for row in rows:
            assert row["row_id"] in spec


class TestTheObservedCaseBalances:
    def test_the_009_draft_passes_unmodified(
        self, spec: str, rows: list[dict], lld: str
    ) -> None:
        """The acceptance, and better than it asked.

        It allowed for the fabricated citations to be replaced first. They are
        not fabrications, so nothing is replaced: the draft as it actually
        halted now balances.
        """
        result = check_manifest_traceability(spec, rows, lld)

        assert result["passed"] is True, result["details"]

    def test_the_fixture_is_the_artifact_that_halted(
        self, spec: str, rows: list[dict]
    ) -> None:
        """Guard: without the LLD this must still fail, or the test above is
        passing for the wrong reason."""
        result = check_manifest_traceability(spec, rows, "")

        assert result["passed"] is False
        assert "test_T010_base_face_generation" in result["details"]

    def test_it_reports_what_it_verified(
        self, spec: str, rows: list[dict], lld: str
    ) -> None:
        details = check_manifest_traceability(spec, rows, lld)["details"]
        assert "10 manifest row(s)" in details
        assert "11 test(s)" in details


class TestAnInvalidCitationIsNamed:
    """#2555: a complaint must name something the draft contains."""

    def test_a_test_citing_only_a_fabricated_id_fails(self, lld: str) -> None:
        spec = _spec_with(
            "def test_alpha():\n    # manifest: S1.1\n    pass",
            "def test_beta():\n    # manifest: row 999\n    pass",
        )
        result = check_manifest_traceability(spec, [{"row_id": "S1.1"}], lld)

        assert result["passed"] is False
        assert "test_beta" in result["details"]

    def test_the_invalid_citation_is_quoted_back(self, lld: str) -> None:
        spec = _spec_with(
            "def test_alpha():\n    # manifest: S1.1\n    pass",
            "def test_beta():\n    # manifest: row 999\n    pass",
        )
        details = check_manifest_traceability(
            spec, [{"row_id": "S1.1"}], lld
        )["details"]

        assert "'row 999'" in details, details

    def test_all_three_namespaces_are_enumerated(self, lld: str) -> None:
        spec = _spec_with(
            "def test_alpha():\n    # manifest: S1.1\n    pass",
            "def test_beta():\n    # manifest: row 999\n    pass",
        )
        details = check_manifest_traceability(
            spec, [{"row_id": "S1.1"}], lld
        )["details"]

        assert "manifest rows are" in details
        assert "LLD requirements are" in details
        assert "LLD test-scenario ids are" in details

    def test_a_test_citing_nothing_at_all_still_fails(self, lld: str) -> None:
        spec = _spec_with(
            "def test_alpha():\n    # manifest: S1.1\n    pass",
            "def test_beta():\n    pass",
        )
        result = check_manifest_traceability(spec, [{"row_id": "S1.1"}], lld)

        assert result["passed"] is False
        assert "tracing to nothing" in result["details"]
        assert "test_beta" in result["details"]


class TestAValidCitationWins:
    def test_a_requirement_citation_traces(self, lld: str) -> None:
        spec = _spec_with(
            "def test_alpha():\n    # manifest: S1.1\n    pass",
            "def test_beta():\n    # manifest: REQ-2\n    pass",
        )
        assert check_manifest_traceability(
            spec, [{"row_id": "S1.1"}], lld
        )["passed"] is True

    def test_a_scenario_citation_traces(self, lld: str) -> None:
        spec = _spec_with(
            "def test_alpha():\n    # manifest: S1.1\n    pass",
            "def test_beta():\n    # manifest: row 030\n    pass",
        )
        assert check_manifest_traceability(
            spec, [{"row_id": "S1.1"}], lld
        )["passed"] is True

    def test_a_bare_scenario_id_traces(self, lld: str) -> None:
        """`row 010` and `010` are the same citation."""
        spec = _spec_with(
            "def test_alpha():\n    # manifest: S1.1\n    pass",
            "def test_beta():\n    # manifest: 030\n    pass",
        )
        assert check_manifest_traceability(
            spec, [{"row_id": "S1.1"}], lld
        )["passed"] is True

    def test_an_unrecognised_extra_is_reported_but_not_fatal(
        self, lld: str
    ) -> None:
        """Failing a correctly-traced test over a redundant annotation is the
        false-alarm disease #2540 removed."""
        spec = _spec_with(
            "def test_alpha():\n    # manifest: S1.1\n    pass",
            "def test_beta():\n    # manifest: REQ-2\n    # manifest: row 999\n"
            "    pass",
        )
        result = check_manifest_traceability(spec, [{"row_id": "S1.1"}], lld)

        assert result["passed"] is True
        assert "row 999" in result["details"]
        assert "not fatal" in result["details"]


class TestTheRowDirectionIsUntouched:
    """The half that catches real gaps. Nothing here loosens it."""

    def test_an_uncited_manifest_row_still_fails(self, lld: str) -> None:
        spec = _spec_with("def test_alpha():\n    # manifest: REQ-1\n    pass")
        result = check_manifest_traceability(
            spec, [{"row_id": "S1.1"}, {"row_id": "S2.1"}], lld
        )

        assert result["passed"] is False
        assert "cited by NO test" in result["details"]
        assert "S1.1" in result["details"]

    def test_a_row_cited_twice_still_fails(self, lld: str) -> None:
        spec = _spec_with(
            "def test_alpha():\n    # manifest: S1.1\n    pass",
            "def test_beta():\n    # manifest: S1.1\n    pass",
        )
        result = check_manifest_traceability(spec, [{"row_id": "S1.1"}], lld)

        assert result["passed"] is False
        assert "MORE than one test" in result["details"]

    def test_a_requirement_citation_cannot_substitute_for_a_row(
        self, lld: str
    ) -> None:
        """The sharpest control: widening the TEST side must not let a
        manifest row go untested."""
        spec = _spec_with(
            "def test_alpha():\n    # manifest: REQ-1\n    pass",
            "def test_beta():\n    # manifest: REQ-2\n    pass",
        )
        result = check_manifest_traceability(spec, [{"row_id": "S1.1"}], lld)

        assert result["passed"] is False
        assert "S1.1" in result["details"]


class TestNotApplicableIsUnchanged:
    """#2608's declared-abstain regime, undisturbed."""

    def test_no_manifest_is_not_applicable(self, lld: str) -> None:
        result = check_manifest_traceability("# Spec\n", [], lld)

        assert result["passed"] is True
        assert "not applicable" in result["details"]

    def test_no_manifest_is_not_applicable_without_an_lld_either(self) -> None:
        result = check_manifest_traceability("# Spec\n", [], "")

        assert result["passed"] is True
        assert "not applicable" in result["details"]

    def test_a_binding_manifest_with_no_tests_is_a_real_gap(
        self, lld: str
    ) -> None:
        """Not applicable is not the same as nothing to check."""
        result = check_manifest_traceability(
            "# Spec\n\nNo fences.\n", [{"row_id": "S1.1"}], lld
        )

        assert result["passed"] is False
        assert "no parseable test functions" in result["details"]


class TestTheNamespacesComeFromTheLld:
    def test_a_bare_lld_supplies_no_extra_namespace(self) -> None:
        """The control for the whole fix: the widening is sourced from the
        LLD, never invented, so an LLD carrying neither requirements nor
        scenarios rejects exactly as before."""
        spec = _spec_with(
            "def test_alpha():\n    # manifest: S1.1\n    pass",
            "def test_beta():\n    # manifest: REQ-2\n    pass",
        )
        result = check_manifest_traceability(
            spec, [{"row_id": "S1.1"}], BARE_LLD
        )

        assert result["passed"] is False
        assert "test_beta" in result["details"]

    def test_the_namespace_list_omits_what_the_lld_lacks(self) -> None:
        spec = _spec_with("def test_beta():\n    # manifest: nonsense\n    pass")
        details = check_manifest_traceability(
            spec, [{"row_id": "S1.1"}], BARE_LLD
        )["details"]

        assert "manifest rows are" in details
        assert "LLD requirements are" not in details
        assert "LLD test-scenario ids are" not in details

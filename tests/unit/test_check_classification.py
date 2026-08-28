"""The completeness-check classification sweep (#2540).

Operator-ratified 2026-08-28: facts stay hard gates, proxies demote to advisory
whenever the adversarial review stage is engaged. This is the sweep as a
program -- it re-runs, it fails when a check joins the suite unclassified, and
it pins the guarantee the ruling is actually about: **no proxy-class check can
produce a cap halt while review is engaged.**

The evidence base is three deep and each instance cost a full roll:
`api_symbols_exist` on `str.isupper` (#2526), `change_instructions_specific` on
a fence-density off-by-one (#2539), and the same check's no-target complaint
(#2592).
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec.check_classification import (
    CLASSIFICATIONS,
    FACT,
    PROXY,
    advisory_details,
    classification_of,
    is_proxy,
)
# The MODULE, not the node function of the same name. `nodes/__init__` binds
# the attribute `validate_completeness` to the FUNCTION, and both `from ...
# import validate_completeness` and `import ....validate_completeness as vc`
# resolve through that attribute -- so both hand back the function. Only
# `import_module` reaches the module object itself.
vc = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
)

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "assemblyzero" / "workflows" / "implementation_spec"
    / "nodes" / "validate_completeness.py"
)


def emitted_check_names() -> set[str]:
    """Every `check_name=` the node can emit, read from its source.

    Read from source rather than listed here, so a check added tomorrow joins
    this set without anyone remembering to update a literal -- which is the
    only way the exhaustiveness test below can actually fail on a new check.
    """
    return set(
        re.findall(r'check_name="([a-z_]+)"', SOURCE.read_text(encoding="utf-8"))
    )


class TestTheSweepIsExhaustive:
    """The lint. Neither list may drift from the other."""

    def test_every_emitted_check_is_classified(self) -> None:
        unclassified = emitted_check_names() - set(CLASSIFICATIONS)
        assert not unclassified, (
            f"checks the sweep has never classified: {sorted(unclassified)}. "
            f"Add an entry to CLASSIFICATIONS with what it READS and why that "
            f"makes it a fact or a proxy."
        )

    def test_every_classification_names_a_real_check(self) -> None:
        """A phantom entry is worse than a missing one: it reads as coverage."""
        phantom = set(CLASSIFICATIONS) - emitted_check_names()
        assert not phantom, f"classified checks nothing emits: {sorted(phantom)}"

    def test_the_sweep_found_the_check_the_issue_did_not_list(self) -> None:
        """#2540 named eleven checks and said the code is authoritative. The
        twelfth is `python_fences_parse`, which reports under its own name
        since #2556 and appears in no issue list. The thirteenth is
        `function_spec_sections_have_examples`, built by #2620 as the path
        back to a hard gate."""
        assert "python_fences_parse" in CLASSIFICATIONS
        assert "function_spec_sections_have_examples" in CLASSIFICATIONS
        assert len(CLASSIFICATIONS) == 13

    @pytest.mark.parametrize("name", sorted(CLASSIFICATIONS))
    def test_each_entry_states_what_it_reads_and_why(self, name: str) -> None:
        entry = CLASSIFICATIONS[name]
        assert entry.kind in (FACT, PROXY)
        assert len(entry.reads) > 20, f"{name}: `reads` must be specific"
        assert len(entry.reason) > 40, f"{name}: `reason` must be specific"
        assert entry.check == name


class TestTheRuling:
    def test_facts_gate(self) -> None:
        for entry in CLASSIFICATIONS.values():
            if entry.kind == FACT:
                assert entry.gates
                assert not is_proxy(entry.check)

    def test_proxies_do_not_gate(self) -> None:
        proxies = {e.check for e in CLASSIFICATIONS.values() if e.kind == PROXY}
        assert proxies == {
            "change_instructions_specific",
            "modify_files_have_excerpts",
            "data_structures_have_examples",
            "functions_have_io_examples",
        }
        for name in proxies:
            assert is_proxy(name)
            assert not classification_of(name).gates

    def test_the_boundaries_the_operator_ruled(self) -> None:
        """#2620, 2026-08-28: **classification follows the implementation.**

        The earlier ruling on the #2590 work order classified this check's
        INTENTION and kept it gating; this one classifies the implementation
        that actually runs, and demotes it. The two disagree, and the
        implementation is what gates, so the implementation is what gets
        classified. The gate it held moves to the structural check built with
        the ruling.
        """
        assert classification_of("functions_have_io_examples").kind == PROXY
        assert classification_of("change_instructions_specific").kind == PROXY
        assert classification_of(
            "function_spec_sections_have_examples"
        ).kind == FACT

    def test_arguable_classifications_are_flagged_not_demoted(self) -> None:
        """Conservative where it is arguable: keep gating, record the tension.

        `functions_have_io_examples` left this set when #2620 ruled on it --
        a flag is for an open question, and that one is answered.
        """
        flagged = {e.check for e in CLASSIFICATIONS.values() if e.flagged}
        assert flagged == {"criteria_have_tests"}
        for name in flagged:
            assert classification_of(name).gates, (
                f"{name} is flagged as arguable and must stay GATING -- a "
                f"sweep does not demote on its own judgement"
            )

    def test_a_demoted_check_carries_no_stale_flag(self) -> None:
        """A ruled question must not keep advertising itself as open."""
        assert classification_of("functions_have_io_examples").flagged == ""

    def test_an_unclassified_name_is_never_demoted(self) -> None:
        """Forgetting to classify a check must not remove its gate."""
        assert is_proxy("a_check_nobody_classified") is False


class TestNoProxyCanCapHalt:
    """The guarantee #2540 asks to be pinned.

    A failing check enters `completeness_issues`, which makes
    `validation_passed` False, which routes back to N2 -- and at
    `max_iterations` routes to HALT. So "cannot produce a cap halt" is exactly
    "cannot enter `completeness_issues` while review is engaged".
    """

    def _failed(self, name: str) -> vc.CompletenessCheck:
        return vc.CompletenessCheck(
            check_name=name, passed=False, details=f"{name} failed"
        )

    @pytest.mark.parametrize(
        "name",
        sorted(e.check for e in CLASSIFICATIONS.values() if e.kind == PROXY),
    )
    def test_a_failing_proxy_stops_blocking(self, name: str) -> None:
        demoted = vc._demote_proxies(self._failed(name), review_engaged=True)
        assert demoted["passed"] is True

    @pytest.mark.parametrize(
        "name",
        sorted(e.check for e in CLASSIFICATIONS.values() if e.kind == FACT),
    )
    def test_a_failing_fact_still_blocks(self, name: str) -> None:
        """The control. Without it, a demoter that demoted everything would
        pass the test above."""
        kept = vc._demote_proxies(self._failed(name), review_engaged=True)
        assert kept["passed"] is False

    def test_the_demoted_check_carries_its_category(self) -> None:
        demoted = vc._demote_proxies(
            self._failed("change_instructions_specific"), review_engaged=True
        )
        assert "ADVISORY" in demoted["details"]
        assert "proxy-heuristic" in demoted["details"]
        assert "#2540" in demoted["details"]
        assert "change_instructions_specific failed" in demoted["details"]

    def test_a_passing_proxy_is_untouched(self) -> None:
        """Demotion must not disturb the pass/not-applicable accounting."""
        passing = vc.CompletenessCheck(
            check_name="change_instructions_specific",
            passed=True,
            details="not applicable",
        )
        assert vc._demote_proxies(passing, review_engaged=True) is passing

    def test_proxies_re_arm_when_no_reviewer_is_engaged(self) -> None:
        """The demotion's justification is that a better judge is about to
        look. Without one, a weak check beats no check."""
        armed = vc._demote_proxies(
            self._failed("change_instructions_specific"), review_engaged=False
        )
        assert armed["passed"] is False


class TestReviewIsReallyEngaged:
    """`review_is_engaged` returning True is a fact about this graph's routing.

    Read from the router rather than asserted, so the constant cannot quietly
    become a lie if a future branch skips N5.
    """

    def test_a_passing_draft_always_reaches_the_reviewer(self) -> None:
        from assemblyzero.workflows.implementation_spec.graph import (
            route_after_validation,
        )

        without_gate = route_after_validation(
            {"validation_passed": True, "human_gate_enabled": False}
        )
        with_gate = route_after_validation(
            {"validation_passed": True, "human_gate_enabled": True}
        )

        assert without_gate == "N5_review_spec"
        assert with_gate == "N4_human_gate"

    def test_the_human_gate_routes_onward_to_the_reviewer(self) -> None:
        """The other half: N4 is a checkpoint before N5, not instead of it.

        The gate's third exit is END, when the human rejects the draft. That is
        the one path where a demoted proxy is never re-judged -- and nothing
        ships either, because the run stops. The demotion's justification holds
        on every path that CONTINUES, which is the claim that matters.
        """
        from assemblyzero.workflows.implementation_spec.graph import (
            route_after_human_gate,
        )

        assert route_after_human_gate(
            {"next_node": "N5_review_spec"}
        ) == "N5_review_spec"
        assert route_after_human_gate(
            {"next_node": "N2_generate_spec"}
        ) == "N2_generate_spec"
        assert route_after_human_gate({}) == "END"

    def test_the_default_is_engaged(self) -> None:
        assert vc.review_is_engaged({}) is True

    def test_a_graph_can_declare_no_reviewer(self) -> None:
        assert vc.review_is_engaged({"review_engaged": False}) is False


class TestTheInlineHackIsGone:
    """#2539's demotion was an inline result rewrite in the runner. The sweep
    replaces it with the table; leaving both would let them disagree."""

    def test_the_runner_no_longer_hardcodes_one_checks_demotion(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        assert "density heuristic — not blocking" not in source
        assert "_demote_proxies(check, review_engaged)" in source

    def test_the_advisory_prefix_has_one_definition(self) -> None:
        assert advisory_details("x").startswith("ADVISORY (proxy-heuristic")

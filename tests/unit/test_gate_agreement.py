"""The two spec gates must agree about what valid code looks like (#2397).

The spec reviewer (N5) and the symbol checker (N3) are each individually correct
and individually well tested. Twice now they have disagreed, and each time the
drafter was handed a contradiction it could not satisfy at any iteration count:

    run-issue1-173403  reviewer demanded `pytest_addoption` registration
                       checker flagged `addoption` as hallucinated      (#2391)

    run-issue1-193349  reviewer dictated `request.config.getoption(...)`
                       verbatim, 012-readiness-verdict.md line 7
                       checker flagged `getoption` as hallucinated      (#2396)

Both were repaired at the resolver. Neither repair could have PREVENTED the
other, because the fault is not in either gate — it is in the relationship, and
a relationship is what neither gate's unit tests can assert. This module is that
assertion.

It fails on the commit that introduces a disagreement, in CI, instead of in a
roll, at the cap, after the operator has spent the launch.
"""

import sys
from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_api_symbols_exist,
    detect_unknown_method_calls,
)

sys.path.insert(0, str(Path(__file__).parent.parent / "fixtures" / "reviewer_idioms"))
from framework_idioms import FRAMEWORK_IDIOMS  # noqa: E402

#: A target repo's surface. Deliberately small and deliberately containing NONE
#: of the framework methods below — which is the whole point. The live runs
#: gathered 21 symbols and none of them was `addoption` or `getoption`.
TARGET_SYMBOLS = ["GaugeWindow", "render", "to_dict", "update", "SkinConfig"]


def _spec_around(snippet: str) -> str:
    """Wrap a snippet the way a real spec presents it — a tagged Python fence."""
    return f"# Implementation Spec\n\n## 6. Files\n\n```python\n{snippet}```\n"


class TestReviewerIdiomsAreAccepted:
    """Every idiom the reviewer recommends must clear the symbol checker."""

    def test_the_corpus_is_not_empty(self):
        """Guards the guard: a corpus that failed to import proves nothing."""
        assert len(FRAMEWORK_IDIOMS) >= 9

    def test_every_idiom_passes_the_check(self):
        failures = []
        for name, provenance, snippet in FRAMEWORK_IDIOMS:
            result = check_api_symbols_exist(_spec_around(snippet), TARGET_SYMBOLS)
            if not result["passed"]:
                failures.append(f"{name}: {result['details']}")
        assert not failures, (
            "The symbol checker rejects idioms the spec reviewer recommends. "
            "Any drafter told to write one of these will deadlock:\n"
            + "\n".join(failures)
        )

    def test_every_idiom_flags_nothing(self):
        """Same contract at the detector level, so a skip cannot hide a flag."""
        failures = []
        for name, provenance, snippet in FRAMEWORK_IDIOMS:
            flagged = detect_unknown_method_calls(
                _spec_around(snippet), set(TARGET_SYMBOLS)
            )
            if flagged:
                failures.append(f"{name}: {flagged}")
        assert not failures, "\n".join(failures)

    def test_the_two_deadlock_idioms_are_in_the_corpus(self):
        """The regressions that cost two rolls stay pinned by name."""
        joined = "\n".join(snippet for _, _, snippet in FRAMEWORK_IDIOMS)
        assert "parser.addoption(" in joined, "#2391's idiom left the corpus"
        assert "request.config.getoption(" in joined, "#2396's idiom left the corpus"


class TestTheContractCanActuallyFail:
    """A green suite that cannot go red is decoration.

    Every assertion above is a negative — 'nothing was flagged'. If the fences
    stopped parsing, or the checker started skipping, all of them would pass
    while proving nothing. That is the exact shape of the empty-symbol-universe
    PASS that nearly shipped as evidence in the #2392 round.
    """

    def test_a_genuine_hallucination_is_still_rejected(self):
        """The instrument is capable of failing."""
        spec = _spec_around(
            "def build():\n"
            "    gauge = GaugeWindow()\n"
            "    return gauge.model_dump()\n"
        )
        result = check_api_symbols_exist(spec, TARGET_SYMBOLS)
        assert result["passed"] is False
        assert "model_dump" in result["details"]

    def test_the_corpus_snippets_actually_parse(self):
        """A snippet that does not parse would be skipped, not cleared."""
        import importlib

        vc = importlib.import_module(
            "assemblyzero.workflows.implementation_spec.nodes"
            ".validate_completeness"
        )
        for name, _, snippet in FRAMEWORK_IDIOMS:
            scan = vc._scan_fences(_spec_around(snippet))
            assert scan.failures == [], f"{name} does not parse: {scan.failures}"
            assert len(scan.facts) == 1, f"{name} produced no facts"

    def test_the_corpus_snippets_contain_judgeable_calls(self):
        """Each snippet must present at least one method call to judge.

        Without this, an idiom could be 'accepted' because it contains nothing
        the checker looks at.
        """
        import importlib

        vc = importlib.import_module(
            "assemblyzero.workflows.implementation_spec.nodes"
            ".validate_completeness"
        )
        for name, _, snippet in FRAMEWORK_IDIOMS:
            scan = vc._scan_fences(_spec_around(snippet))
            calls = [c for f in scan.facts for c in f.calls]
            assert calls, f"{name} has no method calls — it proves nothing"


class TestKnownGaps:
    """Disagreements the corpus has found but that are not repaired yet.

    Recorded as xfail rather than as a comment, so the gap is in the suite and
    flips to green on the day it is closed — instead of being rediscovered by a
    roll.
    """

    @pytest.mark.xfail(
        reason=(
            "#2399: a third-party object returned by a REPO function is flagged. "
            "`img = render(...)` then `img.getpixel(...)` clears today only "
            "because draft 013 happens to import `render`, which exempts `img` "
            "by assignment propagation. Specs legitimately omit import headers "
            "(#1952's own words), and the import-less form deadlocks."
        ),
        strict=True,
    )
    def test_third_party_object_from_a_repo_call_without_the_import(self):
        spec = _spec_around(
            "def test_req_070():\n"
            "    img = render(50, [], 256)\n"
            "    assert img.getpixel((10, 10)) == (255, 255, 255, 255)\n"
        )
        result = check_api_symbols_exist(spec, [*TARGET_SYMBOLS, "render"])
        assert result["passed"] is True, result["details"]

    def test_the_same_shape_WITH_the_import_does_clear(self):
        """Control: proves the xfail above is about the import, not the shape."""
        spec = _spec_around(
            "from boostgauge.gauge import render\n"
            "\n"
            "def test_req_070():\n"
            "    img = render(50, [], 256)\n"
            "    assert img.getpixel((10, 10)) == (255, 255, 255, 255)\n"
        )
        result = check_api_symbols_exist(spec, [*TARGET_SYMBOLS, "render"])
        assert result["passed"] is True, result["details"]


class TestCheckerExemptionsAreReachable:
    """The exemption must survive the way a spec actually presents code.

    The checker pools facts across ALL fences, so a spec that declares the hook
    in one snippet and uses it in another must still clear. Both real deadlocks
    arrived as multi-fence documents.
    """

    def test_exemption_survives_across_separate_fences(self):
        spec = (
            "# Spec\n\n### conftest\n\n```python\n"
            "def pytest_addoption(parser):\n"
            '    parser.addoption("--generate-baselines", action="store_true")\n'
            "```\n\n### the test\n\n```python\n"
            "def test_req_120_visual(request, tmp_path):\n"
            '    generate = request.config.getoption("--generate-baselines", False)\n'
            "    return generate\n"
            "```\n"
        )
        result = check_api_symbols_exist(spec, TARGET_SYMBOLS)
        assert result["passed"] is True, result["details"]

    def test_exemption_survives_alongside_non_python_fences(self):
        """#2392 skips non-Python fences by tag; that must not drop the facts."""
        spec = (
            "# Spec\n\n```text\nclass PositionConfig(TypedDict):\n```\n\n"
            "```json\n{\"skin\": \"stingray\"}\n```\n\n"
            "```python\n"
            "def test_req_120_visual(request, tmp_path):\n"
            '    return request.config.getoption("--generate-baselines", False)\n'
            "```\n"
        )
        result = check_api_symbols_exist(spec, TARGET_SYMBOLS)
        assert result["passed"] is True, result["details"]
        assert "skipped by language tag" in result["details"]

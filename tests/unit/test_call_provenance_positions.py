"""The provenance rule must run in every AST position a Call can occupy (#2411).

Five kills of one class, four fixes each narrower than the class. #2411 was
filed on the hypothesis that the one-rule refactor had an unswept AST position,
decorators, because the checker's source contains no occurrence of the word.

Measurement refuted that. `ast.walk` reaches `decorator_list` without anyone
naming decorators, and the sweep below found the call collected and judged
identically in 16 of 16 positions. The traversal was complete; the RULE was
incomplete.

What the rule was missing: ownership was rooted only for framework-INJECTED
PARAMETERS. `_receiver_key` returns the last attribute by design, so
`pytest.mark.parametrize(...)` keys on `mark`, which is exempt in nobody's
book, while the root `pytest` sat in `exempt` as an import and was never
consulted. Any call rooted in an imported name and reached through more than
one hop fell through to the symbol test.

One hop had always cleared, because the receiver IS the import
(`pytest.raises`). The obvious stdlib instance, `os.path.join`, was masked by
`join` sitting in the allowlist. `parametrize` appears to be the first
non-allowlisted method behind a multi-hop foreign root that a draft produced.

This file exists so the sixth costume is found here rather than by a roll.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    _scan_fences,
    detect_unknown_method_calls,
)

REPO_SYMBOLS = {"Gauge", "GaugeWindow", "render", "load_config"}


@pytest.fixture(scope="module")
def first_party_repo() -> str:
    """A target repo that genuinely owns a top-level package named `gauge`.

    First-party detection reads the filesystem, so a true positive rooted in the
    repo's own package cannot be asserted against a path that does not exist.
    """
    tmp = Path(tempfile.mkdtemp())
    (tmp / "gauge").mkdir()
    (tmp / "gauge" / "__init__.py").write_text("")
    return str(tmp)


def fence(body: str, preamble: str = "import pytest\n\n") -> str:
    return "```python\n" + preamble + body.strip() + "\n```\n"


#: The same foreign-rooted two-hop chain in every position a Call can occupy.
#: Identical payload throughout, so any difference in verdict is attributable
#: to position alone.
CALL_POSITIONS: dict[str, str] = {
    "expression statement": "pytest.mark.parametrize('a', [1])",
    "assignment RHS": "m = pytest.mark.parametrize('a', [1])",
    "decorator": "@pytest.mark.parametrize('a', [1])\ndef t(a): pass",
    "default argument": "def f(x=pytest.mark.parametrize('a', [1])): pass",
    "comprehension": "ys = [pytest.mark.parametrize('a', [i]) for i in range(3)]",
    "lambda body": "f = lambda: pytest.mark.parametrize('a', [1])",
    "nested call argument": "print(pytest.mark.parametrize('a', [1]))",
    "return value": "def f():\n    return pytest.mark.parametrize('a', [1])",
    "with statement": "with pytest.mark.parametrize('a', [1]):\n    pass",
    "conditional test": "if pytest.mark.parametrize('a', [1]):\n    pass",
    "f-string": "s = f'{pytest.mark.parametrize(\"a\", [1])}'",
    "class body": "class C:\n    x = pytest.mark.parametrize('a', [1])",
    "try body": "try:\n    pytest.mark.parametrize('a', [1])\nexcept Exception:\n    pass",
    "augmented assign": "acc = 0\nacc += pytest.mark.parametrize('a', [1])",
    "keyword argument": "print(x=pytest.mark.parametrize('a', [1]))",
    "chained on a call": "pytest.mark.parametrize('a', [1]).twice()",
}


class TestEveryPositionIsReached:
    """The rule runs everywhere a Call can appear, and answers the same."""

    @pytest.mark.parametrize("position", sorted(CALL_POSITIONS))
    def test_the_call_is_collected(self, position: str):
        """A position that collects no call cannot be judged at all.

        This is the failure the issue hypothesised. It does not occur, but a
        future change to the visitor could introduce it silently, and a rule
        that never runs looks exactly like a rule that passes.
        """
        scan = _scan_fences(fence(CALL_POSITIONS[position]))
        assert not scan.failures, f"fence did not parse: {scan.failures}"
        calls = [c for f in scan.facts for c in f.calls]
        assert calls, f"no call collected in {position}"
        assert any(c.method == "parametrize" for c in calls)

    @pytest.mark.parametrize("position", sorted(CALL_POSITIONS))
    def test_a_foreign_rooted_chain_clears(self, position: str):
        """`pytest` is imported, so nothing down that chain is the repo's."""
        flagged = detect_unknown_method_calls(
            fence(CALL_POSITIONS[position]), REPO_SYMBOLS
        )
        assert not flagged, f"{position} flagged {sorted(flagged)}"

    @pytest.mark.parametrize("position", sorted(CALL_POSITIONS))
    def test_the_root_is_what_carries_ownership(self, position: str):
        """Receiver keys on the last attribute; the root is the deciding fact.

        Pinned because the whole defect was a rule that consulted the receiver
        where it needed the root.
        """
        scan = _scan_fences(fence(CALL_POSITIONS[position]))
        call = next(
            c for f in scan.facts for c in f.calls if c.method == "parametrize"
        )
        assert call.receiver == "mark"
        assert call.root == "pytest"


class TestTruePositivesSurviveInEveryPosition:
    """The check must not go blind in the positions it was just taught."""

    @pytest.mark.parametrize(
        "position",
        ["expression statement", "assignment RHS", "decorator", "return value"],
    )
    def test_a_first_party_chain_is_still_judged(
        self, position: str, first_party_repo: str
    ):
        """Rooted in the repo's OWN package, so its symbol table has authority.

        This is the false-clearance surface the pre-#2411 comment protected by
        keying only on framework roots. Widening to foreign roots keeps it
        closed, because first-party tops are excluded from that set.
        """
        body = CALL_POSITIONS[position].replace(
            "pytest.mark.parametrize('a', [1])", "gauge.sub.no_such_call()"
        )
        flagged = detect_unknown_method_calls(
            fence(body, preamble="import gauge\n\n"),
            REPO_SYMBOLS,
            first_party_repo,
        )
        assert "no_such_call" in flagged, f"{position} went blind"

    def test_a_one_hop_first_party_call_is_judged(self, first_party_repo: str):
        """`import gauge; gauge.no_such_marker()` is #1527 wearing an import.

        The blanket import exemption written for #1948's third-party universes
        was never meant to cover the target repo's own package, and covering it
        blinded the check to this shape.
        """
        flagged = detect_unknown_method_calls(
            fence(
                "@gauge.no_such_marker()\ndef t(): pass",
                preamble="import gauge\n\n",
            ),
            REPO_SYMBOLS,
            first_party_repo,
        )
        assert "no_such_marker" in flagged

    def test_the_founding_true_positive_still_fires(self, first_party_repo: str):
        """#1527: a gathered class's instance calling a method it lacks."""
        flagged = detect_unknown_method_calls(
            fence(
                "def t():\n    g = GaugeWindow()\n    g.model_dump()",
                preamble="",
            ),
            REPO_SYMBOLS,
            first_party_repo,
        )
        assert "model_dump" in flagged


class TestTheFailOpenDirection:
    """Without a repo root the checker cannot tell first-party from foreign."""

    def test_an_unknown_repo_treats_imported_roots_as_foreign(self):
        """Unresolved is not hallucinated, ruled correct four times.

        The #1812 telemetry consumer used to call the shared core with no repo
        root. Failing closed there would manufacture findings on every spec that
        imports anything.
        """
        flagged = detect_unknown_method_calls(
            fence("@pytest.mark.parametrize('a', [1])\ndef t(a): pass"),
            REPO_SYMBOLS,
            "",
        )
        assert not flagged

    def test_but_a_gathered_constructor_is_still_judged(self):
        """Failing open on IMPORTS does not surrender jurisdiction generally."""
        flagged = detect_unknown_method_calls(
            fence("def t():\n    g = GaugeWindow()\n    g.model_dump()", preamble=""),
            REPO_SYMBOLS,
            "",
        )
        assert "model_dump" in flagged

    def test_a_missing_repo_path_does_not_raise(self):
        """A symbol check must not fail because a path was unreadable."""
        flagged = detect_unknown_method_calls(
            fence("@pytest.mark.parametrize('a', [1])\ndef t(a): pass"),
            REPO_SYMBOLS,
            r"C:\no\such\directory\anywhere",
        )
        assert not flagged


class TestTheMaskThatHidThisForFourFixes:
    """Why a two-hop foreign chain never surfaced before `parametrize`."""

    def test_one_hop_clears_because_the_receiver_is_the_import(self):
        scan = _scan_fences(fence("def t():\n    pytest.raises(ValueError)"))
        call = next(c for f in scan.facts for c in f.calls)
        assert call.receiver == "pytest", "one hop keys on the import itself"
        assert not detect_unknown_method_calls(
            fence("def t():\n    pytest.raises(ValueError)"), REPO_SYMBOLS
        )

    def test_the_stdlib_instance_was_masked_by_the_allowlist(self):
        """`os.path.join` is the same two-hop shape and always looked fine.

        It cleared on `join` being allowlisted rather than on the rule working,
        which is why the class survived four fixes. Asserted with a method that
        is NOT allowlisted so the rule is what answers.
        """
        text = fence(
            "def t():\n    os.path.nonexistent_thing()", preamble="import os\n\n"
        )
        assert not detect_unknown_method_calls(text, REPO_SYMBOLS)

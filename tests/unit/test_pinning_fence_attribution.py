"""An opening fence belongs to the region it opens (#2681).

boostgauge #384, runs run-issue384-063258 and run-issue384-095434: the spec
stage burned two iteration caps on `manifest_traceability` while the
drafter's fix was already written. Draft 010 carried every `# manifest:`
citation the check demanded, correctly placed inside the §10.1 test bodies,
and the halt still reported those same two tests as "tracing to nothing" —
with six [PINNING] refusals naming ```python in the same log.

The attribution was backward. `_blocks` gave an opening fence delimiter to
the heading block ABOVE it, while the tests inside became their own blocks.
A verdict names tests, so the test blocks unlocked and the fence line stayed
locked in an unnamed heading block — and an insertion inside the fence,
which shifts that line, read as modifying locked content. The citation the
check demands can only live inside the fence, so the two requirements were
jointly unsatisfiable.
"""

from __future__ import annotations

from assemblyzero.workflows.implementation_spec.revision_pinning import (
    enforce_pinning,
    named_line_flags,
)

#: The observed shape: a heading, a fence, and two named tests inside it.
DRAFT = """## 10. Test Plan

### 10.1 Per-criterion test functions

```python
def test_req_010_verify_horizon_returns_to_bright():
    img = render_face(1024)
    assert img is not None


def test_req_020_verify_legacy_bindings_survive():
    img = render_face(1024)
    assert img.size == (1024, 1024)
```
"""

#: The drafter's fix: the citation comment the check demands, inside the
#: fence, in the body of a test the verdict named.
REVISED = DRAFT.replace(
    "def test_req_010_verify_horizon_returns_to_bright():\n",
    "def test_req_010_verify_horizon_returns_to_bright():\n"
    "    # manifest: S10r.1\n",
)

NAMED = {"test_req_010_verify_horizon_returns_to_bright"}


class TestTheFenceIsNotLockedAwayFromItsTests:
    def test_the_opening_delimiter_is_named_with_the_tests_it_opens(self) -> None:
        flags = named_line_flags(DRAFT, NAMED)
        fence_line = DRAFT.splitlines().index("```python")
        assert flags[fence_line], (
            "the opening fence is still attributed to the heading above it, "
            "so an insertion inside the fence reads as modifying locked "
            "content (#2681)"
        )

    def test_the_citation_insertion_is_accepted(self) -> None:
        result = enforce_pinning(
            DRAFT, REVISED,
            current_tokens=NAMED,
            ever_tokens=NAMED,
        )
        assert "# manifest: S10r.1" in result.text, (
            f"the drafter's citation was reverted; refusals={result.refusals} "
            f"regressions={result.regressions}"
        )
        assert not result.refusals
        assert not result.regressions


class TestTheLockStillHoldsWhereItShould:
    def test_an_unnamed_prose_rewrite_is_still_refused(self) -> None:
        """#2532's direction must not become a hole: content in a block no
        verdict named is still locked."""
        draft = DRAFT + "\n## 11. Rollout\n\nShip it on Tuesday.\n"
        revised = draft.replace("Ship it on Tuesday.", "Ship it on Friday.")
        result = enforce_pinning(
            draft, revised,
            current_tokens=NAMED,
            ever_tokens=NAMED,
        )
        assert "Tuesday" in result.text, (
            "an unnamed section was rewritten and pinning allowed it"
        )

    def test_a_fence_holding_no_def_keeps_its_old_attribution(self) -> None:
        """There is no region for such a delimiter to open, so it stays with
        the heading — the change is scoped to fences that hold tests."""
        draft = (
            "## 7. Patterns\n\n```python\nCONSTANT = 3\n```\n\n"
            "### 10.1 Tests\n\n```python\n"
            "def test_req_010_verify_horizon_returns_to_bright():\n"
            "    assert True\n```\n"
        )
        flags = named_line_flags(draft, NAMED)
        lines = draft.splitlines()
        first_fence = lines.index("```python")
        assert not flags[first_fence], (
            "a fence holding no def should not inherit naming from a test "
            "in a different section"
        )

# Test Report — Four Tests That Asserted Nothing (#3490)

## The Repaired Files

```
poetry run pytest tests/unit/test_implement_code_routing.py
24 passed

poetry run pytest tests/unit/test_section_utils.py \
                  tests/unit/test_verdict_analyzer_database.py \
                  tests/unit/test_open_questions_loop.py
73 passed
```

## The One That Had To Be Proved, Was Proved

A test that asserts nothing is easy to replace with a test that asserts nothing
differently. For the tautological case that risk is the whole point, so it was
checked by breaking the code rather than by reading the new test.

`claude_client.py` was temporarily changed from

```python
provider = get_provider(f"claude:{model or 'opus'}", effort=effort)
```

to a hardcoded `get_provider("claude:opus", ...)`, and:

```
FAILED tests/unit/test_implement_code_routing.py::test_call_claude_explicit_model
1 failed, 23 deselected
```

The new test fails on broken routing. **The old test would have passed**, because
it never reached that line. The source was then restored and
`git diff` over `assemblyzero/` is empty — the working tree carries only test
changes.

A second test was added for the other half of REQ-7 (no model supplied →
`claude:opus`). Without it, a regression that dropped the model argument
entirely would satisfy the first test by never reaching it.

## The Anti-Vacuity Guard I Nearly Needed Myself

The compat test parses `generate_draft.py` and asserts
`"validate_draft_structure" not in called_names`. As first written, a bad path or
an empty parse would yield an empty set and the membership test would **pass
while measuring nothing** — the exact defect this issue is about, reintroduced
in the fix for it.

```python
assert called_names, f"parsed no calls from {source}; the check is inert"
```

catches that before the real assertion runs.

## Measured, Not Assumed

`test_generic_feedback_returns_empty` now asserts `result == []`. That value was
**measured** by running `identify_changed_sections` against the test's own
inputs, not inferred from the name. The original comment worried that "detail" in
the feedback would match the "Details" heading; it does not, so the name was
right and the comment's hedge was unnecessary.

## The Full Tier

A local full-tier run was started before this report and had not returned when
the PR was opened. **CI runs the same tier on this PR and gates the merge**,
which is the governing check.

The previous tranche (#3484) established the current baseline: 2 failed, 10525
passed, both failures the known #3468 pair. Nothing here touches those.

Said plainly rather than glossed: #3483 was pushed on a targeted selection while
its full tier was still running, and CI found a regression that selection had
missed. The same exposure applies here, mitigated only by CI gating the merge.

## Not Verified

**`test_context_manager_with_exception` was left alone.** It appeared in the
F841 triage but does verify a real property — that the context manager survives
an exception — so it is not one of the four. Its unused binding belongs to the
#3487 tranche.

**No check prevents a new assertion-free test.** Nothing in the suite would fail
if someone added another test that calls a function and discards the result. The
AST triage written for #3487 could become that check; it is a throwaway script
today, preserved at `data/scratch-2026-09-22-lint/triage_f841.py`.

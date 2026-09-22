# Test Report — Raise the Requirements Drafter Timeout (#3463)

## What Was Run

```
poetry run pytest tests/unit -k "draft"
2 failed, 247 passed, 10306 deselected
```

Both failures are **pre-existing and unrelated**, and that was established
rather than assumed — see below.

## What Was Verified

**1. The parameter exists.** `LLMProvider.invoke` at
`assemblyzero/core/llm_provider.py:332` declares
`timeout_seconds: int = 300`. This is a call-site change only; no provider
signature moved.

An earlier pass of this check grepped `assemblyzero/nodes/` and found nothing,
which would have suggested the parameter was invalid. That was the wrong
directory. Recorded because the near-miss is the interesting part: a grep
scoped to the wrong subtree returns a confident absence.

**2. The file still parses.** `ast.parse` over the edited file succeeds. Worth
asserting because the edits reflowed three call sites across multiple lines.

**3. All three sites changed.** `grep -cF 'timeout_seconds=1800'` returns **3**,
and `grep -nF 'drafter.invoke'` shows no remaining bare call. The count is the
check — two of the three sites were textually identical before the edit, so a
single-site replacement would have looked correct in a diff read quickly.

**4. 1800 matches landed precedent.** `generate_spec.py` already uses it at two
sites on `main`, one commented "30 min — impl specs are large".

## The Two Failures Are Not From This Change

`tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft`
fails on **unmodified `main`** (`cdeaf655`) in a separate checkout:

```
assert len(drafts) - len(passing) == 12
AssertionError: assert (102 - 96) == 12
```

That class reads live files from a different repository's working tree
(`C:/Users/mcwiz/Projects/boostgauge/docs/lineage`) and asserts hardcoded counts
against them. It carries a `skipif` on that directory's existence, so it is
skipped in CI and has never been enforced there, while the corpus it measures
has grown from 90 drafts to 102.

Filed as **#3468**. It is not touched here.

## What Is Not Verified

**No test asserts the timeout value.** Nothing would fail if a future edit
returned these calls to the 300s default. The value is a constant passed to a
provider, and asserting it would mean asserting the argument of a mocked call —
worth doing, but it belongs with a decision about whether these ceilings should
be configuration rather than literals, which is a larger question than this
change.

**The ceiling is not measured.** No profiling establishes that 1800 is right, or
that 300 was the actual cause of any observed failure. This aligns an outlier
with the fleet's existing figure; it does not prove the figure.

**No drafter call was executed.** These tests exercise surrounding logic with
providers mocked. Nothing here made a model call, so the timeout was never
reached in anger.

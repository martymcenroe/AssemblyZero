# Implementation Report — Four Tests That Asserted Nothing (#3490)

Each was found by reading an F841 site under #3487. The unused variable was the
visible end of a test that discarded its result without checking it.

## 1. The tautology

`test_implement_code_routing.py::test_call_claude_explicit_model`

Before, it patched `call_claude_for_file`, then called **the mock** and asserted
the mock had been called. The code under test was never reached. It would have
passed with the routing deleted.

The real seam is `get_provider`: `call_claude_for_file` builds its provider spec
from the model it is handed —

```python
provider = get_provider(f"claude:{model or 'opus'}", effort=effort)
```

— so the test now patches that, calls the real function, and reads the spec back.

**Proved non-vacuous by breaking the source.** With the line changed to a
hardcoded `get_provider("claude:opus", ...)`, the new test **fails**; the old one
would have passed. The source was restored and `git diff` over `assemblyzero/`
is empty.

A second test was added for the other half of REQ-7 — no model supplied means
`claude:opus`, not an empty spec. Without it, a regression dropping the argument
entirely would satisfy the first test by never reaching it.

## 2. The name that promised an assertion

`test_section_utils.py::test_generic_feedback_returns_empty`

Its comment worried that "detail" in the feedback might match a "Details"
heading, and settled for "the important thing is it doesn't crash" — so a test
named `..._returns_empty` never checked the return.

Measured rather than assumed: the function returns `[]`. The worry was
unfounded and the name was right. `assert result == []` now holds it.

## 3. A comment where an assertion belonged

`test_verdict_analyzer_database.py::test_closes_on_exit`

Its comment claimed SQLite has no obvious "is_closed" check. It does — a closed
connection raises `ProgrammingError` on use:

```python
with pytest.raises(sqlite3.ProgrammingError):
    conn.execute("SELECT 1")
```

The test previously built a database and verified no part of its own name.

## 4. The property stated in a comment and never tested

`test_open_questions_loop.py::test_validate_draft_structure_kept_for_compat`

Its comment said "what matters is it's not called in generate_draft" — and it
did not check that. Both halves of the name are now asserted: the function is
still importable and callable, and `generate_draft.py` is **parsed** (not
string-searched, so a mention in a comment cannot satisfy or break it) to
confirm no call to it remains.

That check carries its own anti-vacuity guard: if the parse yields no calls at
all — wrong path, empty file — the membership test would pass while measuring
nothing, which is the exact defect this issue is about. `assert called_names`
catches it.

## Why This Was Not Folded Into the Lint Work

#3487 removes unused variables. For these four that would have meant deleting
the binding and leaving the test asserting nothing — clearing the linter while
making the gap harder to find. The lint tranche leaves them alone; the
assertions land here, and the variables become used as a consequence.

# Test Report: require_status_check.py

**Issue:** #3447
**Branch:** `3447-require-status-check`
**Date:** 2026-09-22

## Result

```
poetry run pytest tests/tools/test_require_status_check.py -q
9 passed in 0.31s

poetry run ruff check tools/require_status_check.py tests/tools/test_require_status_check.py
All checks passed!
```

## What is covered

The decision logic, which is effectively the whole tool. `run()` is called
directly with a placeholder string where the PAT would be, so nothing in the
suite decrypts anything. That decrypt belongs to the operator, never to a test
or an agent, per the `_pat_session` operational rule.

| Case | Expected |
|---|---|
| Branch has no protection | exit 1, nothing written |
| Protected, status checks off | exit 1, nothing written |
| Either refusal, with `--apply` | still exit 1 |
| Context already in the list | exit 0, nothing written |
| Default invocation | dry-run, nothing written, current contexts printed |
| `--apply` with a new context | `add_context` called with that context |
| `contexts: []` | treated as "on, none listed", not as "off" |

## The fixture does the load-bearing work

Every test that expects no write installs a replacement for `add_context` that
raises `AssertionError` when called:

```python
def explode(*_args, **_kwargs):
    raise AssertionError("add_context was called when nothing should be written")
```

A test that merely asserts on the return value and printed text would pass just
as happily if the tool had written to GitHub on its way to that return value.
For a tool whose whole purpose is a privileged mutation, "did not write" has to
be enforced rather than assumed.

## The two cases worth having written

**`--apply` does not override a refusal.** The easy mistake is to treat the
mutation flag as an escalation that also means "and do it anyway". It does not:
`--apply` says to write when writing is the right call, not to write regardless
of what the repository looks like.

**`contexts: []` is not the same as checks being off.** `if not checks` would
collapse an empty context list into the "switched off" branch and refuse to add
the first context to a branch that is perfectly ready for one. The tool
distinguishes them by checking the *type* of `required_status_checks` rather
than its truthiness, and the test pins that.

## Not covered

The network path: the real GET and POST against GitHub. Both need the classic
PAT, and exercising them needs a real repository with real branch protection, so
the first genuine run is the operator's. The refusals are what stand between a
wrong invocation and a branch nothing can merge into, which is why they are the
part with tests.

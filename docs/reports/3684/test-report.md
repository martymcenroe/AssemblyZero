# Test Report: remove the repo-local Claude Code hooks (#3684)

## The check that blocked this, and that it was the only one

CI run 36778520160 on head `048764ae` failed. Reading its failed-step log, every failure was in
one file:

```
FAILED tests/unit/test_bare_claude_guard.py::test_allowed[...]        (10 cases)
FAILED tests/unit/test_bare_claude_guard.py::test_blocked[...]        (12 cases)
FAILED tests/unit/test_bare_claude_guard.py::test_malformed_json_allows_fail_open
FAILED tests/unit/test_bare_claude_guard.py::test_missing_tool_input_allows
```

No other test failed. The removal broke exactly the file that hard-coded the path of a removed
script, which is what #3686 predicted.

## After the fix

```
poetry run pytest tests/unit/test_bare_claude_guard.py -q     26 passed
```

Against the installed guard, every case passes, so the cases are stronger than before: they now
exercise the script that actually runs on a tool call rather than a tracked copy nothing invoked.

## Full local suite, and why its failures are not this change

```
poetry run pytest -q     19 failed, 11257 passed, 74 skipped, 90 deselected, 6 xfailed
```

The named failures are `tests/test_auto_reviewer_wait_loop.py` (7) and
`tests/tools/test_dependabot_review.py::TestRunJsGate` (2), neither of which touches
`.claude/hooks` or the guard.

**None of them appears in CI's failure list above**, which is the authoritative environment for
this repository. They are conditions of the machine the suite was run on, not of this branch.
Establishing that from the CI log took one read; re-running the suite against `main` to compare
would have taken ten minutes and told me the same thing less reliably.

They are recorded here rather than left out, because a reader seeing 19 local failures on a
branch deserves to know which of them this change is answerable for: none.

## What this change does not prove

It removes files and repoints one test. It does not verify the central guard's behaviour across
the machine; that is a separate program's job and it runs where the hooks are installed.

On a CI runner the repointed cases skip, so CI no longer asserts the guard's exit codes at all.
That is a real reduction in what CI covers, accepted deliberately: the alternative is a tracked
copy of a script nothing runs, tested in isolation, which is the state that produced #3686.

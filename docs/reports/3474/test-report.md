# Test Report — Remove 90 Placeholder-Free f-Strings (#3474)

## The Full Unit Suite Was Run

```
poetry run pytest tests/unit
3 failed, 10519 passed, 21 skipped, 7 deselected, 5 xfailed in 604.28s
```

Ten minutes, the whole tier, not a subset. This change touches 37 files across
`assemblyzero/`, `tools/` and `tests/`, so a targeted selection would not have
covered it.

## All Three Failures Are Pre-Existing, and Each Was Checked

Not assumed — each was reproduced against unmodified code before being
dismissed.

**`test_create_initial_state_defaults_to_assemblyzero`** — passes in the primary
checkout (`10 passed`), fails here. The cause is not this change:

```
assert "AssemblyZero" in state["assemblyzero_root"]
AssertionError: assert 'AssemblyZero' in 'C:\\Users\\mcwiz\\Projects\\AZ-3474'
```

The test asserts the checkout directory is *named* "AssemblyZero". This worktree
is `AZ-3474`. `default_assemblyzero_root()` resolves
`Path(__file__).resolve().parents[3]` and is name-independent and correct; the
assertion is about a folder name. Filed as **#3475**.

It is green everywhere by coincidence — CI checks out to
`.../AssemblyZero/AssemblyZero`, and the repo's documented worktree convention is
`AssemblyZero-{ID}`. Both contain the string. Two worktrees named `AZ-` for
brevity are what exposed it.

**The two `TestAgainstEveryRecordedDraft` failures** — already known, already
filed as **#3468**. That class reads live files from another repository's
working tree and asserts hardcoded counts; it is `skipif`-ed in CI and has never
been enforced there. Verified failing on unmodified `main` earlier today.

## Why the Fix Is Safe, Beyond the Suite Passing

The suite is evidence, not proof, and for this rule there is a stronger argument
available: removing an `f` prefix from a string containing no placeholders
cannot change the string's value, because there is nothing to interpolate. The
diff's perfect 90-for-90 line symmetry, and the sampled lines showing only a
dropped prefix, are consistent with that and with nothing else.

## Not Verified

**The tests were not run on Linux.** CI does that on the PR.

**No test asserts the absence of F541.** Nothing prevents a new placeholder-free
f-string from being added tomorrow — the rule has no gate behind it. That gate
is the last piece of #3471, deliberately held until the count reaches zero,
because a CI lint step added now would fail on the 546 findings that remain.

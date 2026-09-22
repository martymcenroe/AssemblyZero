# Implementation Report — Scope ruff to Maintained Source (#3472)

First piece of #3471.

## The Change

A `[tool.ruff]` section in `pyproject.toml`:

```toml
[tool.ruff]
extend-exclude = ["docs/lineage"]
```

with a comment recording why. `pyproject.toml` had no `[tool.ruff]` section at
all, so `ruff check .` ran on defaults across the whole tree.

## Effect, Measured

| | before | after |
|---|---|---|
| total errors | **737** | **636** |
| invalid-syntax | 14 | **0** |
| auto-fixable | 589 | 502 |

101 findings left scope. Every one was in `docs/lineage/**`.

## Why Exclude Rather Than Fix

`docs/lineage/` is the design-review trail — generated `NNN-test-scaffold.py`
and friends, recording what a workflow produced on a given run. Nothing imports
them and nothing runs them.

Editing them to satisfy a linter would rewrite the record of what was actually
generated, which is the opposite of what a lineage trail is for. It would make
the artifacts lie about their own past.

All 14 invalid-syntax findings were there, in files like
`docs/lineage/active/434-testing/005-test-scaffold.py`:

```
invalid-syntax: Expected `import`, found `-`
```

That is evidence about a generator's output on a particular day. It is worth
keeping, and arguably worth its own investigation, but it is not a lint defect
in this repo's source. Nothing in `assemblyzero/`, `tools/` or `tests/` fails to
parse.

## A Prediction That Was Wrong, and the Correction

The issue predicted 633 errors afterwards. The real figure is **636**.

The prediction came from `ruff check assemblyzero tools tests`, which names three
directories and therefore misses everything else. The three extra are in
`docs/temp/` — `fix_598_syntax.py`, `patch_598.py`, `test_587.py`, one-off
scripts that are nonetheless tracked, each with an unused import.

They are deliberately **left in scope**. Widening the exclusion to cover them
would be scope creep on a narrowing change, and they are three trivial findings
the F401 work will absorb. The exclusion stays exactly one directory wide.

## What This Does Not Do

No rule is disabled and no severity is lowered. This narrows *what is linted*,
never *what counts as an error*. All 636 remain findings to be fixed in the
sibling issues under #3471 — none of them is suppressed here.

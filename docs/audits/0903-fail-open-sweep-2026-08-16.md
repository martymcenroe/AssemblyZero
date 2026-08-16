# 0903 — Fail-open sweep of the pipeline (#2475)

**Date:** 2026-08-16
**Scope:** `assemblyzero/` — 275 files, 1,603 functions, 7,216 sites examined
**Program:** `tools/audit_fail_open.py` (logic in `assemblyzero/core/fail_open_audit.py`)
**Gate:** `tests/unit/test_fail_open_audit.py`, against `tests/fixtures/fail_open_baseline.json`

This document is a **snapshot**. The program is the source of truth, and it is
re-runnable:

```
poetry run python tools/audit_fail_open.py
```

A manual read-through proves the state of one moment. Everything below was
derived by parsing the tree, and it will be re-derived on the next commit,
because the unit suite runs the same code this report came from.

## Why the sweep exists

On 2026-08-16 the N0c requirements gate could not reach the governance model,
printed `proceeding`, and the run continued to spend drafter budget with the
check skipped (#2474). The question that raises is not "was that one site
wrong" but **where else does the pipeline continue after something failed** — a
pipeline that advances past a gate it could not run is untrustworthy at every
stage, because a green result becomes indistinguishable from a skipped one.

## Findings

| | Count |
|---|---|
| Fail-open sites | **466** |
| Undeclared (nobody has ruled) | 462 |
| On a spending path | 143 |

Ranked by the column that matters — can the run's final output be told from one
where the step succeeded?

| Answer | Count | What it means |
|---|---|---|
| **no** — nothing is said at all | **244** | The failure leaves no trace. This is the class that makes results untrustworthy. |
| maybe — filed into a structure | 61 | The failure became an entry; whether that entry reaches the operator depends on the caller and is not derivable here. |
| yes — printed or logged | 161 | A nuisance, not a trust problem. |

**68 sites are silent, undeclared, and on a spending path.** That is the
worklist: a failure nobody sees, nobody has ruled on, in a place where the run
keeps paying afterwards.

By shape:

| Category | Count |
|---|---|
| `except` handlers that continue | 440 |
| warned, then returned the all-clear | 21 |
| reported success having examined nothing | 3 |
| precondition unmet, all-clear returned anyway | 2 |

Concentration, silent and on a spending path:

| File | Sites |
|---|---|
| `implementation_spec/nodes/analyze_codebase.py` | 9 |
| `implementation_spec/nodes/validate_completeness.py` | 7 |
| `testing/nodes/verify_phases.py` | 6 |
| `requirements/nodes/analyze_codebase.py` | 5 |
| `testing/nodes/implementation/import_validator.py` | 4 |
| `testing/nodes/augment_tests.py` | 4 |

## A verified example, because the sweep found one in its own author

`assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:900`:

```python
try:
    content = full_path.read_text(encoding="utf-8")
    tree = ast.parse(content)
except (OSError, SyntaxError):
    continue
```

This gathers the codebase context the drafter builds from. A file that will not
parse is dropped, silently, and the drafter receives a smaller context that is
indistinguishable from a complete one.

That is not hypothetical. **The first version of this audit had the same bug.**
Two files in this tree carry a UTF-8 BOM, which `ast.parse` rejects as a
non-printable character while Python's own importer strips it. The audit
reported full coverage of a tree it had not fully read — and the only reason it
was caught is that it prints a counted "files that would NOT parse" line, which
read 2. Fixed by reading with `utf-8-sig`; a test now pins it.

The same two files are still silently dropped from the drafter's context by the
site above.

## Classify, do not blanket-fix

Some fall-throughs are correct. An advisory benchmark should not halt a run.
The job is to make each one **a decision on record rather than an accident**, so
clearing a finding means one of exactly two things:

1. Make the site fail closed.
2. Write `# fail-open: <why continuing is correct here>` on it.

What the audit refuses to allow is a third state where nobody has decided.
Declared sites stay in the inventory — they are still fail-open, and hiding them
would make the count a lie — but they no longer register as *undeclared*, which
is what the gate acts on.

Four sites are declared as of this snapshot, all of them rulings made while
writing this:

| Site | Ruling |
|---|---|
| `analyze_requirements.py` empty issue body | An LLD run from a brief has no issue body; halting would stop every file-input run on the absence of a thing those runs never have. |
| `analyze_requirements.py` unarticulated conflicts (#2462) | Halting would stop the roll on a finding the check itself could not state. It records, so the banner fires. |
| `fail_open_audit.py` unparseable file | One unreadable file must not cost the whole sweep — defensible only because the count is printed. |
| `fail_open_audit.py` unparseable exception type | Costs a label in the report, not a finding. |

## How the gate works

`tests/unit/test_fail_open_audit.py` runs the audit against the repo and
compares it to a frozen baseline, so a **newly-introduced** fail-open fails the
build at the point it lands. The baseline is keyed on file, qualified function
name, category and occurrence index — deliberately **not** line number, because
a baseline that churns on every unrelated edit is one people regenerate without
reading.

Two guards keep the gate from rotting:

- **Staleness.** A baseline entry matching no live site fails the suite, so
  fixing a fail-open shrinks the baseline rather than leaving a fossil.
- **The gate's own regression test.** One site is dropped from the baseline and
  the check is asserted to go red, so "no new fail-open" is a result rather than
  a property of an assertion that can never fire.

## What this audit does not claim

- **It does not know whether a recorded failure reaches the operator.** That is
  a question about the caller. The report says `maybe` and does not guess.
- **`spends_after` is structural, not traced.** A graph node that returns
  normally routes onward and everything downstream calls models, so nodes are
  `yes`. Anywhere else it says `unknown` rather than asserting either way.
- **Scope is `assemblyzero/`.** The launcher scripts under `tools/` are not
  swept by default; `--subdir tools` widens it. That is a deliberate omission,
  stated here rather than left to be discovered.
- **462 undeclared sites are not 462 bugs.** They are 462 places nobody has
  ruled. The 68 silent-and-spending are where to start.

# Test Report — The gate-registry denominator leaves the PR gate (#3527)

## What was run

From the main checkout's venv, against this worktree
(`PYTHONPATH=<worktree>`, `--rootdir <worktree>`, `-p no:cacheprovider`):

```
tests/unit/test_routing_policy.py tests/unit/test_gate_registry.py tests/unit/test_utf8_console.py
99 passed, 1 warning in 6.33s
```

The three files are every test that imports `audit_halt_sites` or reads
`gate_registry_baseline.json`. The warning is the Pydantic V1 notice on
Python 3.14, present on every run in this repo.

```
poetry run ruff check tools/audit_halt_sites.py tests/unit/test_routing_policy.py
All checks passed!
```

## The new tests fail on the old tool

`tools/audit_halt_sites.py` was stashed by name (`git stash push -- tools/audit_halt_sites.py`),
the new class was run alone, and the stash was popped:

```
tests/unit/test_routing_policy.py -k TestTheDenominatorLeftThePRGate
6 failed, 27 deselected, 1 warning in 1.85s
```

Five fail with `AttributeError: module 'audit_halt_sites' has no attribute
'denominator_drift'` or `'measured'`. The sixth,
`test_strict_without_check_is_a_usage_error`, passed on the old tool in its
first form, because argparse rejects an unknown `--strict` with the same exit
code 2; it now asserts the message `--strict only applies with --check` and
fails on the old tool too. Recorded because an exit-code-only assertion would
have counted as a test of a flag that did not exist.

## The six tests

| Test | Shows |
|---|---|
| `test_adding_a_walked_file_passes_the_gate_without_touching_the_baseline` | Requirement 1. A temporary `assemblyzero/workflows/` tree, a baseline written against it, a second module with no halt site added. `halt_counts()` and `model_output_halt_rows()` still equal the baseline, the block still has its three keys, the file is byte-identical, and `denominator_drift` is exactly `{"files_scanned": (1, 2)}`. |
| `test_strict_is_clean_on_the_tree_it_was_measured_against` | No drift on the tree the baseline was written from. |
| `test_a_missing_denominator_is_drift_not_a_pass` | With the block deleted, every count is reported with baseline `None`. |
| `test_strict_mode_exits_one_when_the_file_count_moved` | Acceptance criterion 2. A copy of the real baseline with `files_scanned` set to the live count plus one; `main(["--check", "--strict", "--root", ROOT])` returns 1 and prints `files_scanned: baseline N+1, tree N` and the regenerate line. The moved value is derived from the live walk, so the drift is exactly one count whatever the tree holds. |
| `test_check_without_strict_ignores_the_denominator` | Requirement 1 at the command line: the same moved baseline, plain `--check` returns 0 and prints nothing about `measured_against`. |
| `test_strict_without_check_is_a_usage_error` | Exit 2 with the message. |

## On the real tree

```
tools/audit_halt_sites.py --check --strict
PASS -- 178 files, 142 halt sites, every one registered; 93 gates, halt rows: {'impl': 33, 'lld': 15, 'orchestrator': 16, 'spec': 19}; 51 row(s) paired to their own return, 2 exempt (#2814); denominator matches.

tools/audit_halt_sites.py --check
PASS -- 178 files, 142 halt sites, every one registered; 93 gates, halt rows: {'impl': 33, 'lld': 15, 'orchestrator': 16, 'spec': 19}; 51 row(s) paired to their own return, 2 exempt (#2814)
```

The baseline states 178 / 142 / 93 and the tree agrees, so the fixture is not
regenerated in this PR.

## Not verified

The full unit tier was not run for this change. The two files touched are
imported by the three test files above and by nothing else in `tests/`
(`grep -l audit_halt_sites tests/`), and the fixture is unchanged. CI runs the
full tier on the PR.

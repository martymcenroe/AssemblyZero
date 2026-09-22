# Test Report — Schema Lists `data-dl/README.md` (#3445)

## What Was Run

```
poetry run pytest tests/unit/test_new_repo.py -q
130 passed in 14.93s
```

`test_new_repo.py` is the suite that loads and exercises this schema — schema
loading, path-traversal validation, `flatten_files`, `create_structure` and
`audit_project_structure` all read it. It is the file that would break if a
malformed or unexpected `files` entry were introduced, and it did not.

## What Was Verified

**1. The JSON still parses and still validates.**
`TestSchemaLoading::test_T010_load_schema_valid` passed, which exercises the
`("version", "directories", "files")` key check the loader performs.

**2. The entry is well-formed for the consumers that read it.**
`flatten_files` returns `{"path": ..., **entry}` and only special-cases
`template`, which this entry does not set — so it follows the same path as every
other untemplated required file. `validate_paths_no_traversal` passed it: no
`..`, not absolute.

**3. The delta is exactly four lines and touches nothing else.**
After applying the stashed change onto `origin/main`, `git diff` reported one
modified file and one hunk. `tools/new_repo.py`, the stash's other half, showed
no diff at all — it is byte-identical to main, which is why it is not in this
change.

## What Is Not Claimed

**No test asserts that the audit now catches a missing `data-dl/README.md`.**
That is the actual behavioural consequence of this change and it is currently
covered only by inference: `audit_project_structure` iterates the schema's
`files` list, so an added entry is checked. A test that scaffolds a project,
deletes that README and asserts the audit turns invalid would assert it
directly. It does not exist, and this change does not add it.

Recording that plainly rather than letting 130 passing tests imply a coverage
that is not there. The full unit suite was not run locally either; CI runs it on
this PR and that is the check that governs.

# Implementation Report: the verifier prints no secret, and the lineage move cannot take the working tree (#3278, #4303)

Two small safety repairs from the 2026-10-31 open-issue review, landed together.

## #3278: `tools/verify_encrypted_secret.py`

`main()` printed the first and last decrypted lines for every type. A token is one line, so those two prints were the whole credential, twice. Both are gone, for every type. Gating them on `pem` would not have been enough: the filename decides the type, so a token in a file named `*pem*` would still have printed. `check_pem` already reports its markers and `check_pat` its length, line count and shape, so nothing a reader needs is lost. The module docstring no longer calls those lines metadata.

## #4303: `finalize` and `move_lineage_to_done`

`Path("")` is the working directory, which exists, so N7 with an unset `audit_dir` passed its checks and handed `.` to the lineage move. That fell back to `audit_dir.name`, which is empty, so `docs/lineage/done` became the destination, and `shutil.move` copies across a filesystem boundary and then deletes the source.

- `finalize` refuses an unset or empty `audit_dir` first, before it writes anything: an ERROR line on standard error and an `error_message` that routes to HALT.
- `move_lineage_to_done` calls the new `_lineage_relative_path`, which raises `LineageSourceError` unless the source is a directory strictly inside `<target>/docs/lineage/active/` and holds neither the working directory nor the target repository. The caller alerts and re-raises before anything on disk changes.
- The legacy fallback is removed, and its entry leaves `tests/fixtures/fail_open_baseline.json`.

## Decisions

- **No new gate row.** N7's halt joins `impl.input_precondition`. A new halt row needs an operator ruling under the registry's ratchet, and this is the same check that row already makes: the run's inputs are not what the run needs.
- **The fixtures moved, not the guard.** Thirteen tests had invented a lineage outside `active/`. Every real lineage comes from `create_audit_dir`, `create_testing_audit_dir` or the spec path's `docs/lineage/active/{N}-implspec`, which `tests/unit/test_orchestrator_lineage.py` pins, so no real run is refused.

No test covers a lineage on a filesystem boundary on Windows; the behaviour under test is the refusal, which happens before any move.

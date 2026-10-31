# Test Report: the verifier prints no secret, and the lineage move cannot take the working tree (#3278, #4303)

Each new test file was run against `main`'s unchanged source at `769a6136` in the primary checkout (copied in, run, removed), then on this branch.

## #3278: `tests/unit/test_verify_encrypted_secret_no_disclosure.py` (7)

The tests drive `main()`, which `tests/tools/test_verify_encrypted_secret.py` does not reach, with `_decrypt` stood in, so no gpg runs and the values are synthetic. They sit in `tests/unit/` because CI does not run `tests/tools/`.

- A token never reaches the report, typed as `pat`, as `text`, or mislabelled as `pem`. A multi-line text blob shows neither end.
- A valid PEM reports its markers without its body, and the structural metadata is still printed.
- Against `main`: 4 failed, 3 passed (the three that hold on both). On this branch: 7 passed.

## #4303: `tests/unit/test_lineage_move_refuses_the_working_tree.py` (13)

- T1 (R1): N7 with `audit_dir` missing and with it empty halts, leaves the sentinel, writes no file, and its error routes to HALT.
- T2 and T3 (R2, R3): `.`, a target directory outside `active/`, the active root, the working directory by absolute path, the target repository, an ancestor of the working directory, a file under `active/`, and a lineage holding the working directory each raise `LineageSourceError` and alert, with `shutil.move` patched to fail the test if reached and `done/` not created.
- T4 (R2): a real lineage still moves, with no alert.
- T5 (R4): run from another directory, N7's summary and token-budget files land in the lineage and nothing lands in the working directory.
- Against `main`: 11 failed, 2 passed (T4 and T5, which hold on both). On this branch: 13 passed.

## Tiers on this branch

| Tier | Result |
|---|---|
| unit | 13,210 passed, 0 failed, 66 skipped, 7 xfailed |
| integration | 64 passed, 7 skipped |
| e2e | 19 passed |

The adversarial tier was not run: it holds one opt-in test that needs live Gemini access and is skipped without it, and nothing here touches the adversarial node.

The first unit run had 20 failures. One was the stale fail-open baseline entry, six were the N7 halt site with no registry row, and thirteen were fixtures with a lineage outside `active/`; each is repaired here. After the first fix a further two came from the halt-row ratchet, which is why the site went onto an existing row.

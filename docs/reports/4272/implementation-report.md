# Implementation report: #4272

## The defect

On a resume (#525), `generate_spec` in `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py` reads the most recent `*-spec-draft.md` in the lineage. The read had no handler, so a draft that was not UTF-8 or could not be opened raised `UnicodeDecodeError` or `PermissionError` out of N2 instead of halting. A draft that read as empty was passed over without a word, and the node drafted again.

## The fix

- The resume read catches `(OSError, UnicodeDecodeError)` and returns through N2's `_halt`, naming the draft's path, the resume, and the cause. `_halt` is already registered under `spec.drafter_failed`, so the gate registry needed no change.
- An empty draft (whitespace only) prints one line naming the path and its length, then the node drafts again as before.
- A readable draft is recovered as before, without a drafter call.

## Tests

In `tests/unit/test_generate_spec_resume_4272.py` (new):

- `TestAnUnreadableDraftHalts::test_t1_a_draft_that_is_not_utf8_halts_n2_with_the_path_named` (T1)
- `TestAnUnreadableDraftHalts::test_t1_a_draft_that_cannot_be_opened_halts_n2_with_the_path_named` (T1)
- `TestAnUnreadableDraftHalts::test_the_halt_is_loud_on_stderr`
- `TestAnEmptyDraftIsReported::test_t2_an_empty_draft_is_reported_then_n2_drafts` (T2)
- `TestAGoodDraftStillResumes::test_a_readable_draft_is_recovered_without_a_drafter_call`

Before the fix: `4 failed, 1 passed`, with `UnicodeDecodeError` and `PermissionError` raised out of the node.

## The run

On Ubuntu, 2026-11-14, the new file with `test_generate_spec_loud_failure.py` and `test_generate_spec_pinning.py`: `32 passed`.

`ruff check` on `generate_spec.py` reports the same five findings as at HEAD (`F841`, `I001`, `ISC004` three times), none added. The new test file is clean.

# Implementation report: #3752

## The delegation check tells the drafter what to change

`assemblyzero/core/validation/test_plan_validator.py::check_human_delegation`: the message now names the matched words and both remedies instead of quoting the regular expression:

`Test T100 reads as a human check ("visual check") but is typed 'auto': reword it to state what the test asserts automatically, without the words "visual check", or type it Manual if a person must look.`

The decision is unchanged: the same `HUMAN_DELEGATION_PATTERNS`, the same Manual exemption, one violation per test. The message is what the drafter receives as revision feedback (it appears verbatim under `delegation` in the failed draft's feedback), which is why its wording is the fix.

Found on boostgauge #2, run `run-issue2-021912` (2026-10-07 02:19 Central): T100, "Absent needle (post-reset) visual check (REQ-3)", typed Auto, asserting `#3BD7F0` pixels absent, kept its title through three revisions by `gemini-3.1-pro-high` while the feedback read `matches '\bvisual\s+check\b' but type is 'auto'`.

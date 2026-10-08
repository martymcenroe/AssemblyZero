# Implementation Report: post-ADR fail-open tags (#3767) and restore order (#3764)

## #3767: the five tags

Line numbers were confirmed on `main` at `d32780f5`, and all five matched the work order.

| Site | Decision | Why |
|---|---|---|
| `validate_completeness.py:1725` | Not a failure path; comment reworded | A fence tagged Python that does not parse fails the same draft under `python_fences_parse`, by name. An untagged fence that does not parse claimed no Python, so it holds no calls to check. |
| `validate_completeness.py:1746` | **Fails loud** | A first-party callee that does not parse means `call_signatures_match` cannot run, and the check used to pass with the calls unchecked. It now raises `CompletenessCannotCheck`. N3 returns `completeness_cannot_check` and `error_message`, prints an ERROR line, and `route_after_validation` sends it straight to HALT, which alerts. It keys on its own field because `error_message` also carries the cap message on a grace revision, which must still reach N2 (#2304). |
| `stages.py:2233` | Already fails loud; comment reworded | `transient=False` skips the retry, and `_route_after_stage` sends a failed stage to `terminal`, the HALT node. |
| `analyze_requirements.py:779` | Not a failure path; comment reworded | Both asks answered, and #3747's rule is that a conflict halts only when it reproduces. Each dropped conflict is printed. |
| `finalize.py:643` | **Fails loud** | A durable LLD copy that cannot be written now sets `error_message` (finalize routes to HALT, #3864) and prints an ERROR line. #3764 makes that copy the first restore source, so going on without it would let a later stage restore an older LLD. |

Baselines:
- **Loud-failure:** 323 to 318, and `BASELINE_CEILING` lowered by five.
- **Fail-open (the older audit):** regenerated. The four sites whose tags used to declare them are now frozen as undeclared sites. ADR 0236's check is the authority, and it has all five out.
- **Gate registry:** new row `spec.completeness_cannot_check`, citing the operator's ADR 0236 acceptance. `spec.completeness_cap` moves to return index 1. The `spec` halt rows go from 19 to 20.
- **Ledger 0908:** six rows marked fixed.

## #3764: the restore order

`restore_artifact` now searches, in order:

1. the durable handoff copy (#3750), for the LLD only, found in the primary checkout through git's common directory;
2. `origin/<base>` when the caller passes `base`, then this checkout's `HEAD`;
3. the live `<N>-lld` branch;
4. the graveyard refs.

A graveyard copy is refused, and named in a `[REFUSED]` line, when the issue has a settled LLD and the copy's content hash differs. The issue phrased this as "older than the settlement". The settlement module's rule is content, never timestamps, so the test is the recorded `artifact_sha256`. Each restore names its source in the `[REBUILT]` line.

# Implementation Report: the N7.5 adversarial review halts when it cannot run (#3725)

Batched with the #3581 sweep issues for the same review code: #3817 (`adversarial_node.py`), #3808 (`adversarial_gemini.py`), #3818 (`adversarial_validator.py`) and #3819 (`adversarial_writer.py`). The rule is ADR 0236 and standard 0034.

## #3725

- **`run_adversarial_node`.** Every caught transport, quota, model or timeout failure returns `_review_failed(...)`. That helper prints an ERROR line on stderr and sets `error_message`, which names the seat (`impl.adversarial`), the spec, the exception type and its message. It also sets `adversarial_verdict: "error"`.
- **`route_after_adversarial`.** It sends a non-empty `error_message` to HALT, and HALT alerts (#3724). The dead `end` edge is removed from the router, the graph and the atlas, whose N7.5 entry no longer says "non-blocking".
- **`error_message` added to `AdversarialNodeState`.** LangGraph filters a node's state at the boundary, the trap #3546 and #1757 recorded, and this keeps the halt from being filtered out.
- **Docstring.** "Never blocks the run" is removed.
- **"No implementation files in state" is a failure.** N7.5 is reached only after N7 finalize, so an empty list means the state lost the files, never that there was nothing to review. The reason is recorded on #3725.
- **The mock-run skip stays.** It is now the only `_skipped(...)` call in the node.

## The sweep sites, each failing loud

| Site | Was | Now |
|---|---|---|
| node `:148` client cannot be built | WARNING, skipped | HALT |
| node `:164/167/174/177` quota, forbidden, downgrade, call failed | WARNING, skipped | HALT, one handler each, plus `GeminiEmptyResponseError` |
| node `:184` malformed response | verdict error, on to N8 | HALT |
| node `:235/239` rejected generated file; removal failed | WARNING, partial set; removal ignored | rejected files removed, then HALT naming each problem and any file that could not be removed |
| node `:250` zero valid tests | verdict fail, on to N8 | HALT |
| node `:372` unreadable context file | WARNING, `""` | `_read_file` raises; the node halts |
| gemini `:214` reply neither Pro nor Flash | WARNING, passes | `GeminiModelDowngradeError` |
| gemini `:291` unexpected provider exception | renamed a timeout | ERROR log; the type is carried in the message; the node halts |
| gemini `:361` success with no text | accepted | `GeminiEmptyResponseError` |
| validator `:63` test with no assertions | warning, valid True | error, valid False |
| validator `:79` parse fails after compile | bare `pass` | error recorded and logged at ERROR |
| writer `:45` no test cases | INFO, `{}` | `AdversarialWriteError` |
| writer `:82` write fails | re-raised, no route to HALT | `AdversarialWriteError`; the node halts |
| writer `:90` staging dir removal fails | ignored | `_remove_staging_dir` raises; the #3518 ownership assertion is kept |
| writer `:134` test case with empty code | dropped | `AdversarialWriteError` naming the test id |

Validator `:114`, `:227` and `:251` were already marked compliant in the ledger and are unchanged.

## Baselines and the registry

- **Loud-failure baseline:** unchanged at 318. None of these 20 sites was ever in it: the check sees broad handlers and `# fail-open:` tags, and these were narrow handlers and warning-level logs. So there was nothing to remove, and `BASELINE_CEILING` stays. Work order step 6 asked for it to be lowered; this is why it was not.
- **Fail-open baseline:** regenerated. Eight sites in these files left it, and none was added.
- **Gate registry:** new row `impl.adversarial_review_failed`, citing the operator's ADR 0236 acceptance of 2026-10-06. The `impl` halt rows go from 35 to 36, and the ratchet baseline is raised in this PR.
- **Ledger 0908:** all 20 rows marked fixed.

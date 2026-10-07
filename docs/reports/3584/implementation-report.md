# Implementation Report: the deferred-scope audit runs on Gemini through agy and stops loudly (#3584)

## What changed in `tools/audit_deferred_scope.py`

- **Gemini under every profile.** `require_gemini_seat()` resolves the `tools.audit_deferred_scope` seat and refuses, before any call, unless its spec is `gemini:` (ADR 0237). Under the default profile it is `gemini:3.1-pro`; under `claude.toml` it resolves to `claude:opus` and is refused.
- **A failed classification stops the audit.** `_invoke_classifier` no longer catches anything: a raised transport error propagates, and an unsuccessful result raises `AuditFailed` with the spec. An answer that is not JSON raises `AuditFailed` naming the candidate. Nothing is cached for a failed candidate. The `# fail-open:` tag and its swallowing `except Exception` are gone.
- **Every other failure in the tool stops it too.** Each now raises `AuditFailed`:
  - a failed `gh issue list` (it used to print to stdout and `sys.exit(1)`, alerting no one);
  - a failed or non-JSON comment fetch (it used to leave the issue with no comments, so its deferrals were never scanned);
  - a failed or non-JSON state-index fetch (it used to warn and return `{}`, which strips the open/closed annotations from every prompt);
  - a corrupt state-index cache (it used to be skipped silently);
  - a corrupt classification cache (it used to become `{}`).
- **One handler in `main`.** It calls `alert_operator` with the phase, the candidate's issue number and the spec, and returns 1. Reports are written only after every candidate is classified, so a failed run writes none. `_PROGRESS` tracks the phase and candidate for the alert.
- **The cache holds only successes.** An entry carrying an `error`, written before this change, is dropped on load and reclassified.
- **Dead code removed.** `Classification.error`, `Classification.raw_response`, the report's `ERROR` category, and the "errors:" count are gone.
- **The report names the resolved model.** It names the spec and model id in its Auditor, Method and Audit Record lines, where it used to say "Claude Opus 4.7" and `claude --print`. A `--limit` run says it covered only the first N candidates.
- **The module docstring** describes the seat, the refusal and the stop.

## Runbook

`docs/runbooks/0932-deferred-scope-audit.md` is now v1.1:
- the prerequisites are agy and the alert channel, not the `claude` CLI;
- the invocation no longer spells the Projects root;
- phase C names the seat;
- a new "When the Audit Stops" section replaces the ERROR category;
- the cache table adds the state index;
- the costs name agy.

## Loud-failure baseline

Two entries are removed (`_invoke_classifier`'s tag and handler), from 335 to 333, and `BASELINE_CEILING` moves from 335 to 333.

## Loud-failure compliance (standard 0034)

| Site | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| `main`'s handler | `ERROR [ALERT]` on stderr | phase, issue, spec, cause | returns 1, no report | `alert_operator` |
| `require_gemini_seat` | raises `AuditFailed` | the resolved spec | yes | through `main` |
| `_invoke_classifier`, the parse failure, the fetch and cache failures | raise `AuditFailed` | the cause, plus the candidate or file | yes | through `main` |

## The pattern for the sweep (step 5)

The same shape fixes every tool in `tools/`:
1. A tool-local exception class for "this run cannot go on".
2. Every failure site raises it with the cause and what it was working on, never returning a default.
3. Exactly one handler at the entry point calls `alert_operator` and exits 1.
4. Output is written only after the last fallible step, so no partial result exists.
5. Fields and categories that only existed to carry swallowed errors are deleted.
6. The baseline and ceiling come down in the same PR.

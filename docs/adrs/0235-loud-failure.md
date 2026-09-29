# 0235 - Every failure is loud, logged with details, stops dependent processing, and alerts the operator

**Status:** Accepted
**Date:** 2026-09-29

## Context and Problem Statement

For two months, the operator has required that every failure be loud, stop the run, and alert him. The codebase instead accumulated 124 `# fail-open:` tags that swallow exceptions, an adversarial review that failed silently for over a month due to a stale API key (#2926), and unknown LLM providers that return empty error dicts to the graph.

We need a clear standard to judge whether a line of code handles failure correctly. No class of exception is carved out; there are no deliberate fall-throughs.

## Decision

Every failure in AssemblyZero must meet four properties:

1. **Loud:** A failure must not be swallowed. If it is fatal to the process, it must print to `stderr` and the process must exit non-zero. If it happens within the graph or pipeline, it must be raised or returned as a terminal error that halts the graph.
2. **Logged with details:** The failure must be recorded in the run record (`RunRecord`) and the convergence record with its context: the file and line, the exception or error message, the node or stage where it occurred, and the input that caused it.
3. **Stops dependent processing:** A failure stops anything that depends on its output. For a graph node, the graph halts immediately; it does not return an empty output to the next node. For a transport, the call fails; it does not fall back to another transport or an unauthenticated client.
4. **Alerts the operator:** A failure must immediately notify the operator through the established alert channel (`assemblyzero/core/operator_notify.py`). The alert must reach the operator on both Windows and Ubuntu (e.g. via SES email, not just a Windows toast). If the alert itself fails to send, that failure must also be loud (printed to stderr, exiting non-zero, and never swallowed).

The `# fail-open:` convention and its baseline test are retired. A new test will assert that zero tags exist.

## Consequences

- 124 existing `# fail-open:` sites must be fixed to comply with this standard.
- Any future PR that introduces a swallowed exception or un-alerted failure will be rejected.

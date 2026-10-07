# Implementation Report: ADR 0236 (every failure is loud) and ADR 0237 (Gemini only through agy) (#3579, #3582)

## What was written

- `docs/adrs/0236-every-failure-is-loud.md` (#3579) states the four properties: loud, logged with details, stops dependent processing, alerts the operator. Each is defined so a single line of code can be judged against it. The ADR also:
  - names the alert path: `assemblyzero.core.alert.alert_operator`, built on `assemblyzero/core/operator_notify.py`. It sends an SES email, which reaches the operator from Ubuntu as well as Windows, plus a Windows toast. A failed send is itself loud and exits non-zero, and a start-up check refuses a run whose channel cannot work;
  - retires the `# fail-open:` convention and the fail-open baseline test, replaced by #3580's check aiming at zero tags;
  - judges #3579's three evidence sites.
- `docs/adrs/0237-gemini-only-through-agy-no-api-key.md` (#3582) states the rule: `agy` is the only Gemini transport, with no key, no key SDK and no fallback. It says that an unavailable `agy` stops the run under ADR 0236, records what #3672 and #3673 already removed, lists every remaining site for #3583 with file and line, and defines the guard test.

## Acceptance

Both were drafted as Proposed. The operator accepted them on 2026-10-06 at 10:31 PM Central, in session `55a83d74-76d7-4ae2-8fce-20d30173a8fc`: "I accept ADR 0236 and ADR 0237." Both now read Accepted, and the acceptance is recorded on #3579 and #3582. Before accepting, the operator ruled that ADR 0236's start-up check on the alert channel stays.

## Findings filed while drafting

- #3724: `create_halt_node` (`assemblyzero/core/halt_node.py`) calls no alert path, so every graph's `HALT` alerts no one.
- #3725: N7.5 (`assemblyzero/workflows/testing/nodes/adversarial_node.py:148-179`) records a review that cannot run as "skipped", at `WARNING`, and the run continues.

Both are linked from #3581.

## Correction to #3579's evidence

#3579 said no test shows the graph halting after an unknown provider. `route_after_generate_draft` (`assemblyzero/workflows/requirements/graph.py:182`) sends any draft error to `HALT`, and `tests/unit/test_finalize_repair_routing.py` asserts that route. The missing property at that site is the alert alone, and #3724 covers it.

## Not changed

No code. The ADRs bind steps 2 to 6 of #3585, which change the code.

# Test Report — A Defect-Class Registry (#2576)

## Issue Reference
[#2576: a defect-class registry -- name the classes, give each its fixture, make the audit backlog mechanical](https://github.com/martymcenroe/AssemblyZero/issues/2576)

## Suites Run

| suite | result |
|---|---|
| `tests/unit/test_completeness_message_addressability.py` (new) | **19 passed** |
| `tests/unit/test_completeness_pinning_deadlock.py` (class 3's first entry) | passed |
| `tests/unit/test_revision_pinning.py` (the enforcement being classified) | passed |
| `tests/unit/test_fail_open_audit.py` (the #2475 gate) | passed — no new fail-open sites |
| combined run | **101 passed** |
| `ruff check` on both new Python files | clean |

## What Is Actually Pinned

**The classifier itself (7 tests).** Each pins one property the sweep's conclusions rest on:

- A backticked span present in the draft addresses it — the happy path.
- **A token absent from the draft addresses nothing.** Parsing is not addressing; this is what makes #2590 and #2591 findings rather than passes.
- A dashed range inside the draft addresses it (#2555's repair).
- **A bare line number is not an address** — the exact `SyntaxError: ... line 1` string from the original deadlock, asserted to parse as no range at all.
- An out-of-bounds range is reported, not counted.
- An addition demand is its own verdict.
- **Addressed beats demands-addition** — a message that both cites a line and demands an addition resolves as addressed, because a citable line is the stronger guarantee.

**The sweep proper (5 tests).** Each drives a REAL check with a fixture that genuinely fails it. The shared `_classify` helper asserts `passed is False` first, so a fixture that stops failing produces a loud error rather than silently classifying a success message — which would prove nothing.

The five assert current truth, four of them the broken state, each against its filed issue. **Repairing any one flips its test**, which is the signal to move it into `TestAddressableToday`. The `()`-suffix pair is the strongest: two fixtures differing only in the parameter list, asserting opposite verdicts from a byte-identical message.

**Exhaustiveness (2 tests).** `TestTheSweepIsExhaustive` fails when a new `check_*` is neither swept nor declared uncovered, and fails in the other direction when a declared name does not exist. Without the second, the uncovered list would rot into a lie as checks are renamed.

**Vocabulary coverage (5 parameterised tests).** Standard 0029's class-3 entry claims five readable schemes — Section references, backticked spans, quoted phrases, row ids, test names. Each is pinned, so a vocabulary change that drops one makes the standard's claim false and this says so.

## Honest Coverage Statement

Four of eleven completeness checks are swept. Seven are declared uncovered with a per-check reason, tracked in #2594. This is stated in the audit, in the standard's backlog table, and enforced by a test — not left implicit.

## Regression Risk

Additive. `message_addressability.py` is a new module nothing else imports; it reads `revision_pinning`'s public functions without modifying them. The registry and audit are documentation. No existing behaviour changed, which the 101-test combined run confirms.

# 0905 — Completeness message addressability sweep (2026-08-28)

**Audit:** #2557, executed as a class sweep under #2576
**Registry class:** 3 — the demanded change is never refusable (`docs/standards/0029-defect-class-registry.md`)
**Program:** `tests/unit/test_completeness_message_addressability.py` (19 tests)
**Classifier:** `assemblyzero/workflows/implementation_spec/message_addressability.py`

This audit is a program. It re-runs on every suite, drives each check with a
fixture that genuinely fails it, and classifies the **real emitted message** —
no message text is hardcoded, so a rewording that drops an address changes the
verdict and fails the suite the day it is written.

## The question

The invariant repaired by #2555 and #2558 — *a change a completeness failure
demands is never revertible by pinning in the same round* — holds mechanically
only for complaints the enforcement can READ. So, per check:

> Does `named_tokens(message) | named_line_ranges(message)` address at least
> one line of the draft the message is complaining about?

## The taxonomy is three-way

The sweep's first finding is about the question itself. Classifying messages as
addressable-or-not produces false alarms, because a third case is correct:

| verdict | meaning | is it a defect |
|---|---|---|
| **addressed** | the message cites a line of the draft | no |
| **demands-addition** | it demands NEW content; there is no line to cite by construction, and #2560's exemption carries it | no |
| **unaddressable** | it targets EXISTING content in a scheme the vocabulary cannot read | **yes — the deadlock class** |

Collapsing the middle case into the third would have reported #2560's correctly
exempted messages as defects. The classifier resolves `addressed` first: a
citable line is the stronger guarantee, and the addition exemption is a
fallback rather than an equal alternative.

## Results

Four of eleven checks swept. **All four classified unaddressable**, each filed.

**Update 2026-08-28:** #2590 is **repaired** — the backticked span now carries
the bare name, so the parameterised case addresses its target. The row below
records the sweep's finding as measured; the verdict column carries the
current state.

| check | verdict | finding |
|---|---|---|
| `check_functions_have_io_examples` (parameterised fn) | ~~unaddressable~~ → **addressed** | #2590, fixed |
| `check_functions_have_io_examples` (zero-arg fn) | addressed | — |
| `check_modify_files_have_excerpts` | unaddressable | #2591 |
| `check_change_instructions_specific` | unaddressable | #2592 |
| `check_manifest_traceability` | unaddressable | #2593 |
| seven checks not swept | declared uncovered | #2594 |

### The sharpest finding (#2590)

`check_functions_have_io_examples` backticks the name with a `()` suffix. Two
drafts differing **only** in the parameter list:

| draft | token parsed | draft lines addressed | verdict |
|---|---|---|---|
| `def compute_needle_angle(value, redline):` | `compute_needle_angle()` | none | **unaddressable** |
| `def compute_needle_angle():` | `compute_needle_angle()` | line 5 | addressed |

The emitted message is byte-identical in both cases. Whether the complaint can
be acted on depends on whether the function happens to take arguments — and
the broken case is the ordinary one. This is #2555's deadlock shape on a check
that fires on routine specs rather than on an exotic fence condition.

**Repaired 2026-08-28.** The span now carries the bare name, which every `def`
line contains verbatim. Verifying the fix sharpened the diagnosis: the
deadlock is **shape-dependent**, because `enforce_pinning` passes insertions
through by design. Driven against the real enforcement, a fix that inserted a
line above `pass` always survived; only fixes that **replaced** existing lines
(`pass` → example + `return`, or a docstring rewrite) were reverted. That is
still the ordinary case — replacing `pass` is the natural way to give a stub
an example — but a fixture built on the insertion shape would have passed
before the repair and proved nothing. `test_completeness_pinning_deadlock.py`
uses the replacement shape for exactly this reason.

### The vocabulary gap under #2591

`_ADDITION_DEMAND_RE` recognises exactly three phrases — `have no test`,
`add a test`, `owes each a test` — all about tests. The regex encodes "an
addition means a test", which was true when #2560 was written and is not true
generally: an excerpt, a code block and a data-structure example are all
additions with no line to cite. Every non-test addition demand therefore falls
into the unaddressable bucket by default. This is a family, not one message,
which is why #2591 proposes widening the vocabulary as the honest fix.

### One finding is a ruling, not a repair (#2592)

`check_change_instructions_specific` is a **density heuristic** — it counts
fences against a line-count threshold — and it parses nothing at all from its
own message. #2540 asks whether such proxies should veto. A proxy that cannot
address its own complaint can only ever deadlock, so this finding is evidence
for that discussion, and #2592 says explicitly it should not be fixed in
isolation before #2540 is ruled.

## Coverage, stated honestly

Seven of eleven checks are **declared uncovered**, not silently skipped: they
need a real repo tree, a populated symbol table, or a pass-criteria table that
parses. `TestTheSweepIsExhaustive` fails if a new check is neither swept nor
declared, and fails again if a declared name does not exist — so the gap cannot
widen silently and the list cannot rot. #2594 carries the extension.

With a base rate of four unaddressable messages in four classified, the
remaining seven should not be assumed healthy.

## What this proves about the registry shape

The acceptance for #2576 asks that one backlog audit be executed AS a class
sweep, to prove the shape works. It does, and specifically:

- **The detection question did the work.** "Does this complaint name its edit
  target in a vocabulary the enforcement can read, and does that name actually
  occur in the draft?" is answerable mechanically, and the second half is what
  caught #2590 and #2591 — both parse tokens fine and address nothing.
- **The fixture shape transferred unchanged** from the class's first entry
  (`test_completeness_pinning_deadlock.py`) to eleven new sites.
- **The sweep corrected the class entry.** The three-way taxonomy was
  discovered by running it, and is now written into standard 0029 so the next
  sweep starts with it rather than rediscovering it.

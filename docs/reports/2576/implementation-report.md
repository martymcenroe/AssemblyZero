# Implementation Report — A Defect-Class Registry (#2576)

## Issue Reference
[#2576: a defect-class registry -- name the classes, give each its fixture, make the audit backlog mechanical](https://github.com/martymcenroe/AssemblyZero/issues/2576)

## Files Changed
- `docs/standards/0029-defect-class-registry.md` (new): the registry — eight classes.
- `assemblyzero/workflows/implementation_spec/message_addressability.py` (new): the classifier the #2557 sweep runs on.
- `tests/unit/test_completeness_message_addressability.py` (new): the sweep, as a program — 19 tests.
- `docs/audits/0905-message-addressability-sweep-2026-08-28.md` (new): the sweep's findings.

## The Registry

Eight classes, each with: the invariant it protects, a detection question answerable against a diff or a halt without knowing the history, the canonical fixture shape, and every known instance.

1. A zero needs a denominator (#2546, #2552, #2575)
2. Attribution requires the enforcement record (#2556, #2561, #2574)
3. The demanded change is never refusable (#2555, #2560, #2557)
4. Conservation through transformation (#2559, #2563)
5. The input/litter distinction (#2551, #2144, #2571)
6. Fail-open must be declared (#2475, #2508, #2575)
7. The once-under-load flake (#2522, #2538)
8. A resume inherits, never rediscovers (#2551, #2552, #2514, #2570)

Seven were named in the issue. **The eighth was added by the 2026-08-28 update** after #2570 landed: three defects the campaign fixed separately were one class wearing different artifacts, and the resume contract is the machinery that closes it.

The bar for a new class is **two independent instances**. One is a bug; a class claims the shape recurs, and that claim needs evidence.

## The Sweep (#2557, the acceptance proof)

The issue requires one backlog audit executed AS a class sweep. #2557 was chosen as the smallest.

**Design decision — the taxonomy is three-way, not two.** Classifying messages as addressable-or-not would report #2560's correctly-exempted messages as defects. A complaint is *addressed* (cites a line), *demands an addition* (no line to cite by construction; #2560's exemption carries it), or *unaddressable* (targets existing content in an unreadable scheme). Only the third is a defect. This was discovered by running the sweep and is now written back into the class entry, so the next sweep starts with it.

**Design decision — parsing is not addressing.** A backticked span the draft does not contain parses fine and unlocks nothing. `addresses_draft` requires the token to actually OCCUR in the draft. This second half is what caught #2590 and #2591; a classifier checking only "does the vocabulary parse something" would have passed both.

**Design decision — out-of-bounds ranges are reported, not counted.** A cited range past the end of the draft is worse than no citation: it reads as an address and unlocks nothing. It is surfaced separately rather than folded into the verdict.

**Design decision — the sweep declares what it does not cover.** Seven of eleven checks need a real repo tree, a populated symbol table, or a parseable pass-criteria table. They are named in an explicit `uncovered` set, and `TestTheSweepIsExhaustive` fails both when a new check is neither swept nor declared AND when a declared name does not exist — so the gap cannot widen silently and the list cannot rot.

## Findings

Four of four classified checks are unaddressable — filed as #2590, #2591, #2592, #2593, with coverage tracked in #2594. Each cites registry class 3.

The sharpest is #2590: `check_functions_have_io_examples` backticks `name()`, and a function taking parameters never contains that literal. Two drafts differing only in the parameter list produce a byte-identical message, one addressable and one not — and the broken case is the ordinary one.

#2592 is deliberately filed as a **ruling**, not a repair: the check is a density heuristic, and #2540 asks whether proxies should veto at all. A proxy that cannot address its own complaint can only deadlock, so the two should be ruled together.

## Known Limitations

- Seven of eleven checks unswept (#2594). With four unaddressable in four classified, the rest should not be assumed healthy.
- The registry's backlog table lists #2508 and #2540 as unconverted; only #2557 was executed here.

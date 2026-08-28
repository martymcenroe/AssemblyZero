# Implementation Report — The IO-Example Complaint Addresses Its Target (#2590)

## Issue Reference
[#2590: the io-examples complaint backticks name() -- a function with parameters never contains that literal, so it addresses nothing](https://github.com/martymcenroe/AssemblyZero/issues/2590)

Registry class 3 — the demanded change is never refusable (`docs/standards/0029-defect-class-registry.md`).

## Files Changed
- `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py`: one line — the backticked span drops the call parens.
- `tests/unit/test_completeness_pinning_deadlock.py`: the issue's table as fixture, plus the end-to-end class-3 property (6 tests).
- `tests/unit/test_completeness_message_addressability.py`: the pinned known-gap test moves from `TestUnaddressableToday` to `TestAddressableToday`, fixture unchanged.
- `docs/audits/0905-message-addressability-sweep-2026-08-28.md`: the sweep's #2590 row corrected, and the sharpened diagnosis recorded.

## The Fix

```python
# before
func_list = ", ".join(f"`{f}()`" for f in missing_examples[:5])
# after
func_list = ", ".join(f"`{f}`" for f in missing_examples[:5])
```

`named_tokens` parses what sits inside backticks verbatim, so `compute_needle_angle()` — parens included — occurs in a draft only when the function happens to take no arguments. The bare name appears verbatim in every `def` line.

**Parens dropped rather than a second span added.** The sentence already says "Functions", so the call form earned nothing, and a second `` `name()` `` span would parse as a token matching nothing. **Loosening `named_tokens` to strip trailing parens was rejected** — that vocabulary is shared by every complaint, and a looser token matches more than it should.

## Verification Before The Code

**The table reproduces exactly.** Real check, real `named_tokens`: with parameters → token `compute_needle_angle()`, zero lines addressed, unaddressable. Zero-arg → line 5 addressed. Byte-identical message.

**The diagnosis was sharpened, not refuted.** The issue says "the drafter adds the example, `enforce_pinning` reverts it". That is true for **replacement**-shaped revisions only — enforcement passes insertions through by design ("adding is not un-fixing"). Driven against the real enforcement:

| revision shape | refusals (before fix) | example survived |
|---|---|---|
| insert a comment above `pass` | 0 | yes |
| replace `pass` with example + `return` | 1 | **no** |
| replace `pass` with docstring + `return` | 1 | **no** |
| prose example above the `def` | 0 | yes |

Still the ordinary case — replacing `pass` is the natural way to give a stub an example — but a fixture built on the insertion shape would have passed before the repair and proved nothing. The fixture uses the replacement shape for exactly this reason. Posted to the issue before any code changed.

**The `()` suffix is not shared.** Checked before touching anything, per the cross-read instruction: line 911 was the only paren-suffixed backtick span in the package; every other site formats `` `{x}` `` bare. The reword is local, and **#2591–#2594 are unaffected** — nothing to note on a sibling.

**The fix does not over-unlock.** `_blocks` splits per `def` only inside fences, so the fenced shape is where scoping is testable. With the bare name, the named function's block unlocks (lines 6–9) and a sibling function meddled with in the same round is **still reverted**.

## The #2540 Ruling, Honoured

Ratified 2026-08-28: proxies advise, facts gate. `functions_have_io_examples` is a fact-verifier — an example exists or it does not — so it **stays a hard gate**. This change is to its addressability, not its authority. Nothing was demoted.

## Known Limitations

None for this check. The three sibling unaddressable complaints (#2591, #2593) and the proxy ruling that subsumes #2592 remain open and untouched, as instructed.

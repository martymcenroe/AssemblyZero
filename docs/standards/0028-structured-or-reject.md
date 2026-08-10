# 0028 — Ask structured, get structured, or reject

**Status:** Active
**Issue:** #2202 (the ruling), #2203 (the implementation that landed it)

**A structured ask is a contract, and a contract violated is rejected — never
guessed around.** This is the operator's ruling, made 2026-08-10, and it is
absolute: regex is not a safety fallback. A parser that cannot read its input
raises; a system that quietly degrades to pattern-scraping and hands back a
guess is worse than one that stops, because the guess is trusted.

## 1. The contract

When the pipeline asks a model for schema-constrained output (the providers
send `response_schema` / `json_schema` on every such ask), the response
either parses as JSON and validates against that schema — required keys,
enum membership — or the ask is **rejected**:

- The parser raises `StructuredContractError` (never returns a degraded
  value), carrying the parser's name, the reason, and a bounded excerpt of
  the response — a halt banner must be legible (#2197).
- The node surfaces the rejection as its error; the **stage retry machinery
  is the bounded re-ask**. No bespoke retry loops, no scraping.
- After the stage's attempts are spent, the run halts loudly, naming the
  contract that was violated.

Rejection is cheap by construction: schema-enforced asks rarely violate, and
one re-ask costs seconds against the hours a masked defect costs.

## 2. Recovering JSON is not scraping

Models wrap JSON in ```json fences or a sentence of prose (#1843). Stripping
delimiters to reach a JSON object that must still pass `json.loads`, key
validation, and enum validation is **JSON recovery** — the contract is still
enforced by the schema, and nothing can be hallucinated into existence.
Extracting *meaning* from non-JSON text with patterns is **scraping**, and it
is banned from every structured contract.

## 3. Scanning our own documents is not parsing model output

Deterministic checks of the pipeline's OWN artifacts — the `## Open
Questions` checkbox section a template defines, a residual-TODO scan of a
finalized document — are document-structure scans (`scan_open_questions_
section`, `scan_residual_questions`), implemented with string operations,
named as scans, and never framed as fallbacks. They cannot mask a contract
failure because there is no contract: the document is what it is.

One ask, one contract: a call whose prompt demands a markdown document must
not simultaneously carry a JSON response schema (the drafter carried both
for months; the schema fought the prose and the questions "parse" failed on
every draft by construction).

## 4. A parse failure is never a value

No function returns an empty result, an `UNKNOWN`, or a silent downgrade
because it could not read its input. It raises, and the caller decides —
loudly. The pre-0028 codepaths that mapped garbage to `UNKNOWN → REVISE →
BLOCKED` turned format errors into review outcomes.

## Origin

2026-08-09/10, the boostgauge campaign. The reviewer's structured verdict
parsed perfectly — and the node then regex-parsed a re-rendering of it that
had dropped the very field being sought, ruled the inevitable empty result
"UNANSWERED", and discarded twelve APPROVED LLDs across eight days (#2199).
The regex fallback did not provide resilience; it provided silence. The
operator's ruling, paraphrased: regex fallbacks are at the heart of failed
systems — if we ask for structured and don't get structured, we reject.

## Reference

- `assemblyzero/core/verdict_schema.py` — `StructuredContractError`, the
  strict parsers, the document scanners.
- #2199 — the incident and its counted blast radius.
- #2200 — the lossy-revision amplifier (separate, still governed by this
  standard's §3 once revisions edit rather than regenerate).
- Standard 0027 — the same refuse-loudly posture, applied to janitors.

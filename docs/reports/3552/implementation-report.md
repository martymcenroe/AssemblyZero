# Implementation Report: every artifact that put Claude in a seat is corrected to the 2026-09-24 law (#3552)

## What was asked

The operator's law, 2026-09-24 about 11:20 PM Central: Gemini in agy drafts and Gemini in agy validates, both seats, both workflows, Claude out of both for Anthropic budget reasons. He ordered every artifact carrying the older wording found and corrected. #3552 is the ledger; this PR is the correction.

## What changed

| File | Change |
|---|---|
| `tools/run_requirements_workflow.py`, `tools/run_implement_from_lld.py` | unchanged here: #3517 (PR #3555, `532dc07f`) landed the same defaults first, with its own help text, and kept `--drafter claude:sonnet --reviewer claude:opus` as the docstring's override example. This branch's copies were stashed by name, compared, and dropped |
| `assemblyzero/core/config.py` | `REVIEWER_MODEL` defaults to `gemini-3.1-pro-high`, the id the agy transport accepts (`DEFAULT_PROBE_MODEL` already used it); `REVIEWER_MODEL_FALLBACKS` is empty. `CLAUDE_MODEL` is untouched. A bare `GeminiClient()` no longer raises, which closes the #3541 class at its source; the LLD status stamp in `requirements/audit.py` now records the Gemini reviewer |
| `assemblyzero/core/preflight.py` | the module docstring states the law; the probe-model comment no longer describes `REVIEWER_MODEL` as a Claude id. #3555 had already rewritten the `preflight_for_specs` docstring |
| `assemblyzero/core/capacity.py` | the quoted preflight docstring updated |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py` | docstring: the drafter is Gemini in agy by default |
| `docs/adrs/0234-gemini-in-agy-drafts-and-validates.md` | new, Proposed: the decision, the seat table, what it does not change (ADR 0220, ADR 0232 and ADR 0233, both Accepted, #2927), consequences, provenance. The N7.5 row records #2926 as landed (PR #3556), and the coder row records the operator's 11:50 PM ruling that the coder moves too (#3553, #3562) |
| `docs/adrs/0208-llm-invocation-strategy.md` | status line says superseded in part by ADR 0234; the Claude CLI row, the "Gemini: Adversarial Review Only" section, and the two Positive bullets that rested on Claude drafting are marked superseded; two retired `gemini:3-pro-preview` example ids replaced |
| `docs/skills/0601-gemini-dual-review.md`, `docs/runbooks/0907-unified-requirements-workflow.md`, `docs/runbooks/0904-issue-governance-workflow.md`, `docs/reverse-engineering/*.md`, `docs/lld/drafts/spec-0305-implementation-readiness.md` | every "Claude drafts" line and every `claude:opus-4.5` drafter example now names Gemini; the retired `gemini:3-pro-preview` id replaced with `gemini:3.1-pro` wherever it appeared as an example |
| `wiki/The-Pipeline.md`, `wiki/Gemini-Verification.md`, `wiki/Safety-and-Guardrails.md`, `wiki/End-to-End-Orchestration.md` | same |
| `tests/unit/test_preflight_transport.py` | two docstrings that described the old defaults as current now date them |
| `tests/unit/test_the_law_gemini_in_both_seats.py` | new: asserts no seat argument in the three standalone tools (the LLD tool, the implementation tool, the spec tool) defaults to `claude:`, and walks `docs/`, `wiki/`, `tools/`, `assemblyzero/` for the ledger's closed phrase list by substring (never regex), excluding `done/`, `lineage/`, `reports/`, the lessons files, and the quotes wiki page |

## Read and left alone, by rule

- `wiki/Claudes-World.md:209`: an email Claude drafted for another system. Not a seat.
- `docs/workflow-lessons-learned-1.md`: a past run's draft-file listing; lessons files are append-only.
- Everything under `ideas/done/`, `docs/lld/done/`, `docs/lineage/done/`, `docs/reports/done/`: historical.
- `assemblyzero/visual_gate/modify.py:126-133`: a comment narrating why #2521 failed when `REVIEWER_MODEL` was a Claude id. History; still true of that day.
- `tests/unit/test_requirements_cli.py:201-216`, `test_requirements_config.py:165`, `test_requirements_gate_escalation.py`, the telemetry tests: Claude specs as test data, not defaults.

## Outside this tree

- Issue bodies #3502 and #3517 still carry the old sentence; the supervising session's edit was denied by its permission classifier, so the law sits on each as a comment and the body edit is the operator's.
- `Projects/AssemblyZero-scheduled/` is an independent clone; pull after this lands.
- #2926 (the N7.5 transport) was authorized by the operator and landed in PR #3556 while this branch was open; this PR does not touch it.
- The coder seat (#3553) is not changed here; it lands with the runtime model profile (#3563, under #3562).

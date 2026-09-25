# ADR 0234: Gemini in agy drafts and validates

**Status:** Proposed (the operator gave the rule; he accepts the record)
**Date:** 2026-09-24
**Deciders:** Operator
**Supersedes in part:** ADR 0208 (LLM Invocation Strategy), the Claude-drafts half
**Related:** ADR 0220 (agy transport), ADR 0232 (nested Claude calls load no user hooks; Accepted 2026-09-24), ADR 0233 (agy tool-execution posture; Accepted 2026-09-24), #3517, #3552, #3553, #2926, #3562

---

## Decision

**Gemini, reached through `agy`, holds both model seats in every AssemblyZero workflow: it drafts and it validates.** Claude holds no seat.

The operator gave this rule on 2026-09-24 at about 11:20 PM Central, in these terms: Gemini in agy drafts, and Gemini in agy validates. Both seats, both workflows. The reason he gave is budget: his Anthropic account is constrained, and his Antigravity credit balance is large.

## What it changes

| Seat | Before | Now |
|---|---|---|
| LLD and issue drafter (standalone `--drafter`) | `claude:sonnet` | `gemini:3.1-pro` |
| LLD and issue reviewer (standalone `--reviewer`) | `claude:opus` | `gemini:3.1-pro` |
| Implementation test-plan reviewer (standalone `--reviewer`) | `claude:opus` | `gemini:3.1-pro` |
| Implementation adversarial reviewer (N7.5) | provider discovery that falls back to the paid API (#2926) | `get_provider("gemini:3.1-pro")`; the operator authorized #2926 on 2026-09-24 and it landed in PR #3556 |
| Implementation code-writing seat | Claude CLI, no spec parameter | `gemini:3.1-pro`; the operator ruled at about 11:50 PM Central that the coder moves too (#3553), and it becomes the `impl.code` and `impl.code.small` seats of the runtime model profile (#3562) |
| Orchestrator, every stage | `gemini:3.1-pro` in both seats already | unchanged; the orchestrator was already the intended state |

ADR 0208's premise of "different model families catch different mistakes" is withdrawn as a requirement. The operator weighed it against cost and chose cost. ADR 0208's second premise, zero marginal cost for Claude drafting, no longer holds.

## What it does not change

- ADR 0220: `agy` is the only transport to Gemini. No API key path is reachable from any seat, and `FORBIDDEN_MODELS` still fences retired model ids.
- ADR 0233 (Accepted): `agy` runs with `--sandbox`, cannot run a shell inside the workflow, and can still write files at any path the operator's account can write. The operator gave this rule with that finding in view. It is recorded, and it is not reopened by this ADR.
- #2927's standing rule: nothing on the Gemini-path inventory executes until the operator says so. #2926 was on that inventory; the operator authorized it separately, and this ADR authorizes nothing else on it.
- ADR 0232 (Accepted): a nested `claude -p` call loads no user hooks. It still governs every run that names a Claude spec.
- An operator may still pass Claude specs explicitly. The preflight (#3506) skips the Gemini transport check for such a run. The law sets the defaults and the documented posture; it does not remove the flag.

## Consequences

- Every run spends Antigravity credits and no Anthropic tokens by default.
- The LLD and issue workflows are single-family: the same model drafts and reviews. The operator accepts that trade.
- The `agy` transport is now on every run's critical path; a machine without `agy` logged in cannot draft. The preflight reports that as a transport failure before N1.
- Every document, runbook, wiki page, test, and default that described Claude in a seat is corrected in #3552, and a guard test keeps them corrected.

## Provenance

Recorded by the supervising session from the operator's words, 2026-09-24. The operator's earlier direction that day, which put Claude in the drafter seat with agy in both adversarial roles, is superseded by this rule; the earlier wording survives only in append-only logs, each carrying a dated correction.

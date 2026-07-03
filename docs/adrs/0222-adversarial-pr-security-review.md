# 0222 - Mandatory Adversarial Security Review for Inbound Pull Requests

**Status:** Accepted (stub — to be expanded as the practice is exercised)
**Date:** 2026-07-03
**Supersedes:** none
**Related:** ADR-0216 (PAT scope exclusion / in-process classic-PAT), [Closing the Agent Self-Authorization Loop](https://github.com/martymcenroe/AssemblyZero/wiki/Closing-the-Agent-Self-Authorization-Loop), [OWASP LLM & Agentic Top 10](https://github.com/martymcenroe/AssemblyZero/wiki/OWASP-LLM-and-Agentic-Top-10) (LLM03 Supply Chain, LLM09 Misinformation, ASI04 Agentic Supply Chain, ASI09 Human-Agent Trust)

---

## Context

AssemblyZero is a public repository and receives pull requests from external forks. Automated governance — pr-sentinel's issue-reference check plus separate-identity approval (Cerberus), gated by branch protection (ADR-0216) — establishes **authorization**: it proves a change is allowed to merge and that an agent cannot approve its own work.

It does **not** establish **safety**. As the governance boundary is stated elsewhere, the pipeline "validates the authorization model around a change, not the semantic correctness of the change itself." A syntactically valid, correctly-referenced, CI-green PR can still carry a subtle logic inversion, a silently weakened test, an obfuscated payload, a supply-chain alteration, or a CI change that exfiltrates secrets. None of those is caught by a passing check.

The agentic threat model makes this concrete: a contribution is an attacker-controllable input that asks the maintainer to execute code and extend trust; a clean first contribution can be reputation-laundering ahead of a later malicious one; and the most dangerous change is the one engineered to look harmless. Merging on green CI alone is therefore insufficient.

## Decision

**Every inbound pull request undergoes a mandatory, multi-layer adversarial security review before it is eligible for merge, with heightened rigor for external and fork contributions. No pull request is merged on passing CI alone.**

- The review **assumes hostile intent until the change proves otherwise.** A clean result is the conclusion of the review, never its starting assumption.
- Changes that touch the control plane receive the deepest scrutiny.
- **The review methodology itself — its layers, heuristics, and indicators — is maintained privately and is deliberately not published.** Publishing it would hand a would-be adversary the exact criteria to engineer around. This ADR records that the control exists and is mandatory; it does not describe how the control works. Stating that the wall exists is a deterrent; publishing its blueprint is a gift to whoever wants to climb it.

## Consequences

- Passing CI (pr-sentinel + separate-identity approval) is **necessary but not sufficient** for merge. The adversarial review is an additional, human-gated safety layer sitting on top of the authorization layer.
- External / fork PRs are never auto-approved — fork-triggered workflows do not receive repository secrets, so the approval identity cannot act on them — and always require the review before merge.
- The public surface carries the **policy** (for deterrence and governance transparency); the method is held privately. This split is intentional and is the security posture, not an omission.
- This is a stub. It will be expanded as the review is exercised across the fleet's public repositories.

# 0207 - ADR: Single-Identity Orchestration

**Status:** Implemented
**Date:** 2025-12-29
**Categories:** Process, Cost Optimization, Security

## 1. Context
Modern AI-assisted development involves multiple LLMs (Gemini, Claude, ChatGPT).
* **Cost:** Assigning unique GitHub accounts to each "bot" requires paid seats ($4/mo/user) or managing multiple free accounts.
* **Friction:** Managing auth tokens, SSH keys, and logins for multiple identities slows down the "Flip Turn" workflow.
* **Security:** More accounts = larger attack surface.

## 2. Decision
**We will operate under a Single-User Orchestration model where the human (Marty) authenticates all commits.**

AI agents function as "Bespoke Consultants" who generate CLI instructions, but `martymcenroe` is the sole executor and committer.

## 3. Alternatives Considered

### Option A: Single Human Identity — SELECTED
**Pros:**
- **Zero Cost:** No extra GitHub seats.
- **Speed:** No relogging/auth switching.
- **Accountability:** Human accepts legal liability for all code pushed.

**Cons:**
- **Attribution:** git history doesn't explicitly show "Gemini wrote this." (Mitigated by commit message convention).

### Option B: Bot Accounts
**Pros:**
- Clear authorship in git blame.

**Cons:**
- Costs money.
- High management overhead.

## 4. Rationale
Speed and frugality are paramount. The "human-in-the-loop" is legally required for code generation anyway; explicit bot accounts add friction without adding value.

## 5. Security Risk Analysis
| Risk | Impact | Likelihood | Severity | Mitigation |
|------|--------|------------|----------|------------|
| AI hallucinates destructive command | High | Med | High | Human MUST read before executing. "Plan Before Execute" protocol. |
| AI commits secrets | High | Low | Med | Standard pre-commit hooks (future). |

## 6. Consequences
- **Positive:** Streamlined workflow, zero marginal cost for new agents.
- **Negative:** Loss of granular "which AI wrote this line" history (mitigated by session logs).

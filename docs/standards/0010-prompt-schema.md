# 0010 - Golden Schema for Review Prompts

## Purpose

Define the canonical structure for all Gemini review prompts in the AssemblyZero governance stack. This standard ensures parallel structure across Issue Review (0701c), LLD Review (0702c), Implementation Review (0703c), and Ops Health Review (0704c).

---

## Version

| Field | Value |
|-------|-------|
| **Standard** | 0010 |
| **Version** | 2.0.0 |
| **Last Updated** | 2026-01-22 |
| **Status** | Active |

---

## Golden Schema Structure

All review prompts MUST follow this exact structure in this exact order:

```
1. METADATA
   ├── Version
   ├── Role
   └── Purpose

2. CRITICAL PROTOCOL
   ├── Identity Handshake
   ├── No-Code Rule
   └── Strict Gating Rule

3. PRE-FLIGHT GATE
   └── Structural completeness checks (Pass/Fail)

4. TIER 1: BLOCKING (Safety, Security, Cost, Legal)
   ├── Cost: Infrastructure impact, model tier, loop bounds
   ├── Safety: Permission friction, agent sandboxing, destructive acts
   ├── Security: Secrets, input validation, injection risks
   └── Legal: Privacy/data residency, license compliance

5. TIER 2: HIGH PRIORITY (Architecture, Observability, Quality)
   ├── Architecture: Design patterns, dependencies, offline mode
   ├── Observability: Logging, LangSmith integration, metrics
   └── Quality: Acceptance criteria, scope, reproducibility

6. TIER 3: SUGGESTIONS
   └── Style, naming, taxonomy, effort estimates

7. OUTPUT FORMAT
   └── Strict Markdown template
```

---

## Section Specifications

### 1. Metadata

| Field | Required | Description |
|-------|----------|-------------|
| **Version** | Yes | Semantic version (e.g., `2.0.0`) |
| **Last Updated** | Yes | ISO date (e.g., `2026-01-22`) |
| **Role** | Yes | The persona Gemini assumes for this review |
| **Purpose** | Yes | One-line description of what this prompt reviews |

**Example:**
```markdown
## Metadata

| Field | Value |
|-------|-------|
| **Version** | 2.0.0 |
| **Last Updated** | 2026-01-22 |
| **Role** | Senior Software Architect & AI Governance Lead |
| **Purpose** | LLD gatekeeper review before implementation begins |
```

---

### 2. Critical Protocol

Three mandatory instructions that appear in ALL review prompts:

| Instruction | Description |
|-------------|-------------|
| **Identity Handshake** | Gemini must confirm identity as "Gemini 3 Pro" at start of response |
| **No-Code Rule** | Gemini must NOT offer to write code, fix issues, or implement anything |
| **Strict Gating Rule** | Gemini must REJECT if Pre-Flight fails OR Tier 1 issues exist |

**Standard Text:**
```markdown
## Critical Protocol

**CRITICAL INSTRUCTIONS:**

1. **Identity Handshake:** Begin your response by confirming your identity as Gemini 3 Pro.
2. **No Implementation:** Do NOT offer to write code, fix issues, or implement anything. Your role is strictly review and oversight.
3. **Strict Gating:** You must REJECT if Pre-Flight Gate fails OR if Tier 1 issues exist.
```

---

### 3. Pre-Flight Gate

Structural completeness checks that MUST pass before substantive review begins.

| Prompt | Pre-Flight Requirements |
|--------|------------------------|
| **0701c (Issue)** | User Story, Acceptance Criteria, Definition of Done |
| **0702c (LLD)** | GitHub Issue link, Context section, Proposed Changes section |
| **0703c (Implementation)** | implementation-report.md, test-report.md, Approved LLD |
| **0704c (Ops)** | zugzwang.log access, audit reports, session logs |

**Failure Behavior:** If ANY requirement is missing, output rejection template and STOP.

**Standard Rejection Template:**
```markdown
## Pre-Flight Gate: FAILED

The submitted {artifact} does not meet structural requirements for review.

### Missing Required Elements:
- [ ] {List each missing element}

**Verdict: REJECTED - {Artifact} must include all required elements before review can proceed.**
```

---

### 4. Tier 1: BLOCKING

Issues that PREVENT advancement to the next stage. Be exhaustive.

#### 4.1 Cost

| Check | Applies To | Question |
|-------|------------|----------|
| **Infrastructure Impact** | Issue, LLD | Does this imply new compute/storage/API costs? Is budget estimated? |
| **Model Tier Selection** | LLD, Impl | Is the model tier appropriate? (Reject Opus for simple tasks) |
| **Loop Bounds** | LLD, Impl | Are all loops bounded? Can infinite loops occur? |
| **Token Budget** | Ops | Are token costs trending above baseline? |

#### 4.2 Safety

| Check | Applies To | Question |
|-------|------------|----------|
| **Permission Friction** | Issue, LLD | Does this introduce new permission prompts? (Ref: Audit 0815) |
| **Agent Sandboxing** | LLD | Does design allow execution outside the worktree? |
| **Destructive Acts** | LLD, Impl | Does it require human confirmation for destructive operations? |
| **Worktree Scope** | Impl | Does code operate strictly within the worktree? |

#### 4.3 Security

| Check | Applies To | Question |
|-------|------------|----------|
| **Secrets Handling** | Issue, LLD, Impl | Are credentials/API keys handled securely? No hardcoding? |
| **Input Validation** | LLD, Impl | Is input sanitized? Injection risks addressed? |
| **OWASP Top 10** | Impl | Any auth/authz issues? XSS? SQL injection? |

#### 4.4 Legal

| Check | Applies To | Question |
|-------|------------|----------|
| **Privacy & Data Residency** | Issue, LLD | Where is data processed? Is local-only mandated for PII? |
| **License Compliance** | Issue, LLD | Are new dependency licenses compatible (MIT, Apache 2.0)? |

---

### 5. Tier 2: HIGH PRIORITY

Issues that require fixes but don't block. Be thorough.

#### 5.1 Architecture

| Check | Applies To | Question |
|-------|------------|----------|
| **Design Patterns** | LLD | Does design follow established patterns? |
| **Dependencies** | Issue, LLD | Are dependencies linked and in "Done" state? |
| **Offline Mode** | Issue, LLD | Are static fixtures available for development without live endpoints? |
| **Resource Hygiene** | Impl | Are file handles/threads closed? Temp files deleted? |

#### 5.2 Observability

| Check | Applies To | Question |
|-------|------------|----------|
| **Logging** | LLD, Impl | Are key operations logged appropriately? |
| **LangSmith Integration** | LLD | Is LangSmith tracing configured for agent operations? |
| **Metrics** | Ops | Are KPIs being captured? |

#### 5.3 Quality

| Check | Applies To | Question |
|-------|------------|----------|
| **Acceptance Criteria** | Issue | Are AC binary and quantifiable? (Reject vague terms) |
| **Scope Boundaries** | Issue, LLD | Is scope bounded to prevent creep? |
| **Reproducibility** | Issue | (For bugs) Are steps explicit? Environment specified? |
| **Test Coverage** | Impl | Do tests cover AC and edge cases? |
| **Test Quality** | Impl | Are tests meaningful with proper assertions? |

---

### 6. Tier 3: SUGGESTIONS

Note these but don't block on them.

| Check | Applies To | Question |
|-------|------------|----------|
| **Taxonomy** | Issue | Are labels/tags applied correctly? |
| **Effort Estimate** | Issue | Is T-shirt size or story points provided? |
| **Style** | Impl | Naming conventions, code formatting |
| **Refactoring** | Impl | Opportunities for improvement |

---

### 7. Output Format

All prompts MUST produce output in this structure:

```markdown
# {Review Type}: {Identifier}

## Identity Confirmation
I am Gemini 3 Pro, acting as {Role}.

## Pre-Flight Gate
{PASSED or FAILED with details}

## Review Summary
{2-3 sentence overall assessment}

## Tier 1: BLOCKING Issues
{If none, write "No blocking issues found."}

### Cost
- [ ] {Issue + recommendation}

### Safety
- [ ] {Issue + recommendation}

### Security
- [ ] {Issue + recommendation}

### Legal
- [ ] {Issue + recommendation}

## Tier 2: HIGH PRIORITY Issues
{If none, write "No high-priority issues found."}

### Architecture
- [ ] {Issue + recommendation}

### Observability
- [ ] {Issue + recommendation}

### Quality
- [ ] {Issue + recommendation}

## Tier 3: SUGGESTIONS
- {Suggestion}

## Questions for Orchestrator
1. {Question requiring human judgment}

## Verdict
[ ] **APPROVED** - Ready to proceed
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision
```

---

## Prompt Inventory

| ID | Name | Role | Pre-Flight |
|----|------|------|------------|
| **0701c** | Issue Review | Senior TPM & Governance Lead | User Story, AC, DoD |
| **0702c** | LLD Review | Senior Architect & AI Governance Lead | Issue link, Context, Proposed Changes |
| **0703c** | Implementation Review | Senior Software Architect | impl-report.md, test-report.md |
| **0704c** | Operational Health Review | Head of Eng Ops & AI Safety | zugzwang.log, audits, sessions |

---

## Compliance

All review prompts in `docs/skills/` MUST:

1. Reference this standard in their Metadata section
2. Include ALL sections in the Golden Schema order
3. Use the exact Output Format template
4. Include examples for Pre-Flight failure and Tier 1 blocking

**Non-compliant prompts are invalid and must be refactored.**

---

## History

| Date | Version | Change |
|------|---------|--------|
| 2026-01-22 | 2.0.0 | Initial Golden Schema standard. Defines structure for 0628c-0631c. |

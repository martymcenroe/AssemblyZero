# Gemini Verification

> Multi-model architecture: Claude builds, Gemini reviews

---

## The Innovation

Most AI coding workflows have one model doing everything:
- Generate code
- Review its own work
- Approve its own PRs

This is like letting a student grade their own exam.

AssemblyZero uses **multi-model verification**:
- **Claude** (Opus/Sonnet) generates designs and code
- **Gemini**, through `agy`, reviews the work before it proceeds
- **Different model families** catch different mistakes

This separation provides adversarial verification that neither model alone can achieve.

---

## Architecture

```mermaid
graph TD
    subgraph Claude["CLAUDE AGENTS (Build)"]
        C1["Draft LLD"]
        C2["Implement code"]
        C3["Write tests"]
        C4["Generate reports"]
    end

    subgraph Gemini["GEMINI (Review)"]
        GI["Issue Review<br/>Requirements clarity"]
        GL["LLD Review Gate<br/>Design completeness"]
        GC["Implementation Review<br/>Code quality, tests"]
        GS["Security Audit<br/>OWASP, secrets"]
    end

    subgraph Decision{"DECISION ROUTING"}
        direction LR
        Approve["APPROVE"]
        Block["BLOCK"]
        Quota["Quota Exhausted"]
    end

    Proceed["Proceed to next phase"]
    Return["Return to Claude<br/>with feedback"]
    Stop["STOP<br/>Human decision"]

    Claude --> Gemini
    Gemini --> Decision
    Approve --> Proceed
    Block --> Return
    Quota --> Stop
    Return -.-> Claude
```

---

## Why Multi-Model?

### 1. Adversarial Verification

Different model families have different blind spots:

| What Claude Might Miss | What Gemini Catches |
|------------------------|---------------------|
| Over-engineered solutions | "This adds unnecessary complexity" |
| Missing edge cases | "What happens when X is null?" |
| Security anti-patterns | "This is vulnerable to X injection" |
| Incomplete test coverage | "Missing tests for error paths" |

| What Gemini Might Miss | What Claude Catches |
|------------------------|---------------------|
| Implementation nuance | Context from development process |
| Codebase conventions | Project-specific patterns |
| Technical debt context | Historical decisions |

Together, they catch more than either alone.

### 2. Separation of Concerns

```
Claude's Focus:          Gemini's Focus:
├── Understanding task   ├── Objective evaluation
├── Creative solutions   ├── Standard compliance
├── Codebase context     ├── Security posture
├── Implementation       ├── Quality gates
└── Developer experience └── Audit trail
```

The reviewing model doesn't have implementation bias - it evaluates the artifact objectively.

### 3. Audit Trail

Every Gemini review creates an auditable record:

```json
{
  "review_type": "implementation_review",
  "issue_id": "47",
  "timestamp": "2026-01-21T14:32:00Z",
  "model": "gemini-3.8-flash-high",
  "verdict": "APPROVE",
  "files_reviewed": ["src/export.py", "tests/test_export.py"],
  "findings": [
    {"severity": "info", "message": "Good error handling"},
    {"severity": "info", "message": "Test coverage adequate"}
  ],
  "token_usage": {"input": 12000, "output": 500}
}
```

Security teams can query: "Show me all implementations that passed security review."

---

## Gate Implementation

### LLD Review Gate

**When:** Before any coding begins
**What:** Gemini reviews the low-level design document
**Goal:** Catch design issues before they become code

```bash
# Submission: the workflow drafts the LLD and sends it to Gemini over agy
poetry run python tools/run_requirements_workflow.py --type lld --issue 42

# Prompt includes:
# - Full LLD content
# - Review criteria
# - Response format specification
```

**Review criteria:**
- Design completeness (all requirements addressed?)
- Error handling specification (failure modes covered?)
- Security considerations (authentication, authorization, data protection?)
- API contract (inputs, outputs, error responses?)
- Data flow clarity (how data moves through system?)

**Response format:**
```json
{
  "verdict": "APPROVE" | "BLOCK",
  "summary": "One-sentence overall assessment",
  "strengths": ["List of good elements"],
  "issues": [
    {
      "severity": "critical" | "major" | "minor",
      "category": "security" | "completeness" | "clarity",
      "description": "What's wrong",
      "recommendation": "How to fix"
    }
  ]
}
```

### Implementation Review Gate

**When:** After coding, before PR creation
**What:** Gemini reviews code changes and test results
**Goal:** Catch implementation issues before human review

```bash
# Submission includes:
# - Git diff of changes
# - Implementation report
# - Test report with full output
# - Coverage metrics
```

**Review criteria:**
- Code quality (readability, maintainability?)
- Test coverage (adequate for changes?)
- Pattern compliance (follows project conventions?)
- Security (no vulnerabilities introduced?)
- Documentation (updated for changes?)

### Security Audit

**When:** Part of implementation review
**What:** OWASP-focused security scan
**Goal:** Catch security issues before they reach production

**Checks:**
- Injection vulnerabilities (SQL, command, XSS)
- Authentication weaknesses
- Sensitive data exposure
- Security misconfiguration
- Known vulnerable dependencies

---

## Model Requirements

### Acceptable Models

`config/fleet-models.toml` chooses the model for every role. A review runs on the `reviewer` role:

| Model | Purpose | Status |
|-------|---------|--------|
| `gemini-3.8-flash-high` | Reviews, and every seat of a workflow run | Approved |
| `gemini-3.8-flash-low` | Preflight, and sorting a large input before a judge reads it | Approved |

### Forbidden Models

The `[policy]` table in `config/fleet-models.toml` lists these. An entry refuses every model id that contains it, so no role can use one:

| Model |
|-------|
| `gemini-2.0-flash` |
| `gemini-2.5-flash` |
| `gemini-flash` |
| `gemini-2.5-lite` |
| `gemini-lite` |
| `gemini-3-pro-preview` |
| `gemini-3-pro` |
| `gemini-4-argon` |

Argon's budget is weekly, and one run once spent a whole week of it.

A role on a model that is not live stops its tool, naming the role and the model. Nothing falls back to another model.

### Model Verification

`GeminiClient` (`assemblyzero/core/gemini_client.py`) refuses a forbidden model before it calls `agy`:

```python
lowered = model.lower()
if any(entry.lower() in lowered for entry in FORBIDDEN_MODELS):
    raise ValueError(f"Model '{model}' is forbidden.")
```

---

## Credential Management

There are no credentials to manage. The pipeline reaches Gemini through the `agy` CLI on the subscription, so there is no key to rotate and no second account to fall back on.

`GeminiClient` retries transient capacity errors with exponential backoff, within the call's time budget. It does not retry exhausted quota: the call fails, and the workflow halts with a recovery plan.

### Quota Exhaustion Protocol

When the subscription's quota is exhausted:

1. **STOP** - Do not proceed without review
2. **Report** - Inform user of quota status
3. **Wait** - Until quota resets or user intervenes
4. **DO NOT** substitute a lesser model

This ensures reviews are never skipped due to quota issues.

---

## Integration with Workflow

### Standard Flow

```
1. Gemini (agy) drafts LLD
   ↓
2. LLD Review Gate ←── Gemini
   │
   ├── [APPROVE] → Continue to step 3
   └── [BLOCK] → Return to step 1 with feedback
   ↓
3. Claude implements code
   ↓
4. Claude runs tests, generates reports
   ↓
5. Implementation Review Gate ←── Gemini
   │
   ├── [APPROVE] → Continue to step 6
   └── [BLOCK] → Return to step 3 with feedback
   ↓
6. Claude creates PR
   ↓
7. Human reviews and merges
```

### Gate Statistics

Typical approval rates:

| Gate | First-Pass Approval | After Revision |
|------|---------------------|----------------|
| LLD Review | 65-75% | 95%+ |
| Implementation Review | 75-85% | 98%+ |
| Security Audit | 85-95% | 99%+ |

The gates work: issues are caught before human review.

---

## Why Not Self-Review?

Some ask: "Why not have Claude review its own work?"

| Self-Review | Multi-Model Review |
|-------------|-------------------|
| Same blind spots | Different perspectives |
| Implementation bias | Objective evaluation |
| "Of course it's good" | Genuine adversarial check |
| Hard to audit | Clear separation of roles |
| Single point of failure | Defense in depth |

Self-review is like proofreading your own email immediately after writing it - you see what you meant, not what you wrote.

---

## Related Pages

- [Multi-Agent Orchestration](Multi-Agent-Orchestration) - Overall architecture
- [Governance Gates](Governance-Gates) - Gate details and protocols
- [Measuring Productivity](Measuring-Productivity) - Gate metrics
- [LangGraph Evolution](LangGraph-Evolution) - Enforcement roadmap

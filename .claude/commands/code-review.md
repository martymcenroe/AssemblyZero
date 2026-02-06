---
description: Parallel multi-agent code review (PR or staged changes)
argument-hint: "[PR#] [--files path1 path2...] [--focus security|quality|all]"
---

# Multi-Agent Code Review

**Based on:** `anthropics/claude-code` code-review plugin
**Architecture:** 5 parallel agents with confidence-based filtering

**Model hints:**
- Security Reviewer: **Opus** (complex security reasoning)
- All other agents: **Sonnet** (pattern matching, sufficient capability)

**Cost optimization:** Context is gathered ONCE in Step 1, then PASSED to agents. Agents should NOT read files independently - this wastes tokens on duplicate reads.

---

## Project Detection

Detect the current project and GitHub repo from working directory:
- Extract project name from path
- Look up GitHub repo (or use `gh repo view --json nameWithOwner`)

---

## Help

Usage: `/code-review [PR#] [--files path1 path2...] [--focus security|quality|all]`

| Argument | Description |
|----------|-------------|
| `PR#` | Review a specific pull request (e.g., `123`) |
| `--files` | Review specific files instead of PR |
| `--focus security` | Run only security-focused agents |
| `--focus quality` | Run only code quality agents |
| `--focus all` | Run all agents (default) |

**Examples:**
- `/code-review 123` - review PR #123 with all agents
- `/code-review --files src/main.py` - review specific file
- `/code-review 123 --focus security` - security-only review of PR

---

## Execution

### Step 1: Gather Context

**If PR number provided:**
```bash
gh pr view $PR --json title,body,files,commits
gh pr diff $PR
```

**If --files provided:**
Read the specified files directly.

**If neither provided:**
```bash
git diff --staged
git diff HEAD
```

### Step 2: Spawn Parallel Review Agents

Launch 5 agents in parallel using the Task tool. Each agent operates independently and returns findings with confidence scores.

**CRITICAL:** Use a single message with 5 Task tool calls to run in parallel.

**COST OPTIMIZATION (SHARED CONTEXT):**
- You (the parent agent) already gathered the PR diff in Step 1
- PASS the diff content directly in each agent's spawn prompt
- Agents should NOT use Read/Grep tools to re-fetch the same content
- This avoids 5x duplicate file reads

**Template:** In each agent prompt below, replace `[PR diff or file contents]` with the ACTUAL diff content you gathered in Step 1. Do not use placeholders.

**Agent Prompt Header (include in ALL agent prompts):**
```
IMPORTANT: All context is provided below. Do NOT use Read/Grep tools to fetch files - this wastes tokens. Analyze only the provided content.
```

#### Agent 1: Security Reviewer (Opus)

```
Review code for security vulnerabilities.

IMPORTANT: All context is provided below. Do NOT use Read/Grep tools.

Context: [PR diff or file contents - REPLACE WITH ACTUAL DIFF]

Execute security checklist:
1. Input validation and sanitization
2. Authentication/authorization flaws
3. Injection vulnerabilities (SQL, XSS, command)
4. Sensitive data exposure
5. Security misconfiguration

Return findings in format:
{
  "agent": "security",
  "confidence": 0.0-1.0,
  "critical": [...],
  "warnings": [...],
  "suggestions": [...]
}
```

#### Agent 2: CLAUDE.md Compliance (Sonnet)

```
Review code changes for AssemblyZero compliance.

IMPORTANT: All context is provided below. Do NOT use Read/Grep tools except for CLAUDE.md reference.

Context: [PR diff - REPLACE WITH ACTUAL DIFF]
Reference: Read CLAUDE.md (this is the ONE exception - read it for rules)

Check for violations:
1. Bash commands using && or pipes
2. Code edits on main branch without worktree
3. Missing reports for closed issues
4. Forbidden commands (git reset, pip install, etc.)
5. Path format violations (Bash vs Read/Write)

Return findings in format:
{
  "agent": "claude-md-compliance",
  "confidence": 0.0-1.0,
  "violations": [...],
  "warnings": [...]
}
```

#### Agent 3: Bug Detector (Sonnet)

```
Analyze code for potential bugs and logic errors.

IMPORTANT: All context is provided below. Do NOT use Read/Grep tools.

Context: [PR diff or file contents - REPLACE WITH ACTUAL DIFF]

Check for:
1. Null/undefined handling
2. Race conditions
3. Error handling gaps
4. Edge cases not covered
5. Type mismatches
6. Resource leaks

Return findings in format:
{
  "agent": "bug-detector",
  "confidence": 0.0-1.0,
  "bugs": [...],
  "potential_issues": [...]
}
```

#### Agent 4: Code Quality (Sonnet)

```
Review code for quality, maintainability, and best practices.

IMPORTANT: All context is provided below. Do NOT use Read/Grep tools.

Context: [PR diff or file contents - REPLACE WITH ACTUAL DIFF]

Check for:
1. SOLID principles adherence
2. DRY violations
3. Function/method length
4. Naming clarity
5. Comment quality (not quantity)
6. Cyclomatic complexity

Return findings in format:
{
  "agent": "code-quality",
  "confidence": 0.0-1.0,
  "issues": [...],
  "suggestions": [...]
}
```

#### Agent 5: Test Coverage Analyzer (Sonnet)

```
Analyze test coverage for the changed code.

IMPORTANT: All context is provided below. Do NOT use Read/Grep tools.

Context: [PR diff or file contents - REPLACE WITH ACTUAL DIFF]

Check for:
1. New code has corresponding tests
2. Edge cases covered
3. Error paths tested
4. Mocks appropriate and not excessive
5. Integration vs unit test balance

Return findings in format:
{
  "agent": "test-coverage",
  "confidence": 0.0-1.0,
  "missing_tests": [...],
  "suggestions": [...]
}
```

### Step 3: Confidence-Based Filtering

After all agents return, filter results by confidence:

| Confidence | Action |
|------------|--------|
| >= 0.8 | Include in report (high confidence) |
| 0.5 - 0.8 | Include with caveat "Verify manually" |
| < 0.5 | Exclude from report (too uncertain) |

### Step 4: Synthesize Report

Produce a consolidated report:

```markdown
# Code Review: [PR Title or Files]

## Summary
[1-2 sentence overall assessment]

## Security Findings (Agent: security-reviewer)
### CRITICAL
- [ ] Finding (confidence: X.X)

### WARNING
- [ ] Finding (confidence: X.X)

## CLAUDE.md Compliance (Agent: claude-md-compliance)
- [ ] Violation: ...

## Potential Bugs (Agent: bug-detector)
- [ ] Bug: ... (confidence: X.X)

## Code Quality (Agent: code-quality)
- [ ] Issue: ...

## Test Coverage (Agent: test-coverage)
- [ ] Missing: ...

## Recommendations
1. [Prioritized action items]

---
*Review generated by 5 parallel agents. Findings with confidence < 0.5 excluded.*
```

---

## Focus Modes

### --focus security
Run only:
- Agent 1: Security Reviewer

### --focus quality
Run only:
- Agent 4: Code Quality
- Agent 5: Test Coverage

### --focus all (default)
Run all 5 agents in parallel.

---

## Notes

- Security reviewer uses Opus (more thorough for security)
- Other agents use Sonnet (faster, sufficient for patterns)
- Parallel execution reduces total time from ~5min to ~1min
- Confidence filtering reduces false positive noise

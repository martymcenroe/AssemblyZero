---
description: Single-agent code review (PR or staged changes)
argument-hint: "[PR#] [--files path1 path2...] [--focus security|quality|all]"
---

# Code Review

**Model hint:** Use **Sonnet** for the review agent — sufficient for all checklist areas.

**Cost:** ~$0.05-0.15 per review (single agent, diff passed inline).

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
| `--focus security` | Weight security checks heavily |
| `--focus quality` | Weight code quality and test checks heavily |
| `--focus all` | Equal weight across all areas (default) |

**Examples:**
- `/code-review 123` - review PR #123
- `/code-review --files src/main.py` - review specific file
- `/code-review 123 --focus security` - security-weighted review of PR

---

## Execution

### Step 1: Gather Context (parent agent)

**If PR number provided:**
```bash
gh pr view $PR --json title,body,files,commits --repo {GITHUB_REPO}
```
```bash
gh pr diff $PR --repo {GITHUB_REPO}
```

**If --files provided:**
Read the specified files directly.

**If neither provided:**
```bash
git diff --staged
```
```bash
git diff HEAD
```

### Step 2: Spawn Single Review Agent

Launch ONE Task agent with `subagent_type: general-purpose` and `model: sonnet`.

**COST OPTIMIZATION:** Pass the diff content directly in the agent prompt. The agent should NOT use Read/Grep tools to re-fetch files — all context is inline.

**Agent Prompt:**

```
You are a code reviewer. Analyze the provided diff using the structured checklist below.

IMPORTANT: All context is provided below. Do NOT use Read/Grep/Bash tools to fetch files — this wastes tokens. Analyze only the provided content. The ONE exception: you may Read CLAUDE.md for compliance rules if the project has one.

Project: {PROJECT_NAME}
Focus: {FOCUS: security|quality|all}

## Diff to Review

{ACTUAL DIFF CONTENT — replace this placeholder with the real diff}

## Review Checklist

Work through ALL sections. For each finding, rate confidence 0.0-1.0.
Skip sections with no findings rather than padding with "looks good."

### 1. Security
- Input validation and sanitization
- Authentication/authorization flaws
- Injection vulnerabilities (SQL, XSS, command)
- Sensitive data exposure (secrets, tokens, PII in logs)
- Security misconfiguration

### 2. Bugs & Logic Errors
- Null/undefined handling
- Race conditions
- Error handling gaps (uncaught exceptions, missing error paths)
- Edge cases not covered
- Type mismatches
- Resource leaks (file handles, connections, event listeners)

### 3. Code Quality
- SOLID principles adherence
- DRY violations (copy-paste code)
- Function/method length (>50 lines is a flag)
- Naming clarity
- Cyclomatic complexity

### 4. CLAUDE.md Compliance (if applicable)
- Bash commands using && or pipes (should use git -C instead)
- Path format violations (Bash=Unix, Read/Write=Windows)
- Forbidden commands (git reset --hard, pip install, etc.)

### 5. Test Coverage
- New code has corresponding tests
- Edge cases covered
- Error paths tested
- Mocks appropriate and not excessive

## Output Format

Return a structured review:

SUMMARY: [1-2 sentence overall assessment]

CRITICAL FINDINGS (must fix):
- [Finding] (confidence: X.X) — [file:line if applicable]

WARNINGS (should fix):
- [Finding] (confidence: X.X) — [file:line if applicable]

SUGGESTIONS (nice to have):
- [Finding] (confidence: X.X)

VERDICT: [APPROVE / REQUEST_CHANGES / COMMENT_ONLY]

If focus is "security", weight section 1 heavily and be thorough.
If focus is "quality", weight sections 3 and 5 heavily.
If focus is "all", give equal weight to all sections.

Only include findings with confidence >= 0.5. Skip low-confidence noise.
```

### Step 3: Display Results

Present the agent's review directly. No post-processing needed — the structured format is the final output.

---

## Notes

- Single Sonnet agent covers all 5 review areas in one pass
- Confidence threshold (0.5) filters low-quality findings
- Focus modes weight checklist sections, not spawn different agents
- Diff is passed inline — zero duplicate file reads

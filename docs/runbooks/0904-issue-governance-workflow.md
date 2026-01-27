# 0904 - Issue Governance Workflow

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-01-26

---

## Purpose

Create GitHub issues through a governed workflow that ensures human review at every step. The workflow uses a LangGraph StateGraph to enforce Inversion of Control - Claude drafts, Gemini reviews, but humans approve at every gate.

**Use this when:** You want to create a well-structured GitHub issue with AI assistance but full human oversight.

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| VS Code CLI | `which code` (should return path) |
| GitHub CLI authenticated | `gh auth status` (should show logged in) |
| Poetry environment | `poetry run python --version` |
| Brief file exists | Your idea written in markdown |

---

## Procedure

### Step 1: Write Your Brief

Create a markdown file with your issue idea. This is YOUR input - write whatever you want Claude to expand into a proper issue.

**Location:** `docs/drafts/` (recommended) or anywhere

**Example brief:**
```markdown
# Add rate limiting to API

I want to add rate limiting to prevent abuse. Should use Redis for distributed counting. Need to handle:
- Per-user limits
- Per-endpoint limits
- Graceful degradation when Redis unavailable

Labels: enhancement, security
```

### Step 2: Run the Workflow

```bash
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/run_issue_workflow.py --brief /path/to/your-brief.md
```

The workflow creates an audit directory at `docs/audit/active/{slug}/` where all artifacts are saved.

### Step 3: N0-N1 (Automatic)

The workflow automatically:
- **N0:** Loads your brief, generates a slug, creates audit directory
- **N1:** Verifies VS Code and gh CLI are available

If the slug already exists, you'll be prompted:
- **[R]esume** - Continue existing workflow from checkpoint
- **[N]ew name** - Enter a different slug
- **[A]bort** - Exit cleanly

### Step 4: N2 - Claude Drafts

Claude expands your brief into a full GitHub issue with:
- Clear title and description
- Acceptance criteria
- Technical approach
- Mermaid diagrams (if applicable)
- Labels

**You don't interact here** - the draft is saved to the audit trail.

### Step 5: N3 - Human Gate (Post-Claude)

VS Code opens with the draft. This is your chance to:
1. **Review** Claude's expansion of your idea
2. **Edit** anything - title, description, approach, labels
3. **Save and close** VS Code when done

**Prompt:** `Iteration {n} | Draft #{n}`

Choose:
- **[S]end** - Send to Gemini for review
- **[R]evise** - Send back to Claude with feedback
- **[M]anual** - File the issue yourself (exits workflow)

### Step 6: N4 - Gemini Reviews

Gemini (as adversarial reviewer) checks the draft for:
- Clarity and completeness
- Technical feasibility
- Security considerations
- Missing acceptance criteria

**You don't interact here** - the verdict is saved to the audit trail.

### Step 7: N5 - Human Gate (Post-Gemini)

VS Code opens with BOTH the draft and Gemini's verdict (split view).

**Prompt:** `Iteration {n} | Draft #{n} | Verdict #{n}`

This is the critical sanitization gate:
1. **Read** Gemini's feedback
2. **Decide** if changes are needed
3. **Edit** the draft if desired

Choose:
- **[A]pprove** - File the issue as-is
- **[R]evise** - Send back to Claude with Gemini's feedback incorporated
- **[M]anual** - File the issue yourself (exits workflow)

### Step 8: N6 - Issue Filed

The workflow runs `gh issue create` with your approved draft.

**Output:**
- Issue URL printed to console
- `filed.json` saved to audit trail with issue number and metadata

---

## Resuming an Interrupted Workflow

If VS Code crashes, terminal closes, or you need to continue later:

```bash
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/run_issue_workflow.py --resume {slug}
```

Or just run with the same `--brief` and choose **[R]esume** when prompted about the existing slug.

---

## Audit Trail

All artifacts are saved to `docs/audit/active/{slug}/`:

| File | Description |
|------|-------------|
| `001-brief.md` | Your original input |
| `002-draft.md` | Claude's first draft |
| `003-draft-edited.md` | Your edits at N3 |
| `004-verdict.md` | Gemini's review |
| `005-draft.md` | Revised draft (if looped) |
| `NNN-filed.json` | Final metadata with issue URL |

After the issue is filed, move the folder to `docs/audit/done/`.

---

## Verification Checklist

| Check | Command | Expected |
|-------|---------|----------|
| Issue created | `gh issue view {number}` | Shows your issue |
| Audit complete | `ls docs/audit/active/{slug}/` | Has `*-filed.json` |
| Labels applied | `gh issue view {number} --json labels` | Labels from draft |

---

## Troubleshooting

### "VS Code CLI not found"

Install VS Code and ensure `code` is in your PATH:
- Windows: VS Code installer adds it automatically
- Verify: `which code` or `where code`

### "gh not authenticated"

Run:
```bash
gh auth login
```

### "Slug collision" but I want to start fresh

Delete the existing audit directory:
```bash
rm -rf docs/audit/active/{slug}
```

Then re-run the workflow.

### "Gemini quota exhausted"

The workflow will pause. Wait for quota reset (~24h) or use a different Gemini credential. The orchestrator manages credential rotation.

---

## Related Documents

- [62-governance-workflow-stategraph.md](../LLDs/done/62-governance-workflow-stategraph.md) - Implementation LLD
- [0701c-Issue-Review-Prompt.md](../skills/0701c-Issue-Review-Prompt.md) - Gemini's review prompt (if exists)
- [CLAUDE.md](../../CLAUDE.md) - Core rules including Gemini orchestrator protocol

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-26 | Initial version |

---
description: Validate a GitHub issue against standard 0018 before invoking the LLD workflow
argument-hint: "<issue-number> [--repo owner/repo]"
scope: project
---

# Pre-Flight Check

**Purpose:** Apply the six-dimension Issue Spec Quality Checklist (standard 0018) to a GitHub issue before invoking `tools/run_requirements_workflow.py` against it. Fail-fast at this gate is one operator-minute; failing inside the workflow is 5–30 minutes of wall-time and tokens.

**Model hint:** Use **Sonnet** for the checks. Reasoning over a single issue body doesn't need Opus.

**Cost:** ~$0.005–0.02 per invocation (one issue body + standard 0018 + reasoning).

---

## Help

Usage:

| Form | Effect |
|---|---|
| `/pre-flight-check 35` | Resolves repo from current working directory; fetches issue #35; checks against 0018. |
| `/pre-flight-check 35 --repo martymcenroe/boostgauge` | Explicit repo. Use when running from outside the target project. |

---

## Execution

### Step 1: Resolve repo and fetch issue

If `--repo OWNER/REPO` is in arguments, use that. Otherwise:

```bash
git -C "$(pwd)" remote get-url origin
```

Extract `OWNER/REPO` from the URL (`https://github.com/OWNER/REPO.git` or `git@github.com:OWNER/REPO.git`).

If the directory is not a git repo, return:

```
NO REPO — pass --repo OWNER/REPO explicitly, or invoke from inside a target repo.
```

Then:

```bash
gh issue view <N> --repo <OWNER>/<REPO>
```

If the issue does not exist or is closed, return:

```
ISSUE NOT FOUND / CLOSED — verify number, then re-invoke.
```

### Step 2: Read standard 0018

```
Read docs/standards/0018-issue-spec-quality.md from the AssemblyZero repo
(at /c/Users/mcwiz/Projects/AssemblyZero/docs/standards/0018-issue-spec-quality.md).
```

This is the source of truth for the dimensions and verdict matrix. If the file doesn't exist (cross-repo running outside AZ), fall back to the inline summary in §"Inline 0018 Summary" below.

### Step 3: Apply each dimension

For each dimension in §2 of standard 0018:

| # | Dimension | What to check |
|---|---|---|
| 1 | Strong-verb title | Does the title start with `feat:` / `fix:` / `refactor:` / `chore:` / `docs:` / `test:` / `perf:` AND name a specific deliverable? |
| 2 | Acceptance criteria (binary) | Does the body contain ≥1 binary-verifiable checkpoint (e.g., `- [ ] X returns Y`)? |
| 3 | Explicit IN/OUT scope | Does the body contain at least one explicit "out of scope" statement? |
| 4 | File paths/modules named | Does the body mention ≥1 specific file path, module, or function the work touches? Generic references ("the workflow") do not count. |
| 5 | Determinism | Would two competent engineers reading this body produce substantially the same code? Apply judgment. |
| 6 | Test plan / signal | Does the body indicate how the work will be verified — explicitly OR via concrete acceptance criteria from dimension 2? |

For each dimension: PASS / FAIL with a one-sentence reason citing specific text from the body.

### Step 4: Render verdict

Apply the §3 verdict matrix from standard 0018:

| Dimensions passing | Verdict | Action |
|---|---|---|
| 6/6 | **PROCEED** | Run the LLD workflow. |
| 4–5/6 | **REVISE FIRST** | Edit the issue body to address the failing dimension(s); re-score; then run the workflow. |
| ≤3/6 OR dimension 1 fails (research/discussion title) | **WRONG WORKFLOW** | Route to a research process instead. |

### Step 5: Output

```markdown
## Pre-Flight Check — Issue #<N>

**Title:** {issue title}
**Repo:** {OWNER/REPO}

### Per-Dimension Results

| # | Dimension | Result | Notes |
|---|---|---|---|
| 1 | Strong-verb title | PASS / FAIL | {one-sentence citation} |
| 2 | Acceptance criteria (binary) | PASS / FAIL | {citation} |
| 3 | Explicit IN/OUT scope | PASS / FAIL | {citation} |
| 4 | File paths/modules named | PASS / FAIL | {citation} |
| 5 | Determinism | PASS / FAIL | {citation} |
| 6 | Test plan / signal | PASS / FAIL | {citation} |

### Score: {N}/6

### Verdict

[ ] **PROCEED** — issue meets all six dimensions; ready for the LLD workflow.
[ ] **REVISE FIRST** — edit the issue body to address {failing dimension list} before invoking the workflow.
[ ] **WRONG WORKFLOW** — issue is research/discussion-shaped; route to a research process.

(Mark exactly ONE option with [x].)
```

If verdict is **REVISE FIRST**, also produce a §"Suggested Edits" section:

```markdown
### Suggested Edits

For dimension {N} ({dimension name}):

**Add to the body:**

> {Concrete suggestion — actual text the operator can paste, addressing the failing dimension}

For dimension {M}:
...
```

If verdict is **WRONG WORKFLOW**, also produce a §"Alternative Routes" section:

```markdown
### Alternative Routes

This issue asks for {research / discussion / open-ended exploration}, which the LLD workflow does not handle well.

Suggested next step:

1. {Hand to manual Gemini chat for research summary}, OR
2. {Decompose into N feature-shaped sub-issues that each pass dimensions 1–6}, OR
3. {Close as not-suitable-for-the-workflow if the work is not actually code}.
```

---

## Worked Examples

### Example 1: PROCEED

Issue #4 (boostgauge): `feat: Windows data collector`

Body has:
- Six binary acceptance criteria
- Explicit OUT-of-scope statement
- Module names (`DataCollector`, `WindowsCollector`)
- Threading model specified
- Test plan implied via testable acceptance criteria

All six dimensions pass → **PROCEED**.

### Example 2: REVISE FIRST

Issue #18 (boostgauge): `feat: multi-gauge mode`

- Dimension 1 (title): PASS (`feat:` + deliverable)
- Dimension 2 (binary criteria): FAIL — "visually highlighted" is not testable
- Dimension 3 (OUT scope): FAIL — no OUT statement
- Dimension 4 (file paths): FAIL — generic GUI references only
- Dimension 5 (determinism): FAIL — layout polish is non-deterministic
- Dimension 6 (test plan): FAIL — none

1/6 → **WRONG WORKFLOW** by the strict matrix. But this is a *fixable* issue, not a research one. Suggest the operator add:
- 2–3 binary acceptance criteria
- An OUT statement
- Specific file paths

After those edits, dimensions 2/3/4 flip and the score is 5/6 → **PROCEED**.

### Example 3: WRONG WORKFLOW

Issue #12 (boostgauge): `research: deep dive — optimal system health scoring algorithms`

- Dimension 1: FAIL (`research:` title)
- Dimension 2: FAIL ("Find 2-3 algorithms" is not testable)
- Dimension 3: FAIL ("lightweight widget" undefined)
- Dimension 4: FAIL (no code paths)
- Dimension 5: FAIL (LLM-determined output)
- Dimension 6: FAIL (work product is documentation)

0/6 → **WRONG WORKFLOW.** Suggested route: hand to a manual Gemini chat for research summary; the resulting algorithm choice can become a new `feat:` issue that consumes the research output.

---

## Inline 0018 Summary (fallback)

If the agent cannot read `0018-issue-spec-quality.md`, use this inline summary as the rubric. The full standard always wins when available.

**Six dimensions:**
1. Strong-verb title (deliverable, not topic).
2. Acceptance criteria as ≥1 binary-verifiable checkpoint.
3. Explicit OUT-of-scope statement.
4. ≥1 named file/module/function.
5. Determinism (two engineers converge).
6. Test plan or testable acceptance criteria.

**Verdict matrix:**
- 6/6 → PROCEED
- 4–5/6 → REVISE FIRST
- ≤3/6 OR dim 1 fails → WRONG WORKFLOW

---

## Notes

- **v1 is markdown-only** — the agent does the reasoning. A future Python wrapper (`tools/pre_flight_check.py`) could automate batch invocation; deferred to a follow-up issue.
- **The standard is authoritative.** When this skill and standard 0018 disagree, the standard wins. Update both together if dimensions change.
- **For the boostgauge speed-run**, run `/pre-flight-check` against the chosen demo issue once before pressing record. PROCEED verdict is a precondition for recording.

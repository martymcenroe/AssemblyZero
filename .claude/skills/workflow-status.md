---
description: Walk the lineage audit trail and report where the workflow stopped + how to resume
argument-hint: "<issue-number> [--repo PATH] [--lld | --testing]"
scope: project
---

# Workflow Status

**Purpose:** Diagnose where a halted (or in-flight) AZ workflow last got to and produce a single-command recovery suggestion. Reads the lineage audit trail (`docs/lineage/active/{issue}-{kind}/`) and applies the §4 decision tree from standard 0021 (Workflow Error Recovery Procedures).

**Model hint:** Use **Sonnet** for the read+reasoning. Walking files and pattern-matching error messages doesn't need Opus.

**Cost:** ~$0.005–0.02 per invocation.

---

## Help

Usage:

| Form | Effect |
|---|---|
| `/workflow-status 35` | Auto-detect kind (LLD or testing) by checking which lineage dir exists. |
| `/workflow-status 35 --lld` | Force-read `docs/lineage/active/35-lld/`. |
| `/workflow-status 35 --testing` | Force-read `docs/lineage/active/35-testing/`. |
| `/workflow-status 35 --repo /c/Users/mcwiz/Projects/boostgauge` | Use a different repo's lineage dir. |

**Behavior when both LLD and testing dirs exist** (likely the issue ran both): default to the most recently modified. Pass an explicit kind to override.

---

## Execution

### Step 1: Resolve repo + locate lineage

If `--repo PATH` is given, use that. Otherwise the working directory.

```
{repo}/docs/lineage/active/{issue}-{kind}/
```

Where `{kind}` is `lld` or `testing`. If neither exists, return:

```
NO LINEAGE — no audit trail at docs/lineage/active/{issue}-*/. Has the workflow run yet?
```

If both exist and no `--lld` / `--testing` flag was passed, pick the most-recently-modified directory and note the choice in the output.

### Step 2: Walk numbered files

Read every file in lineage order:

| Pattern | Meaning |
|---|---|
| `001-issue.md` | Input issue body |
| `00N-draft.md` (even N from 002) | Drafter output for cycle N/2 |
| `00N-verdict.md` (odd N from 003) | Reviewer verdict for cycle (N-1)/2 |
| `validation-errors-draft<NNN>-<TS>.md` | Mechanical validator failures (per #334) |
| `verdict.md` (testing dir) | Test plan review verdict |
| `verdict-mechanical.md` (testing dir) | Test plan fast-path approval |
| `reviewer-error.md` (testing dir) | LLM call failure |
| `report.md` (testing dir) | Final test report |

Track:
- Total drafts produced (count of `*-draft.md` files for LLD; `verdict.md` for testing).
- Latest verdict + outcome.
- Validation iteration count (count of `validation-errors-*` files).
- Whether the final state appears APPROVED, BLOCKED, or in-flight.

### Step 3: Diagnose

Apply the decision tree from standard 0021 §4:

1. **Approved** — last verdict is APPROVED, no later draft → workflow completed at the LLD stage. If LLD-only, status is "ready for implementation" + the next-step command.
2. **In-flight** — latest file is < 5 min old → workflow may still be running. Recommend waiting OR `gh run view` if invoked from a workflow runner.
3. **Stagnation** — last two verdicts have substantially the same BLOCKING text → recommend manual LLD edit + `--resume-review`.
4. **Mechanical loop** — N validation-errors files where N >= max_iterations (typical 20) → recommend reading the latest 2-3 to identify root cause; halt is in the LLD content, not the validator.
5. **Resume-review-eligible** — last verdict is BLOCKED with feedback that looks transient (5xx / timeout / quota) → print the `--resume-review` command.
6. **Test plan BLOCKED** — testing dir, `verdict.md` shows BLOCKED → recommend the policy options from #1072 (`--test-plan-policy`).

### Step 4: Output

```markdown
## Workflow Status — Issue #<N>

**Kind:** {LLD | testing}
**Lineage dir:** {path}
**Last activity:** {timestamp from most recent file}

### Trail Summary

| File | Type | Outcome |
|---|---|---|
| 001-issue.md | input | (issue title) |
| 002-draft.md | draft 1 | (length, last edited) |
| 003-verdict.md | verdict 1 | APPROVED / REVISE / BLOCKED |
| 004-draft.md | draft 2 | ... |
| 005-verdict.md | verdict 2 | ... |
| ... | ... | ... |

(Truncate to last 6 entries if trail is long; mention skipped count.)

### Diagnosis

**State:** {APPROVED | BLOCKED | IN_FLIGHT | STAGNATING | MECHANICAL_LOOP | UNKNOWN}

**Why:** {one paragraph diagnostic — what the trail shows}

### Recommended Recovery

```bash
{single command the operator can run}
```

**Why this command:** {one sentence of rationale linked to the diagnosis}

(If no clear recovery: "No automated recovery applies; read \`docs/standards/0021-workflow-error-recovery.md\` §2.X for manual procedures.")
```

---

## Worked Examples

### Example 1: LLD APPROVED, ready for implementation

Trail: 001, 002, 003=APPROVED, NNN-final.md present.

Output:
- State: APPROVED
- Diagnosis: workflow completed at the LLD stage; no halt.
- Recommended recovery (next step actually):

```bash
PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue <N> --repo {repo}
```

### Example 2: STAGNATING

Trail: 001, 002, 003=BLOCKED, 004, 005=BLOCKED with similar text to 003. No 006.

Output:
- State: STAGNATING
- Diagnosis: two consecutive BLOCKED verdicts call out the same issue ("Section 5 missing function signature for foo"); workflow halted via two-strike stagnation.
- Recommended recovery:

```bash
# Manually fix the LLD draft at docs/lld/active/LLD-NNN.md (Section 5),
# then resume:
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue <N> --repo {repo} --resume-review
```

**Why this command:** stagnation is a quality halt, not a transient one — `--resume-review` preserves the (now-edited) draft and routes it back to N3 for re-review.

### Example 3: MECHANICAL LOOP

Trail: 001, 002, validation-errors-draft001-XXX.md, 003 (drafter retry), validation-errors-draft002-XXX.md, … 20 of those.

Output:
- State: MECHANICAL_LOOP
- Diagnosis: 20 validation-error files all calling out "File marked Modify but does not exist: tools/new_repo_setup.py" — the drafter keeps hallucinating that path. The actual file is at `tools/new-repo-setup.py` (hyphenated).
- Recommended recovery:

```bash
# Manually fix the path in the draft, then resume:
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue <N> --repo {repo} --resume-review
```

**Why this command:** validator's suggestion engine (per #300) already pointed at the correct path; resume after editing.

### Example 4: TEST PLAN BLOCKED (testing dir)

Trail: testing dir has `verdict.md` containing `## Verdict\n[x] **BLOCKED** ...`.

Output:
- State: BLOCKED (test plan)
- Diagnosis: N1 reviewer rejected the test plan; revision cycles either exhausted or were disabled.
- Recommended recovery (depending on `test_plan_revision_count`):

```bash
# If revise hasn't been tried, default policy will revise (now default):
PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue <N> --repo {repo}

# If revise already exhausted, manually edit Section 10 of the LLD then re-run.
```

**Why this command:** standard 0021 §2.5 — manual edit is the recovery when automatic revise can't fix the structure.

### Example 5: REVIEWER 503 / RESUME-REVIEW ELIGIBLE

Trail: 001, 002, 003 (in-progress; reviewer call timed out), no 004 yet.

Output:
- State: BLOCKED-but-transient
- Diagnosis: reviewer call hit a 503 / timeout; auto-retry from #1071 exhausted but the draft itself is valid.
- Recommended recovery:

```bash
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue <N> --repo {repo} --resume-review --retry-policy aggressive
```

**Why this command:** the draft is already validated; `--resume-review` skips re-drafting and goes straight to N3. Aggressive retry handles longer transient bursts.

---

## Notes

- **The skill applies the §4 decision tree from standard 0021.** When the standard updates, this skill should mirror those changes.
- **No write side effects.** This skill reads the audit trail and recommends; it never modifies the trail or runs the recovery automatically. Operator's call.
- **For the boostgauge speed-run:** invoke `/workflow-status <issue>` whenever the recording dead-air budget allows — it's the fastest way to find the recovery command without manually walking 20 verdict files.
- **The lineage trail is the contract.** When a future change to the workflow alters what files appear in the lineage dir, update the §"Walk numbered files" table here AND update standard 0011 (audit decisions) AND update standard 0021 (workflow recovery).

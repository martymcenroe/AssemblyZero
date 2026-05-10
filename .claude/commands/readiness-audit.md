---
description: Run the AZ workflow-readiness audit (runbook 0933) against a target repo
argument-hint: "<repo-path-or-name>"
scope: project
---

# Readiness Audit

**Purpose:** Produce the two-document audit pair (`0001-...` config gaps + `0002-...` deeper) for a target repo, following the runbook 0933 methodology. Output lands in the target repo's `docs/audit-results/`.

**Model hint:** Use **Sonnet** for the synthesis. The Explore agents under the hood handle reads.

**Cost:** ~$0.30–0.80 per full audit (5 Explore agents + 2 synthesis passes). The boostgauge audit (2026-05-09) was ~30 min wall-time at this cost.

---

## Help

Usage:

| Form | Effect |
|---|---|
| `/readiness-audit boostgauge` | Resolves to `/c/Users/mcwiz/Projects/boostgauge`. |
| `/readiness-audit /c/Users/mcwiz/Projects/boostgauge` | Explicit absolute path. |
| `/readiness-audit boostgauge --phase a` | Run only Phase A (config gaps). |
| `/readiness-audit boostgauge --phase b` | Run only Phase B (deeper). Phase A must already exist. |

Default (no `--phase`): both phases run sequentially; Phase A first, then Phase B uses A's output as context.

---

## Execution

### Step 1: Resolve target

If the argument is a name (no slashes), resolve to `/c/Users/mcwiz/Projects/<name>`. If it's a path, use as-is.

Verify the path exists. If not:

```
ERROR — target repo not found at {path}. Pass an absolute path or a repo name under /c/Users/mcwiz/Projects/.
```

Verify the AZ repo is at `/c/Users/mcwiz/Projects/AssemblyZero` (the runbook + standards are read from there).

### Step 2: Read the runbook

```
Read /c/Users/mcwiz/Projects/AssemblyZero/docs/runbooks/0933-workflow-readiness-audit.md
```

The runbook is the contract. If it changes, this skill mirrors it.

### Step 3: Run Phase A — config gaps audit

Single Explore agent. Use the prompt in runbook 0933 §6.1, parameterized to the target.

```
Spawn an Explore agent with subagent_type=Explore.

Prompt (from runbook §6.1, with {target_repo_path} substituted):
"Audit the AssemblyZero workflow-readiness of {target_repo_path}. Use Grep,
Glob, Read; do not modify files. For each surface in this list, report
present / missing / misconfigured with a one-line evidence excerpt:
- Repo bootstrap commit
- CLAUDE.md, GEMINI.md
- .unleashed.json
- .claude/hooks/secret-file-guard.sh
- docs/ scaffolding
- tests/
- pyproject.toml + poetry.lock + pytest dev deps
- .github/workflows/auto-reviewer.yml
- Open issues
- Working tree status

Output a markdown table."
```

Capture the agent's output. Use it as the §1 "State of play" content.

### Step 4: Synthesize Phase A document

Apply the §3.3 template from runbook 0933. Write the document to:

```
{target}/docs/audit-results/0001-assemblyzero-workflow-readiness-{YYYY-MM-DD}.md
```

Required sections:
1. TL;DR
2. State of play (from Phase A agent output)
3. Critical pre-flight blocks (your synthesis — mark each as CRITICAL with concrete fix commands)
4. Soft blocks (will degrade quality but not crash)
5. Optional polish
6. Recommended approach
7. Pre-flight checklist
8. Honest assessment
9. Appendix: Citations (file paths + line numbers from AZ source)

If `--phase a` flag was set, stop here. Otherwise continue to Step 5.

### Step 5: Run Phase B — deeper audit (3 parallel Explore agents)

Spawn three Explore agents in parallel:

| Agent | Prompt (from runbook 0933 §6.X) |
|---|---|
| Agent 1 | §6.2 — issue spec quality (sample 3-5 issues, score against 0018, roll up) |
| Agent 2 | §6.3 — workflow node walk (read both graphs, build resilience tables) |
| Agent 3 | §6.4 — standards + skills inventory + gap analysis |

Capture all three outputs.

### Step 6: Synthesize Phase B document

Apply the §4.3 template from runbook 0933. Write the document to:

```
{target}/docs/audit-results/0002-assemblyzero-deeper-readiness-{YYYY-MM-DD}.md
```

Required sections:
1. TL;DR (3 findings: spec quality bottleneck, resilience surface, standards gaps — load-bearing one called out)
2. Spec quality of {target}'s open issues (from Agent 1)
3. Workflow node-by-node resilience surface (from Agent 2)
4. Standards gap analysis (from Agent 3)
5. Skills gap analysis (from Agent 3)
6. How to tell (per-issue / mid-flight / post-flight checklists)
7. Concrete recommendations (split: before-demo / AZ backlog / target-specific)
8. Net assessment (3 honest answers)
9. Appendix: References

### Step 7: Suggest follow-up issues

After both phases land, output a section in the chat (not the doc):

```markdown
## Follow-up Issues to File

### AssemblyZero (workflow improvements identified)
- {Issue 1 title} — {1-line scope}
- {Issue 2 title} — ...

### {target} (target-specific)
- {Issue 1 title} — {1-line scope}
- ...

To file these, run:
  gh issue create --repo martymcenroe/AssemblyZero --title "..." --body "..."
  gh issue create --repo martymcenroe/{target} --title "..." --body "..."
```

The skill does NOT automatically file the issues — operator's call to make.

### Step 8: Done

Print:

```
✓ Readiness audit complete for {target}.

  0001 (config gaps):    {target}/docs/audit-results/0001-...md
  0002 (deeper):         {target}/docs/audit-results/0002-...md

Follow-up issues suggested above. Recommended next step:
  - Apply §2 critical fixes from 0001 before any workflow attempt.
  - Triage open issues using the dimensions in 0002 §1.
  - Pre-flight a demo target with /pre-flight-check before recording.
```

---

## Worked Example

**Invocation:** `/readiness-audit boostgauge`

**Target:** `/c/Users/mcwiz/Projects/boostgauge`

**Phase A agent finds:**
- pyproject.toml MISSING (critical)
- .github/workflows MISSING (critical)
- working tree DIRTY (critical)
- 25 open issues, no labels

**Phase A doc lands at** `boostgauge/docs/audit-results/0001-assemblyzero-workflow-readiness-2026-05-09.md` with §2 listing the three critical fixes + commands.

**Phase B agents find:**
- ~70% of issues are LLD-ready, ~5% wrong-workflow (research-shaped)
- Workflow detection coverage HIGH, recovery coverage MEDIUM-LOW
- Missing standards: 0018, 0019, 0020, 0021
- Missing skills: pre-flight, mid-flight, workflow-status

**Phase B doc lands at** `boostgauge/docs/audit-results/0002-assemblyzero-deeper-readiness-2026-05-09.md`.

**Follow-ups suggested:** 12 AZ issues (the 1065-1076 series) + 6 boostgauge issues.

(This is the canonical real-world output — 2026-05-09 boostgauge audit.)

---

## Notes

- **The runbook is authoritative.** When `0933-workflow-readiness-audit.md` updates, this skill mirrors those changes. Don't fork the methodology here.
- **Audit dates are wall-clock dates.** If you run the same audit twice on different days, both files exist with different date suffixes. The latest one wins for current state; older ones serve as historical records.
- **Read-only.** This skill produces docs and suggests issues; it never modifies the target repo's working code or configuration.
- **For the boostgauge speed-run:** the audit pair already exists at `boostgauge/docs/audit-results/0001-...md` and `0002-...md` from 2026-05-09. Re-running is unnecessary unless significant time has passed.

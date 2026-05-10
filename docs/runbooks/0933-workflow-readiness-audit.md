# Workflow Readiness Audit — Methodology

**Runbook 0933 — repeatable two-phase audit for assessing whether a target repo is ready to run the AssemblyZero workflows. Companion skill: `/readiness-audit` (#1070).**

The first time we ran this audit (boostgauge, 2026-05-09), it took ~30 minutes of agent time across 5 Explore agents and multiple synthesis steps. Useful, but bespoke — the next repo would have started from scratch. This runbook captures the methodology so the next onboarding takes 10 minutes, not 30, and produces a comparable artifact.

---

## 1. When to Run

Run the readiness audit:

- **Before the first attempt** to invoke an AZ workflow (`run_requirements_workflow.py` or `run_implement_from_lld.py`) against a target repo.
- **After a long gap** since the repo last ran an AZ workflow — config drifts, standards land, skills change.
- **Before recording a high-stakes demo** (the boostgauge YouTube speedrun is the canonical example).

Don't run it:

- After every change to a repo. Quick incremental work doesn't warrant a 10-minute audit.
- When you already know the gap (e.g., "the repo has no `pyproject.toml`"). Just fix the gap directly.

---

## 2. Two-Phase Audit Pattern

The audit produces two documents in `{target}/docs/audit-results/`:

| Number | File | Purpose |
|---|---|---|
| 0001 | `0001-assemblyzero-workflow-readiness-{date}.md` | **Phase A — config gaps.** What's missing or misconfigured at the file/directory/repo-settings level? |
| 0002 | `0002-assemblyzero-deeper-readiness-{date}.md` | **Phase B — spec/standards/skills gaps.** Even after Phase A is fixed, where will the workflow break, and what's missing structurally? |

**Phase A produces an actionable punch-list** (commit X to fix Y). **Phase B produces a strategic picture** (here's where the workflow's quality bottleneck is, here's the standards-and-skills debt accumulating around it).

Phase A always runs first. Phase B is optional but recommended for repos that will run multiple AZ workflows over weeks/months.

---

## 3. Phase A — Config Gaps Audit

**Goal:** Identify gaps that will cause the workflow to fail in the first phase of execution.

### 3.1 Inputs

For the target repo at `{target}`:

| Surface | What to check | Source |
|---|---|---|
| Repo bootstrap | `git log --oneline | grep "initialize project with AssemblyZero"` | Indicates `new_repo_setup.py` ran |
| `CLAUDE.md` + `GEMINI.md` | Both present, ≥50 lines each | Files |
| `.unleashed.json` | Present; `assemblyZero: true`; no deprecated `pickupThresholdMinutes` | File |
| Security hooks | `.claude/hooks/secret-file-guard.sh` present | File |
| Canonical structure | `docs/lld/active/`, `docs/lld/done/`, `docs/reports/active/` exist | Directories |
| Test scaffolding | `tests/` exists with subcategories | Directory listing |
| Open issues | ≥1 open issue queued for the workflow | `gh issue list` |
| `pyproject.toml` | Present, declares Python deps + pytest config | File |
| Test runner | `poetry run pytest --version` succeeds | Run |
| GitHub Actions workflows | `.github/workflows/auto-reviewer.yml` present (Cerberus caller) | API or file |
| Branch protection on `main` | Required reviews + required check `pr-sentinel / issue-reference` | API (may need classic PAT) |
| Cerberus secrets | `REVIEWER_APP_ID` + `REVIEWER_APP_PRIVATE_KEY` set | API (write-only — verify by attempting auto-review) |
| Issue labels | At minimum `lld`, `implementation` per #1061 | API |
| Gemini credentials | `~/.config/gemini/credentials.json` accessible | File |
| Working tree | `git status --short` empty (or noted) | Run |
| Stale remote branches | `git branch -r` minus `origin/main` minus PR branches | Run |

### 3.2 Method

1. Run a single Explore-agent invocation (no need to parallelize Phase A — it's sequential reads):

```
Use the Explore agent with subagent_type=Explore.

Prompt:
  Audit the AssemblyZero workflow-readiness of {target}. For each surface
  in runbook 0933 §3.1, report present / missing / misconfigured with
  a one-line evidence excerpt. Use Grep / Glob / Read; do not modify
  files. Output a markdown table matching the §3.1 schema.
```

2. The agent's output goes into the §"State of play" section of the audit doc.

### 3.3 Output Template (Phase A)

```markdown
# 0001 — AssemblyZero Workflow Readiness Audit

**Auditor:** {agent name + model}, {date}
**Subject:** {target}/{repo} running the AssemblyZero LLD + implementation workflows
**Trigger:** {why this audit was run}

---

## TL;DR

{1–2 paragraph summary of whether the repo can survive the first 90 seconds
of either workflow, and what the critical fixes are.}

---

## 1. State of play

{Markdown table from Phase A inputs above.}

---

## 2. Critical pre-flight blocks (FIX BEFORE WORKFLOW)

{One §2.N section per CRITICAL block. Each contains:
- The blocker (what fails, where, on-camera failure mode)
- Concrete fix (commands the operator runs)
- Time estimate}

---

## 3. Soft blocks (will degrade quality but not crash)

{Same structure, lower severity.}

---

## 4. Optional polish (post-demo)

{Niceties.}

---

## 5. Recommended approach

{Picking the first issue, demo cadence, off-camera dry-run advice.}

---

## 6. Pre-flight checklist (paste this and check items off)

{Plain-text checklist matching §2 + §3 critical/soft blocks.}

---

## 7. Honest assessment

{Realistic outcome with §2 done, without §2 done, with §2 + dry run.}

---

## Appendix: Citations

{File paths + line numbers in AZ source for every claim about workflow
expectations.}
```

The boostgauge audit (`docs/audit-results/0001-...md` in that repo) is the canonical example.

---

## 4. Phase B — Spec / Standards / Skills Gaps Audit

**Goal:** Identify the structural debt that will degrade workflow quality even after Phase A fixes are applied.

### 4.1 Inputs

#### 4.1.1 Issue spec quality (per-issue assessment)

Sample 3–5 representative open issues (small / mid / research):

For each, score against **standard 0018** (Issue Spec Quality Checklist) — the 6 dimensions:

1. Strong-verb title
2. Acceptance criteria (binary)
3. Explicit IN/OUT scope
4. File paths/modules named
5. Determinism
6. Test plan / signal

Roll up to category counts: `lld-ready`, `lld-needs-revision`, `wrong-workflow`.

#### 4.1.2 Workflow node-by-node resilience

Walk both StateGraph definitions:

- `assemblyzero/workflows/requirements/graph.py` (LLD workflow)
- `assemblyzero/workflows/testing/graph.py` (implementation workflow)

For each node, identify:

| Aspect | What to capture |
|---|---|
| Failure mode | What kinds of inputs / events cause this node to halt or loop? |
| Recovery available | Auto-retry (#1071)? Revise (#1072 for N1 testing)? Manual flag (`--resume*`)? Or terminal HALT? |
| Detection coverage | Are mechanical/typed checks in place, or does the failure surface only via downstream confusion? |

Roll up: detection coverage rating + recovery coverage rating.

#### 4.1.3 Standards gaps

Inventory `docs/standards/` (in AZ). Cross-reference workflow code:

| Standard exists for | If yes, the standard | If no, where the criteria live |
|---|---|---|
| Issue spec quality | 0018 | (would be in code) |
| LLD mechanical validation | 0019 | `validate_mechanical.py` |
| LLD semantic quality | (none — embedded in Gemini prompt) | `docs/skills/0702c-LLD-Review-Prompt.md` |
| Test plan quality | 0020 | `review_test_plan.py` + `test_plan_validator.py` |
| Workflow error recovery | 0021 | (improvised by operator) |
| Mid-flight diagnosis | (none — see #1070 skill) | nowhere |

#### 4.1.4 Skills inventory by phase

| Phase | Phase definition | Inventory |
|---|---|---|
| **PRE-FLIGHT** | Before workflow runs | `/pre-flight-check` (#1069), `/lld-validate` (future), `/test-plan-validate` (future) |
| **MID-FLIGHT** | Autonomous run, in flight | (none yet — auto-retry #1071 + revise #1072 are workflow-internal) |
| **POST-FLIGHT** | After completion / halt | `/cleanup`, `/handoff`, `/park`, `/commit-push-pr`, `/code-review`, `/workflow-status` (#1070) |
| **INFRASTRUCTURE / META** | Maintenance + auxiliary | `/onboard`, `/dependabot`, `/audit`, `/blog-draft`, etc. |

### 4.2 Method

Phase B is parallelizable. Run 3 Explore agents concurrently:

| Agent | Task |
|---|---|
| 1 | Phase B.1 issue-spec assessment (sample issues, score, roll up) |
| 2 | Phase B.2 workflow node walk (read both graphs, write resilience table) |
| 3 | Phase B.3 + B.4 standards + skills inventory |

Synthesize their reports into the deeper audit doc.

### 4.3 Output Template (Phase B)

```markdown
# 0002 — AssemblyZero Workflow Readiness, Deeper Audit

**Auditor:** {agent name + model}, {date}
**Subject:** Beyond pre-flight — spec quality, workflow node resilience, missing standards & skills
**Scope:** Follow-up to `0001-...md` (which fixed config gaps); answers
"even after pre-flight, where will it break, and what's missing
structurally to prevent that."
**Trigger:** {what surfaced this deeper audit, e.g., user question}

---

## TL;DR

{Three findings: spec quality bottleneck, workflow resilience surface,
standards gaps. Identify the load-bearing one for the next demo.}

---

## 1. Spec quality of {target}'s {N} open issues

{Sample assessment: 3 issues at different quality levels, scored against
0018's six dimensions, with verdict per issue.}

{Roll-up table: lld-ready / lld-needs-revision / wrong-workflow counts.}

{Implication for the demo: which issue to pick first, why.}

---

## 2. Workflow node-by-node resilience surface

### 2.1 LLD workflow

{Per-node table: failure mode, recovery available.}

### 2.2 Implementation workflow

{Per-node table.}

### 2.3 Net resilience pattern

{Detection coverage rating + recovery coverage rating + observation
about iterative-hardening pattern.}

---

## 3. Standards gap analysis

{Table: standard X exists for Y / not yet — and where the criteria live
when the standard doesn't.}

{What's missing — the cost of each gap.}

---

## 4. Skills gap analysis

{By-phase inventory.}

{Concrete absent skills.}

---

## 5. How to tell

{Pre-flight checklist for an individual issue.}
{Mid-flight observation signs.}
{Post-flight validation.}

---

## 6. Concrete recommendations

### 6.1 Before recording the demo
{Items that block the recording.}

### 6.2 To file as backlog issues against AssemblyZero
{Standards / skills / features that improve robustness.}

### 6.3 To file as {target}-specific issues
{Triage / authoring / chore tasks.}

---

## 7. Net assessment

{Three honest answers: workflow ready? architecturally complete? specs
sufficient?}

---

## Appendix: References

{Code paths + standards + lineage of hardening issues.}
```

The boostgauge audit (`docs/audit-results/0002-...md` in that repo) is the canonical example.

---

## 5. Output Cross-Cutting Conventions

Both audit docs follow these conventions:

- **Filename pattern:** `{NNNN}-assemblyzero-{topic}-readiness-{date}.md` where date is `YYYY-MM-DD`. The topic distinguishes 0001 (config gaps) from 0002 (deeper).
- **Auditor identification:** every audit names the agent + model + date so future reads can decide whether the audit is current.
- **TL;DR up top:** every audit has a TL;DR section that answers the load-bearing question in the first 3 paragraphs. The rest is detail.
- **Citations are mandatory.** Every claim about workflow behavior cites a file path + line number. The audit must be re-readable in a year when nobody remembers the original conversation.

---

## 6. Recommended Explore-Agent Prompts

The following prompts produced useful inventory data for the boostgauge audit. Reuse / adapt for new targets.

### 6.1 Phase A — config-gaps inventory

```
Audit the AssemblyZero workflow-readiness of {target_repo_path}. Use Grep,
Glob, Read; do not modify files. For each surface in this list, report
present / missing / misconfigured with a one-line evidence excerpt:

- Repo bootstrap commit ("initialize project with AssemblyZero")
- CLAUDE.md present and ≥50 lines
- GEMINI.md present and ≥40 lines
- .unleashed.json present, assemblyZero=true
- .claude/hooks/secret-file-guard.sh present
- docs/lld/active, docs/lld/done, docs/reports/active directories
- tests/ subcategories
- pyproject.toml + poetry.lock + pytest in dev deps
- .github/workflows/auto-reviewer.yml
- Open issues queued for workflow
- Working tree status

Output a markdown table.
```

### 6.2 Phase B.1 — issue spec quality

```
Sample {N} open GitHub issues from {owner/repo}. For each, score against
the six dimensions of standard 0018 (verb test, acceptance criteria,
file mention, scope-bound, determinism, test plan). Output a per-issue
table + a roll-up by category (lld-ready, lld-needs-revision,
wrong-workflow).
```

### 6.3 Phase B.2 — workflow node walk

```
Walk assemblyzero/workflows/requirements/graph.py and
assemblyzero/workflows/testing/graph.py. For each node, identify:

- failure mode (what causes it to halt or loop)
- recovery available (auto-retry, revise, --resume flag, terminal HALT)
- detection coverage (typed checks vs. silent-pass risk)

Output two tables (one per workflow) + a net assessment paragraph.
```

### 6.4 Phase B.3 — standards + skills gaps

```
Inventory docs/standards/ in AZ. Cross-reference each workflow gate
identified by Phase B.2 against the standards: which gates are backed
by a published standard, which live in code only?

Then inventory .claude/commands/ in {target_repo_path} and AZ. Group
by phase (PRE-FLIGHT, MID-FLIGHT, POST-FLIGHT, META). Identify the
phase with the lightest coverage.
```

---

## 7. Filing Follow-Up Issues

After the audit, file follow-up issues:

| Repo | Issue type | Examples |
|---|---|---|
| AssemblyZero | Standards (#1065-1068) | Lift code-embedded criteria into a published standard |
| AssemblyZero | Skills (#1069/1070/1075) | Pre-flight, mid-flight, post-flight gaps |
| AssemblyZero | Workflow features (#1071/1072/1076) | Auto-retry, BLOCKED recovery, instrumentation |
| Target repo | Triage | Score every existing issue with the labels `lld-ready`, `lld-needs-revision`, `wrong-workflow` |
| Target repo | Repo-specific | Demo issue authoring, audit-driven cleanups |

The boostgauge audit produced 12 AZ backlog issues (#1065-1076) and 6 boostgauge issues (#31-#36). That's a typical scale.

---

## 8. Maintenance

When the AZ workflows gain a new failure mode / standard / skill:

1. Update the relevant §3.1 / §4.1 inventory list here (add the new surface to check).
2. Update §6.X recommended Explore prompts to mention the new check.
3. Update the standards / skills cross-reference tables.

---

## 9. References

- **The skill that automates this runbook:** AZ #1070 / `.claude/commands/readiness-audit.md` (companion file shipping with this runbook).
- **Source standards referenced:** 0009 (canonical project structure), 0018 (issue spec quality), 0019 (LLD mechanical), 0020 (test plan quality), 0021 (workflow error recovery).
- **Source skills referenced:** `/pre-flight-check` (#1069), `/workflow-status` (#1070), `/visual-verify` (#1075).
- **Workflow features that the audit takes credit for surfacing:** #1071 (auto-retry), #1072 (BLOCKED recovery), #1076 (speedrun instrumentation).
- **Canonical example outputs:** `boostgauge/docs/audit-results/0001-assemblyzero-workflow-readiness-2026-05-09.md` and `0002-assemblyzero-deeper-readiness-2026-05-09.md`.

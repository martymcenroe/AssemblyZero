# Workflow Error Recovery Procedures

<!-- Standard: 0021 -->
<!-- Version: 1.0 -->
<!-- Last Updated: 2026-05-09 -->
<!-- Issue: #1068 -->

> **Purpose:** Document the operator-side recovery procedure for each known failure mode of the LLD and implementation workflows. Until now, recovery was improvised — each operator chose between `--resume`, `--resume-review`, `--auto-mode`, manual LLD edits, model swaps, and budget bumps based on intuition. This standard names the failure mode, points at the diagnostic signal that identifies it, and prescribes a concrete recovery sequence.

---

## 1. Overview

Workflows fail. When they do, the question is never *if* the operator should respond, but *how*. This standard maps each failure mode to:

1. **The diagnostic signal** — what you see in the console + audit trail that identifies which mode hit.
2. **The first-line defense** — automatic recovery (#1071 retry, #1072 revise) — does it apply, and did it run?
3. **The operator-side recovery** — the command sequence to run when first-line defenses can't fix it.
4. **When to abort** — the exit conditions that mean "this take is dead, restart from scratch."

### 1.1 First-Line Defenses (Automatic)

Two automated recovery paths run before the operator sees a halt:

| Defense | Issue | What it covers |
|---|---|---|
| **Workflow auto-retry** | #1071 | Transient API failures (5xx, 429, timeouts) at any LLM-calling node. 5 retries by default with 2s→32s exponential backoff. |
| **Test-plan revise** | #1072 | BLOCKED verdict at testing-workflow N1. Up to 2 revision cycles before END. |

When you see a halt, **first check whether the auto-defense ran and exhausted**. The recovery procedures below assume the automatic path either didn't apply or has already exhausted.

### 1.2 Recovery Posture by Speed-Run Phase

For the boostgauge speed-run, the recovery posture changes by attempt phase:

- **Off-camera dry runs** (≥2, ideally 5+): Apply full recovery. Take time to fix root causes. Update the LLD. Tune retry policy. The dry runs are where these procedures matter most.
- **On-camera takes**: Recovery is constrained by recording dead-air budget. For each failure mode below, the table marks which procedures are *take-recoverable* (can finish on-camera) vs. *take-killing* (cut the recording).

---

## 2. The Five Failure Modes

The five named modes from the boostgauge readiness audit (`0002` §2). Each has its own §2.N section.

### 2.1 API Quota / Cost Budget Exhaustion

**Symptom:**

- Console: `[ERROR] Reviewer failed after up to N attempts: ... credit balance is too low / quota exhausted` (or similar).
- Verdict source: `BillingError` from `classify_anthropic_error` / `classify_gemini_error` (errors.py).
- `LLMCallResult.retryable=False` — auto-retry does NOT apply (correctly, since retrying a billing error wastes more money).

**First-line defense:** None. Billing errors are explicitly non-retryable.

**Operator recovery (preferred):**

```bash
# Diagnose: read the cumulative cost and the per-node breakdown
gh issue view <N> --repo martymcenroe/<repo> --comments | tail -30
# (the workflow emits cost summaries to status.json + the workflow.cost
# event log; check both)

# Option A: Bump the budget via --budget for next run.
PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue <N> --repo /c/Users/mcwiz/Projects/<repo> \
    --budget 5.00     # was probably 1.00 or 2.00; adjust upward

# Option B: Switch reviewer to a cheaper model (claude:haiku, gemini:3-flash).
PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue <N> --repo /c/Users/mcwiz/Projects/<repo> \
    --reviewer claude:haiku
```

**Operator recovery (alternate):** If Anthropic API key billing is the problem, the `claude` CLI provider via Max subscription is free — verify `set_api_policy(False)` (default, see `llm_provider.py:144`). If you've manually opted into the API with `--allow-api`, drop the flag.

**When to abort:** PyPI publish path (#1074) is unaffected — that's PyPI side, not LLM cost. For LLM-cost halts, abort only if you've already exceeded the workflow's built-in cost budget by 3× and the failure is stagnating regardless.

**Take-recoverable?** No on a fresh take. The cost-budget halt happens late in the workflow (after meaningful spend); restarting in-take with a higher budget burns recording time twice. Off-camera dry-run problem.

### 2.2 Gemini 5xx / 429 / Connection Timeout

**Symptom:**

- Console: `[N1/N3 reviewer transient failure (attempt N/M, status=503); sleeping ...s then retrying`. After exhaustion: `[N1/N3 reviewer retries exhausted ...`.
- Verdict source: `CapacityError` (503/529), `RateLimitError` (429), or `TimeoutError_` from the typed hierarchy.
- `LLMCallResult.retryable=True` — auto-retry from #1071 applies.

**First-line defense:** #1071 with_retry. With default policy, 5 retries × 2s→32s backoff = up to ~62s of automatic recovery before the operator sees a halt. Server `Retry-After` header is honored regardless of policy.

**Operator recovery (in this order):**

1. **Bump the retry policy** — re-run with `--retry-policy aggressive` (8 retries × 60s cap = up to ~4 minutes of automatic backoff).

   ```bash
   PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
       --issue <N> --repo /c/Users/mcwiz/Projects/<repo> \
       --retry-policy aggressive
   ```

2. **If the halt was at the LLD reviewer (N3), use `--resume-review`** — preserves the validated draft instead of restarting from N1.

   ```bash
   PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
       --type lld --issue <N> --repo /c/Users/mcwiz/Projects/<repo> \
       --resume-review
   ```

3. **Switch model temporarily** — if Gemini is the persistently-down provider, swap to claude:opus for the take-affecting node:

   ```bash
   PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
       --issue <N> --repo /c/Users/mcwiz/Projects/<repo> \
       --reviewer claude:opus
   ```

**When to abort:** Persistent provider outage that's affecting both Gemini and Claude — extremely rare. Check the provider status pages before assuming this.

**Take-recoverable?** Conditionally yes. If `--retry-policy aggressive` is set on the spawn, transient bursts up to ~4 minutes recover automatically. Anything longer cuts the take.

### 2.3 Two-Strike Stagnation (N3 reviewer)

**Symptom:**

- Console: `Two-strike stagnation HALT — same blocking issues twice` from the LLD workflow's N3 reviewer.
- `lld_status: BLOCKED` in workflow state, with `error_message` containing the stagnation marker.
- Audit trail: two consecutive verdict files (`004-verdict.md`, `005-verdict.md`) with similar BLOCKING content.

**First-line defense:** None. Stagnation is a quality issue, not a transient one — auto-retry would just produce more BLOCKED verdicts.

**Operator recovery:**

1. **Read both stuck verdicts.** Look at `docs/lineage/active/<issue>-lld/00X-verdict.md` for the latest two. Identify what the reviewer keeps asking for.

2. **Edit the LLD manually** if the issue is fixable in 5 minutes (a missing section, an unclear function signature). Then resume:

   ```bash
   PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
       --type lld --issue <N> --repo /c/Users/mcwiz/Projects/<repo> \
       --resume-review     # uses the manually-edited draft
   ```

3. **Swap to a different reviewer model** if the current one keeps making the same critique that doesn't translate to actionable revision:

   ```bash
   PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
       --type lld --issue <N> --repo /c/Users/mcwiz/Projects/<repo> \
       --reviewer claude:opus   # was probably gemini
   ```

4. **As a last resort, skip the gate.** Gate the LLD by hand instead of by reviewer:

   ```bash
   PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
       --type lld --issue <N> --repo /c/Users/mcwiz/Projects/<repo> \
       --review none   # no human gate; reviewer-driven only
   ```

   (Use sparingly — bypassing the gate is appropriate only when you've already manually validated the LLD.)

**When to abort:** Stagnation on the same revision after 3 attempts despite manual edits — the issue spec itself probably fails the AZ-#1065 quality dimensions. Stop, file an issue, fix the spec.

**Take-recoverable?** No. Stagnation surfaces a real problem with the LLD; on-camera recovery requires the operator to read two verdicts and reason about them, which is dead-air time. Cut the take.

### 2.4 Mechanical Validation Max-Iterations (N1.5 in LLD workflow)

**Symptom:**

- Console: `MECHANICAL VALIDATION FAILED:` followed by an error list, repeated for `max_iterations` (default 20) drafts.
- `lld_status: BLOCKED`, `validation_iteration_count == max_iterations`.
- Audit trail: `validation-errors-draft<NNN>-<TS>.md` files in the lineage dir (per #334) — 20 of them, each with the same / similar errors.

**First-line defense:** The workflow loops back to N1 (drafter) after each validation failure, providing the validation errors as feedback. So the drafter HAS already had ~20 chances to fix it. If you're seeing this halt, all 20 cycles failed.

**Operator recovery:**

1. **Read the latest 2-3 validation-error files** in the lineage dir. They tell you what specifically the validator keeps catching.

2. **Common causes (per standard 0019):**

   | Error pattern | Likely cause | Fix |
   |---|---|---|
   | `File marked Modify but does not exist` | Hallucinated file path | Verify actual path; `gh search code` if unsure |
   | `Section X missing from LLD` | Drafter omitted a mandatory section | Re-prompt the drafter with explicit section requirement |
   | `Title issue number doesn't match` | Drafter context bleed | Re-run with `--no-cache`; check input issue number |
   | `Path uses 'src/' but that directory doesn't exist` | Convention mismatch | Either add `src/` to repo OR change LLD paths |

3. **If the issue is in the LLD template / drafter prompt**, fix it upstream. The fix is usually obvious once you've read 3 consecutive failures.

4. **As a tactical workaround for an in-flight take**, edit the latest LLD draft directly (in `docs/lld/active/LLD-NNN.md`) to fix the mechanical issue, then resume:

   ```bash
   PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
       --type lld --issue <N> --repo /c/Users/mcwiz/Projects/<repo> \
       --resume-review
   ```

**When to abort:** Validation-loop max-iterations is rare; if it happens, the LLD task is genuinely too hard for the current drafter. Often correlates with the issue spec failing AZ-#1065 §2 (vague acceptance criteria). Off-camera, not on-camera, problem.

**Take-recoverable?** No. Reading 20 validation-error files mid-take is impossible. Cut.

### 2.5 Test-Plan BLOCKED at N1 (testing workflow)

**Symptom:**

- Console: `Reviewer failed after up to N attempts: BLOCKED — Test plan needs revision`.
- `test_plan_status: BLOCKED`, `gemini_feedback` populated with reasoning.

**First-line defense:** #1072 revise. Up to 2 automatic revision cycles before END. Each cycle: feed feedback to revisor → revisor produces fresh Test Scenarios table → loop back to N1 for re-review.

**Operator recovery (when revise exhausts):**

1. **Read the BLOCKED feedback** in the console output (or `docs/lineage/active/<issue>-testing/`). It identifies which scenarios are insufficient.

2. **Pick the recovery flag:**

   | Flag | When to use |
   |---|---|
   | `--test-plan-policy strict` | Pre-#1072 behavior — END on BLOCKED. Useful when you want to discover BLOCKED early instead of seeing 2 revision cycles burn first. |
   | `--test-plan-policy auto` | Bypass the gate entirely. **Tactical only — proceed with a reviewer-rejected test plan.** Appropriate when you've already verified the test plan by hand. |
   | (default) `--test-plan-policy revise` | Already failed twice; switching to strict OR auto won't help unless you also change the LLD's test plan. |

3. **Best path: revise the LLD's Test Plan section by hand**, then re-run:

   ```bash
   # Edit docs/lld/active/LLD-NNN.md, Section 10 (Test Scenarios)
   PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
       --issue <N> --repo /c/Users/mcwiz/Projects/<repo>
   ```

4. **For an on-camera take**: pre-validate the LLD's test plan offline before recording. The first-line revise should handle BLOCKED in most cases; manual recovery is for when the LLM cannot produce parseable scenarios after 2 tries.

**When to abort:** BLOCKED-after-revise-exhausted indicates the LLD's structure can't be parsed by the revisor. Almost always means standard 0020 §6 anti-patterns are in the LLD's Test Plan. Off-camera fix.

**Take-recoverable?** With `--test-plan-policy revise` on the spawn (now the default), about 10-30 seconds of automatic revision before the take feels stalled — that's dead-air budget. If revise succeeds, you're back on track. If it exhausts, cut.

---

## 3. Audit Trail Reading

When recovery requires understanding *why* the workflow halted, the audit trail is your source of truth. Locations:

| Workflow | Audit dir | Notable files |
|---|---|---|
| LLD requirements (`run_requirements_workflow.py`) | `docs/lineage/active/<issue>-lld/` | `001-issue.md` (input), `002-draft.md` (first draft), `003-verdict.md` (first verdict), ..., `validation-errors-draft<NNN>-<TS>.md` (per #334) |
| Implementation (`run_implement_from_lld.py`) | `docs/lineage/active/<issue>-testing/` | `verdict.md` (test plan review), `verdict-mechanical.md` (fast-path), `reviewer-error.md` (LLM call failure), `report.md` (test report) |

**Skill shortcut (AZ #1070):** `/workflow-status <issue>` reads the audit trail and tells you where the workflow last halted, why, and what `--resume*` flag would resume from there. Use that as the first diagnostic step.

---

## 4. Decision Tree

When a workflow halts, walk this tree top-to-bottom:

```
START: workflow halted with error_message X
│
├─ Was an auto-defense supposed to run?
│  ├─ Transient (5xx/429/timeout) → check #1071 retry log
│  │  ├─ Retried and exhausted → §2.2 step 1 (aggressive policy)
│  │  └─ Retry didn't apply (retryable=False) → check error type
│  │     ├─ Billing → §2.1 (cost / quota)
│  │     └─ Auth → fix credentials, NOT in scope of recovery
│  │
│  ├─ Test plan BLOCKED → check #1072 revise log
│  │  ├─ 2 cycles exhausted → §2.5 (manual edit OR --test-plan-policy)
│  │  └─ revision_count<2 (stuck before exhaust) → unusual, investigate
│  │
│  └─ Other halt → no auto-defense applies, continue diagnosis.
│
├─ Is it stagnation (same blocking issues twice)?
│  → §2.3 (read both verdicts, edit LLD or swap reviewer)
│
├─ Is it mechanical validation looping?
│  → §2.4 (read latest validation-errors-draft files)
│
└─ Else: read /workflow-status output, then this standard's §2 by symptom.
```

The decision tree is the operator-side version of `classify_halt(state)` from #1076 — same eight categories, surfaced in human-readable steps.

---

## 5. Cross-References

| Section | Related |
|---|---|
| §2.1 cost / quota | `errors.py` `BillingError`; `set_api_policy` in `llm_provider.py:144` |
| §2.2 transient | **AZ #1071** (workflow auto-retry), `assemblyzero/utils/retry.py`, `--retry-policy` flag |
| §2.3 stagnation | AZ #503 (origin), `--resume-review` (added by #536), `--review` flag |
| §2.4 mechanical | **Standard 0019** (the validator's checks), `validate_mechanical.py`, lineage dir layout |
| §2.5 test plan | **AZ #1072** (revise + recovery), **Standard 0020** (test plan quality criteria), `--test-plan-policy` flag |
| §3 audit trail | **AZ #1070** (`/workflow-status` skill — the human-readable interpreter), Issue #380 (status file format) |
| §4 decision tree | **AZ #1076** (`classify_halt` — programmatic equivalent), `assemblyzero/utils/speedrun.py` |

---

## 6. Maintenance

### 6.1 Updating Procedures

When a new failure mode is discovered:

1. Add a new §2.N section with symptom, first-line defense, recovery, abort criteria, and take-recoverability.
2. Update §1.1 if a new automatic recovery path ships (e.g., AZ #X for "Y").
3. Update §4 decision tree to route to the new section.
4. Update §5 cross-references.
5. Bump this standard's `<!-- Version: -->` and add a row to §6.2.

### 6.2 Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-05-09 | Initial version (Issue #1068). 5 failure modes documented + decision tree + audit-trail reference. |

---

## 7. References

- **Audit:** `boostgauge/docs/audit-results/0002-assemblyzero-deeper-readiness-2026-05-09.md` §2 + §6 (origin of the failure-mode taxonomy).
- **First-line defenses:** AZ #1071 (auto-retry), AZ #1072 (test-plan revise).
- **Diagnostic skill:** AZ #1070 (`/workflow-status`).
- **Speedrun classifier:** AZ #1076 (`classify_halt` in `assemblyzero/utils/speedrun.py`).
- **Adjacent standards:** 0018 (issue spec quality — pre-flight), 0019 (LLD mechanical validation criteria), 0020 (test plan quality criteria).
- **Workflow code:**
  - `tools/run_requirements_workflow.py` (LLD entry point; `--resume-review` flag)
  - `tools/run_implement_from_lld.py` (implementation entry point; `--retry-policy`, `--test-plan-policy`)
  - `assemblyzero/workflows/requirements/graph.py` (LLD graph; stagnation detection at N3)
  - `assemblyzero/workflows/testing/graph.py` (testing graph; BLOCKED routing per #1072)
- **Hardening lineage:** AZ #503 (stagnation), #536 (resume-review), #773 (cost budgets), #1071 (auto-retry), #1072 (revise), #1076 (classifier).

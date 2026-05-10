# Issue Spec Quality Checklist

<!-- Standard: 0018 -->
<!-- Version: 1.0 -->
<!-- Last Updated: 2026-05-09 -->
<!-- Issue: #1065 -->

> **Purpose:** Define the rubric used to determine whether a GitHub issue is suitable input for the AssemblyZero LLD workflow. An issue that fails this rubric should be revised — or routed to a different workflow entirely — before invoking `tools/run_requirements_workflow.py`. Running the LLD workflow on a malformed issue costs tokens and burns revision cycles producing low-quality drafts that the reviewer eventually rejects.

---

## 1. Overview

`assemblyzero/workflows/requirements/nodes/load_input.py` ingests any GitHub issue (title + body) and runs the drafter on it. There is no pre-flight validation that the issue is feature-shaped or has the structure the drafter consumes well. Vague one-line issues produce vacuous drafts; research-shaped issues produce hallucinated code suggestions that conflate research summary with implementation. Both fail late, at the reviewer's REVISE verdicts, after meaningful token spend.

This standard defines a six-dimension rubric that operators (and `/pre-flight-check`, AZ #1069) can use to decide whether an issue is ready for the workflow.

### 1.1 Distinction from Other Quality Gates

| Standard | Stage | What it gates |
|---|---|---|
| **0018 (this doc)** | Pre-LLD-workflow | Is the GitHub issue input fit for the drafter? |
| 0019 | LLD mechanical | Is the LLD draft structurally complete? |
| 0701 | Implementation spec template | What sections must the spec have? |
| 0702 | Implementation readiness review | Is the spec semantically implementable? |

0018 fires earliest in the pipeline. The cost of a 0018 failure is lowest (operator-time only); the cost of failing later is workflow tokens, agent time, and operator review on a draft that was doomed at input.

### 1.2 Workflow Position

```
GitHub issue → [0018 check] → run_requirements_workflow.py → LLD draft → [0019 mechanical] → [reviewer] → ...
                    ^
                    |
            Operator and/or /pre-flight-check skill apply this rubric.
            Failure here means: revise the issue, or pick a different workflow.
```

---

## 2. The Six Dimensions

An issue must satisfy all six to be considered ready for the LLD workflow. Each dimension has a binary check; partial credit is not awarded.

### 2.1 Dimension 1: Strong-Verb Title

**Question:** Does the title describe code that will exist after this work?

| Pass | Fail |
|---|---|
| `feat: add Telltale peak-hold needle logic` | `research: figure out scoring algorithms` |
| `fix: handle 503 errors in reviewer node` | `discussion: should we adopt X?` |
| `refactor: extract retry logic into shared module` | `note: ideas for next quarter` |
| `chore: bump pytest to 8.x` | `question: why does Y happen?` |

**Rule of thumb:** If the title starts with `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`, or `perf:` AND names a specific deliverable, dimension 1 passes. Titles that describe a *topic* rather than a *deliverable* fail.

**Why it matters:** The drafter expects to design code. When the title points at "investigate" or "discuss," the drafter has nothing concrete to design. It will fabricate something — typically a research summary masquerading as a design — that the reviewer cannot evaluate against acceptance criteria.

### 2.2 Dimension 2: Acceptance Criteria as Binary-Verifiable Checkpoints

**Question:** Does the body contain a list of objectively-true-or-false checkpoints that an implementation can be measured against?

| Pass | Fail |
|---|---|
| `- [ ] Function returns dict with 'result' and 'count' keys` | `Should be fast and reliable` |
| `- [ ] Test plan covers null input case` | `Make it work better` |
| `- [ ] No regressions in tests/test_foo.py` | (no acceptance section at all) |
| `- [ ] Standard doc lists 5–7 dimensions` | `Eventually we want X` |

**Count needed:** ≥ 1. A single concrete checkpoint passes; zero checkpoints fail.

**Why it matters:** The reviewer node uses the issue's acceptance criteria as the ground truth against which to evaluate the LLD's "Acceptance Criteria" section. If the issue has no checkpoints, the reviewer has nothing to compare against and will either rubber-stamp APPROVE (silent pass at `review.py:207`) or thrash on subjective criteria.

### 2.3 Dimension 3: Explicit IN/OUT Scope Statement

**Question:** Does the body name what is in scope and what is deliberately out?

| Pass | Fail |
|---|---|
| `## Out of scope: GUI rendering — covered by #N` | (only "in scope" implied; no "out") |
| `IN: retry on 503/529 only. OUT: retry on 4xx.` | `Make the system more resilient` |
| `Scope: this issue covers the Python module only. PyPI publish is #1074.` | (no scope section) |

**Rule of thumb:** The body must contain at least one explicit "out of scope" or "not in this issue" statement. The OUT statement is what prevents the workflow from over-scoping the LLD.

**Why it matters:** Without an OUT statement, the drafter is free to expand scope, and the reviewer is free to ask "what about X?" repeatedly. Scope arguments cause revision cycles. An explicit OUT statement is a forcing function for the issue author to think about boundaries before the workflow runs.

### 2.4 Dimension 4: File Paths or Modules Named in Body

**Question:** Does the body reference at least one specific file path, module, or function the work touches?

| Pass | Fail |
|---|---|
| `New module: assemblyzero/utils/retry.py` | `Add some retry logic` |
| `Modify: docs/standards/0009-canonical-project-structure.md §3.2` | `Update the standards doc` |
| `Touches: tools/new_repo_setup.py + a new release.yml template` | `Set up packaging` |

**Count needed:** ≥ 1 named path/module/function. Generic references ("the workflow," "the codebase") do not count.

**Why it matters:** The drafter's first job is to identify which files change. When the body names files, the drafter has a starting point and the reviewer has a way to verify that "File Changes" in the LLD aligns with author intent. When the body is silent, the drafter guesses, and guesses tend to drift across revision cycles.

### 2.5 Dimension 5: Determinism

**Question:** Would two competent engineers reading this issue produce substantially the same code?

This is the dimension closest to subjective judgment, and it's where the rubric applies *meta-judgment* rather than a checklist. Apply this test:

> Imagine handing the issue to two engineers in parallel. They cannot ask questions. After eight hours, do their PRs differ in *what code they write* or only in *style and naming*?

| Pass | Fail |
|---|---|
| `feat: add Configuration class with .load(path) and .save(path), JSON-only, no validation` | `feat: a config system` |
| `fix: validate_mechanical.py:45 — replace strict equality with normalized comparison` | `fix: validation is too strict` |
| `feat: add `--retry-policy` flag to run_requirements_workflow.py with values {none, conservative, aggressive}` | `add a retry mechanism` |

**Rule of thumb:** If the issue lets the implementer choose between two materially different architectures (sync vs. async, dataclass vs. typeddict, OOP vs. functional, etc.), it fails. If those choices are pre-made or constrained, it passes.

**Why it matters:** Non-deterministic issues produce non-deterministic LLDs. Two runs against the same issue produce different drafts; the reviewer can't tell which is "right" because there is no right answer baked into the input. Determinism is what makes the workflow repeatable and reviewable.

### 2.6 Dimension 6: Test Plan or Test Signal

**Question:** Does the body indicate how the work will be verified?

| Pass | Fail |
|---|---|
| `Test plan: unit test for each public function; integration test against tests/fixtures/...` | (no test mention) |
| `Verify by: pytest tests/unit/test_retry.py passes; existing suite green` | `Make sure it works` |
| `Acceptance criteria above are themselves testable` (when criteria are concrete) | `We'll figure out testing later` |

**Note:** If dimension 2 passes with concrete binary-verifiable acceptance criteria, those criteria *can themselves* serve as the test signal. Dimension 6 is then satisfied implicitly. But the issue must make this connection clear (e.g., "acceptance criteria above are testable as written") rather than leaving the reader to guess.

**Why it matters:** The implementation workflow's test-plan-review node (N1 in testing graph) consumes the LLD's "Test Plan" section, which is derived from the issue. If the issue is silent on testing, the LLD's test plan is fabricated, and the reviewer at N1 will return BLOCKED — terminal in the current workflow without `--auto` or AZ #1072.

---

## 3. Verdict

After scoring all six dimensions, render one of three verdicts:

### 3.1 PROCEED

**Criteria:** All 6 dimensions pass.

**Action:** Run `tools/run_requirements_workflow.py --type lld --issue {N} --repo {path} --yes` against the issue.

**Expected outcome:** First-pass APPROVED LLD or single-revision cycle. Token cost in the typical range; no terminal halts attributable to issue quality.

### 3.2 REVISE ISSUE

**Criteria:** 4 or 5 dimensions pass.

**Action:** Edit the GitHub issue (`gh issue edit {N} --body "..."`) to address the failing dimensions, then re-score. Do not run the workflow on a partially-failing issue — the cost of revising the issue is one operator-minute; the cost of the workflow producing a poor LLD is 5–30 minutes of wall time and tokens.

**Common revision targets:**
- Add an explicit OUT-of-scope statement (dimension 3).
- Add 2–3 binary acceptance criteria checkpoints (dimension 2).
- Name the files the work touches (dimension 4).

### 3.3 WRONG WORKFLOW

**Criteria:** Dimension 1 fails (research/discussion title), OR 3+ dimensions fail.

**Action:** Do not run the LLD workflow. The issue is asking for research, design exploration, or open-ended investigation. Options:
- Hand it to a human reviewer (or a Gemini chat session) for research summary.
- Decompose it into narrower feature-shaped issues that pass dimensions 1–6.
- Close it as out-of-scope-for-the-workflow if the work is not actually code.

**Anti-pattern:** Forcing a research issue through the LLD workflow. The output is a hallucinated design conflating research summary with code suggestions, which then has to be discarded. This is the failure mode that produced the boostgauge audit's wrong-workflow classification of issues #11, #12, #13, #21, etc.

---

## 4. Worked Examples

The boostgauge readiness audit (`docs/audit-results/0002-assemblyzero-deeper-readiness-2026-05-09.md` §1.1, in the boostgauge repo) provided three real issues at different quality levels. They are reused here as canonical examples.

### 4.1 Example 1 — PROCEED: boostgauge #4

**Title:** `feat: Windows data collector`

**Body summary:** Defines an abstract `DataCollector` base class with `.poll()` and `.shutdown()`. Specifies 5 metrics (CPU%, RAM%, ConPTY count, process count, GPU%) with collection frequency (2s default). Names the threading model (background thread, daemon=True). Lists 6 acceptance criteria as binary checkpoints (returns accurate values, < 1% CPU overhead, etc.). OUT-of-scope: GPU collection on non-NVIDIA hardware.

**Scoring:**

| Dimension | Result | Notes |
|---|---|---|
| 1. Strong-verb title | PASS | `feat:` + concrete deliverable |
| 2. Acceptance criteria (binary) | PASS | 6 checkpoints |
| 3. Explicit IN/OUT scope | PASS | "OUT: GPU on non-NVIDIA" |
| 4. File paths/modules named | PASS | Abstract base class hierarchy + module location |
| 5. Determinism | PASS | Two engineers would converge |
| 6. Test plan / signal | PASS | Acceptance criteria are testable as written |

**Verdict: PROCEED.** Expected outcome: usable LLD on first pass, no revision cycle expected.

### 4.2 Example 2 — REVISE ISSUE: boostgauge #18

**Title:** `feat: multi-gauge mode`

**Body summary:** Three layout options sketched in ASCII art for displaying multiple gauges simultaneously. Vague verbs in acceptance ("visually highlighted" — what style?). No explicit OUT statement. No file or module references. Layout algorithm is prescribed; visual polish is open to interpretation.

**Scoring:**

| Dimension | Result | Notes |
|---|---|---|
| 1. Strong-verb title | PASS | `feat:` + a deliverable |
| 2. Acceptance criteria (binary) | FAIL | Vague verbs; criteria are not binary |
| 3. Explicit IN/OUT scope | FAIL | No OUT statement; scope ambiguity (multi-screen? customizable count?) |
| 4. File paths/modules named | FAIL | Generic GUI references only |
| 5. Determinism | FAIL | Layout polish is non-deterministic |
| 6. Test plan / signal | FAIL | None |

**Verdict: WRONG WORKFLOW** (dimension 1 alone passes, 5 fail) — but only because the failures cluster on file/scope/determinism. **Reclassify as REVISE ISSUE if the author can quickly add:**
1. Concrete OUT statement: "Multi-screen layouts and dynamic gauge-count are OUT of scope (separate issues)."
2. Specific files: "Touches `src/boostgauge/gui/multi_gauge_layout.py` (new) and `src/boostgauge/gui/main_window.py` (modify)."
3. Binary acceptance: "≥3 gauges render side-by-side at 60fps", "no overlap at any window size ≥ 800×600."

After those edits, dimensions 2/3/4/5/6 flip to PASS and the issue is ready for the workflow.

### 4.3 Example 3 — WRONG WORKFLOW: boostgauge #12

**Title:** `research: deep dive — optimal system health scoring algorithms`

**Body summary:** Asks for research into 2-3 candidate algorithms for combining CPU/memory/disk metrics into a single "health score." References issue #3 (which would consume the research output). Acceptance is "find 2-3 algorithms with tradeoffs documented."

**Scoring:**

| Dimension | Result | Notes |
|---|---|---|
| 1. Strong-verb title | FAIL | `research:` — describes investigation, not deliverable code |
| 2. Acceptance criteria (binary) | FAIL | "Find 2-3 algorithms" is research-shaped, not testable code behavior |
| 3. Explicit IN/OUT scope | FAIL | "Lightweight widget" undefined |
| 4. File paths/modules named | FAIL | No code paths; references issue #3 only |
| 5. Determinism | FAIL | Gemini's response determines the algorithm; non-deterministic |
| 6. Test plan / signal | FAIL | N/A — work product is documentation, not a feature |

**Verdict: WRONG WORKFLOW.** All six dimensions fail. The LLD workflow would produce a half-baked design conflating research summary with code suggestions. **Action:** route to a research process (manual Gemini chat, or a future research-report workflow if AZ ever adds one). Keep #3 (the consumer) open; close #12 as not-suitable-for-LLD-workflow OR convert into a narrowed `feat:` issue once the algorithm choice is made.

---

## 5. Failure Modes Without This Standard

The cost of skipping the rubric is observable in the audit trail of the LLD workflow:

| Failure mode | Cause | Cost |
|---|---|---|
| **Vacuous draft** (drafter produces generic boilerplate) | Issue body too thin (dimensions 2/4/6 fail) | Tokens spent on a draft that gets REVISE'd or rubber-stamped APPROVE'd |
| **Reviewer thrash** (multiple REVISE cycles converging on subjective taste) | Acceptance criteria not binary (dimension 2 fail) | 3–5 review iterations, escalating to two-strike stagnation HALT |
| **Wrong-workflow output** (LLD conflates research with code suggestions) | `research:` title + zero file paths (dimensions 1/4 fail) | Whole LLD discarded; manual reroute to research path |
| **Scope creep / under-scope** (LLD covers too much or too little) | No OUT statement (dimension 3 fail) | Reviewer asks "what about X?" repeatedly; revision cycles |
| **Test plan BLOCKED** at testing-workflow N1 | No test signal in issue (dimension 6 fail) | Implementation workflow terminates pre-coding (without AZ #1072 fix) |

Pattern: every failure mode listed is one the workflow has been hardened against retroactively (issues #277, #166, #248, #503, #536). Catching the failure pre-flight via this rubric is cheaper than detecting and recovering from it mid-flight.

---

## 6. Application

### 6.1 By an Operator (Manual)

Before invoking the workflow on issue #N:

1. Read the issue body.
2. Score it against the six dimensions in §2.
3. Apply the verdict matrix in §3.
4. If PROCEED: invoke the workflow.
5. If REVISE ISSUE: edit the issue, re-score, then invoke.
6. If WRONG WORKFLOW: route to a different process.

This takes ~2 minutes and saves 5–30 minutes of workflow wall-time on a doomed input.

### 6.2 By the `/pre-flight-check` Skill (Automated)

AZ #1069 will implement this rubric as the `/pre-flight-check` slash command. The skill will:

1. Fetch the issue via `gh issue view {N} --repo {O}/{R}`.
2. Apply the six checks (some can be automated by regex/heuristic; dimension 5 is LLM-judgment).
3. Render a verdict + per-dimension diagnostic output.
4. Suggest specific edits for failing dimensions.

The skill is the operator-facing automation of this standard. The standard itself is the source of truth that the skill implements.

### 6.3 By Issue Authors

When filing a new issue intended for the LLD workflow, structure the body to satisfy all six dimensions. A template that bakes in the structure:

```markdown
## Context
{Why this work matters; link to driving audit/issue/conversation.}

## Scope

### IN
- {Specific deliverable 1}
- {Specific deliverable 2}

### OUT
- {Excluded scope, with link to separate issue if applicable}

## Files Touched
- `{path/to/file.py}` — {modify | add | delete}
- `{path/to/another.py}` — {modify | add | delete}

## Acceptance Criteria
- [ ] {Binary checkpoint 1}
- [ ] {Binary checkpoint 2}
- [ ] {Binary checkpoint N}

## Test Plan
- {How verification happens; or note that acceptance criteria above are testable as-written}
```

Issues filed against this template typically pass all six dimensions on the first try.

---

## 7. Maintenance

### 7.1 Updating the Rubric

When the LLD workflow surfaces a new failure mode that maps onto issue quality:

1. Decide whether the mode fits an existing dimension or warrants a new one. Avoid adding dimensions casually — the rubric is six-by-design to keep operator overhead low.
2. Update §2 with the new check or expanded existing check.
3. Update §4 examples if the new check would have caught an example differently.
4. Update §5 failure-modes table.
5. Update the `/pre-flight-check` skill (AZ #1069) to apply the new check.

### 7.2 Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-05-09 | Initial version (Issue #1065) |

---

## 8. References

- [0019 — LLD Mechanical Validation Criteria](0019-lld-mechanical-validation.md) — what `validate_mechanical.py` actually checks (separate standard, AZ #1066).
- [0020 — Test Plan Quality Criteria](0020-test-plan-quality.md) — what the testing-workflow N1 reviewer evaluates (AZ #1067).
- [0701 — Implementation Spec Template](0701-implementation-spec-template.md) — template the implementation workflow drafts against.
- [0702 — Implementation Readiness Review](0702-implementation-readiness-review.md) — semantic implementability check, fires after this standard.
- AZ #1069 — `/pre-flight-check` skill that automates this rubric.
- Boostgauge audit `docs/audit-results/0002-assemblyzero-deeper-readiness-2026-05-09.md` §1 — origin of the dimensions.
- Workflow code: `assemblyzero/workflows/requirements/nodes/load_input.py` (entry point that bypasses these checks today).
- Related hardening issues: #277 (mechanical validation), #166 (test plan validation), #248 (open questions loop), #503 (two-strike stagnation), #536 (resume-review flag).

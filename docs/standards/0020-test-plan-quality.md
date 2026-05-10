# Test Plan Quality Criteria

<!-- Standard: 0020 -->
<!-- Version: 1.0 -->
<!-- Last Updated: 2026-05-09 -->
<!-- Issue: #1067 -->

> **Purpose:** Document the criteria the testing-workflow N1 reviewer (`review_test_plan`) uses to judge whether an LLD's test plan is implementable. The criteria span three layers: mechanical gates that fail fast before any LLM call, the deterministic `test_plan_validator` that catches vague language and human delegation, and the Gemini semantic review that judges test-type appropriateness and edge-case coverage. Until this standard existed, the criteria lived in code and prompt files — invisible to issue authors, LLD reviewers, and operators interpreting BLOCKED verdicts.

---

## 1. Overview

The implementation workflow's first node — `N1_review_test_plan` (`assemblyzero/workflows/testing/nodes/review_test_plan.py`) — consumes the Test Plan section of an approved LLD, judges its quality, and returns one of two states:

| Verdict | Effect |
|---|---|
| **APPROVED** | Workflow proceeds to N2 (scaffold tests). |
| **BLOCKED** | Workflow halts. No automatic recovery (until AZ #1072 lands). |

A BLOCKED verdict at N1 is terminal under current workflow design. The cost of producing one is high: the LLD round-trip is wasted, and the operator must manually iterate on the LLD before re-running. This standard describes the criteria a test plan must meet to avoid that fate.

### 1.1 Position in the Workflow

```
LLD finalized → N1_review_test_plan → N2_scaffold_tests → ...
                       |
                       | (BLOCKED — no auto-recovery)
                       v
                      END
```

The reviewer applies criteria in three layers, in order:

```
Layer 1: Mechanical Gates (Issue #496)        ← fail fast, no LLM cost
Layer 2: Mechanical Fast-Path (Issue #509)    ← 100% coverage auto-approves
Layer 3: Gemini Semantic Review               ← only if Layers 1+2 don't decide
```

### 1.2 Why Three Layers

- **Layer 1** catches structural failures cheaply ($0 cost, milliseconds).
- **Layer 2** auto-approves when mechanical coverage is perfect, saving Gemini calls (~$0.05–0.10 each).
- **Layer 3** is the semantic judgment for everything else. Gemini reviews test-type fit, edge-case coverage, and design quality.

Issue authors writing the Test Plan section of an LLD should aim for Layer 1 + Layer 2 to handle their submission — that's the cheapest, fastest, most deterministic path.

---

## 2. Layer 1 — Mechanical Gates

Implementation: `_run_mechanical_gates()` in `review_test_plan.py` (Issue #496).

These five gates run before any LLM call. Failure on any gate produces immediate BLOCKED verdict with the gate's error message in `gemini_feedback`.

### 2.1 Gate 1 — Test Scenarios Exist

**Check:** `state["test_scenarios"]` is a non-empty list.

**Pass:** ≥1 scenario extracted from LLD Section 10 (test plan section).

**Fail:** Empty list — usually means LLD Section 10 is missing, malformed, or has no parseable table.

**Failure message:** `No test scenarios found — LLD Section 10 may be missing or malformed`

**Why it exists:** Without scenarios, none of the downstream checks make sense. Failing at gate 1 short-circuits the entire review.

### 2.2 Gate 2 — Requirements Exist

**Check:** `state["requirements"]` is a non-empty list (extracted from LLD Section 3 by `extract_requirements()`).

**Pass:** ≥1 requirement parsed from LLD Section 3 numbered list.

**Fail:** No requirements — Section 3 missing, not formatted as a numbered list, or empty.

**Failure message:** `No requirements extracted from LLD — cannot verify coverage`

**Why it exists:** Coverage check (gate 3) needs a denominator. No requirements means coverage is undefined.

### 2.3 Gate 3 — Scenario-to-Requirement Coverage Ratio

**Check:** `len(test_scenarios) >= len(requirements)` (a necessary but not sufficient condition for 100% coverage).

**Pass:** At least as many scenarios as requirements.

**Fail:** Fewer scenarios than requirements — coverage ratio < 100% by pigeonhole even before mapping check.

**Failure message:** `Only {N} scenario(s) for {M} requirement(s) — coverage ratio {pct}% is below 100%`

**Why it exists:** Cheap pre-check that catches a common drafter mistake (writing 3 scenarios for 5 requirements). Doesn't replace the coverage mapping in Layer 2; just fails fast when the ratio is impossible.

### 2.4 Gate 4 — No Duplicate Scenario Names

**Check:** Trim + lowercase scenario names; verify uniqueness.

**Pass:** All scenario names distinct after normalization.

**Fail:** Two or more scenarios have the same name.

**Failure message:** `Duplicate scenario name(s): {names}`

**Why it exists:** Duplicates are usually a copy-paste artifact in the drafter's output. They cause downstream confusion when scenarios map to test files.

### 2.5 Gate 5 — Minimum LLD Substance

**Check:** `len(lld_content.split()) >= 50` (50-word floor).

**Pass:** LLD content has ≥50 words.

**Fail:** LLD content shorter than 50 words OR empty.

**Failure messages:**
- `LLD content too short ({N} words, minimum 50)`
- `No LLD content available for review`

**Why it exists:** A 10-word LLD has nothing to review. Fail fast and ask for revision rather than spend Gemini tokens to confirm "this is too thin."

---

## 3. Layer 2 — Mechanical Fast-Path (100% Coverage Auto-Approve)

Implementation: `check_requirement_coverage()` in `review_test_plan.py` (Issue #509).

After Layer 1 passes, the reviewer checks whether all requirements have explicit test coverage. If yes, the test plan is auto-approved without invoking Gemini.

### 3.1 The Coverage Check

**Inputs:**
- `requirements` — list of strings, normalized to `REQ-N` IDs by `extract_requirement_ids()`.
- `scenarios` — list of dicts, each with optional `requirement_ref` field, normalized to uppercase by `extract_covered_requirements()`.

**Computation:**
```python
covered = len(all_req_ids & covered_req_ids)
coverage_pct = (covered / total_req_count) * 100
```

**Pass condition:** `coverage_pct >= 100.0`.

**Effect on pass:** Verdict immediately set to APPROVED with method `mechanical_fast_path`. No Gemini call. Cost saved: ~$0.05–0.10 per run.

**Effect on fail:** Proceed to Layer 3 (Gemini semantic review).

### 3.2 Requirement ID Conventions

Requirements must use one of two formats for the coverage matcher to find them:

| Format | Example | Extracted as |
|---|---|---|
| Explicit ID | `REQ-1: Description` or `REQ-2.3: ...` | `REQ-1`, `REQ-2.3` |
| Numbered list | `1. Description` | `REQ-1` |

The extractor is case-insensitive (`req-1` → `REQ-1`) and handles dotted sub-IDs (`REQ-2.3`).

### 3.3 Scenario Reference Conventions

Each scenario in `state["test_scenarios"]` should have a `requirement_ref` field naming the requirement it covers:

```python
{"name": "test_handles_empty_input", "requirement_ref": "REQ-1", ...}
```

Multiple scenarios can reference the same requirement. A scenario without a `requirement_ref` does not count toward coverage.

### 3.4 What Authors Should Do

To hit Layer 2 auto-approval:

1. Number every requirement in LLD Section 3.
2. Reference each requirement by `REQ-N` (or numeric prefix `1.`, `2.`) in the scenario tables of Section 10.
3. Ensure `len(scenarios) ≥ len(requirements)` (Layer 1 gate 3).
4. Cover every requirement at least once.

A perfectly covered test plan auto-approves at $0 LLM cost in milliseconds. This is the target outcome.

---

## 4. Layer 3 — Gemini Semantic Review

When Layers 1 and 2 pass without auto-approving, the reviewer invokes Gemini with the prompt at `docs/skills/0706c-Test-Plan-Review-Prompt.md` (Issue #495). The prompt explicitly skips re-checking what the mechanical layers already verified, so it focuses on semantic quality.

### 4.1 Pre-Validated Items (Reviewer Skips)

Per the prompt's "Pre-Validated (Do NOT Re-Check)" section, the following are confirmed by Layers 1 + 2 + the standalone `test_plan_validator` and the reviewer trusts them:

- Test plan section exists with named scenarios.
- Requirement coverage ≥ 95% (the validator's threshold; the fast-path requires 100%).
- No vague assertions ("verify it works" patterns).
- No human delegation ("manual verification" patterns).

### 4.2 What Gemini Actually Reviews

Two semantic checks that produce **WARNINGs only** (semantic findings can BLOCK only if the verdict block sets it):

#### 4.2.1 Test Type Appropriateness (WARNING if mismatched)

For each scenario, Gemini judges whether the declared test type matches the functionality:

| Type | Expected characteristics |
|---|---|
| **Unit** | Isolated; mocks dependencies; tests a single function. |
| **Integration** | Tests component interactions; may use real DB. |
| **E2E** | Full user flows; minimal mocking. |
| **Browser** | Requires a real browser (Playwright/Selenium). |
| **CLI** | Tests command-line interfaces. |

The reviewer outputs a per-test table:

```markdown
| Test | Declared Type | Appropriate | Notes |
|---|---|---|---|
| test_x | unit | Yes | - |
| test_y | integration | No | Should be unit |
```

Mismatches surface as warnings; they do not BLOCK by themselves but contribute to a BLOCKED verdict if numerous.

#### 4.2.2 Edge Case Coverage (WARNING if missing)

Gemini checks whether the scenario set covers:

- Empty inputs.
- Invalid inputs.
- Boundary conditions.
- Error conditions.
- Concurrent access (if applicable).

Missing edge cases surface as warnings. Material gaps (e.g., no error-path tests at all) may BLOCK.

### 4.3 Verdict Format

The reviewer produces a structured response:

```markdown
## Test Type Review
{table per §4.2.1}

## Edge Cases
- [ ] Empty inputs covered
- [ ] Invalid inputs covered
- [ ] Error conditions covered

## Semantic Issues
{free-form issues with test logic, mock strategy, design}

## Verdict
[x] **APPROVED** - Test plan is ready for implementation
   OR
[x] **BLOCKED** - Test plan needs revision

## Required Changes (if BLOCKED)
1. {Specific, actionable change}
2. {Specific, actionable change}
```

The verdict line is parsed by `_parse_verdict()` (structured JSON first via `parse_structured_verdict`, regex fallback per Issue #775). `REVISE` is mapped to `BLOCKED` for workflow-routing purposes.

### 4.4 Reviewer Configuration

| Setting | Value | Notes |
|---|---|---|
| Reviewer model | `claude:opus` (default), or `gemini:3-pro-preview` | Set via `state["config_reviewer"]` (Issue #773). |
| Retries | 2 attempts with 2s, 4s exponential backoff | Inline retry; no integration with AZ #1071 yet. |
| Schema | `VERDICT_SCHEMA` (Issue #775) | Forces structured JSON when supported. |
| Effort | Configurable via `state["config_effort"]` | For Claude reviewer. |

---

## 5. The `test_plan_validator` — Standalone Mechanical Checks

Implementation: `assemblyzero/core/validation/test_plan_validator.py` (Issue #166).

This module provides a SEPARATE deterministic validator that runs in BOTH the requirements workflow (during LLD validation) and the testing workflow (during N1). It performs four check types, all regex-based, with a <500ms budget.

### 5.1 Coverage Check

**Threshold:** `COVERAGE_THRESHOLD = 0.95` (95%, less strict than the workflow's 100% fast-path).

**Computation:** Maps requirements (LLD Section 3) to scenarios (LLD Section 10.1, fallback to entire Section 10). Each scenario lists `requirement_refs` (a list, not a single ref).

**Severity:**
- ERROR if coverage < 95%.

### 5.2 Assertion Quality Check (Vague Pattern Detection)

**Patterns detected** (case-insensitive, word-boundary):

```python
VAGUE_PATTERNS = [
    r"\bverify\s+it\s+works\b",
    r"\bcheck\s+everything\b",
    r"\bensure\s+proper\s+behavior\b",
    r"\btest\s+that\s+it\s+is\s+correct\b",
    r"\bvalidate\s+functionality\b",
    r"\bconfirm\s+it\s+functions\b",
    r"\bshould\s+work\s+properly\b",
    r"\bworks\s+as\s+expected\b",
]
```

**Severity:** ERROR. Each match produces a violation pointing to the line.

**Why these patterns:** All eight describe verification that cannot be encoded as a deterministic test assertion. "Verify it works" is not testable; "verify `parse_config()` returns `{config_loaded: True, errors: []}` for valid input" is. The validator catches the former before they reach implementation.

### 5.3 Human Delegation Check

**Patterns detected** (case-insensitive, word-boundary):

```python
HUMAN_DELEGATION_PATTERNS = [
    r"\bmanual\s+verification\b",
    r"\bmanual\s+check\b",
    r"\bvisual\s+check\b",
    r"\bvisual\s+verification\b",
    r"\bhuman\s+review\b",
    r"\bmanual\s+inspection\b",
    r"\bvisually\s+inspect\b",
    r"\bmanually\s+verify\b",
]
```

**Severity:** ERROR. Each match produces a violation.

**Why these patterns:** All eight describe verification that depends on a human (the operator running the workflow). The implementation workflow runs autonomously and cannot pause for human inspection. ADR-0207 mandates real, executable tests — a test that says "verify visually" is not a test.

**Note for visual UI work:** When verification genuinely requires a screenshot diff or rendered-image check, use the `/visual-verify` skill (AZ #1075) inside an EXECUTABLE test (e.g., `assert visual_verify("output.png", expected="expected.png")`) — not a manual-inspection step.

### 5.4 Consistency Check

**What it checks:** Each scenario's `requirement_refs` list points to requirements that actually exist in the requirements set extracted from LLD Section 3.

**Severity:** WARNING for unresolved refs.

**Why it exists:** Catches typos like `REQ-12` when only `REQ-1` and `REQ-2` exist.

---

## 6. Anti-Patterns

These are the test-plan shapes the layered review rejects. Issue authors and LLD drafters should avoid them.

### 6.1 Vague Verbs in Assertions

Bad:
```markdown
| test_login | Login works correctly |
| test_save  | Saving the file works |
```

Good:
```markdown
| test_login | POST /login with valid creds returns 200 + session cookie |
| test_save  | save_config(path, data) writes data and returns Path; raises FileNotFoundError on missing parent |
```

### 6.2 Missing Error Paths

Bad: every scenario tests the happy path; no scenario tests what happens when input is invalid, the API is down, or the file is missing.

Good: at least one scenario per error class declared in the LLD ("invalid input → ValueError", "API timeout → retry then raise", "missing file → return None with warning").

### 6.3 Human Delegation Disguised

Bad:
```markdown
| test_renders | Visually inspect that the gauge renders correctly |
```

Good:
```markdown
| test_renders | render_gauge(value=50) writes a PNG; visual_verify(actual.png, expected.png) returns True |
```

The good version uses `/visual-verify` inside an executable assertion. The bad version stops the workflow at a human checkpoint that the autonomous implementation cannot satisfy.

### 6.4 Hand-Waving ("Will Be Tested")

Bad:
```markdown
| test_edge_cases | Edge cases will be tested |
```

Good: enumerate the edge cases as separate scenarios with concrete assertions.

### 6.5 Coverage Gap Hidden in Prose

Bad: requirements list 5 items; scenario table has 3 rows that don't reference requirement IDs at all. Reviewer can't verify coverage; falls through to Layer 3 where Gemini either approves (silent pass) or BLOCKs vaguely.

Good: every scenario row has a `requirement_ref` (or `Requirement` column) naming the requirement it covers. Layer 2 fast-path verifies coverage in milliseconds.

---

## 7. Worked Examples

### 7.1 PASS at Layer 2 — Auto-Approved (Best Outcome)

**LLD Section 3 (Requirements):**
```markdown
1. Configuration loads from JSON file path.
2. Invalid JSON path raises FileNotFoundError.
3. Malformed JSON content raises ValueError with line number.
```

**LLD Section 10.1 (Test Scenarios):**
```markdown
| ID | Scenario | Type | Requirement |
|---|---|---|---|
| test_loads_valid_json | Load config from a real JSON file | unit | REQ-1 |
| test_missing_path_raises | Path that doesn't exist raises FileNotFoundError | unit | REQ-2 |
| test_malformed_raises | Malformed JSON raises ValueError with line number | unit | REQ-3 |
```

**Layer 1 result:** All 5 gates pass (3 scenarios for 3 requirements; no duplicates; >50 words).
**Layer 2 result:** Coverage 3/3 = 100%. Auto-APPROVED.
**Gemini call:** Skipped. Cost: $0.

### 7.2 PASS at Layer 3 — Gemini Approved

**LLD Section 3:**
```markdown
1. Gauge renders at 60fps.
2. Needle position interpolates smoothly between values.
3. Telltale needles hold peaks for 60 seconds.
```

**LLD Section 10.1:**
```markdown
| ID | Scenario | Type | Requirement |
|---|---|---|---|
| test_60fps   | render_gauge() at 60fps for 5 seconds; assert frame rate ≥ 60 | benchmark | REQ-1 |
| test_smooth  | Set value 0 → 100 over 1 second; assert no frame jumps > 10 units | unit | REQ-2 |
| test_hold    | Spike value to 80 then drop to 20; assert telltale stays at 80 for 60s | unit | REQ-3 |
```

**Layer 1 result:** Gates pass.
**Layer 2 result:** Coverage 3/3 = 100% — wait, this would also auto-approve at Layer 2. Let's adjust: imagine the test_60fps scenario forgot the `requirement_ref`. Then Layer 2 sees coverage 2/3 = 67%, falls through to Layer 3.
**Layer 3 result:** Gemini examines test types — `benchmark` is appropriate for a 60fps assertion. Edge cases: missing "what if value is negative?" — surfaces as WARNING but doesn't BLOCK. Verdict: APPROVED.

### 7.3 BLOCKED at Layer 1 — Mechanical Gate Failure

**LLD Section 3:**
```markdown
1. Configuration loads from a JSON file.
2. Invalid path raises an error.
3. Malformed JSON raises an error.
4. Empty JSON returns default config.
5. Comments in JSON are stripped.
```

**LLD Section 10.1:**
```markdown
| ID | Scenario |
|---|---|
| test_load | Tests loading a config file |
| test_load | Tests another loading case |
```

**Layer 1 result:**
- Gate 1: PASS (2 scenarios).
- Gate 2: PASS (5 requirements).
- Gate 3: FAIL — `Only 2 scenario(s) for 5 requirement(s) — coverage ratio 40% is below 100%`.
- Gate 4: FAIL — `Duplicate scenario name(s): test_load`.
- Gate 5: PASS.

**Verdict:** BLOCKED with both gate-3 and gate-4 messages. Gemini call: skipped. Cost: $0.

**Operator action:** revise LLD Section 10.1 to have 5+ uniquely-named scenarios with requirement refs.

### 7.4 BLOCKED at `test_plan_validator` — Vague Assertion

**LLD Section 10.1 (excerpt):**
```markdown
| test_login | Verify it works correctly |
| test_save  | Check that saving works |
```

**Layer 1 result:** Pass (assume scenarios are named uniquely and scenario count matches requirement count).
**`test_plan_validator` result:** TWO ERROR violations:
- `verify it works` matched on test_login.
- `check that` partial match on test_save (depending on regex precision; in current code, `check\s+everything` is the pattern, so this specific text might pass; the example assumes the exact "verify it works" pattern hits).

**Verdict:** BLOCKED before Gemini.
**Operator action:** rewrite assertions with concrete inputs/outputs.

---

## 8. Failure Mode Reference

| Verdict source | Error message contains | Layer | Typical fix |
|---|---|---|---|
| Mechanical gate | `No test scenarios found` | 1 (gate 1) | Add Section 10.1 table with named rows. |
| Mechanical gate | `No requirements extracted from LLD` | 1 (gate 2) | Format Section 3 as numbered list. |
| Mechanical gate | `Only N scenario(s) for M requirement(s)` | 1 (gate 3) | Add scenarios to match requirement count. |
| Mechanical gate | `Duplicate scenario name(s)` | 1 (gate 4) | Rename duplicates. |
| Mechanical gate | `LLD content too short` | 1 (gate 5) | Expand the LLD. |
| Validator | `Coverage X% below 95% threshold` | `test_plan_validator` | Add scenarios for uncovered requirements. |
| Validator | `Vague assertion: 'verify it works'` (or similar pattern) | `test_plan_validator` | Replace with concrete input → expected-output assertion. |
| Validator | `Human delegation: 'manual verification'` (or similar pattern) | `test_plan_validator` | Convert to executable test (e.g., use `/visual-verify` inside an assertion). |
| Validator | `Unresolved requirement_ref REQ-X` | `test_plan_validator` (WARNING) | Fix the typo OR add the missing requirement. |
| Gemini semantic | `Test type {x} should be {y}` | 3 | Reclassify the scenario or change its declared type. |
| Gemini semantic | `Missing edge case: {empty/invalid/error}` | 3 | Add scenarios for the missing edge cases. |
| Gemini semantic | Free-form blocking issue | 3 | Read the verdict's "Required Changes" section. |

---

## 9. Application

### 9.1 By Issue Authors / LLD Drafters

When writing the Test Plan section of an LLD:

1. List requirements as `1.`, `2.`, ... in Section 3 (or use `REQ-N:` prefix).
2. For every requirement, write at least one test scenario in Section 10.1 with `requirement_ref` pointing back to it.
3. Scenarios should have descriptive unique names, declared test types, and concrete assertions (input → expected output, not "verify it works").
4. Cover error paths and edge cases — not just the happy path.
5. Avoid the eight vague-language patterns and eight human-delegation patterns from §5.2 / §5.3.

A test plan that follows this structure auto-approves at Layer 2 in milliseconds at $0 LLM cost.

### 9.2 By Operators

When the implementation workflow halts at `test_plan_status: BLOCKED`:

1. Read `state["gemini_feedback"]` (the verdict's "Required Changes" section).
2. Identify which layer failed (mechanical gate / validator / Gemini semantic) using §8.
3. Decide: revise the LLD's test plan section, OR (when AZ #1072 lands) re-run with `--auto` flag for human override.

Until AZ #1072 ships, BLOCKED at N1 is terminal — workflow must be re-run after LLD revision.

### 9.3 By the Workflow Itself

The reviewer is invoked at `N1_review_test_plan`. Routing:

```python
# Simplified from graph.py:132-136
if state["test_plan_status"] == "APPROVED":
    return "N2_scaffold_tests"
return "END"  # BLOCKED — no recovery path until AZ #1072
```

This routing is one of the demo-blocking issues for the speed-run: a single 503 on the reviewer call after retries returns BLOCKED with a transient-failure message that's not actually about test plan quality. AZ #1071 (auto-retry) and AZ #1072 (BLOCKED recovery) address this.

---

## 10. Cross-References to Other Standards

This standard sits in the larger AZ standards taxonomy:

| Standard | Relationship |
|---|---|
| [0007 — Testing Strategy](0007-testing-strategy.md) | The umbrella testing philosophy (test pyramid, coverage targets, naming conventions). 0020 specializes 0007 to the LLD-driven workflow. **Both are complementary; consult both.** |
| [0018 — Issue Spec Quality Checklist](0018-issue-spec-quality.md) | Pre-LLD-workflow gate. Dimension 6 (test plan / signal) feeds into this standard's expectations. |
| [0019 — LLD Mechanical Validation Criteria](0019-lld-mechanical-validation.md) | Sibling layer-1 validator (LLD structure, not test plan). Both run in the same broad "mechanical gates" pattern. |
| [0701 — Implementation Spec Template](0701-implementation-spec-template.md) | Section 9 of the impl spec is "Test Coverage Mapping" — the criteria here flow into 0701's mapping. |
| [0702 — Implementation Readiness Review](0702-implementation-readiness-review.md) | Criterion 6 is "Test Coverage Mapping" — semantic check that fires later (post-LLD, pre-implementation). |

ADR cross-references:
- **ADR 0207** — mandates 100% requirement coverage in LLM-driven development (the reason `COVERAGE_THRESHOLD = 0.95` is a *minimum*; the fast-path requires 100%).

---

## 11. Maintenance

### 11.1 Updating Criteria

When the test-plan reviewer changes its criteria:

1. Identify the layer (1: mechanical gate, 2: fast-path, 3: Gemini, or `test_plan_validator`).
2. Update the corresponding §2 / §3 / §4 / §5 sub-section here.
3. If the change affects the Gemini prompt, update `docs/skills/0706c-Test-Plan-Review-Prompt.md` to match.
4. Update §8 (Failure Mode Reference) with any new error message.
5. Update tests in `tests/workflows/testing/test_review_test_plan.py` (or wherever they live).
6. Bump this standard's `<!-- Version: -->` and add a row to §11.2.

### 11.2 Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-05-09 | Initial version (Issue #1067). Documents three review layers + standalone validator as of `review_test_plan.py` and `test_plan_validator.py` lines current at 2026-05-09, covering Issues #166 / #494 / #495 / #496 / #509 / #547 / #773 / #775 + ADR 0207. |

---

## 12. References

- **Reviewer code:** [`assemblyzero/workflows/testing/nodes/review_test_plan.py`](../../assemblyzero/workflows/testing/nodes/review_test_plan.py)
- **Validator code:** [`assemblyzero/core/validation/test_plan_validator.py`](../../assemblyzero/core/validation/test_plan_validator.py)
- **Reviewer prompt:** [`docs/skills/0706c-Test-Plan-Review-Prompt.md`](../skills/0706c-Test-Plan-Review-Prompt.md)
- **Verdict schema:** `assemblyzero/core/verdict_schema.py` — defines `VERDICT_SCHEMA` consumed by the reviewer (Issue #775).
- **Hardening lineage:** Issues #166 (shared validator), #494 (structured feedback), #495 (mechanical pre-validation prompt note), #496 (mechanical gates), #509 (fast-path), #547 (skip-on-resume), #773 (unified provider), #775 (structured JSON verdict).
- **ADR 0207** — Real-tests-only mandate.
- **Adjacent standards:** 0007 (testing strategy), 0018 (issue spec quality), 0019 (LLD mechanical), 0701 (implementation spec template), 0702 (implementation readiness review).
- **Related skill:** AZ #1075 — `/visual-verify` skill (legitimate way to handle visual verification inside executable assertions).
- **Workflow improvements driven by this gate:** AZ #1071 (auto-retry on transient failures), AZ #1072 (BLOCKED test-plan recovery — eliminates the no-recovery terminal state).

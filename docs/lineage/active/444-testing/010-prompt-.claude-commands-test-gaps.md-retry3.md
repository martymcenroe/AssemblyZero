# Implementation Request: .claude/commands/test-gaps.md

## Task

Write the complete contents of `.claude/commands/test-gaps.md`.

Change type: Modify
Description: Expand from ~150 lines to ~400-450 lines; restructure into 3 layers with argument parsing, project detection, and structured output

## LLD Specification

# Implementation Spec: Enhance /test-gaps with Infrastructure Audit and Project-Aware Heuristics

| Field | Value |
|-------|-------|
| Issue | #444 |
| LLD | `docs/lld/active/444-enhance-test-gaps.md` |
| Generated | 2026-02-24 |
| Status | DRAFT |

## 1. Overview

Expand the `/test-gaps` Claude skill from a single-layer report keyword grep into a comprehensive three-layer test health analysis system: report mining (Layer 1, preserved verbatim), infrastructure audit (Layer 2), and project-aware heuristics (Layer 3). This is a single-file modification to `.claude/commands/test-gaps.md`.

**Objective:** Deliver three-layer test gap analysis with argument parsing, project detection, and structured output while preserving full backward compatibility.

**Success Criteria:**
- Default `/test-gaps` produces identical output structure to current behavior (Layer 1 only)
- `--full` runs all 3 layers within 50 tool calls
- Output includes severity-sorted Recommended Actions and Issues to Create checklist for HIGH+ findings

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `.claude/commands/test-gaps.md` | Modify | Expand from ~150 lines to ~400-450 lines; restructure into 3 layers with argument parsing, project detection, and structured output |

**Implementation Order Rationale:** Single file modification. No dependencies, no imports, no build steps. The file is a Claude skill prompt definition (markdown with YAML frontmatter).

## 3. Current State (for Modify/Delete files)

### 3.1 `.claude/commands/test-gaps.md`

**Full current file content** (all lines — this is the complete file that exists today):

```markdown
---
description: Mine reports for testing gaps and automation opportunities
argument-hint: "[--full] [--file path] [--layer reports|infra|heuristics|all] [--project-type auto|extension|api|webapp|cli]"
---

# Test Gap Analysis Skill

**Model hint:** Use **Sonnet** - requires pattern recognition across reports and code correlation.

**Purpose:** Analyze implementation reports, test reports, CI infrastructure, and code to identify testing gaps, infrastructure blind spots, and automation opportunities.

**Per AssemblyZero:adrs/test-first-philosophy:** Continuous test improvement requires systematic mining of existing documentation for test debt.

**Ref:** AssemblyZero#444

---

## Help

Usage: `/test-gaps [--full] [--file path] [--layer reports|infra|heuristics|all] [--project-type auto|extension|api|webapp|cli]`

| Argument | Description | Default |
|----------|-------------|---------|
| (none) | Layer 1 quick scan (identical to legacy behavior) | Layer 1 |
| `--full` | All 3 layers, all reports | All layers |
| `--file` | Analyze specific report file (Layer 1 only) | Layer 1 |
| `--layer reports` | Layer 1: report mining only | -- |
| `--layer infra` | Layer 2: CI/config infrastructure audit | -- |
| `--layer heuristics` | Layer 3: project-aware checks | -- |
| `--layer all` | All 3 layers | -- |
| `--project-type` | Override auto-detected project type | `auto` |

---

## Execution

### Step 0: Parse Arguments and Detect Project Type

**Parse the argument string** to extract flags. Set these variables:

- `SCAN_MODE`: `quick` (default), `full` (if `--full`), or `single` (if `--file`)
- `LAYER`: `reports` (default / no flags / `--file`), `infra`, `heuristics`, or `all` (if `--full` or `--layer all`)
- `PROJECT_TYPE`: `auto` (default) or user-specified value

**If `--full` is specified:** Set `LAYER=all` and `SCAN_MODE=full`.

**Project Type Detection** (when `PROJECT_TYPE=auto`):

Use Glob to check for marker files. First match wins:

| Type | Marker Files |
|------|-------------|
| `browser-extension` | `extensions/*/manifest.json` OR root `manifest.json` containing `manifest_version` |
| `webapp` | `vite.config.*` OR `next.config.*` OR `src/**/App.{tsx,jsx}` |
| `api` | `**/lambda_function.py` OR `serverless.yml` OR `src/**/*handler*.py` |
| `cli` | `pyproject.toml` containing `argparse` or `click` or `typer` |
| `generic` | fallback if nothing matches |

Report the detected type in output header. If `--project-type` was specified, use that instead and note "(override)" in the header.

**Routing:**
- If `LAYER=reports` or `LAYER=all` → run Layer 1
- If `LAYER=infra` or `LAYER=all` → run Layer 2
- If `LAYER=heuristics` or `LAYER=all` → run Layer 3

---

### Layer 1: Report Mining

This is the original `/test-gaps` behavior, preserved verbatim.

#### Step 1.1: Pre-Filter Reports (COST OPTIMIZATION)

**Before reading full reports, use Grep to identify which reports have test gaps.**

Run these Grep patterns across report directories:
```
Grep pattern: "manual testing|tested manually"
Grep pattern: "not tested|untested|skipped"
Grep pattern: "deferred|future work"
Grep pattern: "edge case.*not covered"
Grep pattern: "happy path only"
Grep pattern: "hard to test|difficult to mock"
Grep pattern: "TODO|FIXME"
```

This produces a list of files that contain gap indicators. Only proceed with files that have matches.

**Why:** Report files can be large. Pre-filtering with Grep (fast, no token cost) eliminates reports with no gaps before expensive file reads.

**If no reports have gap indicators and LAYER=reports:** Report "No test gaps found in reports" and exit early.

#### Step 1.2: Gather Matched Reports

**Quick scan (default):**
```
Read matched docs/reports/*/test-report.md (last 5 issues with matches)
Read matched docs/reports/*/implementation-report.md (last 5 issues with matches)
```

**Full scan (--full):**
```
Read ALL matched docs/reports/*/test-report.md
Read ALL matched docs/reports/*/implementation-report.md
Read docs/9000-lessons-learned.md (if exists)
```

**Single file (--file):**
```
Read the specified file only (no pre-filter)
```

#### Step 1.3: Pattern Matching

Scan each report for these gap indicators:

| Pattern | Category | Priority |
|---------|----------|----------|
| "manual testing" / "tested manually" | Automation opportunity | HIGH |
| "not tested" / "untested" / "skipped" | Known gap | CRITICAL |
| "deferred" / "future work" | Planned debt | MEDIUM |
| "edge case" + "not covered" | Missing coverage | HIGH |
| "happy path only" | Missing negative tests | HIGH |
| "works on my machine" | Environment-specific gap | MEDIUM |
| "hard to test" / "difficult to mock" | Architecture issue | LOW |
| "TODO" / "FIXME" in test code | Incomplete test | HIGH |

#### Step 1.4: Cross-Reference Code

For each gap found:
1. Identify the affected code file
2. Check if unit tests exist for that file
3. Check current test coverage (if available)
4. Estimate complexity to add tests

---

### Layer 2: Infrastructure Audit

**This layer examines CI workflows, test configuration, and skip patterns — things that never appear in reports but silently degrade test coverage.**

#### Step 2.1: CI Workflow Analysis

Read all `.github/workflows/*.yml` files. Check for these patterns:

| Check | What to Find | Severity |
|-------|-------------|----------|
| CI-001 | `continue-on-error: true` on any job or step that runs tests | HIGH |
| CI-002 | Test commands that don't validate discovery (absence of `collected.*item` assertion or equivalent) | HIGH |
| CI-003 | `fail_ci_if_error: false` on coverage upload steps | MEDIUM |
| CI-004 | Coverage upload steps without a threshold enforcement step | MEDIUM |
| CI-005 | Playwright config has more browser `projects` than CI installs browsers for | HIGH |
| CI-006 | `continue-on-error` without a comment containing an issue reference (e.g., `# ref #NNN`) | HIGH |

**For CI-005:** Read the Playwright config file (Glob for `playwright.config.*`) and extract the `projects` array browser names. Then check each workflow for `npx playwright install` commands and compare browser lists. If CI installs fewer browsers than the config defines, flag the missing ones.

#### Step 2.2: Skip/Xfail Audit

Grep test files for skip patterns:

```
JS/TS:  test\.skip|describe\.skip|it\.skip|xit\(|xdescribe\(
Python: pytest\.mark\.skip|pytest\.skip|@pytest\.mark\.xfail|unittest\.skip
```

For each match, read the surrounding 5 lines of context and classify:

| Classification | Criteria | Severity |
|----------------|----------|----------|
| **Tracked** | Has issue reference (e.g., `#448`, `GH-123`), issue is still open | MEDIUM |
| **Stale** | Has issue reference, but issue is closed | HIGH — skip should be removed |
| **Untracked** | No issue reference at all | HIGH |
| **Conditional** | Uses `skipIf` / `skipUnless` / platform/env check | LOW |

**To check if referenced issues are open or closed:** Use `gh issue view NUMBER --repo OWNER/REPO --json state` for each referenced issue. If the gh call fails or the repo can't be determined, classify as "Unknown" (MEDIUM).

#### Step 2.3: Test Pyramid Count

Count test cases across directory tiers. Use Grep with `output_mode: "count"`:

```
Pattern: "test\(|it\(|it\.only\(|describe\("  in tests/unit/ or test/unit/
Pattern: "test\(|it\(|def test_"               in tests/integration/ or test/integration/
Pattern: "test\(|it\(|def test_"               in tests/e2e/ or test/e2e/
```

Also check for `tests/` vs `test/` directory naming (Glob both).

Display as:
```
Unit:         NN (XX%)  ████████████████
Integration:  NN (XX%)  ████████
E2E:          NN (XX%)  ████████████
```

Use block character █ repeated proportionally (max 20 chars wide).

**Flag:** If E2E count > Unit count → "INVERTED TEST PYRAMID" warning (HIGH severity).
**Flag:** If any tier is 0 → "MISSING TEST TIER" warning (HIGH severity).

#### Step 2.4: Test Config vs CI Parity

1. Glob for test config files: `playwright.config.*`, `vitest.config.*`, `jest.config.*`, `pytest.ini`, `pyproject.toml` (look for `[tool.pytest]`), `setup.cfg` (look for `[tool:pytest]`)
2. For Playwright configs: extract `projects[].name` and compare against CI workflow browser install commands
3. For pytest/vitest/jest: check if CI runs the same test commands with the same flags as local config suggests

---

### Layer 3: Project-Aware Heuristics

**Only checks matching the detected (or overridden) project type run.** Skip this entire layer for `generic` project type with a note: "Project type is generic — no heuristic checks available. Use `--project-type` to override."

#### Browser Extension Checks (`browser-extension`)

| Check | Procedure | Severity |
|-------|-----------|----------|
| EXT-001 | Glob `extensions/**/*.js` (exclude `node_modules`, `lib/`, `vendor/`). For each source file, check if a corresponding test file exists in `tests/unit/` (matching by filename pattern). Flag files with no test. | HIGH |
| EXT-002 | Glob `tests/**/mock*` or `tests/**/__mocks__/**`. For each mock, compare its last-modified date against the source file it mocks. Flag if mock is >30 days older than source (use `git log -1 --format=%ci` on each file). | MEDIUM |
| EXT-003 | Count unit test files under Chrome-specific and Firefox-specific test directories. Flag if counts differ significantly (>20% gap). | HIGH |
| EXT-004 | Read Playwright config `projects` array. For each browser project, verify a CI workflow job exists that targets it. Flag projects with no CI job. | HIGH |
| EXT-005 | Read mock files. Check for API references that don't exist on the target platform. Known bad patterns: `browser.identity` in Firefox mocks (Firefox MV3 has no identity API), `chrome.identity.getAuthToken` in Firefox mocks, `browser.action.getUserSettings` in Firefox < 118 mocks, `chrome.sidePanel` in Firefox mocks, `chrome.offscreen` in Firefox mocks. Flag as CRITICAL. | CRITICAL |
| EXT-006 | Glob for visual regression baseline directories (e.g., `tests/**/*-snapshots/`). Check if baselines exist for all CI platforms (look for platform-specific subdirectories). Flag missing platform baselines. | MEDIUM |

#### API/Lambda Checks (`api`)

| Check | Procedure | Severity |
|-------|-----------|----------|
| API-001 | Glob handler files (`**/lambda_function.py`, `**/handler*.py`, `**/routes/*.py`). For each, check if a corresponding integration test exists. Flag handlers with no test. | HIGH |
| API-002 | Check if `tests/contract/` directory exists (Glob `tests/contract/**`). If not, flag. | MEDIUM |
| API-003 | Read CI workflow files. Check for a post-deploy smoke test step (Grep for `smoke` or `post-deploy` in workflow files). If absent, flag. | MEDIUM |

#### Web App Checks (`webapp`)

| Check | Procedure | Severity |
|-------|-----------|----------|
| WEB-001 | Glob component files (`src/**/*.{tsx,jsx,vue,svelte}`). For each, check if a test file exists (matching `.test.`, `.spec.`, or in `__tests__/`). Flag components with no test. | HIGH |
| WEB-002 | Glob for visual regression snapshot directories (`**/*-snapshots/`, `**/__image_snapshots__/`). If none exist, flag. | MEDIUM |
| WEB-003 | Grep test files for accessibility testing imports (`pa11y`, `axe`, `@axe-core`, `jest-axe`, `testing-library`). If no accessibility tests found, flag. | HIGH |

#### Report Quality Grading (all project types)

Glob for `docs/reports/**/test-report*.md`. For each report:

| Section | Grep Pattern | Points |
|---------|-------------|--------|
| What was tested | `what was tested\|test scope\|tested the following` | +1 |
| How tested | `how tested\|automated\|manual\|approach` | +1 |
| What was NOT tested | `not tested\|gaps\|limitations\|out of scope` | +1 |
| Evidence | `evidence\|screenshot\|log output\|output:` | +1 |

Score 0-4 per report. Flag reports scoring ≤ 1 as LOW quality (MEDIUM severity).

---

### Output Template

Produce the final output as a structured markdown document:

```
# Test Gap Analysis

**Scan type:** {Quick|Full|layer-name} | **Project type:** {type} ({auto|override}) | **Date:** YYYY-MM-DD
```

**If Layer 1 ran:** Include the Layer 1 section with existing report mining tables.

**If Layer 2 ran:** Include:
- CI Workflow Findings table (Check | File | Finding | Severity | Issue Ref)
- Skip/Xfail Audit table (File:Line | Type | Reason | Issue | Status)
- Test Pyramid visualization and warnings
- Config parity findings

**If Layer 3 ran:** Include:
- Project-type-specific findings tables
- Report Quality table (Report | Score | Missing Sections)

**Always include (if any findings):**

**Recommended Actions** table sorted by severity (CRITICAL → HIGH → MEDIUM → LOW). Within same severity, sort by check ID alphabetically.

| # | Severity | Check ID | Finding | File |
|---|----------|----------|---------|------|

**Issues to Create** checklist containing only HIGH and CRITICAL findings:

```
- [ ] `test: {description}` — {Check ID} ({file})
```

Add note: _"Only HIGH and CRITICAL findings listed. Review before creating."_

---

### Cost Guardrails

**Tool call budgets:**
- Quick scan (default, Layer 1 only): 8-15 tool calls maximum
- Single layer (`--layer infra` or `--layer heuristics`): 8-13 tool calls maximum
- Full scan (`--full`): 30-50 tool calls maximum

**If you reach 45 tool calls during a `--full` scan**, stop further analysis, assemble output from findings so far, and add a note: "Analysis truncated at tool call limit. Run individual layers for deeper analysis."

**Sampling threshold:** If any Glob returns more than 200 files, do NOT enumerate all of them. Instead:
1. Report the total count
2. Sample the first 20 files for detailed analysis
3. Note: "Sampled 20 of N files. Run with `--file` for specific file analysis."
```

**What changes:** The file will be expanded significantly. The current file already has the YAML frontmatter, Help section, Step 0, and Layer 1–3 structure including the Output Template and Cost Guardrails. Based on the current state, the file needs the following modifications:

1. The file is truncated (ends mid-sentence in EXT-006). The complete content from the LLD must replace the truncated content.
2. The full Output Template section needs to be complete with exact markdown formatting per Appendix D of the LLD.
3. All check definitions need to be fully specified (EXT-006 is cut off).

## 4. Data Structures

Since this is a Claude skill prompt (markdown), there are no programmatic data structures to implement. However, the skill instructs Claude to internally reason about structured findings. The output format is documented here for implementation guidance.

### 4.1 Finding (Output Row)

**Definition (conceptual):**

A finding is a single row in any findings table in the output.

**Concrete Example (as rendered in markdown output):**

```markdown
| CI-001 | .github/workflows/e2e-edge.yml | `continue-on-error: true` on test job "e2e-edge-tests" at line 47 | HIGH | — |
```

**JSON representation (for understanding; not literally produced):**

```json
{
    "check_id": "CI-001",
    "file": ".github/workflows/e2e-edge.yml",
    "finding": "`continue-on-error: true` on test job 'e2e-edge-tests' at line 47",
    "severity": "HIGH",
    "issue_ref": null
}
```

### 4.2 SkipEntry (Output Row)

**Concrete Example (as rendered in markdown output):**

```markdown
| tests/unit/test_auth.py:42 | Untracked | "OAuth flow not stable" | — | — |
| tests/e2e/test_login.spec.ts:18 | Tracked | "Flaky on CI" | #312 | Open |
| tests/unit/test_cache.py:87 | Stale | "Waiting for fix" | #205 | Closed |
| tests/unit/test_platform.py:15 | Conditional | `skipIf(sys.platform == 'win32')` | — | — |
```

**JSON representation:**

```json
{
    "file_line": "tests/unit/test_auth.py:42",
    "skip_type": "Untracked",
    "reason": "OAuth flow not stable",
    "issue": null,
    "status": null
}
```

### 4.3 TestPyramid (Output Block)

**Concrete Example (as rendered in markdown output):**

```markdown
### Test Pyramid
Unit:         48 (62%)  ████████████████████
Integration:  18 (23%)  ███████
E2E:          12 (15%)  █████

Total: 78 test functions
```

**Inverted pyramid example:**

```markdown
### Test Pyramid
Unit:          5 (10%)  ██
Integration:  12 (24%)  █████
E2E:          33 (66%)  ████████████████████

Total: 50 test functions

⚠️ **INVERTED TEST PYRAMID** — E2E tests (33) outnumber unit tests (5). This indicates fragile, slow test suite.
```

### 4.4 ReportQuality (Output Row)

**Concrete Example (as rendered in markdown output):**

```markdown
| docs/reports/0401/test-report.md | 3 | Evidence |
| docs/reports/0398/test-report.md | 1 | How tested, What NOT tested, Evidence |
```

**JSON representation:**

```json
{
    "report_path": "docs/reports/0398/test-report.md",
    "score": 1,
    "missing_sections": ["How tested", "What NOT tested", "Evidence"]
}
```

### 4.5 Complete Output Example

**Concrete example of full `--full` output:**

```markdown
# Test Gap Analysis

**Scan type:** Full | **Project type:** browser-extension (auto) | **Date:** 2026-02-24

---

## Layer 1: Report Mining

### Gaps Found in Reports

| Report | Pattern | Category | Priority | Affected Code |
|--------|---------|----------|----------|---------------|
| docs/reports/0412/test-report.md | "popup auth tested manually" | Automation opportunity | HIGH | extensions/chrome/popup/auth.js |
| docs/reports/0405/implementation-report.md | "edge cases not covered for sync" | Missing coverage | HIGH | extensions/shared/sync.js |

### Cross-Reference Results

| Source File | Has Unit Test? | Has Integration Test? | Estimated Effort |
|------------|----------------|----------------------|-----------------|
| extensions/chrome/popup/auth.js | ❌ | ❌ | Medium |
| extensions/shared/sync.js | ✅ (partial) | ❌ | Low |

---

## Layer 2: Infrastructure Audit

### CI Workflow Findings

| Check | File | Finding | Severity | Issue Ref |
|-------|------|---------|----------|-----------|
| CI-001 | .github/workflows/e2e-edge.yml:47 | `continue-on-error: true` on job "e2e-tests" | HIGH | — |
| CI-006 | .github/workflows/e2e-edge.yml:47 | `continue-on-error` without issue reference comment | HIGH | — |
| CI-003 | .github/workflows/ci.yml:83 | `fail_ci_if_error: false` on coverage upload | MEDIUM | — |

### Skip/Xfail Audit

| File:Line | Type | Reason | Issue | Status |
|-----------|------|--------|-------|--------|
| tests/unit/test_auth.py:42 | Untracked | "OAuth flow not stable" | — | — |
| tests/e2e/test_popup.spec.ts:18 | Stale (potential) | "Flaky on CI" | #312 | Closed |

### Test Pyramid

```
Unit:         48 (62%)  ████████████████████
Integration:  18 (23%)  ███████
E2E:          12 (15%)  █████
```

Total: 78 test functions

---

## Layer 3: Project-Aware Heuristics (browser-extension)

### Browser Extension Checks

| Check | Finding | Severity |
|-------|---------|----------|
| EXT-001 | 3 extension source files have no unit test: `popup/settings.js`, `background/alarm.js`, `content/inject.js` | HIGH |
| EXT-005 | `tests/mocks/firefox/browser-api.js` references `browser.identity` — does not exist in Firefox MV3 | CRITICAL |
| EXT-003 | Chrome tests: 24, Firefox tests: 14 — 42% gap | HIGH |

### Test Report Quality

| Report | Score | Missing Sections |
|--------|-------|------------------|
| docs/reports/0412/test-report.md | 2 | What NOT tested, Evidence |
| docs/reports/0405/test-report.md | 3 | Evidence |

---

## Recommended Actions

| # | Severity | Check ID | Finding | File |
|---|----------|----------|---------|------|
| 1 | CRITICAL | EXT-005 | Mock references non-existent `browser.identity` API for Firefox | tests/mocks/firefox/browser-api.js |
| 2 | HIGH | CI-001 | `continue-on-error: true` on test job | .github/workflows/e2e-edge.yml |
| 3 | HIGH | CI-006 | `continue-on-error` without issue reference | .github/workflows/e2e-edge.yml |
| 4 | HIGH | EXT-001 | 3 extension source files missing unit tests | extensions/ |
| 5 | HIGH | EXT-003 | Chrome/Firefox test count gap: 42% | tests/ |
| 6 | HIGH | — | Untracked skip marker | tests/unit/test_auth.py:42 |
| 7 | HIGH | — | Stale skip (issue #312 closed) | tests/e2e/test_popup.spec.ts:18 |
| 8 | MEDIUM | CI-003 | Coverage upload with `fail_ci_if_error: false` | .github/workflows/ci.yml |
| 9 | MEDIUM | — | Report quality ≤ 2 | docs/reports/0412/test-report.md |

_Sorted: CRITICAL → HIGH → MEDIUM → LOW_

## Issues to Create

- [ ] `test: fix Firefox mock referencing non-existent browser.identity API` — EXT-005 (tests/mocks/firefox/browser-api.js)
- [ ] `test: remove continue-on-error from e2e test job or add issue ref` — CI-001/CI-006 (.github/workflows/e2e-edge.yml)
- [ ] `test: add unit tests for popup/settings.js, background/alarm.js, content/inject.js` — EXT-001 (extensions/)
- [ ] `test: achieve Chrome/Firefox test parity` — EXT-003 (tests/)
- [ ] `test: add issue ref or remove untracked skip in test_auth.py:42` — Skip audit (tests/unit/test_auth.py)
- [ ] `test: remove stale skip for closed issue #312` — Skip audit (tests/e2e/test_popup.spec.ts)

_Only HIGH and CRITICAL findings listed. Review before creating._
```

## 5. Function Specifications

This is a Claude skill prompt, not Python code. There are no literal functions. Instead, the skill prompt defines **analysis phases** as sequential instructions to Claude. Each phase is documented below with concrete input/output examples showing what Claude's tools would receive and return.

### 5.1 Step 0: Argument Parsing

**Skill Instruction Block:** The argument parsing section of the prompt.

**Input Example 1 (no args):**
```
User invokes: /test-gaps
Argument string: ""
```

**Output (internal variables set):**
```
SCAN_MODE = "quick"
LAYER = "reports"
PROJECT_TYPE = "auto"
```

**Input Example 2 (full scan):**
```
User invokes: /test-gaps --full
Argument string: "--full"
```

**Output:**
```
SCAN_MODE = "full"
LAYER = "all"
PROJECT_TYPE = "auto"
```

**Input Example 3 (specific layer with override):**
```
User invokes: /test-gaps --layer heuristics --project-type api
Argument string: "--layer heuristics --project-type api"
```

**Output:**
```
SCAN_MODE = "quick"
LAYER = "heuristics"
PROJECT_TYPE = "api"
```

**Input Example 4 (single file):**
```
User invokes: /test-gaps --file docs/reports/0412/test-report.md
Argument string: "--file docs/reports/0412/test-report.md"
```

**Output:**
```
SCAN_MODE = "single"
LAYER = "reports"
PROJECT_TYPE = "auto"
FILE_PATH = "docs/reports/0412/test-report.md"
```

**Edge Cases:**
- Unknown arguments (e.g., `--verbose`) → ignored, default to Layer 1
- `--full` combined with `--layer infra` → `--full` takes precedence, LAYER = "all"
- `--file` combined with `--layer infra` → `--layer infra` takes precedence (file only applies to Layer 1)

### 5.2 Step 0: Project Type Detection

**Skill Instruction Block:** Glob-based detection with priority ordering.

**Input (tool calls Claude makes):**

```
Glob("extensions/*/manifest.json")  →  ["extensions/chrome/manifest.json", "extensions/firefox/manifest.json"]
```

**Output:** `PROJECT_TYPE = "browser-extension"`

**Input (no extension markers):**

```
Glob("extensions/*/manifest.json")  →  []
Glob("manifest.json")  →  []
Glob("vite.config.*")  →  ["vite.config.ts"]
```

**Output:** `PROJECT_TYPE = "webapp"`

**Input (nothing matches):**

```
Glob("extensions/*/manifest.json")  →  []
Glob("manifest.json")  →  []
Glob("vite.config.*")  →  []
Glob("next.config.*")  →  []
Glob("src/**/App.{tsx,jsx}")  →  []
Glob("**/lambda_function.py")  →  []
Glob("serverless.yml")  →  []
# Check pyproject.toml for CLI markers
Read("pyproject.toml")  →  (no argparse/click/typer found)
```

**Output:** `PROJECT_TYPE = "generic"`

### 5.3 Layer 2: CI Workflow Analysis (CI-001 through CI-006)

**Tool calls Claude makes:**

```
Glob(".github/workflows/*.yml")  →  [".github/workflows/ci.yml", ".github/workflows/e2e-edge.yml"]
Grep("continue-on-error", include=".github/workflows/*.yml")  →  [".github/workflows/e2e-edge.yml:47:    continue-on-error: true"]
```

**Then Read the file to check context:**

```
Read(".github/workflows/e2e-edge.yml", lines 42-52)
→ Shows the job/step context, confirms it's a test step
→ No issue reference comment found near line 47
→ Findings: CI-001 (HIGH) + CI-006 (HIGH)
```

### 5.4 Layer 2: Skip/Xfail Audit

**Tool calls:**

```
Grep("pytest\\.mark\\.skip|pytest\\.skip|@pytest\\.mark\\.xfail|unittest\\.skip", include="tests/**/*.py")
→ ["tests/unit/test_auth.py:42:    @pytest.mark.skip(reason='OAuth flow not stable')"]

Grep("test\\.skip|describe\\.skip|it\\.skip|xit\\(|xdescribe\\(", include="tests/**/*.{ts,js}")
→ ["tests/e2e/test_popup.spec.ts:18:  test.skip('login flow', async () => { // #312 flaky on CI"]
```

**Then Read surrounding context:**

```
Read("tests/unit/test_auth.py", lines 37-47)
→ No issue reference found
→ Classification: Untracked (HIGH)

Read("tests/e2e/test_popup.spec.ts", lines 13-23)
→ Found "#312" reference
→ Run: gh issue view 312 --repo martymcenroe/AssemblyZero --json state
→ Output: {"state": "CLOSED"}
→ Classification: Stale (potential) (HIGH)
```

### 5.5 Layer 2: Test Pyramid Count

**Tool calls:**

```
Grep("def test_|test\\(|it\\(|describe\\(", include="tests/unit/**", count=true)  →  48
Grep("def test_|test\\(|it\\(", include="tests/integration/**", count=true)  →  18
Grep("def test_|test\\(|it\\(", include="tests/e2e/**", count=true)  →  12
```

**Output:** Pyramid visualization with percentages. Total = 78. No inversion (48 > 12).

### 5.6 Layer 3: Browser Extension EXT-005 Check

**Tool calls:**

```
Glob("tests/**/mock*")  →  ["tests/mocks/firefox/browser-api.js", "tests/mocks/chrome/browser-api.js"]
Read("tests/mocks/firefox/browser-api.js")
→ Contains "browser.identity.getProfileUserInfo" at line 23
→ "browser.identity" is in the known-bad-API list for Firefox
→ Finding: EXT-005 CRITICAL
```

## 6. Change Instructions

### 6.1 `.claude/commands/test-gaps.md` (Modify)

This is a single-file replacement. The current file is truncated mid-content (EXT-006 definition is cut off). The implementation replaces the entire file with the complete expanded version.

**Change Strategy:** Replace the entire file content. The YAML frontmatter is already correct. The file structure is already partially correct but truncated. The complete content follows.

**Change 1:** Verify YAML frontmatter is preserved (lines 1-4)

The current frontmatter is already correct:
```yaml
---
description: Mine reports for testing gaps and automation opportunities
argument-hint: "[--full] [--file path] [--layer reports|infra|heuristics|all] [--project-type auto|extension|api|webapp|cli]"
---
```

No change needed to frontmatter.

**Change 2:** The complete file after the frontmatter

The file currently contains the correct structure through most of Layer 3 but is truncated in the EXT-006 row. The following sections need to be completed/verified to match the LLD specification:

**2a: EXT-006 completion** — The current file cuts off mid-sentence at EXT-006. Complete it:

```diff
-| EXT-006 | Glob for visual regression baseline directories (e.g., `tests/**/*-snapshots/`). Check if baselines exist for all CI platforms (look for platform-specific subdirectories like `linux/`, `
+| EXT-006 | Glob for visual regression baseline directories (e.g., `tests/**/*-snapshots/`). Check if baselines exist for all CI platforms (look for platform-specific subdirectories). Flag missing platform baselines. | MEDIUM |
```

**2b: Add API/Lambda Checks section** — After the Browser Extension Checks table, add:

```markdown
#### API/Lambda Checks (`api`)

| Check | Procedure | Severity |
|-------|-----------|----------|
| API-001 | Glob handler files (`**/lambda_function.py`, `**/handler*.py`, `**/routes/*.py`). For each, check if a corresponding integration test exists. Flag handlers with no test. | HIGH |
| API-002 | Check if `tests/contract/` directory exists (Glob `tests/contract/**`). If not, flag. | MEDIUM |
| API-003 | Read CI workflow files. Check for a post-deploy smoke test step (Grep for `smoke` or `post-deploy` in workflow files). If absent, flag. | MEDIUM |
```

**2c: Add Web App Checks section** — After API checks:

```markdown
#### Web App Checks (`webapp`)

| Check | Procedure | Severity |
|-------|-----------|----------|
| WEB-001 | Glob component files (`src/**/*.{tsx,jsx,vue,svelte}`). For each, check if a test file exists (matching `.test.`, `.spec.`, or in `__tests__/`). Flag components with no test. | HIGH |
| WEB-002 | Glob for visual regression snapshot directories (`**/*-snapshots/`, `**/__image_snapshots__/`). If none exist, flag. | MEDIUM |
| WEB-003 | Grep test files for accessibility testing imports (`pa11y`, `axe`, `@axe-core`, `jest-axe`, `testing-library`). If no accessibility tests found, flag. | HIGH |
```

**2d: Add Report Quality Grading section** — After project-specific checks:

```markdown
#### Report Quality Grading (all project types)

Glob for `docs/reports/**/test-report*.md`. For each report:

| Section | Grep Pattern | Points |
|---------|-------------|--------|
| What was tested | `what was tested\|test scope\|tested the following` | +1 |
| How tested | `how tested\|automated\|manual\|approach` | +1 |
| What was NOT tested | `not tested\|gaps\|limitations\|out of scope` | +1 |
| Evidence | `evidence\|screenshot\|log output\|output:` | +1 |

Score 0-4 per report. Flag reports scoring ≤ 1 as LOW quality (MEDIUM severity).
```

**2e: Add Output Template section** — Replace/complete the Output Template section:

```markdown
---

### Output Template

Produce the final output as a structured markdown document:

```
# Test Gap Analysis

**Scan type:** {Quick|Full|layer-name} | **Project type:** {type} ({auto|override}) | **Date:** YYYY-MM-DD
```

**If Layer 1 ran:** Include the Layer 1 section with existing report mining tables.

**If Layer 2 ran:** Include:
- CI Workflow Findings table: `| Check | File | Finding | Severity | Issue Ref |`
- Skip/Xfail Audit table: `| File:Line | Type | Reason | Issue | Status |`
  - Prefix "Stale" entries with "(potential)" to indicate heuristic detection
- Test Pyramid visualization with block chars and warnings
- Config parity findings

**If Layer 3 ran:** Include:
- Project-type-specific findings tables
- Report Quality table: `| Report | Score | Missing Sections |`

**Always include (if any findings exist):**

**Recommended Actions** — a single table sorted by severity (CRITICAL → HIGH → MEDIUM → LOW), and within same severity by check ID alphabetically:

```
## Recommended Actions

| # | Severity | Check ID | Finding | File |
|---|----------|----------|---------|------|
```

**Issues to Create** — a checkbox list containing ONLY HIGH and CRITICAL findings:

```
## Issues to Create

- [ ] `test: {description}` — {Check ID} ({file})

_Only HIGH and CRITICAL findings listed. Review before creating._
```

If no findings at all, output: "✅ No test gaps detected. Test health looks good!"
```

**2f: Add Cost Guardrails section** — At the end of the file:

```markdown
---

### Cost Guardrails

**Tool call budgets:**
- Quick scan (default, Layer 1 only): 8-15 tool calls maximum
- Single layer (`--layer infra` or `--layer heuristics`): 8-13 tool calls maximum  
- Full scan (`--full`): 30-50 tool calls maximum

**If you reach 45 tool calls during a `--full` scan**, stop further analysis, assemble output from findings so far, and add a note: "⚠️ Analysis truncated at tool call limit. Run individual layers for deeper analysis."

**Sampling threshold:** If any Glob returns more than 200 files, do NOT enumerate all of them. Instead:
1. Report the total count
2. Sample the first 20 files for detailed analysis
3. Note: "Sampled 20 of N files. Run with `--file` for specific file analysis."
```

**Complete file assembly instruction:**

The implementer should verify the file contains these sections in order, each complete and matching the LLD:

1. YAML frontmatter (unchanged)
2. `# Test Gap Analysis Skill` header with model hint, purpose, ADR ref, issue ref
3. `## Help` — argument table (unchanged)
4. `## Execution`
5. `### Step 0: Parse Arguments and Detect Project Type` — argument parsing + project detection table + routing logic
6. `### Layer 1: Report Mining` — Steps 1.1 through 1.4 (preserved verbatim from current)
7. `### Layer 2: Infrastructure Audit` — Steps 2.1 through 2.4
8. `### Layer 3: Project-Aware Heuristics` — Browser Extension, API, WebApp, Report Quality Grading
9. `### Output Template` — Complete output assembly instructions with Recommended Actions and Issues to Create
10. `### Cost Guardrails` — Tool call budgets and sampling thresholds

**The critical constraint:** Layer 1 content (Steps 1.1-1.4) MUST be byte-identical to the current file's Layer 1 content. Do not modify any text within the Layer 1 section.

## 7. Pattern References

### 7.1 Existing Skill File Structure

**File:** `.claude/commands/test-gaps.md` (lines 1-4)

```yaml
---
description: Mine reports for testing gaps and automation opportunities
argument-hint: "[--full] [--file path] [--layer reports|infra|heuristics|all] [--project-type auto|extension|api|webapp|cli]"
---
```

**Relevance:** This is the standard Claude skill YAML frontmatter pattern. The `description` field is shown in Claude's `/` command picker. The `argument-hint` field is shown as placeholder text. This must be preserved exactly.

### 7.2 Layer 1 Report Mining Pattern (Existing Behavior)

**File:** `.claude/commands/test-gaps.md` (lines ~45-115, the Layer 1 section)

```markdown
### Layer 1: Report Mining

This is the original `/test-gaps` behavior, preserved verbatim.

#### Step 1.1: Pre-Filter Reports (COST OPTIMIZATION)

**Before reading full reports, use Grep to identify which reports have test gaps.**

Run these Grep patterns across report directories:
```
Grep pattern: "manual testing|tested manually"
...
```

**Relevance:** This is the core behavior that must be preserved verbatim. The entire block from `### Layer 1: Report Mining` through `#### Step 1.4: Cross-Reference Code` (and its sub-steps) must remain unchanged in the expanded file. All new content (Layers 2 and 3) is added AFTER this section.

### 7.3 Other Claude Skill Files (Pattern for Argument Parsing)

**File:** `.claude/commands/` directory

**Relevance:** Other skill files in the `.claude/commands/` directory follow the same YAML frontmatter + markdown instruction pattern. The `argument-hint` field with bracket notation (`[--flag]`) is the established convention. The expanded file follows this same convention.

### 7.4 CI Workflow Files (Analysis Targets)

**File:** `.github/workflows/` directory

**Relevance:** Layer 2 CI Workflow Analysis reads these files. The implementer should verify that `.github/workflows/` exists in the repository and contains `.yml` files. The skill instructions reference specific patterns (`continue-on-error`, `fail_ci_if_error`, `playwright install`) that may or may not be present — the skill handles both cases gracefully.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| N/A | N/A | N/A |

**New Dependencies:** None. This is a markdown skill file modification. No Python packages, no npm packages, no build tools.

**Tool Dependencies (Claude built-in):**

| Tool | Used For | Layer(s) |
|------|----------|----------|
| Glob | Find files by pattern | All layers |
| Grep | Search file contents, count matches | All layers |
| Read | Read file contents | All layers |
| Bash | `git log` for file dates (EXT-002), `gh issue view` for issue status (Layer 2 skip audit) | Layer 2, Layer 3 |

All tools are built into Claude Code and require no installation or configuration.

## 9. Test Mapping

*Map each LLD test scenario to the specific skill behavior it validates.*

| Test ID | Tests Phase | Invocation | Expected Output Characteristics |
|---------|------------|------------|-------------------------------|
| T010 / Scenario 010 | Backward compat | `/test-gaps` | Layer 1 output only; no Layer 2/3 headings; structure identical to pre-change |
| T020 / Scenario 020 | Layer 2 CI analysis | `/test-gaps --layer infra` | CI findings table with at least one check; header shows project type |
| T030 / Scenario 030 | Layer 2 skip audit | `/test-gaps --layer infra` | Skip audit table with classifications |
| T040 / Scenario 040 | Layer 2 pyramid | `/test-gaps --layer infra` | Pyramid visualization with counts and percentages |
| T050 / Scenario 050 | Layer 3 auto-detection | `/test-gaps --layer heuristics` | Header shows detected project type with "(auto)" |
| T060 / Scenario 060 | Project type override | `/test-gaps --layer heuristics --project-type api` | Header shows "api (override)"; API checks run |
| T070 / Scenario 070 | Report quality | `/test-gaps --layer heuristics` | Report Quality table with scores |
| T080 / Scenario 080 | Full output structure | `/test-gaps --full` | All 3 layer headings; Recommended Actions sorted CRITICAL→LOW; Issues to Create with only HIGH+ items |
| T090 / Scenario 090 | Cost ceiling | `/test-gaps --full` | Completes within 50 tool calls |
| T100 / Scenario 100 | All argument flags | Various | Each flag produces correct routing |
| T110 / Scenario 110 | No workflows | `/test-gaps --layer infra` (no .github/workflows/) | "No CI workflows found" message, no error |
| T120 / Scenario 120 | Generic fallback | `/test-gaps --layer heuristics` (no markers) | "generic (auto)" in header; "no heuristic checks available" note |

**Verification Method:** All tests are manual — run the skill in a Claude Code session and inspect output. See LLD Section 10.3 for justification.

## 10. Implementation Notes

### 10.1 Critical: Layer 1 Preservation

The single most important implementation constraint: **Layer 1 content must be preserved byte-for-byte.** The text from `### Layer 1: Report Mining` through the end of `#### Step 1.4: Cross-Reference Code` must not be modified in any way. This ensures backward compatibility (REQ-1, Scenario 010).

When assembling the final file:
1. Copy the current Layer 1 block exactly
2. Add Layer 2 content after Layer 1
3. Add Layer 3 content after Layer 2
4. Add Output Template after Layer 3
5. Add Cost Guardrails at the end

### 10.2 Known-Bad API List (EXT-005)

The following APIs must be embedded directly in the skill prompt text for the EXT-005 check:

| API | Platform | Notes |
|-----|----------|-------|
| `browser.identity` | Firefox MV3 | Chrome-only API |
| `chrome.identity.getAuthToken` | Firefox | Chrome-specific |
| `browser.action.getUserSettings` | Firefox < 118 | Added late |
| `chrome.sidePanel` | Firefox | Chrome 114+ only |
| `chrome.offscreen` | Firefox | Chrome 109+ only |

### 10.3 Skip Audit: Stale Detection Caveat

Per the LLD's reviewer suggestion, all "Stale" skip classifications should be labeled as "(potential)" in the output. The heuristic detection (using `gh issue view` or comment parsing) is not guaranteed to be accurate. The output should read:

```
| tests/e2e/test_popup.spec.ts:18 | Stale (potential) | "Flaky on CI" | #312 | Closed |
```

Not:

```
| tests/e2e/test_popup.spec.ts:18 | Stale | "Flaky on CI" | #312 | Closed |
```

### 10.4 Issue Status Detection Strategy

The LLD had an open question about whether to use GitHub API or comment heuristics for issue status detection. The LLD's Section 2.6 says "No GitHub API dependency" and recommends comment heuristics. However, the current file's Step 2.2 already includes `gh issue view` instructions. 

**Resolution:** Keep the `gh issue view` approach since it's already in the file AND it's more accurate. The `gh` CLI is typically available in Claude Code sessions. If the call fails, fall back to "Unknown" (MEDIUM) classification. This aligns with the current file's existing instruction: "If the gh call fails or the repo can't be determined, classify as 'Unknown' (MEDIUM)."

### 10.5 File Size Target

The LLD targets 400-450 lines. The current file is approximately 200 lines (truncated). The additions (completing EXT-006, adding API checks, WebApp checks, Report Quality Grading, complete Output Template, and Cost Guardrails) add approximately 150-200 lines, bringing the total to approximately 350-450 lines. This is within the LLD's target.

### 10.6 Developer Comment Block

Per the LLD's reviewer suggestion, add a comment block near the top of the file (after the YAML frontmatter, before the heading) explaining the structure:

```markdown
<!-- 
  SKILL STRUCTURE:
  1. Frontmatter (YAML) — command metadata
  2. Help — argument reference table
  3. Step 0 — argument parsing + project type detection
  4. Layer 1 — report mining (LEGACY — DO NOT MODIFY)
  5. Layer 2 — infrastructure audit (CI, skips, pyramid, config)
  6. Layer 3 — project-aware heuristics (extension/api/webapp checks + report quality)
  7. Output Template — structured markdown output format
  8. Cost Guardrails — tool call budgets
  
  Ref: Issue #444, LLD docs/lld/active/444-enhance-test-gaps.md
-->
```

### 10.7 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| Max tool calls (quick) | 15 | Layer 1 only, cost ~$0.03 |
| Max tool calls (full) | 50 | All layers, cost ~$0.15 |
| Tool call warning threshold | 45 | Triggers truncation notice at 45 to stop before 50 |
| File sampling threshold | 200 | Glob results > 200 trigger sampling mode |
| Sample size | 20 | Number of files to analyze when sampling |
| Mock staleness threshold | 30 days | EXT-002 flags mocks >30 days older than source |
| Test count asymmetry threshold | 20% | EXT-003 flags Chrome/Firefox gap > 20% |
| Report quality low threshold | ≤ 1 | Reports scoring 0 or 1 out of 4 are flagged |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — full file content shown
- [x] Every data structure has a concrete JSON/YAML example (Section 4) — Finding, SkipEntry, TestPyramid, ReportQuality, and complete output example provided
- [x] Every function has input/output examples with realistic values (Section 5) — all phases documented with tool call examples
- [x] Change instructions are diff-level specific (Section 6) — each section change described with before/after
- [x] Pattern references include file:line and are verified to exist (Section 7) — frontmatter, Layer 1, CI workflows referenced
- [x] All imports are listed and verified (Section 8) — N/A (markdown file, no imports; tool dependencies listed)
- [x] Test mapping covers all LLD test scenarios (Section 9) — all 12 scenarios mapped

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #444 |
| Verdict | DRAFT |
| Date | 2026-02-24 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #444 |
| Verdict | APPROVED |
| Date | 2026-02-25 |
| Iterations | 0 |
| Finalized | 2026-02-25T03:12:57Z |

### Review Feedback Summary

Approved with suggestions:
1.  **Assembly List Completeness:** Section 10.6 requests a "Developer Comment Block" be added between the frontmatter and the header. However, the "Complete file assembly instruction" list in Section 6.1 (Steps 1-10) does not explicitly list this comment block. It is recommended to add the comment block as a step in that list to ensure the agent doesn't miss it while following the assembly order.
2.  **Context Clarification:** The Overview (Section 1) describes the cu...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    metrics/
    mock_repo/
      src/
    scout/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 14 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  nodes/
  telemetry/
  utils/
  workflow/
  workflows/
    implementation_spec/
      nodes/
    issue/
      nodes/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Existing File Contents

The file currently contains:

```python
---
description: Mine reports for testing gaps and automation opportunities
argument-hint: "[--full] [--file path] [--layer reports|infra|heuristics|all] [--project-type auto|extension|api|webapp|cli]"
---

# Test Gap Analysis Skill

**Model hint:** Use **Sonnet** - requires pattern recognition across reports and code correlation.

**Purpose:** Analyze implementation reports, test reports, CI infrastructure, and code to identify testing gaps, infrastructure blind spots, and automation opportunities.

**Per AssemblyZero:adrs/test-first-philosophy:** Continuous test improvement requires systematic mining of existing documentation for test debt.

**Ref:** AssemblyZero#444

---

## Help

Usage: `/test-gaps [--full] [--file path] [--layer reports|infra|heuristics|all] [--project-type auto|extension|api|webapp|cli]`

| Argument | Description | Default |
|----------|-------------|---------|
| (none) | Layer 1 quick scan (identical to legacy behavior) | Layer 1 |
| `--full` | All 3 layers, all reports | All layers |
| `--file` | Analyze specific report file (Layer 1 only) | Layer 1 |
| `--layer reports` | Layer 1: report mining only | -- |
| `--layer infra` | Layer 2: CI/config infrastructure audit | -- |
| `--layer heuristics` | Layer 3: project-aware checks | -- |
| `--layer all` | All 3 layers | -- |
| `--project-type` | Override auto-detected project type | `auto` |

---

## Execution

### Step 0: Parse Arguments and Detect Project Type

**Parse the argument string** to extract flags. Set these variables:

- `SCAN_MODE`: `quick` (default), `full` (if `--full`), or `single` (if `--file`)
- `LAYER`: `reports` (default / no flags / `--file`), `infra`, `heuristics`, or `all` (if `--full` or `--layer all`)
- `PROJECT_TYPE`: `auto` (default) or user-specified value

**If `--full` is specified:** Set `LAYER=all` and `SCAN_MODE=full`.

**Project Type Detection** (when `PROJECT_TYPE=auto`):

Use Glob to check for marker files. First match wins:

| Type | Marker Files |
|------|-------------|
| `browser-extension` | `extensions/*/manifest.json` OR root `manifest.json` containing `manifest_version` |
| `webapp` | `vite.config.*` OR `next.config.*` OR `src/**/App.{tsx,jsx}` |
| `api` | `**/lambda_function.py` OR `serverless.yml` OR `src/**/*handler*.py` |
| `cli` | `pyproject.toml` containing `argparse` or `click` or `typer` |
| `generic` | fallback if nothing matches |

Report the detected type in output header. If `--project-type` was specified, use that instead and note "(override)" in the header.

**Routing:**
- If `LAYER=reports` or `LAYER=all` → run Layer 1
- If `LAYER=infra` or `LAYER=all` → run Layer 2
- If `LAYER=heuristics` or `LAYER=all` → run Layer 3

---

### Layer 1: Report Mining

This is the original `/test-gaps` behavior, preserved verbatim.

#### Step 1.1: Pre-Filter Reports (COST OPTIMIZATION)

**Before reading full reports, use Grep to identify which reports have test gaps.**

Run these Grep patterns across report directories:
```
Grep pattern: "manual testing|tested manually"
Grep pattern: "not tested|untested|skipped"
Grep pattern: "deferred|future work"
Grep pattern: "edge case.*not covered"
Grep pattern: "happy path only"
Grep pattern: "hard to test|difficult to mock"
Grep pattern: "TODO|FIXME"
```

This produces a list of files that contain gap indicators. Only proceed with files that have matches.

**Why:** Report files can be large. Pre-filtering with Grep (fast, no token cost) eliminates reports with no gaps before expensive file reads.

**If no reports have gap indicators and LAYER=reports:** Report "No test gaps found in reports" and exit early.

#### Step 1.2: Gather Matched Reports

**Quick scan (default):**
```
Read matched docs/reports/*/test-report.md (last 5 issues with matches)
Read matched docs/reports/*/implementation-report.md (last 5 issues with matches)
```

**Full scan (--full):**
```
Read ALL matched docs/reports/*/test-report.md
Read ALL matched docs/reports/*/implementation-report.md
Read docs/9000-lessons-learned.md (if exists)
```

**Single file (--file):**
```
Read the specified file only (no pre-filter)
```

#### Step 1.3: Pattern Matching

Scan each report for these gap indicators:

| Pattern | Category | Priority |
|---------|----------|----------|
| "manual testing" / "tested manually" | Automation opportunity | HIGH |
| "not tested" / "untested" / "skipped" | Known gap | CRITICAL |
| "deferred" / "future work" | Planned debt | MEDIUM |
| "edge case" + "not covered" | Missing coverage | HIGH |
| "happy path only" | Missing negative tests | HIGH |
| "works on my machine" | Environment-specific gap | MEDIUM |
| "hard to test" / "difficult to mock" | Architecture issue | LOW |
| "TODO" / "FIXME" in test code | Incomplete test | HIGH |

#### Step 1.4: Cross-Reference Code

For each gap found:
1. Identify the affected code file
2. Check if unit tests exist for that file
3. Check current test coverage (if available)
4. Estimate complexity to add tests

---

### Layer 2: Infrastructure Audit

**This layer examines CI workflows, test configuration, and skip patterns — things that never appear in reports but silently degrade test coverage.**

#### Step 2.1: CI Workflow Analysis

Read all `.github/workflows/*.yml` files. Check for these patterns:

| Check | What to Find | Severity |
|-------|-------------|----------|
| CI-001 | `continue-on-error: true` on any job or step that runs tests | HIGH |
| CI-002 | Test commands that don't validate discovery (absence of `collected.*item` assertion or equivalent) | HIGH |
| CI-003 | `fail_ci_if_error: false` on coverage upload steps | MEDIUM |
| CI-004 | Coverage upload steps without a threshold enforcement step | MEDIUM |
| CI-005 | Playwright config has more browser `projects` than CI installs browsers for | HIGH |
| CI-006 | `continue-on-error` without a comment containing an issue reference (e.g., `# ref #NNN`) | HIGH |

**For CI-005:** Read the Playwright config file (Glob for `playwright.config.*`) and extract the `projects` array browser names. Then check each workflow for `npx playwright install` commands and compare browser lists. If CI installs fewer browsers than the config defines, flag the missing ones.

#### Step 2.2: Skip/Xfail Audit

Grep test files for skip patterns:

```
JS/TS:  test\.skip|describe\.skip|it\.skip|xit\(|xdescribe\(
Python: pytest\.mark\.skip|pytest\.skip|@pytest\.mark\.xfail|unittest\.skip
```

For each match, read the surrounding 5 lines of context and classify:

| Classification | Criteria | Severity |
|----------------|----------|----------|
| **Tracked** | Has issue reference (e.g., `#448`, `GH-123`), issue is still open | MEDIUM |
| **Stale** | Has issue reference, but issue is closed | HIGH — skip should be removed |
| **Untracked** | No issue reference at all | HIGH |
| **Conditional** | Uses `skipIf` / `skipUnless` / platform/env check | LOW |

**To check if referenced issues are open or closed:** Use `gh issue view NUMBER --repo OWNER/REPO --json state` for each referenced issue. If the gh call fails or the repo can't be determined, classify as "Unknown" (MEDIUM).

#### Step 2.3: Test Pyramid Count

Count test cases across directory tiers. Use Grep with `output_mode: "count"`:

```
Pattern: "test\(|it\(|it\.only\(|describe\("  in tests/unit/ or test/unit/
Pattern: "test\(|it\(|def test_"               in tests/integration/ or test/integration/
Pattern: "test\(|it\(|def test_"               in tests/e2e/ or test/e2e/
```

Also check for `tests/` vs `test/` directory naming (Glob both).

Display as:
```
Unit:         NN (XX%)  ████████████████
Integration:  NN (XX%)  ████████
E2E:          NN (XX%)  ████████████
```

Use block character █ repeated proportionally (max 20 chars wide).

**Flag:** If E2E count > Unit count → "INVERTED TEST PYRAMID" warning (HIGH severity).
**Flag:** If any tier is 0 → "MISSING TEST TIER" warning (HIGH severity).

#### Step 2.4: Test Config vs CI Parity

1. Glob for test config files: `playwright.config.*`, `vitest.config.*`, `jest.config.*`, `pytest.ini`, `pyproject.toml` (look for `[tool.pytest]`), `setup.cfg` (look for `[tool:pytest]`)
2. For Playwright configs: extract `projects[].name` and compare against CI workflow browser install commands
3. For pytest/vitest/jest: check if CI runs the same test commands with the same flags as local config suggests

---

### Layer 3: Project-Aware Heuristics

**Only checks matching the detected (or overridden) project type run.** Skip this entire layer for `generic` project type with a note: "Project type is generic — no heuristic checks available. Use `--project-type` to override."

#### Browser Extension Checks (`browser-extension`)

| Check | Procedure | Severity |
|-------|-----------|----------|
| EXT-001 | Glob `extensions/**/*.js` (exclude `node_modules`, `lib/`, `vendor/`). For each source file, check if a corresponding test file exists in `tests/unit/` (matching by filename pattern). Flag files with no test. | HIGH |
| EXT-002 | Glob `tests/**/mock*` or `tests/**/__mocks__/**`. For each mock, compare its last-modified date against the source file it mocks. Flag if mock is >30 days older than source (use `git log -1 --format=%ci` on each file). | MEDIUM |
| EXT-003 | Count unit test files under Chrome-specific and Firefox-specific test directories. Flag if counts differ significantly (>20% gap). | HIGH |
| EXT-004 | Read Playwright config `projects` array. For each browser project, verify a CI workflow job exists that targets it. Flag projects with no CI job. | HIGH |
| EXT-005 | Read mock files. Check for API references that don't exist on the target platform. Known bad patterns: `browser.identity` in Firefox mocks (Firefox MV3 has no identity API), `chrome.identity.getAuthToken` in Firefox mocks. Flag as CRITICAL. | CRITICAL |
| EXT-006 | Glob for visual regression baseline directories (e.g., `tests/**/*-snapshots/`). Check if baselines exist for all CI platforms (look for platform-specific subdirectories like `linux/`, `darwin/`, `win32/`). Flag platforms missing baselines. | MEDIUM |

#### API/Lambda Checks (`api`)

| Check | Procedure | Severity |
|-------|-----------|----------|
| API-001 | Glob for handler files (`*handler*.py`, `lambda_function.py`, `**/routes/*.py`). Check if corresponding integration test files exist. Flag handlers with no integration test. | HIGH |
| API-002 | Check if a `tests/contract/` or `tests/contracts/` directory exists. If not, flag as missing contract test layer. | MEDIUM |
| API-003 | Read CI workflows for post-deploy smoke test steps (Grep for `curl.*health` or `smoke` in workflow files). Flag if absent. | MEDIUM |

#### Web App Checks (`webapp`)

| Check | Procedure | Severity |
|-------|-----------|----------|
| WEB-001 | Glob `src/components/**/*.{tsx,jsx,vue,svelte}`. For each component, check if a test file exists (`.test.`, `.spec.`, or in `__tests__/`). Flag components with no test. | HIGH |
| WEB-002 | Check for visual regression snapshot directories. Flag if no snapshots exist anywhere in the test tree. | MEDIUM |
| WEB-003 | Grep test files and CI workflows for accessibility testing tools (`pa11y`, `axe`, `@axe-core`, `toHaveNoViolations`). Flag if no accessibility tests found. | HIGH |

#### Test Report Quality Grading (all project types)

Read the 5 most recent `docs/reports/*/test-report.md` files. Grade each against these criteria:

| Criteria | How to Detect | Points |
|----------|--------------|--------|
| "What was tested" section | Heading containing "tested" or "coverage" or "scope" | +1 |
| "How tested" method specified | Contains "automated", "manual", "unit test", "e2e", or similar | +1 |
| "What was NOT tested" section | Heading containing "not tested" or "limitations" or "out of scope" | +1 |
| Evidence provided | Contains log excerpts, screenshot references, or test output | +1 |

Score 0–4 per report. Flag reports scoring ≤1 as LOW quality (HIGH severity).

---

### Generate Output

Combine all layers that were run into a single output:

```markdown
# Test Gap Analysis

**Scan type:** Quick/Full | **Project type:** [type] ([auto/override]) | **Date:** YYYY-MM-DD

## Layer 1: Report Mining

### Critical Gaps (No tests exist)

| File | Gap Description | Source | Effort |
|------|-----------------|--------|--------|
| `path/to/file.js` | [description] | Report #XXX | [Low/Med/High] |

### Automation Opportunities (Manual → Automated)

| File | Current Testing | Automation Benefit | Source |
|------|-----------------|-------------------|--------|
| `path/to/file.js` | Manual login flow | Reduce regression time | Report #XXX |

### Edge Cases Missing

| File | Edge Case | Why Not Tested | Priority |
|------|-----------|----------------|----------|
| `path/to/file.js` | Empty allowlist | "Deferred" | HIGH |

### Architecture Issues (Hard to test)

| File | Issue | Suggested Refactor |
|------|-------|-------------------|
| `path/to/file.js` | Tight coupling to DOM | Extract pure functions |

## Layer 2: Infrastructure Audit

### CI Workflow Findings
| Check | File | Finding | Severity | Issue Ref |
|-------|------|---------|----------|-----------|

### Skip/Xfail Audit
| File:Line | Type | Reason | Issue | Status |
|-----------|------|--------|-------|--------|

### Test Pyramid
Unit:         NN (XX%)  ████████████████
Integration:  NN (XX%)  ████████
E2E:          NN (XX%)  ████████████

### Config Parity
| Config | Setting | CI | Status |
|--------|---------|-----|--------|

## Layer 3: Project-Aware Heuristics ([type])

### Extension Code Coverage
| Extension File | Lines | Unit Test | Status |
|----------------|-------|-----------|--------|

### Mock Fidelity
| Mock File | Source Age Gap | Known Bad APIs |
|-----------|---------------|----------------|

### Cross-Browser Parity
| Aspect | Chrome | Firefox | Status |
|--------|--------|---------|--------|

### Test Report Quality
| Report | Score | Missing Sections |
|--------|-------|------------------|

## Recommended Actions

1. **[CRITICAL]** ... — Check ID
2. **[HIGH]** ... — Check ID
3. **[MEDIUM]** ... — Check ID

## Issues to Create

- [ ] `test: ...` — Check ID
- [ ] `test: ...` — Check ID
```

**Omit any section that has no findings.** Don't show empty tables.

**Omit layers that weren't run.** If only `--layer infra` was specified, don't show Layer 1 or Layer 3 headings.

---

## Notes

- This skill is READ-ONLY — it analyzes but does not modify files
- Creates issues only when user confirms
- Helps maintain test-first philosophy compliance
- Run periodically (weekly recommended) to prevent test debt accumulation
- Layer 2 and 3 checks use IDs (CI-001, EXT-001, etc.) for traceability in issues

### Cost Efficiency

| Mode | Layers | Est. Tool Calls | Est. Cost |
|------|--------|-----------------|-----------|
| Quick (default) | 1 | 8–15 | ~$0.03 |
| `--layer infra` | 2 | 8–13 | ~$0.05 |
| `--layer heuristics` | 3 | 10–20 | ~$0.08 |
| `--full` | 1, 2, 3 | 30–50 | ~$0.15 |

```

Modify this file according to the LLD specification.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_444.py
"""Test file for Issue #444.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest


# Fixtures for mocking
@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    # TODO: Implement mock
    yield None


# Unit Tests
# -----------

def test_id():
    """
    Tests Phase | Invocation | Expected Output Characteristics
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_id works correctly
    assert False, 'TDD RED: test_id not implemented'


def test_t010_scenario_010():
    """
    Backward compat | `/test-gaps` | Layer 1 output only; no Layer 2/3
    headings; structure identical to pre-change
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t010_scenario_010 works correctly
    assert False, 'TDD RED: test_t010_scenario_010 not implemented'


def test_t020_scenario_020():
    """
    Layer 2 CI analysis | `/test-gaps --layer infra` | CI findings table
    with at least one check; header shows project type
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t020_scenario_020 works correctly
    assert False, 'TDD RED: test_t020_scenario_020 not implemented'


def test_t030_scenario_030():
    """
    Layer 2 skip audit | `/test-gaps --layer infra` | Skip audit table
    with classifications
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t030_scenario_030 works correctly
    assert False, 'TDD RED: test_t030_scenario_030 not implemented'


def test_t040_scenario_040():
    """
    Layer 2 pyramid | `/test-gaps --layer infra` | Pyramid visualization
    with counts and percentages
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t040_scenario_040 works correctly
    assert False, 'TDD RED: test_t040_scenario_040 not implemented'


def test_t050_scenario_050():
    """
    Layer 3 auto-detection | `/test-gaps --layer heuristics` | Header
    shows detected project type with "(auto)"
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t050_scenario_050 works correctly
    assert False, 'TDD RED: test_t050_scenario_050 not implemented'


def test_t060_scenario_060(mock_external_service):
    """
    Project type override | `/test-gaps --layer heuristics --project-type
    api` | Header shows "api (override)"; API checks run
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t060_scenario_060 works correctly
    assert False, 'TDD RED: test_t060_scenario_060 not implemented'


def test_t070_scenario_070():
    """
    Report quality | `/test-gaps --layer heuristics` | Report Quality
    table with scores
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t070_scenario_070 works correctly
    assert False, 'TDD RED: test_t070_scenario_070 not implemented'


def test_t080_scenario_080():
    """
    Full output structure | `/test-gaps --full` | All 3 layer headings;
    Recommended Actions sorted CRITICAL→LOW; Issues to Create with only
    HIGH+ items
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t080_scenario_080 works correctly
    assert False, 'TDD RED: test_t080_scenario_080 not implemented'


def test_t090_scenario_090():
    """
    Cost ceiling | `/test-gaps --full` | Completes within 50 tool calls
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t090_scenario_090 works correctly
    assert False, 'TDD RED: test_t090_scenario_090 not implemented'


def test_t100_scenario_100():
    """
    All argument flags | Various | Each flag produces correct routing
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t100_scenario_100 works correctly
    assert False, 'TDD RED: test_t100_scenario_100 not implemented'


def test_t110_scenario_110():
    """
    No workflows | `/test-gaps --layer infra` (no .github/workflows/) |
    "No CI workflows found" message, no error
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t110_scenario_110 works correctly
    assert False, 'TDD RED: test_t110_scenario_110 not implemented'


def test_t120_scenario_120():
    """
    Generic fallback | `/test-gaps --layer heuristics` (no markers) |
    "generic (auto)" in header; "no heuristic checks available" note
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t120_scenario_120 works correctly
    assert False, 'TDD RED: test_t120_scenario_120 not implemented'




```



## Previous Attempt Failed (Attempt 3/3)

Your previous response had an error:

```
API error: CLI timeout after 368s waiting for response
```

Please fix this issue and provide the corrected, complete file contents.
IMPORTANT: Output the ENTIRE file, not just the fix.

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the code.

```python
# Your implementation here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the code in a single code block

---
description: Mine reports for testing gaps and automation opportunities
argument-hint: "[--full] [--file path] [--layer reports|infra|heuristics|all] [--project-type auto|extension|api|webapp|cli]"
scope: global
---

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

Read all `.github/workflows/*.yml` files. If no workflow directory or files exist, report "No CI workflows found — skipping CI analysis" and proceed to Step 2.2.

Check for these patterns:

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
| **Stale (potential)** | Has issue reference, but issue is closed | HIGH — skip should be removed |
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

Produce the final output as a structured markdown document. **This skill is READ-ONLY** — it analyzes but does not modify files. Issues are only created when the user confirms.

**Header (always include):**

```
# Test Gap Analysis

**Scan type:** {Quick|Full|layer-name} | **Project type:** {type} ({auto|override}) | **Date:** YYYY-MM-DD
```

**If Layer 1 ran**, include report mining findings. Use these tables as appropriate:

```
## Layer 1: Report Mining

### Gaps Found in Reports

| Report | Pattern | Category | Priority | Affected Code |
|--------|---------|----------|----------|---------------|

### Cross-Reference Results

| Source File | Has Unit Test? | Has Integration Test? | Estimated Effort |
|------------|----------------|----------------------|-----------------|
```

**If Layer 2 ran**, include infrastructure audit findings:

```
## Layer 2: Infrastructure Audit

### CI Workflow Findings

| Check | File | Finding | Severity | Issue Ref |
|-------|------|---------|----------|-----------|

### Skip/Xfail Audit

| File:Line | Type | Reason | Issue | Status |
|-----------|------|--------|-------|--------|
```

Prefix "Stale" entries with "(potential)" to indicate heuristic detection — e.g., `Stale (potential)`.

Include the Test Pyramid visualization with block characters (█) and any warnings (INVERTED PYRAMID, MISSING TIER).

Include Config Parity findings if applicable:

```
### Config Parity

| Config | Setting | CI | Status |
|--------|---------|-----|--------|
```

**If Layer 3 ran**, include project-type-specific findings and report quality:

```
## Layer 3: Project-Aware Heuristics ({type})
```

Use project-type-appropriate tables. Examples:

For `browser-extension`:
```
### Extension Code Coverage
| Extension File | Unit Test | Status |
|----------------|-----------|--------|

### Mock Fidelity
| Mock File | Source Age Gap | Known Bad APIs |
|-----------|---------------|----------------|

### Cross-Browser Parity
| Aspect | Chrome | Firefox | Status |
|--------|--------|---------|--------|
```

For `api`:
```
### Handler Test Coverage
| Handler File | Integration Test | Status |
|-------------|-----------------|--------|
```

For `webapp`:
```
### Component Test Coverage
| Component | Test File | Status |
|-----------|-----------|--------|
```

Always include report quality (all project types):
```
### Test Report Quality

| Report | Score | Missing Sections |
|--------|-------|------------------|
```

**Omit any section or table that has no findings.** Don't show empty tables.

**Omit layers that weren't run.** If only `--layer infra` was specified, don't show Layer 1 or Layer 3 headings.

**Always include (if any findings exist across all layers):**

**Recommended Actions** — a single table sorted by severity (CRITICAL → HIGH → MEDIUM → LOW), and within same severity by check ID alphabetically:

```
## Recommended Actions

| # | Severity | Check ID | Finding | File |
|---|----------|----------|---------|------|
| 1 | CRITICAL | EXT-005 | ... | ... |
| 2 | HIGH | CI-001 | ... | ... |
| 3 | HIGH | CI-006 | ... | ... |
| 4 | MEDIUM | CI-003 | ... | ... |

_Sorted: CRITICAL → HIGH → MEDIUM → LOW_
```

**Issues to Create** — a checkbox list containing ONLY HIGH and CRITICAL findings:

```
## Issues to Create

- [ ] `test: {description}` — {Check ID} ({file})
- [ ] `test: {description}` — {Check ID} ({file})

_Only HIGH and CRITICAL findings listed. Review before creating._
```

If no findings at all across all layers that ran, output: "No test gaps detected. Test health looks good!"

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

| Mode | Layers | Est. Tool Calls | Est. Cost |
|------|--------|-----------------|-----------|
| Quick (default) | 1 | 8–15 | ~$0.03 |
| `--layer infra` | 2 | 8–13 | ~$0.05 |
| `--layer heuristics` | 3 | 10–20 | ~$0.08 |
| `--full` | 1, 2, 3 | 30–50 | ~$0.15 |

---

## Notes

- Layer 2 and 3 checks use IDs (CI-001, EXT-001, etc.) for traceability in issues
- Run periodically (weekly recommended) to prevent test debt accumulation
- Helps maintain test-first philosophy compliance

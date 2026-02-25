---
repo: martymcenroe/AssemblyZero
issue: 444
url: https://github.com/martymcenroe/AssemblyZero/issues/444
fetched: 2026-02-25T02:42:32.204924Z
---

# Issue #444: feat: enhance /test-gaps with infrastructure audit and project-aware heuristics

## Summary

Enhance the `/test-gaps` skill from "grep reports for keywords" to "comprehensive test health analysis" by adding two new analysis layers while preserving existing behavior as Layer 1.

### Motivation

Real-world usage across Aletheia and Hermes revealed testing dimensions the skill is completely blind to:

- **Aletheia #448:** Visual regression tests silently skipped on Linux CI because baselines didn't exist — no report would ever mention this
- **Aletheia audit 10826:** Firefox mock had `browser.identity` (an API that doesn't exist in Firefox MV3) — all unit tests passed against fictional APIs
- **Aletheia e2e-edge.yml:** Edge tests gated behind `continue-on-error: true` with no tracked remediation
- **Aletheia:** popup.js had 484 lines with zero unit tests (inverted test pyramid)
- **Hermes:** Good dashboard unit tests but zero backend tests, no CI workflows at all

The skill needs to evolve from "grep reports for keywords" to "comprehensive test health analysis."

---

## Design

### New Arguments (Backward-Compatible)

```
/test-gaps [--full] [--file path] [--layer reports|infra|heuristics|all] [--project-type auto|extension|api|webapp|cli]
```

| Argument | Description | Default |
|----------|-------------|---------|
| (none) | Layer 1 quick scan (identical to current behavior) | Layer 1 |
| `--full` | All 3 layers, all reports | All layers |
| `--layer reports` | Layer 1 only | -- |
| `--layer infra` | Layer 2 only (CI/config audit) | -- |
| `--layer heuristics` | Layer 3 only (project-aware checks) | -- |
| `--project-type` | Override auto-detected project type | `auto` |

### Step 0: Project Type Detection

Before any layer runs, auto-detect project type via Glob for marker files:

| Type | Marker Files |
|------|-------------|
| `browser-extension` | `extensions/*/manifest.json` or `manifest.json` with `manifest_version` |
| `webapp` | `vite.config.*`, `next.config.*`, `src/**/App.{tsx,jsx}` |
| `api` | `**/lambda_function.py`, `serverless.yml`, `src/**/*handler*.py` |
| `cli` | `argparse`/`click`/`typer` in pyproject.toml |
| `generic` | fallback |

### Layer 1: Report Mining (Existing — Preserved Verbatim)

No changes. Existing grep patterns, 8 gap categories, cross-reference logic, output tables. Just wrapped under a "Layer 1" heading.

### Layer 2: Infrastructure Audit (New)

**2.1 CI Workflow Analysis** — Read `.github/workflows/*.yml`:

| Check | Pattern | Severity |
|-------|---------|----------|
| CI-001 | `continue-on-error: true` on test jobs | HIGH |
| CI-002 | No test discovery validation (absence of `collected.*item` check) | HIGH |
| CI-003 | `fail_ci_if_error: false` on coverage upload | MEDIUM |
| CI-004 | Coverage upload without threshold enforcement | MEDIUM |
| CI-005 | Fewer browsers in CI than in playwright config `projects` | HIGH |
| CI-006 | `continue-on-error` without linked issue reference in comment | HIGH |

**2.2 Skip/Xfail Audit** — Grep test files for skip patterns:

```
test\.skip|describe\.skip|it\.skip     (JS/TS)
pytest\.mark\.skip|pytest\.skip|xfail  (Python)
```

Classify each skip:
- **Tracked**: Has issue reference (e.g., `#448`), issue still open → MEDIUM
- **Stale**: Issue reference but issue is closed → HIGH (skip should be removed)
- **Untracked**: No issue reference → HIGH
- **Conditional**: Uses `skipif` with platform/env check → LOW

**2.3 Test Pyramid Count** — Grep count `test\(|it\(|def test_` across `tests/unit/`, `tests/integration/`, `tests/e2e/`:

```
Unit:         NN (XX%)  ████████████████
Integration:  NN (XX%)  ████████
E2E:          NN (XX%)  ████████████
```

Flag if E2E > Unit (inverted pyramid).

**2.4 Test Config Analysis** — Read playwright/vitest/pytest configs, compare configured projects vs CI browser installs.

### Layer 3: Project-Aware Heuristics (New)

Only checks matching the detected project type run.

**Browser Extension (`browser-extension`):**

| Check | What | Severity |
|-------|------|----------|
| EXT-001 | Extension JS file without corresponding unit test | HIGH |
| EXT-002 | Mock file older than source by >30 days (staleness) | MEDIUM |
| EXT-003 | Chrome has N unit test files, Firefox has fewer | HIGH |
| EXT-004 | Playwright config has browser project with no CI job | HIGH |
| EXT-005 | Mock references APIs that don't exist on target platform | CRITICAL |
| EXT-006 | Visual baselines exist for one platform but not another | MEDIUM |

**API/Lambda (`api`):**

| Check | What | Severity |
|-------|------|----------|
| API-001 | Handler file without integration test | HIGH |
| API-002 | No contract tests directory | MEDIUM |
| API-003 | No post-deploy smoke test in CI | MEDIUM |

**Web App (`webapp`):**

| Check | What | Severity |
|-------|------|----------|
| WEB-001 | Component without test file | HIGH |
| WEB-002 | No visual regression snapshots | MEDIUM |
| WEB-003 | No accessibility tests (pa11y/axe) | HIGH |

**Test Report Quality Grading (all types):**

Grade recent test reports against ADR 0205:
- "What was tested" section → +1
- "How tested" (automated vs manual) → +1
- "What was NOT tested" section → +1
- Evidence (logs, screenshots) → +1

Score 0-4 per report; flag reports scoring ≤1.

### Output Format

```markdown
# Test Gap Analysis

**Scan type:** Quick/Full | **Project type:** browser-extension (auto) | **Date:** YYYY-MM-DD

## Layer 1: Report Mining
[existing tables]

## Layer 2: Infrastructure Audit

### CI Workflow Findings
| Check | File | Finding | Severity | Issue Ref |

### Skip/Xfail Audit
| File:Line | Type | Reason | Issue | Status |

### Test Pyramid
[bar chart + inversion warning]

## Layer 3: Project-Aware Heuristics (browser-extension)

### Extension Code Coverage
| Extension File | Lines | Unit Test | Status |

### Mock Fidelity
| Mock File | Age | Known Bad APIs |

### Cross-Browser Parity
| Aspect | Chrome | Firefox | Status |

### Test Report Quality
| Report | Score | Missing Sections |

## Recommended Actions
1. **[CRITICAL]** ... — Check ID
2. **[HIGH]** ... — Check ID

## Issues to Create
- [ ] `test: ...` — Check ID
```

### Cost Efficiency

| Mode | Layers | Est. Tool Calls | Est. Cost |
|------|--------|-----------------|-----------|
| Quick (default) | 1 | 8-15 | ~$0.03 |
| `--layer infra` | 2 | 8-13 | ~$0.05 |
| `--full` | 1,2,3 | 30-50 | ~$0.15 |

All layers use Grep pre-filtering before expensive Read calls.

---

## Files Modified

| File | Change |
|------|--------|
| `.claude/commands/test-gaps.md` | Expand from ~150 lines to ~400-450 lines with 3 layers |

No other files modified — this is a skill definition change only.

## Verification

After implementation, run against Aletheia:
- `/test-gaps` (default) → identical to current behavior
- `/test-gaps --layer infra` → detects `continue-on-error: true` in e2e-edge.yml, counts test pyramid
- `/test-gaps --layer heuristics` → auto-detects `browser-extension`, checks visual baselines, mock fidelity
- `/test-gaps --full` → all 3 layers with separated output
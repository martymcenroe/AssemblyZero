# 116 - Feature: Add GitHub Actions CI Workflow for Automated Testing

<!-- Template Metadata
Last Updated: 2025-01-XX
Updated By: Initial creation
Update Reason: New feature implementation
-->

## 1. Context & Goal
* **Issue:** #116
* **Objective:** Implement a GitHub Actions CI workflow that automatically runs tests on PRs and pushes, with tiered execution strategy for optimal speed vs. coverage balance.
* **Status:** Draft
* **Related Issues:** N/A

### Open Questions

- [x] Which CI strategy to use? → **Option D: Hybrid (tiered by trigger + markers)**
- [ ] Python version matrix: 3.10, 3.11, 3.12 or just 3.11?
- [ ] Coverage threshold for new code: 90% or different?
- [ ] Should live tests require manual trigger or run on nightly schedule?

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `.github/workflows/ci.yml` | Add | Main CI workflow file with tiered test execution |
| `.github/workflows/nightly.yml` | Add | Nightly workflow for full test suite including live tests |
| `pyproject.toml` | Modify | Add pytest markers configuration |
| `pytest.ini` or `pyproject.toml` | Modify | Register custom pytest markers |
| `conftest.py` | Modify | Add marker auto-application fixtures if needed |
| `README.md` | Modify | Add CI status badge |

### 2.2 Dependencies

```toml
# pyproject.toml additions (if any)
# No new runtime dependencies required

# Dev dependencies (likely already present)
pytest = "^7.0"
pytest-cov = "^4.0"
```

### 2.3 Data Structures

```python
# Pseudocode - Pytest marker categories
MARKERS = {
    "fast": "Tests that complete in < 1 second",
    "slow": "Tests that take > 1 second or require heavy setup",
    "live": "Tests that hit real external APIs",
    "unit": "Pure unit tests with no external dependencies",
    "integration": "Tests that verify component integration",
}
```

### 2.4 Function Signatures

```yaml
# GitHub Actions workflow structure (not Python)
# ci.yml jobs:
jobs:
  lint:
    # Code quality checks
  test-fast:
    # Unit + fast tests on all PRs
  test-full:
    # Full regression on main pushes
  coverage:
    # Coverage reporting
```

### 2.5 Logic Flow (Pseudocode)

```
1. PR opened/updated:
   a. Run lint job (ruff, mypy)
   b. Run test-fast job (unit tests, ~2-3 min)
   c. Generate coverage report for changed files
   d. Post coverage comment to PR

2. Push to main:
   a. Run lint job
   b. Run test-full job (all except live, ~20 min)
   c. Generate full coverage report
   d. Upload coverage to service (optional)

3. Nightly schedule (6 AM UTC):
   a. Run lint job
   b. Run all tests including live
   c. Generate comprehensive coverage report
   d. Alert on failures via GitHub notification

4. Manual trigger (workflow_dispatch):
   a. Allow selection of test scope (fast/full/live)
   b. Run selected scope
   c. Generate appropriate reports
```

### 2.6 Technical Approach

* **Module:** `.github/workflows/`
* **Pattern:** Tiered CI with pytest markers (Option D - Hybrid)
* **Key Decisions:**
  - Use matrix strategy for potential multi-Python version testing
  - Cache poetry dependencies for faster runs
  - Separate lint from test jobs for parallel execution
  - Use pytest markers for granular test selection

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| CI Strategy | A (trigger-based), B (markers), C (changed files), D (hybrid) | D (Hybrid) | Best balance of speed (~3 min PRs) and safety (full on main) |
| Test categorization | Directory-based, marker-based | Marker-based | More flexible, allows fine-grained control within directories |
| Python versions | Single (3.11), Multi (3.10-3.12) | Start with 3.11, expand later | Reduce initial CI time, expand once stable |
| Coverage tool | pytest-cov, coverage.py | pytest-cov | Better pytest integration |
| Cache strategy | None, poetry cache, pip cache | Poetry cache | Project uses poetry, significant speedup |

**Architectural Constraints:**
- Must not require API keys for standard CI runs (use mocks)
- Must set `LANGSMITH_TRACING=false` to avoid tracing overhead
- Must complete PR checks in under 5 minutes for good developer experience
- Must be maintainable by team without deep GitHub Actions expertise

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. Tests run automatically on every PR opened or updated
2. Tests run automatically on every push to main branch
3. Nightly workflow runs full test suite including live tests
4. Coverage report generated and visible on PRs
5. CI status badge displayed in README
6. PR tests complete in under 5 minutes
7. Main branch tests complete in under 25 minutes
8. All existing tests continue to pass
9. Clear documentation on how to add markers to new tests

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Option A: Tiered by Trigger | Simple, predictable | PRs might miss integration bugs | Rejected |
| Option B: Tiered by Markers | Fine-grained control | Requires marking all 600 tests upfront | Rejected |
| Option C: Changed Files Detection | Fast, targeted | Complex to configure, might miss cross-cutting bugs | Rejected |
| Option D: Hybrid (A + B) | Balance of speed and safety, can evolve | More complex workflow | **Selected** |

**Rationale:** Option D provides the best developer experience (fast PR feedback) while maintaining safety (full regression on main). The marker system can be adopted incrementally - start with trigger-based tiers, add markers as needed for problematic tests.

## 5. Data & Fixtures

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | GitHub Events (push, pull_request, schedule) |
| Format | GitHub Actions event payloads |
| Size | N/A - event-driven |
| Refresh | Real-time on triggers |
| Copyright/License | N/A |

### 5.2 Data Pipeline

```
GitHub Event ──trigger──► Workflow Runner ──pytest──► Test Results ──upload──► GitHub Checks/Artifacts
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Mock API responses | Generated in conftest.py | Already exist, no live calls in fast/full |
| Test configuration | Repository secrets | Only needed for live tests |

### 5.4 Deployment Pipeline

- **Dev:** Run `poetry run pytest` locally
- **Test (PR):** Automated via ci.yml on PR events
- **Production (main):** Full regression on merge to main

**No external data utility needed.**

## 6. Diagram

### 6.1 Mermaid Quality Gate

Before finalizing any diagram, verify in [Mermaid Live Editor](https://mermaid.live) or GitHub preview:

- [x] **Simplicity:** Similar components collapsed (per 0006 §8.1)
- [x] **No touching:** All elements have visual separation (per 0006 §8.2)
- [x] **No hidden lines:** All arrows fully visible (per 0006 §8.3)
- [x] **Readable:** Labels not truncated, flow direction clear
- [ ] **Auto-inspected:** Agent rendered via mermaid.ink and viewed (per 0006 §8.5)

**Auto-Inspection Results:**
```
- Touching elements: [x] None / [ ] Found: ___
- Hidden lines: [x] None / [ ] Found: ___
- Label readability: [x] Pass / [ ] Issue: ___
- Flow clarity: [x] Clear / [ ] Issue: ___
```

### 6.2 Diagram

```mermaid
flowchart TD
    subgraph Triggers
        PR[PR Opened/Updated]
        PUSH[Push to Main]
        SCHED[Nightly Schedule]
        MANUAL[Manual Dispatch]
    end

    subgraph Jobs
        LINT[Lint Job<br/>ruff + mypy]
        FAST[Test Fast<br/>~3 min]
        FULL[Test Full<br/>~20 min]
        LIVE[Test Live<br/>~5 min]
        COV[Coverage Report]
    end

    subgraph Outputs
        CHECK[GitHub Check Status]
        BADGE[README Badge]
        COMMENT[PR Comment]
        ARTIFACT[Coverage Artifact]
    end

    PR --> LINT
    PR --> FAST
    FAST --> COV
    COV --> COMMENT

    PUSH --> LINT
    PUSH --> FULL
    FULL --> COV
    COV --> ARTIFACT

    SCHED --> LINT
    SCHED --> FULL
    SCHED --> LIVE

    MANUAL --> LINT
    MANUAL --> FAST
    MANUAL --> FULL
    MANUAL --> LIVE

    LINT --> CHECK
    FAST --> CHECK
    FULL --> CHECK
    LIVE --> CHECK
    CHECK --> BADGE
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Secret exposure | Use GitHub Secrets, never echo secrets | Addressed |
| Fork PR attacks | Restrict secrets from fork PRs | Addressed |
| Workflow injection | Pin action versions to SHA | Addressed |
| Dependency confusion | Use poetry.lock for reproducible builds | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| CI outage blocking PRs | Make live tests non-blocking (continue-on-error) | Addressed |
| Flaky tests blocking releases | Mark known flaky tests, track flakiness | TODO |
| Resource exhaustion | Set job timeout limits (30 min max) | Addressed |
| Cost overrun | Monitor usage, set concurrency limits | Addressed |

**Fail Mode:** Fail Closed - PR cannot merge if required checks fail

**Recovery Strategy:** 
- If CI is down: Manual override by admin
- If tests flaky: Skip with `[skip ci]` commit message as last resort, fix ASAP

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| PR check time | < 5 min | Run only fast/unit tests |
| Main branch time | < 25 min | Run full regression excluding live |
| Cache hit rate | > 80% | Cache poetry dependencies |
| Parallelization | 2-4 jobs | Split lint and test jobs |

**Bottlenecks:** 
- Full test suite is ~20 min - acceptable for main branch
- Large dependency installation - mitigated by caching

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| GitHub Actions (Linux) | Free (2000 min/mo for private) | ~500 min/mo | $0 (public repo) |
| Coverage service | Free tier | 1 report/day | $0 |

**Cost Controls:**
- [x] Using GitHub's free tier
- [x] Concurrency limits prevent parallel waste
- [x] Cancel in-progress runs on new pushes to same PR

**Worst-Case Scenario:** If usage spikes 10x, still within free tier for public repos. Private repos may need paid plan (~$4/1000 min overage).

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Tests use synthetic/mock data only |
| Third-Party Licenses | No | All GitHub Actions are MIT/Apache licensed |
| Terms of Service | Yes | Usage within GitHub Actions ToS |
| Data Retention | N/A | No persistent data stored |
| Export Controls | No | No restricted algorithms |

**Data Classification:** Public (all CI data is visible in public repo)

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented (GitHub default)

## 10. Verification & Testing

### 10.0 Test Plan (TDD - Complete Before Implementation)

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | PR triggers ci.yml | Workflow starts on PR open | RED |
| T020 | Push to main triggers full tests | Full regression runs on push | RED |
| T030 | Nightly schedule triggers | Workflow runs at 6 AM UTC | RED |
| T040 | Poetry cache works | Second run faster than first | RED |
| T050 | Coverage report generated | Artifact uploaded | RED |
| T060 | Badge URL works | Badge shows passing/failing status | RED |

**Coverage Target:** N/A (workflow files, not code)

**TDD Checklist:**
- [x] Test scenarios defined before implementation
- [x] Tests can be verified by running workflow
- [ ] Test file created at: N/A (manual workflow testing)

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | PR triggers lint and fast tests | Manual | Open PR with code change | Lint + test-fast jobs run | Jobs complete, status posted |
| 020 | Main push triggers full tests | Manual | Merge PR to main | test-full job runs | All tests pass |
| 030 | Nightly runs all tests | Manual | Wait for schedule or trigger | All jobs including live run | Complete without error |
| 040 | Failing test blocks PR | Manual | PR with failing test | Check shows failed | PR cannot merge |
| 050 | Coverage report on PR | Manual | PR with code changes | Comment with coverage | Coverage visible |
| 060 | Cache speeds up subsequent runs | Manual | Two consecutive runs | Second run faster | Poetry install < 30s |
| 070 | Manual dispatch works | Manual | Trigger workflow_dispatch | Selected tests run | Correct scope executes |
| 080 | Badge reflects status | Auto | Check badge URL | Shows current status | Badge renders correctly |

### 10.2 Test Commands

```bash
# Local testing before pushing workflow
act pull_request  # Requires 'act' tool installed

# Verify pytest markers work
poetry run pytest --collect-only -m "not slow and not live"

# Verify full test suite still works
poetry run pytest -v

# Verify coverage generation
poetry run pytest --cov=src --cov-report=xml
```

### 10.3 Manual Tests (Only If Unavoidable)

| ID | Scenario | Why Not Automated | Steps |
|----|----------|-------------------|-------|
| 010-070 | Workflow triggers | GitHub Actions workflows can only be fully tested by running on GitHub | 1. Push workflow file 2. Create test PR 3. Verify jobs run 4. Check results |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Workflow syntax errors | Med | Med | Test with `act` locally, validate YAML |
| Flaky tests cause CI failures | High | Med | Identify and mark flaky tests, add retry logic |
| Cache invalidation issues | Low | Low | Include cache key with lockfile hash |
| Live tests fail in CI | Med | Med | Ensure proper mocking, skip live by default |
| Excessive CI run times | Med | Low | Monitor and optimize, add timeouts |
| Breaking existing workflows | High | Low | Test in branch before merging |

## 12. Definition of Done

### Code
- [ ] `.github/workflows/ci.yml` created and functional
- [ ] `.github/workflows/nightly.yml` created and functional
- [ ] Pytest markers configured in `pyproject.toml`
- [ ] README updated with CI badge

### Tests
- [ ] All existing tests pass in new CI
- [ ] PR workflow completes in < 5 minutes
- [ ] Main workflow completes in < 25 minutes
- [ ] Coverage report generates correctly

### Documentation
- [ ] LLD updated with any deviations
- [ ] README documents how to add markers to new tests
- [ ] Implementation Report (0103) completed

### Review
- [ ] Code review completed
- [ ] Workflow tested on real PR before merge
- [ ] User approval before closing issue

---

## Appendix A: Workflow File Specifications

### ci.yml Structure

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      test_scope:
        description: 'Test scope to run'
        required: true
        default: 'fast'
        type: choice
        options:
          - fast
          - full
          - all

env:
  LANGSMITH_TRACING: "false"
  PYTHON_VERSION: "3.11"

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install poetry
        uses: snok/install-poetry@v1
      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pypoetry
          key: poetry-${{ hashFiles('poetry.lock') }}
      - name: Install dependencies
        run: poetry install
      - name: Run linters
        run: |
          poetry run ruff check .
          poetry run ruff format --check .

  test-fast:
    if: github.event_name == 'pull_request' || github.event.inputs.test_scope == 'fast'
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install poetry
        uses: snok/install-poetry@v1
      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pypoetry
          key: poetry-${{ hashFiles('poetry.lock') }}
      - name: Install dependencies
        run: poetry install
      - name: Run fast tests
        run: poetry run pytest tests/unit/ -v --tb=short -m "not slow and not live"
      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-fast
          path: coverage.xml

  test-full:
    if: github.event_name == 'push' || github.event.inputs.test_scope == 'full' || github.event.inputs.test_scope == 'all'
    runs-on: ubuntu-latest
    needs: lint
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install poetry
        uses: snok/install-poetry@v1
      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pypoetry
          key: poetry-${{ hashFiles('poetry.lock') }}
      - name: Install dependencies
        run: poetry install
      - name: Run full tests
        run: poetry run pytest -v --tb=short -m "not live" --cov=src --cov-report=xml
      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-full
          path: coverage.xml
```

### nightly.yml Structure

```yaml
name: Nightly

on:
  schedule:
    - cron: '0 6 * * *'  # 6 AM UTC daily
  workflow_dispatch:

env:
  LANGSMITH_TRACING: "false"
  PYTHON_VERSION: "3.11"

jobs:
  test-all:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install poetry
        uses: snok/install-poetry@v1
      - name: Install dependencies
        run: poetry install
      - name: Run all tests including live
        run: poetry run pytest -v --tb=short --cov=src --cov-report=xml --cov-report=html
        env:
          # Add any secrets needed for live tests
          API_KEY: ${{ secrets.API_KEY }}
      - name: Upload coverage report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov/
```

---

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | - |

**Final Status:** PENDING
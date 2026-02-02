# 120 - Feature: Configure LangSmith Project for Tracing

<!-- Template Metadata
Last Updated: 2025-01-10
Updated By: Issue #120 revision per Gemini Review #1
Update Reason: Address Tier 1/2 blocking issues - worktree scope, automated testing
-->

## 1. Context & Goal
* **Issue:** #120
* **Objective:** Create a dedicated "AgentOS" project in LangSmith and configure project-specific tracing for better trace organization.
* **Status:** Draft
* **Related Issues:** None

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [x] Is the LangSmith API key already configured? (Assumed yes - existing tracing works with default project)
- [x] Should we add validation that traces are appearing in the new project? (Yes - automated via SDK)

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/setup/langsmith-configuration.md` | Add | Document LangSmith project setup instructions |
| `scripts/verify_langsmith.py` | Add | Verification script to validate project exists and traces route correctly |
| `templates/env.example` | Modify | Update example env with `LANGCHAIN_PROJECT="AgentOS"` uncommented |

### 2.2 Dependencies

*New packages, APIs, or services required.*

```toml
# pyproject.toml additions (if any)
# langsmith already included - used for programmatic verification
```

### 2.3 Data Structures

```python
# N/A - Configuration change only, no new data structures
```

### 2.4 Function Signatures

```python
# scripts/verify_langsmith.py
def verify_project_exists(project_name: str) -> bool:
    """Check if LangSmith project exists using SDK client."""
    ...

def verify_trace_routing(project_name: str) -> bool:
    """Run minimal chain and verify trace appears in correct project."""
    ...

def main() -> int:
    """Run all verification checks, return exit code."""
    ...
```

### 2.5 Logic Flow (Pseudocode)

```
1. User creates "AgentOS" project in LangSmith web UI (one-time setup)
2. User updates their local ~/.agentos/env based on templates/env.example
3. Run verification script:
   a. Initialize LangSmith client
   b. Call client.read_project("AgentOS") to verify existence
   c. Run minimal traced operation
   d. Query SDK for recent runs with project filter
   e. Verify run appears in correct project
4. Script exits 0 on success, non-zero on failure
```

### 2.6 Technical Approach

* **Module:** `scripts/verify_langsmith.py`, `docs/setup/langsmith-configuration.md`
* **Pattern:** Verification script + documentation pattern
* **Key Decisions:** Using LangSmith Python SDK for automated verification rather than manual UI inspection

### 2.7 Architecture Decisions

*Document key architectural decisions that affect the design.*

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Project naming | "AgentOS", "agentos", "agent-os" | "AgentOS" | Matches project branding, consistent with repository name |
| Configuration method | Hardcode in app, env var, config file | Environment variable | Standard LangChain pattern, allows per-environment override |
| Verification approach | Manual UI, SDK client, API calls | SDK client | Enables automated testing, CI integration |
| Repository artifacts | Config file only, docs only, both | Docs + verification script | Provides both guidance and automated validation |

**Architectural Constraints:**
- Cannot modify user's `~/.agentos/env` directly from repository (user-local config)
- Must use existing LangSmith SDK (already a dependency)
- Verification script must work with any valid LangSmith API key

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. An "AgentOS" project exists in LangSmith (verified programmatically via SDK)
2. `templates/env.example` contains uncommented `LANGCHAIN_PROJECT="AgentOS"` line
3. Documentation exists explaining setup process
4. Verification script confirms traces route to AgentOS project

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| LangSmith project | Clean separation, easy filtering, built-in analytics | Requires web UI setup | **Selected** |
| Tag-based filtering | No project creation needed | Harder to filter, traces mixed with others | Rejected |
| Separate LangSmith org | Complete isolation | Overkill for single project | Rejected |

**Rationale:** LangSmith projects are the intended mechanism for organizing traces by application. This provides clean separation without additional overhead.

## 5. Data & Fixtures

*Per [0108-lld-pre-implementation-review.md](0108-lld-pre-implementation-review.md) - complete this section BEFORE implementation.*

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | LangSmith API (via SDK) |
| Format | SDK client responses |
| Size | N/A |
| Refresh | On-demand verification |
| Copyright/License | N/A - SaaS API |

### 5.2 Data Pipeline

```
templates/env.example ──copied by user──► ~/.agentos/env ──sourced by shell──► Environment Variables ──read by LangChain SDK──► LangSmith API
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Mock LangSmith client | Generated | For unit tests without live API |
| Sample project response | Hardcoded | Expected SDK response structure |

### 5.4 Deployment Pipeline

1. Repository provides `templates/env.example` with correct configuration
2. Developer copies to `~/.agentos/env` and sources it
3. Developer creates project in LangSmith UI
4. Developer runs `scripts/verify_langsmith.py` to confirm setup

**If data source is external:** LangSmith is the external service. Verification script handles validation.

## 6. Diagram

### 6.1 Mermaid Quality Gate

Before finalizing any diagram, verify in [Mermaid Live Editor](https://mermaid.live) or GitHub preview:

- [x] **Simplicity:** Similar components collapsed (per 0006 §8.1)
- [x] **No touching:** All elements have visual separation (per 0006 §8.2)
- [x] **No hidden lines:** All arrows fully visible (per 0006 §8.3)
- [x] **Readable:** Labels not truncated, flow direction clear
- [x] **Auto-inspected:** Agent rendered via mermaid.ink and viewed (per 0006 §8.5)

**Agent Auto-Inspection (MANDATORY):**

**Auto-Inspection Results:**
```
- Touching elements: [x] None / [ ] Found: ___
- Hidden lines: [x] None / [ ] Found: ___
- Label readability: [x] Pass / [ ] Issue: ___
- Flow clarity: [x] Clear / [ ] Issue: ___
```

*Reference: [0006-mermaid-diagrams.md](0006-mermaid-diagrams.md)*

### 6.2 Diagram

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Repo as Repository
    participant Env as ~/.agentos/env
    participant Script as verify_langsmith.py
    participant SDK as LangSmith SDK
    participant LS as LangSmith API

    Dev->>Repo: Copy templates/env.example
    Repo-->>Env: LANGCHAIN_PROJECT=AgentOS
    Dev->>LS: Create AgentOS project (Web UI)
    
    Note over Dev,Script: Verification
    
    Dev->>Script: python scripts/verify_langsmith.py
    Script->>SDK: client.read_project("AgentOS")
    SDK->>LS: GET /projects/AgentOS
    LS-->>SDK: Project exists
    SDK-->>Script: Success
    Script->>SDK: Run minimal traced operation
    SDK->>LS: POST /runs (project=AgentOS)
    LS-->>SDK: Run ID
    Script->>SDK: client.list_runs(project="AgentOS")
    SDK->>LS: GET /runs?project=AgentOS
    LS-->>SDK: Run list
    Script-->>Dev: Verification passed ✓
```

## 7. Security & Safety Considerations

*This section addresses security (10 patterns) and safety (9 patterns) concerns from governance feedback.*

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| API key exposure | Key stored in user-local ~/.agentos/env with appropriate permissions; not committed to repo | Addressed |
| Project access control | LangSmith project inherits organization permissions | Addressed |
| Verification script credentials | Uses environment variables, never hardcodes keys | Addressed |

### 7.2 Safety

*Safety concerns focus on preventing data loss, ensuring fail-safe behavior, and protecting system integrity.*

| Concern | Mitigation | Status |
|---------|------------|--------|
| Loss of existing traces | Existing traces remain in default project, only new traces go to AgentOS | Addressed |
| Configuration error | If project doesn't exist, verification script fails with clear error message | Addressed |
| Verification creates orphan runs | Minimal verification trace clearly labeled, negligible overhead | Addressed |

**Fail Mode:** Fail Closed - Verification script returns non-zero exit code if project doesn't exist or traces don't route correctly

**Recovery Strategy:** If verification fails, user reviews documentation and corrects configuration

## 8. Performance & Cost Considerations

*This section addresses performance and cost concerns (6 patterns) from governance feedback.*

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Verification latency | < 10s | Single project check + one minimal trace |
| Memory | < 50MB | SDK client only |
| API Calls | 3-4 per verification | read_project, create run, list_runs |

**Bottlenecks:** None - verification is one-time setup validation

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| LangSmith API (verification) | Per plan limits | 1-5 runs per setup | Negligible |
| LangSmith traces (ongoing) | Per plan limits | No change from baseline | No change |

**Cost Controls:**
- [x] No additional costs - using existing LangSmith subscription
- [x] Project organization doesn't incur extra charges
- [x] Verification runs minimal traces

**Worst-Case Scenario:** N/A - configuration change doesn't affect trace volume

## 9. Legal & Compliance

*This section addresses legal concerns (8 patterns) from governance feedback.*

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | N/A | No change to what data is traced |
| Third-Party Licenses | N/A | Using existing LangSmith service |
| Terms of Service | Yes | Already compliant with LangSmith ToS |
| Data Retention | N/A | Governed by existing LangSmith settings |
| Export Controls | N/A | No change |

**Data Classification:** Internal (traces may contain workflow execution details)

**Compliance Checklist:**
- [x] No PII stored without consent (no change to trace content)
- [x] All third-party licenses compatible (using existing service)
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented (per LangSmith account settings)

## 10. Verification & Testing

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** All verification automated via LangSmith SDK. No manual UI inspection required.

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Project exists in LangSmith | Auto-Live | project_name="AgentOS" | Project object returned | `client.read_project()` succeeds without exception |
| 020 | Environment template updated | Auto | `grep LANGCHAIN_PROJECT templates/env.example` | Uncommented line with "AgentOS" | Line exists without leading `#` |
| 030 | Traces route to project | Auto-Live | Run minimal traced chain | Run appears in AgentOS project | `client.list_runs(project_name="AgentOS")` contains test run ID |
| 040 | Documentation exists | Auto | Check file exists | `docs/setup/langsmith-configuration.md` present | File exists and contains setup instructions |
| 050 | Verification script runs | Auto-Live | `python scripts/verify_langsmith.py` | Exit code 0 | All checks pass |

*Note: Use 3-digit IDs with gaps of 10 (010, 020, 030...) to allow insertions.*

### 10.2 Test Commands

```bash
# Verify environment template is correct
grep -E "^export LANGCHAIN_PROJECT" templates/env.example

# Run automated verification (requires LANGSMITH_API_KEY set)
python scripts/verify_langsmith.py

# Run pytest suite for verification script
poetry run pytest tests/test_verify_langsmith.py -v

# Run only mocked tests (no live API)
poetry run pytest tests/test_verify_langsmith.py -v -m "not live"

# Run live integration tests
poetry run pytest tests/test_verify_langsmith.py -v -m live
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated via LangSmith SDK.

*Full test results recorded in Implementation Report (0103) or Test Report (0113).*

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Typo in project name | Low | Low | Verification script validates exact match |
| LangSmith API unavailable | Med | Low | Verification script has clear error messages; retry logic |
| User forgets to source env | Low | Medium | Documentation emphasizes this step; verification catches it |
| SDK version incompatibility | Low | Low | Pin SDK version in pyproject.toml |

## 12. Definition of Done

### Code
- [ ] `scripts/verify_langsmith.py` implemented and linted
- [ ] `templates/env.example` updated with correct configuration
- [ ] Code comments reference this LLD

### Tests
- [ ] All test scenarios pass (010-050)
- [ ] Verification script exits 0 when properly configured

### Documentation
- [ ] `docs/setup/langsmith-configuration.md` created
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

---

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

### Gemini Review #1 (REVISE)

**Timestamp:** 2025-01-10
**Reviewer:** Gemini 3 Pro
**Verdict:** REVISE

#### Comments

| ID | Comment | Implemented? |
|----|---------|--------------|
| G1.1 | "Worktree Scope Violation: Section 2.1 lists `~/.agentos/env` as the file to be changed. This path is in the user's home directory and cannot be committed to the repository." | YES - Changed to repository files: `docs/setup/langsmith-configuration.md`, `scripts/verify_langsmith.py`, `templates/env.example` |
| G1.2 | "Requirement Coverage (33%): The LLD relies on manual verification for project creation and trace validation." | YES - All tests now automated via LangSmith SDK |
| G1.3 | "Automated Testing Possible: The `Why Not Automated` column claims these require the Web UI. This is incorrect. The `langsmith` Python SDK allows programmatic verification." | YES - Manual tests replaced with Auto-Live tests using SDK |
| G1.4 | "Path Structure: Explicitly state which repository files will be modified" | YES - Section 2.1 now lists only repository files |

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Gemini #1 | 2025-01-10 | REVISE | Worktree scope violation, manual tests should be automated |

**Final Status:** PENDING
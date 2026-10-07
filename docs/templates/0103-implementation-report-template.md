# 0103 - Template: Implementation Report

## Purpose

The Implementation Report documents **what was actually built** versus what was planned in the LLD. It is the narrative companion to the Test Report (which provides evidence).

**Analogy:**
- LLD = Architectural blueprints (the plan)
- Implementation Report = Construction journal (what happened)
- Test Report = Building inspection certificate (proof it works)

## Usage

After completing implementation of a feature:
1. Create directory `docs/reports/{IssueID}/`
2. Create `implementation-report.md` using this template
3. Create `test-report.md` using template 0113
4. Optionally save raw test output to `test-output.log`

**Always create an Implementation Report**, even if there are no deviations from the LLD.

---

## Template

```markdown
# {IssueID} - Implementation Report: {Feature Title}

## 1. Metadata

| Field | Value |
|-------|-------|
| **Issue** | #{IssueID} |
| **LLD** | `docs/1{IssueID}-{feature-name}.md` |
| **Test Report** | `docs/reports/{IssueID}/test-report.md` |
| **Implementer** | {Model Name} via {Interface} |
| **Date** | {YYYY-MM-DD} |
| **PR** | #{PR_Number} |

## 2. Summary

{Concise description of what was built. May be multiple paragraphs if needed, but stay focused. Reference the LLD for full context.}

## 3. Files Created

| File | Description |
|------|-------------|
| `path/to/file.py` | {What it does} |
| `tests/test_file.py` | {Test coverage} |

## 4. Files Modified

| File | Changes | Description |
|------|---------|-------------|
| `path/to/existing.py` | +XX/-YY lines | {What changed and why} |

## 5. Deviations from LLD

{Always fill this section. If no deviations, state "None - implementation matches LLD exactly."}

| Deviation | Reason | Impact |
|-----------|--------|--------|
| {What changed from plan} | {Why it changed} | {Effect on system} |

## 6. Test Harness

{Describe any test infrastructure created for this feature.}

- **Test file:** `tests/test_{feature}.py`
- **Fixtures:** {Any pytest fixtures created}
- **Test data:** {Any test data files}
- **Utilities:** {Any helper functions for testing}

## 7. Test Coverage

| Area | Coverage | Notes |
|------|----------|-------|
| {Happy path} | Covered | {Test IDs from LLD} |
| {Edge cases} | Covered | {Test IDs} |
| {Error handling} | Partial | {What's not covered and why} |
| {Performance} | Not covered | {Reason - e.g., "deferred to integration testing"} |

**Willison Protocol Compliance:**
- [ ] Automated tests written
- [ ] Tests fail on revert (verified)
- [ ] Proof captured in Test Report

## 7a. Loud-failure compliance (standard 0034)

{Every failure path this change adds or touches: an `except`, a returned error, a checked return code, a retry loop. For each, how it is loud, logged with details, stops dependent processing, and alerts the operator. "None added or touched" is a valid answer only when true.}

| Site (file:line) | Loud | Logged | Stops | Alerts |
|------------------|------|--------|-------|--------|
| {path:line} | {ERROR to stderr} | {fields} | {HALT / exit 1 / raise} | {alert_operator / HALT} |

## 8. Lessons Learned

{What would you do differently? What surprised you? What should future implementers know?}

- {Lesson 1}
- {Lesson 2}

## 9. Open Issues

{Any follow-up work identified during implementation.}

| Issue | Type | Description |
|-------|------|-------------|
| #{NewIssueID} | Bug/Enhancement | {Created during implementation} |
| N/A | Note | {Something to consider for future} |

## 10. Orchestrator Review Notes

**Reviewer:** {Orchestrator name}
**Date:** {YYYY-MM-DD}

### In-Scope Observations
{Observations about this feature that were addressed before merge.}
- {Observation}

### New-Scope Observations
{Observations that warrant new issues.}
- Created: #{IssueID} - {description}

### Meta Observations
{Process improvements identified during this review.}
- {Suggestion for CMS/workflow changes}

### Approval
- [ ] Code reviewed
- [ ] Manual tests passed (see Test Report)
- [ ] Ready for merge
```

---

## Tips for Good Reports

1. **Always fill Deviations:** Even "None" is valuable information
2. **Be specific about files:** Include all created/modified files
3. **Test coverage honesty:** Document what's NOT covered and why
4. **Link to Test Report:** The evidence lives there, not here
5. **Lessons are gold:** Future you (or another agent) will thank you
6. **Orchestrator section:** LLM fills this based on orchestrator feedback via prompts

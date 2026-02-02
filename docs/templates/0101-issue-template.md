# 0101 - Template: GitHub Issue (Feature)

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Verdict Analyzer (tools/verdict-analyzer.py)
Update Reason: Added AC guidance, Open Questions section, dependency validation based on 230 blocking issues from 227 verdicts
Top blockers: quality (60), architecture (52), legal (23), security (19), safety (12), cost (10)
-->

## Usage
Copy this template when creating a new feature issue via `gh issue create`.

---

## Template

```markdown
## User Story
As a {role/persona},
I want {feature/capability},
So that {benefit/outcome}.

## Objective
{One sentence describing what this feature accomplishes for the user.}

## UX Flow

### Scenario 1: {Happy Path}
1. User does X
2. System responds with Y
3. Result: Z

### Scenario 2: {Error/Edge Case}
1. User does X
2. Condition Y occurs
3. System responds with Z

{Add more scenarios as needed}

## Requirements

### {Requirement Category 1}
1. {Specific requirement}
2. {Specific requirement}

### {Requirement Category 2}
1. {Specific requirement}
2. {Specific requirement}

## Technical Approach
- **{Component 1}:** {Brief description of how}
- **{Component 2}:** {Brief description of how}

## Risk Checklist
*Quick assessment - details go in LLD. Check all that apply and add brief notes.*

- [ ] **Architecture:** Does this change system structure? {Note if yes}
- [ ] **Cost:** Does this add API calls, storage, or compute? {Note if yes}
- [ ] **Legal/PII:** Does this handle personal data or have compliance implications? {Note if yes}
- [ ] **Legal/External Data:** Does this fetch from external sources? {Confirm ToS/robots.txt compliance}
- [ ] **Safety:** Can this cause data loss or system instability? {Note if yes}

## Security Considerations
<!-- Address if applicable: path validation, input sanitization, permissions, data handling -->
- **Path Validation:** {How are user-provided paths validated? Symlink handling?}
- **Input Sanitization:** {How is untrusted input handled?}
- **Permissions:** {What access levels are required?}
- N/A (no security-relevant operations)

## Files to Create/Modify
- `path/to/file.js` — {What changes}
- `path/to/new-file.py` — {Purpose of new file}

## Dependencies
<!-- Use actual issue numbers. #TBD is NOT allowed - create the dependency issue first or mark as "None". -->
- Issue #{N} must be completed first (if applicable)
- None (if no dependencies)

## Out of Scope (Future)
- {Feature X} — deferred to future issue
- {Enhancement Y} — nice-to-have, not MVP

## Open Questions
<!-- BLOCKING: All questions MUST be resolved before filing. If any remain open, the issue is NOT ready. -->
- None (all questions resolved)
<!-- Example format for resolved questions:
- [x] Should we use SQLite or PostgreSQL? → Resolved: SQLite for MVP, PostgreSQL deferred to future issue
-->

## Acceptance Criteria
<!-- REQUIRED: Each criterion MUST be binary (pass/fail). Avoid:
  - "works correctly" → specify exact behavior
  - "handles gracefully" → specify exact output/error message
  - ">80% accuracy" → requires ground truth dataset; use fixture_metadata.json
  - "renders correctly" → specify exact visual elements or screenshot comparison
-->
- [ ] {Testable criterion 1}
- [ ] {Testable criterion 2}
- [ ] {Testable criterion 3}

## Definition of Done

### Implementation
- [ ] Core feature implemented
- [ ] Unit tests written and passing

### Tools
- [ ] Update/create relevant CLI tools in `tools/` (if applicable)
- [ ] Document tool usage

### Documentation
- [ ] Update wiki pages affected by this change
- [ ] Update README.md if user-facing
- [ ] Update relevant ADRs or create new ones
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS (if security-relevant)
- [ ] Run 0810 Privacy Audit - PASS (if privacy-relevant)
- [ ] Run 0817 Wiki Alignment Audit - PASS (if wiki updated)

## Testing Notes
{Any special instructions for how to test, including how to force error states}
```

---

## Tips for Good Issues

1. **User Story:** Follow the "As a {role}, I want {feature}, so that {benefit}" format. Identifies WHO benefits and WHY.
2. **Objective:** One sentence. If you need more, scope is too big.
3. **UX Flow:** Walk through what the user sees, step by step.
4. **Scenarios:** Cover happy path AND at least one error/edge case.
5. **Acceptance Criteria:** Must be binary (pass/fail). Bad: "Works correctly", "handles gracefully", ">80% accuracy". Good: "Returns exit code 0", "Outputs JSON with 'status' field", "Bounding box overlaps ground truth by >50% per fixture_metadata.json".
6. **Open Questions:** Resolve ALL questions before filing. #TBD in Dependencies = not ready.
7. **Out of Scope:** Explicitly state what you're NOT doing to prevent scope creep.
8. **Dependencies:** Use actual issue numbers. Create dependency issues first if needed.
9. **Risk Checklist:** Quick flags for governance. If any box is checked, the LLD must address it in detail.
10. **Security:** Always address path validation and input sanitization for file/CLI operations.

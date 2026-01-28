# 0101 - Template: GitHub Issue (Feature)

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

## Security Considerations
{If applicable: explain why the approach is safe, what permissions are needed, data handling}

## Files to Create/Modify
- `path/to/file.js` — {What changes}
- `path/to/new-file.py` — {Purpose of new file}

## Dependencies
- Issue #{N} must be completed first (if applicable)

## Out of Scope (Future)
- {Feature X} — deferred to future issue
- {Enhancement Y} — nice-to-have, not MVP

## Acceptance Criteria
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
5. **Acceptance Criteria:** Must be testable. "Works correctly" is bad. "Button changes color to green" is good.
6. **Out of Scope:** Explicitly state what you're NOT doing to prevent scope creep.
7. **Dependencies:** Call out blockers so work can be sequenced.

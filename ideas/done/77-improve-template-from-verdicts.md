# Improve Issue Template Based on Gemini Verdict Analysis

Audit all Gemini verdicts to identify patterns in feedback, then revise the issue template so Claude passes review with fewer iterations.

## User Story
As a workflow user,
I want Claude to pass Gemini's Pre-Flight Gate on the first or second try,
So that issue creation completes faster with less back-and-forth.

## Objective
Analyze historical Gemini verdicts to identify common feedback patterns, then revise the issue template (0101) to preemptively address those patterns.

## Requirements

### Audit Phase
1. Collect all verdict files from `docs/audit/active/*/` and `docs/audit/done/*/`
2. Extract feedback from each verdict:
   - Pre-Flight Gate failures
   - Tier 1 (BLOCKING) issues
   - Tier 2 (HIGH PRIORITY) issues
   - Tier 3 (SUGGESTIONS)
3. Categorize feedback by theme (e.g., missing sections, vague requirements, security gaps)
4. Identify the top 5-10 most common issues

### Template Revision Phase
1. Update template sections to address common feedback
2. Add guidance/examples for sections that frequently fail
3. Add prompts/placeholders that prevent common omissions
4. Update the "Tips for Good Issues" section with patterns from Gemini feedback

### Validation Phase
1. Test revised template with 3-5 representative briefs
2. Measure first-pass rate (verdicts that come back APPROVED without revisions)
3. Compare to baseline (current first-pass rate)

## Technical Approach
- **Audit script:** Python script to scan verdict files and extract structured feedback
- **Pattern analysis:** Group feedback by category, count occurrences
- **Report generation:** Create audit report with findings and recommendations
- **Template updates:** Manual edits to `docs/templates/0101-issue-template.md`

## Files to Create/Modify
- `tools/audit_verdicts.py` — Script to analyze verdict files
- `docs/reports/verdict-audit-report.md` — Findings and recommendations
- `docs/templates/0101-issue-template.md` — Revised template with improvements

## Acceptance Criteria
- [ ] Audit script processes all verdict files in audit directories
- [ ] Audit report identifies top 5-10 common feedback patterns
- [ ] Template revised to address identified patterns
- [ ] First-pass rate improves by at least 20% in validation testing
- [ ] Documentation updated with new template guidance

## Out of Scope
- Changing the review prompt (0701c) — focus on improving template only
- Modifying workflow logic — pure template improvement
- Reprocessing old issues — this is for future issues only

## Testing Notes
- Baseline measurement: Run 5 test briefs with current template, measure first-pass rate
- Post-revision measurement: Run same 5 briefs with revised template, compare results
- Success metric: Reduction in average iterations per issue

Labels: enhancement, template, governance, workflow

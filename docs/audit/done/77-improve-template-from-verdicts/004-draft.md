# Improve Issue Template Based on Gemini Verdict Analysis

## User Story
As a workflow user,
I want Claude to pass Gemini's Pre-Flight Gate on the first or second try,
So that issue creation completes faster with less back-and-forth.

## Objective
Analyze historical Gemini verdicts to identify common feedback patterns, then revise the issue template (0101) to preemptively address those patterns.

## UX Flow

### Scenario 1: Running the Verdict Audit
1. User runs `python tools/audit_verdicts.py`
2. Script scans `docs/audit/active/*/` and `docs/audit/done/*/` for verdict files
3. Script extracts and categorizes feedback from each verdict
4. Script generates `docs/reports/verdict-audit-report.md` with findings
5. Result: User has prioritized list of common feedback patterns

### Scenario 2: No Verdict Files Found
1. User runs audit script on fresh repo
2. Script finds no verdict files in expected directories
3. Script returns Exit Code 0 and prints to stdout: "No verdict files found. Expected locations: docs/audit/active/*, docs/audit/done/*"
4. Result: User understands what's needed before audit can run

### Scenario 3: Missing Directory
1. User runs audit script but `docs/audit/` directory does not exist
2. Script returns Exit Code 0 and prints to stdout: "Audit directory not found: docs/audit/. Create directory structure before running audit."
3. Result: User receives clear guidance on prerequisite setup

### Scenario 4: Validating Template Improvements
1. User creates 5 test issues using revised template
2. User runs each through Gemini Pre-Flight Gate
3. User records first-pass rate and failure categories
4. Result: Quantitative measure of template improvement

## Requirements

### Audit Phase
1. Scan all verdict files in `docs/audit/active/*/` and `docs/audit/done/*/`
2. Parse verdict structure to extract:
   - Pre-Flight Gate failures (REJECTED verdicts)
   - Tier 1 (BLOCKING) issues
   - Tier 2 (HIGH PRIORITY) issues  
   - Tier 3 (SUGGESTIONS)
3. Categorize feedback by theme:
   - Missing sections (e.g., no security considerations)
   - Vague requirements (e.g., unclear acceptance criteria)
   - Scope issues (e.g., too broad, missing boundaries)
   - Technical gaps (e.g., no error handling described)
   - Documentation gaps (e.g., missing file inventory updates)
4. Count occurrences and rank by frequency
5. Identify top 5-10 most common issues with examples

### Template Revision Phase
1. Add explicit prompts for commonly-missed sections
2. Include inline examples for sections that frequently fail
3. Add validation checklists within template
4. Expand "Tips for Good Issues" with patterns from Gemini feedback
5. Add "Common Pitfalls" section based on audit findings

### Validation Phase
1. Select 5 representative briefs of varying complexity
2. Create issues using current template (baseline measurement)
3. Create issues using revised template (post-revision measurement)
4. Track iterations needed until APPROVED verdict
5. Calculate and compare first-pass rates

## Technical Approach
- **Audit script (`tools/audit_verdicts.py`):** Python script using pathlib for file discovery, regex for verdict parsing, collections.Counter for frequency analysis
- **Pattern extraction:** Parse markdown structure of verdicts, extract feedback items by tier
- **Categorization:** Keyword-based classification into predefined categories
- **Report generation:** Markdown output with tables, ranked lists, and representative examples
- **Template updates:** Manual edits informed by audit findings

## Security Considerations
- Script only reads files, no write operations except to designated report directory
- No external network calls or data exfiltration
- No sensitive data in verdict files (just feedback text)

## Files to Create/Modify
- `tools/audit_verdicts.py` — New script to analyze verdict files and generate report
- `docs/reports/verdict-audit-report.md` — New report documenting findings and recommendations
- `docs/templates/0101-issue-template.md` — Revised template with improvements based on audit
- `docs/0003-file-inventory.md` — Add new files to inventory

## Dependencies
- None — can begin immediately

## Out of Scope (Future)
- Modifying the Gemini review prompt (0701c) — focus on template improvements only
- Changing workflow logic or automation — pure template enhancement
- Reprocessing historical issues — improvements apply to future issues only
- Automated template validation — manual review sufficient for MVP

## Acceptance Criteria
- [ ] `tools/audit_verdicts.py` successfully processes all verdict files in `docs/audit/active/*/` and `docs/audit/done/*/`
- [ ] Script returns Exit Code 0 and prints "No verdict files found. Expected locations: docs/audit/active/*, docs/audit/done/*" to stdout when directories are empty
- [ ] Script returns Exit Code 0 and prints "Audit directory not found: docs/audit/. Create directory structure before running audit." to stdout when directory is missing
- [ ] Audit report identifies and ranks top 5-10 common feedback patterns
- [ ] Each pattern includes frequency count and at least one example
- [ ] Revised template includes at least 3 new validation checklists addressing top feedback patterns
- [ ] "Tips for Good Issues" section expanded with Gemini-derived guidance
- [ ] Validation testing records 0 failures due to "Missing Section" errors across the 5-issue test set
- [ ] All new files added to file inventory

## Definition of Done

### Implementation
- [ ] Audit script implemented and tested
- [ ] Audit report generated with actionable findings
- [ ] Template revised based on audit recommendations

### Tools
- [ ] `tools/audit_verdicts.py` created with clear usage instructions
- [ ] Script includes `--help` output documenting options

### Documentation
- [ ] Audit report documents methodology and findings
- [ ] Template changes documented in report
- [ ] Validation results recorded with before/after comparison
- [ ] Update relevant wiki pages if template usage guidance changes

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created
- [ ] `docs/reports/verdict-audit-report.md` created (deliverable)

### Verification
- [ ] Run 0817 Wiki Alignment Audit - PASS (if wiki updated)

## Testing Notes
- **Baseline measurement:** Run 5 diverse briefs through current template → Gemini gate, record iterations needed
- **Post-revision measurement:** Run same 5 briefs through revised template → Gemini gate, record iterations
- **Structural success metric:** Revised template includes 3+ new validation checklists
- **Error reduction metric:** 0 failures due to "Missing Section" in validation set
- **Test briefs should include:** Simple feature, complex feature, bug fix, documentation change, security-sensitive change

## Effort Estimate
Medium (T-shirt size)

## Labels
`enhancement` `template` `governance` `workflow` `tooling`

## Original Brief
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
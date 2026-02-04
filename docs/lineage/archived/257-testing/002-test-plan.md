# Extracted Test Plan

## Scenarios

### test_id
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Test Description | Expected Behavior | Status

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Parse APPROVED verdict with resolved questions | Returns VerdictParseResult with resolutions | RED

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Parse APPROVED verdict with Tier 3 suggestions | Returns VerdictParseResult with suggestions | RED

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Parse REJECTED verdict | Returns VerdictParseResult with empty resolutions | RED

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Update draft open questions with resolutions | Checkboxes changed to `- [x]` with resolution text | RED

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Update draft with suggestions (new section) | Reviewer Suggestions section appended | RED

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Handle missing open question in draft | Log warning, continue processing | RED

### test_t070
- Type: e2e
- Requirement: 
- Mock needed: False
- Description: End-to-end: review node updates draft on approval | State contains updated_draft after approval | RED

### test_t080
- Type: e2e
- Requirement: 
- Mock needed: False
- Description: End-to-end: finalize uses updated draft | Final LLD contains resolved questions | RED

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Idempotency: same verdict applied twice | Same result both times | RED

### test_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Parse approved verdict with resolutions | Auto | Verdict with "Open Questions: RESOLVED" | List of ResolvedQuestion | Correct questions and resolution text extracted

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Parse approved verdict with suggestions | Auto | Verdict with "Tier 3" section | List of Tier3Suggestion | All suggestions captured

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Parse rejected verdict | Auto | REJECTED verdict | Empty resolutions list | No resolutions extracted

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Update draft checkboxes | Auto | Draft + resolutions | Updated draft

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Add suggestions section | Auto | Draft + suggestions | Updated draft | New section at end

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Missing question in draft | Auto | Resolution for non-existent question | Warning logged, draft unchanged | No error thrown

### test_070
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Review node integration | Auto | State with APPROVED verdict | State with updated_draft | Draft contains resolutions

### test_080
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Finalize node integration | Auto | State with updated_draft | Final LLD | LLD contains `- [x]`

### test_090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Idempotent update | Auto | Apply same verdict twice | Same draft | No duplicate markers

### test_100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Empty Open Questions section | Auto | Verdict resolves nothing | Unchanged draft | No modifications

### test_110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Malformed verdict | Auto | Verdict missing expected sections | Warning, original draft | Graceful degradation


# Extracted Test Plan

## Scenarios

### test_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Genuine footer approval | Auto | LLD with `<sub>**Gemini Review:** APPROVED...` | is_valid=True, confidence="high" | Returns pass

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Review log approval (final) | Auto | LLD with `\ | APPROVED \ | ` as last row | is_valid=True, confidence="medium" | Returns pass

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: False approval - REVISE then APPROVED status | Auto | Review shows REVISE, status APPROVED | is_valid=False, error_type="forgery" | Returns fail with "FALSE APPROVAL"

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: False approval - PENDING then APPROVED status | Auto | Review shows PENDING, status APPROVED | is_valid=False, error_type="forgery" | Returns fail with "FALSE APPROVAL"

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: No approval evidence | Auto | LLD with no approval markers | is_valid=False, error_type="not_approved" | Returns fail

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Multiple reviews, last is APPROVED | Auto | 3 reviews: REVISE, REVISE, APPROVED | is_valid=True | Returns pass

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Multiple reviews, last is REVISE | Auto | 3 reviews: APPROVED, REVISE | is_valid=False | Returns fail

### test_080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Empty review log | Auto | Review log section exists but empty | is_valid=False, error_type="not_approved" | Returns fail

### test_090
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Gate integration - pass | Auto | Valid LLD path | No exception raised | Workflow continues

### test_100
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Gate integration - fail | Auto | Invalid LLD path | LLDVerificationError raised | Exception has suggestion

### test_110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Path traversal attempt | Auto | Path outside project root | Raises exception before read | Security check blocks

### test_120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Status APPROVED but no Final Status line | Auto | LLD missing Final Status section | is_valid=False, error_type="not_approved" | Returns fail


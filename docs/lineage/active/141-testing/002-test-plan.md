# Extracted Test Plan

## Scenarios

### test_010
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Happy path - LLD archived | integration | State with valid LLD path in active/ | LLD moved to done/, path returned | File exists in done/, not in active/, log contains success message

### test_020
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Happy path - Reports archived | integration | State with report paths in active/ | Reports moved to done/ | Files exist in done/, not in active/, log contains success message

### test_030
- Type: integration
- Requirement: 
- Mock needed: False
- Description: LLD not found | integration | State with non-existent LLD path | Warning logged, None returned | No exception, log contains warning

### test_040
- Type: integration
- Requirement: 
- Mock needed: False
- Description: LLD not in active/ | integration | State with LLD in arbitrary path | Skip archival, None returned | File unchanged, log indicates skip

### test_050
- Type: integration
- Requirement: 
- Mock needed: False
- Description: done/ doesn't exist | integration | Valid LLD, no done/ directory | done/ created, LLD moved | Directory created, file moved

### test_060
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Destination file exists | integration | LLD exists in both active/ and done/ | Append timestamp to new name | No overwrite, both files preserved

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Empty state | unit | State with no paths | Graceful no-op | No exception, empty archival list

### test_080
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Mixed success | integration | Some files exist, some don't | Archive existing, log missing | Partial archival succeeds

### test_090
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Workflow failed - no archival | integration | State with workflow_success=False, valid LLD path | No files moved, skip logged | Files remain in active/, log indicates skip

### test_100
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Exception during file rename | unit | Valid LLD, mock rename to raise OSError | None returned, error logged | No exception propagated, log contains error message

### test_110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Generate summary | unit | Complete TestReportMetadata dict | Markdown summary string | Contains issue number, coverage %, file lists, E2E status

### test_120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: LLD archival fails via wrapper | unit | State with LLD path not in active/ | Skipped list includes LLD path | archived=[], skipped=[lld_path]

### test_130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Impl report archival fails | unit | State with impl_report path not in active/ | Skipped list includes impl report | archived=[], skipped=[impl_path]

### test_140
- Type: integration
- Requirement: 
- Mock needed: False
- Description: E2E evaluation (skip_e2e=False) | integration | State with skip_e2e=False, e2e_output="passed" | E2E passed evaluated from output | finalize completes, e2e logic exercised

### test_150
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Successful workflow with archival | integration | State with workflow_success=True (default), valid LLD | LLD archived, archival printed | archived_files populated, LLD moved to done/


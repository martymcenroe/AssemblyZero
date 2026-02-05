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
- Description: test_extract_removed_class | Extracts class name from diff | RED

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_extract_removed_typeddict | Extracts TypedDict from diff | RED

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_extract_removed_type_alias | Extracts type alias from diff | RED

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_find_usages_in_imports | Finds orphaned import statements | RED

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_find_usages_in_annotations | Finds orphaned type annotations | RED

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_excludes_docs_directory | Does not flag docs references | RED

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_excludes_lineage_directory | Does not flag lineage references | RED

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_full_workflow_pass | Passes when all usages updated | RED

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_full_workflow_fail | Fails when orphaned usages exist | RED

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_error_message_format | Error includes file, line, content | RED

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_timeout_enforcement | Raises TimeoutError when timeout exceeded | RED

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_log_scan_summary | Logs removed type count and files scanned | RED

### test_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Extract removed class | Auto | Diff with `-class Foo:` | `[("Foo", "file.py")]` | Correct extraction

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Extract TypedDict | Auto | Diff with `-Bar = TypedDict` | `[("Bar", "file.py")]` | Correct extraction

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Extract type alias | Auto | Diff with `-MyType = Union[...]` | `[("MyType", "file.py")]` | Correct extraction

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Find import usages | Auto | Codebase with `from x import Foo` | Usage detected | Found with location

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Find annotation usages | Auto | Codebase with `def f(x: Foo)` | Usage detected | Found with location

### test_060
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Exclude docs | Auto | Usage in `docs/api.md` | Not reported | No false positive

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Exclude lineage | Auto | Usage in `lineage/old.py` | Not reported | No false positive

### test_080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Clean rename passes | Auto | All usages updated | `passed=True` | Workflow continues

### test_090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Orphaned usage fails | Auto | Missed usage exists | `passed=False` | Workflow stops

### test_100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Error message quality | Auto | One orphaned usage | Message has file:line | Actionable output

### test_110
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Timeout enforcement | Auto | Mock slow grep (>10s) | TimeoutError raised | Fail-safe works

### test_120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Observability logging | Auto | Normal execution | Log contains counts | Debugging enabled


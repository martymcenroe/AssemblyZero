# Extracted Test Plan

## Scenarios

### test_id
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Tests Function | File | Input | Expected Output

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_testing_workflow()` graph structure | `test_cleanup.py` | Compiled graph | N9_cleanup node exists; N9→END edge exists

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `cleanup()` | `test_cleanup.py` | State with merged PR, active lineage | pr_merged=True, summary in done/, worktree removed

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `cleanup()` | `test_cleanup.py` | State with open PR, active lineage | pr_merged=False, summary in active/, lineage preserved

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `cleanup()` | `test_cleanup.py` | State without pr_url | cleanup_skipped_reason="No PR URL in state"

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `cleanup()` | `test_cleanup.py` | State with no active dir | learning_summary_path=""

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `cleanup()` | `test_cleanup.py` | remove_worktree raises CalledProcessError | No exception propagated

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `check_pr_merged()` | `test_cleanup_helpers.py` | gh returns "MERGED" | True

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `check_pr_merged()` | `test_cleanup_helpers.py` | gh returns "OPEN" | False

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `check_pr_merged()` | `test_cleanup_helpers.py` | Empty/malformed URL | ValueError

### test_t095
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `check_pr_merged()` | `test_cleanup_helpers.py` | subprocess.TimeoutExpired | TimeoutExpired raised

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `remove_worktree()` | `test_cleanup_helpers.py` | Existing path, git succeeds | True

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `remove_worktree()` | `test_cleanup_helpers.py` | Nonexistent path | False

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `get_worktree_branch()` | `test_cleanup_helpers.py` | Porcelain output with match | "issue-180-cleanup"

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `get_worktree_branch()` | `test_cleanup_helpers.py` | Porcelain output without match | None

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `delete_local_branch()` | `test_cleanup_helpers.py` | Branch exists | True

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `delete_local_branch()` | `test_cleanup_helpers.py` | Branch "not found" in stderr | False

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `archive_lineage()` | `test_cleanup_helpers.py` | active exists, done doesn't | Done path, active removed

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `archive_lineage()` | `test_cleanup_helpers.py` | active doesn't exist | None

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `archive_lineage()` | `test_cleanup_helpers.py` | done already exists | Timestamped path

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_iteration_data()` | `test_cleanup_helpers.py` | Dir with green-phase file | [IterationSnapshot(coverage=98.5)]

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_iteration_data()` | `test_cleanup_helpers.py` | Empty dir | []

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_stall()` | `test_cleanup_helpers.py` | [85.0, 85.0, 88.0] | (True, 2)

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_stall()` | `test_cleanup_helpers.py` | [80.0, 85.0, 90.0, 95.0] | (False, None)

### test_t230
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_learning_summary()` | `test_cleanup_helpers.py` | Dir with fixtures | LearningSummaryData fully populated

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `render_learning_summary()` | `test_cleanup_helpers.py` | LearningSummaryData | Markdown with all sections

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `render_learning_summary()` | `test_cleanup_helpers.py` | Data with stall_detected=True | "Stall detected: Yes" in output

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `write_learning_summary()` | `test_cleanup_helpers.py` | Dir + content string | File exists at path

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `cleanup()` | `test_cleanup.py` | TimeoutExpired + CalledProcessError | State returned, no exception

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `route_after_document()` | `test_cleanup.py` | state with issue_number=180 | "N9_cleanup"

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `route_after_document()` | `test_cleanup.py` | state without issue_number | "end"

### test_t300
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `cleanup()` | `test_cleanup.py` | Full state | Result has pr_merged (bool), learning_summary_path (str), cleanup_skipped_reason (str)

### test_t310
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `cleanup()` | `test_cleanup.py` | PR not merged + active dir | "/active/" in learning_summary_path

### test_t320
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `cleanup()` | `test_cleanup.py` | PR merged + active dir | "/done/" in learning_summary_path


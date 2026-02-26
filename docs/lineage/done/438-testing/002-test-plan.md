# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_lld_workflow_mock_completes_successfully` | Mock LLD input + mock config | `exit_status="success"`, no error_message, nodes_visited > 0

### test_t020
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_lld_workflow_mock_no_api_credentials_required` | Same + all API env vars stripped | `exit_status="success"`, `api_calls_made=0`, tracker empty

### test_t030
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_lld_workflow_mock_ci_compatible` | Same as T010 | `duration_seconds < 60`, `exit_status="success"`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_lld_workflow_mock_visits_all_nodes` | Same as T010 | All EXPECTED_NODES in visited set, none missing

### test_t050
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_lld_workflow_mock_state_transitions` | Same as T010 | First node is entry, last is terminal, no self-loops

### test_t060
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_lld_workflow_mock_produces_artifacts` | Same as T010 | Non-empty lld_content, non-empty review_verdict

### test_t070
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_lld_workflow_mock_idempotent_rerun` | Same input, two fresh workspaces | `nodes_visited_1 == nodes_visited_2`, `filtered_state_1 == filtered_state_2`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_lld_workflow_mock_checkpoint_created` | Same as T010 | checkpoints.db exists, ≥1 row in checkpoint tables

### test_t090
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_lld_workflow_mock_workspace_isolation` | Same as T010 + filesystem snapshots | No new files in cwd/docs or cwd/data; all artifacts under tmp_path


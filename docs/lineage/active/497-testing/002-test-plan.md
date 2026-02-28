# Extracted Test Plan

## Scenarios

### test_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_feedback_block()` | 5 large verdicts (~1500 tokens each), budget=4000 | `total_tokens <= 4000`

### test_015
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_feedback_block()` | 5 large verdicts, budget=2000 | `total_tokens <= 2000`

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_feedback_block()` | `[v1]` (single JSON verdict fixture) | `latest_verdict_full == v1`, `prior_summaries == []`

### test_025
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_feedback_block()` | `[v1, v2, v3]` (3 JSON verdict fixtures) | `latest_verdict_full == v3`

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_feedback_block()` | `[v1, v2, v3]` (3 JSON verdict fixtures) | 2 VerdictSummary in `prior_summaries`

### test_035
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `format_summary_line()` | `VerdictSummary(iter=2, BLOCKED, 2 issues, 1 persist)` | Contains `"Iteration 2"`, `"BLOCKED"`, `"2 issues"`, persist desc

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `identify_persisting_issues()` | `current=["No rollback plan..."]`, `prior=["Missing error...", "No rollback plan..."]` | `(["No rollback plan..."], [])`

### test_045
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `identify_persisting_issues()` | `current=["Missing rollback plan..."]`, `prior=["No rollback plan..."]` | Persisting detected (similarity > 0.8)

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `identify_persisting_issues()` | `current=["Test coverage..."]`, `prior=["Missing error..."]` | `([], ["Test coverage..."])`

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_feedback_block()` | `abs(t5 - t2) / t2 < 0.20`

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_feedback_block()` | `[]` | `FeedbackWindow(latest="", prior=[], tokens=0, truncated=False)`

### test_075
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `render_feedback_markdown()` | Empty `FeedbackWindow` | `""`

### test_080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_blocking_issues()` | JSON verdict fixture string (3 issues) | `["Missing error handling...", "No rollback plan...", "Security section..."]`

### test_085
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_blocking_issues()` | Text verdict with `**[BLOCKING]**` lines | `["Missing error handling...", "No rollback plan...", "Security section..."]`

### test_090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_feedback_block()` | `[text_verdict, json_verdict]` | Valid `FeedbackWindow`, `prior_summaries[0].verdict == "BLOCKED"`

### test_095
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_blocking_issues()` | `'{invalid json\n- **[BLOCKING]** Fallback issue found'` | `["Fallback issue found"]`, `logger.warning` captured

### test_100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_feedback_block()` | 5 large verdicts, tight budget (2000) | `was_truncated=True`, counter incremented, warning logged

### test_110
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `generate_draft` import chain | Module-level mock patching | `build_feedback_block` and `render_feedback_markdown` importable and patchable

### test_120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `render_feedback_markdown()` | Single-verdict `FeedbackWindow` | Contains `"## Review Feedback"`, not `"Prior Review Summary"`


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
- Description: test_draft_with_questions_proceeds_to_review | Draft not blocked pre-review | RED

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_gemini_answers_questions | Questions resolved in verdict | RED

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_unanswered_triggers_loop | Loop back to N3 with followup | RED

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_human_required_escalates | Goes to human gate | RED

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_max_iterations_respected | Terminates after limit | RED

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_all_answered_proceeds_to_finalize | N5 reached when resolved | RED

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: test_prompt_includes_question_instructions | 0702c has new section | RED

### test_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Draft with open questions proceeds | Auto | Draft with 3 unchecked questions | Reaches N3_review | No BLOCKED status pre-review

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Gemini answers questions | Auto | Review with question instructions | All questions [x] | Verdict contains resolutions

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Unanswered triggers loop | Auto | Verdict approves but questions unchecked | Loop to N3 | Followup prompt sent

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: HUMAN REQUIRED escalates | Auto | Verdict with HUMAN REQUIRED | Goes to N4 | Human gate invoked

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Max iterations respected | Auto | 20 loops without resolution | Terminates | Exit with current state

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Resolved proceeds to finalize | Auto | All questions answered | Reaches N5 | APPROVED status

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Prompt updated | Auto | Load 0702c | Contains question instructions | Regex match


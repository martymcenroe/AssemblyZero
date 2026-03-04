# Test Plan Review Prompt

You are reviewing a test plan extracted from a Low-Level Design (LLD) document.
Your goal is to ensure the test plan provides adequate coverage and uses real, executable tests.

## Review Criteria

### 1. Coverage Analysis (CRITICAL)
- [ ] 100% of requirements have corresponding tests (ADR 0207)
- [ ] Each requirement maps to at least one test scenario
- [ ] Edge cases are covered (empty inputs, error conditions, boundaries)

### 2. Test Reality Check (CRITICAL)
- [ ] Tests are executable code, not human manual steps
- [ ] No test delegates to "manual verification"
- [ ] No test says "verify by inspection" or similar
- [ ] Each test has clear assertions

### 3. Test Type Appropriateness
- [ ] Unit tests are truly isolated (mock dependencies)
- [ ] Integration tests test real component interactions
- [ ] E2E tests cover critical user paths

### 4. Mock Strategy
- [ ] External dependencies (APIs, DB) are mocked appropriately
- [ ] Mocks are realistic and don't hide bugs

## Output Format

Provide your verdict in this exact format:

```
## Coverage Analysis
- Requirements covered: X/Y (Z%)
- Missing coverage: [list any gaps]

## Test Reality Issues
- [list any tests that aren't real executable tests]

## Verdict
[ ] **APPROVED** - Test plan is ready for implementation
[ ] **BLOCKED** - Test plan needs revision

Mark EXACTLY ONE option with [X].

## Required Changes (if BLOCKED)
1. [specific change needed]
2. [specific change needed]
```


---

# Test Plan for Issue #283

## Requirements to Cover

- REQ-T020: ConversationActionBar
- REQ-T030: ConversationFields
- REQ-T040: ComposePanel
- REQ-T050: AuditResultPanel
- REQ-T060: AuditHistoryPanel
- REQ-T070: MessageBubble
- REQ-T080: useDrawerAction
- REQ-T090: useDrawerAction
- REQ-T100: useConversationMutations
- REQ-T110: useConversationMutations
- REQ-T120: useConversationMutations
- REQ-T130: useConversationMutations
- REQ-T250: ConversationActionBar
- REQ-T260: ConversationActionBar
- REQ-T270: ConversationFields
- REQ-T280: ComposePanel
- REQ-T290: AuditResultPanel
- REQ-T300: MessageBubble
- REQ-T310: useAdminAction
- REQ-T320: useAdminAction
- REQ-T330: ConversationActionBar.handleDelete
- REQ-T340: ConversationActionBar.handleDelete
- REQ-T350: ConversationActionBar
- REQ-T360: ConversationActionBar

## Detected Test Types

- browser
- e2e
- integration
- mobile
- performance
- security
- terminal
- unit

## Required Tools

- appium
- bandit
- click.testing
- detox
- docker-compose
- locust
- pexpect
- playwright
- pytest
- pytest-benchmark
- safety
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Performance Tests:** Test against representative data volumes
**Security Tests:** Never use real credentials, test edge cases thoroughly
**Terminal/CLI Tests:** Use CliRunner or capture stdout/stderr
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `ConversationActionBar` | `isOwner=true, conversation=mockConv` | Poke, Audit, Snooze, Delete buttons visible
- **Mock needed:** True
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `ConversationFields` | `conversation=mockConv, isOwner=true` | Sender, Subject, State, Labels rendered
- **Mock needed:** True
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `ComposePanel` | `isOwner=true` | Subject, body, attach, send visible
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `AuditResultPanel` | `audit=mockAudit, disabled=false` | Approve+Send, Load Draft, Approve, Reject visible
- **Mock needed:** True
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `AuditHistoryPanel` | `entries=[mockEntry]` | Collapsible entry with expand toggle
- **Mock needed:** True
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `MessageBubble` | `message=outbound, canUserRate=true` | Direction label + 5 rating emojis
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `useDrawerAction` | `mutationFn=resolves, onClose=fn` | onClose called, toast.success called
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `useDrawerAction` | `mutationFn=rejects` | toast.error called, onClose NOT called
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `useConversationMutations` | `convId=42` | Object with all 15 mutation keys
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `useConversationMutations` | `addLabelMut` | Does NOT call onClose on success
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `useConversationMutations` | `rateMut` | Does NOT call onClose on success
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `useConversationMutations` | `removeLabelMut` | Does NOT call onClose on success
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `ConversationActionBar` | `pokeMut.isPending=true` | Poke button disabled, shows "Poking..."
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `ConversationActionBar` | `isOwner=false` | Only Back visible
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `ConversationFields` | `is_human_managed=true` | Shows "Release to AI"
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `ComposePanel` | `isOwner=false` | Returns null
- **Mock needed:** False
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `AuditResultPanel` | `disabled=true` | All buttons disabled
- **Mock needed:** False
- **Assertions:** 

### test_t300
- **Type:** unit
- **Requirement:** 
- **Description:** `MessageBubble` | `canUserRate=false` | No rating buttons
- **Mock needed:** False
- **Assertions:** 

### test_t310
- **Type:** unit
- **Requirement:** 
- **Description:** `useAdminAction` | `mutationFn=resolves` | Invalidates attention-queue, audit-preview
- **Mock needed:** False
- **Assertions:** 

### test_t320
- **Type:** unit
- **Requirement:** 
- **Description:** `useAdminAction` | Rendered in hook | Returns mutation with mutate function
- **Mock needed:** False
- **Assertions:** 

### test_t330
- **Type:** unit
- **Requirement:** 
- **Description:** `ConversationActionBar.handleDelete` | `confirm=false` | `deleteMut.mutate` NOT called
- **Mock needed:** False
- **Assertions:** 

### test_t340
- **Type:** unit
- **Requirement:** 
- **Description:** `ConversationActionBar.handleDelete` | `confirm=true` | `deleteMut.mutate` called once
- **Mock needed:** False
- **Assertions:** 

### test_t350
- **Type:** unit
- **Requirement:** 
- **Description:** `ConversationActionBar` | `attention_snoozed=true` | Shows "Wake" label
- **Mock needed:** False
- **Assertions:** 

### test_t360
- **Type:** unit
- **Requirement:** 
- **Description:** `ConversationActionBar` | `is_human_managed=true` | Audit button disabled
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function/Component | Input | Expected Output |
|---------|-------------------------|-------|-----------------|
| T020 | `ConversationActionBar` | `isOwner=true, conversation=mockConv` | Poke, Audit, Snooze, Delete buttons visible |
| T030 | `ConversationFields` | `conversation=mockConv, isOwner=true` | Sender, Subject, State, Labels rendered |
| T040 | `ComposePanel` | `isOwner=true` | Subject, body, attach, send visible |
| T050 | `AuditResultPanel` | `audit=mockAudit, disabled=false` | Approve+Send, Load Draft, Approve, Reject visible |
| T060 | `AuditHistoryPanel` | `entries=[mockEntry]` | Collapsible entry with expand toggle |
| T070 | `MessageBubble` | `message=outbound, canUserRate=true` | Direction label + 5 rating emojis |
| T080 | `useDrawerAction` | `mutationFn=resolves, onClose=fn` | onClose called, toast.success called |
| T090 | `useDrawerAction` | `mutationFn=rejects` | toast.error called, onClose NOT called |
| T100 | `useConversationMutations` | `convId=42` | Object with all 15 mutation keys |
| T110 | `useConversationMutations` | `addLabelMut` | Does NOT call onClose on success |
| T120 | `useConversationMutations` | `rateMut` | Does NOT call onClose on success |
| T130 | `useConversationMutations` | `removeLabelMut` | Does NOT call onClose on success |
| T250 | `ConversationActionBar` | `pokeMut.isPending=true` | Poke button disabled, shows "Poking..." |
| T260 | `ConversationActionBar` | `isOwner=false` | Only Back visible |
| T270 | `ConversationFields` | `is_human_managed=true` | Shows "Release to AI" |
| T280 | `ComposePanel` | `isOwner=false` | Returns null |
| T290 | `AuditResultPanel` | `disabled=true` | All buttons disabled |
| T300 | `MessageBubble` | `canUserRate=false` | No rating buttons |
| T310 | `useAdminAction` | `mutationFn=resolves` | Invalidates attention-queue, audit-preview |
| T320 | `useAdminAction` | Rendered in hook | Returns mutation with mutate function |
| T330 | `ConversationActionBar.handleDelete` | `confirm=false` | `deleteMut.mutate` NOT called |
| T340 | `ConversationActionBar.handleDelete` | `confirm=true` | `deleteMut.mutate` called once |
| T350 | `ConversationActionBar` | `attention_snoozed=true` | Shows "Wake" label |
| T360 | `ConversationActionBar` | `is_human_managed=true` | Audit button disabled |

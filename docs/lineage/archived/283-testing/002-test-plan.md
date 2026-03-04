# Extracted Test Plan

## Scenarios

### test_t020
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `ConversationActionBar` | `isOwner=true, conversation=mockConv` | Poke, Audit, Snooze, Delete buttons visible

### test_t030
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `ConversationFields` | `conversation=mockConv, isOwner=true` | Sender, Subject, State, Labels rendered

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `ComposePanel` | `isOwner=true` | Subject, body, attach, send visible

### test_t050
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `AuditResultPanel` | `audit=mockAudit, disabled=false` | Approve+Send, Load Draft, Approve, Reject visible

### test_t060
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `AuditHistoryPanel` | `entries=[mockEntry]` | Collapsible entry with expand toggle

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `MessageBubble` | `message=outbound, canUserRate=true` | Direction label + 5 rating emojis

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `useDrawerAction` | `mutationFn=resolves, onClose=fn` | onClose called, toast.success called

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `useDrawerAction` | `mutationFn=rejects` | toast.error called, onClose NOT called

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `useConversationMutations` | `convId=42` | Object with all 15 mutation keys

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `useConversationMutations` | `addLabelMut` | Does NOT call onClose on success

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `useConversationMutations` | `rateMut` | Does NOT call onClose on success

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `useConversationMutations` | `removeLabelMut` | Does NOT call onClose on success

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `ConversationActionBar` | `pokeMut.isPending=true` | Poke button disabled, shows "Poking..."

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `ConversationActionBar` | `isOwner=false` | Only Back visible

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `ConversationFields` | `is_human_managed=true` | Shows "Release to AI"

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `ComposePanel` | `isOwner=false` | Returns null

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `AuditResultPanel` | `disabled=true` | All buttons disabled

### test_t300
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `MessageBubble` | `canUserRate=false` | No rating buttons

### test_t310
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `useAdminAction` | `mutationFn=resolves` | Invalidates attention-queue, audit-preview

### test_t320
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `useAdminAction` | Rendered in hook | Returns mutation with mutate function

### test_t330
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `ConversationActionBar.handleDelete` | `confirm=false` | `deleteMut.mutate` NOT called

### test_t340
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `ConversationActionBar.handleDelete` | `confirm=true` | `deleteMut.mutate` called once

### test_t350
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `ConversationActionBar` | `attention_snoozed=true` | Shows "Wake" label

### test_t360
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `ConversationActionBar` | `is_human_managed=true` | Audit button disabled


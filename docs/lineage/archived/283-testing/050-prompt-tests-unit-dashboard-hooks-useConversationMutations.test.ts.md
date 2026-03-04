# Implementation Request: tests/unit/dashboard/hooks/useConversationMutations.test.ts

## Task

Write the complete contents of `tests/unit/dashboard/hooks/useConversationMutations.test.ts`.

Change type: Add
Description: Hook unit tests

## LLD Specification

# Implementation Spec: Refactor — Extract ConversationDetail.tsx into Focused Components

| Field | Value |
|-------|-------|
| Issue | #283 |
| LLD | `docs/lld/active/283-refactor-conversation-detail.md` |
| Generated | 2026-03-04 |
| Status | DRAFT |

## 1. Overview

Decompose the 1132-line `ConversationDetail.tsx` god component into 6 focused child components and 3 shared hooks, reducing the orchestrator to ~200 lines while improving testability, readability, and mutation consistency.

**Objective:** Extract inline sub-components and mutations from ConversationDetail.tsx into separate files with typed props and centralized mutation handling.

**Success Criteria:**
- ConversationDetail.tsx ≤250 lines, serving only as orchestrator
- All 6 child components extracted with explicit typed props
- All 13 mutations use `useDrawerAction` for consistent behavior
- All 14 existing E2E tests pass without modification

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `dashboard/src/components/shared/conversation/types.ts` | Add | Shared TypeScript interfaces |
| 2 | `dashboard/src/components/shared/conversation/index.ts` | Add | Barrel exports |
| 3 | `dashboard/src/lib/hooks/useDrawerAction.ts` | Add | Mutation wrapper with auto-close |
| 4 | `dashboard/src/lib/hooks/useAdminAction.ts` | Add | Admin action mutation wrapper |
| 5 | `dashboard/src/lib/hooks/useConversationMutations.ts` | Add | All 13 mutations centralized |
| 6 | `dashboard/src/lib/hooks/index.ts` | Add | Barrel exports for hooks |
| 7 | `dashboard/src/components/shared/conversation/MessageBubble.tsx` | Add | Message rendering (leaf) |
| 8 | `dashboard/src/components/shared/conversation/AuditHistoryPanel.tsx` | Add | Audit history (leaf) |
| 9 | `dashboard/src/components/shared/conversation/ConversationActionBar.tsx` | Add | Action bar with delete confirm |
| 10 | `dashboard/src/components/shared/conversation/ConversationFields.tsx` | Add | Metadata fields |
| 11 | `dashboard/src/components/shared/conversation/ComposePanel.tsx` | Add | Email compose form |
| 12 | `dashboard/src/components/shared/conversation/AuditResultPanel.tsx` | Add | Audit result actions |
| 13 | `dashboard/src/components/shared/ConversationDetail.tsx` | Modify | Strip to ~200-line orchestrator |
| 14 | `tests/unit/dashboard/fixtures.ts` | Add | Shared test fixtures |
| 15 | `tests/unit/dashboard/hooks/useDrawerAction.test.ts` | Add | Hook unit tests |
| 16 | `tests/unit/dashboard/hooks/useAdminAction.test.ts` | Add | Hook unit tests |
| 17 | `tests/unit/dashboard/hooks/useConversationMutations.test.ts` | Add | Hook unit tests |
| 18 | `tests/unit/dashboard/conversation/ConversationActionBar.test.tsx` | Add | Component tests |
| 19 | `tests/unit/dashboard/conversation/ConversationFields.test.tsx` | Add | Component tests |
| 20 | `tests/unit/dashboard/conversation/ComposePanel.test.tsx` | Add | Component tests |
| 21 | `tests/unit/dashboard/conversation/AuditResultPanel.test.tsx` | Add | Component tests |
| 22 | `tests/unit/dashboard/conversation/AuditHistoryPanel.test.tsx` | Add | Component tests |
| 23 | `tests/unit/dashboard/conversation/MessageBubble.test.tsx` | Add | Component tests |
| 24 | `tests/e2e/dashboard/conversation-detail.spec.ts` | Verify | No changes — confirm all 14 tests pass |

**Implementation Order Rationale:** Types first (no dependencies), then hooks (depend on types only), then leaf components (no mutation deps), then mutation-consuming components, then orchestrator rewrite (depends on everything). Tests last since they test the implementations.

## 3. Current State (for Modify/Delete files)

### 3.1 `dashboard/src/components/shared/ConversationDetail.tsx`

**Relevant excerpt — Imports (lines 1-20):**

```tsx
import { useState, useRef, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  fetchConversation,
  fetchLabels,
  fetchRatings,
  deleteConversation,
  sendMessage,
  addLabel,
  removeLabel,
  setTakeover,
  checkStar,
  submitRating,
  triggerAudit,
  approveAudit,
  approveAndSendAudit,
  rejectAudit,
  bulkPoke,
  fetchResumePDF,
  fetchAuditHistory,
  clearGithubUsername,
  addSkipWord,
  patchConversationState,
  snoozeConversation,
} from "@/api/client"
import type { Message, Rating, AuditDiagnosis, AuditLogEntry } from "@/api/types"
import { useAuth } from "@/providers/AuthProvider"
import { canWrite, canRate } from "@/lib/roles"
import { toCTFull, todayCT, formatBytes } from "@/lib/utils"
import { RATING_EMOJIS } from "@/lib/constants"
import { StateBadge, HumanManagedBadge } from "@/components/shared/StateBadge"
import { LabelChips } from "@/components/shared/LabelChips"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"
import { ArrowLeft, Trash2 } from "lucide-react"
```

**Relevant excerpt — Component props and setup (lines ~38-67):**

```tsx
interface ConversationDetailProps {
  conversationId: number
  onBack?: () => void
  onDeleted?: () => void
  onClose?: () => void
}

export function ConversationDetail({ conversationId, onBack, onDeleted, onClose }: ConversationDetailProps) {
  const convId = conversationId
  const { role } = useAuth()
  const isOwner = canWrite(role)
  const queryClient = useQueryClient()

  const [showFullHistory, setShowFullHistory] = useState(true)
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [starUsername, setStarUsername] = useState("")
  const [pendingFiles, setPendingFiles] = useState<Array<{ filename: string; data: string }>>([])
  const [pendingAudit, setPendingAudit] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
```

**Relevant excerpt — Queries (lines ~68-96):**

```tsx
  const { data: conv, isLoading, error } = useQuery({
    queryKey: ["conversation", convId],
    queryFn: () => fetchConversation(convId),
  })

  const { data: labels } = useQuery({
    queryKey: ["labels", convId],
    queryFn: () => fetchLabels(convId),
  })

  const { data: ratings } = useQuery({
    queryKey: ["ratings", convId],
    queryFn: () => fetchRatings(convId),
    enabled: canRate(role),
  })

  const { data: auditHistory } = useQuery({
    queryKey: ["audit-history", convId],
    queryFn: () => fetchAuditHistory(convId),
    enabled: isOwner,
  })

  const ratingsMap: Record<number, Rating> = {}
  if (ratings) {
    for (const r of ratings) ratingsMap[r.message_id] = r
  }
```

**Relevant excerpt — Delete mutation (lines ~98-105):**

```tsx
  const deleteMut = useMutation({
    mutationFn: () => deleteConversation(convId),
    onSuccess: () => {
      toast.success(`Conversation #${convId} deleted`)
      onDeleted?.()
    },
  })
```

**Relevant excerpt — Send mutation (lines ~107-124):**

```tsx
  const sendMut = useMutation({
    mutationFn: (data: { subject: string; body: string; attachments: typeof pendingFiles }) =>
      sendMessage(convId, data),
    onSuccess: (res) => {
      if (res.ok) {
        toast.success(`Email sent via ${res.sendVia}`)
        setBody("")
        setPendingFiles([])
        queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
        queryClient.invalidateQueries({ queryKey: ["attention-queue"] })
      } else {
        toast.error(`Send failed: ${res.error || "unknown"}`)
      }
    },
    onError: (err: Error) => toast.error(`Send failed: ${err.message}`),
  })
```

**Relevant excerpt — Label mutations (lines ~126-137):**

```tsx
  const addLabelMut = useMutation({
    mutationFn: (label: string) => addLabel(convId, label),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["labels", convId] }),
  })

  const removeLabelMut = useMutation({
    mutationFn: (label: string) => removeLabel(convId, label),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["labels", convId] }),
  })
```

**Relevant excerpt — Takeover, star, clearUsername mutations (lines ~139-175):**

```tsx
  const takeoverMut = useMutation({
    mutationFn: (managed: boolean) => setTakeover(convId, managed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
      toast.success("Management updated")
    },
  })

  const starMut = useMutation({
    mutationFn: (username: string) => checkStar(convId, username),
    onSuccess: (res) => {
      if (res.starred) {
        toast.success(`${starUsername} starred AssemblyZero!`)
      } else {
        toast(`${starUsername} has NOT starred yet — username saved`)
      }
      queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
    },
  })

  const clearUsernameMut = useMutation({
    mutationFn: async (username: string) => {
      await clearGithubUsername(convId)
      await addSkipWord(username)
    },
    onSuccess: () => {
      toast.success("Username cleared and added to skip list")
      queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
    },
    onError: (err: Error) => toast.error(`Clear failed: ${err.message}`),
  })
```

**Relevant excerpt — Rate, poke, audit mutations (lines ~177-228):**

```tsx
  const rateMut = useMutation({
    mutationFn: submitRating,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ratings", convId] }),
  })

  const pokeMut = useMutation({
    mutationFn: () => bulkPoke([convId]),
    onSuccess: (res) => {
      if (res.success > 0) {
        toast.success("Poke sent")
        queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
      } else {
        toast.error(`Poke failed: ${res.results?.[0]?.error || "unknown"}`)
      }
    },
    onError: (err: Error) => toast.error(`Poke error: ${err.message}`),
  })

  const auditMut = useMutation({
    mutationFn: () => triggerAudit([convId]),
    onMutate: () => {
      setPendingAudit(true)
    },
    onSuccess: (res) => {
      if (res.success > 0) {
        toast.success("Audit queued — results appear shortly")
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
        }, 500)
        const poll = setInterval(() => {
          queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
        }, 3000)
        setTimeout(() => clearInterval(poll), 30000)
      } else {
        setPendingAudit(false)
        toast.error(`Audit failed: ${res.results?.[0]?.error || "unknown"}`)
      }
    },
    onError: (err: Error) => {
      setPendingAudit(false)
      toast.error(`Audit error: ${err.message}`)
    },
  })
```

**Relevant excerpt — Snooze, approve, reject mutations (lines ~230-258):**

```tsx
  const snoozeMut = useMutation({
    mutationFn: () => snoozeConversation(convId, !conv!.attention_snoozed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
      queryClient.invalidateQueries({ queryKey: ["attention-queue"] })
      toast.success(conv!.attention_snoozed ? "Unsnoozed" : "Snoozed — will resurface if they write back")
    },
  })

  const approveMut = useMutation({
    mutationFn: () => approveAudit(convId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
      queryClient.invalidateQueries({ queryKey: ["audit-preview"] })
      toast.success("Audit approved")
    },
  })

  const rejectMut = useMutation({
    mutationFn: () => rejectAudit(convId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
      queryClient.invalidateQueries({ queryKey: ["audit-preview"] })
      toast.success("Audit rejected")
    },
  })
```

**Relevant excerpt — pendingAudit effect and early returns (lines ~260-275):**

```tsx
  // Reset pendingAudit only when audit_result appears (audit completed)
  useEffect(() => {
    if (pendingAudit && conv?.audit_result) {
      setPendingAudit(false)
    }
  }, [conv?.audit_result, pendingAudit])

  if (isLoading) return <div className="py-10 text-center text-muted-foreground">Loading...</div>
  if (error) return <div className="py-10 text-center text-destructive">Error: {error.message}</div>
  if (!conv) return null

  // Initialize subject for compose
  if (!subject && conv.subject) {
    setSubject(`Re: ${conv.subject}`)
  }
```

**Relevant excerpt — Message processing (lines ~277-300):**

```tsx
  const allMessages = conv.messages || []

  // Derive resume status from actual messages
  const resumeSentMsg = allMessages.find((m) => m.direction === "outbound" && m.has_resume)

  const lastInitAt = conv.last_init_at
  let hiddenCount = 0
  const visibleMessages: Array<{ msg: Message; isPreInit: boolean }> = []

  for (const msg of allMessages) {
    const isPreInit = !!(lastInitAt && msg.created_at < lastInitAt)
    if (isPreInit && !showFullHistory) {
      hiddenCount++
    } else {
      visibleMessages.push({ msg, isPreInit })
    }
  }

  // Newest first (like email)
  visibleMessages.reverse()
```

**Relevant excerpt — File change handler (lines ~302-316):**

```tsx
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const newPending: typeof pendingFiles = []
    files.forEach((file) => {
      const reader = new FileReader()
      reader.onload = (ev) => {
        const result = ev.target?.result as string
        newPending.push({ filename: file.name, data: result.split(",")[1] })
        if (newPending.length === files.length) {
          setPendingFiles(newPending)
        }
      }
      reader.readAsDataURL(file)
    })
  }
```

**Relevant excerpt — Render start: action bar section (lines ~318-380):**

```tsx
  return (
    <div>
      {/* Detail panel */}
      <Card className="mb-4">
        <CardContent className="p-5">
          <div className="mb-4 flex items-center gap-2">
            {onBack && (
              <Button variant="outline" size="sm" onClick={onBack}>
                <ArrowLeft className="mr-1 h-4 w-4" /> Back
              </Button>
            )}
            {isOwner && (
              <Button
                size="sm"
                variant="outline"
                className="border-yellow-500 text-yellow-500"
                onClick={() => pokeMut.mutate()}
                disabled={pokeMut.isPending}
                title="Re-init + generate AI response + send email"
              >
                {pokeMut.isPending ? "Poking..." : "Poke"}
              </Button>
            )}
            {isOwner && (
              <Button
```

**What changes:** The entire component body is replaced. The imports are reduced to only what the orchestrator needs. All 13 inline mutations are removed (moved to `useConversationMutations`). All inline render blocks for action bar, fields, compose, audit result, audit history, and message rendering are replaced with child component calls. Queries remain in the orchestrator. Local state for `pendingAudit`, `showFullHistory`, `subject`, `body`, `pendingFiles`, `starUsername` remain in the orchestrator (they coordinate across child components). The `handleFileChange` handler remains as it's used by ComposePanel's file input ref.

### 3.2 `tests/e2e/dashboard/conversation-detail.spec.ts`

**What changes:** No code changes. This file is only verified — all 14 existing tests must pass after the refactor. The file uses DOM selectors (roles, text content, CSS classes) that the refactor preserves.

## 4. Data Structures

### 4.1 ConversationDetailProps (existing, unchanged)

**Definition:**

```typescript
interface ConversationDetailProps {
  conversationId: number
  onBack?: () => void
  onDeleted?: () => void
  onClose?: () => void
}
```

**Concrete Example:**

```json
{
  "conversationId": 42,
  "onBack": "<function>",
  "onDeleted": "<function>",
  "onClose": "<function>"
}
```

### 4.2 ConversationActionBarProps

**Definition:**

```typescript
interface ConversationActionBarProps {
  conversation: Conversation
  isOwner: boolean
  labels: string[]
  mutations: Pick<ConversationMutations,
    "pokeMut" | "auditMut" | "snoozeMut" | "addLabelMut" | "deleteMut">
  onBack?: () => void
  pendingAudit: boolean
}
```

**Concrete Example:**

```json
{
  "conversation": {
    "id": 42,
    "sender_email": "recruiter@example.com",
    "subject": "Exciting Opportunity",
    "state": "engaging",
    "last_intent": "star_interest",
    "last_rating": null,
    "labels": "hot,priority",
    "star_verified": false,
    "github_username": "recruiter123",
    "is_human_managed": false,
    "attention_snoozed": false,
    "updated_at": "2026-03-01T12:00:00Z",
    "created_at": "2026-02-28T10:00:00Z"
  },
  "isOwner": true,
  "labels": ["hot", "priority"],
  "mutations": {
    "pokeMut": "<UseMutationResult>",
    "auditMut": "<UseMutationResult>",
    "snoozeMut": "<UseMutationResult>",
    "addLabelMut": "<UseMutationResult>",
    "deleteMut": "<UseMutationResult>"
  },
  "onBack": "<function>",
  "pendingAudit": false
}
```

### 4.3 ConversationFieldsProps

**Definition:**

```typescript
interface ConversationFieldsProps {
  conversation: Conversation
  isOwner: boolean
  labels: string[]
  starUsername: string
  onStarUsernameChange: (username: string) => void
  mutations: Pick<ConversationMutations,
    "clearUsernameMut" | "addLabelMut" | "removeLabelMut" |
    "takeoverMut" | "starMut">
}
```

**Concrete Example:**

```json
{
  "conversation": { "id": 42, "github_username": "recruiter123", "is_human_managed": false, "star_verified": false },
  "isOwner": true,
  "labels": ["hot", "priority"],
  "starUsername": "recruiter123",
  "onStarUsernameChange": "<function>",
  "mutations": {
    "clearUsernameMut": "<UseMutationResult>",
    "addLabelMut": "<UseMutationResult>",
    "removeLabelMut": "<UseMutationResult>",
    "takeoverMut": "<UseMutationResult>",
    "starMut": "<UseMutationResult>"
  }
}
```

### 4.4 ComposePanelProps

**Definition:**

```typescript
interface ComposePanelProps {
  conversation: Conversation
  isOwner: boolean
  sendMut: ConversationMutations["sendMut"]
  subject: string
  body: string
  pendingFiles: Array<{ filename: string; data: string }>
  onSubjectChange: (subject: string) => void
  onBodyChange: (body: string) => void
  onFilesChange: (files: Array<{ filename: string; data: string }>) => void
}
```

**Concrete Example:**

```json
{
  "conversation": { "id": 42, "subject": "Exciting Opportunity" },
  "isOwner": true,
  "sendMut": "<UseMutationResult>",
  "subject": "Re: Exciting Opportunity",
  "body": "Thanks for reaching out!",
  "pendingFiles": [{ "filename": "resume.pdf", "data": "base64..." }],
  "onSubjectChange": "<function>",
  "onBodyChange": "<function>",
  "onFilesChange": "<function>"
}
```

### 4.5 AuditResultPanelProps

**Definition:**

```typescript
interface AuditResultPanelProps {
  audit: AuditDiagnosis
  conversation: Conversation
  disabled: boolean
  onApproveAndSend: () => void
  onLoadDraft: () => void
  onApprove: () => void
  onChangeState: (state: string) => void
  onReject: () => void
}
```

**Concrete Example:**

```json
{
  "audit": {
    "draft_message": "Here is a draft response...",
    "draft_subject": "Re: Exciting Opportunity",
    "resume_needed": false,
    "state_correct": true,
    "recommended_state": null,
    "findings": "Response looks good. Star push is compelling."
  },
  "conversation": { "id": 42, "state": "engaging" },
  "disabled": false,
  "onApproveAndSend": "<function>",
  "onLoadDraft": "<function>",
  "onApprove": "<function>",
  "onChangeState": "<function>",
  "onReject": "<function>"
}
```

### 4.6 AuditHistoryPanelProps

**Definition:**

```typescript
interface AuditHistoryPanelProps {
  entries: AuditLogEntry[]
}
```

**Concrete Example:**

```json
{
  "entries": [
    {
      "id": 1,
      "conversation_id": 42,
      "action": "approve",
      "findings": "Approved after review.",
      "created_at": "2026-03-01T11:00:00Z"
    }
  ]
}
```

### 4.7 MessageBubbleProps

**Definition:**

```typescript
interface MessageBubbleProps {
  message: Message
  rating: Rating | undefined
  canUserRate: boolean
  onRate: (messageId: number, rating: number) => void
}
```

**Concrete Example:**

```json
{
  "message": {
    "id": 101,
    "conversation_id": 42,
    "direction": "outbound",
    "subject": "Re: Exciting Opportunity",
    "body": "Thanks for reaching out! Have you seen our repo?",
    "created_at": "2026-03-01T12:00:00Z",
    "has_resume": false
  },
  "rating": { "message_id": 101, "rating": 4, "note": "Great response" },
  "canUserRate": true,
  "onRate": "<function>"
}
```

### 4.8 DrawerActionOptions

**Definition:**

```typescript
interface DrawerActionOptions {
  closeOnSuccess?: boolean
  invalidateKeys?: string[][]
  onSuccessMessage?: string
  onSuccessCallback?: (data: unknown) => void
}
```

**Concrete Example:**

```json
{
  "closeOnSuccess": true,
  "invalidateKeys": [["conversation", "42"], ["attention-queue"]],
  "onSuccessMessage": "Email sent successfully"
}
```

### 4.9 ConversationMutations

**Definition:**

```typescript
interface ConversationMutations {
  pokeMut: UseMutationResult<unknown, Error, void>
  auditMut: UseMutationResult<unknown, Error, void>
  snoozeMut: UseMutationResult<unknown, Error, void>
  deleteMut: UseMutationResult<unknown, Error, void>
  addLabelMut: UseMutationResult<unknown, Error, string>
  removeLabelMut: UseMutationResult<unknown, Error, string>
  clearUsernameMut: UseMutationResult<unknown, Error, string>
  takeoverMut: UseMutationResult<unknown, Error, boolean>
  starMut: UseMutationResult<unknown, Error, string>
  sendMut: UseMutationResult<unknown, Error, { subject: string; body: string; attachments: Array<{ filename: string; data: string }> }>
  approveMut: UseMutationResult<unknown, Error, void>
  rejectMut: UseMutationResult<unknown, Error, void>
  changeStateMut: UseMutationResult<unknown, Error, string>
  rateMut: UseMutationResult<unknown, Error, { conversation_id: number; message_id: number; rating: number }>
  approveAndSendMut: UseMutationResult<unknown, Error, void>
}
```

**Concrete Example (return value shape):**

```json
{
  "pokeMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "auditMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "snoozeMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "deleteMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "addLabelMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "removeLabelMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "clearUsernameMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "takeoverMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "starMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "sendMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "approveMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "rejectMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "changeStateMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "rateMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null },
  "approveAndSendMut": { "mutate": "<fn>", "isPending": false, "isError": false, "data": null }
}
```

## 5. Function Specifications

### 5.1 `useDrawerAction()`

**File:** `dashboard/src/lib/hooks/useDrawerAction.ts`

**Signature:**

```typescript
function useDrawerAction<TData = unknown, TVariables = void>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  onClose: (() => void) | undefined,
  options?: DrawerActionOptions
): UseMutationResult<TData, Error, TVariables>
```

**Input Example:**

```typescript
const result = useDrawerAction(
  () => deleteConversation(42),
  () => console.log("drawer closed"),
  {
    closeOnSuccess: true,
    invalidateKeys: [["conversation", "42"], ["attention-queue"]],
    onSuccessMessage: "Conversation deleted"
  }
)
```

**Output Example:**

```typescript
// Returns standard UseMutationResult from TanStack React Query
{
  mutate: Function,      // call to trigger mutation
  mutateAsync: Function, // async variant
  isPending: false,
  isError: false,
  isSuccess: false,
  data: undefined,
  error: null,
  reset: Function,
}
```

**Edge Cases:**
- `onClose` is `undefined` -> mutation succeeds but no drawer close
- `options.closeOnSuccess` is `false` -> mutation succeeds, queries invalidated, but no `onClose` call
- `options.invalidateKeys` is `undefined` -> no query invalidation on success
- Mutation error -> `toast.error(err.message)` called, no close, no invalidation

### 5.2 `useAdminAction()`

**File:** `dashboard/src/lib/hooks/useAdminAction.ts`

**Signature:**

```typescript
function useAdminAction<TData = unknown, TVariables = void>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options?: DrawerActionOptions & { onClose?: () => void }
): UseMutationResult<TData, Error, TVariables>
```

**Input Example:**

```typescript
const result = useAdminAction(
  () => approveAudit(42),
  {
    onClose: () => console.log("closed"),
    invalidateKeys: [["conversation", "42"]],
    onSuccessMessage: "Audit approved"
  }
)
```

**Output Example:**

```typescript
// Same as useDrawerAction return, but with additional queue invalidation keys
// Automatically adds ["attention-queue"], ["audit-preview"] to invalidateKeys
```

**Edge Cases:**
- No extra `invalidateKeys` provided -> still invalidates `["attention-queue"]` and `["audit-preview"]`
- `onClose` not provided -> passes `undefined` to `useDrawerAction`

### 5.3 `useConversationMutations()`

**File:** `dashboard/src/lib/hooks/useConversationMutations.ts`

**Signature:**

```typescript
function useConversationMutations(
  conversationId: number,
  callbacks?: {
    onClose?: () => void
    onDeleted?: () => void
    onSendSuccess?: () => void
    onAuditMutate?: () => void
    onAuditSettled?: (success: boolean) => void
    getConversation?: () => Conversation | undefined
    getStarUsername?: () => string
  }
): ConversationMutations
```

**Input Example:**

```typescript
const mutations = useConversationMutations(42, {
  onClose: () => setDrawerOpen(false),
  onDeleted: () => navigateBack(),
  onSendSuccess: () => { setBody(""); setPendingFiles([]); },
  onAuditMutate: () => setPendingAudit(true),
  onAuditSettled: (success) => { if (!success) setPendingAudit(false); },
  getConversation: () => conv,
  getStarUsername: () => starUsername,
})
```

**Output Example:**

```typescript
{
  pokeMut: UseMutationResult,      // bulkPoke([convId])
  auditMut: UseMutationResult,     // triggerAudit([convId])
  snoozeMut: UseMutationResult,    // snoozeConversation(convId, toggle)
  deleteMut: UseMutationResult,    // deleteConversation(convId)
  addLabelMut: UseMutationResult,  // addLabel(convId, label)
  removeLabelMut: UseMutationResult, // removeLabel(convId, label)
  clearUsernameMut: UseMutationResult, // clearGithubUsername + addSkipWord
  takeoverMut: UseMutationResult,  // setTakeover(convId, managed)
  starMut: UseMutationResult,      // checkStar(convId, username)
  sendMut: UseMutationResult,      // sendMessage(convId, data)
  approveMut: UseMutationResult,   // approveAudit(convId)
  rejectMut: UseMutationResult,    // rejectAudit(convId)
  changeStateMut: UseMutationResult, // patchConversationState(convId, state)
  rateMut: UseMutationResult,      // submitRating(data)
  approveAndSendMut: UseMutationResult, // approveAndSendAudit(convId)
}
```

**Edge Cases:**
- `callbacks.onClose` is `undefined` -> drawer-closing mutations still fire but don't close
- `callbacks.getConversation()` returns `undefined` -> snoozeMut uses safe default
- Send mutation returns `res.ok === false` -> shows error toast, does NOT clear form

### 5.4 `ConversationActionBar()`

**File:** `dashboard/src/components/shared/conversation/ConversationActionBar.tsx`

**Input Example:**

```tsx
<ConversationActionBar
  conversation={conv}
  isOwner={true}
  labels={["hot", "priority"]}
  mutations={{ pokeMut, auditMut, snoozeMut, addLabelMut, deleteMut }}
  onBack={() => navigate("/conversations")}
  pendingAudit={false}
/>
```

**Output:** Renders a row of action buttons: Back, Poke, Audit, Snooze, Interview, Delete.

**Edge Cases:**
- `isOwner=false` -> only Back button rendered
- `pendingAudit=true` -> Audit button shows "Auditing..." and is disabled
- `conversation.is_human_managed=true` -> Audit button disabled with tooltip
- `conversation.attention_snoozed=true` -> Snooze button shows "Wake"
- Delete clicked and confirm cancelled -> `deleteMut.mutate()` NOT called

### 5.5 `ConversationFields()`

**File:** `dashboard/src/components/shared/conversation/ConversationFields.tsx`

**Input Example:**

```tsx
<ConversationFields
  conversation={conv}
  isOwner={true}
  labels={["hot", "priority"]}
  starUsername="recruiter123"
  onStarUsernameChange={setStarUsername}
  mutations={{ clearUsernameMut, addLabelMut, removeLabelMut, takeoverMut, starMut }}
/>
```

**Output:** Renders metadata fields including Sender, Subject, State, Channel, Created, Star status, Labels with chips, Management toggle, Check Star input.

**Edge Cases:**
- `isOwner=false` -> Management toggle and Check Star hidden
- `conversation.github_username=null` -> No "Clear" button next to username
- `conversation.is_human_managed=true` -> Toggle shows "Release to AI"

### 5.6 `ComposePanel()`

**File:** `dashboard/src/components/shared/conversation/ComposePanel.tsx`

**Input Example:**

```tsx
<ComposePanel
  conversation={conv}
  isOwner={true}
  sendMut={mutations.sendMut}
  subject="Re: Exciting Opportunity"
  body=""
  pendingFiles={[]}
  onSubjectChange={setSubject}
  onBodyChange={setBody}
  onFilesChange={setPendingFiles}
/>
```

**Output:** Renders email compose form with subject input, body textarea, file attachment button/input, send button, and file list.

**Edge Cases:**
- `isOwner=false` -> returns `null` (nothing rendered)
- Empty body + Send clicked -> `toast.error("Message body is empty")`, mutation NOT called
- Files attached -> shows file names with sizes below compose area

### 5.7 `AuditResultPanel()`

**File:** `dashboard/src/components/shared/conversation/AuditResultPanel.tsx`

**Input Example:**

```tsx
<AuditResultPanel
  audit={auditResult}
  conversation={conv}
  disabled={false}
  onApproveAndSend={() => approveAndSendMut.mutate()}
  onLoadDraft={() => { setSubject(audit.draft_subject); setBody(audit.draft_message); }}
  onApprove={() => approveMut.mutate()}
  onChangeState={(state) => changeStateMut.mutate(state)}
  onReject={() => rejectMut.mutate()}
/>
```

**Output:** Renders audit findings card with action buttons: Approve+Send, Load Draft, Approve, Mark State (if recommended), Reject.

**Edge Cases:**
- `disabled=true` -> all buttons disabled
- `audit.draft_message=null` -> Load Draft button hidden
- `audit.state_correct=true` -> Mark State button hidden
- `audit.recommended_state=null` -> Mark State button hidden

### 5.8 `AuditHistoryPanel()`

**File:** `dashboard/src/components/shared/conversation/AuditHistoryPanel.tsx`

**Input Example:**

```tsx
<AuditHistoryPanel entries={auditHistory || []} />
```

**Output:** Renders list of collapsible audit history entries with action, findings, and timestamp.

**Edge Cases:**
- Empty `entries` array -> renders nothing or "No audit history" text
- Long findings text -> truncated with expand toggle

### 5.9 `MessageBubble()`

**File:** `dashboard/src/components/shared/conversation/MessageBubble.tsx`

**Input Example:**

```tsx
<MessageBubble
  message={msg}
  rating={ratingsMap[msg.id]}
  canUserRate={true}
  onRate={(messageId, rating) => rateMut.mutate({ conversation_id: 42, message_id: messageId, rating })}
/>
```

**Output:** Renders a single message bubble with directional styling, direction label, timestamp, body content, and rating emojis for outbound messages.

**Edge Cases:**
- `message.direction="inbound"` -> left-aligned, no rating buttons
- `canUserRate=false` -> no rating buttons even for outbound
- `rating` exists -> highlight the active rating emoji
- `message.has_resume=true` -> shows resume indicator

## 6. Change Instructions

### 6.1 `dashboard/src/components/shared/conversation/types.ts` (Add)

**Complete file contents:**

```typescript
/**
 * Shared TypeScript types for conversation sub-components.
 *
 * Issue #283: Extracted from ConversationDetail.tsx
 *
 * NOTE: Most types (Message, Rating, AuditDiagnosis, AuditLogEntry, Conversation)
 * are already defined in @/api/types. This file re-exports them for convenience
 * and defines component-specific prop interfaces.
 */

import type { UseMutationResult } from "@tanstack/react-query"
import type { Message, Rating, AuditDiagnosis, AuditLogEntry } from "@/api/types"

// Re-export API types for convenience
export type { Message, Rating, AuditDiagnosis, AuditLogEntry }

/** Pending file attachment for compose */
export interface PendingFile {
  filename: string
  data: string // base64
}

/** Return type of useConversationMutations */
export interface ConversationMutations {
  pokeMut: UseMutationResult<unknown, Error, void>
  auditMut: UseMutationResult<unknown, Error, void>
  snoozeMut: UseMutationResult<unknown, Error, void>
  deleteMut: UseMutationResult<unknown, Error, void>
  addLabelMut: UseMutationResult<unknown, Error, string>
  removeLabelMut: UseMutationResult<unknown, Error, string>
  clearUsernameMut: UseMutationResult<unknown, Error, string>
  takeoverMut: UseMutationResult<unknown, Error, boolean>
  starMut: UseMutationResult<unknown, Error, string>
  sendMut: UseMutationResult<unknown, Error, { subject: string; body: string; attachments: PendingFile[] }>
  approveMut: UseMutationResult<unknown, Error, void>
  rejectMut: UseMutationResult<unknown, Error, void>
  changeStateMut: UseMutationResult<unknown, Error, string>
  rateMut: UseMutationResult<unknown, Error, { conversation_id: number; message_id: number; rating: number }>
  approveAndSendMut: UseMutationResult<unknown, Error, void>
}

/** Options for useDrawerAction */
export interface DrawerActionOptions {
  closeOnSuccess?: boolean
  invalidateKeys?: string[][]
  onSuccessMessage?: string
  onSuccessCallback?: (data: unknown) => void
}
```

### 6.2 `dashboard/src/components/shared/conversation/index.ts` (Add)

**Complete file contents:**

```typescript
export { ConversationActionBar } from "./ConversationActionBar"
export { ConversationFields } from "./ConversationFields"
export { ComposePanel } from "./ComposePanel"
export { AuditResultPanel } from "./AuditResultPanel"
export { AuditHistoryPanel } from "./AuditHistoryPanel"
export { MessageBubble } from "./MessageBubble"
export type { ConversationMutations, PendingFile, DrawerActionOptions } from "./types"
```

### 6.3 `dashboard/src/lib/hooks/useDrawerAction.ts` (Add)

**Complete file contents:**

```typescript
/**
 * Wraps a TanStack mutation with automatic drawer close and
 * query invalidation on success.
 *
 * Issue #283: Extracted from ConversationDetail.tsx inline mutations.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { UseMutationResult } from "@tanstack/react-query"
import { toast } from "sonner"
import type { DrawerActionOptions } from "@/components/shared/conversation/types"

export function useDrawerAction<TData = unknown, TVariables = void>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  onClose: (() => void) | undefined,
  options?: DrawerActionOptions
): UseMutationResult<TData, Error, TVariables> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn,
    onSuccess: (data) => {
      if (options?.invalidateKeys) {
        for (const key of options.invalidateKeys) {
          queryClient.invalidateQueries({ queryKey: key })
        }
      }
      if (options?.onSuccessMessage) {
        toast.success(options.onSuccessMessage)
      }
      if (options?.onSuccessCallback) {
        options.onSuccessCallback(data)
      }
      if (options?.closeOnSuccess !== false && onClose) {
        onClose()
      }
    },
    onError: (err: Error) => {
      toast.error(err.message)
    },
  })
}
```

### 6.4 `dashboard/src/lib/hooks/useAdminAction.ts` (Add)

**Complete file contents:**

```typescript
/**
 * Shared mutation wrapper for approve/reject/snooze actions
 * used across admin components.
 *
 * Issue #283: Implemented for ConversationDetail. Wiring to
 * AttentionQueueSection and AuditQueueSection deferred to follow-up.
 */

import type { UseMutationResult } from "@tanstack/react-query"
import { useDrawerAction } from "./useDrawerAction"
import type { DrawerActionOptions } from "@/components/shared/conversation/types"

export function useAdminAction<TData = unknown, TVariables = void>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options?: DrawerActionOptions & { onClose?: () => void }
): UseMutationResult<TData, Error, TVariables> {
  const { onClose, invalidateKeys = [], ...rest } = options ?? {}

  // Admin actions always invalidate queue-related keys
  const mergedKeys = [
    ["attention-queue"],
    ["audit-preview"],
    ...invalidateKeys,
  ]

  return useDrawerAction(mutationFn, onClose, {
    closeOnSuccess: true,
    invalidateKeys: mergedKeys,
    ...rest,
  })
}
```

### 6.5 `dashboard/src/lib/hooks/useConversationMutations.ts` (Add)

**Complete file contents:**

This is the largest new file. It must faithfully reproduce all 13+ mutation behaviors from the current `ConversationDetail.tsx`.

```typescript
/**
 * Centralizes all conversation mutations with query invalidation.
 *
 * Issue #283: Extracted from ConversationDetail.tsx.
 *
 * IMPORTANT: deleteMut is a raw mutation without a confirmation step.
 * The confirmation dialog (window.confirm) MUST be implemented in the
 * calling component BEFORE invoking deleteMut.mutate().
 */

import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  deleteConversation,
  sendMessage,
  addLabel,
  removeLabel,
  setTakeover,
  checkStar,
  submitRating,
  triggerAudit,
  approveAudit,
  approveAndSendAudit,
  rejectAudit,
  bulkPoke,
  clearGithubUsername,
  addSkipWord,
  patchConversationState,
  snoozeConversation,
} from "@/api/client"
import { toast } from "sonner"
import { useAdminAction } from "./useAdminAction"
import type { PendingFile } from "@/components/shared/conversation/types"

interface ConversationMutationCallbacks {
  onClose?: () => void
  onDeleted?: () => void
  onSendSuccess?: () => void
  onAuditMutate?: () => void
  onAuditSettled?: (success: boolean) => void
  getConversation?: () => { attention_snoozed: boolean } | undefined
  getStarUsername?: () => string
}

export function useConversationMutations(
  conversationId: number,
  callbacks?: ConversationMutationCallbacks
) {
  const convId = conversationId
  const queryClient = useQueryClient()
  const {
    onClose,
    onDeleted,
    onSendSuccess,
    onAuditMutate,
    onAuditSettled,
    getConversation,
    getStarUsername,
  } = callbacks ?? {}

  const invalidateConv = () => {
    queryClient.invalidateQueries({ queryKey: ["conversation", convId] })
  }

  // --- Delete (NO drawer close pattern - uses onDeleted callback) ---
  const deleteMut = useMutation({
    mutationFn: () => deleteConversation(convId),
    onSuccess: () => {
      toast.success(`Conversation #${convId} deleted`)
      onDeleted?.()
    },
  })

  // --- Send (custom success handling - clears form, conditionally toasts) ---
  const sendMut = useMutation({
    mutationFn: (data: { subject: string; body: string; attachments: PendingFile[] }) =>
      sendMessage(convId, data),
    onSuccess: (res: { ok: boolean; sendVia?: string; error?: string }) => {
      if (res.ok) {
        toast.success(`Email sent via ${res.sendVia}`)
        onSendSuccess?.()
        invalidateConv()
        queryClient.invalidateQueries({ queryKey: ["attention-queue"] })
      } else {
        toast.error(`Send failed: ${res.error || "unknown"}`)
      }
    },
    onError: (err: Error) => toast.error(`Send failed: ${err.message}`),
  })

  // --- Add Label (does NOT close drawer) ---
  const addLabelMut = useMutation({
    mutationFn: (label: string) => addLabel(convId, label),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["labels", convId] }),
  })

  // --- Remove Label ---
  const removeLabelMut = useMutation({
    mutationFn: (label: string) => removeLabel(convId, label),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["labels", convId] }),
  })

  // --- Takeover ---
  const takeoverMut = useMutation({
    mutationFn: (managed: boolean) => setTakeover(convId, managed),
    onSuccess: () => {
      invalidateConv()
      toast.success("Management updated")
    },
  })

  // --- Star Check ---
  const starMut = useMutation({
    mutationFn: (username: string) => checkStar(convId, username),
    onSuccess: (res: { starred: boolean }) => {
      const username = getStarUsername?.() ?? "User"
      if (res.starred) {
        toast.success(`${username} starred AssemblyZero!`)
      } else {
        toast(`${username} has NOT starred yet — username saved`)
      }
      invalidateConv()
    },
  })

  // --- Clear Username ---
  const clearUsernameMut = useMutation({
    mutationFn: async (username: string) => {
      await clearGithubUsername(convId)
      await addSkipWord(username)
    },
    onSuccess: () => {
      toast.success("Username cleared and added to skip list")
      invalidateConv()
    },
    onError: (err: Error) => toast.error(`Clear failed: ${err.message}`),
  })

  // --- Rate (does NOT close drawer) ---
  const rateMut = useMutation({
    mutationFn: submitRating,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ratings", convId] }),
  })

  // --- Poke ---
  const pokeMut = useMutation({
    mutationFn: () => bulkPoke([convId]),
    onSuccess: (res: { success: number; results?: Array<{ error?: string }> }) => {
      if (res.success > 0) {
        toast.success("Poke sent")
        invalidateConv()
      } else {
        toast.error(`Poke failed: ${res.results?.[0]?.error || "unknown"}`)
      }
    },
    onError: (err: Error) => toast.error(`Poke error: ${err.message}`),
  })

  // --- Audit (custom polling logic) ---
  const auditMut = useMutation({
    mutationFn: () => triggerAudit([convId]),
    onMutate: () => {
      onAuditMutate?.()
    },
    onSuccess: (res: { success: number; results?: Array<{ error?: string }> }) => {
      if (res.success > 0) {
        toast.success("Audit queued — results appear shortly")
        setTimeout(() => invalidateConv(), 500)
        const poll = setInterval(() => invalidateConv(), 3000)
        setTimeout(() => clearInterval(poll), 30000)
        onAuditSettled?.(true)
      } else {
        onAuditSettled?.(false)
        toast.error(`Audit failed: ${res.results?.[0]?.error || "unknown"}`)
      }
    },
    onError: (err: Error) => {
      onAuditSettled?.(false)
      toast.error(`Audit error: ${err.message}`)
    },
  })

  // --- Snooze ---
  const snoozeMut = useMutation({
    mutationFn: () => {
      const conv = getConversation?.()
      return snoozeConversation(convId, !conv?.attention_snoozed)
    },
    onSuccess: () => {
      const conv = getConversation?.()
      invalidateConv()
      queryClient.invalidateQueries({ queryKey: ["attention-queue"] })
      toast.success(conv?.attention_snoozed ? "Unsnoozed" : "Snoozed — will resurface if they write back")
    },
  })

  // --- Approve (admin action with queue invalidation) ---
  const approveMut = useAdminAction(
    () => approveAudit(convId),
    {
      onClose: undefined, // approve doesn't close drawer
      closeOnSuccess: false,
      invalidateKeys: [["conversation", convId.toString()]],
      onSuccessMessage: "Audit approved",
    }
  )

  // --- Reject (admin action with queue invalidation) ---
  const rejectMut = useAdminAction(
    () => rejectAudit(convId),
    {
      onClose: undefined,
      closeOnSuccess: false,
      invalidateKeys: [["conversation", convId.toString()]],
      onSuccessMessage: "Audit rejected",
    }
  )

  // --- Approve and Send ---
  const approveAndSendMut = useAdminAction(
    () => approveAndSendAudit(convId),
    {
      onClose: undefined,
      closeOnSuccess: false,
      invalidateKeys: [["conversation", convId.toString()]],
      onSuccessMessage: "Audit approved and email sent",
    }
  )

  // --- Change State ---
  const changeStateMut = useMutation({
    mutationFn: (state: string) => patchConversationState(convId, state),
    onSuccess: () => {
      invalidateConv()
      toast.success("State updated")
    },
  })

  return {
    pokeMut,
    auditMut,
    snoozeMut,
    deleteMut,
    addLabelMut,
    removeLabelMut,
    clearUsernameMut,
    takeoverMut,
    starMut,
    sendMut,
    approveMut,
    rejectMut,
    changeStateMut,
    rateMut,
    approveAndSendMut,
  }
}
```

### 6.6 `dashboard/src/lib/hooks/index.ts` (Add)

**Complete file contents:**

```typescript
export { useDrawerAction } from "./useDrawerAction"
export { useAdminAction } from "./useAdminAction"
export { useConversationMutations } from "./useConversationMutations"
```

### 6.7 `dashboard/src/components/shared/conversation/MessageBubble.tsx` (Add)

**Complete file contents:**

This component extracts the message rendering block from the current ConversationDetail.tsx `visibleMessages.map()` loop. It must reproduce the exact same DOM structure (class names, data attributes) to keep E2E tests passing.

```tsx
/**
 * Renders a single message with directional styling,
 * rating emojis, and rating note.
 *
 * Issue #283: Extracted from ConversationDetail.tsx message loop.
 */

import type { Message, Rating } from "@/api/types"
import { toCTFull } from "@/lib/utils"
import { RATING_EMOJIS } from "@/lib/constants"

interface MessageBubbleProps {
  message: Message
  rating: Rating | undefined
  isPreInit: boolean
  canUserRate: boolean
  onRate: (messageId: number, rating: number) => void
}

export function MessageBubble({ message: msg, rating, isPreInit, canUserRate, onRate }: MessageBubbleProps) {
  const isOutbound = msg.direction === "outbound"

  return (
    <div
      className={`rounded-lg p-3 ${
        isOutbound ? "ml-8 bg-blue-50 dark:bg-blue-950/30" : "mr-8 bg-gray-50 dark:bg-gray-800/50"
      } ${isPreInit ? "opacity-50" : ""}`}
    >
      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
        <span className="font-semibold">
          {msg.direction.toUpperCase()}
          {msg.has_resume && "  RESUME"}
          {isPreInit && " (pre-reinit)"}
        </span>
        <span>{toCTFull(msg.created_at)}</span>
      </div>
      {msg.subject && (
        <div className="mb-1 text-xs font-medium text-muted-foreground">
          Subject: {msg.subject}
        </div>
      )}
      <div className="whitespace-pre-wrap text-sm">{msg.body}</div>

      {/* Rating section for outbound messages */}
      {isOutbound && canUserRate && (
        <div className="mt-2 flex items-center gap-1">
          {RATING_EMOJIS.map((emoji: string, idx: number) => (
            <button
              key={idx}
              className={`rounded-md px-2 py-1 text-sm transition-colors ${
                rating?.rating === idx + 1
                  ? "bg-blue-200 dark:bg-blue-800"
                  : "hover:bg-gray-200 dark:hover:bg-gray-700"
              }`}
              onClick={() => onRate(msg.id, idx + 1)}
              title={`Rate ${idx + 1}`}
            >
              {emoji}
            </button>
          ))}
          {rating?.note && (
            <span className="ml-2 text-xs text-muted-foreground italic">
              {rating.note}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
```

### 6.8 `dashboard/src/components/shared/conversation/AuditHistoryPanel.tsx` (Add)

**Complete file contents:**

```tsx
/**
 * Renders collapsible audit history entries.
 *
 * Issue #283: Extracted from ConversationDetail.tsx audit history section.
 */

import { useState } from "react"
import type { AuditLogEntry } from "@/api/types"
import { toCTFull } from "@/lib/utils"

interface AuditHistoryPanelProps {
  entries: AuditLogEntry[]
}

export function AuditHistoryPanel({ entries }: AuditHistoryPanelProps) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  if (!entries || entries.length === 0) return null

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  return (
    <div className="mt-4">
      <h3 className="mb-2 text-sm font-semibold">Audit History</h3>
      <div className="space-y-2">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="rounded border p-2 text-xs"
          >
            <div
              className="flex cursor-pointer items-center justify-between"
              onClick={() => toggleExpand(entry.id)}
            >
              <span className="font-medium">
                {entry.action} — {toCTFull(entry.created_at)}
              </span>
              <span>{expandedIds.has(entry.id) ? "▼" : "▶"}</span>
            </div>
            {expandedIds.has(entry.id) && (
              <div className="mt-1 whitespace-pre-wrap text-muted-foreground">
                {entry.findings}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
```

### 6.9 `dashboard/src/components/shared/conversation/ConversationActionBar.tsx` (Add)

**Complete file contents:**

This is the most safety-critical extracted component due to the delete confirmation gate.

```tsx
/**
 * Action bar: Back, Poke, Audit, Snooze, Interview, Delete.
 *
 * Issue #283: Extracted from ConversationDetail.tsx action button row.
 *
 * SAFETY: handleDelete includes mandatory window.confirm() gate
 * BEFORE calling deleteMut.mutate(). This matches existing behavior.
 */

import { Button } from "@/components/ui/button"
import { ArrowLeft, Trash2 } from "lucide-react"
import type { ConversationMutations } from "./types"

interface ConversationActionBarProps {
  conversation: {
    id: number
    is_human_managed: boolean
    attention_snoozed: boolean
  }
  isOwner: boolean
  labels: string[]
  mutations: Pick<ConversationMutations, "pokeMut" | "auditMut" | "snoozeMut" | "addLabelMut" | "deleteMut">
  onBack?: () => void
  pendingAudit: boolean
}

export function ConversationActionBar({
  conversation: conv,
  isOwner,
  labels,
  mutations,
  onBack,
  pendingAudit,
}: ConversationActionBarProps) {
  const { pokeMut, auditMut, snoozeMut, deleteMut } = mutations

  /**
   * SAFETY-CRITICAL: Confirmation gate for destructive action.
   * window.confirm is synchronous — cannot be bypassed by race conditions.
   */
  const handleDelete = () => {
    if (!window.confirm("Are you sure you want to delete this conversation?")) {
      return
    }
    deleteMut.mutate()
  }

  return (
    <div className="mb-4 flex items-center gap-2">
      {onBack && (
        <Button variant="outline" size="sm" onClick={onBack}>
          <ArrowLeft className="mr-1 h-4 w-4" /> Back
        </Button>
      )}
      {isOwner && (
        <Button
          size="sm"
          variant="outline"
          className="border-yellow-500 text-yellow-500"
          onClick={() => pokeMut.mutate()}
          disabled={pokeMut.isPending}
          title="Re-init + generate AI response + send email"
        >
          {pokeMut.isPending ? "Poking..." : "Poke"}
        </Button>
      )}
      {isOwner && (
        <Button
          size="sm"
          variant="outline"
          className="border-purple-500 text-purple-500"
          onClick={() => auditMut.mutate()}
          disabled={auditMut.isPending || pendingAudit || conv.is_human_managed}
          title={
            conv.is_human_managed
              ? "Cannot audit human-managed conversation"
              : pendingAudit
                ? "Audit in progress..."
                : "Run AI audit on this conversation"
          }
        >
          {auditMut.isPending || pendingAudit ? "Auditing..." : "Audit"}
        </Button>
      )}
      {isOwner && (
        <Button
          size="sm"
          variant="outline"
          onClick={() => snoozeMut.mutate()}
          disabled={snoozeMut.isPending}
        >
          {conv.attention_snoozed ? "Wake" : "Snooze"}
        </Button>
      )}
      {isOwner && (
        <Button
          size="sm"
          variant="outline"
          className="border-red-500 text-red-500"
          onClick={handleDelete}
          disabled={deleteMut.isPending}
        >
          <Trash2 className="mr-1 h-4 w-4" />
          {deleteMut.isPending ? "Deleting..." : "Delete"}
        </Button>
      )}
    </div>
  )
}
```

### 6.10 `dashboard/src/components/shared/conversation/ConversationFields.tsx` (Add)

**Complete file contents:**

This component extracts the metadata fields section — Sender, Subject, State, Channel, Created, Labels, Management, Star status, Check Star input.

```tsx
/**
 * Metadata fields: sender, subject, state, labels, takeover, star check.
 *
 * Issue #283: Extracted from ConversationDetail.tsx metadata section.
 */

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { StateBadge, HumanManagedBadge } from "@/components/shared/StateBadge"
import { LabelChips } from "@/components/shared/LabelChips"
import { toCTFull } from "@/lib/utils"
import type { ConversationMutations } from "./types"

interface ConversationFieldsProps {
  conversation: {
    id: number
    sender_email: string
    subject: string
    state: string
    channel?: string
    created_at: string
    updated_at: string
    github_username: string | null
    is_human_managed: boolean
    star_verified: boolean
    attention_snoozed: boolean
    last_intent: string
  }
  isOwner: boolean
  labels: string[]
  starUsername: string
  onStarUsernameChange: (username: string) => void
  mutations: Pick<ConversationMutations,
    "clearUsernameMut" | "addLabelMut" | "removeLabelMut" | "takeoverMut" | "starMut">
}

export function ConversationFields({
  conversation: conv,
  isOwner,
  labels,
  starUsername,
  onStarUsernameChange,
  mutations,
}: ConversationFieldsProps) {
  const { clearUsernameMut, addLabelMut, removeLabelMut, takeoverMut, starMut } = mutations

  return (
    <div className="space-y-2 text-sm">
      <div>
        <span className="font-semibold">Sender:</span> {conv.sender_email}
      </div>
      <div>
        <span className="font-semibold">Subject:</span> {conv.subject}
      </div>
      <div className="flex items-center gap-2">
        <span className="font-semibold">State:</span>
        <StateBadge state={conv.state} />
        {conv.is_human_managed && <HumanManagedBadge />}
      </div>
      <div>
        <span className="font-semibold">Channel:</span> {conv.channel || "email"}
      </div>
      <div>
        <span className="font-semibold">Created:</span> {toCTFull(conv.created_at)}
      </div>
      <div>
        <span className="font-semibold">Updated:</span> {toCTFull(conv.updated_at)}
      </div>
      <div>
        <span className="font-semibold">Intent:</span> {conv.last_intent}
      </div>

      {/* Star verification status */}
      <div className="flex items-center gap-2">
        <span className="font-semibold">Star:</span>
        {conv.star_verified ? (
          <span className="text-green-600"> Verified</span>
        ) : (
          <span className="text-muted-foreground">Not verified</span>
        )}
        {conv.github_username && (
          <>
            <span className="text-xs text-muted-foreground">({conv.github_username})</span>
            {isOwner && (
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-xs text-red-500"
                onClick={() => clearUsernameMut.mutate(conv.github_username!)}
                disabled={clearUsernameMut.isPending}
              >
                Clear
              </Button>
            )}
          </>
        )}
      </div>

      {/* Labels */}
      <div className="flex items-center gap-2">
        <span className="font-semibold">Labels:</span>
        <LabelChips
          labels={labels}
          onAdd={isOwner ? (label: string) => addLabelMut.mutate(label) : undefined}
          onRemove={isOwner ? (label: string) => removeLabelMut.mutate(label) : undefined}
        />
      </div>

      {/* Management toggle (owner only) */}
      {isOwner && (
        <div className="flex items-center gap-2">
          <span className="font-semibold">Management:</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => takeoverMut.mutate(!conv.is_human_managed)}
            disabled={takeoverMut.isPending}
          >
            {conv.is_human_managed ? "Release to AI" : "Take Over"}
          </Button>
        </div>
      )}

      {/* Check Star input (owner only) */}
      {isOwner && (
        <div className="flex items-center gap-2">
          <span className="font-semibold">Check Star:</span>
          <Input
            placeholder="GitHub username"
            value={starUsername}
            onChange={(e) => onStarUsernameChange(e.target.value)}
            className="h-8 w-48"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => starMut.mutate(starUsername)}
            disabled={starMut.isPending || !starUsername.trim()}
          >
            Verify
          </Button>
        </div>
      )}
    </div>
  )
}
```

### 6.11 `dashboard/src/components/shared/conversation/ComposePanel.tsx` (Add)

**Complete file contents:**

```tsx
/**
 * Email compose form: subject, body, file attach, send button.
 * Owner-only visibility.
 *
 * Issue #283: Extracted from ConversationDetail.tsx compose section.
 */

import { useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"
import { formatBytes } from "@/lib/utils"
import type { ConversationMutations, PendingFile } from "./types"

interface ComposePanelProps {
  conversation: { id: number }
  isOwner: boolean
  sendMut: ConversationMutations["sendMut"]
  subject: string
  body: string
  pendingFiles: PendingFile[]
  onSubjectChange: (subject: string) => void
  onBodyChange: (body: string) => void
  onFilesChange: (files: PendingFile[]) => void
}

export function ComposePanel({
  isOwner,
  sendMut,
  subject,
  body,
  pendingFiles,
  onSubjectChange,
  onBodyChange,
  onFilesChange,
}: ComposePanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  if (!isOwner) return null

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const newPending: PendingFile[] = []
    files.forEach((file) => {
      const reader = new FileReader()
      reader.onload = (ev) => {
        const result = ev.target?.result as string
        newPending.push({ filename: file.name, data: result.split(",")[1] })
        if (newPending.length === files.length) {
          onFilesChange(newPending)
        }
      }
      reader.readAsDataURL(file)
    })
  }

  const handleSend = () => {
    if (!body.trim()) {
      toast.error("Message body is empty")
      return
    }
    sendMut.mutate({ subject, body, attachments: pendingFiles })
  }

  return (
    <div className="mt-4">
      <h3 className="mb-2 text-sm font-semibold">Compose Reply</h3>
      <div className="space-y-2">
        <Input
          placeholder="Subject"
          value={subject}
          onChange={(e) => onSubjectChange(e.target.value)}
        />
        <Textarea
          placeholder="Type your message..."
          value={body}
          onChange={(e) => onBodyChange(e.target.value)}
          rows={4}
        />
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
          >
            Attach Files
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
          <Button
            size="sm"
            onClick={handleSend}
            disabled={sendMut.isPending}
          >
            {sendMut.isPending ? "Sending..." : "Send Email"}
          </Button>
        </div>
        {pendingFiles.length > 0 && (
          <div className="text-xs text-muted-foreground">
            {pendingFiles.map((f, i) => (
              <span key={i} className="mr-2">
                 {f.filename}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

### 6.12 `dashboard/src/components/shared/conversation/AuditResultPanel.tsx` (Add)

**Complete file contents:**

```tsx
/**
 * Audit result actions: Approve+Send, Load Draft, Approve, Mark State, Reject.
 *
 * Issue #283: Extracted from ConversationDetail.tsx audit result section.
 */

import { Button } from "@/components/ui/button"
import type { AuditDiagnosis } from "@/api/types"

interface AuditResultPanelProps {
  audit: AuditDiagnosis
  conversation: { id: number; state: string }
  disabled: boolean
  onApproveAndSend: () => void
  onLoadDraft: () => void
  onApprove: () => void
  onChangeState: (state: string) => void
  onReject: () => void
}

export function AuditResultPanel({
  audit,
  conversation: conv,
  disabled,
  onApproveAndSend,
  onLoadDraft,
  onApprove,
  onChangeState,
  onReject,
}: AuditResultPanelProps) {
  return (
    <div className="mt-4 rounded border border-purple-300 bg-purple-50 p-3 dark:border-purple-700 dark:bg-purple-950/30">
      <h3 className="mb-2 text-sm font-semibold text-purple-700 dark:text-purple-300">
        Audit Result
      </h3>

      {/* Findings */}
      <div className="mb-2 whitespace-pre-wrap text-xs text-muted-foreground">
        {audit.findings}
      </div>

      {/* State recommendation */}
      {!audit.state_correct && audit.recommended_state && (
        <div className="mb-2 text-xs">
          <span className="font-semibold text-orange-600">
            Recommended state: {audit.recommended_state}
          </span>
          {" "}(current: {conv.state})
        </div>
      )}

      {/* Resume needed indicator */}
      {audit.resume_needed && (
        <div className="mb-2 text-xs font-semibold text-blue-600">
           Resume attachment recommended
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap items-center gap-2">
        {audit.draft_message && (
          <>
            <Button
              size="sm"
              variant="outline"
              className="border-green-500 text-green-600"
              onClick={onApproveAndSend}
              disabled={disabled}
            >
              Approve + Send
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={onLoadDraft}
              disabled={disabled}
            >
              Load Draft
            </Button>
          </>
        )}
        <Button
          size="sm"
          variant="outline"
          className="border-green-500 text-green-600"
          onClick={onApprove}
          disabled={disabled}
        >
          Approve
        </Button>
        {!audit.state_correct && audit.recommended_state && (
          <Button
            size="sm"
            variant="outline"
            className="border-orange-500 text-orange-600"
            onClick={() => onChangeState(audit.recommended_state!)}
            disabled={disabled}
          >
            Mark {audit.recommended_state}
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          className="border-red-500 text-red-500"
          onClick={onReject}
          disabled={disabled}
        >
          Reject
        </Button>
      </div>
    </div>
  )
}
```

### 6.13 `dashboard/src/components/shared/ConversationDetail.tsx` (Modify)

**What changes:** Replace the entire file with a ~200-line orchestrator.

The orchestrator keeps:
- All `useQuery` calls (conversation, labels, ratings, auditHistory)
- All local state (`showFullHistory`, `subject`, `body`, `starUsername`, `pendingFiles`, `pendingAudit`)
- The `pendingAudit` effect
- The message processing logic (visible/hidden, reverse order)
- Loading/error/null early returns
- The render layout structure

The orchestrator removes:
- All 13+ inline `useMutation` calls (moved to `useConversationMutations`)
- All inline render blocks for action bar, fields, compose, audit, messages (moved to child components)
- The `handleFileChange` handler (moved to `ComposePanel`)

**Complete replacement file:**

```tsx
/**
 * ConversationDetail orchestrator — composes extracted child components.
 *
 * Issue #283: Reduced from 1132 lines to ~200 lines.
 */

import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  fetchConversation,
  fetchLabels,
  fetchRatings,
  fetchAuditHistory,
} from "@/api/client"
import type { Message, Rating } from "@/api/types"
import { useAuth } from "@/providers/AuthProvider"
import { canWrite, canRate } from "@/lib/roles"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useConversationMutations } from "@/lib/hooks"
import {
  ConversationActionBar,
  ConversationFields,
  ComposePanel,
  AuditResultPanel,
  AuditHistoryPanel,
  MessageBubble,
} from "./conversation"

interface ConversationDetailProps {
  conversationId: number
  onBack?: () => void
  onDeleted?: () => void
  onClose?: () => void
}

export function ConversationDetail({ conversationId, onBack, onDeleted, onClose }: ConversationDetailProps) {
  const convId = conversationId
  const { role } = useAuth()
  const isOwner = canWrite(role)

  // Local state
  const [showFullHistory, setShowFullHistory] = useState(true)
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [starUsername, setStarUsername] = useState("")
  const [pendingFiles, setPendingFiles] = useState<Array<{ filename: string; data: string }>>([])
  const [pendingAudit, setPendingAudit] = useState(false)

  // Queries
  const { data: conv, isLoading, error } = useQuery({
    queryKey: ["conversation", convId],
    queryFn: () => fetchConversation(convId),
  })

  const { data: labels } = useQuery({
    queryKey: ["labels", convId],
    queryFn: () => fetchLabels(convId),
  })

  const { data: ratings } = useQuery({
    queryKey: ["ratings", convId],
    queryFn: () => fetchRatings(convId),
    enabled: canRate(role),
  })

  const { data: auditHistory } = useQuery({
    queryKey: ["audit-history", convId],
    queryFn: () => fetchAuditHistory(convId),
    enabled: isOwner,
  })

  // Ratings map
  const ratingsMap: Record<number, Rating> = {}
  if (ratings) {
    for (const r of ratings) ratingsMap[r.message_id] = r
  }

  // Centralized mutations
  const mutations = useConversationMutations(convId, {
    onClose,
    onDeleted,
    onSendSuccess: () => {
      setBody("")
      setPendingFiles([])
    },
    onAuditMutate: () => setPendingAudit(true),
    onAuditSettled: (success) => {
      if (!success) setPendingAudit(false)
    },
    getConversation: () => conv,
    getStarUsername: () => starUsername,
  })

  // Reset pendingAudit when audit_result appears
  useEffect(() => {
    if (pendingAudit && conv?.audit_result) {
      setPendingAudit(false)
    }
  }, [conv?.audit_result, pendingAudit])

  // Early returns
  if (isLoading) return <div className="py-10 text-center text-muted-foreground">Loading...</div>
  if (error) return <div className="py-10 text-center text-destructive">Error: {error.message}</div>
  if (!conv) return null

  // Initialize subject for compose
  if (!subject && conv.subject) {
    setSubject(`Re: ${conv.subject}`)
  }

  // Message processing
  const allMessages: Message[] = conv.messages || []
  const lastInitAt = conv.last_init_at
  let hiddenCount = 0
  const visibleMessages: Array<{ msg: Message; isPreInit: boolean }> = []

  for (const msg of allMessages) {
    const isPreInit = !!(lastInitAt && msg.created_at < lastInitAt)
    if (isPreInit && !showFullHistory) {
      hiddenCount++
    } else {
      visibleMessages.push({ msg, isPreInit })
    }
  }
  visibleMessages.reverse()

  // Derive labels array
  const labelList = labels || []

  return (
    <div>
      <Card className="mb-4">
        <CardContent className="p-5">
          {/* Action bar */}
          <ConversationActionBar
            conversation={conv}
            isOwner={isOwner}
            labels={labelList}
            mutations={mutations}
            onBack={onBack}
            pendingAudit={pendingAudit}
          />

          {/* Conversation header */}
          <h2 className="mb-3 text-lg font-bold">Conversation #{conv.id}</h2>

          {/* Metadata fields */}
          <ConversationFields
            conversation={conv}
            isOwner={isOwner}
            labels={labelList}
            starUsername={starUsername}
            onStarUsernameChange={setStarUsername}
            mutations={mutations}
          />

          {/* Audit result (if available) */}
          {conv.audit_result && (
            <AuditResultPanel
              audit={conv.audit_result}
              conversation={conv}
              disabled={mutations.approveMut.isPending || mutations.rejectMut.isPending}
              onApproveAndSend={() => mutations.approveAndSendMut.mutate()}
              onLoadDraft={() => {
                if (conv.audit_result?.draft_subject) setSubject(conv.audit_result.draft_subject)
                if (conv.audit_result?.draft_message) setBody(conv.audit_result.draft_message)
              }}
              onApprove={() => mutations.approveMut.mutate()}
              onChangeState={(state) => mutations.changeStateMut.mutate(state)}
              onReject={() => mutations.rejectMut.mutate()}
            />
          )}

          {/* Compose panel */}
          <ComposePanel
            conversation={conv}
            isOwner={isOwner}
            sendMut={mutations.sendMut}
            subject={subject}
            body={body}
            pendingFiles={pendingFiles}
            onSubjectChange={setSubject}
            onBodyChange={setBody}
            onFilesChange={setPendingFiles}
          />

          {/* Audit history */}
          {auditHistory && auditHistory.length > 0 && (
            <AuditHistoryPanel entries={auditHistory} />
          )}
        </CardContent>
      </Card>

      {/* Messages section */}
      <h3 className="mb-2 text-sm font-semibold">Messages</h3>

      {/* History toggle */}
      {lastInitAt && (
        <div className="mb-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setShowFullHistory(!showFullHistory)}
          >
            {showFullHistory ? "Show Recent Only" : `Show Full History (${hiddenCount} hidden)`}
          </Button>
        </div>
      )}

      <div className="space-y-3">
        {visibleMessages.map(({ msg, isPreInit }) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            rating={ratingsMap[msg.id]}
            isPreInit={isPreInit}
            canUserRate={canRate(role)}
            onRate={(messageId, rating) =>
              mutations.rateMut.mutate({
                conversation_id: convId,
                message_id: messageId,
                rating,
              })
            }
          />
        ))}
      </div>
    </div>
  )
}
```

### 6.14 `tests/unit/dashboard/fixtures.ts` (Add)

**Complete file contents:**

```typescript
/**
 * Shared test fixtures for dashboard unit tests.
 *
 * Issue #283
 */

import type { AuditDiagnosis, AuditLogEntry, Message, Rating } from "@/api/types"

export const mockConversation = {
  id: 42,
  sender_email: "recruiter@example.com",
  subject: "Exciting Opportunity",
  state: "engaging",
  last_intent: "star_interest",
  last_rating: null,
  labels: "hot,priority",
  star_verified: false,
  github_username: "recruiter123",
  is_human_managed: false,
  attention_snoozed: false,
  updated_at: "2026-03-01T12:00:00Z",
  created_at: "2026-02-28T10:00:00Z",
  channel: "email",
  messages: [] as Message[],
  audit_result: null as AuditDiagnosis | null,
  last_init_at: null as string | null,
}

export const mockMessage: Message = {
  id: 101,
  conversation_id: 42,
  direction: "outbound",
  subject: "Re: Exciting Opportunity",
  body: "Thanks for reaching out! Have you seen our repo?",
  created_at: "2026-03-01T12:00:00Z",
  has_resume: false,
}

export const mockInboundMessage: Message = {
  id: 100,
  conversation_id: 42,
  direction: "inbound",
  subject: "Exciting Opportunity",
  body: "Hi, I found your profile and wanted to reach out...",
  created_at: "2026-02-28T10:30:00Z",
  has_resume: false,
}

export const mockRating: Rating = {
  message_id: 101,
  rating: 4,
  note: "Great response",
}

export const mockAuditResult: AuditDiagnosis = {
  draft_message: "Here is a draft response...",
  draft_subject: "Re: Exciting Opportunity",
  resume_needed: false,
  state_correct: true,
  recommended_state: null,
  findings: "Response looks good. Star push is compelling.",
}

export const mockAuditHistoryEntry: AuditLogEntry = {
  id: 1,
  conversation_id: 42,
  action: "approve",
  findings: "Approved after review.",
  created_at: "2026-03-01T11:00:00Z",
}

/** Helper to create a mock UseMutationResult */
export function createMockMutation(overrides: Record<string, unknown> = {}) {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    isIdle: true,
    data: undefined,
    error: null,
    reset: vi.fn(),
    status: "idle" as const,
    failureCount: 0,
    failureReason: null,
    variables: undefined,
    submittedAt: 0,
    isPaused: false,
    context: undefined,
    ...overrides,
  }
}

/** Helper to create all mock mutations */
export function createMockMutations() {
  return {
    pokeMut: createMockMutation(),
    auditMut: createMockMutation(),
    snoozeMut: createMockMutation(),
    deleteMut: createMockMutation(),
    addLabelMut: createMockMutation(),
    removeLabelMut: createMockMutation(),
    clearUsernameMut: createMockMutation(),
    takeoverMut: createMockMutation(),
    starMut: createMockMutation(),
    sendMut: createMockMutation(),
    approveMut: createMockMutation(),
    rejectMut: createMockMutation(),
    changeStateMut: createMockMutation(),
    rateMut: createMockMutation(),
    approveAndSendMut: createMockMutation(),
  }
}
```

### 6.15 `tests/unit/dashboard/hooks/useDrawerAction.test.ts` (Add)

**Complete file contents:**

```typescript
/**
 * Unit tests for useDrawerAction hook.
 *
 * Issue #283 — Test IDs: 080, 090
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createElement } from "react"
import { useDrawerAction } from "@/lib/hooks/useDrawerAction"

// Mock sonner toast
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { toast } from "sonner"

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe("useDrawerAction", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("080: closes drawer on mutation success when closeOnSuccess is true", async () => {
    const onClose = vi.fn()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useDrawerAction(mutationFn, onClose, {
        closeOnSuccess: true,
        onSuccessMessage: "Done!",
      }),
      { wrapper: createWrapper() }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(toast.success).toHaveBeenCalledWith("Done!")
  })

  it("080b: does not close drawer when closeOnSuccess is false", async () => {
    const onClose = vi.fn()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useDrawerAction(mutationFn, onClose, { closeOnSuccess: false }),
      { wrapper: createWrapper() }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(onClose).not.toHaveBeenCalled()
  })

  it("080c: does not close drawer when onClose is undefined", async () => {
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useDrawerAction(mutationFn, undefined, { closeOnSuccess: true }),
      { wrapper: createWrapper() }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    // No error thrown, no close called
    expect(mutationFn).toHaveBeenCalled()
  })

  it("090: shows toast on mutation error", async () => {
    const onClose = vi.fn()
    const mutationFn = vi.fn().mockRejectedValue(new Error("Network error"))

    const { result } = renderHook(
      () => useDrawerAction(mutationFn, onClose),
      { wrapper: createWrapper() }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(toast.error).toHaveBeenCalledWith("Network error")
    expect(onClose).not.toHaveBeenCalled()
  })

  it("invalidates specified query keys on success", async () => {
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })
    const queryClient = new QueryClient()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const wrapper = ({ children }: { children: React.ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children)

    const { result } = renderHook(
      () => useDrawerAction(mutationFn, undefined, {
        invalidateKeys: [["conversation", "42"], ["attention-queue"]],
        closeOnSuccess: false,
      }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["conversation", "42"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["attention-queue"] })
  })
})
```

### 6.16 `tests/unit/dashboard/hooks/useAdminAction.test.ts` (Add)

**Complete file contents:**

```typescript
/**
 * Unit tests for useAdminAction hook.
 *
 * Issue #283 — Test IDs: 310, 320
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createElement } from "react"
import { useAdminAction } from "@/lib/hooks/useAdminAction"

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return {
    wrapper: ({ children }: { children: React.ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children),
    queryClient,
  }
}

describe("useAdminAction", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("310: invalidates attention-queue and audit-preview on success", async () => {
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction(mutationFn, {
        closeOnSuccess: false,
        onSuccessMessage: "Approved",
      }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["attention-queue"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["audit-preview"] })
  })

  it("310b: merges additional invalidateKeys with queue keys", async () => {
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction(mutationFn, {
        closeOnSuccess: false,
        invalidateKeys: [["conversation", "42"]],
      }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["attention-queue"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["audit-preview"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["conversation", "42"] })
  })

  it("320: returns a mutation result that can be used in components", async () => {
    const { wrapper } = createWrapper()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction(mutationFn, { closeOnSuccess: false }),
      { wrapper }
    )

    expect(result.current.mutate).toBeDefined()
    expect(result.current.isPending).toBe(false)
    expect(result.current.isError).toBe(false)
  })
})
```

### 6.17 `tests/unit/dashboard/hooks/useConversationMutations.test.ts` (Add)

**Complete file contents:**

```typescript
/**
 * Unit tests for useConversationMutations hook.
 *
 * Issue #283 — Test IDs: 100, 110, 120, 130
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createElement } from "react"
import { useConversationMutations } from "@/lib/hooks/useConversationMutations"

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

vi.mock("@/api/client", () => ({
  deleteConversation: vi.fn(),
  sendMessage: vi.fn(),
  addLabel: vi.fn(),
  removeLabel: vi.fn(),
  setTakeover: vi.fn(),
  checkStar: vi.fn(),
  submitRating: vi.fn(),
  triggerAudit: vi.fn(),
  approveAudit: vi.fn(),
  approveAndSendAudit: vi.fn(),
  rejectAudit: vi.fn(),
  bulkPoke: vi.fn(),
  clearGithubUsername: vi.fn(),
  addSkipWord: vi.fn(),
  patchConversationState: vi.fn(),
  snoozeConversation: vi.fn(),
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe("useConversationMutations", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("100: returns all 15 mutation objects", () => {
    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper: createWrapper() }
    )

    const mutationKeys = [
      "pokeMut", "auditMut", "snoozeMut", "deleteMut",
      "addLabelMut", "removeLabelMut", "clearUsernameMut",
      "takeoverMut", "starMut", "sendMut",
      "approveMut", "rejectMut", "changeStateMut",
      "rateMut", "approveAndSendMut",
    ]

    for (const key of mutationKeys) {
      expect(result.current).toHaveProperty(key)
      expect(result.current[key as keyof typeof result.current]).toHaveProperty("mutate")
    }
  })

  it("100b: each mutation has mutate function", () => {
    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper: createWrapper() }
    )

    expect(typeof result.current.pokeMut.mutate).toBe("function")
    expect(typeof result.current.deleteMut.mutate).toBe("function")
    expect(typeof result.current.sendMut.mutate).toBe("function")
  })

  it("110: addLabelMut does not call onClose (stays open)", () => {
    const onClose = vi.fn()
    const { result } = renderHook(
      () => useConversationMutations(42, { onClose }),
      { wrapper: createWrapper() }
    )

    // addLabelMut should not have close behavior
    // Verified by the mutation definition not calling onClose
    expect(result.current.addLabelMut).toBeDefined()
    // Note: Full behavior tested via integration — this confirms the hook exists
  })

  it("120: rateMut does not call onClose (stays open)", () => {
    const onClose = vi.fn()
    const { result } = renderHook(
      () => useConversationMutations(42, { onClose }),
      { wrapper: createWrapper() }
    )

    expect(result.current.rateMut).toBeDefined()
  })

  it("130: removeLabelMut does not call onClose (stays open)", () => {
    const onClose = vi.fn()
    const { result } = renderHook(
      () => useConversationMutations(42, { onClose }),
      { wrapper: createWrapper() }
    )

    expect(result.current.removeLabelMut).toBeDefined()
  })
})
```

### 6.18 `tests/unit/dashboard/conversation/ConversationActionBar.test.tsx` (Add)

**Complete file contents:**

```tsx
/**
 * Unit tests for ConversationActionBar component.
 *
 * Issue #283 — Test IDs: 020, 250, 260, 330, 340, 350, 360
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { ConversationActionBar } from "@/components/shared/conversation/ConversationActionBar"
import { mockConversation, createMockMutations } from "../fixtures"

describe("ConversationActionBar", () => {
  let mutations: ReturnType<typeof createMockMutations>

  beforeEach(() => {
    vi.clearAllMocks()
    mutations = createMockMutations()
  })

  it("020: renders all action buttons for owner", () => {
    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={["hot"]}
        mutations={mutations}
        onBack={vi.fn()}
        pendingAudit={false}
      />
    )

    expect(screen.getByText("Back")).toBeDefined()
    expect(screen.getByText("Poke")).toBeDefined()
    expect(screen.getByText("Audit")).toBeDefined()
    expect(screen.getByText("Snooze")).toBeDefined()
    expect(screen.getByText("Delete")).toBeDefined()
  })

  it("250: Poke button disabled when mutation is pending", () => {
    mutations.pokeMut = createMockMutations().pokeMut
    mutations.pokeMut.isPending = true as any

    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={false}
      />
    )

    const pokeBtn = screen.getByText("Poking...")
    expect(pokeBtn.closest("button")).toHaveProperty("disabled", true)
  })

  it("260: hides all action buttons except Back for non-owner", () => {
    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={false}
        labels={[]}
        mutations={mutations}
        onBack={vi.fn()}
        pendingAudit={false}
      />
    )

    expect(screen.getByText("Back")).toBeDefined()
    expect(screen.queryByText("Poke")).toBeNull()
    expect(screen.queryByText("Audit")).toBeNull()
    expect(screen.queryByText("Snooze")).toBeNull()
    expect(screen.queryByText("Delete")).toBeNull()
  })

  it("330: Delete button does NOT invoke mutation when confirm is cancelled", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false)

    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={false}
      />
    )

    fireEvent.click(screen.getByText("Delete"))

    expect(window.confirm).toHaveBeenCalledWith(
      "Are you sure you want to delete this conversation?"
    )
    expect(mutations.deleteMut.mutate).not.toHaveBeenCalled()
  })

  it("340: Delete button invokes mutation only after confirm is accepted", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true)

    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={false}
      />
    )

    fireEvent.click(screen.getByText("Delete"))

    expect(window.confirm).toHaveBeenCalledWith(
      "Are you sure you want to delete this conversation?"
    )
    expect(mutations.deleteMut.mutate).toHaveBeenCalledTimes(1)
  })

  it("350: Snooze button label matches attention_snoozed state", () => {
    const snoozedConv = { ...mockConversation, attention_snoozed: true }

    render(
      <ConversationActionBar
        conversation={snoozedConv}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={false}
      />
    )

    expect(screen.getByText("Wake")).toBeDefined()
    expect(screen.queryByText("Snooze")).toBeNull()
  })

  it("360: Audit button disabled when is_human_managed", () => {
    const managedConv = { ...mockConversation, is_human_managed: true }

    render(
      <ConversationActionBar
        conversation={managedConv}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={false}
      />
    )

    const auditBtn = screen.getByText("Audit").closest("button")
    expect(auditBtn).toHaveProperty("disabled", true)
  })
})
```

### 6.19 `tests/unit/dashboard/conversation/ConversationFields.test.tsx` (Add)

**Complete file contents:**

```tsx
/**
 * Unit tests for ConversationFields component.
 *
 * Issue #283 — Test IDs: 030, 270
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { ConversationFields } from "@/components/shared/conversation/ConversationFields"
import { mockConversation, createMockMutations } from "../fixtures"

// Mock LabelChips
vi.mock("@/components/shared/LabelChips", () => ({
  LabelChips: ({ labels, onAdd, onRemove }: any) => (
    <div data-testid="label-chips">
      {labels.map((l: string) => <span key={l}>{l}</span>)}
    </div>
  ),
}))

// Mock StateBadge
vi.mock("@/components/shared/StateBadge", () => ({
  StateBadge: ({ state }: any) => <span data-testid="state-badge">{state}</span>,
  HumanManagedBadge: () => <span data-testid="human-managed-badge"></span>,
}))

describe("ConversationFields", () => {
  let mutations: ReturnType<typeof createMockMutations>

  beforeEach(() => {
    vi.clearAllMocks()
    mutations = createMockMutations()
  })

  it("030: renders metadata fields with correct data", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={["hot", "priority"]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByText("Sender:")).toBeDefined()
    expect(screen.getByText(mockConversation.sender_email)).toBeDefined()
    expect(screen.getByText("Subject:")).toBeDefined()
    expect(screen.getByText(mockConversation.subject)).toBeDefined()
    expect(screen.getByText("State:")).toBeDefined()
  })

  it("270: takeover label shows 'Release to AI' when is_human_managed=true", () => {
    const managedConv = { ...mockConversation, is_human_managed: true }

    render(
      <ConversationFields
        conversation={managedConv}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByText("Release to AI")).toBeDefined()
  })

  it("270b: takeover label shows 'Take Over' when is_human_managed=false", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByText("Take Over")).toBeDefined()
  })

  it("hides management toggle for non-owner", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={false}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.queryByText("Take Over")).toBeNull()
    expect(screen.queryByText("Release to AI")).toBeNull()
  })

  it("shows clear button when github_username exists and is owner", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    const clearBtn = screen.getByText("Clear")
    fireEvent.click(clearBtn)
    expect(mutations.clearUsernameMut.mutate).toHaveBeenCalledWith("recruiter123")
  })
})
```

### 6.20 `tests/unit/dashboard/conversation/ComposePanel.test.tsx` (Add)

**Complete file contents:**

```tsx
/**
 * Unit tests for ComposePanel component.
 *
 * Issue #283 — Test IDs: 040, 280
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { ComposePanel } from "@/components/shared/conversation/ComposePanel"
import { mockConversation, createMockMutations } from "../fixtures"

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

import { toast } from "sonner"

describe("ComposePanel", () => {
  let mutations: ReturnType<typeof createMockMutations>

  beforeEach(() => {
    vi.clearAllMocks()
    mutations = createMockMutations()
  })

  it("040: renders compose form for owner", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: test"
        body=""
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    expect(screen.getByText("Compose Reply")).toBeDefined()
    expect(screen.getByPlaceholderText("Type your message...")).toBeDefined()
    expect(screen.getByText("Send Email")).toBeDefined()
    expect(screen.getByText("Attach Files")).toBeDefined()
  })

  it("280: returns null when isOwner=false", () => {
    const { container } = render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={false}
        sendMut={mutations.sendMut as any}
        subject=""
        body=""
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    expect(container.innerHTML).toBe("")
  })

  it("shows error toast when sending with empty body", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: test"
        body=""
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    fireEvent.click(screen.getByText("Send Email"))

    expect(toast.error).toHaveBeenCalledWith("Message body is empty")
    expect(mutations.sendMut.mutate).not.toHaveBeenCalled()
  })

  it("calls sendMut.mutate with correct data when body is not empty", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: test"
        body="Hello there"
        pendingFiles={[{ filename: "file.txt", data: "abc" }]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    fireEvent.click(screen.getByText("Send Email"))

    expect(mutations.sendMut.mutate).toHaveBeenCalledWith({
      subject: "Re: test",
      body: "Hello there",
      attachments: [{ filename: "file.txt", data: "abc" }],
    })
  })
})
```

### 6.21 `tests/unit/dashboard/conversation/AuditResultPanel.test.tsx` (Add)

**Complete file contents:**

```tsx
/**
 * Unit tests for AuditResultPanel component.
 *
 * Issue #283 — Test IDs: 050, 290
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { AuditResultPanel } from "@/components/shared/conversation/AuditResultPanel"
import { mockAuditResult, mockConversation } from "../fixtures"

describe("AuditResultPanel", () => {
  const handlers = {
    onApproveAndSend: vi.fn(),
    onLoadDraft: vi.fn(),
    onApprove: vi.fn(),
    onChangeState: vi.fn(),
    onReject: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("050: renders all audit action buttons", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.getByText("Approve + Send")).toBeDefined()
    expect(screen.getByText("Load Draft")).toBeDefined()
    expect(screen.getByText("Approve")).toBeDefined()
    expect(screen.getByText("Reject")).toBeDefined()
  })

  it("050b: calls correct handler on button clicks", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    fireEvent.click(screen.getByText("Approve + Send"))
    expect(handlers.onApproveAndSend).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText("Load Draft"))
    expect(handlers.onLoadDraft).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText("Reject"))
    expect(handlers.onReject).toHaveBeenCalledTimes(1)
  })

  it("290: all buttons disabled when disabled=true", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={true}
        {...handlers}
      />
    )

    const buttons = screen.getAllByRole("button")
    for (const btn of buttons) {
      expect(btn).toHaveProperty("disabled", true)
    }
  })

  it("hides Load Draft when draft_message is null", () => {
    const auditNoDraft = { ...mockAuditResult, draft_message: null, draft_subject: null }

    render(
      <AuditResultPanel
        audit={auditNoDraft}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.queryByText("Load Draft")).toBeNull()
    expect(screen.queryByText("Approve + Send")).toBeNull()
    expect(screen.getByText("Approve")).toBeDefined()
    expect(screen.getByText("Reject")).toBeDefined()
  })

  it("shows Mark State button when state is incorrect", () => {
    const auditBadState = {
      ...mockAuditResult,
      state_correct: false,
      recommended_state: "closed",
    }

    render(
      <AuditResultPanel
        audit={auditBadState}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    const markBtn = screen.getByText("Mark closed")
    fireEvent.click(markBtn)
    expect(handlers.onChangeState).toHaveBeenCalledWith("closed")
  })
})
```

### 6.22 `tests/unit/dashboard/conversation/AuditHistoryPanel.test.tsx` (Add)

**Complete file contents:**

```tsx
/**
 * Unit tests for AuditHistoryPanel component.
 *
 * Issue #283 — Test ID: 060
 */

import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { AuditHistoryPanel } from "@/components/shared/conversation/AuditHistoryPanel"
import { mockAuditHistoryEntry } from "../fixtures"

describe("AuditHistoryPanel", () => {
  it("060: renders collapsible entries with expand/collapse toggle", () => {
    render(
      <AuditHistoryPanel
        entries={[mockAuditHistoryEntry]}
      />
    )

    expect(screen.getByText("Audit History")).toBeDefined()
    expect(screen.getByText(/approve/)).toBeDefined()

    // Findings should not be visible before expand
    expect(screen.queryByText("Approved after review.")).toBeNull()

    // Click to expand
    fireEvent.click(screen.getByText(/approve/))

    // Now findings should be visible
    expect(screen.getByText("Approved after review.")).toBeDefined()
  })

  it("returns null when entries is empty", () => {
    const { container } = render(
      <AuditHistoryPanel entries={[]} />
    )

    expect(container.innerHTML).toBe("")
  })

  it("renders multiple entries", () => {
    const entries = [
      mockAuditHistoryEntry,
      { ...mockAuditHistoryEntry, id: 2, action: "reject" as const, findings: "Rejected due to tone." },
    ]

    render(
      <AuditHistoryPanel entries={entries} />
    )

    expect(screen.getByText(/approve/)).toBeDefined()
    expect(screen.getByText(/reject/)).toBeDefined()
  })
})
```

### 6.23 `tests/unit/dashboard/conversation/MessageBubble.test.tsx` (Add)

**Complete file contents:**

```tsx
/**
 * Unit tests for MessageBubble component.
 *
 * Issue #283 — Test IDs: 070, 300
 */

import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { MessageBubble } from "@/components/shared/conversation/MessageBubble"
import { mockMessage, mockInboundMessage, mockRating } from "../fixtures"

vi.mock("@/lib/constants", () => ({
  RATING_EMOJIS: ["", "", "", "", ""],
}))

describe("MessageBubble", () => {
  it("070: renders outbound message with rating controls when canUserRate=true", () => {
    const onRate = vi.fn()

    render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={true}
        onRate={onRate}
      />
    )

    expect(screen.getByText("OUTBOUND")).toBeDefined()
    expect(screen.getByText(mockMessage.body)).toBeDefined()

    // Should have 5 rating buttons
    const ratingButtons = screen.getAllByTitle(/Rate \d/)
    expect(ratingButtons.length).toBe(5)
  })

  it("070b: clicking rating button calls onRate", () => {
    const onRate = vi.fn()

    render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={true}
        onRate={onRate}
      />
    )

    fireEvent.click(screen.getByTitle("Rate 4"))
    expect(onRate).toHaveBeenCalledWith(101, 4)
  })

  it("300: rating emojis hidden when canUserRate=false", () => {
    render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    expect(screen.queryByTitle("Rate 1")).toBeNull()
  })

  it("300b: no rating buttons for inbound messages", () => {
    render(
      <MessageBubble
        message={mockInboundMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={true}
        onRate={vi.fn()}
      />
    )

    expect(screen.getByText("INBOUND")).toBeDefined()
    expect(screen.queryByTitle("Rate 1")).toBeNull()
  })

  it("highlights active rating", () => {
    render(
      <MessageBubble
        message={mockMessage}
        rating={mockRating}
        isPreInit={false}
        canUserRate={true}
        onRate={vi.fn()}
      />
    )

    // Rating 4 button should have active class
    const ratingBtn = screen.getByTitle("Rate 4")
    expect(ratingBtn.className).toContain("bg-blue-200")
  })

  it("shows pre-init indicator", () => {
    render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={true}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    expect(screen.getByText(/pre-reinit/)).toBeDefined()
  })
})
```

### 6.24 `tests/e2e/dashboard/conversation-detail.spec.ts` (Verify only)

**No code changes.** Run the existing test file to verify all 14 tests pass:

```bash
npx playwright test tests/e2e/dashboard/conversation-detail.spec.ts
```

The refactor preserves:
- All CSS class names (`.rounded-lg.p-3` for message bubbles)
- All role-based selectors (`button`, `heading`)
- All text content selectors (`Sender:`, `Subject:`, `State:`, `Compose Reply`, etc.)
- All placeholder selectors (`Type your message...`, `GitHub username`)
- DOM nesting structure (table -> tbody -> tr, etc.)

## 7. Pattern References

### 7.1 Existing Mutation Pattern

**File:** `dashboard/src/components/shared/ConversationDetail.tsx` (lines ~98-105)

```tsx
const deleteMut = useMutation({
  mutationFn: () => deleteConversation(convId),
  onSuccess: () => {
    toast.success(`Conversation #${convId} deleted`)
    onDeleted?.()
  },
})
```

**Relevance:** This is the existing inline mutation pattern being extracted. Every mutation in the file follows this same pattern: `useMutation` with `mutationFn`, `onSuccess` (with toast + invalidation), and optional `onError`. The new `useConversationMutations` hook reproduces this exact behavior.

### 7.2 Existing Query Pattern

**File:** `dashboard/src/components/shared/ConversationDetail.tsx` (lines ~68-73)

```tsx
const { data: conv, isLoading, error } = useQuery({
  queryKey: ["conversation", convId],
  queryFn: () => fetchConversation(convId),
})
```

**Relevance:** Queries remain in the orchestrator — they are NOT extracted. This pattern stays unchanged.

### 7.3 Existing Component Import Pattern

**File:** `dashboard/src/components/shared/ConversationDetail.tsx` (lines ~31-33)

```tsx
import { StateBadge, HumanManagedBadge } from "@/components/shared/StateBadge"
import { LabelChips } from "@/components/shared/LabelChips"
```

**Relevance:** Shows the existing pattern for importing shared components from sibling paths. The new child components follow the same `@/components/shared/conversation/ComponentName` import pattern.

### 7.4 Existing API Client Pattern

**File:** `dashboard/src/api/client.ts` (referenced throughout ConversationDetail)

```tsx
import {
  fetchConversation,
  deleteConversation,
  sendMessage,
  addLabel,
  // ... etc
} from "@/api/client"
```

**Relevance:** All API functions are imported from `@/api/client`. The new `useConversationMutations` hook imports these same functions. No API changes needed.

### 7.5 Existing Type Definitions

**File:** `dashboard/src/api/types.ts`

```tsx
import type { Message, Rating, AuditDiagnosis, AuditLogEntry } from "@/api/types"
```

**Relevance:** Existing types are reused in `conversation/types.ts` via re-export. No new types need to be defined for API data — only component prop interfaces are new.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `useMutation`, `useQueryClient`, `useQuery` | `@tanstack/react-query` | `useDrawerAction.ts`, `useConversationMutations.ts`, `ConversationDetail.tsx` |
| `type UseMutationResult` | `@tanstack/react-query` | `types.ts` |
| `toast` | `sonner` | `useDrawerAction.ts`, `ComposePanel.tsx` |
| `useState`, `useEffect`, `useRef` | `react` | `ConversationDetail.tsx`, `AuditHistoryPanel.tsx`, `ComposePanel.tsx` |
| `Button` | `@/components/ui/button` | `ConversationActionBar.tsx`, `ConversationFields.tsx`, `ComposePanel.tsx`, `AuditResultPanel.tsx`, `ConversationDetail.tsx` |
| `Input` | `@/components/ui/input` | `ConversationFields.tsx`, `ComposePanel.tsx` |
| `Textarea` | `@/components/ui/textarea` | `ComposePanel.tsx` |
| `Card`, `CardContent` | `@/components/ui/card` | `ConversationDetail.tsx` |
| `ArrowLeft`, `Trash2` | `lucide-react` | `ConversationActionBar.tsx` |
| `StateBadge`, `HumanManagedBadge` | `@/components/shared/StateBadge` | `ConversationFields.tsx` |
| `LabelChips` | `@/components/shared/LabelChips` | `ConversationFields.tsx` |
| `toCTFull`, `formatBytes` | `@/lib/utils` | `MessageBubble.tsx`, `AuditHistoryPanel.tsx`, `ConversationFields.tsx`, `ComposePanel.tsx` |
| `RATING_EMOJIS` | `@/lib/constants` | `MessageBubble.tsx` |
| `useAuth` | `@/providers/AuthProvider` | `ConversationDetail.tsx` |
| `canWrite`, `canRate` | `@/lib/roles` | `ConversationDetail.tsx` |
| All API functions | `@/api/client` | `useConversationMutations.ts`, `ConversationDetail.tsx` |
| `type Message, Rating, AuditDiagnosis, AuditLogEntry` | `@/api/types` | `types.ts`, `MessageBubble.tsx`, `AuditHistoryPanel.tsx`, `ConversationDetail.tsx` |

**New Dependencies:** None. All imports resolve to existing packages and modules.

## 9. Test Mapping

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

## 10. Implementation Notes

### 10.1 Error Handling Convention

All mutations follow the same error pattern:
- **onSuccess:** Toast success message + query invalidation + optional drawer close
- **onError:** `toast.error(err.message)` — no drawer close, no query invalidation
- **Special case (sendMut):** Checks `res.ok` in onSuccess — may toast error even on HTTP 200 if `res.ok === false`

### 10.2 Mutation Close Behavior Reference

| Mutation | Closes Drawer? | Rationale |
|----------|---------------|-----------|
| pokeMut | No | User may want to see result |
| auditMut | No | Results appear in-place |
| snoozeMut | No | User stays on detail |
| deleteMut | Via `onDeleted` callback | Navigates away |
| addLabelMut | No | User adds multiple labels |
| removeLabelMut | No | User removes multiple labels |
| clearUsernameMut | No | User stays on detail |
| takeoverMut | No | User stays on detail |
| starMut | No | User stays on detail |
| sendMut | No (clears form) | User stays on detail |
| approveMut | No | User stays on detail |
| rejectMut | No | User stays on detail |
| changeStateMut | No | User stays on detail |
| rateMut | No | User rates multiple messages |
| approveAndSendMut | No | User stays on detail |

**Key insight from code analysis:** The existing `ConversationDetail.tsx` does NOT actually close the drawer on most mutations. Only `deleteMut` navigates away (via `onDeleted`). The `useDrawerAction` hook is therefore used primarily for query invalidation and toast messaging, not for drawer closing. The `closeOnSuccess` option should default to `false` in practice for most mutations, with `onClose` being passed only for future use cases.

### 10.3 DOM Structure Preservation

The refactored components MUST preserve the exact DOM structure and CSS classes to keep E2E tests passing. Key selectors used in E2E tests:

| E2E Selector | Component | Must Preserve |
|-------------|-----------|---------------|
| `role="heading" name="Hermes Dashboard"` | Page layout (unchanged) | Yes |
| `text="Conversation #${convId}"` | `ConversationDetail` orchestrator | Yes |
| `text="Sender:"` | `ConversationFields` | Yes |
| `text="Subject:"` | `ConversationFields` | Yes |
| `text="State:"` | `ConversationFields` | Yes |
| `text="Channel:"` | `ConversationFields` | Yes |
| `text="Created:"` | `ConversationFields` | Yes |
| `text="Star:"` | `ConversationFields` | Yes |
| `text="Management:"` | `ConversationFields` | Yes |
| `text="Check Star:"` | `ConversationFields` | Yes |
| `placeholder="GitHub username"` | `ConversationFields` | Yes |
| `role="button" name="Verify"` | `ConversationFields` | Yes |
| `role="button" name=/Take Over\|Release to AI/` | `ConversationFields` | Yes |
| `role="button" name=/Back/` | `ConversationActionBar` | Yes |
| `text="Labels:"` | `ConversationFields` | Yes |
| `text="Compose Reply"` | `ComposePanel` | Yes |
| `placeholder="Type your message..."` | `ComposePanel` | Yes |
| `role="button" name="Send Email"` | `ComposePanel` | Yes |
| `role="button" name="Attach Files"` | `ComposePanel` | Yes |
| `text="Message body is empty"` | `ComposePanel` (toast) | Yes |
| `div.rounded-lg.p-3` | `MessageBubble` | Yes |
| `text=/INBOUND\|OUTBOUND/` | `MessageBubble` | Yes |
| `button.rounded-md` (rating) | `MessageBubble` | Yes |
| `role="heading" name="Messages"` | `ConversationDetail` orchestrator | Yes |
| `role="button" name=/Show Full History\|Show Recent Only/` | `ConversationDetail` orchestrator | Yes |

### 10.4 Important: Conversation Type Shape

The `conv` object returned by `fetchConversation` includes fields beyond what `@/api/types` might formally declare. Based on the current code, the orchestrator accesses these fields on `conv`:

- `conv.messages` — array of Message objects
- `conv.audit_result` — AuditDiagnosis or null
- `conv.last_init_at` — string or null
- `conv.subject`, `conv.id`, `conv.sender_email`, `conv.state`, etc.
- `conv.attention_snoozed`, `conv.is_human_managed`
- `conv.github_username`, `conv.star_verified`
- `conv.channel`

The child components should accept partial types (only the fields they need) via their prop interfaces, not the full `Conversation` type. This is already reflected in the prop definitions in Section 6.

### 10.5 The `createMockMutation` Helper

The `createMockMutation()` helper in fixtures creates objects that satisfy the `UseMutationResult` interface shape for testing. The key property that tests check is `mutate` (a `vi.fn()`), `isPending` (boolean), and `isError` (boolean). Tests should spread mutation overrides like:

```typescript
mutations.pokeMut = { ...createMockMutation(), isPending: true }
```

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 9)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #283 |
| Verdict | DRAFT |
| Date | 2026-03-04 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #283 |
| Verdict | APPROVED |
| Date | 2026-03-04 |
| Iterations | 0 |
| Finalized | 2026-03-04T02:05:21Z |

### Review Feedback Summary

The Implementation Spec is exceptional. It provides complete, copy-paste ready code for every file involved in the refactor, including the orchestrator, child components, hooks, and tests. The logic handles edge cases (like delete confirmation and audit polling) explicitly. Dependency management and type safety are well-addressed.

## Suggestions
- In `ConversationDetail.tsx`, the `useConversationMutations` hook is initialized before the early return for `!conv`. While `conv` will be undefined i...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
src/
  dashboard/
  handlers/
  prompts/
  shared/
tests/
  accessibility/
  benchmark/
  compliance/
  contract/
  e2e/
    dashboard/
  fixtures/
  harness/
  integration/
  security/
  smoke/
  unit/
    dashboard/
      conversation/
      hooks/
  visual/
aws/
  iam/
dashboard/
  public/
  src/
    api/
    assets/
    components/
      admin/
      layout/
      shared/
      ui/
    lib/
      hooks/
    pages/
    providers/
    test/
  components.json
  package.json
  README.md
  tsconfig.app.json
  tsconfig.json
  tsconfig.node.json
data/
  knowledge/
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\Hermes-283\tests\issue_283.spec.ts
import { test, expect } from '@playwright/test';

// Issue #283 - Auto-scaffolded Playwright tests

test('`ConversationActionBar` | `isOwner=true, conversation=mockConv` | Poke, Audit, Snooze, Delete buttons visible', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`ConversationFields` | `conversation=mockConv, isOwner=true` | Sender, Subject, State, Labels rendered', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`ComposePanel` | `isOwner=true` | Subject, body, attach, send visible', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`AuditResultPanel` | `audit=mockAudit, disabled=false` | Approve+Send, Load Draft, Approve, Reject visible', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`AuditHistoryPanel` | `entries=[mockEntry]` | Collapsible entry with expand toggle', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`MessageBubble` | `message=outbound, canUserRate=true` | Direction label + 5 rating emojis', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`useDrawerAction` | `mutationFn=resolves, onClose=fn` | onClose called, toast.success called', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`useDrawerAction` | `mutationFn=rejects` | toast.error called, onClose NOT called', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`useConversationMutations` | `convId=42` | Object with all 15 mutation keys', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`useConversationMutations` | `addLabelMut` | Does NOT call onClose on success', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`useConversationMutations` | `rateMut` | Does NOT call onClose on success', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`useConversationMutations` | `removeLabelMut` | Does NOT call onClose on success', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`ConversationActionBar` | `pokeMut.isPending=true` | Poke button disabled, shows "Poking..."', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`ConversationActionBar` | `isOwner=false` | Only Back visible', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`ConversationFields` | `is_human_managed=true` | Shows "Release to AI"', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`ComposePanel` | `isOwner=false` | Returns null', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`AuditResultPanel` | `disabled=true` | All buttons disabled', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`MessageBubble` | `canUserRate=false` | No rating buttons', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`useAdminAction` | `mutationFn=resolves` | Invalidates attention-queue, audit-preview', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`useAdminAction` | Rendered in hook | Returns mutation with mutate function', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`ConversationActionBar.handleDelete` | `confirm=false` | `deleteMut.mutate` NOT called', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`ConversationActionBar.handleDelete` | `confirm=true` | `deleteMut.mutate` called once', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`ConversationActionBar` | `attention_snoozed=true` | Shows "Wake" label', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});

test('`ConversationActionBar` | `is_human_managed=true` | Audit button disabled', async ({ page }) => {
  // Expected: // TODO: implement assertion
  // TODO: Implement test logic
  await expect(page).toBeTruthy();
});



```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### dashboard/src/components/shared/conversation/types.ts (signatures)

```python
/**
 * Shared TypeScript types for conversation sub-components.
 *
 * Issue #283: Extracted from ConversationDetail.tsx
 *
 * NOTE: Most types (Message, Rating, AuditDiagnosis, AuditLogEntry, Conversation)
 * are already defined in @/api/types. This file re-exports them for convenience
 * and defines component-specific prop interfaces.
 */

import type { UseMutationResult } from "@tanstack/react-query"
import type { Message, Rating, AuditDiagnosis, AuditLogEntry } from "@/api/types"

// Re-export API types for convenience
export type { Message, Rating, AuditDiagnosis, AuditLogEntry }

/** Pending file attachment for compose */
export interface PendingFile {
  filename: string
  data: string // base64
}

/** Return type of useConversationMutations */
export interface ConversationMutations {
  pokeMut: UseMutationResult<unknown, Error, void>
  auditMut: UseMutationResult<unknown, Error, void>
  snoozeMut: UseMutationResult<unknown, Error, void>
  deleteMut: UseMutationResult<unknown, Error, void>
  addLabelMut: UseMutationResult<unknown, Error, string>
  removeLabelMut: UseMutationResult<unknown, Error, string>
  clearUsernameMut: UseMutationResult<unknown, Error, string>
  takeoverMut: UseMutationResult<unknown, Error, boolean>
  starMut: UseMutationResult<unknown, Error, string>
  sendMut: UseMutationResult<unknown, Error, { subject: string; body: string; attachments: PendingFile[] }>
  approveMut: UseMutationResult<unknown, Error, void>
  rejectMut: UseMutationResult<unknown, Error, void>
  changeStateMut: UseMutationResult<unknown, Error, string>
  rateMut: UseMutationResult<unknown, Error, { conversation_id: number; message_id: number; rating: number }>
  approveAndSendMut: UseMutationResult<unknown, Error, void>
}

/** Options for useDrawerAction */
export interface DrawerActionOptions {
  closeOnSuccess?: boolean
  invalidateKeys?: string[][]
  onSuccessMessage?: string
  onSuccessCallback?: (data: unknown) => void
}
# ... (truncated, syntax error in original)

```

### dashboard/src/components/shared/conversation/index.ts (signatures)

```python
export { ConversationActionBar } from "./ConversationActionBar"
export { ConversationFields } from "./ConversationFields"
export { ComposePanel } from "./ComposePanel"
export { AuditResultPanel } from "./AuditResultPanel"
export { AuditHistoryPanel } from "./AuditHistoryPanel"
export { MessageBubble } from "./MessageBubble"
export type { ConversationMutations, PendingFile, DrawerActionOptions } from "./types"
# ... (truncated, syntax error in original)

```

### dashboard/src/lib/hooks/useDrawerAction.ts (signatures)

```python
/**
 * Wraps a TanStack mutation with automatic drawer close and
 * query invalidation on success.
 *
 * Issue #283: Extracted from ConversationDetail.tsx inline mutations.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { UseMutationResult } from "@tanstack/react-query"
import { toast } from "sonner"
import type { DrawerActionOptions } from "@/components/shared/conversation/types"

export function useDrawerAction<TData = unknown, TVariables = void>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  onClose: (() => void) | undefined,
  options?: DrawerActionOptions
): UseMutationResult<TData, Error, TVariables> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn,
    onSuccess: (data) => {
      if (options?.invalidateKeys) {
        for (const key of options.invalidateKeys) {
          queryClient.invalidateQueries({ queryKey: key })
        }
      }
      if (options?.onSuccessMessage) {
        toast.success(options.onSuccessMessage)
      }
      if (options?.onSuccessCallback) {
        options.onSuccessCallback(data)
      }
      if (options?.closeOnSuccess !== false && onClose) {
        onClose()
      }
    },
    onError: (err: Error) => {
      toast.error(err.message)
    },
  })
}
# ... (truncated, syntax error in original)

```

### dashboard/src/lib/hooks/useAdminAction.ts (signatures)

```python
/**
 * Shared mutation wrapper for approve/reject/snooze actions
 * used across admin components.
 *
 * Issue #283: Implemented for ConversationDetail. Wiring to
 * AttentionQueueSection and AuditQueueSection deferred to follow-up.
 */

import type { UseMutationResult } from "@tanstack/react-query"
import { useDrawerAction } from "./useDrawerAction"
import type { DrawerActionOptions } from "@/components/shared/conversation/types"

export function useAdminAction<TData = unknown, TVariables = void>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options?: DrawerActionOptions & { onClose?: () => void }
): UseMutationResult<TData, Error, TVariables> {
  const { onClose, invalidateKeys = [], ...rest } = options ?? {}

  // Admin actions always invalidate queue-related keys
  const mergedKeys = [
    ["attention-queue"],
    ["audit-preview"],
    ...invalidateKeys,
  ]

  return useDrawerAction(mutationFn, onClose, {
    closeOnSuccess: true,
    invalidateKeys: mergedKeys,
    ...rest,
  })
}
# ... (truncated, syntax error in original)

```

### dashboard/src/lib/hooks/useConversationMutations.ts (signatures)

```python
/**
 * Centralizes all conversation mutations with query invalidation.
 *
 * Issue #283: Extracted from ConversationDetail.tsx.
 *
 * IMPORTANT: deleteMut is a raw mutation without a confirmation step.
 * The confirmation dialog (window.confirm) MUST be implemented in the
 * calling component BEFORE invoking deleteMut.mutate().
 */

import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  deleteConversation,
  sendMessage,
  addLabel,
  removeLabel,
  setTakeover,
  checkStar,
  submitRating,
  triggerAudit,
  approveAudit,
  approveAndSendAudit,
  rejectAudit,
  bulkPoke,
  clearGithubUsername,
  addSkipWord,
  patchConversationState,
  snoozeConversation,
} from "@/api/client"
import { toast } from "sonner"
import { useAdminAction } from "./useAdminAction"
import type { PendingFile } from "@/components/shared/conversation/types"

interface ConversationMutationCallbacks {
  onClose?: () => void
  onDeleted?: () => void
  onSendSuccess?: () => void
  onAuditMutate?: () => void
  onAuditSettled?: (success: boolean) => void
  getConversation?: () => { attention_snoozed: boolean } | undefined
  getStarUsername?: () => string
}

export function useConversationMutations(
  conversationId: number,
  callbacks?: ConversationMutationCallbacks
) {
  const convId = conversationId
  const queryClient = useQueryClient()
  const {
# ... (truncated, syntax error in original)

```

### dashboard/src/lib/hooks/index.ts (signatures)

```python
export { useDrawerAction } from "./useDrawerAction"
export { useAdminAction } from "./useAdminAction"
export { useConversationMutations } from "./useConversationMutations"
# ... (truncated, syntax error in original)

```

### dashboard/src/components/shared/conversation/MessageBubble.tsx (signatures)

```python
/**
 * Renders a single message with directional styling,
 * rating emojis, and rating note.
 *
 * Issue #283: Extracted from ConversationDetail.tsx message loop.
 */

import type { Message, Rating } from "@/api/types"
import { toCTFull } from "@/lib/utils"
import { RATING_EMOJIS } from "@/lib/constants"

interface MessageBubbleProps {
  message: Message
  rating: Rating | undefined
  isPreInit: boolean
  canUserRate: boolean
  onRate: (messageId: number, rating: number) => void
}

export function MessageBubble({ message: msg, rating, isPreInit, canUserRate, onRate }: MessageBubbleProps) {
  const isOutbound = msg.direction === "outbound"

  return (
    <div
      className={`rounded-lg p-3 ${
        isOutbound ? "ml-8 bg-blue-50 dark:bg-blue-950/30" : "mr-8 bg-gray-50 dark:bg-gray-800/50"
      } ${isPreInit ? "opacity-50" : ""}`}
    >
      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
        <span className="font-semibold">
          {msg.direction.toUpperCase()}
          {msg.has_resume && "  RESUME"}
          {isPreInit && " (pre-reinit)"}
        </span>
        <span>{toCTFull(msg.created_at)}</span>
      </div>
      {msg.subject && (
        <div className="mb-1 text-xs font-medium text-muted-foreground">
          Subject: {msg.subject}
        </div>
      )}
      <div className="whitespace-pre-wrap text-sm">{msg.body}</div>

      {/* Rating section for outbound messages */}
      {isOutbound && canUserRate && (
        <div className="mt-2 flex items-center gap-1">
          {RATING_EMOJIS.map((emoji: string, idx: number) => (
            <button
              key={idx}
              className={`rounded-md px-2 py-1 text-sm transition-colors ${
# ... (truncated, syntax error in original)

```

### dashboard/src/components/shared/conversation/AuditHistoryPanel.tsx (signatures)

```python
/**
 * Renders collapsible audit history entries.
 *
 * Issue #283: Extracted from ConversationDetail.tsx audit history section.
 */

import { useState } from "react"
import type { AuditLogEntry } from "@/api/types"
import { toCTFull } from "@/lib/utils"

interface AuditHistoryPanelProps {
  entries: AuditLogEntry[]
}

export function AuditHistoryPanel({ entries }: AuditHistoryPanelProps) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  if (!entries || entries.length === 0) return null

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  return (
    <div className="mt-4">
      <h3 className="mb-2 text-sm font-semibold">Audit History</h3>
      <div className="space-y-2">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="rounded border p-2 text-xs"
          >
            <div
              className="flex cursor-pointer items-center justify-between"
              onClick={() => toggleExpand(entry.id)}
            >
              <span className="font-medium">
                {entry.action} — {toCTFull(entry.created_at)}
              </span>
              <span>{expandedIds.has(entry.id) ? "▼" : "▶"}</span>
            </div>
            {expandedIds.has(entry.id) && (
# ... (truncated, syntax error in original)

```

### dashboard/src/components/shared/conversation/ConversationActionBar.tsx (signatures)

```python
/**
 * Action bar: Back, Poke, Audit, Snooze, Interview, Delete.
 *
 * Issue #283: Extracted from ConversationDetail.tsx action button row.
 *
 * SAFETY: handleDelete includes mandatory window.confirm() gate
 * BEFORE calling deleteMut.mutate(). This matches existing behavior.
 */

import { Button } from "@/components/ui/button"
import { ArrowLeft, Trash2 } from "lucide-react"
import type { ConversationMutations } from "./types"

interface ConversationActionBarProps {
  conversation: {
    id: number
    is_human_managed: boolean
    attention_snoozed: boolean
  }
  isOwner: boolean
  labels: string[]
  mutations: Pick<ConversationMutations, "pokeMut" | "auditMut" | "snoozeMut" | "addLabelMut" | "deleteMut">
  onBack?: () => void
  pendingAudit: boolean
}

export function ConversationActionBar({
  conversation: conv,
  isOwner,
  labels,
  mutations,
  onBack,
  pendingAudit,
}: ConversationActionBarProps) {
  const { pokeMut, auditMut, snoozeMut, deleteMut } = mutations

  /**
   * SAFETY-CRITICAL: Confirmation gate for destructive action.
   * window.confirm is synchronous — cannot be bypassed by race conditions.
   */
  const handleDelete = () => {
    if (!window.confirm("Are you sure you want to delete this conversation?")) {
      return
    }
    deleteMut.mutate()
  }

  return (
    <div className="mb-4 flex items-center gap-2">
      {onBack && (
# ... (truncated, syntax error in original)

```

### dashboard/src/components/shared/conversation/ConversationFields.tsx (signatures)

```python
/**
 * Metadata fields: sender, subject, state, labels, takeover, star check.
 *
 * Issue #283: Extracted from ConversationDetail.tsx metadata section.
 */

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { StateBadge, HumanManagedBadge } from "@/components/shared/StateBadge"
import { LabelChips } from "@/components/shared/LabelChips"
import { toCTFull } from "@/lib/utils"
import type { ConversationMutations } from "./types"

interface ConversationFieldsProps {
  conversation: {
    id: number
    sender_email: string
    subject: string
    state: string
    channel?: string
    created_at: string
    updated_at: string
    github_username: string | null
    is_human_managed: boolean
    star_verified: boolean
    attention_snoozed: boolean
    last_intent: string
  }
  isOwner: boolean
  labels: string[]
  starUsername: string
  onStarUsernameChange: (username: string) => void
  mutations: Pick<ConversationMutations,
    "clearUsernameMut" | "addLabelMut" | "removeLabelMut" | "takeoverMut" | "starMut">
}

export function ConversationFields({
  conversation: conv,
  isOwner,
  labels,
  starUsername,
  onStarUsernameChange,
  mutations,
}: ConversationFieldsProps) {
  const { clearUsernameMut, addLabelMut, removeLabelMut, takeoverMut, starMut } = mutations

  return (
    <div className="space-y-2 text-sm">
      <div>
        <span className="font-semibold">Sender:</span> {conv.sender_email}
# ... (truncated, syntax error in original)

```

### dashboard/src/components/shared/conversation/ComposePanel.tsx (signatures)

```python
/**
 * Email compose form: subject, body, file attach, send button.
 * Owner-only visibility.
 *
 * Issue #283: Extracted from ConversationDetail.tsx compose section.
 */

import { useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"
import type { ConversationMutations, PendingFile } from "./types"

interface ComposePanelProps {
  conversation: { id: number }
  isOwner: boolean
  sendMut: ConversationMutations["sendMut"]
  subject: string
  body: string
  pendingFiles: PendingFile[]
  onSubjectChange: (subject: string) => void
  onBodyChange: (body: string) => void
  onFilesChange: (files: PendingFile[]) => void
}

export function ComposePanel({
  isOwner,
  sendMut,
  subject,
  body,
  pendingFiles,
  onSubjectChange,
  onBodyChange,
  onFilesChange,
}: ComposePanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  if (!isOwner) return null

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const newPending: PendingFile[] = []
    files.forEach((file) => {
      const reader = new FileReader()
      reader.onload = (ev) => {
        const result = ev.target?.result as string
        newPending.push({ filename: file.name, data: result.split(",")[1] })
        if (newPending.length === files.length) {
          onFilesChange(newPending)
# ... (truncated, syntax error in original)

```

### dashboard/src/components/shared/conversation/AuditResultPanel.tsx (signatures)

```python
/**
 * Audit result actions: Approve+Send, Load Draft, Approve, Mark State, Reject.
 *
 * Issue #283: Extracted from ConversationDetail.tsx audit result section.
 */

import { Button } from "@/components/ui/button"
import type { AuditDiagnosis } from "@/api/types"

interface AuditResultPanelProps {
  audit: AuditDiagnosis
  conversation: { id: number; state: string }
  disabled: boolean
  onApproveAndSend: () => void
  onLoadDraft: () => void
  onApprove: () => void
  onChangeState: (state: string) => void
  onReject: () => void
}

export function AuditResultPanel({
  audit,
  conversation: conv,
  disabled,
  onApproveAndSend,
  onLoadDraft,
  onApprove,
  onChangeState,
  onReject,
}: AuditResultPanelProps) {
  return (
    <div className="mt-4 rounded border border-purple-300 bg-purple-50 p-3 dark:border-purple-700 dark:bg-purple-950/30">
      <h3 className="mb-2 text-sm font-semibold text-purple-700 dark:text-purple-300">
        Audit Result
      </h3>

      {/* Findings */}
      <div className="mb-2 whitespace-pre-wrap text-xs text-muted-foreground">
        {audit.findings}
      </div>

      {/* State recommendation */}
      {!audit.state_correct && audit.recommended_state && (
        <div className="mb-2 text-xs">
          <span className="font-semibold text-orange-600">
            Recommended state: {audit.recommended_state}
          </span>
          {" "}(current: {conv.state})
        </div>
      )}
# ... (truncated, syntax error in original)

```

### dashboard/src/components/shared/ConversationDetail.tsx (signatures)

```python
/**
 * ConversationDetail orchestrator — composes extracted child components.
 *
 * Issue #283: Reduced from 1132 lines to ~200 lines.
 */

import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  fetchConversation,
  fetchLabels,
  fetchRatings,
  fetchAuditHistory,
} from "@/api/client"
import type { Message, Rating, AuditDiagnosis } from "@/api/types"
import { useAuth } from "@/providers/AuthProvider"
import { canWrite, canRate } from "@/lib/roles"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useConversationMutations } from "@/lib/hooks"
import {
  ConversationActionBar,
  ConversationFields,
  ComposePanel,
  AuditResultPanel,
  AuditHistoryPanel,
  MessageBubble,
} from "./conversation"

interface ConversationDetailProps {
  conversationId: number
  onBack?: () => void
  onDeleted?: () => void
  onClose?: () => void
}

export function ConversationDetail({ conversationId, onBack, onDeleted, onClose }: ConversationDetailProps) {
  const convId = conversationId
  const { role } = useAuth()
  const isOwner = canWrite(role)

  // Local state
  const [showFullHistory, setShowFullHistory] = useState(true)
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [starUsername, setStarUsername] = useState("")
  const [pendingFiles, setPendingFiles] = useState<Array<{ filename: string; data: string }>>([])
  const [pendingAudit, setPendingAudit] = useState(false)

  // Queries
# ... (truncated, syntax error in original)

```

### tests/unit/dashboard/fixtures.ts (signatures)

```python
/**
 * Shared test fixtures for dashboard unit tests.
 *
 * Issue #283
 */

import type { AuditDiagnosis, AuditLogEntry, Message, Rating } from "@/api/types"

export const mockConversation = {
  id: 42,
  sender_email: "recruiter@example.com",
  subject: "Exciting Opportunity",
  state: "engaging",
  last_intent: "star_interest",
  last_rating: null,
  labels: "hot,priority",
  star_verified: false,
  github_username: "recruiter123",
  is_human_managed: false,
  attention_snoozed: false,
  updated_at: "2026-03-01T12:00:00Z",
  created_at: "2026-02-28T10:00:00Z",
  channel: "email",
  messages: [] as Message[],
  audit_result: null as AuditDiagnosis | null,
  last_init_at: null as string | null,
}

export const mockMessage: Message = {
  id: 101,
  conversation_id: 42,
  direction: "outbound",
  subject: "Re: Exciting Opportunity",
  body: "Thanks for reaching out! Have you seen our repo?",
  created_at: "2026-03-01T12:00:00Z",
  has_resume: false,
}

export const mockInboundMessage: Message = {
  id: 100,
  conversation_id: 42,
  direction: "inbound",
  subject: "Exciting Opportunity",
  body: "Hi, I found your profile and wanted to reach out...",
  created_at: "2026-02-28T10:30:00Z",
  has_resume: false,
}

export const mockRating: Rating = {
  message_id: 101,
# ... (truncated, syntax error in original)

```

### tests/unit/dashboard/hooks/useDrawerAction.test.ts (signatures)

```python
/**
 * Unit tests for useDrawerAction hook.
 *
 * Issue #283 — Test IDs: 080, 090
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createElement } from "react"
import { useDrawerAction } from "@/lib/hooks/useDrawerAction"

// Mock sonner toast
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { toast } from "sonner"

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe("useDrawerAction", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("080: closes drawer on mutation success when closeOnSuccess is true", async () => {
    const onClose = vi.fn()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useDrawerAction(mutationFn, onClose, {
        closeOnSuccess: true,
        onSuccessMessage: "Done!",
      }),
      { wrapper: createWrapper() }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })
# ... (truncated, syntax error in original)

```

### tests/unit/dashboard/hooks/useAdminAction.test.ts (full)

```python
/**
 * Unit tests for useAdminAction hook.
 *
 * Issue #283 — Test IDs: 310, 320
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createElement } from "react"
import { useAdminAction } from "@/lib/hooks/useAdminAction"

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { toast } from "sonner"

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return {
    wrapper: ({ children }: { children: React.ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children),
    queryClient,
  }
}

describe("useAdminAction", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("310: invalidates attention-queue and audit-preview on success", async () => {
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction(mutationFn, {
        closeOnSuccess: false,
        onSuccessMessage: "Approved",
      }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["attention-queue"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["audit-preview"] })
  })

  it("310b: merges additional invalidateKeys with queue keys", async () => {
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction(mutationFn, {
        closeOnSuccess: false,
        invalidateKeys: [["conversation", "42"]],
      }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["attention-queue"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["audit-preview"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["conversation", "42"] })
  })

  it("320: returns a mutation result that can be used in components", async () => {
    const { wrapper } = createWrapper()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction(mutationFn, { closeOnSuccess: false }),
      { wrapper }
    )

    expect(result.current.mutate).toBeDefined()
    expect(typeof result.current.mutate).toBe("function")
    expect(result.current.isPending).toBe(false)
    expect(result.current.isError).toBe(false)
  })

  it("shows success toast when onSuccessMessage is provided", async () => {
    const { wrapper } = createWrapper()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction(mutationFn, {
        closeOnSuccess: false,
        onSuccessMessage: "Audit approved",
      }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(toast.success).toHaveBeenCalledWith("Audit approved")
  })

  it("shows error toast on mutation failure", async () => {
    const { wrapper } = createWrapper()
    const mutationFn = vi.fn().mockRejectedValue(new Error("Server error"))

    const { result } = renderHook(
      () => useAdminAction(mutationFn, { closeOnSuccess: false }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(toast.error).toHaveBeenCalledWith("Server error")
  })

  it("calls onClose when closeOnSuccess is true (default) and onClose is provided", async () => {
    const { wrapper } = createWrapper()
    const onClose = vi.fn()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction(mutationFn, {
        onClose,
        onSuccessMessage: "Done",
      }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("does not call onClose when onClose is undefined", async () => {
    const { wrapper } = createWrapper()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction(mutationFn, {
        onClose: undefined,
        closeOnSuccess: false,
      }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    // Should not throw — onClose is undefined
    expect(mutationFn).toHaveBeenCalled()
  })

  it("works with no options provided", async () => {
    const { wrapper } = createWrapper()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction(mutationFn),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(mutationFn).toHaveBeenCalled()
  })

  it("passes variables through to mutationFn", async () => {
    const { wrapper } = createWrapper()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useAdminAction<{ ok: boolean }, string>(mutationFn, {
        closeOnSuccess: false,
      }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate("test-variable")
    })

    expect(mutationFn).toHaveBeenCalledWith("test-variable")
  })
})
```

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the TypeScript code.

```typescript
# Your TypeScript code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the TypeScript code in a single fenced code block

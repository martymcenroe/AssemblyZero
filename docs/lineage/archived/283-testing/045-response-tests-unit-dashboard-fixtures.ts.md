

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

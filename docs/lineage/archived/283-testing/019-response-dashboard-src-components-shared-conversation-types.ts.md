

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

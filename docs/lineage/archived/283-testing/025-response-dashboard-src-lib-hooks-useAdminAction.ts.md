

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

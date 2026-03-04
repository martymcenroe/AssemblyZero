

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

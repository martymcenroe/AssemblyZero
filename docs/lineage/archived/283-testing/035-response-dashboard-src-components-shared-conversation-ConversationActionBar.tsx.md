

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

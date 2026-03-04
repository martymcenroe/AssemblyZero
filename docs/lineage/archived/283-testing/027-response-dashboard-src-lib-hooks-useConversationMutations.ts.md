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

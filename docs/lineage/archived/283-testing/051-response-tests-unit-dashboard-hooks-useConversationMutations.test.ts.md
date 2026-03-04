

```typescript
/**
 * Unit tests for useConversationMutations hook.
 *
 * Issue #283 — Test IDs: 100, 110, 120, 130
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createElement } from "react"
import { useConversationMutations } from "@/lib/hooks/useConversationMutations"

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

import { toast } from "sonner"

vi.mock("@/api/client", () => ({
  deleteConversation: vi.fn().mockResolvedValue({}),
  sendMessage: vi.fn().mockResolvedValue({ ok: true, sendVia: "smtp" }),
  addLabel: vi.fn().mockResolvedValue({}),
  removeLabel: vi.fn().mockResolvedValue({}),
  setTakeover: vi.fn().mockResolvedValue({}),
  checkStar: vi.fn().mockResolvedValue({ starred: true }),
  submitRating: vi.fn().mockResolvedValue({}),
  triggerAudit: vi.fn().mockResolvedValue({ success: 1, results: [] }),
  approveAudit: vi.fn().mockResolvedValue({}),
  approveAndSendAudit: vi.fn().mockResolvedValue({}),
  rejectAudit: vi.fn().mockResolvedValue({}),
  bulkPoke: vi.fn().mockResolvedValue({ success: 1, results: [] }),
  clearGithubUsername: vi.fn().mockResolvedValue({}),
  addSkipWord: vi.fn().mockResolvedValue({}),
  patchConversationState: vi.fn().mockResolvedValue({}),
  snoozeConversation: vi.fn().mockResolvedValue({}),
}))

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

describe("useConversationMutations", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("100: returns all 15 mutation objects", () => {
    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
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
    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    expect(typeof result.current.pokeMut.mutate).toBe("function")
    expect(typeof result.current.deleteMut.mutate).toBe("function")
    expect(typeof result.current.sendMut.mutate).toBe("function")
    expect(typeof result.current.auditMut.mutate).toBe("function")
    expect(typeof result.current.snoozeMut.mutate).toBe("function")
    expect(typeof result.current.addLabelMut.mutate).toBe("function")
    expect(typeof result.current.removeLabelMut.mutate).toBe("function")
    expect(typeof result.current.clearUsernameMut.mutate).toBe("function")
    expect(typeof result.current.takeoverMut.mutate).toBe("function")
    expect(typeof result.current.starMut.mutate).toBe("function")
    expect(typeof result.current.approveMut.mutate).toBe("function")
    expect(typeof result.current.rejectMut.mutate).toBe("function")
    expect(typeof result.current.changeStateMut.mutate).toBe("function")
    expect(typeof result.current.rateMut.mutate).toBe("function")
    expect(typeof result.current.approveAndSendMut.mutate).toBe("function")
  })

  it("110: addLabelMut does not call onClose (stays open)", async () => {
    const { wrapper, queryClient } = createWrapper()
    const onClose = vi.fn()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const { result } = renderHook(
      () => useConversationMutations(42, { onClose }),
      { wrapper }
    )

    await act(async () => {
      result.current.addLabelMut.mutate("hot")
    })

    expect(onClose).not.toHaveBeenCalled()
    expect(addLabel).toHaveBeenCalledWith(42, "hot")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["labels", 42] })
  })

  it("120: rateMut does not call onClose (stays open)", async () => {
    const { wrapper } = createWrapper()
    const onClose = vi.fn()

    const { result } = renderHook(
      () => useConversationMutations(42, { onClose }),
      { wrapper }
    )

    await act(async () => {
      result.current.rateMut.mutate({ conversation_id: 42, message_id: 101, rating: 4 })
    })

    expect(onClose).not.toHaveBeenCalled()
    expect(submitRating).toHaveBeenCalledWith({ conversation_id: 42, message_id: 101, rating: 4 })
  })

  it("130: removeLabelMut does not call onClose (stays open)", async () => {
    const { wrapper, queryClient } = createWrapper()
    const onClose = vi.fn()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const { result } = renderHook(
      () => useConversationMutations(42, { onClose }),
      { wrapper }
    )

    await act(async () => {
      result.current.removeLabelMut.mutate("hot")
    })

    expect(onClose).not.toHaveBeenCalled()
    expect(removeLabel).toHaveBeenCalledWith(42, "hot")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["labels", 42] })
  })

  it("deleteMut calls onDeleted on success", async () => {
    const { wrapper } = createWrapper()
    const onDeleted = vi.fn()

    const { result } = renderHook(
      () => useConversationMutations(42, { onDeleted }),
      { wrapper }
    )

    await act(async () => {
      result.current.deleteMut.mutate()
    })

    expect(deleteConversation).toHaveBeenCalledWith(42)
    expect(onDeleted).toHaveBeenCalledTimes(1)
    expect(toast.success).toHaveBeenCalledWith("Conversation #42 deleted")
  })

  it("sendMut calls onSendSuccess and shows toast on success", async () => {
    const { wrapper } = createWrapper()
    const onSendSuccess = vi.fn()

    const { result } = renderHook(
      () => useConversationMutations(42, { onSendSuccess }),
      { wrapper }
    )

    await act(async () => {
      result.current.sendMut.mutate({
        subject: "Re: Test",
        body: "Hello",
        attachments: [],
      })
    })

    expect(sendMessage).toHaveBeenCalledWith(42, {
      subject: "Re: Test",
      body: "Hello",
      attachments: [],
    })
    expect(onSendSuccess).toHaveBeenCalledTimes(1)
    expect(toast.success).toHaveBeenCalledWith("Email sent via smtp")
  })

  it("sendMut shows error toast when res.ok is false", async () => {
    const { wrapper } = createWrapper()
    vi.mocked(sendMessage).mockResolvedValueOnce({ ok: false, error: "Rate limited" })

    const onSendSuccess = vi.fn()

    const { result } = renderHook(
      () => useConversationMutations(42, { onSendSuccess }),
      { wrapper }
    )

    await act(async () => {
      result.current.sendMut.mutate({
        subject: "Re: Test",
        body: "Hello",
        attachments: [],
      })
    })

    expect(onSendSuccess).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenCalledWith("Send failed: Rate limited")
  })

  it("sendMut does not call onClose", async () => {
    const { wrapper } = createWrapper()
    const onClose = vi.fn()

    const { result } = renderHook(
      () => useConversationMutations(42, { onClose }),
      { wrapper }
    )

    await act(async () => {
      result.current.sendMut.mutate({
        subject: "Re: Test",
        body: "Hello",
        attachments: [],
      })
    })

    expect(onClose).not.toHaveBeenCalled()
  })

  it("takeoverMut calls setTakeover and shows toast", async () => {
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.takeoverMut.mutate(true)
    })

    expect(setTakeover).toHaveBeenCalledWith(42, true)
    expect(toast.success).toHaveBeenCalledWith("Management updated")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["conversation", 42] })
  })

  it("starMut calls checkStar with username and shows toast", async () => {
    const { wrapper } = createWrapper()
    const getStarUsername = vi.fn().mockReturnValue("testuser")

    const { result } = renderHook(
      () => useConversationMutations(42, { getStarUsername }),
      { wrapper }
    )

    await act(async () => {
      result.current.starMut.mutate("testuser")
    })

    expect(checkStar).toHaveBeenCalledWith(42, "testuser")
    expect(toast.success).toHaveBeenCalledWith("testuser starred AssemblyZero!")
  })

  it("starMut shows non-starred toast when result is false", async () => {
    const { wrapper } = createWrapper()
    vi.mocked(checkStar).mockResolvedValueOnce({ starred: false })
    const getStarUsername = vi.fn().mockReturnValue("testuser")

    const { result } = renderHook(
      () => useConversationMutations(42, { getStarUsername }),
      { wrapper }
    )

    await act(async () => {
      result.current.starMut.mutate("testuser")
    })

    expect(toast).toHaveBeenCalledWith("testuser has NOT starred yet — username saved")
  })

  it("clearUsernameMut calls clearGithubUsername and addSkipWord", async () => {
    const { wrapper } = createWrapper()

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.clearUsernameMut.mutate("recruiter123")
    })

    expect(clearGithubUsername).toHaveBeenCalledWith(42)
    expect(addSkipWord).toHaveBeenCalledWith("recruiter123")
    expect(toast.success).toHaveBeenCalledWith("Username cleared and added to skip list")
  })

  it("clearUsernameMut shows error toast on failure", async () => {
    const { wrapper } = createWrapper()
    vi.mocked(clearGithubUsername).mockRejectedValueOnce(new Error("DB error"))

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.clearUsernameMut.mutate("recruiter123")
    })

    expect(toast.error).toHaveBeenCalledWith("Clear failed: DB error")
  })

  it("pokeMut calls bulkPoke and shows toast on success", async () => {
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.pokeMut.mutate()
    })

    expect(bulkPoke).toHaveBeenCalledWith([42])
    expect(toast.success).toHaveBeenCalledWith("Poke sent")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["conversation", 42] })
  })

  it("pokeMut shows error toast when success is 0", async () => {
    const { wrapper } = createWrapper()
    vi.mocked(bulkPoke).mockResolvedValueOnce({ success: 0, results: [{ error: "no email" }] })

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.pokeMut.mutate()
    })

    expect(toast.error).toHaveBeenCalledWith("Poke failed: no email")
  })

  it("auditMut calls onAuditMutate on mutate and onAuditSettled on success", async () => {
    const { wrapper } = createWrapper()
    const onAuditMutate = vi.fn()
    const onAuditSettled = vi.fn()

    const { result } = renderHook(
      () => useConversationMutations(42, { onAuditMutate, onAuditSettled }),
      { wrapper }
    )

    await act(async () => {
      result.current.auditMut.mutate()
    })

    expect(triggerAudit).toHaveBeenCalledWith([42])
    expect(onAuditMutate).toHaveBeenCalledTimes(1)
    expect(onAuditSettled).toHaveBeenCalledWith(true)
    expect(toast.success).toHaveBeenCalledWith("Audit queued — results appear shortly")
  })

  it("auditMut calls onAuditSettled(false) on failure", async () => {
    const { wrapper } = createWrapper()
    vi.mocked(triggerAudit).mockRejectedValueOnce(new Error("Timeout"))
    const onAuditMutate = vi.fn()
    const onAuditSettled = vi.fn()

    const { result } = renderHook(
      () => useConversationMutations(42, { onAuditMutate, onAuditSettled }),
      { wrapper }
    )

    await act(async () => {
      result.current.auditMut.mutate()
    })

    expect(onAuditSettled).toHaveBeenCalledWith(false)
    expect(toast.error).toHaveBeenCalledWith("Audit error: Timeout")
  })

  it("auditMut calls onAuditSettled(false) when success is 0", async () => {
    const { wrapper } = createWrapper()
    vi.mocked(triggerAudit).mockResolvedValueOnce({ success: 0, results: [{ error: "locked" }] })
    const onAuditSettled = vi.fn()

    const { result } = renderHook(
      () => useConversationMutations(42, { onAuditSettled }),
      { wrapper }
    )

    await act(async () => {
      result.current.auditMut.mutate()
    })

    expect(onAuditSettled).toHaveBeenCalledWith(false)
    expect(toast.error).toHaveBeenCalledWith("Audit failed: locked")
  })

  it("snoozeMut uses getConversation to determine toggle direction", async () => {
    const { wrapper } = createWrapper()
    const getConversation = vi.fn().mockReturnValue({ attention_snoozed: false })

    const { result } = renderHook(
      () => useConversationMutations(42, { getConversation }),
      { wrapper }
    )

    await act(async () => {
      result.current.snoozeMut.mutate()
    })

    expect(snoozeConversation).toHaveBeenCalledWith(42, true)
    expect(toast.success).toHaveBeenCalledWith("Snoozed — will resurface if they write back")
  })

  it("snoozeMut shows unsnoozed toast when already snoozed", async () => {
    const { wrapper } = createWrapper()
    const getConversation = vi.fn().mockReturnValue({ attention_snoozed: true })

    const { result } = renderHook(
      () => useConversationMutations(42, { getConversation }),
      { wrapper }
    )

    await act(async () => {
      result.current.snoozeMut.mutate()
    })

    expect(snoozeConversation).toHaveBeenCalledWith(42, false)
    expect(toast.success).toHaveBeenCalledWith("Unsnoozed")
  })

  it("approveMut calls approveAudit", async () => {
    const { wrapper } = createWrapper()

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.approveMut.mutate()
    })

    expect(approveAudit).toHaveBeenCalledWith(42)
  })

  it("rejectMut calls rejectAudit", async () => {
    const { wrapper } = createWrapper()

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.rejectMut.mutate()
    })

    expect(rejectAudit).toHaveBeenCalledWith(42)
  })

  it("approveAndSendMut calls approveAndSendAudit", async () => {
    const { wrapper } = createWrapper()

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.approveAndSendMut.mutate()
    })

    expect(approveAndSendAudit).toHaveBeenCalledWith(42)
  })

  it("changeStateMut calls patchConversationState and shows toast", async () => {
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.changeStateMut.mutate("closed")
    })

    expect(patchConversationState).toHaveBeenCalledWith(42, "closed")
    expect(toast.success).toHaveBeenCalledWith("State updated")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["conversation", 42] })
  })

  it("works with no callbacks provided", () => {
    const { wrapper } = createWrapper()

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    expect(result.current.pokeMut).toBeDefined()
    expect(result.current.deleteMut).toBeDefined()
  })

  it("snoozeMut handles undefined getConversation gracefully", async () => {
    const { wrapper } = createWrapper()

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.snoozeMut.mutate()
    })

    // With no getConversation, conv is undefined, so !undefined?.attention_snoozed = true
    expect(snoozeConversation).toHaveBeenCalledWith(42, true)
  })

  it("starMut uses fallback username when getStarUsername is not provided", async () => {
    const { wrapper } = createWrapper()

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.starMut.mutate("someuser")
    })

    expect(checkStar).toHaveBeenCalledWith(42, "someuser")
    expect(toast.success).toHaveBeenCalledWith("User starred AssemblyZero!")
  })

  it("pokeMut does not call onClose", async () => {
    const { wrapper } = createWrapper()
    const onClose = vi.fn()

    const { result } = renderHook(
      () => useConversationMutations(42, { onClose }),
      { wrapper }
    )

    await act(async () => {
      result.current.pokeMut.mutate()
    })

    expect(onClose).not.toHaveBeenCalled()
  })

  it("pokeMut shows error toast on network error", async () => {
    const { wrapper } = createWrapper()
    vi.mocked(bulkPoke).mockRejectedValueOnce(new Error("Network failure"))

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.pokeMut.mutate()
    })

    expect(toast.error).toHaveBeenCalledWith("Poke error: Network failure")
  })

  it("sendMut shows error toast on network error", async () => {
    const { wrapper } = createWrapper()
    vi.mocked(sendMessage).mockRejectedValueOnce(new Error("Connection refused"))

    const { result } = renderHook(
      () => useConversationMutations(42),
      { wrapper }
    )

    await act(async () => {
      result.current.sendMut.mutate({
        subject: "Test",
        body: "Hello",
        attachments: [],
      })
    })

    expect(toast.error).toHaveBeenCalledWith("Send failed: Connection refused")
  })
})
```



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

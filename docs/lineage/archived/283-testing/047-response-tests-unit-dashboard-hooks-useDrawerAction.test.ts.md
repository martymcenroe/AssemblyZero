

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

  it("calls onSuccessCallback with mutation data on success", async () => {
    const onSuccessCallback = vi.fn()
    const responseData = { id: 1, status: "ok" }
    const mutationFn = vi.fn().mockResolvedValue(responseData)

    const { result } = renderHook(
      () => useDrawerAction(mutationFn, undefined, {
        closeOnSuccess: false,
        onSuccessCallback,
      }),
      { wrapper: createWrapper() }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(onSuccessCallback).toHaveBeenCalledWith(responseData)
  })

  it("does not toast success when onSuccessMessage is not provided", async () => {
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useDrawerAction(mutationFn, undefined, { closeOnSuccess: false }),
      { wrapper: createWrapper() }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(toast.success).not.toHaveBeenCalled()
  })

  it("does not invalidate queries when invalidateKeys is not provided", async () => {
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })
    const queryClient = new QueryClient()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const wrapper = ({ children }: { children: React.ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children)

    const { result } = renderHook(
      () => useDrawerAction(mutationFn, undefined, { closeOnSuccess: false }),
      { wrapper }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    expect(invalidateSpy).not.toHaveBeenCalled()
  })

  it("closes drawer by default when closeOnSuccess is not specified and onClose exists", async () => {
    const onClose = vi.fn()
    const mutationFn = vi.fn().mockResolvedValue({ ok: true })

    const { result } = renderHook(
      () => useDrawerAction(mutationFn, onClose),
      { wrapper: createWrapper() }
    )

    await act(async () => {
      result.current.mutate(undefined as never)
    })

    // Default behavior: closeOnSuccess !== false is true, so onClose should be called
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
```

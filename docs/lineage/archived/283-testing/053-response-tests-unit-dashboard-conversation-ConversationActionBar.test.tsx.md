

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
    mutations.pokeMut = { ...mutations.pokeMut, isPending: true as any }

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

  it("Audit button disabled when pendingAudit is true", () => {
    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={true}
      />
    )

    const auditBtn = screen.getByText("Auditing...").closest("button")
    expect(auditBtn).toHaveProperty("disabled", true)
  })

  it("Poke button calls pokeMut.mutate on click", () => {
    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={false}
      />
    )

    fireEvent.click(screen.getByText("Poke"))
    expect(mutations.pokeMut.mutate).toHaveBeenCalledTimes(1)
  })

  it("Audit button calls auditMut.mutate on click", () => {
    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={false}
      />
    )

    fireEvent.click(screen.getByText("Audit"))
    expect(mutations.auditMut.mutate).toHaveBeenCalledTimes(1)
  })

  it("Snooze button calls snoozeMut.mutate on click", () => {
    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={false}
      />
    )

    fireEvent.click(screen.getByText("Snooze"))
    expect(mutations.snoozeMut.mutate).toHaveBeenCalledTimes(1)
  })

  it("Back button calls onBack when provided", () => {
    const onBack = vi.fn()

    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        onBack={onBack}
        pendingAudit={false}
      />
    )

    fireEvent.click(screen.getByText("Back"))
    expect(onBack).toHaveBeenCalledTimes(1)
  })

  it("Back button hidden when onBack is not provided", () => {
    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={false}
      />
    )

    expect(screen.queryByText("Back")).toBeNull()
  })

  it("Delete button shows 'Deleting...' when mutation is pending", () => {
    mutations.deleteMut = { ...mutations.deleteMut, isPending: true as any }

    render(
      <ConversationActionBar
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        mutations={mutations}
        pendingAudit={false}
      />
    )

    const deleteBtn = screen.getByText("Deleting...")
    expect(deleteBtn.closest("button")).toHaveProperty("disabled", true)
  })
})
```

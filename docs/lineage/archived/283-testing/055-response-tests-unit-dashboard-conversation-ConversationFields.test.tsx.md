

```tsx
/**
 * Unit tests for ConversationFields component.
 *
 * Issue #283 — Test IDs: 030, 270
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { ConversationFields } from "@/components/shared/conversation/ConversationFields"
import { mockConversation, createMockMutations } from "../fixtures"

// Mock LabelChips
vi.mock("@/components/shared/LabelChips", () => ({
  LabelChips: ({ labels, onAdd, onRemove }: any) => (
    <div data-testid="label-chips">
      {labels.map((l: string) => <span key={l}>{l}</span>)}
    </div>
  ),
}))

// Mock StateBadge
vi.mock("@/components/shared/StateBadge", () => ({
  StateBadge: ({ state }: any) => <span data-testid="state-badge">{state}</span>,
  HumanManagedBadge: () => <span data-testid="human-managed-badge"></span>,
}))

describe("ConversationFields", () => {
  let mutations: ReturnType<typeof createMockMutations>

  beforeEach(() => {
    vi.clearAllMocks()
    mutations = createMockMutations()
  })

  it("030: renders metadata fields with correct data", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={["hot", "priority"]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByText("Sender:")).toBeDefined()
    expect(screen.getByText(mockConversation.sender_email)).toBeDefined()
    expect(screen.getByText("Subject:")).toBeDefined()
    expect(screen.getByText(mockConversation.subject)).toBeDefined()
    expect(screen.getByText("State:")).toBeDefined()
    expect(screen.getByText("Channel:")).toBeDefined()
    expect(screen.getByText("Created:")).toBeDefined()
    expect(screen.getByText("Updated:")).toBeDefined()
    expect(screen.getByText("Intent:")).toBeDefined()
    expect(screen.getByText("Star:")).toBeDefined()
    expect(screen.getByText("Labels:")).toBeDefined()
  })

  it("270: takeover label shows 'Release to AI' when is_human_managed=true", () => {
    const managedConv = { ...mockConversation, is_human_managed: true }

    render(
      <ConversationFields
        conversation={managedConv}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByText("Release to AI")).toBeDefined()
  })

  it("270b: takeover label shows 'Take Over' when is_human_managed=false", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByText("Take Over")).toBeDefined()
  })

  it("hides management toggle for non-owner", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={false}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.queryByText("Take Over")).toBeNull()
    expect(screen.queryByText("Release to AI")).toBeNull()
  })

  it("hides Check Star input for non-owner", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={false}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.queryByText("Check Star:")).toBeNull()
    expect(screen.queryByPlaceholderText("GitHub username")).toBeNull()
    expect(screen.queryByText("Verify")).toBeNull()
  })

  it("shows clear button when github_username exists and is owner", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    const clearBtn = screen.getByText("Clear")
    fireEvent.click(clearBtn)
    expect(mutations.clearUsernameMut.mutate).toHaveBeenCalledWith("recruiter123")
  })

  it("hides clear button when github_username is null", () => {
    const convNoUsername = { ...mockConversation, github_username: null }

    render(
      <ConversationFields
        conversation={convNoUsername}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.queryByText("Clear")).toBeNull()
  })

  it("shows star verified indicator when star_verified=true", () => {
    const verifiedConv = { ...mockConversation, star_verified: true }

    render(
      <ConversationFields
        conversation={verifiedConv}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByText(/Verified/)).toBeDefined()
  })

  it("shows 'Not verified' when star_verified=false", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByText("Not verified")).toBeDefined()
  })

  it("calls takeoverMut.mutate with toggled value on click", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    fireEvent.click(screen.getByText("Take Over"))
    expect(mutations.takeoverMut.mutate).toHaveBeenCalledWith(true)
  })

  it("calls takeoverMut.mutate with false when releasing to AI", () => {
    const managedConv = { ...mockConversation, is_human_managed: true }

    render(
      <ConversationFields
        conversation={managedConv}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    fireEvent.click(screen.getByText("Release to AI"))
    expect(mutations.takeoverMut.mutate).toHaveBeenCalledWith(false)
  })

  it("calls starMut.mutate with username on Verify click", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername="testuser"
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    fireEvent.click(screen.getByText("Verify"))
    expect(mutations.starMut.mutate).toHaveBeenCalledWith("testuser")
  })

  it("disables Verify button when starUsername is empty", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    const verifyBtn = screen.getByText("Verify").closest("button")
    expect(verifyBtn).toHaveProperty("disabled", true)
  })

  it("calls onStarUsernameChange when input value changes", () => {
    const onStarUsernameChange = vi.fn()

    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={onStarUsernameChange}
        mutations={mutations}
      />
    )

    const input = screen.getByPlaceholderText("GitHub username")
    fireEvent.change(input, { target: { value: "newuser" } })
    expect(onStarUsernameChange).toHaveBeenCalledWith("newuser")
  })

  it("renders github username in parentheses when present", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByText(`(${mockConversation.github_username})`)).toBeDefined()
  })

  it("renders state badge with correct state", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByTestId("state-badge")).toBeDefined()
    expect(screen.getByTestId("state-badge").textContent).toBe(mockConversation.state)
  })

  it("renders human managed badge when is_human_managed=true", () => {
    const managedConv = { ...mockConversation, is_human_managed: true }

    render(
      <ConversationFields
        conversation={managedConv}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByTestId("human-managed-badge")).toBeDefined()
  })

  it("does not render human managed badge when is_human_managed=false", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.queryByTestId("human-managed-badge")).toBeNull()
  })

  it("renders label chips component", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={true}
        labels={["hot", "priority"]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByTestId("label-chips")).toBeDefined()
    expect(screen.getByText("hot")).toBeDefined()
    expect(screen.getByText("priority")).toBeDefined()
  })

  it("hides clear button for non-owner even when github_username exists", () => {
    render(
      <ConversationFields
        conversation={mockConversation}
        isOwner={false}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.queryByText("Clear")).toBeNull()
  })

  it("shows channel defaulting to 'email' when not set", () => {
    const convNoChannel = { ...mockConversation, channel: undefined }

    render(
      <ConversationFields
        conversation={convNoChannel}
        isOwner={false}
        labels={[]}
        starUsername=""
        onStarUsernameChange={vi.fn()}
        mutations={mutations}
      />
    )

    expect(screen.getByText("email")).toBeDefined()
  })
})
```

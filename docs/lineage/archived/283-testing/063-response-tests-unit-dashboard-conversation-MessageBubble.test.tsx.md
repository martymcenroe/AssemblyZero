

```tsx
/**
 * Unit tests for MessageBubble component.
 *
 * Issue #283 — Test IDs: 070, 300
 */

import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { MessageBubble } from "@/components/shared/conversation/MessageBubble"
import { mockMessage, mockInboundMessage, mockRating } from "../fixtures"

vi.mock("@/lib/utils", () => ({
  toCTFull: (date: string) => date,
}))

vi.mock("@/lib/constants", () => ({
  RATING_EMOJIS: ["", "", "", "", ""],
}))

describe("MessageBubble", () => {
  it("070: renders outbound message with rating controls when canUserRate=true", () => {
    const onRate = vi.fn()

    render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={true}
        onRate={onRate}
      />
    )

    expect(screen.getByText("OUTBOUND")).toBeDefined()
    expect(screen.getByText(mockMessage.body)).toBeDefined()

    // Should have 5 rating buttons
    const ratingButtons = screen.getAllByTitle(/Rate \d/)
    expect(ratingButtons.length).toBe(5)
  })

  it("070b: clicking rating button calls onRate with correct args", () => {
    const onRate = vi.fn()

    render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={true}
        onRate={onRate}
      />
    )

    fireEvent.click(screen.getByTitle("Rate 4"))
    expect(onRate).toHaveBeenCalledWith(101, 4)
  })

  it("070c: renders message subject when present", () => {
    render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    expect(screen.getByText(`Subject: ${mockMessage.subject}`)).toBeDefined()
  })

  it("070d: renders message timestamp", () => {
    render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    // toCTFull is mocked to return the date string as-is
    expect(screen.getByText(mockMessage.created_at)).toBeDefined()
  })

  it("300: rating emojis hidden when canUserRate=false", () => {
    render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    expect(screen.queryByTitle("Rate 1")).toBeNull()
    expect(screen.queryByTitle("Rate 2")).toBeNull()
    expect(screen.queryByTitle("Rate 3")).toBeNull()
    expect(screen.queryByTitle("Rate 4")).toBeNull()
    expect(screen.queryByTitle("Rate 5")).toBeNull()
  })

  it("300b: no rating buttons for inbound messages even when canUserRate=true", () => {
    render(
      <MessageBubble
        message={mockInboundMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={true}
        onRate={vi.fn()}
      />
    )

    expect(screen.getByText("INBOUND")).toBeDefined()
    expect(screen.queryByTitle("Rate 1")).toBeNull()
  })

  it("highlights active rating with bg-blue-200 class", () => {
    render(
      <MessageBubble
        message={mockMessage}
        rating={mockRating}
        isPreInit={false}
        canUserRate={true}
        onRate={vi.fn()}
      />
    )

    // Rating 4 button should have active class
    const ratingBtn = screen.getByTitle("Rate 4")
    expect(ratingBtn.className).toContain("bg-blue-200")
  })

  it("does not highlight non-active rating buttons", () => {
    render(
      <MessageBubble
        message={mockMessage}
        rating={mockRating}
        isPreInit={false}
        canUserRate={true}
        onRate={vi.fn()}
      />
    )

    // Rating 1 button should NOT have active class
    const ratingBtn = screen.getByTitle("Rate 1")
    expect(ratingBtn.className).not.toContain("bg-blue-200")
  })

  it("shows rating note when present", () => {
    render(
      <MessageBubble
        message={mockMessage}
        rating={mockRating}
        isPreInit={false}
        canUserRate={true}
        onRate={vi.fn()}
      />
    )

    expect(screen.getByText("Great response")).toBeDefined()
  })

  it("shows pre-init indicator and opacity when isPreInit=true", () => {
    const { container } = render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={true}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    expect(screen.getByText(/pre-reinit/)).toBeDefined()
    // The root div should have opacity-50 class
    const rootDiv = container.firstChild as HTMLElement
    expect(rootDiv.className).toContain("opacity-50")
  })

  it("does not show pre-init indicator when isPreInit=false", () => {
    render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    expect(screen.queryByText(/pre-reinit/)).toBeNull()
  })

  it("applies outbound styling (ml-8 bg-blue-50) for outbound messages", () => {
    const { container } = render(
      <MessageBubble
        message={mockMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    const rootDiv = container.firstChild as HTMLElement
    expect(rootDiv.className).toContain("ml-8")
    expect(rootDiv.className).toContain("bg-blue-50")
  })

  it("applies inbound styling (mr-8 bg-gray-50) for inbound messages", () => {
    const { container } = render(
      <MessageBubble
        message={mockInboundMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    const rootDiv = container.firstChild as HTMLElement
    expect(rootDiv.className).toContain("mr-8")
    expect(rootDiv.className).toContain("bg-gray-50")
  })

  it("shows RESUME indicator when message has_resume=true", () => {
    const resumeMessage = { ...mockMessage, has_resume: true }

    render(
      <MessageBubble
        message={resumeMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    expect(screen.getByText(/RESUME/)).toBeDefined()
  })

  it("does not show subject line when message subject is empty", () => {
    const noSubjectMessage = { ...mockMessage, subject: "" }

    render(
      <MessageBubble
        message={noSubjectMessage}
        rating={undefined}
        isPreInit={false}
        canUserRate={false}
        onRate={vi.fn()}
      />
    )

    expect(screen.queryByText(/Subject:/)).toBeNull()
  })
})
```

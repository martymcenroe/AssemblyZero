```tsx
/**
 * Unit tests for AuditResultPanel component.
 *
 * Issue #283 — Test IDs: 050, 290
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { AuditResultPanel } from "@/components/shared/conversation/AuditResultPanel"
import { mockAuditResult, mockConversation } from "../fixtures"

describe("AuditResultPanel", () => {
  const handlers = {
    onApproveAndSend: vi.fn(),
    onLoadDraft: vi.fn(),
    onApprove: vi.fn(),
    onChangeState: vi.fn(),
    onReject: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("050: renders all audit action buttons", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.getByText("Approve + Send")).toBeDefined()
    expect(screen.getByText("Load Draft")).toBeDefined()
    expect(screen.getByText("Approve")).toBeDefined()
    expect(screen.getByText("Reject")).toBeDefined()
  })

  it("050b: calls correct handler on button clicks", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    fireEvent.click(screen.getByText("Approve + Send"))
    expect(handlers.onApproveAndSend).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText("Load Draft"))
    expect(handlers.onLoadDraft).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText("Approve"))
    expect(handlers.onApprove).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText("Reject"))
    expect(handlers.onReject).toHaveBeenCalledTimes(1)
  })

  it("290: all buttons disabled when disabled=true", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={true}
        {...handlers}
      />
    )

    const buttons = screen.getAllByRole("button")
    for (const btn of buttons) {
      expect(btn).toHaveProperty("disabled", true)
    }
  })

  it("hides Load Draft and Approve + Send when draft_message is null", () => {
    const auditNoDraft = { ...mockAuditResult, draft_message: null, draft_subject: null }

    render(
      <AuditResultPanel
        audit={auditNoDraft}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.queryByText("Load Draft")).toBeNull()
    expect(screen.queryByText("Approve + Send")).toBeNull()
    expect(screen.getByText("Approve")).toBeDefined()
    expect(screen.getByText("Reject")).toBeDefined()
  })

  it("shows Mark State button when state is incorrect with recommended_state", () => {
    const auditBadState = {
      ...mockAuditResult,
      state_correct: false,
      recommended_state: "closed",
    }

    render(
      <AuditResultPanel
        audit={auditBadState}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    const markBtn = screen.getByText("Mark closed")
    fireEvent.click(markBtn)
    expect(handlers.onChangeState).toHaveBeenCalledWith("closed")
  })

  it("hides Mark State button when state_correct is true", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.queryByText(/^Mark /)).toBeNull()
  })

  it("hides Mark State button when recommended_state is null", () => {
    const auditNoRec = {
      ...mockAuditResult,
      state_correct: false,
      recommended_state: null,
    }

    render(
      <AuditResultPanel
        audit={auditNoRec}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.queryByText(/^Mark /)).toBeNull()
  })

  it("renders findings text", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.getByText("Response looks good. Star push is compelling.")).toBeDefined()
  })

  it("renders Audit Result heading", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.getByText("Audit Result")).toBeDefined()
  })

  it("shows resume needed indicator when resume_needed is true", () => {
    const auditResume = { ...mockAuditResult, resume_needed: true }

    render(
      <AuditResultPanel
        audit={auditResume}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.getByText(/Resume attachment recommended/)).toBeDefined()
  })

  it("does not show resume indicator when resume_needed is false", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.queryByText(/Resume attachment recommended/)).toBeNull()
  })

  it("shows recommended state text when state is incorrect", () => {
    const auditBadState = {
      ...mockAuditResult,
      state_correct: false,
      recommended_state: "closed",
    }

    render(
      <AuditResultPanel
        audit={auditBadState}
        conversation={mockConversation}
        disabled={false}
        {...handlers}
      />
    )

    expect(screen.getByText(/Recommended state: closed/)).toBeDefined()
    expect(screen.getByText(/current: engaging/)).toBeDefined()
  })

  it("does not call handlers when buttons are disabled", () => {
    render(
      <AuditResultPanel
        audit={mockAuditResult}
        conversation={mockConversation}
        disabled={true}
        {...handlers}
      />
    )

    // Attempt clicks on disabled buttons — handlers should not fire
    // (disabled buttons don't fire click events in the DOM)
    const buttons = screen.getAllByRole("button")
    for (const btn of buttons) {
      fireEvent.click(btn)
    }

    expect(handlers.onApproveAndSend).not.toHaveBeenCalled()
    expect(handlers.onLoadDraft).not.toHaveBeenCalled()
    expect(handlers.onApprove).not.toHaveBeenCalled()
    expect(handlers.onReject).not.toHaveBeenCalled()
  })
})
```

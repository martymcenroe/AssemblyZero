

```tsx
/**
 * Unit tests for AuditHistoryPanel component.
 *
 * Issue #283 — Test ID: 060
 */

import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { AuditHistoryPanel } from "@/components/shared/conversation/AuditHistoryPanel"
import { mockAuditHistoryEntry } from "../fixtures"

vi.mock("@/lib/utils", () => ({
  toCTFull: (date: string) => date,
}))

describe("AuditHistoryPanel", () => {
  it("060: renders collapsible entries with expand/collapse toggle", () => {
    render(
      <AuditHistoryPanel
        entries={[mockAuditHistoryEntry]}
      />
    )

    expect(screen.getByText("Audit History")).toBeDefined()
    expect(screen.getByText(/approve/)).toBeDefined()

    // Findings should not be visible before expand
    expect(screen.queryByText("Approved after review.")).toBeNull()

    // Click to expand
    fireEvent.click(screen.getByText(/approve/))

    // Now findings should be visible
    expect(screen.getByText("Approved after review.")).toBeDefined()
  })

  it("060b: collapses expanded entry on second click", () => {
    render(
      <AuditHistoryPanel
        entries={[mockAuditHistoryEntry]}
      />
    )

    // Expand
    fireEvent.click(screen.getByText(/approve/))
    expect(screen.getByText("Approved after review.")).toBeDefined()

    // Collapse
    fireEvent.click(screen.getByText(/approve/))
    expect(screen.queryByText("Approved after review.")).toBeNull()
  })

  it("returns null when entries is empty", () => {
    const { container } = render(
      <AuditHistoryPanel entries={[]} />
    )

    expect(container.innerHTML).toBe("")
  })

  it("returns null when entries is undefined-like empty array", () => {
    const { container } = render(
      <AuditHistoryPanel entries={[]} />
    )

    expect(container.innerHTML).toBe("")
  })

  it("renders multiple entries", () => {
    const entries = [
      mockAuditHistoryEntry,
      { ...mockAuditHistoryEntry, id: 2, action: "reject" as const, findings: "Rejected due to tone." },
    ]

    render(
      <AuditHistoryPanel entries={entries} />
    )

    expect(screen.getByText(/approve/)).toBeDefined()
    expect(screen.getByText(/reject/)).toBeDefined()
  })

  it("expands multiple entries independently", () => {
    const entries = [
      mockAuditHistoryEntry,
      { ...mockAuditHistoryEntry, id: 2, action: "reject" as const, findings: "Rejected due to tone." },
    ]

    render(
      <AuditHistoryPanel entries={entries} />
    )

    // Expand first entry
    fireEvent.click(screen.getByText(/approve/))
    expect(screen.getByText("Approved after review.")).toBeDefined()
    expect(screen.queryByText("Rejected due to tone.")).toBeNull()

    // Expand second entry
    fireEvent.click(screen.getByText(/reject/))
    expect(screen.getByText("Approved after review.")).toBeDefined()
    expect(screen.getByText("Rejected due to tone.")).toBeDefined()
  })

  it("shows collapse indicator when expanded", () => {
    render(
      <AuditHistoryPanel
        entries={[mockAuditHistoryEntry]}
      />
    )

    // Before expand — should show right arrow
    expect(screen.getByText("▶")).toBeDefined()

    // Expand
    fireEvent.click(screen.getByText(/approve/))

    // After expand — should show down arrow
    expect(screen.getByText("▼")).toBeDefined()
  })

  it("renders entry timestamp", () => {
    render(
      <AuditHistoryPanel
        entries={[mockAuditHistoryEntry]}
      />
    )

    // toCTFull is mocked to return the date string as-is
    expect(screen.getByText(/2026-03-01T11:00:00Z/)).toBeDefined()
  })
})
```

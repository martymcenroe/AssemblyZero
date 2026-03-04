

```tsx
/**
 * Unit tests for ComposePanel component.
 *
 * Issue #283 — Test IDs: 040, 280
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { ComposePanel } from "@/components/shared/conversation/ComposePanel"
import { mockConversation, createMockMutations } from "../fixtures"

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

import { toast } from "sonner"

describe("ComposePanel", () => {
  let mutations: ReturnType<typeof createMockMutations>

  beforeEach(() => {
    vi.clearAllMocks()
    mutations = createMockMutations()
  })

  it("040: renders compose form for owner", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: test"
        body=""
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    expect(screen.getByText("Compose Reply")).toBeDefined()
    expect(screen.getByPlaceholderText("Subject")).toBeDefined()
    expect(screen.getByPlaceholderText("Type your message...")).toBeDefined()
    expect(screen.getByText("Send Email")).toBeDefined()
    expect(screen.getByText("Attach Files")).toBeDefined()
  })

  it("280: returns null when isOwner=false", () => {
    const { container } = render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={false}
        sendMut={mutations.sendMut as any}
        subject=""
        body=""
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    expect(container.innerHTML).toBe("")
  })

  it("shows error toast when sending with empty body", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: test"
        body=""
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    fireEvent.click(screen.getByText("Send Email"))

    expect(toast.error).toHaveBeenCalledWith("Message body is empty")
    expect(mutations.sendMut.mutate).not.toHaveBeenCalled()
  })

  it("shows error toast when sending with whitespace-only body", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: test"
        body="   "
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    fireEvent.click(screen.getByText("Send Email"))

    expect(toast.error).toHaveBeenCalledWith("Message body is empty")
    expect(mutations.sendMut.mutate).not.toHaveBeenCalled()
  })

  it("calls sendMut.mutate with correct data when body is not empty", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: test"
        body="Hello there"
        pendingFiles={[{ filename: "file.txt", data: "abc" }]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    fireEvent.click(screen.getByText("Send Email"))

    expect(mutations.sendMut.mutate).toHaveBeenCalledWith({
      subject: "Re: test",
      body: "Hello there",
      attachments: [{ filename: "file.txt", data: "abc" }],
    })
  })

  it("calls sendMut.mutate with empty attachments when no files", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: Exciting Opportunity"
        body="Thanks for reaching out"
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    fireEvent.click(screen.getByText("Send Email"))

    expect(mutations.sendMut.mutate).toHaveBeenCalledWith({
      subject: "Re: Exciting Opportunity",
      body: "Thanks for reaching out",
      attachments: [],
    })
  })

  it("disables Send Email button when sendMut is pending", () => {
    const pendingMutations = createMockMutations()
    pendingMutations.sendMut = { ...pendingMutations.sendMut, isPending: true as any }

    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={pendingMutations.sendMut as any}
        subject="Re: test"
        body="Hello"
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    const sendBtn = screen.getByText("Sending...").closest("button")
    expect(sendBtn).toHaveProperty("disabled", true)
  })

  it("shows 'Sending...' text when sendMut is pending", () => {
    const pendingMutations = createMockMutations()
    pendingMutations.sendMut = { ...pendingMutations.sendMut, isPending: true as any }

    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={pendingMutations.sendMut as any}
        subject="Re: test"
        body="Hello"
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    expect(screen.getByText("Sending...")).toBeDefined()
    expect(screen.queryByText("Send Email")).toBeNull()
  })

  it("displays pending file names", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: test"
        body=""
        pendingFiles={[
          { filename: "resume.pdf", data: "base64data1" },
          { filename: "cover-letter.docx", data: "base64data2" },
        ]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    expect(screen.getByText(/resume\.pdf/)).toBeDefined()
    expect(screen.getByText(/cover-letter\.docx/)).toBeDefined()
  })

  it("does not display file list when pendingFiles is empty", () => {
    const { container } = render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: test"
        body=""
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    // No file name spans should be rendered
    const fileList = container.querySelector(".text-xs.text-muted-foreground")
    expect(fileList).toBeNull()
  })

  it("calls onSubjectChange when subject input changes", () => {
    const onSubjectChange = vi.fn()

    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject=""
        body=""
        pendingFiles={[]}
        onSubjectChange={onSubjectChange}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    const subjectInput = screen.getByPlaceholderText("Subject")
    fireEvent.change(subjectInput, { target: { value: "New Subject" } })
    expect(onSubjectChange).toHaveBeenCalledWith("New Subject")
  })

  it("calls onBodyChange when textarea changes", () => {
    const onBodyChange = vi.fn()

    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject=""
        body=""
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={onBodyChange}
        onFilesChange={vi.fn()}
      />
    )

    const textarea = screen.getByPlaceholderText("Type your message...")
    fireEvent.change(textarea, { target: { value: "New message content" } })
    expect(onBodyChange).toHaveBeenCalledWith("New message content")
  })

  it("renders subject input with provided value", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject="Re: Exciting Opportunity"
        body=""
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    const subjectInput = screen.getByPlaceholderText("Subject") as HTMLInputElement
    expect(subjectInput.value).toBe("Re: Exciting Opportunity")
  })

  it("renders body textarea with provided value", () => {
    render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject=""
        body="Draft message content"
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    const textarea = screen.getByPlaceholderText("Type your message...") as HTMLTextAreaElement
    expect(textarea.value).toBe("Draft message content")
  })

  it("has a hidden file input element", () => {
    const { container } = render(
      <ComposePanel
        conversation={mockConversation}
        isOwner={true}
        sendMut={mutations.sendMut as any}
        subject=""
        body=""
        pendingFiles={[]}
        onSubjectChange={vi.fn()}
        onBodyChange={vi.fn()}
        onFilesChange={vi.fn()}
      />
    )

    const fileInput = container.querySelector('input[type="file"]')
    expect(fileInput).toBeDefined()
    expect(fileInput?.className).toContain("hidden")
  })
})
```

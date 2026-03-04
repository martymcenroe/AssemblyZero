

```tsx
/**
 * Email compose form: subject, body, file attach, send button.
 * Owner-only visibility.
 *
 * Issue #283: Extracted from ConversationDetail.tsx compose section.
 */

import { useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"
import type { ConversationMutations, PendingFile } from "./types"

interface ComposePanelProps {
  conversation: { id: number }
  isOwner: boolean
  sendMut: ConversationMutations["sendMut"]
  subject: string
  body: string
  pendingFiles: PendingFile[]
  onSubjectChange: (subject: string) => void
  onBodyChange: (body: string) => void
  onFilesChange: (files: PendingFile[]) => void
}

export function ComposePanel({
  isOwner,
  sendMut,
  subject,
  body,
  pendingFiles,
  onSubjectChange,
  onBodyChange,
  onFilesChange,
}: ComposePanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  if (!isOwner) return null

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const newPending: PendingFile[] = []
    files.forEach((file) => {
      const reader = new FileReader()
      reader.onload = (ev) => {
        const result = ev.target?.result as string
        newPending.push({ filename: file.name, data: result.split(",")[1] })
        if (newPending.length === files.length) {
          onFilesChange(newPending)
        }
      }
      reader.readAsDataURL(file)
    })
  }

  const handleSend = () => {
    if (!body.trim()) {
      toast.error("Message body is empty")
      return
    }
    sendMut.mutate({ subject, body, attachments: pendingFiles })
  }

  return (
    <div className="mt-4">
      <h3 className="mb-2 text-sm font-semibold">Compose Reply</h3>
      <div className="space-y-2">
        <Input
          placeholder="Subject"
          value={subject}
          onChange={(e) => onSubjectChange(e.target.value)}
        />
        <Textarea
          placeholder="Type your message..."
          value={body}
          onChange={(e) => onBodyChange(e.target.value)}
          rows={4}
        />
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
          >
            Attach Files
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
          <Button
            size="sm"
            onClick={handleSend}
            disabled={sendMut.isPending}
          >
            {sendMut.isPending ? "Sending..." : "Send Email"}
          </Button>
        </div>
        {pendingFiles.length > 0 && (
          <div className="text-xs text-muted-foreground">
            {pendingFiles.map((f, i) => (
              <span key={i} className="mr-2">
                 {f.filename}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

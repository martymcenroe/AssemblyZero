

```tsx
/**
 * Renders collapsible audit history entries.
 *
 * Issue #283: Extracted from ConversationDetail.tsx audit history section.
 */

import { useState } from "react"
import type { AuditLogEntry } from "@/api/types"
import { toCTFull } from "@/lib/utils"

interface AuditHistoryPanelProps {
  entries: AuditLogEntry[]
}

export function AuditHistoryPanel({ entries }: AuditHistoryPanelProps) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  if (!entries || entries.length === 0) return null

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  return (
    <div className="mt-4">
      <h3 className="mb-2 text-sm font-semibold">Audit History</h3>
      <div className="space-y-2">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="rounded border p-2 text-xs"
          >
            <div
              className="flex cursor-pointer items-center justify-between"
              onClick={() => toggleExpand(entry.id)}
            >
              <span className="font-medium">
                {entry.action} — {toCTFull(entry.created_at)}
              </span>
              <span>{expandedIds.has(entry.id) ? "▼" : "▶"}</span>
            </div>
            {expandedIds.has(entry.id) && (
              <div className="mt-1 whitespace-pre-wrap text-muted-foreground">
                {entry.findings}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
```

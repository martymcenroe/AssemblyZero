

```tsx
/**
 * Audit result actions: Approve+Send, Load Draft, Approve, Mark State, Reject.
 *
 * Issue #283: Extracted from ConversationDetail.tsx audit result section.
 */

import { Button } from "@/components/ui/button"
import type { AuditDiagnosis } from "@/api/types"

interface AuditResultPanelProps {
  audit: AuditDiagnosis
  conversation: { id: number; state: string }
  disabled: boolean
  onApproveAndSend: () => void
  onLoadDraft: () => void
  onApprove: () => void
  onChangeState: (state: string) => void
  onReject: () => void
}

export function AuditResultPanel({
  audit,
  conversation: conv,
  disabled,
  onApproveAndSend,
  onLoadDraft,
  onApprove,
  onChangeState,
  onReject,
}: AuditResultPanelProps) {
  return (
    <div className="mt-4 rounded border border-purple-300 bg-purple-50 p-3 dark:border-purple-700 dark:bg-purple-950/30">
      <h3 className="mb-2 text-sm font-semibold text-purple-700 dark:text-purple-300">
        Audit Result
      </h3>

      {/* Findings */}
      <div className="mb-2 whitespace-pre-wrap text-xs text-muted-foreground">
        {audit.findings}
      </div>

      {/* State recommendation */}
      {!audit.state_correct && audit.recommended_state && (
        <div className="mb-2 text-xs">
          <span className="font-semibold text-orange-600">
            Recommended state: {audit.recommended_state}
          </span>
          {" "}(current: {conv.state})
        </div>
      )}

      {/* Resume needed indicator */}
      {audit.resume_needed && (
        <div className="mb-2 text-xs font-semibold text-blue-600">
           Resume attachment recommended
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap items-center gap-2">
        {audit.draft_message && (
          <>
            <Button
              size="sm"
              variant="outline"
              className="border-green-500 text-green-600"
              onClick={onApproveAndSend}
              disabled={disabled}
            >
              Approve + Send
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={onLoadDraft}
              disabled={disabled}
            >
              Load Draft
            </Button>
          </>
        )}
        <Button
          size="sm"
          variant="outline"
          className="border-green-500 text-green-600"
          onClick={onApprove}
          disabled={disabled}
        >
          Approve
        </Button>
        {!audit.state_correct && audit.recommended_state && (
          <Button
            size="sm"
            variant="outline"
            className="border-orange-500 text-orange-600"
            onClick={() => onChangeState(audit.recommended_state!)}
            disabled={disabled}
          >
            Mark {audit.recommended_state}
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          className="border-red-500 text-red-500"
          onClick={onReject}
          disabled={disabled}
        >
          Reject
        </Button>
      </div>
    </div>
  )
}
```

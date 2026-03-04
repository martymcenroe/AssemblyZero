```tsx
/**
 * ConversationDetail orchestrator — composes extracted child components.
 *
 * Issue #283: Reduced from 1132 lines to ~200 lines.
 */

import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  fetchConversation,
  fetchLabels,
  fetchRatings,
  fetchAuditHistory,
} from "@/api/client"
import type { Message, Rating, AuditDiagnosis } from "@/api/types"
import { useAuth } from "@/providers/AuthProvider"
import { canWrite, canRate } from "@/lib/roles"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useConversationMutations } from "@/lib/hooks"
import {
  ConversationActionBar,
  ConversationFields,
  ComposePanel,
  AuditResultPanel,
  AuditHistoryPanel,
  MessageBubble,
} from "./conversation"

interface ConversationDetailProps {
  conversationId: number
  onBack?: () => void
  onDeleted?: () => void
  onClose?: () => void
}

export function ConversationDetail({ conversationId, onBack, onDeleted, onClose }: ConversationDetailProps) {
  const convId = conversationId
  const { role } = useAuth()
  const isOwner = canWrite(role)

  // Local state
  const [showFullHistory, setShowFullHistory] = useState(true)
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [starUsername, setStarUsername] = useState("")
  const [pendingFiles, setPendingFiles] = useState<Array<{ filename: string; data: string }>>([])
  const [pendingAudit, setPendingAudit] = useState(false)

  // Queries
  const { data: conv, isLoading, error } = useQuery({
    queryKey: ["conversation", convId],
    queryFn: () => fetchConversation(convId),
  })

  const { data: labels } = useQuery({
    queryKey: ["labels", convId],
    queryFn: () => fetchLabels(convId),
  })

  const { data: ratings } = useQuery({
    queryKey: ["ratings", convId],
    queryFn: () => fetchRatings(convId),
    enabled: canRate(role),
  })

  const { data: auditHistory } = useQuery({
    queryKey: ["audit-history", convId],
    queryFn: () => fetchAuditHistory(convId),
    enabled: isOwner,
  })

  // Ratings map
  const ratingsMap: Record<number, Rating> = {}
  if (ratings) {
    for (const r of ratings) ratingsMap[r.message_id] = r
  }

  // Centralized mutations
  const mutations = useConversationMutations(convId, {
    onClose,
    onDeleted,
    onSendSuccess: () => {
      setBody("")
      setPendingFiles([])
    },
    onAuditMutate: () => setPendingAudit(true),
    onAuditSettled: (success) => {
      if (!success) setPendingAudit(false)
    },
    getConversation: () => conv,
    getStarUsername: () => starUsername,
  })

  // Reset pendingAudit when audit_result appears
  useEffect(() => {
    if (pendingAudit && conv?.audit_result) {
      setPendingAudit(false)
    }
  }, [conv?.audit_result, pendingAudit])

  // Early returns
  if (isLoading) return <div className="py-10 text-center text-muted-foreground">Loading...</div>
  if (error) return <div className="py-10 text-center text-destructive">Error: {error.message}</div>
  if (!conv) return null

  // Initialize subject for compose
  if (!subject && conv.subject) {
    setSubject(`Re: ${conv.subject}`)
  }

  // Parse audit result (stored as JSON string in API)
  let auditResult: AuditDiagnosis | null = null
  if (conv.audit_result) {
    try {
      auditResult = typeof conv.audit_result === "string"
        ? JSON.parse(conv.audit_result)
        : conv.audit_result
    } catch { /* ignore malformed JSON */ }
  }

  // Message processing
  const allMessages: Message[] = conv.messages || []
  const lastInitAt = conv.last_init_at
  let hiddenCount = 0
  const visibleMessages: Array<{ msg: Message; isPreInit: boolean }> = []

  for (const msg of allMessages) {
    const isPreInit = !!(lastInitAt && msg.created_at < lastInitAt)
    if (isPreInit && !showFullHistory) {
      hiddenCount++
    } else {
      visibleMessages.push({ msg, isPreInit })
    }
  }
  visibleMessages.reverse()

  // Derive labels array
  const labelList = labels || []

  return (
    <div>
      <Card className="mb-4">
        <CardContent className="p-5">
          {/* Action bar */}
          <ConversationActionBar
            conversation={conv}
            isOwner={isOwner}
            labels={labelList}
            mutations={mutations}
            onBack={onBack}
            pendingAudit={pendingAudit}
          />

          {/* Conversation header */}
          <h2 className="mb-3 text-lg font-bold">Conversation #{conv.id}</h2>

          {/* Metadata fields */}
          <ConversationFields
            conversation={conv}
            isOwner={isOwner}
            labels={labelList}
            starUsername={starUsername}
            onStarUsernameChange={setStarUsername}
            mutations={mutations}
          />

          {/* Audit result (if available) */}
          {auditResult && (
            <AuditResultPanel
              audit={auditResult}
              conversation={conv}
              disabled={mutations.approveMut.isPending || mutations.rejectMut.isPending}
              onApproveAndSend={() => mutations.approveAndSendMut.mutate()}
              onLoadDraft={() => {
                if (auditResult?.draft_subject) setSubject(auditResult.draft_subject)
                if (auditResult?.draft_message) setBody(auditResult.draft_message)
              }}
              onApprove={() => mutations.approveMut.mutate()}
              onChangeState={(state) => mutations.changeStateMut.mutate(state)}
              onReject={() => mutations.rejectMut.mutate()}
            />
          )}

          {/* Compose panel */}
          <ComposePanel
            conversation={conv}
            isOwner={isOwner}
            sendMut={mutations.sendMut}
            subject={subject}
            body={body}
            pendingFiles={pendingFiles}
            onSubjectChange={setSubject}
            onBodyChange={setBody}
            onFilesChange={setPendingFiles}
          />

          {/* Audit history */}
          {auditHistory && auditHistory.length > 0 && (
            <AuditHistoryPanel entries={auditHistory} />
          )}
        </CardContent>
      </Card>

      {/* Messages section */}
      <h3 className="mb-2 text-sm font-semibold">Messages</h3>

      {/* History toggle */}
      {lastInitAt && (
        <div className="mb-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setShowFullHistory(!showFullHistory)}
          >
            {showFullHistory ? "Show Recent Only" : `Show Full History (${hiddenCount} hidden)`}
          </Button>
        </div>
      )}

      <div className="space-y-3">
        {visibleMessages.map(({ msg, isPreInit }) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            rating={ratingsMap[msg.id]}
            isPreInit={isPreInit}
            canUserRate={canRate(role)}
            onRate={(messageId, rating) =>
              mutations.rateMut.mutate({
                conversation_id: convId,
                message_id: messageId,
                rating,
              })
            }
          />
        ))}
      </div>
    </div>
  )
}
```

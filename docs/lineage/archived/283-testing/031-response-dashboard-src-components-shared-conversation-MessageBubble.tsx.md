

```tsx
/**
 * Renders a single message with directional styling,
 * rating emojis, and rating note.
 *
 * Issue #283: Extracted from ConversationDetail.tsx message loop.
 */

import type { Message, Rating } from "@/api/types"
import { toCTFull } from "@/lib/utils"
import { RATING_EMOJIS } from "@/lib/constants"

interface MessageBubbleProps {
  message: Message
  rating: Rating | undefined
  isPreInit: boolean
  canUserRate: boolean
  onRate: (messageId: number, rating: number) => void
}

export function MessageBubble({ message: msg, rating, isPreInit, canUserRate, onRate }: MessageBubbleProps) {
  const isOutbound = msg.direction === "outbound"

  return (
    <div
      className={`rounded-lg p-3 ${
        isOutbound ? "ml-8 bg-blue-50 dark:bg-blue-950/30" : "mr-8 bg-gray-50 dark:bg-gray-800/50"
      } ${isPreInit ? "opacity-50" : ""}`}
    >
      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
        <span className="font-semibold">
          {msg.direction.toUpperCase()}
          {msg.has_resume && "  RESUME"}
          {isPreInit && " (pre-reinit)"}
        </span>
        <span>{toCTFull(msg.created_at)}</span>
      </div>
      {msg.subject && (
        <div className="mb-1 text-xs font-medium text-muted-foreground">
          Subject: {msg.subject}
        </div>
      )}
      <div className="whitespace-pre-wrap text-sm">{msg.body}</div>

      {/* Rating section for outbound messages */}
      {isOutbound && canUserRate && (
        <div className="mt-2 flex items-center gap-1">
          {RATING_EMOJIS.map((emoji: string, idx: number) => (
            <button
              key={idx}
              className={`rounded-md px-2 py-1 text-sm transition-colors ${
                rating?.rating === idx + 1
                  ? "bg-blue-200 dark:bg-blue-800"
                  : "hover:bg-gray-200 dark:hover:bg-gray-700"
              }`}
              onClick={() => onRate(msg.id, idx + 1)}
              title={`Rate ${idx + 1}`}
            >
              {emoji}
            </button>
          ))}
          {rating?.note && (
            <span className="ml-2 text-xs text-muted-foreground italic">
              {rating.note}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
```

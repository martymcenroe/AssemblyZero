

```tsx
/**
 * Metadata fields: sender, subject, state, labels, takeover, star check.
 *
 * Issue #283: Extracted from ConversationDetail.tsx metadata section.
 */

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { StateBadge, HumanManagedBadge } from "@/components/shared/StateBadge"
import { LabelChips } from "@/components/shared/LabelChips"
import { toCTFull } from "@/lib/utils"
import type { ConversationMutations } from "./types"

interface ConversationFieldsProps {
  conversation: {
    id: number
    sender_email: string
    subject: string
    state: string
    channel?: string
    created_at: string
    updated_at: string
    github_username: string | null
    is_human_managed: boolean
    star_verified: boolean
    attention_snoozed: boolean
    last_intent: string
  }
  isOwner: boolean
  labels: string[]
  starUsername: string
  onStarUsernameChange: (username: string) => void
  mutations: Pick<ConversationMutations,
    "clearUsernameMut" | "addLabelMut" | "removeLabelMut" | "takeoverMut" | "starMut">
}

export function ConversationFields({
  conversation: conv,
  isOwner,
  labels,
  starUsername,
  onStarUsernameChange,
  mutations,
}: ConversationFieldsProps) {
  const { clearUsernameMut, addLabelMut, removeLabelMut, takeoverMut, starMut } = mutations

  return (
    <div className="space-y-2 text-sm">
      <div>
        <span className="font-semibold">Sender:</span> {conv.sender_email}
      </div>
      <div>
        <span className="font-semibold">Subject:</span> {conv.subject}
      </div>
      <div className="flex items-center gap-2">
        <span className="font-semibold">State:</span>
        <StateBadge state={conv.state} />
        {conv.is_human_managed && <HumanManagedBadge />}
      </div>
      <div>
        <span className="font-semibold">Channel:</span> {conv.channel || "email"}
      </div>
      <div>
        <span className="font-semibold">Created:</span> {toCTFull(conv.created_at)}
      </div>
      <div>
        <span className="font-semibold">Updated:</span> {toCTFull(conv.updated_at)}
      </div>
      <div>
        <span className="font-semibold">Intent:</span> {conv.last_intent}
      </div>

      {/* Star verification status */}
      <div className="flex items-center gap-2">
        <span className="font-semibold">Star:</span>
        {conv.star_verified ? (
          <span className="text-green-600"> Verified</span>
        ) : (
          <span className="text-muted-foreground">Not verified</span>
        )}
        {conv.github_username && (
          <>
            <span className="text-xs text-muted-foreground">({conv.github_username})</span>
            {isOwner && (
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-xs text-red-500"
                onClick={() => clearUsernameMut.mutate(conv.github_username!)}
                disabled={clearUsernameMut.isPending}
              >
                Clear
              </Button>
            )}
          </>
        )}
      </div>

      {/* Labels */}
      <div className="flex items-center gap-2">
        <span className="font-semibold">Labels:</span>
        <LabelChips
          labels={labels}
          onAdd={isOwner ? (label: string) => addLabelMut.mutate(label) : undefined}
          onRemove={isOwner ? (label: string) => removeLabelMut.mutate(label) : undefined}
        />
      </div>

      {/* Management toggle (owner only) */}
      {isOwner && (
        <div className="flex items-center gap-2">
          <span className="font-semibold">Management:</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => takeoverMut.mutate(!conv.is_human_managed)}
            disabled={takeoverMut.isPending}
          >
            {conv.is_human_managed ? "Release to AI" : "Take Over"}
          </Button>
        </div>
      )}

      {/* Check Star input (owner only) */}
      {isOwner && (
        <div className="flex items-center gap-2">
          <span className="font-semibold">Check Star:</span>
          <Input
            placeholder="GitHub username"
            value={starUsername}
            onChange={(e) => onStarUsernameChange(e.target.value)}
            className="h-8 w-48"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => starMut.mutate(starUsername)}
            disabled={starMut.isPending || !starUsername.trim()}
          >
            Verify
          </Button>
        </div>
      )}
    </div>
  )
}
```

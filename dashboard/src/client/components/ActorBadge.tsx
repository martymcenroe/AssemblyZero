interface ActorBadgeProps {
  actor: string;
}

export function ActorBadge({ actor }: ActorBadgeProps) {
  if (actor === "human") {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-xs px-2 py-0.5 rounded bg-human/10 text-human border border-human/20">
        <span className="w-1.5 h-1.5 rounded-full bg-human" />
        human
      </span>
    );
  }
  if (actor === "claude") {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-xs px-2 py-0.5 rounded bg-claude/10 text-claude border border-claude/20">
        <span className="w-1.5 h-1.5 rounded-full bg-claude" />
        claude
      </span>
    );
  }
  return (
    <span className="font-mono text-xs text-text-muted">{actor}</span>
  );
}

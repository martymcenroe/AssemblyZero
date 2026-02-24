import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import type { EventsResponse } from "../api";

function ActorPanel({
  label,
  events,
  isLoading,
  isError,
  error,
  color,
}: {
  label: string;
  events: EventsResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  color: "human" | "claude";
}) {
  const borderColor = color === "human" ? "border-human/20" : "border-claude/20";
  const textColor = color === "human" ? "text-human" : "text-claude";
  const glowClass = color === "human" ? "stat-glow-human" : "stat-glow-claude";

  // Aggregate event types
  const typeCounts: Record<string, number> = {};
  if (events?.items) {
    for (const item of events.items) {
      const t = item.event_type ?? "unknown";
      typeCounts[t] = (typeCounts[t] ?? 0) + 1;
    }
  }
  const sorted = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);

  return (
    <div className={`bg-surface border ${borderColor} rounded-lg p-5`}>
      <h3 className={`text-lg font-semibold ${textColor} mb-4 font-mono`}>
        {label}
      </h3>

      {isError ? (
        <div className="text-error font-mono text-sm">Error: {error?.message}</div>
      ) : isLoading ? (
        <div className="text-text-muted font-mono text-xs">Loading…</div>
      ) : (
        <>
          <div className={`text-3xl font-mono font-bold ${textColor} ${glowClass} mb-4`}>
            {events?.items.length ?? 0} events
          </div>
          {sorted.length === 0 ? (
            <div className="text-text-muted font-mono text-xs">No events</div>
          ) : (
            <div className="space-y-1">
              {sorted.map(([type, count]) => (
                <div
                  key={type}
                  className="flex justify-between py-1.5 border-b border-border/50 last:border-0"
                >
                  <span className="font-mono text-xs text-text-muted truncate mr-2">
                    {type}
                  </span>
                  <span className="font-mono text-xs font-semibold text-text">
                    {count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function ComparisonPage() {
  const human = useQuery({
    queryKey: ["events", "by-actor", "human"],
    queryFn: () =>
      apiFetch<EventsResponse>("/api/events/by-actor?actor=human&limit=100"),
  });

  const claude = useQuery({
    queryKey: ["events", "by-actor", "claude"],
    queryFn: () =>
      apiFetch<EventsResponse>("/api/events/by-actor?actor=claude&limit=100"),
  });

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <ActorPanel
        label="Human"
        events={human.data}
        isLoading={human.isLoading}
        isError={human.isError}
        error={human.error}
        color="human"
      />
      <ActorPanel
        label="Claude"
        events={claude.data}
        isLoading={claude.isLoading}
        isError={claude.isError}
        error={claude.error}
        color="claude"
      />
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import type { OverviewResponse, WeeklyResponse } from "../api";
import { StatCard } from "../components/StatCard";
import { Sparkline } from "../components/Sparkline";
import { ActorBadge } from "../components/ActorBadge";

export function OverviewPage() {
  const overview = useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: () => apiFetch<OverviewResponse>("/api/dashboard/overview"),
  });

  const weekly = useQuery({
    queryKey: ["summary", "weekly"],
    queryFn: () => apiFetch<WeeklyResponse>("/api/summary/weekly"),
  });

  if (overview.isError) {
    return (
      <div className="text-error font-mono text-sm p-4">
        Error: {overview.error.message}
      </div>
    );
  }

  const today = overview.data?.today;

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Today's Events"
          value={today?.total ?? "—"}
          variant="total"
          delay={0}
        />
        <StatCard
          label="Human"
          value={today?.human ?? "—"}
          variant="human"
          delay={60}
        />
        <StatCard
          label="Claude"
          value={today?.claude ?? "—"}
          variant="claude"
          delay={120}
        />
        <StatCard
          label="Errors"
          value={today?.errors ?? "—"}
          variant="error"
          delay={180}
        />
      </div>

      {/* Sparkline — last 7 days */}
      <div className="animate-fade-up bg-surface border border-border rounded-lg p-5" style={{ animationDelay: "240ms" }}>
        <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-4">
          Last 7 Days
        </div>
        {weekly.data ? (
          <Sparkline days={weekly.data.days} />
        ) : weekly.isLoading ? (
          <div className="h-20 flex items-center justify-center text-text-muted font-mono text-xs">
            Loading…
          </div>
        ) : null}
        {/* Legend */}
        <div className="flex gap-4 mt-3 text-xs font-mono text-text-muted">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-human" /> human
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-claude" /> claude
          </span>
        </div>
      </div>

      {/* Recent errors */}
      <div className="animate-fade-up bg-surface border border-border rounded-lg p-5" style={{ animationDelay: "300ms" }}>
        <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-4">
          Recent Errors
        </div>
        {overview.data?.recent_errors.length === 0 ? (
          <div className="font-mono text-sm text-human">No errors today</div>
        ) : overview.data?.recent_errors ? (
          <div className="space-y-2">
            {overview.data.recent_errors.map((e, i) => (
              <div key={i} className="flex items-center gap-3 py-1.5 border-b border-border/50 last:border-0">
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-error/10 text-error border border-error/20">
                  {e.event_type}
                </span>
                <span className="font-mono text-xs text-text-muted">
                  {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : "—"}
                </span>
                <ActorBadge actor={e.actor} />
                <span className="text-xs text-text-muted truncate">
                  {(e.metadata?.error_message as string) ?? ""}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-text-muted font-mono text-xs">Loading…</div>
        )}
      </div>
    </div>
  );
}

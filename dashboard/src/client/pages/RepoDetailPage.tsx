import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import type { RepoSummaryResponse } from "../api";
import { EventTable } from "../components/EventTable";

const REPOS = ["AssemblyZero", "unleashed", "Talos", "Aletheia"] as const;

function ActivityBar({ count, max }: { count: number; max: number }) {
  const pct = max > 0 ? (count / max) * 100 : 0;
  return (
    <div className="h-5 bg-surface-raised rounded-sm overflow-hidden">
      <div
        className="h-full bg-accent/60 rounded-sm"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function RepoDetailPage() {
  const [repo, setRepo] = useState<string>("AssemblyZero");

  const summary = useQuery({
    queryKey: ["repos", repo, "summary"],
    queryFn: () => apiFetch<RepoSummaryResponse>(`/api/repos/${encodeURIComponent(repo)}/summary`),
  });

  const data = summary.data;
  const maxDaily = data
    ? Math.max(...data.daily_activity.map((d) => d.count), 1)
    : 1;

  const total = data?.total_events ?? 0;
  const humanCount = data?.by_actor.human ?? 0;
  const claudeCount = data?.by_actor.claude ?? 0;
  const humanPct = total > 0 ? ((humanCount / total) * 100).toFixed(1) : "0";
  const claudePct = total > 0 ? ((claudeCount / total) * 100).toFixed(1) : "0";

  // Sort event types by count
  const eventTypes = data
    ? Object.entries(data.by_event_type).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <div className="space-y-6">
      {/* Repo selector */}
      <select
        value={repo}
        onChange={(e) => setRepo(e.target.value)}
        className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono text-text focus:outline-none focus:border-accent/50"
      >
        {REPOS.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>

      {summary.isError ? (
        <div className="text-error font-mono text-sm p-4">
          Error: {summary.error.message}
        </div>
      ) : summary.isLoading ? (
        <div className="text-text-muted font-mono text-xs p-8 text-center">
          Loading…
        </div>
      ) : data ? (
        <>
          {/* Top row: actor breakdown + total */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-surface border border-border rounded-lg p-5">
              <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-2">
                Total Events
              </div>
              <div className="text-3xl font-mono font-bold text-accent stat-glow-accent">
                {total}
              </div>
            </div>
            <div className="bg-surface border border-human/20 rounded-lg p-5">
              <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-2">
                Human
              </div>
              <div className="text-3xl font-mono font-bold text-human stat-glow-human">
                {humanCount}
                <span className="text-sm font-normal text-text-muted ml-2">
                  {humanPct}%
                </span>
              </div>
            </div>
            <div className="bg-surface border border-claude/20 rounded-lg p-5">
              <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-2">
                Claude
              </div>
              <div className="text-3xl font-mono font-bold text-claude stat-glow-claude">
                {claudeCount}
                <span className="text-sm font-normal text-text-muted ml-2">
                  {claudePct}%
                </span>
              </div>
            </div>
          </div>

          {/* Daily activity timeline */}
          <div className="bg-surface border border-border rounded-lg p-5">
            <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-4">
              Daily Activity
            </div>
            {data.daily_activity.length === 0 ? (
              <div className="text-text-muted font-mono text-xs">No activity data</div>
            ) : (
              <div className="space-y-1.5">
                {data.daily_activity.map((d) => (
                  <div key={d.date} className="flex items-center gap-3">
                    <span className="font-mono text-xs text-text-muted w-20 shrink-0">
                      {d.date.slice(5)}
                    </span>
                    <div className="flex-1">
                      <ActivityBar count={d.count} max={maxDaily} />
                    </div>
                    <span className="font-mono text-xs text-text-muted w-8 text-right">
                      {d.count}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Event type distribution */}
          <div className="bg-surface border border-border rounded-lg p-5">
            <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-4">
              Event Types
            </div>
            {eventTypes.length === 0 ? (
              <div className="text-text-muted font-mono text-xs">No events</div>
            ) : (
              <div className="space-y-1">
                {eventTypes.map(([type, count]) => (
                  <div
                    key={type}
                    className="flex justify-between py-1.5 border-b border-border/50 last:border-0"
                  >
                    <span className="font-mono text-xs text-accent">{type}</span>
                    <span className="font-mono text-xs font-semibold text-text">
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent events */}
          <div className="bg-surface border border-border rounded-lg overflow-hidden">
            <div className="px-5 pt-5 pb-3">
              <div className="text-xs font-mono uppercase tracking-wider text-text-muted">
                Recent Events
              </div>
            </div>
            <EventTable events={data.recent_events} />
          </div>
        </>
      ) : null}
    </div>
  );
}

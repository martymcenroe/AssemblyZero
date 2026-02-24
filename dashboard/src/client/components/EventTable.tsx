import type { TelemetryEvent } from "../api";
import { ActorBadge } from "./ActorBadge";

type Column = "time" | "type" | "actor" | "repo" | "details" | "message";

interface EventTableProps {
  events: TelemetryEvent[];
  columns?: Column[];
  emptyMessage?: string;
}

function fmtTime(ts?: string): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + "…" : s;
}

const defaultColumns: Column[] = ["time", "type", "actor", "repo", "details"];

export function EventTable({ events, columns: columnsProp, emptyMessage = "No events" }: EventTableProps) {
  const columns = columnsProp ?? defaultColumns;
  const headers: Record<string, string> = {
    time: "Time",
    type: "Event Type",
    actor: "Actor",
    repo: "Repo",
    details: "Details",
    message: "Message",
  };

  if (events.length === 0) {
    return (
      <div className="text-center py-12 text-text-muted font-mono text-sm">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={col}
                className="text-left px-4 py-3 text-xs font-mono uppercase tracking-wider text-text-muted font-medium"
              >
                {headers[col]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {events.map((event, i) => (
            <tr key={event.sk ?? i} className="event-row border-b border-border/50">
              {columns.map((col) => (
                <td key={col} className="px-4 py-2.5">
                  {col === "time" && (
                    <span className="font-mono text-xs text-text-muted">
                      {fmtTime(event.timestamp)}
                    </span>
                  )}
                  {col === "type" && (
                    <span className="font-mono text-xs text-accent">
                      {event.event_type ?? "—"}
                    </span>
                  )}
                  {col === "actor" && <ActorBadge actor={event.actor} />}
                  {col === "repo" && (
                    <span className="font-mono text-xs text-text-muted">
                      {event.repo ?? "—"}
                    </span>
                  )}
                  {col === "details" && (
                    <span className="font-mono text-xs text-text-muted">
                      {event.metadata
                        ? truncate(JSON.stringify(event.metadata), 80)
                        : "—"}
                    </span>
                  )}
                  {col === "message" && (
                    <span className="text-xs text-text-muted">
                      {(event.metadata?.error_message as string) ?? "—"}
                    </span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

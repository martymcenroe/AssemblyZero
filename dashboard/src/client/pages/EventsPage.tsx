import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import type { EventsResponse } from "../api";
import { EventTable } from "../components/EventTable";

export function EventsPage() {
  const [actor, setActor] = useState("");
  const [repo, setRepo] = useState("AssemblyZero");

  const events = useQuery({
    queryKey: ["events", actor, repo],
    queryFn: () => {
      if (actor) {
        return apiFetch<EventsResponse>(
          `/api/events/by-actor?actor=${encodeURIComponent(actor)}&limit=50`
        );
      }
      return apiFetch<EventsResponse>(
        `/api/events?repo=${encodeURIComponent(repo)}&limit=50`
      );
    },
  });

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex gap-3">
        <select
          value={actor}
          onChange={(e) => setActor(e.target.value)}
          className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono text-text focus:outline-none focus:border-accent/50"
        >
          <option value="">All Actors</option>
          <option value="human">Human</option>
          <option value="claude">Claude</option>
        </select>
        <select
          value={repo}
          onChange={(e) => setRepo(e.target.value)}
          className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono text-text focus:outline-none focus:border-accent/50"
        >
          <option value="AssemblyZero">AssemblyZero</option>
          <option value="unleashed">unleashed</option>
          <option value="Talos">Talos</option>
          <option value="Aletheia">Aletheia</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-surface border border-border rounded-lg overflow-hidden">
        {events.isError ? (
          <div className="text-error font-mono text-sm p-4">
            Error: {events.error.message}
          </div>
        ) : events.isLoading ? (
          <div className="text-text-muted font-mono text-xs p-8 text-center">
            Loading…
          </div>
        ) : (
          <EventTable events={events.data?.items ?? []} />
        )}
      </div>
    </div>
  );
}

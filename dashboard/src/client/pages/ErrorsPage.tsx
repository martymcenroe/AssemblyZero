import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import type { EventsResponse } from "../api";
import { EventTable } from "../components/EventTable";

export function ErrorsPage() {
  const errors = useQuery({
    queryKey: ["errors"],
    queryFn: () => apiFetch<EventsResponse>("/api/errors"),
  });

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      {errors.isError ? (
        <div className="text-error font-mono text-sm p-4">
          Error: {errors.error.message}
        </div>
      ) : errors.isLoading ? (
        <div className="text-text-muted font-mono text-xs p-8 text-center">
          Loading…
        </div>
      ) : (
        <EventTable
          events={errors.data?.items ?? []}
          columns={["time", "type", "actor", "repo", "message"]}
          emptyMessage="No errors recorded"
        />
      )}
    </div>
  );
}

import type { DaySummary } from "../api";

interface SparklineProps {
  days: DaySummary[];
}

export function Sparkline({ days }: SparklineProps) {
  // Reverse so oldest is on the left
  const ordered = [...days].reverse();
  const maxVal = Math.max(...ordered.map((d) => d.total), 1);
  const barHeight = 80;

  return (
    <div className="flex items-end gap-1.5" style={{ height: barHeight + 24 }}>
      {ordered.map((d) => {
        const humanH = Math.max(2, (d.human / maxVal) * barHeight);
        const claudeH = Math.max(2, (d.claude / maxVal) * barHeight);
        return (
          <div key={d.date} className="flex flex-col items-center gap-0.5 flex-1 min-w-0">
            <div className="flex flex-col items-center gap-px" style={{ height: barHeight, justifyContent: "flex-end" }}>
              <div
                className="w-full rounded-t-sm bg-claude"
                style={{ height: claudeH, opacity: 0.85 }}
                title={`Claude: ${d.claude}`}
              />
              <div
                className="w-full rounded-b-sm bg-human"
                style={{ height: humanH, opacity: 0.85 }}
                title={`Human: ${d.human}`}
              />
            </div>
            <span className="text-[10px] font-mono text-text-muted mt-1 truncate w-full text-center">
              {d.date.slice(5)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

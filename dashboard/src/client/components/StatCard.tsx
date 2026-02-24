interface StatCardProps {
  label: string;
  value: number | string;
  variant: "total" | "human" | "claude" | "error";
  delay?: number;
}

const variantStyles: Record<StatCardProps["variant"], { color: string; glow: string; border: string }> = {
  total: { color: "text-accent", glow: "stat-glow-accent", border: "border-accent/20" },
  human: { color: "text-human", glow: "stat-glow-human", border: "border-human/20" },
  claude: { color: "text-claude", glow: "stat-glow-claude", border: "border-claude/20" },
  error: { color: "text-error", glow: "stat-glow-error", border: "border-error/20" },
};

export function StatCard({ label, value, variant, delay = 0 }: StatCardProps) {
  const v = variantStyles[variant];
  return (
    <div
      className={`animate-fade-up bg-surface border ${v.border} rounded-lg p-5`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-2">
        {label}
      </div>
      <div className={`text-3xl font-mono font-bold ${v.color} ${v.glow}`}>
        {value}
      </div>
    </div>
  );
}

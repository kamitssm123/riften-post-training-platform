export function Progress({
  value,
  max = 100,
  color = "var(--accent)",
  className = "",
  showLabel = false,
}: {
  value: number;
  max?: number;
  color?: string;
  className?: string;
  showLabel?: boolean;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div
        className="h-1.5 flex-1 overflow-hidden rounded-full"
        style={{ background: "var(--bg-hover)" }}
      >
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      {showLabel && (
        <span className="shrink-0 text-[10px] tabular-nums text-[var(--text-faint)]">
          {pct.toFixed(0)}%
        </span>
      )}
    </div>
  );
}

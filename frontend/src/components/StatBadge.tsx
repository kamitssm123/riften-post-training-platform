type Tone = "neutral" | "accent" | "dim";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "border-[var(--border-strong)] text-[var(--text)]",
  accent: "border-[var(--accent)] text-[var(--accent)]",
  dim: "border-[var(--border)] text-[var(--text-faint)]",
};

export function StatBadge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${TONE_CLASSES[tone]}`}
    >
      {label}
    </span>
  );
}

/** Compact status read for a trace row: usable / error / truncated, at a glance. */
export function TraceStatusBadges({
  errored,
  truncated,
  feedback,
}: {
  errored: boolean;
  truncated: boolean;
  feedback: string | null;
}) {
  return (
    <div className="flex items-center gap-1">
      {errored && <StatBadge label="Error" tone="accent" />}
      {truncated && <StatBadge label="Truncated" tone="accent" />}
      {!errored && !truncated && <StatBadge label="OK" tone="dim" />}
      {feedback && (
        <StatBadge label={feedback} tone={feedback === "weak" ? "accent" : "dim"} />
      )}
    </div>
  );
}

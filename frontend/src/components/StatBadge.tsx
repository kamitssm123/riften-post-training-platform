type Tone = "neutral" | "accent" | "dim" | "success" | "warning" | "error" | "info";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "border-[var(--border-strong)] bg-[var(--bg-hover)] text-[var(--text)]",
  accent: "border-[var(--accent)] bg-[var(--accent-dim)] text-[var(--accent)]",
  dim: "border-[var(--border)] bg-transparent text-[var(--text-faint)]",
  success: "border-[var(--success)] bg-[var(--success-dim)] text-[var(--success)]",
  warning: "border-[var(--warning)] bg-[var(--warning-dim)] text-[var(--warning)]",
  error: "border-[var(--error)] bg-[var(--error-dim)] text-[var(--error)]",
  info: "border-[var(--info)] bg-[var(--info-dim)] text-[var(--info)]",
};

export function StatBadge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${TONE_CLASSES[tone]}`}
    >
      {label}
    </span>
  );
}

// Feedback is a human quality rating, independent of whether the call itself
// succeeded -- labelled distinctly from the Error/Truncated/OK call-outcome
// badge so a healthy call rated "ok" doesn't render as two identical "OK"
// badges side by side.
const FEEDBACK_LABELS: Record<string, string> = {
  weak: "Weak",
  ok: "Fair",
  strong: "Great",
};

const FEEDBACK_TONES: Record<string, Tone> = {
  weak: "error",
  ok: "info",
  strong: "success",
};

export function FeedbackBadge({ feedback }: { feedback: string | null }) {
  if (!feedback) return null;
  return (
    <StatBadge label={FEEDBACK_LABELS[feedback] ?? feedback} tone={FEEDBACK_TONES[feedback] ?? "neutral"} />
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
    <div className="flex flex-wrap items-center gap-1">
      {errored && <StatBadge label="Error" tone="error" />}
      {truncated && <StatBadge label="Truncated" tone="warning" />}
      {!errored && !truncated && <StatBadge label="OK" tone="success" />}
      <FeedbackBadge feedback={feedback} />
    </div>
  );
}

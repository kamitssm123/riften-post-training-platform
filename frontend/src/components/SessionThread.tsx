import type { SessionResponse } from "../types/trace";
import { StatBadge } from "./StatBadge";

interface Props {
  session: SessionResponse | null;
  loading: boolean;
  onSelectTrace: (traceId: string) => void;
  onClose: () => void;
}

export function SessionThread({ session, loading, onSelectTrace, onClose }: Props) {
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-[12px] text-[var(--text-faint)]">
        Loading session…
      </div>
    );
  }
  if (!session) return null;

  // The longest trace already contains the full transcript (agent clients
  // resend the whole conversation each turn), so render off that one, but
  // let each turn's badges + click-through reflect its own trace_id.
  const byTurn = [...session.traces].sort((a, b) => a.turn_index - b.turn_index);
  const longest = byTurn.reduce((a, b) => (b.messages.length > a.messages.length ? b : a));

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div>
          <div className="font-mono text-[12px]">{session.session_id}</div>
          <div className="mt-1 text-[11px] text-[var(--text-faint)]">
            {byTurn.length} trace{byTurn.length !== 1 ? "s" : ""} &middot; {longest.messages.length}{" "}
            messages in longest transcript
          </div>
        </div>
        <button onClick={onClose} className="text-[var(--text-faint)] hover:text-[var(--text)]">
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        <div className="border-b border-[var(--border)] px-4 py-2 text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
          Full transcript (from longest trace)
        </div>
        {longest.messages.map((m, i) => (
          <div key={i} className="border-b border-[var(--border)] px-4 py-3">
            <div className="mb-1 text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
              {m.role}
            </div>
            <div className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-[var(--text-dim)]">
              {m.content}
            </div>
          </div>
        ))}

        <div className="border-b border-t border-[var(--border)] px-4 py-2 text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
          Traces by turn
        </div>
        {byTurn.map((t) => {
          const errored = t.status_code >= 400 || (t.tool_calls ?? []).some((tc) => tc.result.status_code >= 400);
          const truncated = t.finish_reason === "length";
          return (
            <button
              key={t.trace_id}
              onClick={() => onSelectTrace(t.trace_id)}
              className="flex w-full items-center justify-between border-b border-[var(--border)] px-4 py-2.5 text-left text-[11px] hover:bg-[var(--bg-raised)]"
            >
              <span className="flex items-center gap-2">
                <span className="tabular-nums text-[var(--text-faint)]">turn {t.turn_index}</span>
                <span className="font-mono text-[var(--text-dim)]">{t.model}</span>
                {t.is_retrial && <StatBadge label="retrial" tone="dim" />}
                {errored && <StatBadge label="error" tone="accent" />}
                {truncated && <StatBadge label="truncated" tone="accent" />}
                {t.feedback && (
                  <StatBadge label={t.feedback} tone={t.feedback === "weak" ? "accent" : "dim"} />
                )}
              </span>
              <span className="font-mono text-[var(--text-faint)]">{t.trace_id.slice(0, 8)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

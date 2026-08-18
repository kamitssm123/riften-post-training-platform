import { ChevronRight, GitBranch, MessageSquare } from "lucide-react";
import type { SessionResponse } from "../types/trace";
import { StatBadge } from "./StatBadge";
import { LoadingSpinner } from "./ui/LoadingSpinner";
import { PanelHeader } from "./ui/PanelHeader";

interface Props {
  session: SessionResponse | null;
  loading: boolean;
  onSelectTrace: (traceId: string) => void;
  onClose: () => void;
}

export function SessionThread({ session, loading, onSelectTrace, onClose }: Props) {
  if (loading) {
    return <LoadingSpinner label="Loading session…" />;
  }
  if (!session) return null;

  const byTurn = [...session.traces].sort((a, b) => a.turn_index - b.turn_index);
  const longest = byTurn.reduce((a, b) => (b.messages.length > a.messages.length ? b : a));

  return (
    <div className="flex h-full flex-col">
      <PanelHeader
        title={<span className="font-mono text-[12px]">{session.session_id}</span>}
        subtitle={`${byTurn.length} trace${byTurn.length !== 1 ? "s" : ""} · ${longest.messages.length} messages`}
        icon={<GitBranch size={14} />}
        onClose={onClose}
      />

      <div className="flex-1 overflow-auto">
        <div className="section-label px-4 py-2.5">Full transcript</div>
        <div className="space-y-2 px-3 pb-3">
          {longest.messages.map((m, i) => (
            <div
              key={i}
              className="rounded-xl border px-3.5 py-3"
              style={{
                borderColor: m.role === "user" ? "var(--info-dim)" : "var(--border)",
                background: m.role === "user" ? "var(--info-dim)" : "var(--bg-raised)",
              }}
            >
              <div className="mb-1.5 flex items-center gap-1.5">
                <MessageSquare size={10} className="text-[var(--text-faint)]" />
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-faint)]">
                  {m.role}
                </span>
              </div>
              <div className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-[var(--text-dim)]">
                {m.content}
              </div>
            </div>
          ))}
        </div>

        <div
          className="section-label border-t px-4 py-2.5"
          style={{ borderColor: "var(--border)" }}
        >
          Traces by turn
        </div>
        <div className="space-y-1.5 px-3 pb-3">
          {byTurn.map((t) => {
            const errored =
              t.status_code >= 400 ||
              (t.tool_calls ?? []).some((tc) => tc.result.status_code >= 400);
            const truncated = t.finish_reason === "length";
            return (
              <button
                key={t.trace_id}
                onClick={() => onSelectTrace(t.trace_id)}
                className="group flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left text-[11px] transition-all hover:shadow-sm"
                style={{ borderColor: "var(--border)", background: "var(--bg-raised)" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--brand)";
                  e.currentTarget.style.background = "var(--brand-dim)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border)";
                  e.currentTarget.style.background = "var(--bg-raised)";
                }}
              >
                <span className="flex flex-wrap items-center gap-2">
                  <span
                    className="flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold tabular-nums"
                    style={{ background: "var(--bg-hover)", color: "var(--text-dim)" }}
                  >
                    {t.turn_index}
                  </span>
                  <span className="font-mono text-[var(--text-dim)]">{t.model}</span>
                  {t.is_retrial && <StatBadge label="retrial" tone="dim" />}
                  {errored && <StatBadge label="error" tone="error" />}
                  {truncated && <StatBadge label="truncated" tone="warning" />}
                  {t.feedback && (
                    <StatBadge
                      label={t.feedback}
                      tone={
                        t.feedback === "weak"
                          ? "error"
                          : t.feedback === "strong"
                            ? "success"
                            : "info"
                      }
                    />
                  )}
                </span>
                <span className="flex items-center gap-1 font-mono text-[var(--text-faint)] group-hover:text-[var(--text)]">
                  {t.trace_id.slice(0, 8)}
                  <ChevronRight size={12} />
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

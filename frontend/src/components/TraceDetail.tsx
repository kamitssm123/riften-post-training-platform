import type { TraceDetail as TraceDetailT } from "../types/trace";
import { StatBadge } from "./StatBadge";

interface Props {
  trace: TraceDetailT | null;
  loading: boolean;
  onOpenSession: (sessionId: string) => void;
  onClose: () => void;
}

function MessageBubble({ role, content }: { role: string; content: string }) {
  const isAssistant = role === "assistant";
  return (
    <div className="border-b border-[var(--border)] px-4 py-3">
      <div className="mb-1 text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
        {role}
      </div>
      <div
        className={`whitespace-pre-wrap text-[12.5px] leading-relaxed ${
          isAssistant ? "text-[var(--text)]" : "text-[var(--text-dim)]"
        }`}
      >
        {content}
      </div>
    </div>
  );
}

export function TraceDetail({ trace, loading, onOpenSession, onClose }: Props) {
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-[12px] text-[var(--text-faint)]">
        Loading…
      </div>
    );
  }
  if (!trace) {
    return (
      <div className="flex h-full items-center justify-center text-[12px] text-[var(--text-faint)]">
        Select a trace to inspect it.
      </div>
    );
  }

  const errored = trace.status_code >= 400 || (trace.tool_calls ?? []).some((tc) => tc.result.status_code >= 400);
  const truncated = trace.finish_reason === "length";

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-4 py-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[12px] text-[var(--text)]">{trace.trace_id}</span>
            {errored && <StatBadge label="Error" tone="accent" />}
            {truncated && <StatBadge label="Truncated" tone="accent" />}
            {trace.feedback && (
              <StatBadge label={trace.feedback} tone={trace.feedback === "weak" ? "accent" : "dim"} />
            )}
            {trace.is_retrial && <StatBadge label="Retrial" tone="dim" />}
            {trace.continuation_status && (
              <StatBadge
                label={`continuation: ${trace.continuation_status}`}
                tone={trace.continuation_status === "rejected" ? "accent" : "dim"}
              />
            )}
          </div>
          <button
            onClick={() => onOpenSession(trace.session_id)}
            className="mt-1.5 font-mono text-[11px] text-[var(--text-faint)] hover:text-[var(--accent)]"
          >
            session {trace.session_id} → turn {trace.turn_index}
          </button>
        </div>
        <button onClick={onClose} className="text-[var(--text-faint)] hover:text-[var(--text)]">
          ✕
        </button>
      </div>

      <div className="grid grid-cols-4 gap-px border-b border-[var(--border)] bg-[var(--border)] text-[11px]">
        {[
          ["Model", trace.model],
          ["Status", String(trace.status_code)],
          ["Finish", trace.finish_reason],
          ["Latency", `${trace.latency_ms}ms`],
          ["Prompt tok", String(trace.tokens_prompt)],
          ["Completion tok", String(trace.tokens_completion)],
          ["Cost", `$${trace.cost_usd.toFixed(4)}`],
          ["Timestamp", new Date(trace.timestamp).toLocaleString()],
        ].map(([label, value]) => (
          <div key={label} className="bg-[var(--bg)] px-3 py-2">
            <div className="text-[10px] uppercase tracking-wider text-[var(--text-faint)]">{label}</div>
            <div className="mt-0.5 truncate text-[var(--text)]">{value}</div>
          </div>
        ))}
      </div>

      <div className="flex-1 overflow-auto">
        <div className="border-b border-[var(--border)] px-4 py-2 text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
          Transcript
        </div>
        {trace.messages.map((m, i) => (
          <MessageBubble key={i} role={m.role} content={m.content} />
        ))}
        <MessageBubble role="assistant (response)" content={trace.response.content} />

        {trace.tool_calls && trace.tool_calls.length > 0 && (
          <div>
            <div className="border-b border-t border-[var(--border)] px-4 py-2 text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
              Tool calls
            </div>
            {trace.tool_calls.map((tc, i) => (
              <div key={i} className="border-b border-[var(--border)] px-4 py-3 text-[12px]">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[var(--text)]">{tc.name}</span>
                  <StatBadge
                    label={String(tc.result.status_code)}
                    tone={tc.result.status_code >= 400 ? "accent" : "dim"}
                  />
                </div>
                <pre className="mt-2 overflow-auto rounded-sm border border-[var(--border)] bg-[var(--bg-raised)] p-2 text-[11px] text-[var(--text-dim)]">
{JSON.stringify(tc.args, null, 2)}
                </pre>
                <div className="mt-2 text-[11px] text-[var(--text-faint)]">result</div>
                <pre className="mt-1 overflow-auto rounded-sm border border-[var(--border)] bg-[var(--bg-raised)] p-2 text-[11px] text-[var(--text-dim)]">
{JSON.stringify(tc.result.output, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

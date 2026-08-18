import { ArrowRight, Bot, Copy, FileText, User, Wrench } from "lucide-react";
import { useState } from "react";
import type { TraceDetail as TraceDetailT } from "../types/trace";
import { StatBadge } from "./StatBadge";
import { Card, CardContent } from "./ui/Card";
import { LoadingSpinner } from "./ui/LoadingSpinner";
import { PanelHeader } from "./ui/PanelHeader";
import { Tooltip } from "./ui/Tooltip";

interface Props {
  trace: TraceDetailT | null;
  loading: boolean;
  onOpenSession: (sessionId: string) => void;
  onClose: () => void;
}

function MessageBubble({ role, content }: { role: string; content: string }) {
  const isAssistant = role.startsWith("assistant");
  const isUser = role === "user";
  const Icon = isUser ? User : Bot;

  return (
    <div
      className={`mx-3 my-2 rounded-xl border px-3.5 py-3 ${
        isAssistant ? "ml-6" : "mr-6"
      }`}
      style={{
        borderColor: isAssistant ? "var(--border)" : "var(--info-dim)",
        background: isAssistant ? "var(--bg-raised)" : "var(--info-dim)",
      }}
    >
      <div className="mb-2 flex items-center gap-2">
        <div
          className="flex h-6 w-6 items-center justify-center rounded-full"
          style={{
            background: isAssistant ? "var(--accent-dim)" : "var(--info-dim)",
            color: isAssistant ? "var(--accent)" : "var(--info)",
          }}
        >
          <Icon size={12} strokeWidth={2} />
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-faint)]">
          {role}
        </span>
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

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="rounded-lg border px-3 py-2.5"
      style={{ borderColor: "var(--border)", background: "var(--bg-subtle)" }}
    >
      <div className="section-label">{label}</div>
      <div className="mt-1 truncate text-[12px] font-semibold text-[var(--text)]">{value}</div>
    </div>
  );
}

export function TraceDetail({ trace, loading, onOpenSession, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  if (loading) {
    return <LoadingSpinner label="Loading trace…" />;
  }
  if (!trace) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <div
          className="flex h-14 w-14 items-center justify-center rounded-2xl"
          style={{ background: "var(--brand-dim)", color: "var(--brand)" }}
        >
          <FileText size={24} />
        </div>
        <div className="text-[13px] font-medium text-[var(--text-dim)]">
          Select a trace to inspect it
        </div>
        <div className="text-[11px] text-[var(--text-faint)]">
          Click any row in the table to view its full transcript and metadata.
        </div>
      </div>
    );
  }

  const errored =
    trace.status_code >= 400 ||
    (trace.tool_calls ?? []).some((tc) => tc.result.status_code >= 400);
  const truncated = trace.finish_reason === "length";

  const copyId = () => {
    navigator.clipboard.writeText(trace.trace_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex h-full flex-col">
      <PanelHeader
        title={
          <span className="flex items-center gap-2 font-mono text-[12px]">
            {trace.trace_id}
            <Tooltip content={copied ? "Copied!" : "Copy trace ID"}>
              <button onClick={copyId} className="btn-ghost !p-1">
                <Copy size={12} />
              </button>
            </Tooltip>
          </span>
        }
        subtitle={`${trace.model} · turn ${trace.turn_index}`}
        icon={<FileText size={14} />}
        onClose={onClose}
      >
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {errored && <StatBadge label="Error" tone="error" />}
          {truncated && <StatBadge label="Truncated" tone="warning" />}
          {trace.feedback && (
            <StatBadge
              label={trace.feedback}
              tone={
                trace.feedback === "weak"
                  ? "error"
                  : trace.feedback === "strong"
                    ? "success"
                    : "info"
              }
            />
          )}
          {trace.is_retrial && <StatBadge label="Retrial" tone="dim" />}
          {trace.continuation_status && (
            <StatBadge
              label={`continuation: ${trace.continuation_status}`}
              tone={trace.continuation_status === "rejected" ? "error" : "dim"}
            />
          )}
        </div>
        <button
          onClick={() => onOpenSession(trace.session_id)}
          className="btn mt-2.5 flex w-fit items-center gap-1.5 !text-[11px]"
        >
          View session {trace.session_id.slice(0, 8)}…
          <ArrowRight size={12} />
        </button>
      </PanelHeader>

      <div className="grid grid-cols-2 gap-2 border-b p-3" style={{ borderColor: "var(--border)" }}>
        <MetricBox label="Model" value={trace.model} />
        <MetricBox label="Status" value={String(trace.status_code)} />
        <MetricBox label="Finish" value={trace.finish_reason} />
        <MetricBox label="Latency" value={`${trace.latency_ms}ms`} />
        <MetricBox label="Prompt tokens" value={String(trace.tokens_prompt)} />
        <MetricBox label="Completion tokens" value={String(trace.tokens_completion)} />
        <MetricBox label="Cost" value={`$${trace.cost_usd.toFixed(4)}`} />
        <MetricBox label="Timestamp" value={new Date(trace.timestamp).toLocaleString()} />
      </div>

      <div className="flex-1 overflow-auto py-2">
        <div className="section-label px-4 py-2">Transcript</div>
        {trace.messages.map((m, i) => (
          <MessageBubble key={i} role={m.role} content={m.content} />
        ))}
        <MessageBubble role="assistant (response)" content={trace.response.content} />

        {trace.tool_calls && trace.tool_calls.length > 0 && (
          <div className="mt-2 px-3">
            <div className="section-label mb-2 flex items-center gap-1.5 px-1">
              <Wrench size={11} />
              Tool calls ({trace.tool_calls.length})
            </div>
            {trace.tool_calls.map((tc, i) => (
              <Card key={i} className="mb-2">
                <CardContent className="!p-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[12px] font-semibold">{tc.name}</span>
                    <StatBadge
                      label={String(tc.result.status_code)}
                      tone={tc.result.status_code >= 400 ? "error" : "success"}
                    />
                  </div>
                  <div className="mt-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-faint)]">
                    Arguments
                  </div>
                  <pre
                    className="mt-1 overflow-auto rounded-lg border p-2.5 text-[11px] text-[var(--text-dim)]"
                    style={{ borderColor: "var(--border)", background: "var(--bg-subtle)" }}
                  >
                    {JSON.stringify(tc.args, null, 2)}
                  </pre>
                  <div className="mt-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-faint)]">
                    Result
                  </div>
                  <pre
                    className="mt-1 overflow-auto rounded-lg border p-2.5 text-[11px] text-[var(--text-dim)]"
                    style={{ borderColor: "var(--border)", background: "var(--bg-subtle)" }}
                  >
                    {JSON.stringify(tc.result.output, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

import type { TraceSummary } from "../types/trace";
import { TraceStatusBadges } from "./StatBadge";

interface Props {
  traces: TraceSummary[];
  onSelect: (traceId: string) => void;
  selectedId: string | null;
}

function isErrored(t: TraceSummary): boolean {
  return t.status_code >= 400 || t.has_tool_error;
}

function isTruncated(t: TraceSummary): boolean {
  return t.finish_reason === "length";
}

const HEADERS = ["Status", "Model", "Turn", "Tokens", "Cost", "Latency", "Timestamp"];

export function TraceTable({ traces, onSelect, selectedId }: Props) {
  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-left text-[12px]">
        <thead className="sticky top-0 z-10 bg-[var(--bg)]">
          <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-wider text-[var(--text-faint)]">
            {HEADERS.map((h) => (
              <th key={h} className="whitespace-nowrap px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {traces.map((t) => {
            const errored = isErrored(t);
            const truncated = isTruncated(t);
            const selected = t.trace_id === selectedId;
            return (
              <tr
                key={t.trace_id}
                onClick={() => onSelect(t.trace_id)}
                className={`cursor-pointer border-b border-[var(--border)] transition-colors ${
                  selected ? "bg-[var(--bg-hover)]" : "hover:bg-[var(--bg-raised)]"
                }`}
              >
                <td className="px-3 py-2">
                  <TraceStatusBadges errored={errored} truncated={truncated} feedback={t.feedback} />
                </td>
                <td className="px-3 py-2 font-mono text-[11px] text-[var(--text-dim)]">
                  {t.model}
                </td>
                <td className="px-3 py-2 tabular-nums text-[var(--text-dim)]">
                  {t.turn_index}
                  {t.is_retrial && <span className="ml-1 text-[var(--accent)]">retrial</span>}
                </td>
                <td className="px-3 py-2 tabular-nums text-[var(--text-dim)]">
                  {t.tokens_prompt}+{t.tokens_completion}
                </td>
                <td className="px-3 py-2 tabular-nums text-[var(--text-dim)]">
                  ${t.cost_usd.toFixed(4)}
                </td>
                <td className="px-3 py-2 tabular-nums text-[var(--text-dim)]">{t.latency_ms}ms</td>
                <td className="px-3 py-2 whitespace-nowrap text-[var(--text-faint)]">
                  {new Date(t.timestamp).toLocaleString()}
                </td>
              </tr>
            );
          })}
          {traces.length === 0 && (
            <tr>
              <td colSpan={HEADERS.length} className="px-3 py-10 text-center text-[var(--text-faint)]">
                No traces match the current filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

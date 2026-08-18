import {
  Activity,
  Clock,
  Cpu,
  DollarSign,
  Hash,
  Search,
  ShieldCheck,
} from "lucide-react";
import type { TraceSummary } from "../types/trace";
import { TraceStatusBadges } from "./StatBadge";
import { Progress } from "./ui/Progress";
import { TableSkeleton } from "./ui/Skeleton";
import { Tooltip } from "./ui/Tooltip";

interface Props {
  traces: TraceSummary[];
  loading?: boolean;
  onSelect: (traceId: string) => void;
  selectedId: string | null;
}

function isErrored(t: TraceSummary): boolean {
  return t.status_code >= 400 || t.has_tool_error;
}

function isTruncated(t: TraceSummary): boolean {
  return t.finish_reason === "length";
}

const COLUMNS = [
  { key: "status", label: "Status", icon: ShieldCheck, width: "" },
  { key: "model", label: "Model", icon: Cpu, width: "" },
  { key: "turn", label: "Turn", icon: Hash, width: "w-20" },
  { key: "tokens", label: "Tokens", icon: Activity, width: "w-24" },
  { key: "cost", label: "Cost", icon: DollarSign, width: "w-28" },
  { key: "latency", label: "Latency", icon: Clock, width: "w-32" },
  { key: "timestamp", label: "Timestamp", icon: null, width: "" },
] as const;

export function TraceTable({ traces, loading, onSelect, selectedId }: Props) {
  const maxLatency = Math.max(...traces.map((t) => t.latency_ms), 1);
  const maxCost = Math.max(...traces.map((t) => t.cost_usd), 0.0001);

  if (loading && traces.length === 0) {
    return <TableSkeleton rows={10} />;
  }

  return (
    <table className="w-full border-collapse text-left text-[12px]">
      <thead>
        <tr
          className="sticky top-0 z-10 border-b"
          style={{
            borderColor: "var(--border)",
            background: "var(--bg-subtle)",
          }}
        >
          {COLUMNS.map(({ key, label, icon: Icon, width }) => (
            <th
              key={key}
              className={`whitespace-nowrap px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-faint)] ${width}`}
            >
              <span className="flex items-center gap-1.5">
                {Icon && <Icon size={11} strokeWidth={2} />}
                {label}
              </span>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {traces.map((t, idx) => {
          const errored = isErrored(t);
          const truncated = isTruncated(t);
          const selected = t.trace_id === selectedId;
          return (
            <tr
              key={t.trace_id}
              onClick={() => onSelect(t.trace_id)}
              className="group cursor-pointer border-b transition-all duration-100"
              style={{
                borderColor: "var(--border)",
                background: selected
                  ? "var(--selected-row)"
                  : idx % 2 === 1
                    ? "var(--table-stripe)"
                    : "transparent",
                boxShadow: selected ? "inset 3px 0 0 var(--selected-border)" : "none",
              }}
              onMouseEnter={(e) => {
                if (!selected) e.currentTarget.style.background = "var(--bg-hover)";
              }}
              onMouseLeave={(e) => {
                if (!selected) {
                  e.currentTarget.style.background =
                    idx % 2 === 1 ? "var(--table-stripe)" : "transparent";
                }
              }}
            >
              <td className="px-4 py-2.5">
                <TraceStatusBadges errored={errored} truncated={truncated} feedback={t.feedback} />
              </td>
              <td className="px-4 py-2.5">
                <Tooltip content={t.model}>
                  <span className="data-cell inline-block max-w-[140px] truncate">
                    {t.model}
                  </span>
                </Tooltip>
              </td>
              <td className="px-4 py-2.5 tabular-nums text-[var(--text-dim)]">
                <span className="font-medium">{t.turn_index}</span>
                {t.is_retrial && (
                  <span
                    className="ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                    style={{ background: "var(--accent-dim)", color: "var(--accent)" }}
                  >
                    retrial
                  </span>
                )}
              </td>
              <td className="px-4 py-2.5 tabular-nums">
                <span className="text-[var(--text-faint)]">{t.tokens_prompt}</span>
                <span className="mx-0.5 text-[var(--border-strong)]">+</span>
                <span className="font-medium text-[var(--text-dim)]">{t.tokens_completion}</span>
              </td>
              <td className="px-4 py-2.5">
                <div className="flex flex-col gap-1">
                  <span className="tabular-nums font-medium text-[var(--text-dim)]">
                    ${t.cost_usd.toFixed(4)}
                  </span>
                  <Progress value={t.cost_usd} max={maxCost} color="var(--success)" />
                </div>
              </td>
              <td className="px-4 py-2.5">
                <div className="flex flex-col gap-1">
                  <span className="tabular-nums font-medium text-[var(--text-dim)]">
                    {t.latency_ms}
                    <span className="ml-0.5 text-[10px] font-normal text-[var(--text-faint)]">ms</span>
                  </span>
                  <Progress value={t.latency_ms} max={maxLatency} color="var(--info)" />
                </div>
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-[var(--text-faint)]">
                {new Date(t.timestamp).toLocaleString()}
              </td>
            </tr>
          );
        })}
        {traces.length === 0 && !loading && (
          <tr>
            <td colSpan={COLUMNS.length} className="px-4 py-20 text-center">
              <div className="flex flex-col items-center gap-4 text-[var(--text-faint)]">
                <div
                  className="flex h-16 w-16 items-center justify-center rounded-2xl"
                  style={{
                    background: "var(--brand-dim)",
                    color: "var(--brand)",
                  }}
                >
                  <Search size={28} strokeWidth={1.5} />
                </div>
                <div>
                  <div className="text-[15px] font-semibold text-[var(--text)]">
                    No traces found
                  </div>
                  <div className="mt-1 text-[12px]">
                    Try adjusting your filters to see more results.
                  </div>
                </div>
              </div>
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

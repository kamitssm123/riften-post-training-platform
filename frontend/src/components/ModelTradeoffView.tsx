import { Gauge } from "lucide-react";
import type { ModelTradeoff } from "../types/modelTradeoff";
import { colorForModel } from "../utils/modelColors";
import { ModelTradeoffChart } from "./ModelTradeoffChart";
import { Card, CardContent } from "./ui/Card";
import { TableSkeleton } from "./ui/Skeleton";
import { Tooltip } from "./ui/Tooltip";

interface Props {
  items: ModelTradeoff[] | null;
  loading: boolean;
}

function QualityCell({ item }: { item: ModelTradeoff }) {
  if (item.avg_quality_score === null) {
    return <span className="text-[var(--text-faint)]">no feedback data</span>;
  }
  return (
    <span>
      <span className="font-semibold tabular-nums text-[var(--text)]">
        {item.avg_quality_score.toFixed(2)}
      </span>
      <span className="ml-1 text-[10px] text-[var(--text-faint)]">
        ({(item.feedback_coverage * 100).toFixed(0)}% coverage)
      </span>
    </span>
  );
}

export function ModelTradeoffView({ items, loading }: Props) {
  if (loading || !items) {
    return (
      <div className="space-y-3">
        <div className="card h-[360px] animate-pulse" style={{ background: "var(--bg-hover)" }} />
        <TableSkeleton rows={5} />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div
        className="flex h-[300px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed text-center"
        style={{ borderColor: "var(--border)" }}
      >
        <Gauge size={22} className="text-[var(--text-faint)]" />
        <div className="text-[12px] text-[var(--text-faint)]">No traces in the corpus yet.</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent>
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-[13px] font-semibold">Cost vs. quality, per model</div>
              <div className="text-[11px] text-[var(--text-faint)]">
                Validates whether cheaper models are actually the ones worth routing to.
              </div>
            </div>
          </div>
          <ModelTradeoffChart items={items} />
        </CardContent>
      </Card>

      <Card>
        <div className="overflow-auto">
          <table className="w-full border-collapse text-left text-[12px]">
            <thead>
              <tr
                className="border-b"
                style={{ borderColor: "var(--border)", background: "var(--bg-subtle)" }}
              >
                {[
                  "Model",
                  "Traces",
                  "Avg cost",
                  "Avg latency",
                  "Avg quality",
                  "Error rate",
                  "Truncation rate",
                  "Avg prompt tok",
                  "Avg completion tok",
                ].map((label) => (
                  <th
                    key={label}
                    className="whitespace-nowrap px-3.5 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-faint)]"
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => (
                <tr
                  key={item.model}
                  className="border-b"
                  style={{
                    borderColor: "var(--border)",
                    background: idx % 2 === 1 ? "var(--table-stripe)" : "transparent",
                  }}
                >
                  <td className="px-3.5 py-2.5">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="inline-block h-2 w-2 shrink-0 rounded-full"
                        style={{ background: colorForModel(item.model) }}
                      />
                      <span className="data-cell">{item.model}</span>
                    </div>
                  </td>
                  <td className="px-3.5 py-2.5 tabular-nums text-[var(--text-dim)]">
                    {item.trace_count}
                  </td>
                  <td className="px-3.5 py-2.5 tabular-nums text-[var(--text-dim)]">
                    {item.avg_cost_usd !== null ? `$${item.avg_cost_usd.toFixed(6)}` : "—"}
                  </td>
                  <td className="px-3.5 py-2.5 tabular-nums text-[var(--text-dim)]">
                    {item.avg_latency_ms !== null ? `${item.avg_latency_ms.toFixed(0)}ms` : "—"}
                  </td>
                  <td className="px-3.5 py-2.5">
                    <QualityCell item={item} />
                  </td>
                  <td className="px-3.5 py-2.5 tabular-nums" style={{ color: "var(--error)" }}>
                    {(item.error_rate * 100).toFixed(1)}%
                  </td>
                  <td className="px-3.5 py-2.5 tabular-nums" style={{ color: "var(--warning)" }}>
                    {(item.truncation_rate * 100).toFixed(1)}%
                  </td>
                  <td className="px-3.5 py-2.5 tabular-nums text-[var(--text-faint)]">
                    <Tooltip content="Average prompt tokens per call">
                      <span>{item.avg_tokens_prompt?.toFixed(0) ?? "—"}</span>
                    </Tooltip>
                  </td>
                  <td className="px-3.5 py-2.5 tabular-nums text-[var(--text-faint)]">
                    <Tooltip content="Average completion tokens per call">
                      <span>{item.avg_tokens_completion?.toFixed(0) ?? "—"}</span>
                    </Tooltip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

import { ExternalLink, FileWarning } from "lucide-react";
import type { ExclusionReport } from "../types/exclusion";
import { Card, CardContent } from "./ui/Card";
import { LoadingSpinner } from "./ui/LoadingSpinner";
import { PanelHeader } from "./ui/PanelHeader";
import { Progress } from "./ui/Progress";

interface Props {
  report: ExclusionReport | null;
  loading: boolean;
  onClose: () => void;
  onInspectTrace: (traceId: string) => void;
}

function ReasonTable({
  excluded,
  onInspectTrace,
}: {
  excluded: Record<string, { count: number; sample_trace_ids: string[] }>;
  onInspectTrace: (traceId: string) => void;
}) {
  const entries = Object.entries(excluded);
  if (entries.length === 0) {
    return (
      <div
        className="rounded-xl border border-dashed px-4 py-6 text-center text-[11px] text-[var(--text-faint)]"
        style={{ borderColor: "var(--border)" }}
      >
        No exclusions.
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      {entries.map(([reason, data]) => (
        <Card key={reason}>
          <CardContent className="!p-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] font-semibold text-[var(--text)]">
                {reason}
              </span>
              <span
                className="rounded-full px-2.5 py-0.5 text-[11px] font-bold tabular-nums"
                style={{ background: "var(--error-dim)", color: "var(--error)" }}
              >
                {data.count}
              </span>
            </div>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {data.sample_trace_ids.map((id) => (
                <button
                  key={id}
                  onClick={() => onInspectTrace(id)}
                  className="btn flex items-center gap-1 !px-2 !py-1 font-mono !text-[10px]"
                >
                  {id.slice(0, 8)}
                  <ExternalLink size={9} />
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ExportSection({
  title,
  considered,
  kept,
  keptLabel,
  extra,
  excluded,
  onInspectTrace,
}: {
  title: string;
  considered: number;
  kept: number;
  keptLabel: string;
  extra?: React.ReactNode;
  excluded: Record<string, { count: number; sample_trace_ids: string[] }>;
  onInspectTrace: (traceId: string) => void;
}) {
  const excludedTotal = Object.values(excluded).reduce((s, e) => s + e.count, 0);
  const keepRate = considered > 0 ? (kept / considered) * 100 : 0;

  return (
    <section>
      <div className="section-label">{title}</div>
      <Card className="mt-2">
        <CardContent className="!p-3.5">
          <div className="flex items-end justify-between gap-4">
            <div>
              <div className="text-2xl font-bold tabular-nums">{kept}</div>
              <div className="text-[11px] text-[var(--text-faint)]">{keptLabel}</div>
            </div>
            <div className="text-right">
              <div className="text-[11px] text-[var(--text-faint)]">{considered} considered</div>
              <div className="text-[11px] font-medium text-[var(--error)]">
                {excludedTotal} excluded
              </div>
            </div>
          </div>
          <div className="mt-3">
            <div className="mb-1 flex justify-between text-[10px]">
              <span className="text-[var(--text-dim)]">Keep rate</span>
              <span className="font-semibold tabular-nums text-[var(--success)]">
                {keepRate.toFixed(1)}%
              </span>
            </div>
            <Progress value={keepRate} color="var(--success)" />
          </div>
          {extra}
        </CardContent>
      </Card>
      <div className="mt-3">
        <ReasonTable excluded={excluded} onInspectTrace={onInspectTrace} />
      </div>
    </section>
  );
}

export function ExclusionPanel({ report, loading, onClose, onInspectTrace }: Props) {
  return (
    <div className="flex h-full flex-col">
      <PanelHeader
        title="Exclusion report"
        subtitle="SFT and preference pair export analysis"
        icon={<FileWarning size={14} />}
        onClose={onClose}
      />

      {loading || !report ? (
        <LoadingSpinner label="Loading report…" />
      ) : (
        <div className="flex-1 space-y-6 overflow-auto p-4">
          <ExportSection
            title="SFT export"
            considered={report.sft.total_traces_considered}
            kept={report.sft.kept_count}
            keptLabel={`kept across ${report.sft.total_sessions} sessions`}
            excluded={report.sft.excluded}
            onInspectTrace={onInspectTrace}
          />

          <ExportSection
            title="Preference pair export"
            considered={report.preference.total_traces_considered}
            kept={report.preference.pair_count}
            keptLabel="pairs written"
            extra={
              <div className="mt-3 flex flex-wrap gap-1.5">
                {Object.entries(report.preference.pairs_by_source).map(([source, count]) => (
                  <span key={source} className="chip">
                    {source}: <strong>{count}</strong>
                  </span>
                ))}
              </div>
            }
            excluded={report.preference.excluded}
            onInspectTrace={onInspectTrace}
          />
        </div>
      )}
    </div>
  );
}

import type { ExclusionReport } from "../types/exclusion";

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
    return <div className="text-[11px] text-[var(--text-faint)]">No exclusions.</div>;
  }
  return (
    <div className="flex flex-col gap-2">
      {entries.map(([reason, data]) => (
        <div key={reason} className="border border-[var(--border)] px-3 py-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] text-[var(--text)]">{reason}</span>
            <span className="tabular-nums text-[11px] text-[var(--accent)]">{data.count}</span>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {data.sample_trace_ids.map((id) => (
              <button
                key={id}
                onClick={() => onInspectTrace(id)}
                className="rounded-sm border border-[var(--border)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--text-faint)] hover:border-[var(--border-strong)] hover:text-[var(--text)]"
              >
                {id.slice(0, 8)}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ExclusionPanel({ report, loading, onClose, onInspectTrace }: Props) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div className="text-[12px] font-semibold">Exclusion report</div>
        <button onClick={onClose} className="text-[var(--text-faint)] hover:text-[var(--text)]">
          ✕
        </button>
      </div>

      {loading || !report ? (
        <div className="flex flex-1 items-center justify-center text-[12px] text-[var(--text-faint)]">
          Loading…
        </div>
      ) : (
        <div className="flex-1 overflow-auto px-4 py-3">
          <section>
            <div className="text-[11px] uppercase tracking-wider text-[var(--text-faint)]">
              SFT export
            </div>
            <div className="mt-1.5 text-[11px] text-[var(--text-dim)]">
              {report.sft.total_traces_considered} traces considered across{" "}
              {report.sft.total_sessions} sessions &middot; {report.sft.kept_count} kept
            </div>
            <div className="mt-2">
              <ReasonTable excluded={report.sft.excluded} onInspectTrace={onInspectTrace} />
            </div>
          </section>

          <section className="mt-6">
            <div className="text-[11px] uppercase tracking-wider text-[var(--text-faint)]">
              Preference pair export
            </div>
            <div className="mt-1.5 text-[11px] text-[var(--text-dim)]">
              {report.preference.total_traces_considered} traces considered &middot;{" "}
              {report.preference.pair_count} pairs written
            </div>
            <div className="mt-1 flex gap-3 text-[11px] text-[var(--text-faint)]">
              {Object.entries(report.preference.pairs_by_source).map(([source, count]) => (
                <span key={source}>
                  {source}: <span className="text-[var(--text-dim)]">{count}</span>
                </span>
              ))}
            </div>
            <div className="mt-2">
              <ReasonTable excluded={report.preference.excluded} onInspectTrace={onInspectTrace} />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

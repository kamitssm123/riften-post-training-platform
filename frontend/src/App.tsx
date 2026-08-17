import { useEffect, useState } from "react";
import { fetchSession, fetchStats, fetchTrace, fetchTraces } from "./api/client";
import { FilterRail } from "./components/FilterRail";
import { SessionThread } from "./components/SessionThread";
import { TraceDetail } from "./components/TraceDetail";
import { TraceTable } from "./components/TraceTable";
import {
  EMPTY_FILTERS,
  type SessionResponse,
  type Stats,
  type TraceDetail as TraceDetailT,
  type TraceFilters,
  type TraceSummary,
} from "./types/trace";

const PAGE_SIZE = 30;

type Panel = { kind: "none" } | { kind: "trace"; id: string } | { kind: "session"; id: string };

export default function App() {
  const [filters, setFilters] = useState<TraceFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<Stats | null>(null);
  const [tableLoading, setTableLoading] = useState(false);

  const [panel, setPanel] = useState<Panel>({ kind: "none" });
  const [traceDetail, setTraceDetail] = useState<TraceDetailT | null>(null);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [panelLoading, setPanelLoading] = useState(false);

  useEffect(() => {
    setPage(1);
  }, [filters]);

  useEffect(() => {
    let cancelled = false;
    setTableLoading(true);
    fetchTraces(filters, page, PAGE_SIZE).then((res) => {
      if (cancelled) return;
      setTraces(res.items);
      setTotal(res.total);
      setTableLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [filters, page]);

  useEffect(() => {
    let cancelled = false;
    fetchStats(filters).then((res) => {
      if (!cancelled) setStats(res);
    });
    return () => {
      cancelled = true;
    };
  }, [filters]);

  useEffect(() => {
    if (panel.kind === "trace") {
      let cancelled = false;
      setPanelLoading(true);
      setSession(null);
      fetchTrace(panel.id).then((res) => {
        if (!cancelled) {
          setTraceDetail(res);
          setPanelLoading(false);
        }
      });
      return () => {
        cancelled = true;
      };
    }
    if (panel.kind === "session") {
      let cancelled = false;
      setPanelLoading(true);
      setTraceDetail(null);
      fetchSession(panel.id).then((res) => {
        if (!cancelled) {
          setSession(res);
          setPanelLoading(false);
        }
      });
      return () => {
        cancelled = true;
      };
    }
    setTraceDetail(null);
    setSession(null);
  }, [panel]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div className="flex items-baseline gap-3">
          <span className="text-[14px] font-semibold tracking-tight">riften</span>
          <span className="text-[12px] text-[var(--text-faint)]">trace inspector</span>
        </div>
        <div className="text-[11px] text-[var(--text-faint)]">synthetic corpus &middot; no production traffic</div>
      </header>

      <div className="flex min-h-0 flex-1">
        <FilterRail
          filters={filters}
          onChange={setFilters}
          stats={stats}
          resultCount={total}
        />

        <main className="flex min-h-0 flex-1 flex-col">
          <div className={tableLoading ? "flex-1 overflow-auto opacity-50" : "flex-1 overflow-auto"}>
            <TraceTable
              traces={traces}
              onSelect={(id) => setPanel({ kind: "trace", id })}
              selectedId={panel.kind === "trace" ? panel.id : null}
            />
          </div>
          <div className="flex items-center justify-between border-t border-[var(--border)] px-4 py-2 text-[11px] text-[var(--text-faint)]">
            <span>
              Page {page} of {totalPages} &middot; {total} traces
            </span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-sm border border-[var(--border)] px-2 py-1 disabled:opacity-30"
              >
                prev
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="rounded-sm border border-[var(--border)] px-2 py-1 disabled:opacity-30"
              >
                next
              </button>
            </div>
          </div>
        </main>

        {panel.kind !== "none" && (
          <div className="w-[520px] shrink-0 border-l border-[var(--border)]">
            {panel.kind === "trace" ? (
              <TraceDetail
                trace={traceDetail}
                loading={panelLoading}
                onOpenSession={(sessionId) => setPanel({ kind: "session", id: sessionId })}
                onClose={() => setPanel({ kind: "none" })}
              />
            ) : (
              <SessionThread
                session={session}
                loading={panelLoading}
                onSelectTrace={(id) => setPanel({ kind: "trace", id })}
                onClose={() => setPanel({ kind: "none" })}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

import { FileWarning, Layers, LineChart, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  fetchExclusionReport,
  fetchExportPreview,
  fetchModelTradeoff,
  fetchSession,
  fetchStats,
  fetchTrace,
  fetchTraces,
} from "./api/client";
import { ExclusionPanel } from "./components/ExclusionPanel";
import { FilterRail } from "./components/FilterRail";
import { ModelTradeoffView } from "./components/ModelTradeoffView";
import { Pagination } from "./components/Pagination";
import { SessionThread } from "./components/SessionThread";
import { StatsOverview } from "./components/StatsOverview";
import { ThemeSwitcher } from "./components/ThemeSwitcher";
import { TraceDetail } from "./components/TraceDetail";
import { TraceTable } from "./components/TraceTable";
import { useRouter } from "./hooks/useRouter";
import { useTheme } from "./hooks/useTheme";
import { pathForRoute, parsePath } from "./routes";
import type { ExclusionReport } from "./types/exclusion";
import type { ExportPreview } from "./types/exportPreview";
import type { ModelTradeoff } from "./types/modelTradeoff";
import {
  EMPTY_FILTERS,
  type SessionResponse,
  type Stats,
  type TraceDetail as TraceDetailT,
  type TraceFilters,
  type TraceSummary,
} from "./types/trace";

const PAGE_SIZE = 30;

type MainView = "traces" | "tradeoff";

type Panel =
  | { kind: "none" }
  | { kind: "trace"; id: string }
  | { kind: "session"; id: string }
  | { kind: "exclusions" };

export default function App() {
  const { theme, setTheme } = useTheme();
  const { pathname, navigate } = useRouter();
  const route = useMemo(() => parsePath(pathname), [pathname]);

  const mainView: MainView = route.name === "tradeoff" ? "tradeoff" : "traces";
  const panel: Panel = useMemo<Panel>(() => {
    if (route.name === "trace") return { kind: "trace", id: route.id };
    if (route.name === "session") return { kind: "session", id: route.id };
    if (route.name === "exclusions") return { kind: "exclusions" };
    return { kind: "none" };
  }, [route]);

  const goTraces = () => navigate(pathForRoute({ name: "traces" }));
  const goTradeoff = () => navigate(pathForRoute({ name: "tradeoff" }));
  const goExclusions = () => navigate(pathForRoute({ name: "exclusions" }));
  const openTrace = (id: string) => navigate(pathForRoute({ name: "trace", id }));
  const openSession = (id: string) => navigate(pathForRoute({ name: "session", id }));
  const closePanel = () => navigate(pathForRoute({ name: "traces" }));

  const [filters, setFilters] = useState<TraceFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<Stats | null>(null);
  const [tableLoading, setTableLoading] = useState(false);
  const [tradeoff, setTradeoff] = useState<ModelTradeoff[] | null>(null);
  const [tradeoffLoading, setTradeoffLoading] = useState(false);

  const [traceDetail, setTraceDetail] = useState<TraceDetailT | null>(null);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [exclusionReport, setExclusionReport] = useState<ExclusionReport | null>(null);
  const [panelLoading, setPanelLoading] = useState(false);
  const [exportPreview, setExportPreview] = useState<ExportPreview | null>(null);
  const [exportPreviewLoading, setExportPreviewLoading] = useState(false);

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
    if (mainView !== "tradeoff") return;
    let cancelled = false;
    setTradeoffLoading(true);
    fetchModelTradeoff().then((res) => {
      if (cancelled) return;
      setTradeoff(res.items);
      setTradeoffLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [mainView]);

  useEffect(() => {
    if (panel.kind === "trace") {
      let cancelled = false;
      setPanelLoading(true);
      setExportPreviewLoading(true);
      setSession(null);
      fetchTrace(panel.id).then((res) => {
        if (!cancelled) {
          setTraceDetail(res);
          setPanelLoading(false);
        }
      });
      fetchExportPreview(panel.id)
        .then((res) => {
          if (!cancelled) {
            setExportPreview(res);
            setExportPreviewLoading(false);
          }
        })
        .catch(() => {
          if (!cancelled) setExportPreviewLoading(false);
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
    if (panel.kind === "exclusions") {
      let cancelled = false;
      setPanelLoading(true);
      setTraceDetail(null);
      setSession(null);
      fetchExclusionReport().then((res) => {
        if (!cancelled) {
          setExclusionReport(res);
          setPanelLoading(false);
        }
      });
      return () => {
        cancelled = true;
      };
    }
    setTraceDetail(null);
    setSession(null);
    setExportPreview(null);
  }, [panel]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex h-screen flex-col">
      <header
        className="glass flex shrink-0 items-center justify-between border-b px-5 py-2.5"
        style={{
          borderColor: "var(--border)",
          background: "var(--header-bg)",
        }}
      >
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2">
              <img src="/logo-mark.png" alt="" className="brand-mark h-4 w-4 shrink-0" />
              <span
                className="text-[13px] font-medium uppercase text-[var(--text)]"
                style={{ fontFamily: "var(--mono)", letterSpacing: "0.08em" }}
              >
                riften
              </span>
              <span className="chip">
                <Sparkles size={9} />
                Trace Inspector
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={goTraces}
            className={`btn flex items-center gap-1.5 !text-[11px] ${
              mainView === "traces" ? "btn-active" : ""
            }`}
          >
            <Layers size={13} />
            Traces
          </button>
          <button
            onClick={goTradeoff}
            className={`btn flex items-center gap-1.5 !text-[11px] ${
              mainView === "tradeoff" ? "btn-active" : ""
            }`}
          >
            <LineChart size={13} />
            Model tradeoff
          </button>
          <button
            onClick={goExclusions}
            className={`btn flex items-center gap-1.5 !text-[11px] ${
              panel.kind === "exclusions" ? "btn-active" : ""
            }`}
          >
            <FileWarning size={13} />
            Exclusion report
          </button>
          <div className="hidden h-5 w-px sm:block" style={{ background: "var(--border)" }} />
          <span className="chip hidden sm:inline-flex">
            synthetic corpus · no production traffic
          </span>
          <ThemeSwitcher theme={theme} onChange={setTheme} />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {mainView === "traces" && (
          <FilterRail
            filters={filters}
            onChange={setFilters}
            stats={stats}
            resultCount={total}
          />
        )}

        {mainView === "traces" ? (
          <main className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-4">
            <StatsOverview stats={stats} resultCount={total} />

            <div
              className="relative min-h-0 flex-1 overflow-hidden rounded-xl border"
              style={{ borderColor: "var(--border)", background: "var(--bg-raised)" }}
            >
              {tableLoading && (
                <div className="pointer-events-none absolute inset-x-0 top-0 z-20 h-0.5 overflow-hidden rounded-t-xl">
                  <div
                    className="h-full w-1/3 animate-[shimmer_1s_ease-in-out_infinite]"
                    style={{
                      background: "linear-gradient(90deg, transparent, var(--brand), transparent)",
                    }}
                  />
                </div>
              )}
              <div className={`h-full overflow-auto ${tableLoading ? "opacity-70 transition-opacity" : ""}`}>
                <TraceTable
                  traces={traces}
                  loading={tableLoading}
                  onSelect={openTrace}
                  selectedId={panel.kind === "trace" ? panel.id : null}
                />
              </div>
            </div>

            <div
              className="flex shrink-0 items-center justify-between rounded-xl border px-4 py-2.5 text-[11px]"
              style={{
                borderColor: "var(--border)",
                background: "var(--bg-raised)",
              }}
            >
              <span className="text-[var(--text-faint)]">
                Page <span className="font-semibold text-[var(--text)]">{page}</span> of{" "}
                <span className="font-semibold text-[var(--text)]">{totalPages}</span>
                <span className="mx-2 text-[var(--border-strong)]">·</span>
                <span className="font-semibold text-[var(--text)]">{total}</span> traces
              </span>
              <Pagination page={page} totalPages={totalPages} onChange={setPage} />
            </div>
          </main>
        ) : (
          <main className="min-h-0 flex-1 overflow-auto p-4">
            <ModelTradeoffView items={tradeoff} loading={tradeoffLoading} />
          </main>
        )}

        {panel.kind !== "none" && (
          <div
            className="panel-surface w-[540px] shrink-0 border-l shadow-xl animate-fade-in"
            style={{ borderColor: "var(--border)" }}
          >
            {panel.kind === "trace" && (
              <TraceDetail
                trace={traceDetail}
                loading={panelLoading}
                exportPreview={exportPreview}
                exportPreviewLoading={exportPreviewLoading}
                onOpenSession={openSession}
                onSelectTrace={openTrace}
                onClose={closePanel}
              />
            )}
            {panel.kind === "session" && (
              <SessionThread
                session={session}
                loading={panelLoading}
                onSelectTrace={openTrace}
                onClose={closePanel}
              />
            )}
            {panel.kind === "exclusions" && (
              <ExclusionPanel
                report={exclusionReport}
                loading={panelLoading}
                onClose={closePanel}
                onInspectTrace={openTrace}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

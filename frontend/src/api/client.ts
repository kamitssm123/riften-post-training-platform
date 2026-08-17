import type { ExclusionReport } from "../types/exclusion";
import type {
  SessionResponse,
  Stats,
  TraceDetail,
  TraceFilters,
  TracesResponse,
} from "../types/trace";

const BASE = "/api";

function filtersToParams(filters: Partial<TraceFilters>, extra?: Record<string, string | number>) {
  const params = new URLSearchParams();
  filters.model?.forEach((m) => params.append("model", m));
  filters.feedback?.forEach((f) => params.append("feedback", f));
  if (filters.min_cost != null) params.set("min_cost", String(filters.min_cost));
  if (filters.max_cost != null) params.set("max_cost", String(filters.max_cost));
  if (filters.min_latency != null) params.set("min_latency", String(filters.min_latency));
  if (filters.max_latency != null) params.set("max_latency", String(filters.max_latency));
  if (filters.truncated != null) params.set("truncated", String(filters.truncated));
  if (filters.errored != null) params.set("errored", String(filters.errored));
  if (filters.session_id) params.set("session_id", filters.session_id);
  if (extra) {
    for (const [k, v] of Object.entries(extra)) params.set(k, String(v));
  }
  return params;
}

export async function fetchTraces(
  filters: Partial<TraceFilters>,
  page: number,
  pageSize: number
): Promise<TracesResponse> {
  const params = filtersToParams(filters, { page, page_size: pageSize });
  const res = await fetch(`${BASE}/traces?${params.toString()}`);
  if (!res.ok) throw new Error(`GET /traces failed: ${res.status}`);
  return res.json();
}

export async function fetchTrace(traceId: string): Promise<TraceDetail> {
  const res = await fetch(`${BASE}/traces/${traceId}`);
  if (!res.ok) throw new Error(`GET /traces/${traceId} failed: ${res.status}`);
  return res.json();
}

export async function fetchSession(sessionId: string): Promise<SessionResponse> {
  const res = await fetch(`${BASE}/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`GET /sessions/${sessionId} failed: ${res.status}`);
  return res.json();
}

export async function fetchStats(filters: Partial<TraceFilters>): Promise<Stats> {
  const params = filtersToParams(filters);
  const res = await fetch(`${BASE}/stats?${params.toString()}`);
  if (!res.ok) throw new Error(`GET /stats failed: ${res.status}`);
  return res.json();
}

export async function fetchExclusionReport(): Promise<ExclusionReport> {
  const res = await fetch(`${BASE}/export/exclusions`);
  if (!res.ok) throw new Error(`GET /export/exclusions failed: ${res.status}`);
  return res.json();
}

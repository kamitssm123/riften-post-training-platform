export interface ExclusionReasonSummary {
  count: number;
  sample_trace_ids: string[];
}

export interface ExclusionReport {
  sft: {
    total_traces_considered: number;
    total_sessions: number;
    kept_count: number;
    excluded: Record<string, ExclusionReasonSummary>;
  };
  preference: {
    total_traces_considered: number;
    pair_count: number;
    pairs_by_source: Record<string, number>;
    excluded: Record<string, ExclusionReasonSummary>;
  };
}

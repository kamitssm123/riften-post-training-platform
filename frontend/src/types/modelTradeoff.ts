export interface ModelTradeoff {
  model: string;
  trace_count: number;
  avg_cost_usd: number | null;
  avg_latency_ms: number | null;
  avg_tokens_prompt: number | null;
  avg_tokens_completion: number | null;
  avg_quality_score: number | null;
  feedback_coverage: number;
  error_rate: number;
  truncation_rate: number;
}

export interface ModelTradeoffResponse {
  items: ModelTradeoff[];
}

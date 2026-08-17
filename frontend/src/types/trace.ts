export type Model =
  | "gpt-4o"
  | "gpt-4o-mini"
  | "claude-3-5-sonnet"
  | "llama-3.1-70b"
  | "gemini-1.5-flash";

export type FinishReason = "stop" | "length" | "tool_calls" | "content_filter";
export type Feedback = "weak" | "ok" | "strong";
export type ContinuationStatus = "accepted" | "rejected";

export interface Message {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
}

export interface ToolCallResult {
  status_code: number;
  output: unknown;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result: ToolCallResult;
}

/** Summary row as returned by GET /traces (no messages/tool_calls body). */
export interface TraceSummary {
  trace_id: string;
  session_id: string;
  turn_index: number;
  timestamp: string;
  model: Model;
  finish_reason: FinishReason;
  status_code: number;
  tokens_prompt: number;
  tokens_completion: number;
  cost_usd: number;
  latency_ms: number;
  feedback: Feedback | null;
  is_retrial: boolean;
  retrial_of: string | null;
  continuation_status: ContinuationStatus | null;
  has_tool_error: boolean;
}

/** Full trace as returned by GET /traces/{id} and GET /sessions/{id}. */
export interface TraceDetail extends Omit<TraceSummary, "has_tool_error"> {
  messages: Message[];
  response: Message;
  tool_calls: ToolCall[] | null;
}

export interface TracesResponse {
  items: TraceSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface SessionResponse {
  session_id: string;
  traces: TraceDetail[];
}

export interface Stats {
  total: number;
  per_model: Record<string, number>;
  per_feedback: Record<string, number>;
  error_count: number;
  error_rate: number;
  truncated_count: number;
  truncated_rate: number;
}

export interface TraceFilters {
  model: string[];
  min_cost: number | null;
  max_cost: number | null;
  min_latency: number | null;
  max_latency: number | null;
  feedback: string[];
  truncated: boolean | null;
  errored: boolean | null;
  session_id: string | null;
}

export const EMPTY_FILTERS: TraceFilters = {
  model: [],
  min_cost: null,
  max_cost: null,
  min_latency: null,
  max_latency: null,
  feedback: [],
  truncated: null,
  errored: null,
  session_id: null,
};

export const ALL_MODELS: Model[] = [
  "gpt-4o",
  "gpt-4o-mini",
  "claude-3-5-sonnet",
  "llama-3.1-70b",
  "gemini-1.5-flash",
];

export const ALL_FEEDBACK: Feedback[] = ["weak", "ok", "strong"];

"""
Single source of truth for the trace schema. Every later phase (generator,
ingest, API, exports) imports from here rather than redefining fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal, Optional
import json

Model = Literal[
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-5-sonnet",
    "llama-3.1-70b",
    "gemini-1.5-flash",
]

FinishReason = Literal["stop", "length", "tool_calls", "content_filter"]
Feedback = Literal["weak", "ok", "strong"]
ContinuationStatus = Literal["accepted", "rejected"]

# Rough $/1K token pricing used by the generator to compute cost_usd.
# Not real Riften/provider pricing -- illustrative only, for a synthetic corpus.
MODEL_PRICING_PER_1K = {
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "claude-3-5-sonnet": {"prompt": 0.003, "completion": 0.015},
    "llama-3.1-70b": {"prompt": 0.0009, "completion": 0.0009},
    "gemini-1.5-flash": {"prompt": 0.000075, "completion": 0.0003},
}

# Relative latency profile (ms, mean) used by the generator.
MODEL_LATENCY_MS = {
    "gpt-4o": 2200,
    "gpt-4o-mini": 700,
    "claude-3-5-sonnet": 1900,
    "llama-3.1-70b": 1100,
    "gemini-1.5-flash": 500,
}


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]  # {"status_code": int, "output": ...}


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str


@dataclass
class Trace:
    trace_id: str
    session_id: str
    turn_index: int
    timestamp: str  # ISO 8601
    model: Model
    messages: list[dict[str, Any]]  # serialized Message dicts
    response: dict[str, Any]  # serialized Message dict (assistant reply)
    tool_calls: Optional[list[dict[str, Any]]]
    finish_reason: FinishReason
    status_code: int
    tokens_prompt: int
    tokens_completion: int
    cost_usd: float
    latency_ms: int
    feedback: Optional[Feedback]
    is_retrial: bool
    retrial_of: Optional[str]
    continuation_status: Optional[ContinuationStatus]

    def to_row(self) -> dict[str, Any]:
        """Flatten for SQLite storage: JSON-encode nested structures."""
        d = asdict(self)
        d["messages"] = json.dumps(d["messages"])
        d["response"] = json.dumps(d["response"])
        d["tool_calls"] = json.dumps(d["tool_calls"]) if d["tool_calls"] is not None else None
        d["is_retrial"] = int(d["is_retrial"])
        return d

    @staticmethod
    def from_row(row: dict[str, Any]) -> dict[str, Any]:
        """Inflate a SQLite row back into a JSON-ready trace dict."""
        d = dict(row)
        d["messages"] = json.loads(d["messages"])
        d["response"] = json.loads(d["response"])
        d["tool_calls"] = json.loads(d["tool_calls"]) if d["tool_calls"] is not None else None
        d["is_retrial"] = bool(d["is_retrial"])
        return d


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    model TEXT NOT NULL,
    messages TEXT NOT NULL,
    response TEXT NOT NULL,
    tool_calls TEXT,
    finish_reason TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    tokens_prompt INTEGER NOT NULL,
    tokens_completion INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    latency_ms INTEGER NOT NULL,
    feedback TEXT,
    is_retrial INTEGER NOT NULL DEFAULT 0,
    retrial_of TEXT,
    continuation_status TEXT
);
CREATE INDEX IF NOT EXISTS idx_traces_session ON traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_model ON traces(model);
CREATE INDEX IF NOT EXISTS idx_traces_feedback ON traces(feedback);
CREATE INDEX IF NOT EXISTS idx_traces_retrial_of ON traces(retrial_of);
"""

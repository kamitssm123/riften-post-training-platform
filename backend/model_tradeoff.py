"""
Cost/quality tradeoff aggregation, per model. Backs GET /stats/model-tradeoff.
Read-only: computes aggregates over the existing `traces` table, no new
tables or columns. `feedback` maps to a numeric quality score
(weak=0, ok=0.5, strong=1) averaged only over traces that carry non-null
feedback -- `feedback_coverage` reports what fraction of a model's traces
that average is based on, so a low-coverage score isn't mistaken for a
score backed by the full trace population.
"""
from __future__ import annotations

import sqlite3
from typing import Any

QUALITY_SCORE_SQL = """
CASE feedback
    WHEN 'weak' THEN 0.0
    WHEN 'ok' THEN 0.5
    WHEN 'strong' THEN 1.0
    ELSE NULL
END
"""

MODEL_TRADEOFF_SQL = f"""
SELECT
    model,
    COUNT(*) AS trace_count,
    AVG(cost_usd) AS avg_cost_usd,
    AVG(latency_ms) AS avg_latency_ms,
    AVG(tokens_prompt) AS avg_tokens_prompt,
    AVG(tokens_completion) AS avg_tokens_completion,
    SUM(CASE WHEN feedback IS NOT NULL THEN 1 ELSE 0 END) AS feedback_count,
    AVG({QUALITY_SCORE_SQL}) AS avg_quality_score,
    AVG(CASE WHEN status_code < 200 OR status_code >= 300 THEN 1.0 ELSE 0.0 END) AS error_rate,
    AVG(CASE WHEN finish_reason = 'length' THEN 1.0 ELSE 0.0 END) AS truncation_rate
FROM traces
GROUP BY model
ORDER BY model
"""


def compute_model_tradeoff(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(MODEL_TRADEOFF_SQL).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        trace_count = d["trace_count"]
        feedback_count = d.pop("feedback_count")
        d["feedback_coverage"] = round(feedback_count / trace_count, 4) if trace_count else 0.0
        d["avg_quality_score"] = (
            round(d["avg_quality_score"], 4) if d["avg_quality_score"] is not None else None
        )
        d["avg_cost_usd"] = round(d["avg_cost_usd"], 6) if d["avg_cost_usd"] is not None else None
        d["avg_latency_ms"] = round(d["avg_latency_ms"], 2) if d["avg_latency_ms"] is not None else None
        d["avg_tokens_prompt"] = (
            round(d["avg_tokens_prompt"], 2) if d["avg_tokens_prompt"] is not None else None
        )
        d["avg_tokens_completion"] = (
            round(d["avg_tokens_completion"], 2) if d["avg_tokens_completion"] is not None else None
        )
        d["error_rate"] = round(d["error_rate"], 4)
        d["truncation_rate"] = round(d["truncation_rate"], 4)
        result.append(d)
    return result

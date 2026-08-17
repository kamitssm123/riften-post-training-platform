"""
FastAPI app exposing the trace inspector API.

GET /traces               paginated, filterable list
GET /traces/{trace_id}    full detail
GET /sessions/{session_id} all traces in a session, ordered by turn_index
GET /stats                aggregate counts for the filter sidebar
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from export_sft import build_sft_export
from schema import Trace

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "traces.db"

app = FastAPI(title="Riften Trace Inspector API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def build_filter_clause(
    model: Optional[list[str]] = None,
    min_cost: Optional[float] = None,
    max_cost: Optional[float] = None,
    min_latency: Optional[int] = None,
    max_latency: Optional[int] = None,
    feedback: Optional[list[str]] = None,
    truncated: Optional[bool] = None,
    errored: Optional[bool] = None,
    session_id: Optional[str] = None,
) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []

    if model:
        placeholders = ", ".join("?" for _ in model)
        clauses.append(f"model IN ({placeholders})")
        params.extend(model)

    if min_cost is not None:
        clauses.append("cost_usd >= ?")
        params.append(min_cost)
    if max_cost is not None:
        clauses.append("cost_usd <= ?")
        params.append(max_cost)

    if min_latency is not None:
        clauses.append("latency_ms >= ?")
        params.append(min_latency)
    if max_latency is not None:
        clauses.append("latency_ms <= ?")
        params.append(max_latency)

    if feedback:
        placeholders = ", ".join("?" for _ in feedback)
        clauses.append(f"feedback IN ({placeholders})")
        params.extend(feedback)

    if truncated is True:
        clauses.append("finish_reason = 'length'")
    elif truncated is False:
        clauses.append("finish_reason != 'length'")

    if errored is True:
        clauses.append(
            "(status_code >= 400 OR "
            "(tool_calls IS NOT NULL AND "
            "EXISTS (SELECT 1 FROM json_each(tool_calls) je "
            "WHERE json_extract(je.value, '$.result.status_code') >= 400)))"
        )
    elif errored is False:
        clauses.append(
            "(status_code < 400 AND "
            "(tool_calls IS NULL OR NOT EXISTS "
            "(SELECT 1 FROM json_each(tool_calls) je "
            "WHERE json_extract(je.value, '$.result.status_code') >= 400)))"
        )

    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


@app.get("/traces")
def list_traces(
    model: Optional[list[str]] = Query(default=None),
    min_cost: Optional[float] = None,
    max_cost: Optional[float] = None,
    min_latency: Optional[int] = None,
    max_latency: Optional[int] = None,
    feedback: Optional[list[str]] = Query(default=None),
    truncated: Optional[bool] = None,
    errored: Optional[bool] = None,
    session_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
):
    where, params = build_filter_clause(
        model=model,
        min_cost=min_cost,
        max_cost=max_cost,
        min_latency=min_latency,
        max_latency=max_latency,
        feedback=feedback,
        truncated=truncated,
        errored=errored,
        session_id=session_id,
    )

    conn = get_connection()
    try:
        total = conn.execute(f"SELECT COUNT(*) c FROM traces {where}", params).fetchone()["c"]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT trace_id, session_id, turn_index, timestamp, model,
                   finish_reason, status_code, tokens_prompt, tokens_completion,
                   cost_usd, latency_ms, feedback, is_retrial, retrial_of,
                   continuation_status,
                   tool_calls
            FROM traces
            {where}
            ORDER BY timestamp ASC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

        items = []
        for row in rows:
            d = dict(row)
            d["is_retrial"] = bool(d["is_retrial"])
            has_tool_error = False
            if d["tool_calls"]:
                import json as _json

                tool_calls = _json.loads(d["tool_calls"])
                has_tool_error = any(tc["result"]["status_code"] >= 400 for tc in tool_calls)
            d["has_tool_error"] = has_tool_error
            del d["tool_calls"]
            items.append(d)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        conn.close()


@app.get("/traces/{trace_id}")
def get_trace(trace_id: str):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM traces WHERE trace_id = ?", [trace_id]).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="trace not found")
        return Trace.from_row(dict(row))
    finally:
        conn.close()


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM traces WHERE session_id = ? ORDER BY turn_index ASC, timestamp ASC",
            [session_id],
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="session not found")
        return {
            "session_id": session_id,
            "traces": [Trace.from_row(dict(r)) for r in rows],
        }
    finally:
        conn.close()


@app.get("/stats")
def get_stats(
    model: Optional[list[str]] = Query(default=None),
    min_cost: Optional[float] = None,
    max_cost: Optional[float] = None,
    min_latency: Optional[int] = None,
    max_latency: Optional[int] = None,
    feedback: Optional[list[str]] = Query(default=None),
    truncated: Optional[bool] = None,
    errored: Optional[bool] = None,
    session_id: Optional[str] = None,
):
    """Aggregate counts for the filter sidebar, scoped by the same filters
    as /traces so the UI can show live result counts as filters compose."""
    where, params = build_filter_clause(
        model=model,
        min_cost=min_cost,
        max_cost=max_cost,
        min_latency=min_latency,
        max_latency=max_latency,
        feedback=feedback,
        truncated=truncated,
        errored=errored,
        session_id=session_id,
    )

    conn = get_connection()
    try:
        total = conn.execute(f"SELECT COUNT(*) c FROM traces {where}", params).fetchone()["c"]

        per_model = conn.execute(
            f"SELECT model, COUNT(*) c FROM traces {where} GROUP BY model", params
        ).fetchall()

        per_feedback = conn.execute(
            f"SELECT feedback, COUNT(*) c FROM traces {where} GROUP BY feedback", params
        ).fetchall()

        errored_where, errored_params = build_filter_clause(
            model=model,
            min_cost=min_cost,
            max_cost=max_cost,
            min_latency=min_latency,
            max_latency=max_latency,
            feedback=feedback,
            truncated=truncated,
            errored=True,
            session_id=session_id,
        )
        error_count = conn.execute(
            f"SELECT COUNT(*) c FROM traces {errored_where}", errored_params
        ).fetchone()["c"]

        truncated_where, truncated_params = build_filter_clause(
            model=model,
            min_cost=min_cost,
            max_cost=max_cost,
            min_latency=min_latency,
            max_latency=max_latency,
            feedback=feedback,
            truncated=True,
            errored=errored,
            session_id=session_id,
        )
        truncated_count = conn.execute(
            f"SELECT COUNT(*) c FROM traces {truncated_where}", truncated_params
        ).fetchone()["c"]

        return {
            "total": total,
            "per_model": {r["model"]: r["c"] for r in per_model},
            "per_feedback": {(r["feedback"] or "none"): r["c"] for r in per_feedback},
            "error_count": error_count,
            "error_rate": round(error_count / total, 4) if total else 0.0,
            "truncated_count": truncated_count,
            "truncated_rate": round(truncated_count / total, 4) if total else 0.0,
        }
    finally:
        conn.close()


@app.post("/export/sft")
def export_sft():
    return build_sft_export()

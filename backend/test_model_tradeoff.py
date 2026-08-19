"""Tests for the per-model cost/quality tradeoff aggregation."""
from __future__ import annotations

import json

import pytest

import ingest
import model_tradeoff


def trace(**overrides):
    base = {
        "trace_id": "t",
        "session_id": "s",
        "turn_index": 0,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hi"}],
        "response": {"role": "assistant", "content": "hello"},
        "tool_calls": None,
        "finish_reason": "stop",
        "status_code": 200,
        "tokens_prompt": 10,
        "tokens_completion": 5,
        "cost_usd": 0.001,
        "latency_ms": 400,
        "feedback": None,
        "is_retrial": False,
        "retrial_of": None,
        "continuation_status": None,
    }
    base.update(overrides)
    return base


@pytest.fixture()
def load(tmp_path, monkeypatch):
    def _load(traces):
        db_path = tmp_path / "traces.db"
        traces_path = tmp_path / "traces.json"
        traces_path.write_text(json.dumps(traces))
        monkeypatch.setattr(ingest, "DB_PATH", db_path)
        ingest.load_corpus(traces_path)
        conn = ingest.get_connection()
        return conn

    return _load


def test_aggregates_known_fixture(load):
    conn = load(
        [
            trace(
                trace_id="a",
                model="gpt-4o",
                cost_usd=0.01,
                latency_ms=1000,
                tokens_prompt=100,
                tokens_completion=50,
                feedback="strong",
                status_code=200,
                finish_reason="stop",
            ),
            trace(
                trace_id="b",
                model="gpt-4o",
                cost_usd=0.03,
                latency_ms=2000,
                tokens_prompt=200,
                tokens_completion=100,
                feedback="weak",
                status_code=502,
                finish_reason="length",
            ),
            trace(
                trace_id="c",
                model="gpt-4o-mini",
                cost_usd=0.001,
                latency_ms=500,
                tokens_prompt=50,
                tokens_completion=20,
                feedback=None,
                status_code=200,
                finish_reason="stop",
            ),
        ]
    )
    try:
        rows = {r["model"]: r for r in model_tradeoff.compute_model_tradeoff(conn)}
    finally:
        conn.close()

    gpt4o = rows["gpt-4o"]
    assert gpt4o["trace_count"] == 2
    assert gpt4o["avg_cost_usd"] == pytest.approx(0.02)
    assert gpt4o["avg_latency_ms"] == pytest.approx(1500)
    assert gpt4o["avg_tokens_prompt"] == pytest.approx(150)
    assert gpt4o["avg_tokens_completion"] == pytest.approx(75)
    # quality: weak=0, strong=1 -> average 0.5, over both traces (both have feedback)
    assert gpt4o["avg_quality_score"] == pytest.approx(0.5)
    assert gpt4o["feedback_coverage"] == pytest.approx(1.0)
    assert gpt4o["error_rate"] == pytest.approx(0.5)
    assert gpt4o["truncation_rate"] == pytest.approx(0.5)

    mini = rows["gpt-4o-mini"]
    assert mini["trace_count"] == 1
    assert mini["avg_cost_usd"] == pytest.approx(0.001)
    assert mini["avg_quality_score"] is None
    assert mini["feedback_coverage"] == pytest.approx(0.0)
    assert mini["error_rate"] == pytest.approx(0.0)
    assert mini["truncation_rate"] == pytest.approx(0.0)

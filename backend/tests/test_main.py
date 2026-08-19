"""Basic pytest coverage for the /traces filter combinations."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import main
from core.schema import CREATE_TABLE_SQL
from db import ingest

FIXTURE_TRACES = [
    {
        "trace_id": "t1",
        "session_id": "s1",
        "turn_index": 0,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hi"}],
        "response": {"role": "assistant", "content": "hello"},
        "tool_calls": None,
        "finish_reason": "stop",
        "status_code": 200,
        "tokens_prompt": 5,
        "tokens_completion": 3,
        "cost_usd": 0.001,
        "latency_ms": 400,
        "feedback": "strong",
        "is_retrial": False,
        "retrial_of": None,
        "continuation_status": None,
    },
    {
        "trace_id": "t2",
        "session_id": "s1",
        "turn_index": 1,
        "timestamp": "2026-01-01T00:01:00+00:00",
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        "response": {"role": "assistant", "content": "cut off mid-sent"},
        "tool_calls": None,
        "finish_reason": "length",
        "status_code": 200,
        "tokens_prompt": 8,
        "tokens_completion": 3,
        "cost_usd": 0.01,
        "latency_ms": 2000,
        "feedback": "weak",
        "is_retrial": False,
        "retrial_of": None,
        "continuation_status": None,
    },
    {
        "trace_id": "t3",
        "session_id": "s2",
        "turn_index": 0,
        "timestamp": "2026-01-01T00:02:00+00:00",
        "model": "llama-3.1-70b",
        "messages": [{"role": "user", "content": "do a thing"}],
        "response": {"role": "assistant", "content": "tried"},
        "tool_calls": [{"name": "do_thing", "args": {}, "result": {"status_code": 500, "output": "err"}}],
        "finish_reason": "tool_calls",
        "status_code": 502,
        "tokens_prompt": 6,
        "tokens_completion": 2,
        "cost_usd": 0.002,
        "latency_ms": 900,
        "feedback": None,
        "is_retrial": False,
        "retrial_of": None,
        "continuation_status": None,
    },
]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "traces.db"
    traces_path = tmp_path / "traces.json"
    traces_path.write_text(json.dumps(FIXTURE_TRACES))

    monkeypatch.setattr(ingest, "DB_PATH", db_path)
    monkeypatch.setattr(main, "DB_PATH", db_path)

    ingest.load_corpus(traces_path)

    return TestClient(main.app)


def test_list_traces_no_filter(client):
    resp = client.get("/traces")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_filter_by_model(client):
    resp = client.get("/traces", params={"model": "gpt-4o-mini"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["trace_id"] == "t1"


def test_filter_by_multiple_models(client):
    resp = client.get("/traces", params=[("model", "gpt-4o-mini"), ("model", "gpt-4o")])
    body = resp.json()
    assert body["total"] == 2


def test_filter_by_cost_range(client):
    resp = client.get("/traces", params={"min_cost": 0.005})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["trace_id"] == "t2"


def test_filter_by_latency_range(client):
    resp = client.get("/traces", params={"max_latency": 500})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["trace_id"] == "t1"


def test_filter_by_feedback(client):
    resp = client.get("/traces", params={"feedback": "weak"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["trace_id"] == "t2"


def test_filter_truncated(client):
    resp = client.get("/traces", params={"truncated": True})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["trace_id"] == "t2"


def test_filter_errored(client):
    resp = client.get("/traces", params={"errored": True})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["trace_id"] == "t3"
    assert body["items"][0]["has_tool_error"] is True


def test_filter_session_id(client):
    resp = client.get("/traces", params={"session_id": "s1"})
    body = resp.json()
    assert body["total"] == 2


def test_composed_filters(client):
    resp = client.get("/traces", params={"session_id": "s1", "truncated": True})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["trace_id"] == "t2"


def test_get_trace_detail(client):
    resp = client.get("/traces/t1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["messages"] == [{"role": "user", "content": "hi"}]


def test_get_trace_not_found(client):
    resp = client.get("/traces/does-not-exist")
    assert resp.status_code == 404


def test_get_session(client):
    resp = client.get("/sessions/s1")
    assert resp.status_code == 200
    body = resp.json()
    assert [t["trace_id"] for t in body["traces"]] == ["t1", "t2"]


def test_get_session_not_found(client):
    resp = client.get("/sessions/nope")
    assert resp.status_code == 404


def test_stats(client):
    resp = client.get("/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["per_model"]["gpt-4o-mini"] == 1
    assert body["error_count"] == 1
    assert body["truncated_count"] == 1


def test_stats_scoped_by_filter(client):
    resp = client.get("/stats", params={"session_id": "s1"})
    body = resp.json()
    assert body["total"] == 2
    assert body["error_count"] == 0
    assert body["truncated_count"] == 1

"""Tests for SFT export: session collapsing + row-level exclusion rules."""
from __future__ import annotations

import json

import pytest

import export_sft
import ingest


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
        "tokens_prompt": 5,
        "tokens_completion": 3,
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
    monkeypatch.setattr(export_sft, "EXPORTS_DIR", tmp_path / "exports")
    monkeypatch.setattr(export_sft, "OUT_PATH", tmp_path / "exports" / "sft.jsonl")

    def _load(traces):
        db_path = tmp_path / "traces.db"
        traces_path = tmp_path / "traces.json"
        traces_path.write_text(json.dumps(traces))
        monkeypatch.setattr(ingest, "DB_PATH", db_path)
        ingest.load_corpus(traces_path)

    return _load


def test_collapses_to_highest_turn_index(load):
    load(
        [
            trace(trace_id="a", session_id="s1", turn_index=0),
            trace(trace_id="b", session_id="s1", turn_index=1),
        ]
    )
    result = export_sft.build_sft_export()
    assert result["kept_count"] == 1
    assert result["excluded_by_reason"]["superseded_by_longer_session_trace"] == ["a"]


def test_retrial_tiebreak_at_same_turn_index(load):
    load(
        [
            trace(trace_id="bad", session_id="s1", turn_index=0, feedback="weak"),
            trace(
                trace_id="good",
                session_id="s1",
                turn_index=0,
                is_retrial=True,
                retrial_of="bad",
                feedback="strong",
            ),
        ]
    )
    result = export_sft.build_sft_export()
    assert result["kept_count"] == 1
    with open(result["output_path"]) as f:
        rows = [json.loads(line) for line in f]
    assert rows[0]["metadata"]["feedback"] == "strong"
    assert result["excluded_by_reason"]["superseded_by_longer_session_trace"] == ["bad"]


def test_excludes_non_2xx(load):
    load([trace(trace_id="a", session_id="s1", status_code=502)])
    result = export_sft.build_sft_export()
    assert result["kept_count"] == 0
    assert result["excluded_by_reason"]["non_2xx_response"] == ["a"]


def test_excludes_truncated(load):
    load([trace(trace_id="a", session_id="s1", finish_reason="length")])
    result = export_sft.build_sft_export()
    assert result["kept_count"] == 0
    assert result["excluded_by_reason"]["truncated_response"] == ["a"]


def test_excludes_rejected_continuation(load):
    load([trace(trace_id="a", session_id="s1", continuation_status="rejected")])
    result = export_sft.build_sft_export()
    assert result["kept_count"] == 0
    assert result["excluded_by_reason"]["rejected_continuation"] == ["a"]


def test_metadata_does_not_leak_into_messages(load):
    load([trace(trace_id="a", session_id="s1", feedback="strong")])
    result = export_sft.build_sft_export()
    with open(result["output_path"]) as f:
        row = json.loads(f.readline())
    assert set(row.keys()) == {"messages", "metadata"}
    assert all("feedback" not in m for m in row["messages"])

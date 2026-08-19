"""Tests for preference pair export: retrials, weak ratings, rejected continuations."""
from __future__ import annotations

import json

import pytest

from db import ingest
from exports import export_preference


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
    monkeypatch.setattr(export_preference, "EXPORTS_DIR", tmp_path / "exports")
    monkeypatch.setattr(export_preference, "OUT_PATH", tmp_path / "exports" / "preference.jsonl")

    def _load(traces):
        db_path = tmp_path / "traces.db"
        traces_path = tmp_path / "traces.json"
        traces_path.write_text(json.dumps(traces))
        monkeypatch.setattr(ingest, "DB_PATH", db_path)
        ingest.load_corpus(traces_path)

    return _load


def test_retrial_pair(load):
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
    result = export_preference.build_preference_export()
    assert result["pairs_by_source"]["retrial"] == 1
    assert result["excluded_by_reason"] == {}


def test_retrial_loser_also_produces_weak_rating_pair(load):
    # A trace can be both the discarded side of a retrial *and* a valid
    # weak-rating candidate against the same winner -- these are two
    # independent signals and both should produce a pair.
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
    result = export_preference.build_preference_export()
    assert result["pair_count"] == 2
    assert result["pairs_by_source"]["retrial"] == 1
    assert result["pairs_by_source"]["weak_rating"] == 1
    assert result["excluded_by_reason"] == {}


def test_weak_rating_paired_when_candidate_exists(load):
    load(
        [
            trace(trace_id="weak1", session_id="s1", turn_index=0, feedback="weak"),
            trace(trace_id="strong1", session_id="s1", turn_index=0, feedback="strong"),
        ]
    )
    result = export_preference.build_preference_export()
    assert result["pairs_by_source"]["weak_rating"] == 1


def test_weak_rating_unpaired_logs_no_candidate(load):
    load([trace(trace_id="weak1", session_id="s1", turn_index=0, feedback="weak")])
    result = export_preference.build_preference_export()
    assert result["pair_count"] == 0
    assert result["excluded_by_reason"]["no_pairing_candidate"] == ["weak1"]


def test_continuation_rejected_paired(load):
    load(
        [
            trace(trace_id="acc", session_id="s1", turn_index=0, continuation_status="accepted"),
            trace(trace_id="rej", session_id="s1", turn_index=0, continuation_status="rejected"),
        ]
    )
    result = export_preference.build_preference_export()
    assert result["pairs_by_source"]["continuation_rejected"] == 1


def test_pair_requires_shared_session_and_turn(load):
    load(
        [
            trace(trace_id="weak1", session_id="s1", turn_index=0, feedback="weak"),
            trace(trace_id="strong1", session_id="s1", turn_index=1, feedback="strong"),
        ]
    )
    result = export_preference.build_preference_export()
    assert result["pair_count"] == 0
    assert result["excluded_by_reason"]["no_pairing_candidate"] == ["weak1"]


def test_output_shape(load):
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
    result = export_preference.build_preference_export()
    with open(result["output_path"]) as f:
        row = json.loads(f.readline())
    assert set(row.keys()) == {"input", "chosen", "rejected", "metadata"}
    assert set(row["metadata"].keys()) == {
        "source",
        "chosen_model",
        "rejected_model",
        "chosen_feedback",
        "rejected_feedback",
        "chosen_cost_usd",
        "rejected_cost_usd",
    }

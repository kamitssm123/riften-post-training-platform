"""Tests for SFT export: session collapsing + row-level exclusion rules."""
from __future__ import annotations

import json

import pytest

from db import ingest
from exports import export_sft


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


def test_longest_trace_excluded_drops_whole_session_no_fallback(load):
    # A 4-turn session where the longest trace (turn 3) is truncated and
    # excluded must drop the *entire* session -- not fall back to an
    # earlier, shorter turn.
    load(
        [
            trace(trace_id="t0", session_id="s1", turn_index=0),
            trace(trace_id="t1", session_id="s1", turn_index=1),
            trace(trace_id="t2", session_id="s1", turn_index=2),
            trace(trace_id="t3", session_id="s1", turn_index=3, finish_reason="length"),
        ]
    )
    result = export_sft.build_sft_export()
    assert result["kept_count"] == 0
    assert result["excluded_by_reason"]["session_longest_trace_excluded"] == ["t3"]
    assert set(result["excluded_by_reason"]["superseded_by_longer_session_trace"]) == {
        "t0",
        "t1",
        "t2",
    }


def test_single_trace_session_row_exclusion_keeps_original_reason(load):
    # A single-trace session failing a row-level check is a plain row-level
    # exclusion, not a "session_longest_trace_excluded" -- there was no
    # collapsing to speak of.
    load([trace(trace_id="a", session_id="s1", finish_reason="length")])
    result = export_sft.build_sft_export()
    assert result["excluded_by_reason"]["truncated_response"] == ["a"]
    assert "session_longest_trace_excluded" not in result["excluded_by_reason"]


def test_same_turn_tie_without_retrial_or_continuation_link(load):
    # Two independent traces tied on turn_index, neither a retrial loser
    # nor a rejected continuation of the other: the tiebreak falls back to
    # longest `messages` array, and exactly one row is kept.
    load(
        [
            trace(
                trace_id="short",
                session_id="s1",
                turn_index=0,
                messages=[{"role": "user", "content": "hi"}],
            ),
            trace(
                trace_id="long",
                session_id="s1",
                turn_index=0,
                messages=[
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "hi"},
                ],
            ),
        ]
    )
    result = export_sft.build_sft_export()
    assert result["kept_count"] == 1
    with open(result["output_path"]) as f:
        rows = [json.loads(line) for line in f]
    assert len(rows[0]["messages"]) == 3  # 2 long-session messages + response
    assert result["excluded_by_reason"]["superseded_by_longer_session_trace"] == ["short"]


def test_duplicate_message_content_across_sessions_is_deduped(load):
    # Two different sessions whose canonical trace happens to produce a
    # byte-identical messages+response array: only the first is kept, the
    # rest are dropped and logged, never silently duplicated in the output.
    load(
        [
            trace(trace_id="a", session_id="s1", turn_index=0),
            trace(trace_id="b", session_id="s2", turn_index=0),
        ]
    )
    result = export_sft.build_sft_export()
    assert result["kept_count"] == 1
    assert result["excluded_by_reason"]["duplicate_message_content"] == ["b"]
    with open(result["output_path"]) as f:
        rows = [json.loads(line) for line in f]
    assert len(rows) == 1

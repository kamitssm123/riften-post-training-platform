"""Tests for the live per-trace export-eligibility preview."""
from __future__ import annotations

import export_preview


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


def test_superseded_by_longer_session_trace_names_the_superseding_trace():
    traces = [
        trace(trace_id="a", session_id="s1", turn_index=0),
        trace(trace_id="b", session_id="s1", turn_index=1),
    ]
    preview = export_preview.build_export_preview("a", traces)
    assert preview["sft"]["included"] is False
    assert preview["sft"]["reason"] == "superseded_by_longer_session_trace"
    assert "b" in preview["sft"]["detail"]


def test_included_trace_reports_included_true():
    traces = [trace(trace_id="a", session_id="s1", turn_index=0)]
    preview = export_preview.build_export_preview("a", traces)
    assert preview["sft"] == {
        "included": True,
        "reason": None,
        "detail": "included in sft.jsonl",
    }


def test_retrial_pair_shows_role_source_and_partner():
    traces = [
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
    preview = export_preview.build_export_preview("bad", traces)
    assert preview["preference"]["eligible"] is True
    assert preview["preference"]["role"] == "rejected"
    assert preview["preference"]["source"] == "retrial"
    assert preview["preference"]["paired_with_trace_id"] == "good"


def test_trace_never_considered_is_not_eligible():
    traces = [trace(trace_id="a", session_id="s1", turn_index=0)]
    preview = export_preview.build_export_preview("a", traces)
    assert preview["preference"]["eligible"] is False
    assert preview["preference"]["role"] is None

"""Tests for the combined exclusion report."""
from __future__ import annotations

import json

import pytest

import exclusion_report
import export_preference
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
    monkeypatch.setattr(export_preference, "EXPORTS_DIR", tmp_path / "exports")
    monkeypatch.setattr(export_preference, "OUT_PATH", tmp_path / "exports" / "preference.jsonl")

    def _load(traces):
        db_path = tmp_path / "traces.db"
        traces_path = tmp_path / "traces.json"
        traces_path.write_text(json.dumps(traces))
        monkeypatch.setattr(ingest, "DB_PATH", db_path)
        ingest.load_corpus(traces_path)

    return _load


def test_report_counts_sum_correctly(load):
    load(
        [
            trace(trace_id="a", session_id="s1", turn_index=0),
            trace(trace_id="b", session_id="s1", turn_index=1, status_code=502),
            trace(trace_id="c", session_id="s2", turn_index=0, finish_reason="length"),
        ]
    )
    report = exclusion_report.build_exclusion_report()
    sft = report["sft"]
    total_excluded = sum(v["count"] for v in sft["excluded"].values())
    assert total_excluded + sft["kept_count"] == sft["total_traces_considered"]
    assert sft["excluded"]["superseded_by_longer_session_trace"]["sample_trace_ids"] == ["a"]


def test_report_has_both_export_sections(load):
    load([trace(trace_id="a", session_id="s1", turn_index=0)])
    report = exclusion_report.build_exclusion_report()
    assert "sft" in report and "preference" in report


def test_markdown_renders_without_error(load):
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
    report = exclusion_report.build_exclusion_report()
    md = exclusion_report.render_markdown(report)
    assert "# Exclusion Report" in md
    assert "SFT export" in md
    assert "Preference pair export" in md

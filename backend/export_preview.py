"""
Live per-trace export-eligibility preview. Runs the exact same
`compute_sft_plan()` / `compute_preference_plan()` used by the real
exports (`export_sft.py`, `export_preference.py`) over the full corpus,
then reads off the one requested trace's fate -- so the preview can never
diverge from what an actual export run would do. Backs
GET /traces/{trace_id}/export-preview.
"""
from __future__ import annotations

from typing import Any

from exclusion_rules import compute_preference_plan, compute_sft_plan

SFT_REASON_DETAIL = {
    "non_2xx_response": lambda t, _plan: f"status_code is {t['status_code']}, not in the 2xx range",
    "truncated_response": lambda t, _plan: "finish_reason is 'length'",
    "rejected_continuation": lambda t, _plan: "continuation_status is 'rejected'",
    "superseded_by_retrial": lambda t, plan: (
        f"a later retrial (trace {plan['superseded_by_trace_id']}) replaced this response"
    ),
    "superseded_by_longer_session_trace": lambda t, plan: (
        f"trace {plan['superseded_by_trace_id']} in the same session has a higher "
        "turn_index and was kept as the session's representative instead"
    ),
    "session_longest_trace_excluded": lambda t, plan: (
        "this was the session's longest trace, but it failed a row-level "
        f"check ({plan['row_level_reason']}) -- the whole session is "
        "excluded rather than falling back to a shorter trace"
    ),
    "duplicate_message_content": lambda t, _plan: (
        "another kept row already has an identical messages array"
    ),
}


def build_sft_preview(trace_id: str, all_traces: list[dict[str, Any]]) -> dict[str, Any]:
    plan = compute_sft_plan(all_traces)
    entry = plan["per_trace"].get(trace_id)
    if entry is None:
        # Should not happen for a trace_id that exists in the traces table --
        # every trace is grouped into exactly one session and given an entry.
        return {"included": False, "reason": None, "detail": None}

    if entry["included"]:
        return {"included": True, "reason": None, "detail": "included in sft.jsonl"}

    trace = next((t for t in all_traces if t["trace_id"] == trace_id), None)
    detail_fn = SFT_REASON_DETAIL.get(entry["reason"])
    detail = detail_fn(trace, entry) if detail_fn else None
    return {"included": False, "reason": entry["reason"], "detail": detail}


def build_preference_preview(trace_id: str, all_traces: list[dict[str, Any]]) -> dict[str, Any]:
    plan = compute_preference_plan(all_traces)
    entry = plan["per_trace"].get(trace_id)
    if entry is None:
        return {
            "eligible": False,
            "role": None,
            "source": None,
            "paired_with_trace_id": None,
            "detail": "never considered as either side of a preference pair",
        }

    if entry["eligible"]:
        return {
            "eligible": True,
            "role": entry["role"],
            "source": entry["source"],
            "paired_with_trace_id": entry["paired_with_trace_id"],
            "detail": f"{entry['role']} side of a {entry['source']} pair, "
            f"paired with trace {entry['paired_with_trace_id']}",
        }

    return {
        "eligible": False,
        "role": None,
        "source": None,
        "paired_with_trace_id": None,
        "detail": "no pairing candidate at the same session + turn_index",
    }


def build_export_preview(trace_id: str, all_traces: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sft": build_sft_preview(trace_id, all_traces),
        "preference": build_preference_preview(trace_id, all_traces),
    }

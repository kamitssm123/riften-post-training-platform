"""
SFT export: collapse each session down to its one canonical trace (the one
that already contains the full conversation), then apply row-level quality
exclusions. Writes /data/exports/sft.jsonl in OpenAI chat fine-tuning
format. Callable as a script or via POST /export/sft.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ingest import get_connection
from schema import Trace

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXPORTS_DIR = DATA_DIR / "exports"
OUT_PATH = EXPORTS_DIR / "sft.jsonl"

# Ordered so the first matching reason wins when a kept trace fails more
# than one rule -- keeps exclusion counts mutually exclusive and auditable.
ROW_EXCLUSION_ORDER = [
    "non_2xx_response",
    "truncated_response",
    "rejected_continuation",
    "superseded_by_retrial",
]


def fetch_all_traces() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM traces").fetchall()
        return [Trace.from_row(dict(r)) for r in rows]
    finally:
        conn.close()


def select_session_representative(session_traces: list[dict]) -> tuple[dict, list[dict]]:
    """Pick the one trace per session that already contains the full
    conversation, and return (kept, superseded).

    Traces are grouped by turn_index; the highest turn_index is the longest
    transcript. When more than one trace shares that turn_index (a retrial
    pair, or an accepted/rejected continuation pair -- both branch off the
    same prior context so their `messages` arrays are identical), we break
    the tie by preferring the branch that isn't already a "loser" by
    construction: not the discarded side of a retrial, not a rejected
    continuation. This is a deliberate call documented in the README --
    the spec's "highest turn_index / longest messages" rule alone doesn't
    disambiguate same-turn branches.
    """
    max_turn = max(t["turn_index"] for t in session_traces)
    candidates = [t for t in session_traces if t["turn_index"] == max_turn]
    superseded = [t for t in session_traces if t["turn_index"] != max_turn]

    if len(candidates) == 1:
        return candidates[0], superseded

    retrial_losers = {t["retrial_of"] for t in candidates if t["retrial_of"]}
    preferred = [
        t
        for t in candidates
        if t["trace_id"] not in retrial_losers and t["continuation_status"] != "rejected"
    ]

    if len(preferred) == 1:
        kept = preferred[0]
    elif len(preferred) > 1:
        kept = max(preferred, key=lambda t: t["timestamp"])
    else:
        kept = max(candidates, key=lambda t: t["timestamp"])

    superseded += [t for t in candidates if t["trace_id"] != kept["trace_id"]]
    return kept, superseded


def row_level_exclusion_reason(trace: dict, all_traces_by_id: dict[str, dict]) -> str | None:
    if not (200 <= trace["status_code"] < 300):
        return "non_2xx_response"
    if trace["finish_reason"] == "length":
        return "truncated_response"
    if trace["continuation_status"] == "rejected":
        return "rejected_continuation"
    is_retrial_loser = any(
        t["retrial_of"] == trace["trace_id"] for t in all_traces_by_id.values()
    )
    if is_retrial_loser:
        return "superseded_by_retrial"
    return None


def build_sft_export() -> dict[str, Any]:
    traces = fetch_all_traces()
    by_id = {t["trace_id"]: t for t in traces}

    by_session: dict[str, list[dict]] = defaultdict(list)
    for t in traces:
        by_session[t["session_id"]].append(t)

    kept_rows: list[dict] = []
    excluded: dict[str, list[str]] = defaultdict(list)

    for session_traces in by_session.values():
        kept, superseded = select_session_representative(session_traces)
        for t in superseded:
            excluded["superseded_by_longer_session_trace"].append(t["trace_id"])

        reason = row_level_exclusion_reason(kept, by_id)
        if reason:
            excluded[reason].append(kept["trace_id"])
        else:
            kept_rows.append(kept)

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as f:
        for t in kept_rows:
            record = {
                "messages": t["messages"] + [t["response"]],
                "metadata": {
                    "model": t["model"],
                    "tokens_prompt": t["tokens_prompt"],
                    "tokens_completion": t["tokens_completion"],
                    "cost_usd": t["cost_usd"],
                    "latency_ms": t["latency_ms"],
                    "feedback": t["feedback"],
                },
            }
            f.write(json.dumps(record) + "\n")

    return {
        "output_path": str(OUT_PATH),
        "total_traces_considered": len(traces),
        "total_sessions": len(by_session),
        "kept_count": len(kept_rows),
        "excluded_by_reason": {k: v for k, v in excluded.items()},
    }


def main() -> None:
    result = build_sft_export()
    print(
        f"Wrote {result['kept_count']} conversations to {result['output_path']} "
        f"(from {result['total_traces_considered']} traces across {result['total_sessions']} sessions)"
    )
    for reason, ids in result["excluded_by_reason"].items():
        print(f"  excluded[{reason}] = {len(ids)}")


if __name__ == "__main__":
    main()

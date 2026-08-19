"""
SFT export: collapse each session down to its one canonical trace (the one
that already contains the full conversation), then apply row-level quality
exclusions. Writes /data/exports/sft.jsonl in OpenAI chat fine-tuning
format. Callable as a script or via POST /export/sft.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.schema import Trace
from db.ingest import get_connection
from exports.exclusion_rules import (
    SFT_ROW_EXCLUSION_ORDER as ROW_EXCLUSION_ORDER,
    compute_sft_plan,
    row_level_exclusion_reason,
    select_session_representative,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
EXPORTS_DIR = DATA_DIR / "exports"
OUT_PATH = EXPORTS_DIR / "sft.jsonl"

__all__ = [
    "fetch_all_traces",
    "select_session_representative",
    "row_level_exclusion_reason",
    "build_sft_export",
    "ROW_EXCLUSION_ORDER",
]


def fetch_all_traces() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM traces").fetchall()
        return [Trace.from_row(dict(r)) for r in rows]
    finally:
        conn.close()


def build_sft_export() -> dict[str, Any]:
    traces = fetch_all_traces()
    plan = compute_sft_plan(traces)
    kept_rows = plan["kept_rows"]
    excluded = plan["excluded_by_reason"]

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
        "total_sessions": plan["total_sessions"],
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

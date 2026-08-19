"""
Preference pair export: build chosen/rejected pairs from retrials, weak
feedback ratings, and rejected continuations -- always requiring a shared
context (same session_id + turn_index). Writes
/data/exports/preference.jsonl. Callable as a script and via
POST /export/preference.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exclusion_rules import compute_preference_plan, make_preference_pair
from export_sft import fetch_all_traces

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXPORTS_DIR = DATA_DIR / "exports"
OUT_PATH = EXPORTS_DIR / "preference.jsonl"

# Kept as an alias so any external code importing `make_pair` from here
# keeps working -- the implementation now lives in exclusion_rules.py.
make_pair = make_preference_pair


def build_preference_export() -> dict[str, Any]:
    traces = fetch_all_traces()
    plan = compute_preference_plan(traces)
    pairs = plan["pairs"]
    excluded = plan["excluded_by_reason"]

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")

    return {
        "output_path": str(OUT_PATH),
        "total_traces_considered": len(traces),
        "pair_count": len(pairs),
        "pairs_by_source": plan["pairs_by_source"],
        "excluded_by_reason": {k: v for k, v in excluded.items()},
    }


def main() -> None:
    result = build_preference_export()
    print(
        f"Wrote {result['pair_count']} preference pairs to {result['output_path']} "
        f"(from {result['total_traces_considered']} traces)"
    )
    for source, count in result["pairs_by_source"].items():
        print(f"  {source}: {count}")
    for reason, ids in result["excluded_by_reason"].items():
        print(f"  excluded[{reason}] = {len(ids)}")


if __name__ == "__main__":
    main()

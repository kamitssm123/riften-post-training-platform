"""
Preference pair export: build chosen/rejected pairs from retrials, weak
feedback ratings, and rejected continuations -- always requiring a shared
context (same session_id + turn_index). Writes
/data/exports/preference.jsonl. Callable as a script and via
POST /export/preference.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from export_sft import fetch_all_traces

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXPORTS_DIR = DATA_DIR / "exports"
OUT_PATH = EXPORTS_DIR / "preference.jsonl"


def make_pair(chosen: dict, rejected: dict, source: str) -> dict[str, Any]:
    return {
        "input": {"messages": chosen["messages"]},
        "chosen": chosen["response"],
        "rejected": rejected["response"],
        "metadata": {
            "source": source,
            "chosen_model": chosen["model"],
            "rejected_model": rejected["model"],
            "chosen_feedback": chosen["feedback"],
            "rejected_feedback": rejected["feedback"],
            "chosen_cost_usd": chosen["cost_usd"],
            "rejected_cost_usd": rejected["cost_usd"],
        },
    }


def build_preference_export() -> dict[str, Any]:
    traces = fetch_all_traces()
    by_id = {t["trace_id"]: t for t in traces}

    by_session_turn: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for t in traces:
        by_session_turn[(t["session_id"], t["turn_index"])].append(t)

    pairs: list[dict] = []
    excluded: dict[str, list[str]] = defaultdict(list)
    used_rejected_ids: set[str] = set()

    # 1. Retrials: the discarded attempt is rejected, the trace that
    # replaced it (retrial_of points back to it) is chosen.
    for t in traces:
        if t["retrial_of"]:
            rejected = by_id.get(t["retrial_of"])
            if rejected is None:
                continue
            pairs.append(make_pair(t, rejected, "retrial"))
            used_rejected_ids.add(rejected["trace_id"])

    # 2. Weak ratings: paired against an ok/strong trace at the same
    # session+turn_index, if one exists. Never fabricate a chosen response
    # from an unrelated context -- skip and log otherwise.
    for t in traces:
        if t["feedback"] != "weak" or t["trace_id"] in used_rejected_ids:
            continue
        candidates = [
            c
            for c in by_session_turn[(t["session_id"], t["turn_index"])]
            if c["trace_id"] != t["trace_id"] and c["feedback"] in ("ok", "strong")
        ]
        if candidates:
            chosen = max(candidates, key=lambda c: c["feedback"] == "strong")
            pairs.append(make_pair(chosen, t, "weak_rating"))
            used_rejected_ids.add(t["trace_id"])
        else:
            excluded["no_pairing_candidate"].append(t["trace_id"])

    # 3. Continuation rejected: paired against the accepted continuation at
    # the same turn.
    for t in traces:
        if t["continuation_status"] != "rejected" or t["trace_id"] in used_rejected_ids:
            continue
        candidates = [
            c
            for c in by_session_turn[(t["session_id"], t["turn_index"])]
            if c["trace_id"] != t["trace_id"] and c["continuation_status"] == "accepted"
        ]
        if candidates:
            chosen = candidates[0]
            pairs.append(make_pair(chosen, t, "continuation_rejected"))
            used_rejected_ids.add(t["trace_id"])
        else:
            excluded["no_pairing_candidate"].append(t["trace_id"])

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")

    return {
        "output_path": str(OUT_PATH),
        "total_traces_considered": len(traces),
        "pair_count": len(pairs),
        "pairs_by_source": {
            source: sum(1 for p in pairs if p["metadata"]["source"] == source)
            for source in ("retrial", "weak_rating", "continuation_rejected")
        },
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

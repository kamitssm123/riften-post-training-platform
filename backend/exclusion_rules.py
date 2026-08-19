"""
Single source of truth for the SFT and preference-pair exclusion rules.
Both `export_sft.py`/`export_preference.py` (which write the real
`.jsonl` files) and `GET /traces/{trace_id}/export-preview` (a read-only
per-trace preview) call the `compute_*_plan()` functions below -- neither
export script nor the preview endpoint re-implements the rule logic itself.

The `select_session_representative` / `row_level_exclusion_reason` /
`make_preference_pair` functions are moved here verbatim from
`export_sft.py` / `export_preference.py`; behavior is unchanged.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

SFT_ROW_EXCLUSION_ORDER = [
    "non_2xx_response",
    "truncated_response",
    "rejected_continuation",
    "superseded_by_retrial",
]


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


def retrial_winner_of(trace_id: str, all_traces_by_id: dict[str, dict]) -> dict | None:
    """The trace (if any) whose retrial_of points back at trace_id."""
    for t in all_traces_by_id.values():
        if t["retrial_of"] == trace_id:
            return t
    return None


def compute_sft_plan(traces: list[dict]) -> dict[str, Any]:
    """Run the full SFT session-collapse + row-level exclusion algorithm.

    Returns kept_rows, excluded_by_reason (same shape build_sft_export has
    always returned), total_sessions, and a per_trace map giving every
    trace's SFT fate -- used by the export-preview endpoint.
    """
    by_id = {t["trace_id"]: t for t in traces}
    by_session: dict[str, list[dict]] = defaultdict(list)
    for t in traces:
        by_session[t["session_id"]].append(t)

    kept_rows: list[dict] = []
    excluded: dict[str, list[str]] = defaultdict(list)
    per_trace: dict[str, dict[str, Any]] = {}

    for session_traces in by_session.values():
        kept, superseded = select_session_representative(session_traces)
        for t in superseded:
            excluded["superseded_by_longer_session_trace"].append(t["trace_id"])
            per_trace[t["trace_id"]] = {
                "included": False,
                "reason": "superseded_by_longer_session_trace",
                "superseded_by_trace_id": kept["trace_id"],
            }

        reason = row_level_exclusion_reason(kept, by_id)
        if reason:
            excluded[reason].append(kept["trace_id"])
            per_trace[kept["trace_id"]] = {
                "included": False,
                "reason": reason,
                "superseded_by_trace_id": (
                    retrial_winner_of(kept["trace_id"], by_id)["trace_id"]
                    if reason == "superseded_by_retrial"
                    else None
                ),
            }
        else:
            kept_rows.append(kept)
            per_trace[kept["trace_id"]] = {
                "included": True,
                "reason": None,
                "superseded_by_trace_id": None,
            }

    return {
        "kept_rows": kept_rows,
        "excluded_by_reason": dict(excluded),
        "total_sessions": len(by_session),
        "per_trace": per_trace,
    }


def make_preference_pair(chosen: dict, rejected: dict, source: str) -> dict[str, Any]:
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


def compute_preference_plan(traces: list[dict]) -> dict[str, Any]:
    """Run the full preference-pairing algorithm.

    Returns pairs, excluded_by_reason, pairs_by_source (same shape
    build_preference_export has always returned) and a per_trace map giving
    every trace's preference-pair fate -- used by the export-preview
    endpoint. A trace not mentioned in per_trace was never considered as
    either side of any pair.
    """
    by_id = {t["trace_id"]: t for t in traces}

    by_session_turn: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for t in traces:
        by_session_turn[(t["session_id"], t["turn_index"])].append(t)

    pairs: list[dict] = []
    excluded: dict[str, list[str]] = defaultdict(list)
    used_rejected_ids: set[str] = set()
    per_trace: dict[str, dict[str, Any]] = {}

    def mark_once(trace_id: str, **fields: Any) -> None:
        # First pairing found wins if a trace ends up on the "chosen" side
        # of more than one pair -- deterministic, and irrelevant to what
        # gets written (this is read-only bookkeeping for the preview).
        per_trace.setdefault(trace_id, fields)

    # 1. Retrials: the discarded attempt is rejected, the trace that
    # replaced it (retrial_of points back to it) is chosen.
    for t in traces:
        if t["retrial_of"]:
            rejected = by_id.get(t["retrial_of"])
            if rejected is None:
                continue
            pairs.append(make_preference_pair(t, rejected, "retrial"))
            used_rejected_ids.add(rejected["trace_id"])
            mark_once(
                t["trace_id"],
                eligible=True,
                role="chosen",
                source="retrial",
                paired_with_trace_id=rejected["trace_id"],
            )
            mark_once(
                rejected["trace_id"],
                eligible=True,
                role="rejected",
                source="retrial",
                paired_with_trace_id=t["trace_id"],
            )

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
            pairs.append(make_preference_pair(chosen, t, "weak_rating"))
            used_rejected_ids.add(t["trace_id"])
            mark_once(
                chosen["trace_id"],
                eligible=True,
                role="chosen",
                source="weak_rating",
                paired_with_trace_id=t["trace_id"],
            )
            mark_once(
                t["trace_id"],
                eligible=True,
                role="rejected",
                source="weak_rating",
                paired_with_trace_id=chosen["trace_id"],
            )
        else:
            excluded["no_pairing_candidate"].append(t["trace_id"])
            mark_once(
                t["trace_id"],
                eligible=False,
                role=None,
                source=None,
                paired_with_trace_id=None,
                exclusion_reason="no_pairing_candidate",
            )

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
            pairs.append(make_preference_pair(chosen, t, "continuation_rejected"))
            used_rejected_ids.add(t["trace_id"])
            mark_once(
                chosen["trace_id"],
                eligible=True,
                role="chosen",
                source="continuation_rejected",
                paired_with_trace_id=t["trace_id"],
            )
            mark_once(
                t["trace_id"],
                eligible=True,
                role="rejected",
                source="continuation_rejected",
                paired_with_trace_id=chosen["trace_id"],
            )
        else:
            excluded["no_pairing_candidate"].append(t["trace_id"])
            mark_once(
                t["trace_id"],
                eligible=False,
                role=None,
                source=None,
                paired_with_trace_id=None,
                exclusion_reason="no_pairing_candidate",
            )

    return {
        "pairs": pairs,
        "excluded_by_reason": dict(excluded),
        "pairs_by_source": {
            source: sum(1 for p in pairs if p["metadata"]["source"] == source)
            for source in ("retrial", "weak_rating", "continuation_rejected")
        },
        "per_trace": per_trace,
    }

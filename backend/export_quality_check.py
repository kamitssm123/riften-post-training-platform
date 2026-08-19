"""
Standalone export-quality scorer, independent of `exclusion_rules.py`'s own
bookkeeping. Loads `/data/traces.json`, `/data/exports/sft.jsonl`, and
`/data/exports/preference.jsonl`, and re-derives ground truth directly from
the raw corpus (not by trusting `compute_sft_plan`/`compute_preference_plan`)
so a bug shared between the exporter and the scorer can't hide itself.

Run directly: `python export_quality_check.py`.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from corpus_quality_check import STOPWORDS, TOKEN_RE, tokenize  # noqa: F401 (STOPWORDS/TOKEN_RE re-exported for callers)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXPORTS_DIR = DATA_DIR / "exports"
TRACES_PATH = DATA_DIR / "traces.json"
SFT_PATH = EXPORTS_DIR / "sft.jsonl"
PREFERENCE_PATH = EXPORTS_DIR / "preference.jsonl"

REQUIRED_SFT_METADATA_FIELDS = [
    "model",
    "tokens_prompt",
    "tokens_completion",
    "cost_usd",
    "latency_ms",
]


def load_json_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True)


def build_trace_index(traces: list[dict]) -> dict[tuple, dict]:
    """Key every trace by (context messages, response, model, cost_usd) --
    a near-certainly-unique fingerprint used to match an export row back to
    its source trace, since neither export retains trace_id."""
    index: dict[tuple, dict] = {}
    for t in traces:
        key = (canon(t["messages"]), canon(t["response"]), t["model"], t["cost_usd"])
        index[key] = t
    return index


def find_trace(index: dict[tuple, dict], messages: Any, response: Any, model: str, cost_usd: float) -> dict | None:
    return index.get((canon(messages), canon(response), model, cost_usd))


# ---------------------------------------------------------------------------
# SFT scoring
# ---------------------------------------------------------------------------

def score_sft_coherence(sft_rows: list[dict]) -> tuple[float, dict[str, str]]:
    total = len(sft_rows)
    overlapping = 0
    for row in sft_rows:
        messages = row["messages"]
        response = messages[-1]["content"]
        question = None
        for m in reversed(messages[:-1]):
            if m["role"] == "user":
                question = m["content"]
                break
        if question is None:
            continue
        if tokenize(question) & tokenize(response):
            overlapping += 1

    rate = overlapping / total if total else 0.0
    if rate >= 0.95:
        pts = 40.0
    elif rate <= 0.20:
        pts = 0.0
    else:
        pts = 40.0 * (rate - 0.20) / (0.95 - 0.20)

    return pts, {"keyword_overlap_rate": f"{overlapping}/{total} = {rate:.2%} (target >=95%)"}


def score_sft_metadata_completeness(sft_rows: list[dict]) -> tuple[float, dict[str, str]]:
    total = len(sft_rows)
    complete = 0
    for row in sft_rows:
        meta = row.get("metadata", {})
        if all(f in meta and meta[f] is not None for f in REQUIRED_SFT_METADATA_FIELDS):
            complete += 1
    rate = complete / total if total else 1.0
    pts = 15.0 * rate
    return pts, {"rows_with_all_5_fields": f"{complete}/{total} = {rate:.2%}"}


def score_sft_row_level_exclusion(sft_rows: list[dict], trace_index: dict[tuple, dict], traces_by_id: dict[str, dict]) -> tuple[float, dict[str, str]]:
    total = len(sft_rows)
    bad = 0
    unmatched = 0
    retrial_loser_ids = {t["retrial_of"] for t in traces_by_id.values() if t["retrial_of"]}
    for row in sft_rows:
        messages = row["messages"]
        response = messages[-1]
        model = row["metadata"]["model"]
        cost_usd = row["metadata"]["cost_usd"]
        t = find_trace(trace_index, messages[:-1], response, model, cost_usd)
        if t is None:
            unmatched += 1
            continue
        if not (200 <= t["status_code"] < 300):
            bad += 1
        elif t["finish_reason"] == "length":
            bad += 1
        elif t["continuation_status"] == "rejected":
            bad += 1
        elif t["trace_id"] in retrial_loser_ids:
            bad += 1

    rate_bad = (bad + unmatched) / total if total else 0.0
    pts = 15.0 * (1 - rate_bad)
    return pts, {
        "rows_failing_row_level_check": f"{bad}/{total}",
        "rows_unmatched_to_source_trace": f"{unmatched}/{total}",
    }


def score_sft_session_collapsing(sft_rows: list[dict], trace_index: dict[tuple, dict]) -> tuple[float, dict[str, str]]:
    # No two rows may share identical `messages` arrays.
    message_keys = [canon(row["messages"]) for row in sft_rows]
    dup_message_groups = sum(1 for count in Counter(message_keys).values() if count > 1)

    # No session may contribute more than one row.
    session_counts: Counter[str] = Counter()
    unmatched = 0
    for row in sft_rows:
        messages = row["messages"]
        response = messages[-1]
        model = row["metadata"]["model"]
        cost_usd = row["metadata"]["cost_usd"]
        t = find_trace(trace_index, messages[:-1], response, model, cost_usd)
        if t is None:
            unmatched += 1
            continue
        session_counts[t["session_id"]] += 1
    leaking_sessions = {sid: c for sid, c in session_counts.items() if c > 1}

    passed = dup_message_groups == 0 and not leaking_sessions and unmatched == 0
    pts = 30.0 if passed else 0.0
    return pts, {
        "duplicate_message_array_groups": str(dup_message_groups),
        "sessions_leaking_more_than_1_row": f"{len(leaking_sessions)} {list(leaking_sessions.items())[:5]}",
        "rows_unmatched_to_source_trace": str(unmatched),
        "result": "PASS" if passed else "FAIL",
    }


def score_sft_export(traces: list[dict], sft_rows: list[dict]) -> dict[str, Any]:
    traces_by_id = {t["trace_id"]: t for t in traces}
    trace_index = build_trace_index(traces)

    coherence_pts, coherence_d = score_sft_coherence(sft_rows)
    meta_pts, meta_d = score_sft_metadata_completeness(sft_rows)
    row_pts, row_d = score_sft_row_level_exclusion(sft_rows, trace_index, traces_by_id)
    collapse_pts, collapse_d = score_sft_session_collapsing(sft_rows, trace_index)

    total = coherence_pts + meta_pts + row_pts + collapse_pts
    return {
        "total": total,
        "content_coherence": {"points": coherence_pts, "max": 40.0, "details": coherence_d},
        "metadata_completeness": {"points": meta_pts, "max": 15.0, "details": meta_d},
        "row_level_exclusion_correctness": {"points": row_pts, "max": 15.0, "details": row_d},
        "session_collapsing_correctness": {"points": collapse_pts, "max": 30.0, "details": collapse_d},
    }


# ---------------------------------------------------------------------------
# Preference scoring
# ---------------------------------------------------------------------------

def score_pref_no_identical_pairs(pairs: list[dict]) -> tuple[float, dict[str, str]]:
    bad = sum(1 for p in pairs if canon(p["chosen"]) == canon(p["rejected"]))
    passed = bad == 0
    return (25.0 if passed else 0.0), {
        "pairs_with_identical_chosen_rejected": str(bad),
        "result": "PASS" if passed else "FAIL",
    }


def _match_pair_sides(p: dict, trace_index: dict[tuple, dict]) -> tuple[dict | None, dict | None]:
    messages = p["input"]["messages"]
    meta = p["metadata"]
    chosen_t = find_trace(trace_index, messages, p["chosen"], meta["chosen_model"], meta["chosen_cost_usd"])
    rejected_t = find_trace(trace_index, messages, p["rejected"], meta["rejected_model"], meta["rejected_cost_usd"])
    return chosen_t, rejected_t


def score_pref_retrial(pairs: list[dict], trace_index: dict[tuple, dict], traces: list[dict]) -> tuple[float, dict[str, str]]:
    retrial_pairs = [p for p in pairs if p["metadata"]["source"] == "retrial"]
    total = len(retrial_pairs)
    all_ids = {t["trace_id"] for t in traces}
    expected = sum(1 for t in traces if t.get("retrial_of") and t["retrial_of"] in all_ids)

    valid = 0
    for p in retrial_pairs:
        chosen_t, rejected_t = _match_pair_sides(p, trace_index)
        if chosen_t is None or rejected_t is None:
            continue
        if chosen_t.get("retrial_of") == rejected_t["trace_id"]:
            valid += 1

    # Denominator is the independently-scanned expected count, not the
    # export's own total -- an export that silently produced zero pairs
    # must not score full marks just because 0/0 looks "clean".
    rate = (valid / expected) if expected else (1.0 if total == 0 else 0.0)
    rate = min(1.0, rate)
    return 20.0 * rate, {
        "retrial_pairs_verified": f"{valid}/{total}",
        "independently_expected_retrial_pairs": str(expected),
    }


def score_pref_continuation_rejected(pairs: list[dict], trace_index: dict[tuple, dict], traces: list[dict]) -> tuple[float, dict[str, str]]:
    cont_pairs = [p for p in pairs if p["metadata"]["source"] == "continuation_rejected"]
    total = len(cont_pairs)

    by_session_turn: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for t in traces:
        by_session_turn[(t["session_id"], t["turn_index"])].append(t)
    expected = sum(
        1
        for t in traces
        if t.get("continuation_status") == "rejected"
        and any(c["continuation_status"] == "accepted" for c in by_session_turn[(t["session_id"], t["turn_index"])])
    )

    valid = 0
    for p in cont_pairs:
        chosen_t, rejected_t = _match_pair_sides(p, trace_index)
        if chosen_t is None or rejected_t is None:
            continue
        if (
            chosen_t["continuation_status"] == "accepted"
            and rejected_t["continuation_status"] == "rejected"
            and chosen_t["session_id"] == rejected_t["session_id"]
            and chosen_t["turn_index"] == rejected_t["turn_index"]
        ):
            valid += 1

    rate = (valid / expected) if expected else (1.0 if total == 0 else 0.0)
    rate = min(1.0, rate)
    return 20.0 * rate, {
        "continuation_rejected_pairs_verified": f"{valid}/{total}",
        "independently_expected_continuation_rejected_pairs": str(expected),
    }


def independent_weak_rating_candidates(traces: list[dict]) -> dict[str, dict]:
    """Scan the raw corpus for every weak-feedback trace that has an
    ok/strong trace at the same session_id + turn_index. Returns
    {weak_trace_id: better_trace} -- one candidate mapping per weak trace,
    computed without importing exclusion_rules.py."""
    by_session_turn: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for t in traces:
        by_session_turn[(t["session_id"], t["turn_index"])].append(t)

    candidates: dict[str, dict] = {}
    for t in traces:
        if t["feedback"] != "weak":
            continue
        better = [
            c
            for c in by_session_turn[(t["session_id"], t["turn_index"])]
            if c["trace_id"] != t["trace_id"] and c["feedback"] in ("ok", "strong")
        ]
        if better:
            candidates[t["trace_id"]] = better[0]
    return candidates


def score_pref_weak_rating(pairs: list[dict], traces: list[dict], trace_index: dict[tuple, dict]) -> tuple[float, dict[str, str]]:
    candidates = independent_weak_rating_candidates(traces)
    weak_pairs = [p for p in pairs if p["metadata"]["source"] == "weak_rating"]

    validated_weak_trace_ids: set[str] = set()
    for p in weak_pairs:
        chosen_t, rejected_t = _match_pair_sides(p, trace_index)
        if chosen_t is None or rejected_t is None:
            continue
        if (
            rejected_t["feedback"] == "weak"
            and chosen_t["feedback"] in ("ok", "strong")
            and chosen_t["session_id"] == rejected_t["session_id"]
            and chosen_t["turn_index"] == rejected_t["turn_index"]
            and rejected_t["trace_id"] in candidates
        ):
            validated_weak_trace_ids.add(rejected_t["trace_id"])

    denom = len(candidates)
    rate = len(validated_weak_trace_ids) / denom if denom else 1.0
    pts = min(35.0, 35.0 * rate)
    return pts, {
        "independently_found_valid_candidates": str(denom),
        "weak_rating_pairs_in_export": str(len(weak_pairs)),
        "validated_pairs_matching_a_real_candidate": f"{len(validated_weak_trace_ids)}/{denom}",
    }


def score_preference_export(traces: list[dict], pairs: list[dict]) -> dict[str, Any]:
    trace_index = build_trace_index(traces)

    identical_pts, identical_d = score_pref_no_identical_pairs(pairs)
    retrial_pts, retrial_d = score_pref_retrial(pairs, trace_index, traces)
    cont_pts, cont_d = score_pref_continuation_rejected(pairs, trace_index, traces)
    weak_pts, weak_d = score_pref_weak_rating(pairs, traces, trace_index)

    total = identical_pts + retrial_pts + cont_pts + weak_pts
    return {
        "total": total,
        "zero_identical_pairs": {"points": identical_pts, "max": 25.0, "details": identical_d},
        "retrial_pairs_verified": {"points": retrial_pts, "max": 20.0, "details": retrial_d},
        "continuation_rejected_pairs_verified": {"points": cont_pts, "max": 20.0, "details": cont_d},
        "weak_rating_source": {"points": weak_pts, "max": 35.0, "details": weak_d},
    }


# ---------------------------------------------------------------------------

def print_section(title: str, result: dict[str, Any], parts: list[tuple[str, str]]) -> None:
    print(f"=== {title}: {result['total']:.1f} / 100 ===\n")
    for key, label in parts:
        section = result[key]
        print(f"-- {label}: {section['points']:.1f} / {section['max']:.0f} --")
        for k, v in section["details"].items():
            print(f"  {k}: {v}")
        print()


def main() -> None:
    traces = json.loads(TRACES_PATH.read_text())
    sft_rows = load_json_lines(SFT_PATH)
    pref_pairs = load_json_lines(PREFERENCE_PATH)

    sft_result = score_sft_export(traces, sft_rows)
    pref_result = score_preference_export(traces, pref_pairs)

    print_section(
        "SFT export score",
        sft_result,
        [
            ("content_coherence", "Content coherence (40 pts)"),
            ("metadata_completeness", "Metadata completeness (15 pts)"),
            ("row_level_exclusion_correctness", "Row-level exclusion correctness (15 pts)"),
            ("session_collapsing_correctness", "Session collapsing correctness (30 pts, pass/fail)"),
        ],
    )
    print_section(
        "Preference export score",
        pref_result,
        [
            ("zero_identical_pairs", "Zero identical chosen/rejected pairs (25 pts, pass/fail)"),
            ("retrial_pairs_verified", "Retrial pairs verified (20 pts)"),
            ("continuation_rejected_pairs_verified", "Continuation-rejected pairs verified (20 pts)"),
            ("weak_rating_source", "Weak-rating source (35 pts)"),
        ],
    )

    for label, result in (("SFT", sft_result), ("Preference", pref_result)):
        status = "OK" if 90 <= result["total"] <= 95 else ("BELOW TARGET" if result["total"] < 90 else "ABOVE TARGET RANGE")
        print(f"{label} total: {result['total']:.1f} / 100 (target 90-95) [{status}]")


if __name__ == "__main__":
    sys.exit(main())

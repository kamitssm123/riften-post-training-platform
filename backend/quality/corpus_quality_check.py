"""
Standalone corpus content-quality scorer.

Loads /data/traces.json and scores it 0-100 against three categories:

  - Category coverage (40 pts): model mix, truncation rate, tool-error
    rate, retrial rate/links, continuation accept/reject presence and
    session-length spread. This should already be in a realistic range and
    is here to catch regressions, not to be chased.
  - Content coherence (40 pts): stopword-stripped keyword overlap between
    each trace's own question and its own response.
  - Diversity (20 pts): unique question count, unique response count, and
    the rate of sessions with an unexplained verbatim-repeated question.

Run directly: `python -m quality.corpus_quality_check [path/to/traces.json]`.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_TRACES_PATH = DATA_DIR / "traces.json"

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing", "have", "has", "had", "having",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
    "them", "my", "your", "his", "its", "our", "their", "this", "that",
    "these", "those", "to", "of", "in", "on", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "from", "up", "down", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "s", "t", "can", "will", "just",
    "should", "now", "and", "or", "but", "if", "as", "what", "which",
    "who", "whom", "please", "would", "could", "get", "let", "one", "go",
    "going", "want", "need", "help", "give", "tell", "check", "quick",
    "short", "make", "sure",
}

TOKEN_RE = re.compile(r"[a-z0-9']+")

MODEL_SHARE_CAP = 0.45
MODEL_MIN_DISTINCT = 4
TRUNCATION_BAND = (0.05, 0.12)
ERROR_BAND = (0.05, 0.15)
RETRIAL_BAND = (0.02, 0.08)


def load_traces(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def tokenize(text: str) -> set[str]:
    tokens = TOKEN_RE.findall(text.lower())
    return {t for t in tokens if t not in STOPWORDS and len(t) > 1}


# ---------------------------------------------------------------------------
# Category coverage (40 pts)
# ---------------------------------------------------------------------------

def score_model_mix(traces: list[dict]) -> tuple[float, str]:
    counts = Counter(t["model"] for t in traces)
    total = len(traces)
    distinct = len(counts)
    max_share = max(counts.values()) / total if total else 1.0
    ok = distinct >= MODEL_MIN_DISTINCT and max_share <= MODEL_SHARE_CAP
    pts = 8.0 if ok else 0.0
    detail = f"{distinct} distinct models, max share {max_share:.1%} ({dict(counts)})"
    return pts, detail


def score_band(value: float, band: tuple[float, float], label: str) -> tuple[float, str]:
    lo, hi = band
    ok = lo <= value <= hi
    pts = 8.0 if ok else 0.0
    detail = f"{label} = {value:.2%} (target {lo:.0%}-{hi:.0%})"
    return pts, detail


def score_truncation(traces: list[dict]) -> tuple[float, str]:
    total = len(traces)
    truncated = sum(1 for t in traces if t["finish_reason"] == "length")
    rate = truncated / total if total else 0.0
    return score_band(rate, TRUNCATION_BAND, "truncation rate")


def is_errored(t: dict) -> bool:
    if t["status_code"] >= 400:
        return True
    for tc in (t.get("tool_calls") or []):
        if tc.get("result", {}).get("status_code", 0) >= 400:
            return True
    return False


def score_tool_error(traces: list[dict]) -> tuple[float, str]:
    total = len(traces)
    errored = sum(1 for t in traces if is_errored(t))
    rate = errored / total if total else 0.0
    return score_band(rate, ERROR_BAND, "tool-error/non-2xx rate")


def score_retrial(traces: list[dict]) -> tuple[float, str]:
    total = len(traces)
    by_id = {t["trace_id"]: t for t in traces}
    retrials = [t for t in traces if t.get("is_retrial")]
    rate = len(retrials) / total if total else 0.0
    lo, hi = RETRIAL_BAND
    rate_ok = lo <= rate <= hi
    links_ok = all(
        t.get("retrial_of") and t["retrial_of"] in by_id for t in retrials
    ) if retrials else False
    ok = rate_ok and links_ok
    pts = 8.0 if ok else 0.0
    detail = (
        f"retrial rate = {rate:.2%} (target {lo:.0%}-{hi:.0%}), "
        f"valid retrial_of links: {links_ok} ({len(retrials)} retrials)"
    )
    return pts, detail


def score_continuation_and_sessions(traces: list[dict]) -> tuple[float, str]:
    total = len(traces)
    accepted = sum(1 for t in traces if t.get("continuation_status") == "accepted")
    rejected = sum(1 for t in traces if t.get("continuation_status") == "rejected")
    accepted_rate = accepted / total if total else 0.0
    rejected_rate = rejected / total if total else 0.0
    continuation_ok = accepted_rate >= 0.01 and rejected_rate >= 0.01

    by_session: dict[str, set[int]] = defaultdict(set)
    for t in traces:
        by_session[t["session_id"]].add(t["turn_index"])
    lengths = [len(v) for v in by_session.values()]
    length_spread_ok = len(set(lengths)) >= 3 and not all(l == lengths[0] for l in lengths)

    ok = continuation_ok and length_spread_ok
    pts = 8.0 if ok else 0.0
    detail = (
        f"accepted={accepted_rate:.2%}, rejected={rejected_rate:.2%}, "
        f"session length distinct values={sorted(set(lengths))}"
    )
    return pts, detail


def score_category_coverage(traces: list[dict]) -> tuple[float, dict[str, str]]:
    details: dict[str, str] = {}
    total_pts = 0.0

    pts, d = score_model_mix(traces)
    total_pts += pts
    details["model_mix (8)"] = f"{pts:.1f} pts -- {d}"

    pts, d = score_truncation(traces)
    total_pts += pts
    details["truncation_rate (8)"] = f"{pts:.1f} pts -- {d}"

    pts, d = score_tool_error(traces)
    total_pts += pts
    details["tool_error_rate (8)"] = f"{pts:.1f} pts -- {d}"

    pts, d = score_retrial(traces)
    total_pts += pts
    details["retrial (8)"] = f"{pts:.1f} pts -- {d}"

    pts, d = score_continuation_and_sessions(traces)
    total_pts += pts
    details["continuation_and_session_spread (8)"] = f"{pts:.1f} pts -- {d}"

    return total_pts, details


# ---------------------------------------------------------------------------
# Content coherence (40 pts)
# ---------------------------------------------------------------------------

def last_user_question(messages: list[dict]) -> str | None:
    for m in reversed(messages):
        if m["role"] == "user":
            return m["content"]
    return None


def score_content_coherence(traces: list[dict]) -> tuple[float, dict[str, str]]:
    total = len(traces)
    overlapping = 0
    for t in traces:
        question = last_user_question(t["messages"])
        response = t["response"]["content"]
        if question is None:
            continue
        q_tokens = tokenize(question)
        r_tokens = tokenize(response)
        if q_tokens & r_tokens:
            overlapping += 1

    rate = overlapping / total if total else 0.0
    # Linear: 40 pts at >=90% overlap, 0 pts at <=20% overlap.
    if rate >= 0.90:
        pts = 40.0
    elif rate <= 0.20:
        pts = 0.0
    else:
        pts = 40.0 * (rate - 0.20) / (0.90 - 0.20)

    details = {
        "keyword_overlap_rate": f"{overlapping}/{total} = {rate:.2%} (target >=90%)",
    }
    return pts, details


# ---------------------------------------------------------------------------
# Diversity (20 pts)
# ---------------------------------------------------------------------------

def score_diversity(traces: list[dict]) -> tuple[float, dict[str, str]]:
    unique_questions = {last_user_question(t["messages"]) for t in traces} - {None}
    unique_responses = {t["response"]["content"] for t in traces}

    q_pts = 8.0 if len(unique_questions) >= 60 else 0.0
    r_pts = 8.0 if len(unique_responses) >= 60 else 0.0

    by_session: dict[str, list[dict]] = defaultdict(list)
    for t in traces:
        by_session[t["session_id"]].append(t)

    unexplained_repeat_sessions = 0
    for session_id, session_traces in by_session.items():
        seen_questions: dict[str, dict] = {}
        flagged = False
        for t in sorted(session_traces, key=lambda x: (x["turn_index"], x["timestamp"])):
            q = last_user_question(t["messages"])
            if q is None:
                continue
            prior = seen_questions.get(q)
            if prior is not None:
                explained = bool(t.get("is_retrial")) or bool(t.get("continuation_status")) or bool(
                    prior.get("continuation_status")
                )
                if not explained:
                    flagged = True
            seen_questions[q] = t
        if flagged:
            unexplained_repeat_sessions += 1

    session_total = len(by_session)
    repeat_rate = unexplained_repeat_sessions / session_total if session_total else 0.0
    repeat_pts = 4.0 if repeat_rate <= 0.03 else 0.0

    total_pts = q_pts + r_pts + repeat_pts
    details = {
        "unique_questions (8)": f"{q_pts:.1f} pts -- {len(unique_questions)} unique (target >=60)",
        "unique_responses (8)": f"{r_pts:.1f} pts -- {len(unique_responses)} unique (target >=60)",
        "unexplained_repeat_sessions (4)": (
            f"{repeat_pts:.1f} pts -- {unexplained_repeat_sessions}/{session_total} = "
            f"{repeat_rate:.2%} (target <=3%)"
        ),
    }
    return total_pts, details


# ---------------------------------------------------------------------------

def score_corpus(traces: list[dict]) -> dict:
    coverage_pts, coverage_details = score_category_coverage(traces)
    coherence_pts, coherence_details = score_content_coherence(traces)
    diversity_pts, diversity_details = score_diversity(traces)

    total = coverage_pts + coherence_pts + diversity_pts

    return {
        "total": total,
        "category_coverage": {"points": coverage_pts, "max": 40.0, "details": coverage_details},
        "content_coherence": {"points": coherence_pts, "max": 40.0, "details": coherence_details},
        "diversity": {"points": diversity_pts, "max": 20.0, "details": diversity_details},
    }


def print_report(result: dict) -> None:
    print(f"=== Corpus quality score: {result['total']:.1f} / 100 ===\n")
    for section_key, label in (
        ("category_coverage", "Category coverage (40 pts)"),
        ("content_coherence", "Content coherence (40 pts)"),
        ("diversity", "Diversity (20 pts)"),
    ):
        section = result[section_key]
        print(f"-- {label}: {section['points']:.1f} / {section['max']:.0f} --")
        for k, v in section["details"].items():
            print(f"  {k}: {v}")
        print()


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TRACES_PATH
    traces = load_traces(path)
    result = score_corpus(traces)
    print_report(result)
    if result["total"] < 85:
        print("Below target (85-90). Widen the content bank / fix remaining mismatches.")


if __name__ == "__main__":
    main()

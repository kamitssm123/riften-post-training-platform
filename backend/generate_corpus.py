"""
Synthetic corpus generator for the Riften post-training data platform.

Produces 300-400 Trace rows across ~100-150 sessions, written to
/data/traces.json (an intermediate artifact -- ingest.py loads this into
SQLite). Deliberately messy: retries, tool errors, truncated responses,
mixed models skewed toward cheaper ones, multi-turn sessions that resend
the full transcript each turn, and agentic continuation accept/reject pairs.

Content is drawn from the topic-locked bank in content_bank.py: every trace
picks a Topic first, then draws its question and response from the same
Exchange within that topic, so a trace's response is always about what its
own question asked. Session-internal question repetition only happens for
genuine retries (paired with is_retrial/retrial_of); any other multi-turn
session either moves to a new topic or advances to a natural follow-up
exchange within the current topic.

Deterministic via a fixed random seed so runs are reproducible.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from content_bank import AGENTIC_TOPICS, NON_AGENTIC_TOPICS, Exchange, Topic
from schema import MODEL_LATENCY_MS, MODEL_PRICING_PER_1K, Model

random.seed(42)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_PATH = DATA_DIR / "traces.json"

MODELS: list[Model] = [
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-5-sonnet",
    "llama-3.1-70b",
    "gemini-1.5-flash",
]
# Skew volume toward cheaper models, matching Riften's own "cheapest model
# likely to succeed" routing pitch.
MODEL_WEIGHTS = {
    "gpt-4o": 0.10,
    "gpt-4o-mini": 0.32,
    "claude-3-5-sonnet": 0.13,
    "llama-3.1-70b": 0.20,
    "gemini-1.5-flash": 0.25,
}

SYSTEM_PROMPT = (
    "You are a helpful assistant embedded in a customer support and "
    "developer tools product. Answer concisely and use tools when needed."
)

# Probability that a non-retry turn after the first continues the current
# topic via its next follow-up exchange (when one is available) instead of
# jumping to a brand new topic.
FOLLOW_UP_PROBABILITY = 0.5


def now_iso(offset_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


def pick_model() -> Model:
    return random.choices(MODELS, weights=[MODEL_WEIGHTS[m] for m in MODELS], k=1)[0]


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()) * 4 // 3)


def cost_for(model: Model, tokens_prompt: int, tokens_completion: int) -> float:
    pricing = MODEL_PRICING_PER_1K[model]
    return round(
        (tokens_prompt / 1000) * pricing["prompt"]
        + (tokens_completion / 1000) * pricing["completion"],
        6,
    )


def latency_for(model: Model) -> int:
    base = MODEL_LATENCY_MS[model]
    return max(80, int(random.gauss(base, base * 0.25)))


def pick_topic(pool: list[Topic], exclude_id: str | None = None) -> Topic:
    candidates = [t for t in pool if t.id != exclude_id] or pool
    return random.choice(candidates)


def pick_question(exchange: Exchange, used: set[str]) -> str:
    available = [q for q in exchange.questions if q not in used] or list(exchange.questions)
    question = random.choice(available)
    used.add(question)
    return question


def pick_answer(pool: list[str], exclude: str | None = None) -> str:
    candidates = [a for a in pool if a != exclude] or pool
    return random.choice(candidates)


def truncated_text(answer: str) -> str:
    """Simulate a cut-off response as a prefix of a real, on-topic answer
    rather than an unrelated canned sentence, so truncated traces still
    share vocabulary with their own question."""
    words = answer.split()
    cut = max(3, min(len(words) - 1, random.randint(6, 14))) if len(words) > 3 else len(words)
    return " ".join(words[:cut])


def build_trace(
    session_id: str,
    turn_index: int,
    transcript: list[dict],
    *,
    exchange: Exchange,
    agentic: bool,
    model: Model | None = None,
    force_status: int | None = None,
    force_finish: str | None = None,
    response_kind: str = "normal",  # "normal" | "alt" | "error" | "truncated"
    exclude_answer: str | None = None,
    feedback: str | None = None,
    is_retrial: bool = False,
    retrial_of: str | None = None,
    seconds_offset: int = 0,
) -> dict:
    model = model or pick_model()
    trace_id = str(uuid.uuid4())

    tool_calls = None
    finish_reason = force_finish or "stop"
    status_code = force_status or 200

    use_tool = agentic and exchange.tool is not None
    tool_error = response_kind == "error"

    if use_tool:
        tool_status = 500 if tool_error else 200
        tool_result = {
            "status_code": tool_status,
            "output": exchange.tool.error_output if tool_error else exchange.tool.success_output,
        }
        tool_calls = [{"name": exchange.tool.name, "args": exchange.tool.args, "result": tool_result}]
        finish_reason = force_finish or "tool_calls"
        status_code = force_status or (502 if tool_error else 200)

    if response_kind == "truncated":
        base = pick_answer(exchange.answers, exclude=exclude_answer)
        response_text = truncated_text(base)
        finish_reason = "length"
        status_code = force_status or 200
    elif response_kind == "error":
        error_pool = exchange.error_answers or exchange.answers
        response_text = pick_answer(error_pool, exclude=exclude_answer)
        if not use_tool:
            finish_reason = force_finish or "stop"
            status_code = force_status or 502
    else:
        # "normal" and "alt" both draw from the exchange's own answer pool;
        # "alt" excludes whichever answer a sibling trace at this same turn
        # already used, so accepted/rejected and retry pairs don't end up
        # byte-identical.
        response_text = pick_answer(exchange.answers, exclude=exclude_answer)

    response = {"role": "assistant", "content": response_text}
    messages = transcript  # full transcript INCLUDING the new user turn, per spec

    tokens_prompt = sum(estimate_tokens(m["content"]) for m in messages)
    tokens_completion = estimate_tokens(response_text)

    trace = {
        "trace_id": trace_id,
        "session_id": session_id,
        "turn_index": turn_index,
        "timestamp": now_iso(seconds_offset),
        "model": model,
        "messages": messages,
        "response": response,
        "tool_calls": tool_calls,
        "finish_reason": finish_reason,
        "status_code": status_code,
        "tokens_prompt": tokens_prompt,
        "tokens_completion": tokens_completion,
        "cost_usd": cost_for(model, tokens_prompt, tokens_completion),
        "latency_ms": latency_for(model),
        "feedback": feedback,
        "is_retrial": is_retrial,
        "retrial_of": retrial_of,
        "continuation_status": None,
    }
    return trace


def generate() -> list[dict]:
    traces: list[dict] = []
    num_sessions = random.randint(115, 140)
    t_offset = 0

    for s in range(num_sessions):
        session_id = str(uuid.uuid4())
        is_agentic_session = random.random() < 0.30
        pool = AGENTIC_TOPICS if is_agentic_session else NON_AGENTIC_TOPICS

        # ~30%+ of sessions get 3+ turns.
        roll = random.random()
        if roll < 0.35:
            num_turns = random.randint(3, 6)
        elif roll < 0.70:
            num_turns = random.randint(2, 2)
        else:
            num_turns = 1

        will_retry = random.random() < 0.12  # ~10-15% of sessions
        retry_turn = random.randint(0, num_turns - 1) if will_retry else None

        transcript: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

        current_topic: Topic | None = None
        current_exchange_idx = 0
        used_questions: set[str] = set()

        for turn in range(num_turns):
            if turn == 0:
                topic = pick_topic(pool)
                exchange_idx = 0
            else:
                can_follow_up = (
                    current_topic is not None
                    and current_exchange_idx + 1 < len(current_topic.exchanges)
                    and random.random() < FOLLOW_UP_PROBABILITY
                )
                if can_follow_up:
                    topic = current_topic
                    exchange_idx = current_exchange_idx + 1
                else:
                    topic = pick_topic(pool, exclude_id=current_topic.id if current_topic else None)
                    exchange_idx = 0

            current_topic = topic
            current_exchange_idx = exchange_idx
            exchange = topic.exchanges[exchange_idx]

            user_q = pick_question(exchange, used_questions)
            transcript.append({"role": "user", "content": user_q})

            t_offset += random.randint(5, 600)

            tool_error = is_agentic_session and random.random() < 0.30
            truncated = (not tool_error) and random.random() < 0.11

            if turn == retry_turn:
                # First attempt: weak/errored, discarded.
                bad_kind = random.choice(["weak_feedback", "tool_error"])
                first = build_trace(
                    session_id,
                    turn,
                    list(transcript),
                    exchange=exchange,
                    agentic=is_agentic_session and bad_kind == "tool_error",
                    response_kind="error" if bad_kind == "tool_error" else "normal",
                    force_status=502 if bad_kind == "tool_error" else 200,
                    feedback="weak" if bad_kind == "weak_feedback" else None,
                    seconds_offset=t_offset,
                )
                traces.append(first)
                t_offset += random.randint(2, 30)

                # Second attempt: same session/turn_index, better outcome,
                # and a different response than the first attempt used.
                second = build_trace(
                    session_id,
                    turn,
                    list(transcript),
                    exchange=exchange,
                    agentic=is_agentic_session,
                    response_kind="normal",
                    exclude_answer=first["response"]["content"],
                    feedback=random.choice(["ok", "strong"]),
                    is_retrial=True,
                    retrial_of=first["trace_id"],
                    seconds_offset=t_offset,
                )
                traces.append(second)
                assistant_for_transcript = second
            else:
                feedback = None
                if random.random() < 0.18:
                    feedback = random.choices(
                        ["weak", "ok", "strong"], weights=[0.25, 0.45, 0.30]
                    )[0]

                response_kind = "error" if tool_error else ("truncated" if truncated else "normal")
                trace = build_trace(
                    session_id,
                    turn,
                    list(transcript),
                    exchange=exchange,
                    agentic=is_agentic_session,
                    response_kind=response_kind,
                    force_status=502 if tool_error else None,
                    feedback=feedback,
                    seconds_offset=t_offset,
                )
                traces.append(trace)
                assistant_for_transcript = trace

                # Continuation accept/reject for agentic, non-error, non-truncated traces.
                if (
                    is_agentic_session
                    and not tool_error
                    and not truncated
                    and random.random() < 0.15
                ):
                    assistant_for_transcript["continuation_status"] = "accepted"
                    rejected = build_trace(
                        session_id,
                        turn,
                        list(transcript),
                        exchange=exchange,
                        agentic=True,
                        response_kind="alt",
                        exclude_answer=assistant_for_transcript["response"]["content"],
                        feedback=None,
                        model=assistant_for_transcript["model"],
                        seconds_offset=t_offset + 1,
                    )
                    rejected["continuation_status"] = "rejected"
                    traces.append(rejected)

            transcript.append(assistant_for_transcript["response"])

    return traces


def main() -> None:
    traces = generate()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(traces, indent=2))
    sessions = {t["session_id"] for t in traces}
    print(f"Generated {len(traces)} traces across {len(sessions)} sessions -> {OUT_PATH}")


if __name__ == "__main__":
    main()

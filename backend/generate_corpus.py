"""
Synthetic corpus generator for the Riften post-training data platform.

Produces 300-400 Trace rows across ~100-150 sessions, written to
/data/traces.json (an intermediate artifact -- ingest.py loads this into
SQLite). Deliberately messy: retries, tool errors, truncated responses,
mixed models skewed toward cheaper ones, multi-turn sessions that resend
the full transcript each turn, and agentic continuation accept/reject pairs.

Deterministic via a fixed random seed so runs are reproducible.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

TOPICS = [
    ("How do I reset a user's password via the admin API?",
     "Call `POST /admin/users/{{id}}/reset-password` with a valid admin "
     "token. This invalidates existing sessions and emails the user a "
     "reset link."),
    ("Why is my webhook delivery failing with a timeout?",
     "Your endpoint is likely taking longer than the 5s delivery timeout. "
     "Move slow processing to a background job and return a 200 "
     "immediately on receipt."),
    ("What's the difference between the `sync` and `async` client modes?",
     "`sync` blocks until the response is fully received; `async` returns "
     "a future/promise you can await, useful for concurrent requests."),
    ("Can you summarize this changelog entry for release notes?",
     "Added rate-limit headers to all API responses, fixed a race "
     "condition in session refresh, and deprecated the v1 `/search` "
     "endpoint in favor of v2."),
    ("How do I paginate through a large export?",
     "Use the `cursor` field returned in each page's response and pass it "
     "as `?cursor=...` on the next request until the field is null."),
    ("Write a regex to validate US phone numbers.",
     "`^\\(?\\d{3}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}$` matches common US "
     "phone number formats with optional separators."),
    ("Draft a short apology email for a billing overcharge.",
     "Subject: We're sorry about the billing error\\n\\nHi there, we "
     "identified an overcharge on your last invoice and have issued a "
     "full refund, which should post within 3-5 business days."),
    ("Explain exponential backoff in one paragraph.",
     "Exponential backoff retries a failed request with progressively "
     "longer delays (e.g. 1s, 2s, 4s, 8s), often with jitter, to avoid "
     "overwhelming a struggling service."),
    ("What status code should I return for a rate-limited request?",
     "Return `429 Too Many Requests`, ideally with a `Retry-After` header "
     "indicating when the client can try again."),
    ("Convert this CSV row into a JSON object for me.",
     "Given the header row and values, here's the resulting JSON object "
     "with each column mapped to its corresponding field."),
    ("Debug why this SQL query returns duplicate rows.",
     "The join against the `orders` table is one-to-many without "
     "aggregation, so each matching order row duplicates the parent "
     "record. Add a `GROUP BY` or use a window function."),
    ("Help me write a cron expression for every weekday at 9am.",
     "`0 9 * * 1-5` runs at 9:00 AM Monday through Friday."),
]

AGENTIC_TOPICS = [
    ("Look up the current status of order #48213 and refund it if it's "
     "still pending.",
     "lookup_order", {"order_id": "48213"},
     "I checked order #48213 and it's still pending, so I've issued a full refund."),
    ("Check disk usage on the prod-db-2 host and restart the service if "
     "it's above 90%.",
     "check_disk_usage", {"host": "prod-db-2"},
     "Disk usage on prod-db-2 is at 94%, so I restarted the service and cleared temp logs."),
    ("Find the customer record for jane@example.com and update their plan "
     "to Pro.",
     "lookup_customer", {"email": "jane@example.com"},
     "Found the customer record and upgraded jane@example.com to the Pro plan."),
    ("Search recent deploys for the payments service and tell me if the "
     "last one succeeded.",
     "search_deploys", {"service": "payments"},
     "The last deploy for the payments service completed successfully 2 hours ago."),
    ("Pull the latest error logs for the ingestion worker and summarize "
     "the top issue.",
     "fetch_logs", {"service": "ingestion-worker"},
     "The top recurring error is a connection timeout to the upstream queue, "
     "occurring roughly every 10 minutes."),
]

TRUNCATION_CUTS = [
    "Here's how you can approach this: first, you'll want to check the",
    "The root cause is most likely related to a race condition between the",
    "Sure, here's a draft: \"Thank you for reaching out regarding your",
    "To fix this, update the configuration file so that the timeout value",
]


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


def build_trace(
    session_id: str,
    turn_index: int,
    transcript: list[dict],
    *,
    model: Model | None = None,
    force_status: int | None = None,
    force_finish: str | None = None,
    tool_error: bool = False,
    truncated: bool = False,
    agentic: bool = False,
    feedback: str | None = None,
    is_retrial: bool = False,
    retrial_of: str | None = None,
    seconds_offset: int = 0,
) -> dict:
    model = model or pick_model()
    trace_id = str(uuid.uuid4())

    tool_calls = None
    finish_reason = force_finish or "stop"
    response_text = None
    status_code = force_status or 200
    continuation_status = None

    if agentic:
        _, tool_name, tool_args, resolution = random.choice(AGENTIC_TOPICS)
        tool_status = 500 if tool_error else 200
        tool_result = (
            {"status_code": tool_status, "output": "internal error: upstream unavailable"}
            if tool_error
            else {"status_code": 200, "output": "ok"}
        )
        tool_calls = [{"name": tool_name, "args": tool_args, "result": tool_result}]
        if tool_error:
            finish_reason = force_finish or "tool_calls"
            status_code = force_status or 502
            response_text = "I attempted the requested action but the tool call failed."
        else:
            finish_reason = force_finish or "tool_calls"
            response_text = resolution

    if truncated:
        finish_reason = "length"
        response_text = random.choice(TRUNCATION_CUTS)
        status_code = force_status or 200

    if response_text is None:
        _, canned = TOPICS[hash((session_id, turn_index)) % len(TOPICS)]
        response_text = canned

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
        "continuation_status": continuation_status,
    }
    return trace


def generate() -> list[dict]:
    traces: list[dict] = []
    num_sessions = random.randint(115, 140)
    t_offset = 0

    for s in range(num_sessions):
        session_id = str(uuid.uuid4())
        is_agentic_session = random.random() < 0.30
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

        for turn in range(num_turns):
            if is_agentic_session:
                user_q, *_ = random.choice(AGENTIC_TOPICS)
            else:
                user_q, _ = random.choice(TOPICS)
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
                    agentic=is_agentic_session and bad_kind == "tool_error",
                    tool_error=(bad_kind == "tool_error"),
                    force_status=502 if bad_kind == "tool_error" else 200,
                    feedback="weak" if bad_kind == "weak_feedback" else None,
                    seconds_offset=t_offset,
                )
                traces.append(first)
                t_offset += random.randint(2, 30)

                # Second attempt: same session/turn_index, better outcome.
                second = build_trace(
                    session_id,
                    turn,
                    list(transcript),
                    agentic=is_agentic_session,
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

                trace = build_trace(
                    session_id,
                    turn,
                    list(transcript),
                    agentic=is_agentic_session,
                    tool_error=tool_error,
                    truncated=truncated,
                    force_status=502 if tool_error else 200,
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
                        agentic=True,
                        feedback=None,
                        seconds_offset=t_offset + 1,
                    )
                    rejected["continuation_status"] = "rejected"
                    rejected["model"] = assistant_for_transcript["model"]
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

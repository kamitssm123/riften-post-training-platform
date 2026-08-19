"""
Loads /data/traces.json (produced by generate_corpus.py) into the SQLite
database at /data/traces.db. Idempotent: wipes and reloads the `traces`
table so repeated dev runs stay in sync with the generator output.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.schema import CREATE_TABLE_SQL

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DATA_DIR / "traces.db"
TRACES_JSON_PATH = DATA_DIR / "traces.json"

COLUMNS = [
    "trace_id",
    "session_id",
    "turn_index",
    "timestamp",
    "model",
    "messages",
    "response",
    "tool_calls",
    "finish_reason",
    "status_code",
    "tokens_prompt",
    "tokens_completion",
    "cost_usd",
    "latency_ms",
    "feedback",
    "is_retrial",
    "retrial_of",
    "continuation_status",
]


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_corpus(traces_path: Path = TRACES_JSON_PATH) -> int:
    """Wipe and reload the traces table from the given JSON file. Returns row count."""
    raw_traces = json.loads(traces_path.read_text())

    conn = get_connection()
    try:
        conn.executescript(CREATE_TABLE_SQL)
        conn.execute("DELETE FROM traces")

        rows = []
        for t in raw_traces:
            rows.append(
                (
                    t["trace_id"],
                    t["session_id"],
                    t["turn_index"],
                    t["timestamp"],
                    t["model"],
                    json.dumps(t["messages"]),
                    json.dumps(t["response"]),
                    json.dumps(t["tool_calls"]) if t["tool_calls"] is not None else None,
                    t["finish_reason"],
                    t["status_code"],
                    t["tokens_prompt"],
                    t["tokens_completion"],
                    t["cost_usd"],
                    t["latency_ms"],
                    t["feedback"],
                    int(bool(t["is_retrial"])),
                    t["retrial_of"],
                    t["continuation_status"],
                )
            )

        placeholders = ", ".join("?" for _ in COLUMNS)
        conn.executemany(
            f"INSERT INTO traces ({', '.join(COLUMNS)}) VALUES ({placeholders})",
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def main() -> None:
    if not TRACES_JSON_PATH.exists():
        raise SystemExit(
            f"{TRACES_JSON_PATH} not found. Run generate_corpus.py first."
        )
    count = load_corpus()
    print(f"Loaded {count} traces into {DB_PATH}")


if __name__ == "__main__":
    main()

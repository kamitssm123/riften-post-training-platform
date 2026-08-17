# Database

Single SQLite file at `/data/traces.db`, one table (`traces`), defined in
`backend/schema.py:97-121` and created by `ingest.py`'s `load_corpus()`.
There is no migration system — the DDL is `CREATE TABLE IF NOT EXISTS`,
applied fresh every time `load_corpus()` runs.

## Table: `traces`

| Column | Type | Nullable | Default | Purpose |
|---|---|---|---|---|
| `trace_id` | `TEXT` | No (`PRIMARY KEY`) | — | UUID identifying this specific call. Primary key; also the join target for `retrial_of`. |
| `session_id` | `TEXT` | No | — | UUID grouping every trace that belongs to the same growing conversation. Not a foreign key to another table (there is no `sessions` table) — a session is purely "the set of rows sharing this value." |
| `turn_index` | `INTEGER` | No | — | 0-indexed position of this call within its session. Two traces can share the same `(session_id, turn_index)` — see "Same-turn branches" below; it is not part of a composite key. |
| `timestamp` | `TEXT` | No | — | ISO 8601 string (`datetime.isoformat()` output from Python), stored as text — SQLite has no native datetime type, and nothing in the codebase parses this column back into a date for SQL-side comparisons (ordering uses the string's lexicographic order, which is safe because ISO 8601 sorts correctly as text). |
| `model` | `TEXT` | No | — | One of the five model literals (`gpt-4o`, `gpt-4o-mini`, `claude-3-5-sonnet`, `llama-3.1-70b`, `gemini-1.5-flash`). Not constrained by a `CHECK` — the column accepts any string. |
| `messages` | `TEXT` | No | — | JSON-encoded array of `{role, content}` objects: the full transcript sent for this call (system + every prior turn + the new user turn), matching how a real agent client resends context each turn. |
| `response` | `TEXT` | No | — | JSON-encoded single `{role: "assistant", content}` object: what the model returned for this call. Stored separately from `messages` rather than appended to it — the SFT exporter reassembles `messages + [response]` at export time (`export_sft.py:120`). |
| `tool_calls` | `TEXT` | Yes | — (SQLite implicit `NULL`) | JSON-encoded array of `{name, args, result: {status_code, output}}` objects, or SQL `NULL` if the call made no tool calls. `NULL` (not `"[]"` or `"null"` string) is how the generator, ingest, and the API's `errored` filter all agree a trace is tool-call-free. |
| `finish_reason` | `TEXT` | No | — | One of `stop`, `length`, `tool_calls`, `content_filter`. `length` is what the SFT export's truncation filter keys on. |
| `status_code` | `TEXT` — wait, see note below | No | — | Simulated HTTP-style status for the call as a whole. **Declared as `INTEGER NOT NULL`** in the DDL (schema.py:108) — corrected below. |
| `tokens_prompt` | `INTEGER` | No | — | Estimated prompt token count (word-count-based estimate, not a real tokenizer — see `docs/06-dataset.md`). |
| `tokens_completion` | `INTEGER` | No | — | Estimated completion token count, same estimation method. |
| `cost_usd` | `REAL` | No | — | `tokens_prompt/1000 * prompt_rate + tokens_completion/1000 * completion_rate`, rounded to 6 decimals, using the per-model rates in `schema.py:25-31`. |
| `latency_ms` | `INTEGER` | No | — | Simulated call latency: a Gaussian draw around the model's configured mean (`schema.py:34-40`), floored at 80ms. |
| `feedback` | `TEXT` | Yes | `NULL` | One of `weak`, `ok`, `strong`, or `NULL` if no feedback was recorded for this trace. |
| `is_retrial` | `INTEGER` | No | `0` | SQLite has no boolean type; stored as `0`/`1`, cast to Python `bool` on read by `Trace.from_row` (schema.py:93) and to `int(bool(...))` on write by `ingest.py:75`. |
| `retrial_of` | `TEXT` | Yes | `NULL` | `trace_id` of the attempt this trace replaced, or `NULL` if this trace isn't a retrial. Not declared as a SQL foreign key (no `REFERENCES traces(trace_id)`) even though it always points at another row in the same table in practice — referential integrity here is enforced by the generator's construction, not by the schema. |
| `continuation_status` | `TEXT` | Yes | `NULL` | One of `accepted`, `rejected`, or `NULL`. Only ever set on agentic-session traces that proposed a next action; `NULL` for everything else. |

**Correction on `status_code`'s type**: the DDL (schema.py:108) declares it
`INTEGER NOT NULL`, not `TEXT` — every row always has a concrete simulated
status (`schema.py`'s dataclass field has no default and every call to
`build_trace` in the generator resolves one via `force_status or 200`).

## Indexes

```sql
CREATE INDEX idx_traces_session     ON traces(session_id);
CREATE INDEX idx_traces_model       ON traces(model);
CREATE INDEX idx_traces_feedback    ON traces(feedback);
CREATE INDEX idx_traces_retrial_of  ON traces(retrial_of);
```

(`schema.py:118-121`.) These four cover the columns every API filter and
every export's grouping/lookup actually touches: `session_id` (session view,
session-grouping in both exports), `model` (the model filter), `feedback`
(the feedback filter and the preference exporter's weak-rating scan),
`retrial_of` (the preference exporter's retrial-pairing lookup and the SFT
exporter's `is_retrial_loser` scan in `row_level_exclusion_reason`).

**Gap**: `turn_index` has no index, despite being one of the three columns
this doc calls out as load-bearing for the hardest logic in the project.
Every query that needs it — `GET /sessions/{id}`'s `ORDER BY turn_index`,
both exporters' per-session grouping — first filters or groups by
`session_id`, so in practice SQLite is only ever ordering/scanning
`turn_index` values *within* an already-small, already-indexed
`session_id` bucket (max session size in the current corpus is well under
10 rows), which is why the omission doesn't show up as a real performance
problem at this data size. There is also no composite index on
`(session_id, turn_index)`, which would be the more precise choice if this
ever needed to scale past a few hundred rows. `status_code` and
`finish_reason` — the two columns the `truncated`/`errored` filters and both
row-level exclusion rules key on — are unindexed too, for the same reason:
fine at 381 rows, would need revisiting before this ran against real
volume.

## Entity relationships

There is exactly one table, so there's no foreign-key ER diagram in the
usual sense — the relationships are all *within* `traces`, encoded by three
columns referencing each other by value:

```
┌───────────────────────────── traces ─────────────────────────────┐
│                                                                    │
│  session_id ─────┐                                                │
│                   │  groups N rows into one conversation          │
│                   │  (no session-level metadata exists anywhere   │
│                   │   else — the "session" is only ever this      │
│                   │   grouping key)                                │
│                   ▼                                                │
│         ┌── turn_index 0 ──┐  ┌── turn_index 1 ──┐  ┌── turn_index 2 ──┐
│         │ 1 row (normal)    │  │ 1 row (normal)    │  │ 2 rows: a retry pair │
│         └───────────────────┘  └───────────────────┘  │  ┌─────────────┐  │
│                                                        │  │ trace A      │  │
│                                                        │  │ (discarded)  │  │
│                                                        │  └──────┬───────┘  │
│                                                        │         │ retrial_of│
│                                                        │         │ (A.trace_id)│
│                                                        │  ┌──────▼───────┐  │
│                                                        │  │ trace B      │  │
│                                                        │  │ is_retrial=1 │  │
│                                                        │  │ (kept)       │  │
│                                                        │  └──────────────┘  │
│                                                        └─────────────────────┘
└────────────────────────────────────────────────────────────────────┘
```

`retrial_of` is a **self-referential pointer within one `(session_id,
turn_index)` bucket**: it never points across sessions or across turns in
this corpus (nothing in the schema enforces that — it's a property of how
`generate_corpus.py` constructs retrial pairs, `generate_corpus.py:265-293`,
always passing the same `turn` and `session_id` to both `build_trace` calls).
A rejected/accepted continuation pair (`continuation_status`) is the same
shape one level up — two rows sharing `(session_id, turn_index)` — but with
no pointer column between them at all; pairing them back up requires a
`WHERE session_id = ? AND turn_index = ?` scan, which is exactly what
`export_preference.py`'s `by_session_turn` dict (export_preference.py:43-45)
precomputes once for the whole table rather than re-querying per pair.

## Worked example: a 3-turn session with one retry

Real data, session `2eacd229-0d7f-46b8-bc41-bc08faadb478`, pulled directly
from the current `/data/traces.db`. This session has 3 conversational turns
(`turn_index` 0, 1, 2) and one retry at the last turn, so it's represented
by **4 rows**:

| trace_id | turn_index | is_retrial | retrial_of | status_code | feedback | `len(messages)` |
|---|---|---|---|---|---|---|
| `bdb66f8e-cd57-4d4c-ae86-ff88f4f6c7d5` | 0 | 0 | `NULL` | 200 | `NULL` | 2 |
| `61d291b5-9684-4bfc-a8c9-ca3b827182f0` | 1 | 0 | `NULL` | 200 | `NULL` | 4 |
| `158fd41d-ffab-45b6-bd80-4611a2cfde85` | 2 | 0 | `NULL` | **502** | `NULL` | 6 |
| `a70b1e6c-f862-4725-824b-41879ee1d811` | 2 | **1** | `158fd41d-...` | 200 | `ok` | 6 |

Reading this as a conversation:

- **Turn 0** (`bdb66f8e...`): `messages` = `[system, user:"Convert this CSV
  row into a JSON object for me."]` (2 entries). Response: "Your endpoint is
  likely taking longer than the 5s delivery timeout...". Succeeds cleanly.
- **Turn 1** (`61d291b5...`): `messages` now has 4 entries — the same
  system + first user turn, **plus** the turn-0 assistant response, **plus**
  the new user turn ("Debug why this SQL query returns duplicate rows.").
  This is the "agent clients resend the whole transcript" behavior the spec
  calls out: turn 1's `messages` array is a strict superset of turn 0's.
- **Turn 2, first attempt** (`158fd41d...`): `messages` grows to 6 entries
  (turns 0-1 fully resent plus the new user question, "Why is my webhook
  delivery failing with a timeout?"). This attempt gets `status_code = 502`
  — a failed call — so it's discarded.
- **Turn 2, retrial** (`a70b1e6c...`): a **new row**, `retrial_of` pointing
  back at `158fd41d...`'s `trace_id`, `is_retrial = 1`, same `session_id`
  and `turn_index = 2`, and — because `generate_corpus.py`'s
  `list(transcript)` snapshot at the point of retry is identical for both
  attempts (`generate_corpus.py:271` and `:285` both copy the same
  `transcript` list before either attempt's response is appended) — **an
  identical 6-entry `messages` array** to the discarded attempt. Only the
  outcome differs: `status_code = 200`, `feedback = "ok"`.

Because both turn-2 attempts share the same `(session_id, turn_index)`, the
SFT exporter's "keep the highest turn_index" rule alone can't tell them
apart by transcript length — both attempts show `turn_index = 2`. This is
exactly the tie-break case documented in `export_sft.py`'s
`select_session_representative` and worked through in full in
`docs/07-exports.md`: it keeps `a70b1e6c...` (the retrial winner) and marks
the other three rows (`bdb66f8e...`, `61d291b5...`, `158fd41d...`) as
`superseded_by_longer_session_trace`.

A subtler consequence, visible in this same example: `158fd41d...` (the
discarded attempt) and `a70b1e6c...` (the winning retrial) have **the exact
same response text**, "Return `429 Too Many Requests`, ideally with a
`Retry-After` header...". This isn't a bug in the retry logic — it's the
canned-response selection in `build_trace()` keying on `hash((session_id,
turn_index))` (generate_corpus.py:199) rather than on the attempt's
`trace_id`, so any two traces sharing a `(session_id, turn_index)` get the
same canned text regardless of how many attempts happened. See
`docs/08-known-gaps.md`.

## Sample rows

Pulled live from `/data/traces.db` (`python3 -c "import sqlite3; ..."`
against the real file — not invented). `messages` is truncated to its
first entry's role for brevity here; full JSON is in the actual DB.

**Vanilla trace** (`stop`, 200, no tool calls, not a retrial, no
continuation):
```
trace_id:          7f1ae2f4-9529-4dec-a8b3-c39b749e77fd
session_id:         2dea996b-91d1-46ee-bf3d-53a5fdac3ad0
turn_index:         0
model:              llama-3.1-70b
finish_reason:       stop
status_code:         200
tokens_prompt:       36
tokens_completion:    25
cost_usd:            0.000055
latency_ms:          1471
feedback:            strong
response.content:    "Given the header row and values, here's the resulting
                       JSON object with each column mapped to its
                       corresponding field."
```

**Truncated trace** (`finish_reason = length`, response visibly cut off):
```
trace_id:          04d76f7b-9fc8-4d17-bc87-d646dbb9a00b
session_id:         40ed96f6-34fc-4b01-8a6e-c898f7de190a
turn_index:         0
model:              llama-3.1-70b
finish_reason:       length
status_code:         200
tokens_prompt:       42
tokens_completion:    17
cost_usd:            0.000053
latency_ms:          672
feedback:            NULL
response.content:    "The root cause is most likely related to a race
                       condition between the"     ← cut mid-sentence
```

**Tool-error trace** (`tool_calls` present with a 5xx result, outer
`status_code` also non-2xx):
```
trace_id:          b9e2ff5f-c6f1-4471-a67e-f33d577a5757
session_id:         8b3c718e-374e-48b0-a777-bcea8504619f
turn_index:         4
model:              gpt-4o
finish_reason:       tool_calls
status_code:         502
tokens_prompt:       203
tokens_completion:    13
cost_usd:            0.00121
latency_ms:          2812
feedback:            NULL
tool_calls:          [{"name": "search_deploys",
                        "args": {"service": "payments"},
                        "result": {"status_code": 500,
                                   "output": "internal error: upstream unavailable"}}]
response.content:    "I attempted the requested action but the tool call failed."
```

**Retrial pair** (from a different session than the worked example above,
showing the same shape):
```
original (rejected):
  trace_id:      670369d9-badf-49fc-929d-32eb2eca0d3f
  session_id:     b998bd5f-0675-441b-8cb8-878bb3868801
  turn_index:     3
  status_code:    502
  is_retrial:     0
  retrial_of:     NULL
  feedback:       NULL

replacement (chosen):
  trace_id:      83754fa1-089d-46a6-9b7f-52702afc6eb1
  session_id:     b998bd5f-0675-441b-8cb8-878bb3868801   (same)
  turn_index:     3                                       (same)
  status_code:    200
  is_retrial:     1
  retrial_of:     670369d9-badf-49fc-929d-32eb2eca0d3f    (points at original)
  feedback:       ok
```

**Rejected-continuation pair**:
```
accepted:
  trace_id:            d23afc03-8cd4-4416-86b0-3ab3b22823df
  session_id:           8b3c718e-374e-48b0-a777-bcea8504619f
  turn_index:           3
  continuation_status:  accepted
  tool_calls:           [{"name": "lookup_order", "args": {"order_id": "48213"}, ...}]
  response.content:     "I checked order #48213 and it's still pending, so
                          I've issued a full refund."

rejected:
  trace_id:            85e48579-d63a-4eb4-9b51-d35e5ef7239d
  session_id:           8b3c718e-374e-48b0-a777-bcea8504619f   (same)
  turn_index:           3                                       (same)
  continuation_status:  rejected
  tool_calls:           [{"name": "lookup_customer", "args": {"email": "jane@example.com"}, ...}]
  response.content:     "Found the customer record and upgraded
                          jane@example.com to the Pro plan."
```

Note the accepted/rejected pair here proposes **two different tool calls**
(`lookup_order` vs. `lookup_customer`) — the generator doesn't constrain a
continuation pair to differ only in the response text; it's two
independently-built `build_trace()` calls that happen to share a session and
turn.

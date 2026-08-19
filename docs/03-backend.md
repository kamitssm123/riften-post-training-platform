# Backend

All paths relative to `/backend`. Files are covered in the order you'd read
them to understand the system: schema → ingest → generator → API → exports →
tests.

## `schema.py`

**Purpose**: single source of truth for the trace shape. Every other backend
module imports from here instead of redefining fields.

| Reads | Writes |
|---|---|
| nothing | nothing (pure definitions) |

Contents:

- `Model`, `FinishReason`, `Feedback`, `ContinuationStatus` (lines 11-21) —
  `typing.Literal` unions used as type hints only; SQLite stores these as
  plain `TEXT`, nothing in the schema enforces the literal set at the
  database level.
- `MODEL_PRICING_PER_1K` (lines 25-31) and `MODEL_LATENCY_MS` (lines 34-40)
  — per-model $/1K-token prompt/completion rates and mean latency in ms,
  used only by `generate_corpus.py` to compute `cost_usd` and `latency_ms`.
  Explicitly commented as "not real provider pricing."
- `ToolCall` and `Message` (lines 43-53) — `@dataclass` definitions that
  exist for documentation/typing purposes; nothing in the codebase actually
  constructs `ToolCall(...)` or `Message(...)` instances — the generator and
  API both work with plain dicts shaped like these classes.
- `Trace` (lines 56-94) — the dataclass matching every trace field. Two
  methods:
  - `to_row(self)` (lines 77-84) — flattens a `Trace` instance to a dict
    with `messages`/`response`/`tool_calls` JSON-encoded as strings and
    `is_retrial` cast to `int`. **Not actually called anywhere in the
    codebase** — `ingest.py` builds its insert tuples manually
    (ingest.py:58-79) rather than constructing `Trace` objects and calling
    `to_row()`. This method is dead code as of the current implementation.
  - `Trace.from_row(row)` (lines 86-94, `@staticmethod`) — the inverse:
    takes a `dict` (from `sqlite3.Row`), JSON-decodes the three TEXT
    columns back into nested structures, and casts `is_retrial` to `bool`.
    This one **is** used, by `main.py` (`get_trace`, `get_session`) and by
    `export_sft.py`'s `fetch_all_traces()`.
- `CREATE_TABLE_SQL` (lines 97-121) — the DDL for the `traces` table and its
  four indexes. See `docs/05-database.md` for the full column-by-column
  breakdown.

## `ingest.py`

**Purpose**: load `/data/traces.json` into the SQLite `traces` table,
destructively and idempotently.

| Reads | Writes |
|---|---|
| `/data/traces.json` | `/data/traces.db` (creates file if absent; wipes and reloads the `traces` table) |

- `get_connection()` (lines 40-44) — `DATA_DIR.mkdir(parents=True,
  exist_ok=True)` then `sqlite3.connect(DB_PATH)` with `row_factory =
  sqlite3.Row` so query results are dict-like. Called by `ingest.py` itself
  and imported directly by `export_sft.py` (`from ingest import
  get_connection`) — the exports do not go through `main.py` at all.
- `load_corpus(traces_path=TRACES_JSON_PATH)` (lines 47-89) — the function
  the task spec calls out by name. Steps: parse the JSON file: run
  `CREATE_TABLE_SQL` (idempotent `CREATE TABLE IF NOT EXISTS`); `DELETE FROM
  traces` (the actual wipe); build one tuple per trace in the fixed
  `COLUMNS` order (lines 18-37); `executemany` insert; `commit()`. Returns
  the row count. Every test fixture in the four `test_*.py` files calls this
  function directly (via a monkeypatched `DB_PATH`) rather than going
  through a running server.
- `main()` (lines 92-98) — CLI entry point. Checks `TRACES_JSON_PATH.exists()`
  and raises `SystemExit` with a message pointing at `generate_corpus.py` if
  not; otherwise calls `load_corpus()` and prints the row count.

## `generate_corpus.py`

**Purpose**: produce the synthetic trace corpus as a JSON file. Full
parameter and messiness breakdown lives in `docs/06-dataset.md` — this
section covers structure only.

| Reads | Writes |
|---|---|
| nothing (all content is hardcoded in-file: `TOPICS`, `AGENTIC_TOPICS`, `TRUNCATION_CUTS`, `SYSTEM_PROMPT`) | `/data/traces.json` |

- `now_iso(offset_seconds=0)` (line 125) — wall-clock timestamp plus an
  offset, used to give traces within a session monotonically increasing
  timestamps.
- `pick_model()` (line 129) — weighted random choice over `MODELS` using
  `MODEL_WEIGHTS`.
- `estimate_tokens(text)` (line 133) — `len(text.split()) * 4 // 3`, a crude
  word-count-based token estimate (not a real tokenizer).
- `cost_for(model, tokens_prompt, tokens_completion)` (line 137) — looks up
  `MODEL_PRICING_PER_1K[model]` and computes cost, rounded to 6 decimals.
- `latency_for(model)` (line 146) — `max(80, gauss(mean, mean*0.25))`,
  i.e. a noisy draw around each model's configured mean latency, floored at
  80ms.
- `build_trace(session_id, turn_index, transcript, **flags)` (lines
  151-228) — constructs one trace dict. Takes the *already-appended*
  `transcript` (system + all prior turns + the new user turn) and:
  - if `agentic=True`, picks a random `AGENTIC_TOPICS` tuple, builds a
    single `tool_calls` entry, and sets `finish_reason="tool_calls"`; if
    `tool_error=True` the tool result gets `status_code=500` and the outer
    trace gets `status_code=502` (or `force_status` if given) — **note**:
    `tool_error` and `force_status` are independent parameters, so a caller
    can set `tool_error=True` while `agentic=False`, in which case the
    `if agentic:` block (line 176) never runs and no `tool_calls` are
    attached at all — only the forced `status_code` takes effect. This
    happens in practice; see `docs/08-known-gaps.md`.
  - if `truncated=True`, overrides `finish_reason="length"` and picks a
    response from `TRUNCATION_CUTS` — deliberately mid-sentence.
  - otherwise, falls back to a deterministic canned response:
    `TOPICS[hash((session_id, turn_index)) % len(TOPICS)][1]` (line 199) —
    **the same `(session_id, turn_index)` pair always maps to the same
    canned response text, regardless of which trace_id or which attempt
    (original vs. retrial) is asking**. This is why a retrial pair's
    `chosen` and `rejected` text can be byte-identical in the exported
    preference data (see `docs/07-exports.md` and `docs/08-known-gaps.md`).
  - computes `tokens_prompt` as the sum of `estimate_tokens` over every
    message in `messages` (i.e. the full resent transcript, not just the
    new turn) and `tokens_completion` from the response text alone.
- `generate()` (lines 231-337) — the main loop:
  - `num_sessions = random.randint(115, 140)` (line 233).
  - Per session: `is_agentic_session` at 30% (line 238); turn count via a
    3-way roll (lines 240-246) — 35% chance of 3-6 turns, next 35% chance
    (`0.35 <= roll < 0.70`) of exactly 2 turns, remaining 30% chance of 1
    turn; `will_retry` at 12% of sessions (line 248), with the retry turn
    chosen uniformly among the session's turns (line 249).
  - Per turn: picks a user question from `AGENTIC_TOPICS` or `TOPICS`
    depending on the session type, appends it to `transcript`, then rolls
    `tool_error` (30%, agentic sessions only, line 262) and `truncated`
    (11%, only if not already a tool error, line 263).
  - If this turn is the session's designated retry turn (line 265): builds
    a "bad" first attempt — either `feedback="weak"` or a tool-error trace,
    chosen 50/50 (line 267) — then a second trace with `is_retrial=True`,
    `retrial_of=<first trace_id>`, same `session_id`/`turn_index`, and
    `feedback` randomly `"ok"` or `"strong"` (lines 268-292). Only the
    second (winning) trace's response gets appended to `transcript` for
    subsequent turns (line 335, via `assistant_for_transcript`).
  - Otherwise: builds one normal trace, with an 18% independent chance of a
    `feedback` value weighted `weak:0.25, ok:0.45, strong:0.30` (lines
    295-299). If the session is agentic and this trace is neither a tool
    error nor truncated, there's a further 15% chance of spawning a
    continuation pair (lines 316-333): the just-built trace gets
    `continuation_status="accepted"` mutated in place, and a second trace
    is built at the same `session_id`/`turn_index` with
    `continuation_status="rejected"`, forced to the same `model` as the
    accepted one (line 332) — but **not** appended to `transcript`, so a
    rejected continuation never becomes part of any later turn's resent
    context.
- `main()` (lines 340-345) — calls `generate()`, writes indented JSON to
  `OUT_PATH`, prints a summary line with total trace and session counts.

## `main.py`

**Purpose**: the FastAPI app. Read-only trace/session/stats endpoints plus
thin wrappers around the three export functions.

| Reads | Writes |
|---|---|
| `/data/traces.db` (via `get_connection()`, main.py:35-38 — a module-local copy of the same pattern as `ingest.py`, not imported from it) | `/data/exports/*` indirectly, via the imported `build_sft_export`/`build_preference_export`/`build_exclusion_report` |

CORS is wide open: `allow_origins=["*"]`, `allow_methods=["*"]`,
`allow_headers=["*"]` (lines 27-32) — fine for a local synthetic-data demo,
not something to carry into a deployment with real traffic.

### `build_filter_clause(...)` (lines 41-104)

Not a route — a shared helper that both `list_traces` and `get_stats` call
to build an identical `WHERE` clause + parameter list from the same set of
filter arguments, which is how the UI's live result count stays in sync
with the table (`docs/02-workflow.md`'s first sequence diagram). Per filter:

| Filter | SQL produced |
|---|---|
| `model: list[str]` | `model IN (?, ?, ...)` |
| `min_cost` / `max_cost` | `cost_usd >= ?` / `cost_usd <= ?` |
| `min_latency` / `max_latency` | `latency_ms >= ?` / `latency_ms <= ?` |
| `feedback: list[str]` | `feedback IN (?, ?, ...)` |
| `truncated: bool` | `True` → `finish_reason = 'length'`; `False` → `finish_reason != 'length'`; `None` → no clause |
| `errored: bool` | see below |
| `session_id: str` | `session_id = ?` |

`errored=True` (lines 84-90) produces:
```sql
(status_code >= 400 OR
 (tool_calls IS NOT NULL AND
  EXISTS (SELECT 1 FROM json_each(tool_calls) je
          WHERE json_extract(je.value, '$.result.status_code') >= 400)))
```
using SQLite's JSON1 `json_each`/`json_extract` to reach inside the
`tool_calls` TEXT column without a join table. `errored=False` is the
logical negation, not just the absence of the clause.

### `GET /traces` — `list_traces` (lines 107-174)

| Param | Type | Notes |
|---|---|---|
| `model` | `list[str] \| None` | repeatable query param |
| `min_cost`, `max_cost` | `float \| None` | |
| `min_latency`, `max_latency` | `int \| None` | |
| `feedback` | `list[str] \| None` | repeatable |
| `truncated`, `errored` | `bool \| None` | |
| `session_id` | `str \| None` | |
| `page` | `int`, default 1, `ge=1` | |
| `page_size` | `int`, default 25, `ge=1, le=200` | note: the frontend always passes 30 (`PAGE_SIZE` in `App.tsx`), not the default |

Response: `{items: TraceSummary[], total: int, page: int, page_size: int}`.
Each item is a trimmed row — `SELECT` explicitly lists 15 columns plus
`tool_calls` (lines 140-144) — with `tool_calls` itself dropped from the
final payload after being used to compute a `has_tool_error: bool` field
(lines 157-164, JSON-decoded in Python rather than in SQL for this
particular endpoint). No `messages`/`response` body is returned by this
route — that's `GET /traces/{trace_id}` only. Ordered by `timestamp ASC`
(line 147) unconditionally; there is no sort parameter. Only status code
returned is 200 (no validation errors possible beyond FastAPI's own
422 on malformed query params).

### `GET /traces/{trace_id}` — `get_trace` (lines 177-186)

No params beyond the path segment. `SELECT * WHERE trace_id = ?`; 404 with
`{"detail": "trace not found"}` if no row; otherwise the full
`Trace.from_row(dict(row))` dict, which includes `messages`, `response`,
`tool_calls` and every scalar field.

### `GET /sessions/{session_id}` — `get_session` (lines 189-204)

`SELECT * WHERE session_id = ? ORDER BY turn_index ASC, timestamp ASC`; 404
if the session has no rows; otherwise `{session_id, traces: TraceDetail[]}`
with every trace in the session (not just the longest) fully inflated via
`Trace.from_row`.

### `GET /stats` — `get_stats` (lines 207-285)

Same filter params as `list_traces` (no `page`/`page_size`). Runs four
separate queries against the same filtered base: a total count, a
`per_model` GROUP BY, a `per_feedback` GROUP BY (feedback `NULL` is
relabeled `"none"` in the response, line 278), then two **more**
`build_filter_clause` calls with `errored`/`truncated` forced to `True`
respectively (lines 245-273) to get error/truncation counts and rates
*within the currently-applied filter set* — this is why toggling "Truncated
only" in the UI still shows a sensible `truncated_rate` rather than always
reading `1.0`. Response:
```json
{"total": int, "per_model": {...}, "per_feedback": {...},
 "error_count": int, "error_rate": float, "truncated_count": int, "truncated_rate": float}
```

### `POST /export/sft` (line 288-290), `POST /export/preference` (293-295), `GET /export/exclusions` (298-300)

Each is a one-line wrapper: no request body, no params, calls the
corresponding `build_*` function from the export modules and returns its
dict as-is. See `docs/07-exports.md` for the full response shape of each.

## `exclusion_rules.py`

**Purpose**: single source of truth for the SFT and preference-pair
exclusion rules, extracted out of `export_sft.py`/`export_preference.py` so
`GET /traces/{trace_id}/export-preview` can compute the exact same fate for
one trace that a real export run would give it, without a second
implementation. Pure functions, no I/O.

| Reads | Writes |
|---|---|
| nothing (operates on an in-memory `list[dict]` of already-fetched traces) | nothing |

- `select_session_representative(session_traces)` and
  `row_level_exclusion_reason(trace, all_traces_by_id)` — moved here
  verbatim from `export_sft.py`; behavior unchanged. Full algorithm
  walkthrough in `docs/07-exports.md`.
- `retrial_winner_of(trace_id, all_traces_by_id)` — new helper, finds the
  trace (if any) whose `retrial_of` points back at `trace_id`; used so the
  preview can name *which* retrial superseded a given trace, not just that
  one did.
- `compute_sft_plan(traces)` — runs the full session-collapse +
  row-level-exclusion algorithm once and returns `kept_rows`,
  `excluded_by_reason` (same shape `build_sft_export()` has always
  returned), `total_sessions`, and a `per_trace` map (`trace_id ->
  {included, reason, superseded_by_trace_id}`) giving every trace's SFT
  fate. `export_sft.py` uses `kept_rows`/`excluded_by_reason` to write
  `sft.jsonl`; `export_preview.py` reads `per_trace`.
- `make_preference_pair(chosen, rejected, source)` — moved here verbatim
  from `export_preference.py`'s `make_pair`; `export_preference.py` keeps a
  `make_pair = make_preference_pair` alias for backward compatibility.
- `compute_preference_plan(traces)` — runs the full three-pass pairing
  algorithm once and returns `pairs`, `excluded_by_reason`,
  `pairs_by_source`, and a `per_trace` map (`trace_id -> {eligible, role,
  source, paired_with_trace_id}` for a trace that was chosen or rejected on
  some pair; `{eligible: False, ..., exclusion_reason: "no_pairing_candidate"}`
  for a weak/rejected-continuation trace that found no partner; absent
  entirely for a trace never considered on either side of a pair).

## `export_sft.py`

Covered in full step-by-step detail with worked examples in
`docs/07-exports.md`. Summary:

| Reads | Writes |
|---|---|
| `/data/traces.db` (via `ingest.get_connection`) | `/data/exports/sft.jsonl` |

- `fetch_all_traces()` — `SELECT * FROM traces`, no filter, inflated via
  `Trace.from_row`. Also imported by `export_preference.py` and
  `main.py` (for the export-preview route).
- `select_session_representative` / `row_level_exclusion_reason` are
  re-exported from `exclusion_rules.py` (see above) for any code that
  imported them from `export_sft` before the refactor.
- `build_sft_export()` — calls `exclusion_rules.compute_sft_plan(traces)`,
  writes `kept_rows` to `sft.jsonl`, returns the summary dict consumed by
  `main.py` and `exclusion_report.py`. The write-to-file step is the only
  thing left in this module; the exclusion logic itself now lives in
  `exclusion_rules.py`.
- `main()` — CLI entry point, prints a one-line summary plus one line per
  exclusion reason.

## `export_preference.py`

| Reads | Writes |
|---|---|
| `/data/traces.db` (via `export_sft.fetch_all_traces`) | `/data/exports/preference.jsonl` |

- `make_pair` — alias for `exclusion_rules.make_preference_pair`.
- `build_preference_export()` — calls
  `exclusion_rules.compute_preference_plan(traces)`, writes `pairs` to
  `preference.jsonl`, returns the summary dict. As with `export_sft.py`,
  the three-pass pairing algorithm itself now lives in `exclusion_rules.py`;
  this module only handles fetching and writing. Full algorithm walkthrough
  in `docs/07-exports.md`.
- `main()` — CLI entry point.

## `export_preview.py`

**Purpose**: backs `GET /traces/{trace_id}/export-preview`. Runs
`exclusion_rules.compute_sft_plan()` and `compute_preference_plan()` over
the *entire* corpus (same as a real export would), then reads off the one
requested trace's entry from each plan's `per_trace` map — so the preview
can never diverge from what an actual `POST /export/sft` /
`POST /export/preference` run would do to that trace, and adding this
endpoint doesn't change either `.jsonl` output.

| Reads | Writes |
|---|---|
| nothing (operates on the `list[dict]` passed in by the caller) | nothing |

- `SFT_REASON_DETAIL` — a `{reason: (trace, plan_entry) -> str}` map of
  human-readable detail strings, one per SFT exclusion reason. The
  `superseded_by_retrial` and `superseded_by_longer_session_trace` entries
  name the specific trace that superseded this one, using
  `plan_entry["superseded_by_trace_id"]`.
- `build_sft_preview(trace_id, all_traces)` / `build_preference_preview(trace_id,
  all_traces)` — look up `trace_id` in the corresponding plan's `per_trace`
  map and shape the response.
- `build_export_preview(trace_id, all_traces)` — combines both into
  `{"sft": {...}, "preference": {...}}`, the full response body for the
  route. See `docs/07-exports.md` for the JSON shape.

## `model_tradeoff.py`

**Purpose**: backs `GET /stats/model-tradeoff` — average cost vs. average
quality per model, the one analysis that validates Riften's cost-aware
routing pitch using this project's own trace data.

| Reads | Writes |
|---|---|
| `/data/traces.db` (via a connection passed in by the caller) | nothing |

- `QUALITY_SCORE_SQL` — a SQL `CASE feedback WHEN 'weak' THEN 0.0 WHEN 'ok'
  THEN 0.5 WHEN 'strong' THEN 1.0 ELSE NULL END` expression; `AVG()` over
  this skips `NULL` rows automatically, which is what makes
  `avg_quality_score` an average over only the traces that carry feedback,
  not over all of a model's traces.
- `MODEL_TRADEOFF_SQL` — one `GROUP BY model` query computing
  `trace_count`, `avg_cost_usd`, `avg_latency_ms`, `avg_tokens_prompt`,
  `avg_tokens_completion`, a `feedback_count` (used to derive
  `feedback_coverage`, not returned itself), `avg_quality_score`,
  `error_rate` (`AVG` of a `status_code NOT IN [200,300)` indicator), and
  `truncation_rate` (`AVG` of a `finish_reason = 'length'` indicator).
- `compute_model_tradeoff(conn)` — runs `MODEL_TRADEOFF_SQL`, derives
  `feedback_coverage = feedback_count / trace_count`, rounds every float
  field, and leaves `avg_quality_score` as `None` (rather than `0.0`) for a
  model with zero feedback coverage — the frontend renders that as "no
  feedback data" rather than a misleadingly low score.

### `GET /stats/model-tradeoff` — `get_model_tradeoff`

No params. Calls `model_tradeoff.compute_model_tradeoff(conn)` and returns
`{"items": ModelTradeoff[]}`, one entry per distinct `model` in the traces
table. See `docs/07-exports.md` for the field-by-field JSON shape.

### `GET /traces/{trace_id}/export-preview` — `get_trace_export_preview`

404s with `{"detail": "trace not found"}` if `trace_id` doesn't exist
(checked with a lightweight `SELECT 1` before doing the full-corpus scan).
Otherwise calls `export_sft.fetch_all_traces()` once and passes the result
to `export_preview.build_export_preview(trace_id, all_traces)`. Read-only —
does not write `sft.jsonl`/`preference.jsonl`/`exclusion_report.md`, unlike
`POST /export/sft`/`POST /export/preference`/`GET /export/exclusions`,
which all rewrite those files as a side effect.

## `exclusion_report.py`

| Reads | Writes |
|---|---|
| `/data/traces.db` (indirectly, by calling `build_sft_export()` and `build_preference_export()`, each of which re-queries the DB) | `/data/exports/sft.jsonl` and `/data/exports/preference.jsonl` (as a side effect of calling those two functions) and `/data/exports/exclusion_report.md` |

- `_reasons_with_samples(excluded_by_reason)` (lines 23-27) — turns
  `{reason: [trace_id, ...]}` into `{reason: {count, sample_trace_ids}}`,
  capping the sample at `SAMPLE_SIZE = 5` (line 20).
- `build_exclusion_report()` (lines 30-55) — calls both export builders,
  wraps their exclusion dicts with sample counts, and asserts
  `total_sft_excluded + kept_count == total_traces_considered` (lines
  37-40) — this assertion is the thing that makes "counts sum correctly" a
  guarantee rather than a hope; if it ever fails the route/script raises
  instead of silently returning a report with a hole in it.
- `render_markdown(report)` (lines 58-97) — builds the Markdown text
  written to `exclusion_report.md`: two `##` sections (SFT export,
  Preference pair export), each with a couple of summary bullet lines and a
  `| Reason | Count | Sample trace_ids |` table.
- `main()` (lines 100-104) — CLI entry point.

## Tests

| File | Lines | What it covers |
|---|---|---|
| `test_main.py` | 202 | 16 tests against a 3-row fixture (`FIXTURE_TRACES`, lines 15-76) loaded through a `TestClient(main.app)` fixture (lines 79-90) that monkeypatches both `ingest.DB_PATH` and `main.DB_PATH` to a `tmp_path` file — every `/traces`, `/traces/{id}`, `/sessions/{id}`, `/stats` filter combination named in the route docstrings gets at least one test. |
| `test_export_sft.py` | 113 | 6 tests: turn-index collapsing, the retrial tiebreak at equal turn_index, each of the 4 row-level exclusion reasons individually, and a metadata-leak check confirming `messages` never contains a `feedback`/other metadata key. |
| `test_export_preference.py` | 140 | 6 tests: retrial pairing, weak-rating pairing when a same-turn candidate exists, weak-rating logged as `no_pairing_candidate` when none exists, continuation-rejected pairing, a same-session-different-turn case proving pairing does *not* cross turn boundaries, and an output-shape check on the written JSONL. |
| `test_exclusion_report.py` | 95 | 3 tests: the sum-to-total invariant on a synthetic 3-trace fixture, presence of both `sft`/`preference` top-level keys, and that `render_markdown` doesn't raise and contains both section headers. |
| `test_model_tradeoff.py` | new | 1 test: `compute_model_tradeoff` against a known 3-trace, 2-model fixture, asserting every aggregate (`avg_cost_usd`, `avg_latency_ms`, `avg_tokens_prompt`/`completion`, `avg_quality_score`, `feedback_coverage`, `error_rate`, `truncation_rate`) by hand-computed expected value, including the no-feedback-data case (`avg_quality_score is None`, `feedback_coverage == 0.0`) for the model with no feedback. |
| `test_export_preview.py` | new | 4 tests against `export_preview.build_export_preview`: the `superseded_by_longer_session_trace` case names the specific superseding trace_id in `detail`; an included trace reports `included: True`; a retrial pair reports the correct `role`/`source`/`paired_with_trace_id` for the rejected side; a trace never considered on either side of a pair reports `eligible: False`. |

All test files define their own local `trace(**overrides)` fixture builder
(or `FIXTURE_TRACES` list) rather than sharing one — there's no
`conftest.py` in this repo, so each test module duplicates a full trace-dict
skeleton with sensible defaults, wired to accept keyword overrides for the
specific fields each test cares about.

## `requirements.txt`

Unpinned (`fastapi`, `uvicorn[standard]`, `pytest`, `httpx` — no version
specifiers). Installed versions in this repo's venv are captured in
`docs/01-overview.md`'s stack table.

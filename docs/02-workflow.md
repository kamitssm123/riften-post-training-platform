# Workflow: run order and request flow

## 1. Generate the synthetic corpus

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m generation.generate_corpus
```

`generate_corpus.py` (backend/generation/generate_corpus.py:340-349, `main()`) calls
`generate()` (line 231), which builds a Python list of trace dicts in
memory, then writes it as a single pretty-printed JSON array to
`/data/traces.json` (`OUT_PATH`, line 25). Nothing touches SQLite in this
step. `random.seed(42)` (line 22) is set at module import time, so re-running
this script produces byte-identical output every time — the only thing that
varies between runs is the `timestamp` field, which is computed from
`datetime.now(timezone.utc)` (line 126) at generation time, not from the
seeded RNG.

Immediately after this step: `/data/traces.json` exists and contains one
JSON array of trace objects (381 of them against the corpus currently
checked into `/data`, see `docs/06-dataset.md`); `/data/traces.db` does not
yet reflect this data (it may not exist, or may hold stale data from a
previous run).

## 2. Ingest into SQLite

```bash
python -m db.ingest
```

`ingest.py:92-98` (`main()`) checks `TRACES_JSON_PATH.exists()` and exits
with `SystemExit` if step 1 hasn't run. It then calls `load_corpus()`
(line 47), which:

1. Reads and JSON-parses `/data/traces.json`.
2. Opens `/data/traces.db` via `get_connection()` (line 40) — this creates
   the file if it doesn't exist.
3. Runs `CREATE_TABLE_SQL` from `backend/core/schema.py:97-121` via
   `executescript` — this is `CREATE TABLE IF NOT EXISTS`, so it's a no-op
   if the table already exists.
4. Runs `DELETE FROM traces` (line 54) — **this is the destructive step**.
5. Bulk-inserts every row from the freshly parsed JSON via `executemany`
   (line 82).

**Idempotency**: running `ingest.py` twice in a row is safe and produces the
same end state — the `DELETE FROM traces` before the insert means the table
is always wiped and reloaded from whatever `/data/traces.json` currently
contains, never appended to. Running it *without* first regenerating the
corpus just reloads the same data. Running it against a *different*
`/data/traces.json` (e.g. after re-running the generator, which is
deterministic and so produces the same content anyway) replaces the table
contents entirely.

After this step: `/data/traces.db` has a `traces` table with one row per
generated trace, plus four indexes (`idx_traces_session`,
`idx_traces_model`, `idx_traces_feedback`, `idx_traces_retrial_of` —
schema.py:118-121).

## 3. Run the tests

```bash
python -m pytest -q
```

The 42 tests across `tests/test_main.py`, `tests/test_export_sft.py`,
`tests/test_export_preference.py`, `tests/test_export_preview.py`,
`tests/test_model_tradeoff.py`, and `tests/test_exclusion_report.py` do **not**
depend on steps 1-2 having been run against the real `/data` directory —
every test fixture monkeypatches the relevant module's `DB_PATH` (and, for
the export tests, `EXPORTS_DIR`/`OUT_PATH`) to point at `pytest`'s
`tmp_path`, then calls `ingest.load_corpus()` against a small in-memory
fixture written to that temp path. This step can run before or after steps
1-2 with no interaction between them.

## 4. Start the backend and frontend

```bash
# backend, from /backend with venv active
uvicorn api.main:app --reload      # http://127.0.0.1:8000

# frontend, from /frontend, separate terminal
npm install
npm run dev                        # http://127.0.0.1:5173
```

**Order matters, but not the way it looks.** The frontend dev server will
start fine with the backend not yet running — Vite serves static assets
regardless. But every data-fetching `useEffect` in `App.tsx` fires on mount
(the trace list, the stats sidebar) and will fail silently: the
`fetch()` calls in `frontend/src/api/client.ts` throw on a non-OK response
or a connection error, and nothing in `App.tsx` catches that rejection — the
relevant `useState` (`traces`, `stats`, etc.) simply never updates past its
initial empty value, so the UI renders an empty table with no error message.
Start the backend first, or accept a blank screen until you do.

**What breaks if step 2 (ingest) was skipped**: the backend starts fine —
`api/main.py` only opens a SQLite connection inside each route handler, not at
import time — but every route that queries the `traces` table
(`/traces`, `/traces/{id}`, `/sessions/{id}`, `/stats`, and by extension all
three `/export/*` routes, which call the same `fetch_all_traces()`) returns
a 500 with `sqlite3.OperationalError: no such table: traces`, because
`sqlite3.connect()` happily creates an empty file at `DB_PATH` if none
exists but does not create the schema.

## 5. Run the exports

```bash
# as scripts, from /backend with venv active
python -m exports.export_sft
python -m exports.export_preference
python -m exports.exclusion_report

# or, with the backend running, via HTTP
curl -X POST http://127.0.0.1:8000/export/sft
curl -X POST http://127.0.0.1:8000/export/preference
curl       http://127.0.0.1:8000/export/exclusions
```

Each export requires only that step 2 (ingest) has completed — none of them
require the API server to be running; `export_sft.py` and
`export_preference.py` import `get_connection` from `db/ingest.py` directly
and open the SQLite file themselves. Running them via the
API is exactly the same code path: `api/main.py` imports
`build_sft_export`, `build_preference_export`, and `build_exclusion_report`
and calls them directly inside the route handlers — there is no
serialization/RPC boundary between "run as script" and "run via API" beyond
FastAPI turning the returned dict into a JSON response.

**Dependency order between the three exports**: `exclusion_report.py`
imports and calls both `build_sft_export()` and `build_preference_export()`
itself — running `exclusion_report.py`
**re-runs both other exports as a side effect**, overwriting
`/data/exports/sft.jsonl` and `/data/exports/preference.jsonl` even if you
only wanted the report. All three scripts read directly from SQLite each
time they run, so none of them depend on a previous export having been run
first — they're independent reads of the same table, not a pipeline.

Confirming non-empty, correct output on this repo's current data:

```
$ wc -l data/exports/*.jsonl
      24 data/exports/preference.jsonl
     108 data/exports/sft.jsonl
```

See `docs/07-exports.md` for the full exclusion breakdown and worked
examples.

## Request sequence diagrams

### Loading the trace table with filters applied

```
Browser                Frontend (App.tsx)         Vite proxy         Backend (api/main.py)          SQLite
   │                         │                         │                     │                     │
   │ user checks "gpt-4o-mini"                          │                     │                     │
   │ in FilterRail           │                         │                     │                     │
   ├────────────────────────>│ setFilters(...)          │                     │                     │
   │                         │ useEffect([filters,page])│                     │                     │
   │                         │ fetchTraces(filters,1,30)│                     │                     │
   │                         ├─ GET /api/traces?model=gpt-4o-mini&page=1&page_size=30 ─>│            │
   │                         │                         ├─ rewrite /api -> '' ─>│           │            │
   │                         │                         │                     │ list_traces(...)     │
   │                         │                         │                     │ build_filter_clause() │
   │                         │                         │                     │ -> "WHERE model IN (?)"│
   │                         │                         │                     ├─ SELECT COUNT(*) ... ─>│
   │                         │                         │                     │<──────── total ────────┤
   │                         │                         │                     ├─ SELECT ... LIMIT/OFFSET ─>│
   │                         │                         │                     │<──── rows (Row objects)────┤
   │                         │                         │                     │ per-row: parse tool_calls,│
   │                         │                         │                     │  compute has_tool_error   │
   │                         │<── 200 {items, total, page, page_size} ────────┤                     │
   │                         │ setTraces(items); setTotal(total)             │                     │
   │                         │ (separate effect) fetchStats(filters) ── same round trip, /stats ────>│
   │<── re-render: TraceTable rows + FilterRail result count ──┤                         │
```

`main.py`'s `list_traces` (api/main.py:109-178) and `get_stats` (api/main.py:218-297)
are called independently — `App.tsx` has two separate `useEffect` hooks
(one keyed on `[filters, page]`, one keyed on `[filters]`) so a filter change
triggers two parallel requests, not one.

### Opening a trace detail

```
Browser              Frontend (App.tsx)                     Backend (api/main.py)         SQLite
   │                       │                                       │                     │
   │ click a table row      │                                       │                     │
   ├──────────────────────>│ navigate("/traces/{id}") → panel={kind:"trace", id}           │
   │                       │ useEffect([panel]) branch: panel.kind==="trace"               │
   │                       │ fetchTrace(id)                          │                     │
   │                       ├─ GET /api/traces/{trace_id} ──────────>│ get_trace(trace_id)  │
   │                       │                                       ├─ SELECT * WHERE trace_id=? ─>│
   │                       │                                       │<──────── row or None ─────────┤
   │                       │                                       │ 404 if None, else Trace.from_row(row)
   │                       │<── 200 full TraceDetail (messages, response, tool_calls, ...) ──┤
   │                       │ setTraceDetail(res)                    │                     │
   │<── TraceDetail panel renders transcript + tool calls ──┤        │                     │
```

`Trace.from_row` (core/schema.py:87-94) JSON-decodes the `messages`, `response`,
and `tool_calls` TEXT columns back into nested objects and casts
`is_retrial` from SQLite's `0`/`1` integer to a Python bool before FastAPI
serializes the dict to JSON.

### Triggering an export

```
Browser (or curl)        Backend (api/main.py)     exports/export_sft.py / exports/export_preference.py    SQLite      Filesystem
      │                        │                                    │                                  │            │
      │ POST /export/sft        │                                    │                                  │            │
      ├───────────────────────>│ export_sft() route handler          │                                  │            │
      │                        ├─ build_sft_export() ───────────────>│ fetch_all_traces()                │            │
      │                        │                                    ├─ SELECT * FROM traces ────────────>│            │
      │                        │                                    │<──────── all rows ──────────────────┤            │
      │                        │                                    │ group by session_id                │            │
      │                        │                                    │ select_session_representative() per session      │
      │                        │                                    │ row_level_exclusion_reason() per kept trace      │
      │                        │                                    ├─ write JSONL rows ──────────────────────────────>│ /data/exports/sft.jsonl
      │                        │<── dict: {output_path, total_traces_considered, total_sessions, kept_count, excluded_by_reason} │
      │<── 200 JSON (same dict) ┤                                    │                                  │            │
```

The frontend never calls the `POST /export/*` routes directly — only `GET
/export/exclusions` is wired into the UI (`ExclusionPanel` via
`fetchExclusionReport` in `frontend/src/api/client.ts:59-63`), and that route itself
triggers both exports as a side effect (see the dependency note in step 5
above). There is no "export" button in the UI that fires `POST /export/sft`
or `POST /export/preference` — those are reachable only via script or direct
HTTP call.

## Where the real run order differs from the original phase order

It doesn't, structurally — the code was built and is meant to be run in the
same order the phases were specified (schema → generator/ingest → API → UI →
SFT export → preference export → exclusion report). The one nuance worth
calling out: **the exclusion report is not a separate read of pre-computed
export results** — `build_exclusion_report()` re-executes both
`build_sft_export()` and `build_preference_export()` from scratch every time
it's called (including every time the "Exclusion report" panel is opened in
the UI, since it's fetched fresh via `GET /export/exclusions` with no
caching on either side). This is idempotent and harmless given the exports
are deterministic reads of an unchanging SQLite table, but it does mean
opening the exclusion panel in the UI silently rewrites both `.jsonl` files
on disk as a side effect of a `GET` request.

# Known gaps

Honest inventory of what's incomplete, implemented differently than the
spec implied, or would need to change before this ran against anything
real. Nothing below is hidden elsewhere in the docs without being flagged
here too.

## Spec deviations and dead/inconsistent code

- **`Trace.to_row()` is dead code.** `schema.py:77-84` defines a method to
  flatten a `Trace` dataclass instance into a SQLite-ready row, but nothing
  in the codebase ever constructs a `Trace(...)` instance or calls it —
  `ingest.py:58-79` builds its insert tuples by hand from the raw parsed
  JSON dicts instead. Only `Trace.from_row` (the read-side inverse) is
  actually used, by `main.py` and `export_sft.py`. The dataclass and
  `ToolCall`/`Message` classes exist purely as documentation of the shape;
  nothing is ever instantiated from them.
- **A "tool error" retry can produce a trace with no `tool_calls` at all.**
  In `generate_corpus.py`'s retry branch (lines 265-277), `bad_kind` is
  chosen independently of whether the session is agentic
  (`is_agentic_session`). When `bad_kind == "tool_error"` in a
  *non-agentic* session, `agentic=is_agentic_session and bad_kind ==
  "tool_error"` evaluates to `False`, so `build_trace`'s `if agentic:`
  block (schema.py's counterpart logic, `generate_corpus.py:176`) never
  runs — no `tool_calls` are attached — but `tool_error=True` still forces
  `status_code=502` via the `force_status` param. The result: 5 rows in the
  current corpus have `status_code=502` and `tool_calls IS NULL`
  simultaneously (verified directly against the live DB — see
  `docs/06-dataset.md`). This means the `errored` filter's two clauses
  (`status_code >= 400` and `tool_calls` reaching-in check) aren't fully
  redundant with each other in practice, which is arguably fine (a call can
  fail at the gateway level without a tool being involved at all — that's
  realistic), but the *label* `"tool_error"` in the generator's own
  variable naming is misleading for these 5 rows, since no tool was
  actually involved.
- **Canned response text is keyed on `(session_id, turn_index)`, not on
  `trace_id`.** `generate_corpus.py:199` — `TOPICS[hash((session_id,
  turn_index)) % len(TOPICS)]` — means every trace sharing a
  `(session_id, turn_index)` pair (a retrial pair, or an accepted/rejected
  continuation pair, whenever neither branch is truncated or a tool error)
  gets **the same canned response text**, regardless of which attempt it
  is. This is directly visible in the real retrial example in
  `docs/07-exports.md`: the exported `chosen` and `rejected` sides of that
  preference pair have byte-identical `content`. For a preference-pair
  dataset, where the entire point is that `chosen` should read as better
  than `rejected`, having them sometimes be textually identical weakens the
  training signal the export claims to construct — a real preference
  dataset built this way would need the generator to vary response text per
  attempt, not just per turn.
- **Two of the four SFT row-level exclusion reasons are unreachable given
  the current tiebreak + generator combination.** `rejected_continuation`
  and `superseded_by_retrial` are checked in `row_level_exclusion_reason`
  (`export_sft.py:79-91`) but never fire against the real corpus (verified:
  the live `data/exports/exclusion_report.md` lists only
  `non_2xx_response`, `truncated_response`, and
  `superseded_by_longer_session_trace` under the SFT section — zero counts
  for the other two). This is a direct consequence of
  `select_session_representative`'s tiebreak deliberately preferring the
  non-loser branch whenever two same-turn traces compete for "kept" status
  — which means these two exclusion reasons only exist to protect against
  a kept trace that turns out to *also* be a rejected continuation or
  retrial loser *and* isn't at a session's single highest turn_index in a
  way the tiebreak would catch. Whether that combination can actually occur
  given how `generate_corpus.py` constructs sessions is untested against
  real data; only a hand-built `test_export_sft.py` fixture exercises
  `rejected_continuation`, and no test exercises `superseded_by_retrial`
  reaching the row-level check at all (see `docs/03-backend.md`'s test
  table).
- **The `weak_rating` preference-pairing path produces zero real pairs.**
  Every one of the 21 `weak`-feedback traces in the current corpus either
  got consumed by the retrial pass first, or has no `ok`/`strong` trace
  sharing its exact `(session_id, turn_index)` — because outside of a
  retrial or continuation branch, `generate_corpus.py` only ever produces
  one trace per `(session_id, turn_index)`. This isn't a bug in the pairing
  logic (the spec explicitly requires skipping rather than fabricating a
  cross-context pairing, and the code does exactly that — see
  `docs/07-exports.md`), but it means the `weak_rating` source is currently
  dead in terms of real output: 0/24 real preference pairs come from it,
  and its only demonstrated-working example in this doc set comes from a
  test fixture, not generated data. If a "weak rating gets paired" example
  in the real exported file specifically matters, the generator would need
  a mechanism to occasionally produce two independently-feedback-rated
  traces at the same turn outside of the retrial/continuation machinery —
  there isn't one today.

## Edge cases not handled

- **A weak-rated trace with no pairing candidate *anywhere* in the corpus,
  not just in-session, is always skipped — by design, not by omission.**
  The spec is explicit that fabricating a pairing across unrelated contexts
  is wrong, and the code (`export_preference.py:64-77`) only ever searches
  `by_session_turn[(session_id, turn_index)]`. There's no fallback tier
  (e.g. "pair against the highest-feedback trace anywhere with the same
  `model`") — which is the correct behavior per the stated design goal, but
  it does mean the `weak_rating` yield is entirely a function of how often
  the generator happens to produce two same-turn traces, not of how many
  weak-rated traces exist overall. See the point above.
- **Multiple `preferred` candidates surviving the SFT tiebreak.** If more
  than one same-turn candidate is neither a retrial loser nor a rejected
  continuation, `select_session_representative` (export_sft.py:70-71)
  breaks the tie by most-recent `timestamp`. This path is unreachable by
  the current generator (which only ever produces exactly 2 candidates at
  a shared max turn_index, and they're always in an explicit
  winner/loser relationship), so it's defensive code with no test coverage
  and no real-data exercise.
- **`export_preference.py`'s weak-rating "prefer strong" selection** (line
  73, `max(candidates, key=lambda c: c["feedback"] == "strong")`) doesn't
  distinguish between multiple `"strong"` candidates or multiple `"ok"`
  candidates at the same turn — it picks whichever Python's `max` happens
  to return first among ties, which is insertion order from
  `by_session_turn`'s list, not a deliberate secondary sort (e.g. by cost
  or latency). Unexercised by real data since this path currently yields
  zero pairs (see above).
- **`GET /export/exclusions` is a `GET` with file-writing side effects.**
  Every call re-runs both exporters and overwrites
  `/data/exports/sft.jsonl` and `/data/exports/preference.jsonl` (see
  `docs/02-workflow.md`). This violates the normal expectation that a GET
  request is safe/idempotent from the caller's point of view — a browser
  prefetch, a monitoring probe, or simply opening the Inspector UI's
  exclusion panel more than once will silently rewrite both export files
  every time, which is harmless today only because the exports are pure
  deterministic reads of an unchanging table.

## What would need to change before running against real router traffic

- **No PII/redaction handling anywhere.** Real router traces would contain
  real user prompts, real customer data in tool call args/results, and
  potentially secrets. Nothing in the schema, ingest path, or exports does
  any redaction, scrubbing, or access control — the entire design assumes
  synthetic, consequence-free content.
- **No authentication or authorization on any endpoint.** `main.py`'s CORS
  config (`allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]`,
  lines 27-32) accepts requests from anywhere, and no route checks any
  credential. Fine for a local synthetic-data demo; not fine once
  `/traces/{id}` can return real conversation content.
- **Token counts and cost are not real.** `estimate_tokens` is a word-count
  heuristic (`generate_corpus.py:133`) and `MODEL_PRICING_PER_1K`/
  `MODEL_LATENCY_MS` are illustrative round numbers (schema.py:23-40, with
  an explicit comment saying so). A real ingestion path would need a real
  tokenizer per model family and real, currently-accurate provider pricing.
- **SQLite's single-writer model doesn't fit a live ingestion pipeline.**
  `ingest.py`'s `load_corpus()` is a wipe-and-reload batch job — reasonable
  for a dev corpus regenerated from scratch each time, but real router
  traffic is an append-only, continuously-arriving stream from
  (potentially) multiple router instances, which is a different write
  pattern than this schema/ingest path was built for. `DELETE FROM traces`
  followed by a bulk insert (ingest.py:54-85) would destroy live data if
  pointed at a real, continuously-populated database.
- **No indexes on `turn_index`, `status_code`, or `finish_reason`**
  (`docs/05-database.md`). Fine at 381 rows; the session-grouping and
  filtering logic that scans these columns would need those indexes (and
  likely a composite `(session_id, turn_index)` index) before running
  against real volume.
- **`retrial_of` must be populated by whatever captures the trace, not
  inferred after the fact.** The generator sets it directly because it
  controls both attempts; a real ingestion pipeline would need the router
  itself (or a downstream heuristic) to identify that two calls represent
  the same logical retry — there's no retry-detection logic in this
  codebase at all, only retry-*recording* once the relationship is already
  known.
- **No pagination on `/sessions/{id}` or any `/export/*` route.**
  `get_session` (main.py:189-204) and every export's `fetch_all_traces()`
  (`export_sft.py:31-37`) load the entire result set into memory in one
  `SELECT`. Fine for a few hundred rows or a session with a handful of
  turns; would need streaming or chunked reads against real traffic volume
  or a session with thousands of turns.
- **No frontend error states, and no frontend tests.** As documented in
  `docs/04-frontend.md`, a failed fetch in `App.tsx` leaves the relevant
  `useState` at its initial empty value with no visible error — acceptable
  for a local demo talking to a backend you just started yourself, not
  acceptable once the frontend is talking to a service that can genuinely
  be down or slow. There is no test file anywhere under `/frontend` — all
  31 automated tests in this repo are backend-only (`docs/03-backend.md`).
- **No CI configuration.** There's no `.github/workflows` or equivalent in
  this repo — `pytest`, `tsc -b`, and `vite build` are all run manually per
  the instructions in `docs/02-workflow.md`, not automatically on push.
- **Dependency versions are unpinned.** `backend/requirements.txt` lists
  bare package names with no version specifiers; `frontend/package.json`
  uses caret ranges. The exact versions installed in this repo's venv and
  `node_modules` are recorded in `docs/01-overview.md` for reference, but a
  fresh `pip install`/`npm install` at a later date is not guaranteed to
  reproduce them.

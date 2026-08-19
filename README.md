# Riften Post-Training Data Platform

A take-home project for Riften (LLM router/gateway). Riften routes each
request to the cheapest model likely to complete it correctly, and captures
a trace of every call. This project turns raw router traffic into
post-training data (SFT + preference pairs), with a UI to inspect the traces
first.

**All data in this project is synthetic.** No real API keys, no real model
calls, no production traffic — traces are generated locally by a script that
simulates realistic messiness (retries, tool errors, truncation, multi-turn
sessions).

## Stack

- **Backend**: Python (FastAPI) — good fit for data/export scripting and a
  small filterable REST API.
- **Frontend**: React + TypeScript, Vite, Tailwind v4.
- **Storage**: SQLite (file-based, zero setup, fine for a few hundred rows).

## Directory layout

```
/backend
  api/         FastAPI app (main.py) + the model cost/quality tradeoff query
  core/        shared Trace schema (schema.py)
  db/          SQLite connection + corpus loading (ingest.py)
  generation/  synthetic corpus generator + its content bank
  exports/     SFT/preference export + exclusion-rule/report logic
  quality/     standalone corpus- and export-quality scorers
  tests/       pytest suite (mirrors the modules above)
/frontend   React + TS + Vite + Tailwind inspector UI
/data       generated traces (sqlite db) + exports (gitignored, kept via .gitkeep)
/docs       supporting docs
```

## Architecture

```
generation/generate_corpus.py --> /data/traces.json --> db/ingest.py --> /data/traces.db (SQLite)
                                                                  |
                                                                  v
                                                        api/main.py (FastAPI)
                                        /traces  /traces/{id}  /sessions/{id}  /stats
                                        /traces/{id}/export-preview  /stats/model-tradeoff
                                        POST /export/sft  POST /export/preference
                                        GET  /export/exclusions
                                                                  |
                        -----------------------------------------+-----------------------------
                        |                                        |                             |
                        v                                        v                             v
              frontend (React/Vite,             /data/exports/sft.jsonl        /data/exports/preference.jsonl
              proxies /api -> :8000)             (OpenAI chat FT format)       (chosen/rejected pairs)
                                                                                /data/exports/exclusion_report.md
```

## Trace schema

Defined once in `backend/core/schema.py` and consumed by the generator, the
API, and both exports:

| field | type | notes |
|---|---|---|
| `trace_id` | uuid | |
| `session_id` | uuid | groups traces belonging to the same growing conversation |
| `turn_index` | int | 0-indexed position within the session |
| `timestamp` | ISO 8601 | |
| `model` | enum | `gpt-4o`, `gpt-4o-mini`, `claude-3-5-sonnet`, `llama-3.1-70b`, `gemini-1.5-flash` |
| `messages` | array | full transcript sent for this call (system + prior turns + new user turn) |
| `response` | object | the assistant message returned |
| `tool_calls` | array\|null | each has `name`, `args`, `result: {status_code, output}` |
| `finish_reason` | enum | `stop` \| `length` \| `tool_calls` \| `content_filter` |
| `status_code` | int | simulated HTTP-style status for the call |
| `tokens_prompt`, `tokens_completion` | int | |
| `cost_usd`, `latency_ms` | float, int | |
| `feedback` | enum\|null | `weak` \| `ok` \| `strong` |
| `is_retrial` | bool | true if this call re-sent the same context after a discarded prior attempt |
| `retrial_of` | uuid\|null | points at the attempt this one replaced |
| `continuation_status` | enum\|null | `accepted` \| `rejected`, only meaningful for agentic multi-step traces |

## How to run

```bash
# 1. Backend setup
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Generate the synthetic corpus and load it into SQLite
python -m generation.generate_corpus   # -> /data/traces.json
python -m db.ingest                    # -> /data/traces.db

# 3. Run the tests
python -m pytest -q

# 4. Run the API
uvicorn api.main:app --reload    # http://127.0.0.1:8000

# 5. Run the frontend (separate terminal)
cd ../frontend
npm install
npm run dev                   # http://127.0.0.1:5173, proxies /api -> :8000

# 6. Run the exports (either via script or the running API)
cd ../backend
python -m exports.export_sft          # -> /data/exports/sft.jsonl
python -m exports.export_preference   # -> /data/exports/preference.jsonl
python -m exports.exclusion_report    # -> /data/exports/exclusion_report.md
# or, with the API running:
#   curl -X POST localhost:8000/export/sft
#   curl -X POST localhost:8000/export/preference
#   curl localhost:8000/export/exclusions

# 7. Run the corpus/export quality scorers (optional, standalone)
python -m quality.corpus_quality_check
python -m quality.export_quality_check
```

The Inspector UI's header has an "Exclusion report" link that renders the
same report the API returns, with sample trace_ids clickable straight into
the trace detail view for auditing.

## Design decisions where the spec was ambiguous

- **Session grouping / collapsing for SFT.** Agent clients resend the full
  transcript every turn, so the trace with the highest `turn_index` in a
  session already contains the whole conversation. That much is
  unambiguous. What the spec doesn't resolve: sometimes more than one trace
  *shares* that highest `turn_index` — a retrial pair (original + retry) or
  a continuation accept/reject pair both branch off the same prior context,
  so their `messages` arrays are identical and "longest messages array"
  can't break the tie. We resolve it in
  `exports.export_sft.select_session_representative` by preferring the
  branch that isn't already a "loser" by construction:
  not the discarded side of a retrial, not a rejected continuation. If that
  narrows to exactly one candidate, it's kept; the rest of the session's
  traces (including the other branch) are excluded as
  `superseded_by_longer_session_trace`.
- **What counts as "rejected" for SFT.** The four row-level exclusion rules
  (`non_2xx_response`, `truncated_response`, `rejected_continuation`,
  `superseded_by_retrial`) are checked in that order and the first match
  wins, so a trace that's simultaneously truncated *and* non-2xx is only
  ever counted once — exclusion counts stay mutually exclusive and sum
  exactly to `total_traces_considered - kept_count`.
- **How non-2xx is simulated.** `status_code` is set directly by the
  generator (mostly 200, with 429/500/502/503 sprinkled into tool-call
  errors and some plain traces) rather than derived from `finish_reason` —
  the two are independent signals in the real system (a call can fail at
  the transport/gateway level independent of how the model finished), so
  the schema and the `errored` filter treat them as such.
- **Preference pair format.** Chose `{input: {messages}, chosen, rejected,
  metadata}` over a flat list-of-two-completions format because it mirrors
  how most DPO/RLHF training pipelines and dataset loaders (e.g. TRL)
  expect preference data, and keeps the shared prompt context explicit and
  deduplicated rather than repeated per side.
- **Preference pairing scope.** All three sources (retrial, weak rating,
  rejected continuation) require the same `session_id` + `turn_index` so a
  pair is always a genuine "same prompt, different response" comparison.
  When no same-turn `ok`/`strong` partner exists for a `weak`-rated trace
  (the common case in this corpus, since most turns only produce one trace
  unless they're part of a retrial or continuation branch), we skip it and
  log `no_pairing_candidate` rather than fabricate a pairing across
  unrelated contexts. A trace already consumed as the rejected side of a
  retrial pair is not double-counted if it also happens to carry
  `feedback=weak`.

## Verified end-to-end

On a fresh clone: `generation.generate_corpus` → `db.ingest` → `pytest` →
both export scripts → `exports.exclusion_report` all run without errors;
`sft.jsonl` and `preference.jsonl` are non-empty; and for the SFT export,
`sum(excluded counts) + kept_count == total_traces_considered` (asserted in
`exclusion_report.build_exclusion_report` and covered by
`tests/test_exclusion_report.py`).

# Dataset

## Generation parameters actually used

Read directly from `backend/generation/generate_corpus.py`'s constants and
`generate()`'s logic — not the target ranges from the original spec (those
were 300-400 traces / 100-150 sessions; the actual generator constants are
narrower and are reproduced here as written):

| Parameter | Value in code | Location |
|---|---|---|
| RNG seed | `42` | `generate_corpus.py:22` |
| Session count | `random.randint(115, 140)` | `generate_corpus.py:233` |
| Model list | `gpt-4o`, `gpt-4o-mini`, `claude-3-5-sonnet`, `llama-3.1-70b`, `gemini-1.5-flash` | `generate_corpus.py:27-33` |
| Model volume weights | `gpt-4o: 0.10, gpt-4o-mini: 0.32, claude-3-5-sonnet: 0.13, llama-3.1-70b: 0.20, gemini-1.5-flash: 0.25` | `generate_corpus.py:36-42` |
| Agentic session probability | `0.30` | `generate_corpus.py:238` |
| Turn count distribution | `roll < 0.35` → 3-6 turns; `0.35 ≤ roll < 0.70` → exactly 2 turns; `roll ≥ 0.70` → 1 turn | `generate_corpus.py:240-246` |
| Session retry probability | `0.12` | `generate_corpus.py:248` |
| Retry turn selection | uniform over `range(num_turns)` | `generate_corpus.py:249` |
| Retry failure mode | 50/50 `weak_feedback` vs. `tool_error` | `generate_corpus.py:267` |
| Retrial feedback | uniform choice of `ok`/`strong` | `generate_corpus.py:287` |
| Per-turn tool-error probability | `0.30`, agentic sessions only | `generate_corpus.py:262` |
| Per-turn truncation probability | `0.11`, only rolled if not already a tool error | `generate_corpus.py:263` |
| Per-turn feedback probability (non-retry turns) | `0.18`, weighted `weak: 0.25, ok: 0.45, strong: 0.30` | `generate_corpus.py:296-299` |
| Continuation pair probability | `0.15`, agentic + non-error + non-truncated turns only | `generate_corpus.py:320` |

These are the exact constants in the file today. They were tuned (see the
git history) to land the *realized* corpus inside the spec's target ranges
(300-400 traces / 100-150 sessions, ~10-15% of sessions retried, ~8-10% of
traces tool-errored, ~8-10% truncated, ~30%+ of sessions with 3+ turns) —
the constants above are not themselves the target ranges, they're what
was found to produce output inside them given the fixed seed.

## How each messiness category is actually constructed

- **Retries** (~12% of sessions, `will_retry` at `generate_corpus.py:248`):
  one turn per flagged session is built twice. The first `build_trace()`
  call gets either `feedback="weak"` or `tool_error=True` (chosen 50/50,
  `generate_corpus.py:267`); the second call gets `is_retrial=True` and
  `retrial_of=<first trace_id>`, same `session_id`/`turn_index`. **Why it
  matters downstream**: this is the entire input to the SFT exporter's
  same-turn tiebreak logic (`select_session_representative`) and to the
  preference exporter's `retrial` pairing source — without retries, neither
  of those code paths would ever execute against real data, only against
  hand-built test fixtures.
- **Tool errors** (~10% of traces overall, but only ever generated inside
  agentic sessions at a 30% per-turn rate — `generate_corpus.py:262`): a
  `tool_calls` entry is attached with `result.status_code=500`, and the
  outer trace gets `status_code=502` (or whatever `force_status` was
  passed). **Why it matters**: exercises the API's `errored` filter (which
  reaches into the JSON `tool_calls` column via SQLite's `json_each`) and
  the SFT exporter's `non_2xx_response` exclusion rule against real
  tool-call-shaped data, not just a plain non-2xx trace.
- **Truncated rows** (~9% of traces, `generate_corpus.py:263`):
  `finish_reason` forced to `"length"`, response text taken from
  `TRUNCATION_CUTS` — four hand-written sentences that stop mid-clause
  (e.g. "The root cause is most likely related to a race condition
  between the"). **Why it matters**: proves the SFT exporter's
  `truncated_response` exclusion rule is exercised against a real row in
  the corpus, not merely present in the code with zero coverage from
  generated data (it is separately covered by a synthetic fixture in
  `test_export_sft.py::test_excludes_truncated`, but the whole point of
  generating some truncated rows into the actual corpus is that the
  exclusion report and the UI's "Truncated" filter have something real to
  show).
- **Continuation rejects** (8 accepted/8 rejected pairs in the current
  corpus, ~15% of eligible agentic non-error/non-truncated turns —
  `generate_corpus.py:316-333`): the just-built trace is mutated to
  `continuation_status="accepted"` and a sibling trace is built at the same
  `session_id`/`turn_index` with `continuation_status="rejected"`, forced
  to the same model. **Why it matters**: this is the only source (besides
  hand-built test fixtures) of the preference exporter's
  `continuation_rejected` pairing path, and the SFT exporter's
  `rejected_continuation` row-level exclusion rule.
- **Mixed models, skewed cheap** (`MODEL_WEIGHTS`,
  `generate_corpus.py:36-42`): `gpt-4o-mini` (0.32) and `gemini-1.5-flash`
  (0.25) together account for more than half the weight, `gpt-4o` (the most
  expensive) gets the smallest share (0.10). **Why it matters**: makes the
  cost-range filter in the UI and the `per_model` stats breakdown show a
  realistic "router sends most traffic to cheap models" distribution rather
  than a uniform spread, matching the framing in `docs/01-overview.md`.

## Actual corpus currently in `/data`

Computed by querying the live `/data/traces.db` directly (`sqlite3` CLI
equivalent of the queries below run via Python in this session) —
regenerating the corpus reproduces these exact numbers, since the generator
is seeded, but re-running `python -m generation.generate_corpus` will still
shift the `timestamp` column (see `docs/02-workflow.md`).

**Totals**: 381 traces across 135 sessions.

**Per-model breakdown**:

| model | count | share |
|---|---|---|
| gpt-4o-mini | 118 | 31.0% |
| gemini-1.5-flash | 91 | 23.9% |
| llama-3.1-70b | 83 | 21.8% |
| claude-3-5-sonnet | 49 | 12.9% |
| gpt-4o | 40 | 10.5% |

(Matches the configured weights closely — `gpt-4o-mini` at 31.0% realized
vs. 32% configured, `gpt-4o` at 10.5% realized vs. 10% configured.)

**Per-feedback breakdown**:

| feedback | count |
|---|---|
| (none) | 308 |
| ok | 26 |
| strong | 26 |
| weak | 21 |

**`finish_reason` breakdown**:

| finish_reason | count |
|---|---|
| stop | 231 |
| tool_calls | 117 |
| length | 33 |

**Retrial / continuation counts**:

| metric | count |
|---|---|
| traces with `is_retrial = 1` | 16 |
| traces with `retrial_of IS NOT NULL` | 16 (same 16 rows) |
| traces with `continuation_status = 'accepted'` | 8 |
| traces with `continuation_status = 'rejected'` | 8 |
| traces with non-null `tool_calls` | 125 |

**Error / truncation rate** (as computed by `GET /stats`, which is the same
definition the SFT exporter's `non_2xx_response`/`truncated_response` rules
use): error_count = 43 (11.29%), truncated_count = 33 (8.66%). Of the 43
errored traces, 38 have an actual `tool_calls` entry with a ≥400 result; the
remaining 5 have `status_code = 502` with `tool_calls IS NULL` — see
`docs/08-known-gaps.md` for why (a retry's "tool_error" failure mode can be
selected in a non-agentic session, where it forces the status code without
attaching any tool call).

Spec target ranges vs. realized: retries ~10-15% of sessions → 12/135 ≈ 8.9%
of sessions contain a retry pair (16 retrial traces belong to 16 distinct
sessions, since `will_retry` is a per-session boolean); tool errors ~8-10%
of traces → 43/381 ≈ 11.3% by the `errored` definition (38/381 ≈ 10.0% by
strict "has a tool_calls entry with a ≥400 result" count); truncated ~8-10%
→ 33/381 ≈ 8.7%; sessions with 3+ turns ~30%+ → measured directly against
`generate_corpus.py`'s turn-count roll, ~35% of sessions land in the 3-6
turn bucket per the `roll < 0.35` branch.

## Why synthetic data, and what to assume about it

No real API keys, no real model calls, no production Riften traffic exist
anywhere in this repo — `generate_corpus.py` is the only source of trace
data, and it runs entirely offline with hardcoded topic/response text. This
was a deliberate constraint (see the top-level task's "no real API keys or
production traffic" rule), not a limitation discovered after the fact.

What a reader should assume about its realism:

- **Response content is not model output.** Every canned response in
  `TOPICS`/`AGENTIC_TOPICS` was hand-written once and is reused
  deterministically (keyed on `hash((session_id, turn_index))` for the
  non-agentic/non-truncated case) — the corpus demonstrates the *shape* of
  router trace data (retries, errors, truncation, multi-turn context growth,
  cost/latency variance) faithfully, but says nothing about what any of
  these models would actually produce for these prompts.
- **Token counts are estimates, not real tokenization.** `estimate_tokens`
  (`generate_corpus.py:133`) is `len(text.split()) * 4 // 3` — a
  word-count heuristic, not a real tokenizer (no `tiktoken` or
  model-specific tokenizer is used anywhere in this repo). `tokens_prompt`/
  `tokens_completion`, and therefore `cost_usd`, are directionally
  reasonable but not numerically accurate.
- **Cost and latency are illustrative, not real pricing.** `schema.py:24`
  says so directly in a comment; the `MODEL_PRICING_PER_1K` and
  `MODEL_LATENCY_MS` tables are round numbers chosen to differentiate the
  five models' cost/speed profiles, not sourced from any provider's actual
  rate card.
- **Topic diversity is intentionally small.** 12 non-agentic topics and 5
  agentic topics (`generate_corpus.py:49-115`) are recycled across all 381
  traces — real router traffic would have far higher prompt diversity; this
  corpus is sized for demonstrating the pipeline's mechanics (filtering,
  session collapsing, pairing), not for producing a diverse training set.

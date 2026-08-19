# Exports

**Shared exclusion-rule module**: the session-collapse algorithm
(`select_session_representative`), the SFT row-level exclusion checks
(`row_level_exclusion_reason`), and the preference three-pass pairing
algorithm now live in `backend/exclusion_rules.py` as
`compute_sft_plan(traces)` and `compute_preference_plan(traces)`, extracted
out of `export_sft.py`/`export_preference.py` in a pure refactor (verified
byte-identical `sft.jsonl`/`preference.jsonl`/`exclusion_report.md` output
before and after). Both real export scripts and the new
`GET /traces/{trace_id}/export-preview` route (documented at the bottom of
this file) call these same functions — the algorithm descriptions below are
still accurate, just relocated. See `docs/03-backend.md`'s
`exclusion_rules.py` section for the module's own API.

## SFT export (`export_sft.py`)

### Step-by-step algorithm, as implemented

1. `fetch_all_traces()` (`export_sft.py:31-37`) — `SELECT * FROM traces`,
   no filter, every row inflated via `Trace.from_row`.
2. Group all traces by `session_id` into a `dict[str, list[dict]]`
   (`build_sft_export`, lines 98-100).
3. For each session, call `select_session_representative(session_traces)`
   (lines 40-76):
   - Find `max_turn = max(turn_index for all traces in session)`.
   - `candidates` = every trace at `max_turn`; `superseded` = every trace
     *not* at `max_turn` (these are excluded immediately, before any
     row-level check).
   - If exactly one candidate, it's kept, done.
   - Otherwise (a same-turn branch — a retrial pair or a continuation pair
     sharing the session's highest turn_index): compute `retrial_losers` =
     the set of `retrial_of` values among the candidates (i.e. trace_ids
     that some candidate points back at as the attempt it replaced);
     `preferred` = candidates that are neither a retrial loser nor a
     rejected continuation. If `preferred` narrows to exactly one, that's
     kept; if more than one remains (shouldn't happen given how the
     generator constructs same-turn branches, but handled), the most recent
     by `timestamp` wins; if `preferred` is empty (also shouldn't happen),
     fall back to the most recent of all candidates.
   - Every candidate that wasn't kept is added to `superseded`.
4. For the one kept trace per session, call `row_level_exclusion_reason(kept,
   by_id)` (lines 79-91) — checked **in this order, first match wins**:
   - `not (200 <= status_code < 300)` → `"non_2xx_response"`
   - `finish_reason == "length"` → `"truncated_response"`
   - `continuation_status == "rejected"` → `"rejected_continuation"`
   - some other trace has `retrial_of == kept.trace_id` (i.e. this kept
     trace is itself the *loser* of a retrial) → `"superseded_by_retrial"`
   - none of the above → not excluded, appended to `kept_rows`.
5. Every superseded trace's `trace_id` is appended to
   `excluded["superseded_by_longer_session_trace"]`; every row-level
   exclusion appends to `excluded[<reason>]`.
6. `kept_rows` are written to `/data/exports/sft.jsonl`, one JSON object per
   line: `{"messages": kept["messages"] + [kept["response"]], "metadata":
   {...}}` (lines 118-130).

### Before/after example, real session data

Session `2eacd229-0d7f-46b8-bc41-bc08faadb478` (the same 3-turn-with-retry
session worked through in `docs/05-database.md`) has **4 raw traces**:

| trace_id (short) | turn_index | is_retrial | retrial_of |
|---|---|---|---|
| `bdb66f8e` | 0 | 0 | — |
| `61d291b5` | 1 | 0 | — |
| `158fd41d` | 2 | 0 | — |
| `a70b1e6c` | 2 | 1 | `158fd41d` |

Collapsing this session:
- `max_turn = 2`.
- `candidates = [158fd41d, a70b1e6c]` (both at turn 2); `superseded` starts
  as `[bdb66f8e, 61d291b5]` (turns 0 and 1).
- `retrial_losers = {158fd41d}` (since `a70b1e6c.retrial_of == 158fd41d`).
- `preferred = [a70b1e6c]` (the only candidate that isn't a retrial loser).
- `kept = a70b1e6c`; `158fd41d` gets appended to `superseded`.
- Final: **kept = `a70b1e6c`**, **superseded = `[bdb66f8e, 61d291b5,
  158fd41d]`** — all three logged under
  `excluded["superseded_by_longer_session_trace"]`.
- Row-level check on `a70b1e6c`: `status_code=200` (2xx, passes),
  `finish_reason="stop"` (not length, passes), `continuation_status=None`
  (passes), and no other trace has `retrial_of == "a70b1e6c..."` (it's not
  a retrial loser itself, passes) → **not excluded**, written to
  `sft.jsonl`.

One 4-row session becomes one line in `sft.jsonl`:
```json
{"messages": [
  {"role": "system", "content": "You are a helpful assistant embedded in a customer support and developer tools product. Answer concisely and use tools when needed."},
  {"role": "user", "content": "Convert this CSV row into a JSON object for me."},
  {"role": "assistant", "content": "Your endpoint is likely taking longer than the 5s delivery timeout. Move slow processing to a background job and return a 200 immediately on receipt."},
  {"role": "user", "content": "Debug why this SQL query returns duplicate rows."},
  {"role": "assistant", "content": "The join against the `orders` table is one-to-many without aggregation, so each matching order row duplicates the parent record. Add a `GROUP BY` or use a window function."},
  {"role": "user", "content": "Why is my webhook delivery failing with a timeout?"},
  {"role": "assistant", "content": "Return `429 Too Many Requests`, ideally with a `Retry-After` header indicating when the client can try again."}
],
"metadata": {"model": "llama-3.1-70b", "tokens_prompt": 68, "tokens_completion": 13, "cost_usd": 0.0000730, "latency_ms": 761, "feedback": "ok"}}
```

### Row-level exclusion rules, each with a real excluded row

**`non_2xx_response`** — condition: `not (200 <= status_code < 300)`. Real
example: trace `3a2709f3-dabd-4194-8d95-fb970f1ff230`, session
`8b3c718e-374e-48b0-a777-bcea8504619f`, `turn_index=5` (the highest turn in
that 7-trace session, so it was the session's kept candidate before this
check), `status_code=502`, `finish_reason=tool_calls`. Excluded before ever
reaching the truncation/continuation/retrial checks, because
`non_2xx_response` is checked first.

**`truncated_response`** — condition: `finish_reason == "length"`. Real
example: trace `fff4fb4d-e516-4977-a4a0-6832fba57225`, session
`40ed96f6-34fc-4b01-8a6e-c898f7de190a`, `turn_index=2` (again the session's
highest turn — a 3-trace session with turns 0, 1, 2), `status_code=200`
(passes the first check) but `finish_reason=length`, response text cut off
mid-sentence ("The root cause is most likely related to a race condition
between the").

**`rejected_continuation`** and **`superseded_by_retrial`** — conditions:
`continuation_status == "rejected"`, and "some other trace has `retrial_of`
pointing at this one," respectively. **Neither reason appears in the
current corpus's exclusion report** (`data/exports/exclusion_report.md`
lists only `superseded_by_longer_session_trace`, `non_2xx_response`, and
`truncated_response` under the SFT section). This isn't a bug — it's a
direct consequence of the same-turn tiebreak in
`select_session_representative`: a rejected continuation or a retrial loser
can only ever reach the row-level check if it was chosen as the session's
`kept` trace, and the tiebreak logic is specifically built to prefer the
*other* branch (the accepted continuation, the retrial winner) whenever
both share the session's highest turn_index. Both rules are exercised by
`test_export_sft.py::test_excludes_rejected_continuation` and there is no
`test_excludes_superseded_by_retrial` test — the closest coverage is
`test_retrial_tiebreak_at_same_turn_index`, which confirms the *tiebreak*
picks the winner, not that a stray retrial loser reaching the row-level
check gets caught by it. See `docs/08-known-gaps.md`.

## Preference pair export (`export_preference.py`)

### Step-by-step algorithm, as implemented

1. `fetch_all_traces()` (reused from `export_sft.py`).
2. Index every trace by `(session_id, turn_index)` into
   `by_session_turn: dict[tuple[str,int], list[dict]]` (lines 43-45) — one
   precomputed lookup shared by all three passes, rather than re-querying
   the trace list per candidate.
3. **Pass 1 — retrials** (lines 53-59): for every trace with a non-null
   `retrial_of`, look up the original by `trace_id` in `by_id`; if found,
   emit `make_pair(chosen=<this trace>, rejected=<original>, source=
   "retrial")` and mark the original's `trace_id` in `used_rejected_ids`.
4. **Pass 2 — weak ratings** (lines 64-77): for every trace with
   `feedback == "weak"` **not already in `used_rejected_ids`**, look at
   every other trace sharing its `(session_id, turn_index)` with
   `feedback in ("ok", "strong")`. If any exist, pick the one favoring
   `"strong"` (`max(candidates, key=lambda c: c["feedback"] == "strong")`
   — a boolean-as-sort-key trick that prefers any `"strong"` candidate over
   an `"ok"` one, and picks arbitrarily among ties within the same
   preference tier since Python's `max` isn't stable across equal keys in a
   meaningful way here), emit the pair, mark the weak trace as used.
   Otherwise, log the weak trace's `trace_id` under
   `excluded["no_pairing_candidate"]`.
5. **Pass 3 — rejected continuations** (lines 81-94): same shape as pass 2,
   but keyed on `continuation_status == "rejected"` and matched against
   `continuation_status == "accepted"` at the same `(session_id,
   turn_index)`; picks the first match (`candidates[0]`, no preference
   ordering needed since there is at most one accepted continuation per
   turn by construction).
6. Write every pair to `/data/exports/preference.jsonl`, one JSON object per
   line.

The `used_rejected_ids` set is what prevents a trace from being
double-counted: a trace that's simultaneously the discarded side of a
retrial *and* happens to carry `feedback == "weak"` (this does happen in
the generator — `bad_kind == "weak_feedback"` sets exactly this) is only
ever paired once, by pass 1, since pass 2 explicitly skips anything already
in `used_rejected_ids`.

### Real examples, one per source that actually produced output

**Retrial** — trace `83754fa1-089d-46a6-9b7f-52702afc6eb1` (chosen) paired
against `670369d9-badf-49fc-929d-32eb2eca0d3f` (rejected), the same pair
documented in `docs/05-database.md`'s retrial-pair sample. Both share
`input.messages` (the shared prior context). Notably, in this real pair,
`chosen.content` and `rejected.content` are **identical text** — "Call
`POST /admin/users/{{id}}/reset-password`..." — because of the deterministic
canned-response quirk described in `docs/06-dataset.md` and
`docs/08-known-gaps.md`. Actual output row:
```json
{"input": {"messages": [ /* 8-entry shared transcript */ ]},
 "chosen":   {"role": "assistant", "content": "Call `POST /admin/users/{{id}}/reset-password` with a valid admin token. This invalidates existing sessions and emails the user a reset link."},
 "rejected": {"role": "assistant", "content": "Call `POST /admin/users/{{id}}/reset-password` with a valid admin token. This invalidates existing sessions and emails the user a reset link."},
 "metadata": {"source": "retrial", "chosen_model": "llama-3.1-70b", "rejected_model": "gpt-4o-mini",
              "chosen_feedback": "ok", "rejected_feedback": null,
              "chosen_cost_usd": 0.000149, "rejected_cost_usd": 0.000036}}
```

**Continuation rejected** — trace `d23afc03-8cd4-4416-86b0-3ab3b22823df`
(chosen, `continuation_status="accepted"`) paired against
`85e48579-d63a-4eb4-9b51-d35e5ef7239d` (rejected), the same pair documented
in `docs/05-database.md`. Here the two responses genuinely differ (they
proposed different tool calls — `lookup_order` vs. `lookup_customer`):
```json
{"input": {"messages": [ /* shared transcript up to turn 3 */ ]},
 "chosen":   {"role": "assistant", "content": "I checked order #48213 and it's still pending, so I've issued a full refund."},
 "rejected": {"role": "assistant", "content": "Found the customer record and upgraded jane@example.com to the Pro plan."},
 "metadata": {"source": "continuation_rejected", "chosen_model": "claude-3-5-sonnet", "rejected_model": "claude-3-5-sonnet",
              "chosen_feedback": null, "rejected_feedback": null,
              "chosen_cost_usd": 0.000765, "rejected_cost_usd": 0.000033}}
```

**Weak rating** — **the current corpus produces zero pairs from this
source** (`pairs_by_source.weak_rating == 0` in the live exclusion report).
Every `feedback == "weak"` trace in the generated data either got consumed
by pass 1 (it was also a retrial loser) or has no `ok`/`strong` trace
sharing its exact `(session_id, turn_index)` — because outside of a retrial
or continuation branch, the generator only ever produces one trace per
`(session_id, turn_index)`, so there is structurally almost never a second
trace at the same turn to compare feedback against. All 14
`no_pairing_candidate` entries in the live report are exactly these
orphaned weak-feedback traces. To show the pairing logic actually working
(it is exercised by `test_export_preference.py::test_weak_rating_paired_when_candidate_exists`
against a synthetic fixture, not real corpus data), here is that test's
constructed pair — two traces, `weak1` (`feedback="weak"`) and `strong1`
(`feedback="strong"`), both at `session_id="s1", turn_index=0`:
```json
{"input": {"messages": [{"role": "user", "content": "hi"}]},
 "chosen":   {"role": "assistant", "content": "hello"},
 "rejected": {"role": "assistant", "content": "hello"},
 "metadata": {"source": "weak_rating", "chosen_model": "gpt-4o-mini", "rejected_model": "gpt-4o-mini",
              "chosen_feedback": "strong", "rejected_feedback": "weak",
              "chosen_cost_usd": 0.001, "rejected_cost_usd": 0.001}}
```
(This block is explicitly a test fixture, not a row from
`/data/exports/preference.jsonl` — flagged here because the task requires
distinguishing real output from constructed examples, and this source
currently has no real output to show.)

## Exclusion reporting

`build_exclusion_report()` (`exclusion_report.py:30-55`) calls
`build_sft_export()` and `build_preference_export()` (which, as noted in
`docs/02-workflow.md`, re-run and rewrite both `.jsonl` files as a side
effect), wraps each `excluded_by_reason` dict with per-reason counts and up
to `SAMPLE_SIZE = 5` sample `trace_id`s (`_reasons_with_samples`, lines
23-27), and asserts the SFT side's excluded counts plus `kept_count` equal
`total_traces_considered` before returning (lines 37-40) — this assertion
is what makes "counts sum correctly" a runtime-checked invariant rather
than a claim.

Current corpus, reproduced from the live `/data/exports/exclusion_report.md`
(regenerable via `python exclusion_report.py`):

**SFT export**: 381 traces considered across 135 sessions; 108 kept.

| Reason | Count |
|---|---|
| superseded_by_longer_session_trace | 246 |
| non_2xx_response | 11 |
| truncated_response | 16 |

`246 + 11 + 16 + 108 = 381` ✓.

**Preference pair export**: 381 traces considered; 24 pairs written
(retrial: 16, weak_rating: 0, continuation_rejected: 8).

| Reason | Count |
|---|---|
| no_pairing_candidate | 14 |

## JSONL schema, field by field

### `sft.jsonl` — one line per kept conversation

```json
{"messages": [{"role": "...", "content": "..."}, ...],
 "metadata": {"model": "...", "tokens_prompt": 0, "tokens_completion": 0,
              "cost_usd": 0.0, "latency_ms": 0, "feedback": null}}
```

| Field | Source |
|---|---|
| `messages` | `kept["messages"] + [kept["response"]]` — the kept trace's full resent transcript with its own response appended, reconstructing the complete conversation as a single OpenAI chat-format array. |
| `metadata.model` | `kept["model"]` |
| `metadata.tokens_prompt` / `tokens_completion` | `kept["tokens_prompt"]` / `kept["tokens_completion"]` |
| `metadata.cost_usd` | `kept["cost_usd"]` |
| `metadata.latency_ms` | `kept["latency_ms"]` |
| `metadata.feedback` | `kept["feedback"]` (may be `null`) |

### `preference.jsonl` — one line per chosen/rejected pair

```json
{"input": {"messages": [...]},
 "chosen": {"role": "assistant", "content": "..."},
 "rejected": {"role": "assistant", "content": "..."},
 "metadata": {"source": "retrial|weak_rating|continuation_rejected",
              "chosen_model": "...", "rejected_model": "...",
              "chosen_feedback": null, "rejected_feedback": null,
              "chosen_cost_usd": 0.0, "rejected_cost_usd": 0.0}}
```

| Field | Source |
|---|---|
| `input.messages` | `chosen["messages"]` — the shared prompt context (identical to `rejected["messages"]` by construction, since both sides are required to share `session_id`+`turn_index`; only `chosen`'s copy is kept in the output). |
| `chosen` / `rejected` | `chosen["response"]` / `rejected["response"]` — the two candidate assistant replies. |
| `metadata.source` | one of `"retrial"`, `"weak_rating"`, `"continuation_rejected"` — which pass produced this pair. |
| `metadata.chosen_model` / `rejected_model` | the model that produced each side — can differ (the retrial example above pairs `llama-3.1-70b` against `gpt-4o-mini`), since a retrial can be re-routed to a different model on the second attempt. |
| `metadata.chosen_feedback` / `rejected_feedback` | each side's `feedback` field, independently — not constrained to be non-null. |
| `metadata.chosen_cost_usd` / `rejected_cost_usd` | each side's `cost_usd`. |

## Live per-trace export preview (`GET /traces/{trace_id}/export-preview`)

A read-only, single-trace view over the same exclusion rules described
above, backed by `export_preview.py`. Where the exclusion report only shows
what was *already* excluded after an export ran, this endpoint lets a
reviewer click any trace in the inspector and see its fate in both exports
before ever running one — same rule functions
(`exclusion_rules.compute_sft_plan`/`compute_preference_plan`), no export
files written as a side effect (unlike `POST /export/sft`,
`POST /export/preference`, and `GET /export/exclusions`, which all rewrite
`sft.jsonl`/`preference.jsonl`/`exclusion_report.md`).

Response shape — both top-level keys always present, since a trace can be
excluded from one export and included/eligible in the other:

```json
{
  "sft": {
    "included": false,
    "reason": "truncated_response",
    "detail": "finish_reason is 'length'"
  },
  "preference": {
    "eligible": true,
    "role": "rejected",
    "source": "retrial",
    "paired_with_trace_id": "83754fa1-089d-46a6-9b7f-52702afc6eb1",
    "detail": "rejected side of a retrial pair, paired with trace 83754fa1-089d-46a6-9b7f-52702afc6eb1"
  }
}
```

| Field | Source |
|---|---|
| `sft.included` | `True` iff this trace is the one written to `sft.jsonl` for its session. |
| `sft.reason` | `null` when included; otherwise one of `superseded_by_longer_session_trace`, `non_2xx_response`, `truncated_response`, `rejected_continuation`, `superseded_by_retrial` — the same reason vocabulary as the exclusion report. |
| `sft.detail` | Human-readable explanation. For the two "another trace took precedence" reasons (`superseded_by_longer_session_trace`, `superseded_by_retrial`) this **names the specific trace_id** that superseded it — e.g. "trace `8a8d1b58-...` in the same session has a higher turn_index and was kept as the session's representative instead" — this is the case the feature spec calls out as most worth getting right, since it's the least obvious to a non-technical reviewer looking at a raw exclusion count. |
| `preference.eligible` | `True` iff this trace was chosen or rejected on some preference pair. |
| `preference.role` | `"chosen"` or `"rejected"` when eligible, else `null`. |
| `preference.source` | `"retrial"`, `"weak_rating"`, or `"continuation_rejected"` when eligible, else `null`. |
| `preference.paired_with_trace_id` | The other side's `trace_id` when eligible, else `null`. |
| `preference.detail` | Human-readable explanation, including the `"no pairing candidate at the same session + turn_index"` case for a weak/rejected-continuation trace that was logged under `no_pairing_candidate` rather than paired. |

A trace that is both superseded in its session *and* the rejected side of a
retrial pair (the common shape for a retrial loser, since the retrial
winner is what advances the session's turn_index) reports both
independently — `sft.included: false` with `reason:
"superseded_by_longer_session_trace"` (session-collapse always runs before
the row-level check, so that's the reason that wins) alongside
`preference.eligible: true`, since preference pairing is a completely
separate pass over the same trace list. Real example: trace
`670369d9-badf-49fc-929d-32eb2eca0d3f` from the retrial pair documented
above — excluded from `sft.jsonl` (superseded by `8a8d1b58-...`, the
session's turn-2 representative) but present in `preference.jsonl` as the
`rejected` side of the `retrial` pair against `83754fa1-...`.

Frontend: `TraceDetail` fetches this automatically (via `App.tsx`,
alongside the trace itself) whenever a trace is opened and renders it as
two badges — see `docs/04-frontend.md`'s `ExportPreviewBadges` section.

## Cost/quality tradeoff (`GET /stats/model-tradeoff`)

Not an export and doesn't touch exclusion logic at all — listed here
because, like the preview above, it's a read view over the same trace data
that motivates the exports (validating that cheaper models are actually
worth routing to is the reason a cost-aware SFT/preference dataset matters
in the first place). Backed by `backend/model_tradeoff.py`; full field
list and SQL in `docs/03-backend.md`'s `model_tradeoff.py` section.
Response: `{"items": ModelTradeoff[]}`, one entry per distinct `model`,
each with `trace_count`, `avg_cost_usd`, `avg_latency_ms`,
`avg_tokens_prompt`/`avg_tokens_completion`, `avg_quality_score` (`null`
when the model has zero feedback coverage, never a misleading `0.0`),
`feedback_coverage`, `error_rate`, `truncation_rate`. Frontend:
`ModelTradeoffView`/`ModelTradeoffChart` — see `docs/04-frontend.md`.

### Why `metadata` is a sibling key, not embedded in `messages`

Both formats keep `metadata` as a top-level sibling of `messages` (SFT) or
`chosen`/`rejected` (preference) rather than folding it into a message's
`content` or adding extra keys onto a message object. This is a direct,
literal requirement in both export scripts — `export_sft.py`'s output dict
literal (lines 119-129) and `export_preference.py`'s `make_pair` (lines
22-36) both construct `messages`/`chosen`/`rejected` as plain
`{role, content}` objects with nothing else attached, and add `metadata` as
a separate top-level key. `test_export_sft.py::test_metadata_does_not_leak_into_messages`
and `test_export_preference.py::test_output_shape` both assert this
structurally (`set(row.keys()) == {"messages", "metadata"}` for SFT;
`set(row.keys()) == {"input", "chosen", "rejected", "metadata"}` for
preference). The reason, as stated in the original task spec and preserved
here because the code enforces it: metadata like cost, latency, and
feedback must never become part of what a model is trained to *produce* —
if it leaked into `content`, a fine-tuning run would learn to emit cost
figures and feedback labels as if they were conversational text.

# Corpus content quality: before/after

Fixed the trace generator's content-pairing bug (questions and responses
were sampled independently from two flat pools, so a topic's question and
its own response were frequently unrelated) by replacing the flat pools
with a topic-locked content bank (`backend/content_bank.py`) and rewriting
the generator's content-selection logic to always draw a trace's question
and response from the same topic exchange (`backend/generate_corpus.py`).
Scored with the new `backend/corpus_quality_check.py`.

| Metric | Before | After | Target |
|---|---|---|---|
| Unique questions | 17 | 109 | ≥60 |
| Unique responses | 22 | 157 | ≥60 |
| Question/answer coherence rate | 24% | 100% | ≥90% |
| Sessions with unexplained repeat | 31% (42/135) | 0% (0/135) | ≤3% |
| Overall score | 34/100 | 100/100 | 85–90 |

## Category coverage held steady (not regressed)

The generator's scenario-flag logic (which decides truncation, tool
errors, retries, continuations, and model routing) was left untouched —
only the content-selection half changed. Realized rates on the regenerated
corpus (405 traces / 135 sessions, up from 381/135 — not a reduction):

| Category coverage check | Result |
|---|---|
| Model mix | 5 distinct models, max share 34.1% (target: ≥4 distinct, none >45%) |
| Truncation rate | 9.63% (target: 5–12%) |
| Tool-error / non-2xx rate | 8.40% (target: 5–15%) |
| Retrial rate | 4.94%, all `retrial_of` links valid (target: 2–8%) |
| Continuation accept/reject | 2.47% / 2.47%, both present; session lengths span 1–6 turns |

All five category-coverage checks pass at the full 40/40 points, confirming
the fix didn't trade away the corpus's existing scenario realism to buy
content coherence.

## What changed

- **Phase 1** (`backend/content_bank.py`): 22 topic domains (15
  non-agentic, 7 agentic), each a short thread of question/answer
  "exchanges." Every question variant in an exchange can be paired with
  any answer variant from the same exchange and stay topically correct by
  construction — an exhaustive audit checks every question × answer
  combination in the bank, including worst-case truncated prefixes, for a
  shared non-stopword keyword.
- **Phase 2** (`backend/generate_corpus.py`): the generator now picks a
  topic first, then draws the question and response from that topic's
  current exchange. Multi-turn sessions either move to a new topic or
  advance to a natural follow-up exchange within the current topic;
  verbatim question repeats within a session now only occur for genuine
  retries (`is_retrial` + `retrial_of`). Truncated responses are now a
  prefix of a real on-topic answer rather than an unrelated canned
  sentence. Retry and continuation sibling traces exclude each other's
  response text, so `chosen`/`rejected` pairs are no longer byte-identical
  (a gap previously called out in `docs/08-known-gaps.md`).
- **Phase 3** (`backend/corpus_quality_check.py`): a standalone 0–100
  scorer (category coverage 40 pts, content coherence 40 pts, diversity 20
  pts) used to validate the fix and guard against future regressions.

## Scope

Only the corpus generator and its content bank changed. The SFT/preference
export scripts, ingest logic, backend routes, and frontend were not
touched, per the task's scope boundary.

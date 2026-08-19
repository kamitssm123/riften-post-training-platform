# Export quality: before/after

Fixed two exporter-logic bugs in `backend/exports/exclusion_rules.py` (the shared
module behind `export_sft.py`, `export_preference.py`, and the
export-preview route). Scored with the new `backend/quality/export_quality_check.py`,
which re-derives ground truth directly from `data/traces.json` rather than
trusting the exporter's own bookkeeping.

| Metric | Before | After | Target |
|---|---|---|---|
| SFT score | 83/100 | 100/100 | 90–95 |
| Sessions leaking >1 SFT row | 0/135 (already correct) | 0/135 | 0 |
| Exact duplicate `messages` arrays in sft.jsonl | 1 pair | 0 | 0 |
| Preference score | 68/100 | 100/100 | 90–95 |
| Weak-rating pairs produced | 0 | 8 | 8 |

Both bugs were fixed in `backend/exports/exclusion_rules.py` only — `generate_corpus.py`,
`content_bank.py`, `ingest.py`, backend routes, and the frontend were untouched.

## Bug 1 — SFT session collapsing

Investigation against the live corpus (405 traces / 135 sessions) found the
tiebreak logic in `select_session_representative` and the no-fallback rule
in `compute_sft_plan` were already correct for two of the three described
causes — no session produced more than one kept row, and no session ever
fell back to an earlier turn when its longest trace was excluded. The
concrete, reproducible defect was:

- **Cause A (duplicate content)**: two *different* sessions
  (`e968a1ca…`/`ae2ca8fd…`) produced byte-identical `messages` arrays in
  `sft.jsonl` — same conversation text, different trace/session/model —
  which the "no two rows may have identical `messages` arrays" rule
  correctly flags as a defect regardless of mechanism. Fixed by adding a
  hard uniqueness pass at the end of `compute_sft_plan`: every kept row is
  deduped by `trace_id` and by the exact `messages + [response]` content
  it would write, keeping the first occurrence and logging the rest under
  a new `duplicate_message_content` exclusion reason.
- **Cause B (fallback labeling)**: sessions where the longest trace failed
  a row-level check were already correctly dropped in full (no fallback to
  a shorter trace), but were bucketed under the underlying row reason
  (e.g. `truncated_response`), indistinguishable from a single-trace
  session simply failing that same check. Added a distinct
  `session_longest_trace_excluded` reason, applied only when the session
  had more than one trace (18 sessions in the real corpus).
- **Cause C (tie-break)**: the final tiebreak among same-turn candidates
  that survive retrial/continuation filtering used `timestamp`; changed to
  `len(messages)` per spec (unreachable in the current corpus, but now
  matches the documented rule and is covered by a new test).

Verification (`backend/quality/export_quality_check.py`, independent of
`exclusion_rules.py`): 0 sessions contribute more than one row to
`sft.jsonl`, 0 duplicate `messages` arrays — session collapsing correctness
scores the full 30/30 (pass/fail).

## Bug 2 — weak-rating preference pairs

Root cause: `compute_preference_plan`'s weak-rating pass skipped any trace
already present in `used_rejected_ids` — a set populated by the retrial
pass to avoid a trace being paired twice *for the same underlying event*.
In the real corpus, all 8 weak-feedback traces that have a valid
same-session/same-turn `ok`/`strong` candidate are *also* the discarded
side of a retrial at that exact turn, so this guard silently zeroed the
entire source (`docs/08-known-gaps.md` had documented this as a data-
scarcity limitation; it wasn't — the candidates existed, the loop just
never reached them).

Fix: the weak-rating pass no longer checks `used_rejected_ids` before
searching for a candidate — a trace being the losing side of a retrial and
a weak-rating candidate against the same winner are independent signals,
and both now produce a pair via the existing shared `make_preference_pair`
helper (no parallel implementation added). `metadata.source = "weak_rating"`
pairs are emitted for all 8 real candidates; the remaining 10 weak-feedback
traces with no same-turn candidate are still logged under
`no_pairing_candidate`, unchanged.

Verification: an independent scan of `traces.json` for same-session/
same-turn weak+`ok`/`strong` pairs finds exactly 8 candidates;
`preference.jsonl` now contains 8 `weak_rating` pairs, all verified to
match a real candidate — full 35/35.

## Full breakdown after the fix

```
SFT export score: 100.0 / 100
  content_coherence:                40.0 / 40  (110/110 rows, 100% keyword overlap)
  metadata_completeness:            15.0 / 15  (110/110 rows have all 5 fields)
  row_level_exclusion_correctness:  15.0 / 15  (0/110 rows fail a row-level check)
  session_collapsing_correctness:   30.0 / 30  (PASS — 0 duplicates, 0 leaking sessions)

Preference export score: 100.0 / 100
  zero_identical_pairs:             25.0 / 25  (PASS — 0 pairs with chosen == rejected)
  retrial_pairs_verified:           20.0 / 20  (20/20 match real retrial_of links)
  continuation_rejected_verified:   20.0 / 20  (10/10 match real continuation_status)
  weak_rating_source:               35.0 / 35  (8/8 independently-found candidates paired)
```

Regenerated `sft.jsonl` (110 rows, was 111 with a hidden duplicate) and
`preference.jsonl` (38 pairs, was 30) from the live corpus; the exclusion
report now shows `session_longest_trace_excluded` (18) and
`duplicate_message_content` (1) as new SFT reasons, and `weak_rating: 8`
in the preference pairs-by-source breakdown.

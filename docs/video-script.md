# Video walkthrough — narration script

Target: 2:30–3:00 spoken at ~140 wpm. Timestamps are cumulative cues for the
recording, not a hard clock — pace to the words, not the numbers.

---

[0:00–0:06] — ON SCREEN: terminal, `data/traces.db` / row count, or the
Trace Inspector's stats panel showing the total count.
"Every router call becomes a trace — prompt, model, cost, latency, outcome."

[0:06–0:18] — ON SCREEN: stay on the stats panel / corpus summary.
"This is synthetic data, not real Riften traffic — there's no production access here, so the corpus is generated entirely offline. Right now: 381 traces across 135 sessions, sitting in SQLite."

[0:18–0:23] — ON SCREEN: Trace Inspector loads, full table visible.
"This is the trace inspector — every trace, filterable and searchable."

[0:23–0:30] — ON SCREEN: click the Model filter, select `claude-3-5-sonnet`.
"Filter by model — here, just claude-3-5-sonnet calls."

[0:30–0:37] — ON SCREEN: clear that filter, toggle the Truncated flag on.
"Flip on Truncated to isolate responses that got cut off mid-sentence."

[0:37–0:44] — ON SCREEN: clear that, filter Feedback to "weak".
"Same with feedback — pull up just the weak-rated calls."

[0:44–0:51] — ON SCREEN: clear filters, let the full dark UI sit on screen a beat.
"Dark, monochrome, on purpose — it matches Riften's own minimal product design. Color only ever means state, never decoration."

[0:51–1:03] — ON SCREEN: click a trace row; detail panel opens showing transcript, metadata, and the two export-preview badges.
"Open one trace: full transcript, tool calls, cost, latency. And these two badges are new — live export status, right on the trace — excluded from SFT, but eligible as the rejected side of a preference pair."

[1:03–1:20] — ON SCREEN: open a session with multiple traces (Session Thread view), highlighting several rows sharing one session_id.
"Agent clients resend the whole conversation on every turn, so one real conversation shows up as several traces here. We keep only the longest one per session — everything shorter gets marked superseded."

[1:20–1:35] — ON SCREEN: terminal or editor, `data/exports/sft.jsonl` open, one line visible.
"From what's left, we drop anything rejected, anything that errored, anything truncated. What survives — 108 conversations out of 381 traces — becomes sft.jsonl."

[1:35–1:48] — ON SCREEN: `data/exports/preference.jsonl` open, a retrial pair visible.
"Preference pairs come from three places. A retrial: this response got a weak rating, so the retry becomes the accepted side, the original the rejected one."

[1:48–2:00] — ON SCREEN: scroll to a `continuation_rejected` pair.
"A rejected continuation: one branch issued a refund, the other upgraded an unrelated customer's plan — the refund wins. Weak ratings pair the same way, against a stronger response at the same turn, when one exists."

[2:00–2:08] — ON SCREEN: the app's `pairs_by_source` chip row, or the file's line count.
"Twenty-four pairs, all told, in preference.jsonl."

[2:08–2:20] — ON SCREEN: zoom on the `metadata` block of an open exported line.
"Every line carries a metadata block — model, tokens, cost, latency, feedback — kept separate from the training messages, so none of it ever leaks into what the model actually learns to say."

[2:20–2:34] — ON SCREEN: Exclusion Report panel or `exclusion_report.md`.
"Nothing here gets silently dropped. Two hundred seventy-three excluded traces, fourteen unpaired ones — every single one logged with a named reason, traceable back to its trace_id."

[2:34–2:48] — ON SCREEN: the model cost/quality tradeoff chart.
"That same show-your-work principle carries into this view — cost against quality, per model. It's literally testing Riften's own pitch: route to the cheapest model likely to succeed, against real data."

[2:48–2:58] — ON SCREEN: back to the Trace Inspector home view.
"That's raw router traffic turned into training data, with every drop explained. Next: because responses are keyed by session and turn, not by attempt, a retry can come out byte-identical to the response it replaced — that's what I'd fix first."

---

**Estimated runtime**: 396 spoken words ÷ 140 wpm ≈ **2:50**.

# Frontend

All paths relative to `/frontend/src` unless noted.

## Component tree

```
main.tsx
  └── App.tsx                                    (owns all state; see "State management" below)
        ├── <header>                              (inline JSX, not extracted — wordmark + Traces/Model tradeoff/Exclusion report nav buttons)
        ├── mainView === "traces":
        │     ├── FilterRail                       (components/FilterRail.tsx)
        │     │     ├── FilterSection ×5             (private, module-local)
        │     │     ├── ToggleRow ×2                  (private)
        │     │     └── RangeInputs ×2                (private)
        │     └── <main>
        │           ├── TraceTable                   (components/TraceTable.tsx)
        │           │     └── TraceStatusBadges       (components/StatBadge.tsx, exported alongside StatBadge)
        │           │           └── StatBadge ×N
        │           └── pagination bar                (inline JSX in App.tsx)
        ├── mainView === "tradeoff":
        │     └── ModelTradeoffView                  (components/ModelTradeoffView.tsx)
        │           ├── ModelTradeoffChart             (components/ModelTradeoffChart.tsx)
        │           │     └── Tooltip ×N                 (components/ui/Tooltip.tsx, one per plotted point)
        │           └── table (inline JSX)
        └── right panel (conditionally one of, based on `panel.kind`):
              ├── TraceDetail                       (components/TraceDetail.tsx)
              │     ├── MessageBubble ×N              (private, module-local)
              │     ├── ExportPreviewBadges           (components/ExportPreviewBadges.tsx)
              │     │     └── StatBadge ×2              (components/StatBadge.tsx)
              │     └── StatBadge ×N                  (components/StatBadge.tsx)
              ├── SessionThread                      (components/SessionThread.tsx)
              │     └── StatBadge ×N
              └── ExclusionPanel                     (components/ExclusionPanel.tsx)
                    └── ReasonTable ×2                 (private, module-local)
                          (button per sample trace_id, calls back up to App.tsx's setPanel)
```

There is no router and no nested route components — the "page" is always
`App.tsx`; navigation between trace detail / session thread / exclusion
report is modeled as a single `panel` state value (a discriminated union,
`App.tsx`) that swaps which component renders in the right-hand column, and
independently a `mainView: "traces" | "tradeoff"` state value swaps which
content fills the main (non-panel) area. The two are orthogonal — switching
`mainView` does not close whatever `panel` is open, so a trace detail panel
opened from the Traces tab stays open while browsing the Model tradeoff
tab.

## `main.tsx`

Entry point. `createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)`
— unmodified from the Vite `react-ts` template scaffold. No props, no
state.

## `App.tsx`

The only stateful component in the app. Owns:

| State | Type | Set by |
|---|---|---|
| `filters` | `TraceFilters` | `FilterRail`'s `onChange` |
| `page` | `number` | pagination buttons; reset to `1` whenever `filters` changes (line 40-42) |
| `traces` | `TraceSummary[]` | resolved `fetchTraces()` response |
| `total` | `number` | resolved `fetchTraces()` response, drives `FilterRail`'s live result count and the pagination label |
| `stats` | `Stats \| null` | resolved `fetchStats()` response |
| `tableLoading` | `boolean` | true while a `fetchTraces` call is in flight — drives an `opacity-50` class on the table wrapper (line 151), not a spinner |
| `panel` | `Panel` (discriminated union) | click handlers passed down to `TraceTable`, `TraceDetail`, `SessionThread`, `ExclusionPanel`, and the header's "Exclusion report" button |
| `traceDetail` | `TraceDetailT \| null` | resolved `fetchTrace()` response, only relevant when `panel.kind === "trace"` |
| `session` | `SessionResponse \| null` | resolved `fetchSession()` response, only relevant when `panel.kind === "session"` |
| `exclusionReport` | `ExclusionReport \| null` | resolved `fetchExclusionReport()` response, only relevant when `panel.kind === "exclusions"` |
| `panelLoading` | `boolean` | true while any of the three panel fetches above is in flight |
| `mainView` | `"traces" \| "tradeoff"` | the header's "Traces"/"Model tradeoff" nav buttons |
| `tradeoff` | `ModelTradeoff[] \| null` | resolved `fetchModelTradeoff()` response, only fetched while `mainView === "tradeoff"` |
| `tradeoffLoading` | `boolean` | true while the tradeoff fetch is in flight |
| `exportPreview` | `ExportPreview \| null` | resolved `fetchExportPreview(traceId)` response, fetched alongside `traceDetail` whenever `panel.kind === "trace"` |
| `exportPreviewLoading` | `boolean` | true while the export-preview fetch is in flight |

Six `useEffect` hooks:
1. `[filters]` → reset `page` to 1.
2. `[filters, page]` → `fetchTraces`, sets `traces`/`total`/`tableLoading`.
3. `[filters]` → `fetchStats`, sets `stats`. Runs in parallel
   with #2 on every filter change (both keyed on `filters`, but this one
   isn't also keyed on `page` — changing page alone does not refetch stats).
4. `[mainView]` → fires only when `mainView === "tradeoff"`; calls
   `fetchModelTradeoff()`, sets `tradeoff`/`tradeoffLoading`. Fetched once
   per switch into the tab, not re-fetched on every render, and not
   filtered by the Traces tab's `filters` state (the tradeoff view has no
   filter UI — it always summarizes the whole corpus).
5. `[panel]` → branches on `panel.kind`; for `"trace"` fires **two**
   parallel fetches (`fetchTrace` and `fetchExportPreview`, both keyed off
   the same `panel.id`) so the export-eligibility badges load automatically
   alongside the transcript rather than needing a separate action; for
   `"session"`/`"exclusions"` fires the matching single fetch; clears the
   other panel state slots on every branch, including `exportPreview` on
   the final "none" fallthrough. Every branch uses a local `cancelled` flag
   closed over the effect's cleanup function to avoid setting state after a
   newer panel selection has superseded an in-flight request — standard
   React fetch-in-effect race guard, not a library.

No `try`/`catch` around any fetch call, and no error state anywhere in the
component — a failed request just leaves the relevant `useState` at its
initial value, so the render for that state is indistinguishable from "no
data yet" (see `docs/02-workflow.md`'s note on the backend-not-running
case).

Render: a `flex h-screen flex-col` root — header, then a `flex min-h-0
flex-1` row containing `FilterRail`, the `<main>` table+pagination column,
and (conditionally, `panel.kind !== "none"`) a fixed `w-[520px]` right
column that renders exactly one of `TraceDetail`/`SessionThread`/`ExclusionPanel`
based on `panel.kind` (lines 181-208).

## `api/client.ts`

The entire HTTP layer — seven exported async functions, no class, no
generated client, no caching layer:

| Function | Route | Called from |
|---|---|---|
| `fetchTraces(filters, page, pageSize)` | `GET /api/traces?...` | `App.tsx` effect #2 |
| `fetchTrace(traceId)` | `GET /api/traces/{id}` | `App.tsx` effect #5, `panel.kind === "trace"` |
| `fetchSession(sessionId)` | `GET /api/sessions/{id}` | `App.tsx` effect #5, `panel.kind === "session"` |
| `fetchStats(filters)` | `GET /api/stats?...` | `App.tsx` effect #3 |
| `fetchExclusionReport()` | `GET /api/export/exclusions` | `App.tsx` effect #5, `panel.kind === "exclusions"` |
| `fetchModelTradeoff()` | `GET /api/stats/model-tradeoff` | `App.tsx` effect #4, `mainView === "tradeoff"` |
| `fetchExportPreview(traceId)` | `GET /api/traces/{id}/export-preview` | `App.tsx` effect #5, `panel.kind === "trace"` (alongside `fetchTrace`) |

`filtersToParams(filters, extra?)` (lines 12-27) is the one piece of shared
logic: it builds a `URLSearchParams` from a `Partial<TraceFilters>`,
`append`-ing `model` and `feedback` once per array element (matching
FastAPI's repeated-query-param convention for `list[str]` params) and
`set`-ting scalar filters only when non-null. Every function prefixes its
path with `const BASE = "/api"` (line 10), which is what the Vite dev-server
proxy (`vite.config.ts`) rewrites to the backend's real root.

## `components/StatBadge.tsx`

Two exports:
- `StatBadge({label, tone})` — a single `<span>` pill. `tone` is one of
  `"neutral" | "accent" | "dim"`, mapped to Tailwind classes referencing the
  CSS custom properties from `index.css` (`--border-strong`/`--text`,
  `--accent`/`--accent`, `--border`/`--text-faint` respectively, lines 3-7).
  This is the one place in the codebase where the "one accent color, used
  only for state" rule from the design brief is enforced structurally —
  every other component that wants to signal error/truncated/weak state
  goes through this component's `tone="accent"` rather than hardcoding a
  color.
- `TraceStatusBadges({errored, truncated, feedback})` — composes multiple
  `StatBadge`s: an `Error` badge (accent) if `errored`, a `Truncated` badge
  (accent) if `truncated`, an `OK` badge (dim) if neither, and a feedback
  badge if `feedback` is non-null (accent only when `feedback === "weak"`,
  dim otherwise). This is the "answers 'is this usable for training data'
  at a glance" component from the design brief, and it's used identically
  in both `TraceTable` (compact row view) and inlined manually — not
  reused — in `TraceDetail` and `SessionThread`'s per-turn rows (those two
  compose `StatBadge` directly rather than calling `TraceStatusBadges`,
  because they need extra badges — `Retrial`, `continuation: accepted`,
  etc. — interleaved with the status ones).

## `components/TraceTable.tsx`

Props: `{traces: TraceSummary[], onSelect: (id: string) => void,
selectedId: string | null}`. No local state. Renders a single `<table>` with
7 columns (`HEADERS`, line 18: Status, Model, Turn, Tokens, Cost, Latency,
Timestamp). `isErrored`/`isTruncated` (lines 10-16) are pure functions
derived from `status_code`/`has_tool_error`/`finish_reason` — no separate
"errored" flag is stored anywhere; it's recomputed from the raw fields on
every render. Row click calls `onSelect(t.trace_id)`; the selected row gets
`bg-[var(--bg-hover)]` instead of the hover style. Empty state: a single
full-width cell reading "No traces match the current filters." (lines
69-75) when `traces.length === 0` — this is the only explicit empty-state
render in the whole frontend.

## `components/FilterRail.tsx`

Props: `{filters, onChange, stats, resultCount}`. No local state — this is
a fully controlled component; every checkbox/button mutates `filters` via
`onChange({...filters, ...})` and waits for the new value to flow back down
from `App.tsx`. Sections, top to bottom: a result-count summary (reads
`resultCount` and, if `stats` is loaded, `stats.total`/`error_rate`/
`truncated_rate`); Model (checkbox per `ALL_MODELS`, with a live per-model
count from `stats.per_model`); Feedback (toggle buttons, multi-select via
`toggleInArray`); Cost range and Latency range (two `RangeInputs` pairs);
Flags (two `ToggleRow`s — `truncated`/`errored` are 3-state:
`null`→`true`→`null`, never `false`, since `ToggleRow`'s `onClick` only ever
sets `true` or clears to `null`, line 164 — there's no UI path to
explicitly request `truncated=false`, even though the backend filter
supports it); a conditional "Session" section showing the active
`session_id` filter with a clear button, only rendered when one is set
(this is how the app surfaces that you're viewing a single session's
traces after following a "session xyz → turn N" link from `TraceDetail`);
and a "Reset all filters" button that replaces the whole `filters` object
with a fresh all-null/all-empty literal (not imported from `EMPTY_FILTERS`
— it's a separate inline object literal, lines 122-132, that happens to
match `EMPTY_FILTERS`'s shape).

## `components/TraceDetail.tsx`

Props: `{trace: TraceDetailT | null, loading: boolean, exportPreview:
ExportPreview | null, exportPreviewLoading: boolean, onOpenSession:
(sessionId: string) => void, onSelectTrace: (traceId: string) => void,
onClose: () => void}`. No local state. Three render branches: `loading` →
centered "Loading…" text; `!trace` → centered "Select a trace to inspect
it." (the initial/no-selection state); otherwise the populated view: a
header row with the `trace_id`, computed `errored`/`truncated` badges plus
`feedback`/`is_retrial`/`continuation_status` badges, an `ExportPreviewBadges`
row (see below), and a button reading `session {id} → turn {turn_index}`
that calls `onOpenSession` (this is the only way to reach the session view
from the UI); a 4-column metadata grid (Model, Status, Finish, Latency,
Prompt tok, Completion tok, Cost, Timestamp — 8 cells in a 4-column grid);
the transcript, rendered as one `MessageBubble` per entry in
`trace.messages` plus one more for `trace.response` (labelled `"assistant
(response)"` rather than reusing the `"assistant"` role string, so it's
visually distinguishable from an assistant turn that was already part of
the resent context); and, if `tool_calls` is non-empty, a Tool calls
section listing each call's name, a status badge, and pretty-printed
`args`/`result.output` JSON in `<pre>` blocks.

## `components/ExportPreviewBadges.tsx`

Props: `{preview: ExportPreview | null, loading: boolean, onSelectTrace:
(traceId: string) => void}`. Renders inside `TraceDetail`'s header,
immediately below the error/truncated/feedback badge row, and fetches
nothing itself — `App.tsx` fetches `fetchExportPreview(traceId)` in the
same effect that fetches the trace, so this section populates automatically
the moment a trace is opened rather than requiring a separate click. Two
`StatBadge`s: one for `preview.sft` (`"SFT: included"` in `success` tone,
or `"SFT: excluded — {reason}"` in `error` tone, each wrapped in a
`Tooltip` showing `preview.sft.detail` — the human-readable explanation,
e.g. naming the specific superseding trace_id for
`superseded_by_longer_session_trace`); one for `preview.preference`
(`"Preference: eligible — {role} side ({source})"` in `info` tone when
`eligible`, `"Preference: not eligible"` in `dim` tone otherwise). When
eligible and `paired_with_trace_id` is set, a small button reading `paired
with #{shortId}` sits next to the preference badge and calls
`onSelectTrace(paired_with_trace_id)` — in `App.tsx` this is wired to the
same `(id) => setPanel({kind: "trace", id})` handler used everywhere else,
so clicking it swaps the detail panel straight to the paired trace (the
chosen or rejected counterpart of the same pair).

## `components/SessionThread.tsx`

Props: `{session: SessionResponse | null, loading: boolean, onSelectTrace:
(id: string) => void, onClose: () => void}`. No local state. Computes
`byTurn` (all of the session's traces sorted by `turn_index`) and `longest`
(the trace with the most `messages` — a client-side re-derivation of the
same "longest transcript wins" rule the backend's SFT export applies
server-side, done independently here rather than relying on the backend to
flag which trace is the canonical one). Renders the full transcript from
`longest.messages` first, then a "Traces by turn" list — one row per trace
in the session (not collapsed), each clickable through to `onSelectTrace`,
showing turn number, model, and the same badge vocabulary as
`TraceDetail`'s header (retrial/error/truncated/feedback).

## `components/ExclusionPanel.tsx`

Props: `{report: ExclusionReport | null, loading: boolean, onClose: () =>
void, onInspectTrace: (id: string) => void}`. No local state.
`ReasonTable({excluded, onInspectTrace})` (lines 10-44) is a private helper
rendering one bordered block per exclusion reason, with the count in accent
color and up to 5 sample `trace_id`s as small buttons — clicking one calls
`onInspectTrace(id)`, which in `App.tsx` is wired to `(id) => setPanel({kind:
"trace", id})` (App.tsx:204), so clicking a sample trace_id swaps the right
panel from the exclusion report straight into that trace's detail view.
The panel itself has two `<section>`s (SFT export, Preference pair export),
each showing summary counts above its `ReasonTable`.

## `components/ModelTradeoffView.tsx`

Props: `{items: ModelTradeoff[] | null, loading: boolean}`. Rendered by
`App.tsx` in place of `FilterRail` + `TraceTable` when `mainView ===
"tradeoff"` — this tab has no filters, since it always summarizes the
whole corpus. Three render branches: `loading || !items` → skeleton cards;
`items.length === 0` → empty-corpus state; otherwise a `Card` containing
`ModelTradeoffChart` above a plain `<table>` with one row per model
(Model, Traces, Avg cost, Avg latency, Avg quality, Error rate, Truncation
rate, Avg prompt/completion tokens) — the table exists so anyone who wants
exact figures doesn't have to read them off the scatter plot. The Avg
quality cell (`QualityCell`, module-local) renders `"no feedback data"` in
muted text instead of a bare `0.00` when `avg_quality_score` is `null`,
otherwise the score plus a `(NN% coverage)` qualifier from
`feedback_coverage` — the same "don't silently hide that the score is
based on a subset" rule the chart follows.

## `components/ModelTradeoffChart.tsx`

Props: `{items: ModelTradeoff[]}`. A hand-rolled inline SVG scatter plot —
no charting library is added; the frontend has none installed and this is
a single scatter with five points, well within what plain SVG handles.
X-axis is `avg_cost_usd` on a **log scale** (cost spans roughly two orders
of magnitude across the five models, so a linear scale would collapse the
cheap, high-volume models into a single pixel cluster); Y-axis is
`avg_quality_score`, fixed `0`–`1`. Point radius encodes `trace_count`
(`radiusFor`, `sqrt`-scaled so area rather than radius tracks volume
linearly). Color is a **fixed** model→color assignment
(`utils/modelColors.ts`) reusing the app's existing `--accent`/`--info`/
`--brand`/`--success`/`--warning` tokens in `ALL_MODELS` order, rather than
introducing a new palette — this keeps the chart in the same visual
language as the rest of the inspector (status badges use the same five
tokens for unrelated purposes) instead of adding a second color system. A
model with `avg_quality_score === null` (zero feedback coverage) is
**excluded from the plot entirely** rather than plotted at a misleading
`y=0` — its name appears instead in a "Not plotted (no feedback coverage
yet): …" note below the chart. Each point is wrapped in the existing
`Tooltip` component (hover shows model, quality + coverage, cost, trace
count); a legend row below the chart maps color → model name (no separate
legend component — inline JSX, since this is the only place model colors
are shown).

## `utils/modelColors.ts`

`colorForModel(model: string): string` — the fixed model→CSS-variable
lookup described above. Not derived from `stats.per_model` or any
API response; the assignment is a module-level constant built once from
`ALL_MODELS`, so a model's color never changes based on which models
happen to appear in the current result set.

## Types

- `types/trace.ts` — `Model`, `FinishReason`, `Feedback`,
  `ContinuationStatus` (string literal unions mirroring `schema.py`'s
  `Literal` types, but not generated from them — hand-kept in sync);
  `Message`, `ToolCallResult`, `ToolCall`; `TraceSummary` (the `/traces`
  list-item shape, includes `has_tool_error` which only exists on this
  shape); `TraceDetail` (`Omit<TraceSummary, "has_tool_error"> &
  {messages, response, tool_calls}` — modeled as an extension so the two
  types can't silently drift on their shared fields); `TracesResponse`,
  `SessionResponse`, `Stats`; `TraceFilters` (the UI-side filter state
  shape, using `string[]` for `model`/`feedback` rather than the narrower
  `Model[]`/`Feedback[]`, since `EMPTY_FILTERS` and the reset button both
  need a plain empty-array default); `EMPTY_FILTERS`, `ALL_MODELS`,
  `ALL_FEEDBACK` constants.
- `types/exclusion.ts` — `ExclusionReasonSummary` (`{count, sample_trace_ids}`)
  and `ExclusionReport` (`{sft: {...}, preference: {...}}`), mirroring the
  dict shape `exclusion_report.build_exclusion_report()` returns field for
  field.
- `types/modelTradeoff.ts` — `ModelTradeoff` (one row per model: `model`,
  `trace_count`, `avg_cost_usd`, `avg_latency_ms`, `avg_tokens_prompt`,
  `avg_tokens_completion`, `avg_quality_score: number | null`,
  `feedback_coverage`, `error_rate`, `truncation_rate`) and
  `ModelTradeoffResponse` (`{items: ModelTradeoff[]}`), mirroring
  `model_tradeoff.compute_model_tradeoff()`'s return shape field for field.
- `types/exportPreview.ts` — `SftPreview` (`{included, reason, detail}`),
  `PreferencePreview` (`{eligible, role, source, paired_with_trace_id,
  detail}`), and `ExportPreview` (`{sft: SftPreview, preference:
  PreferencePreview}`), mirroring `export_preview.build_export_preview()`'s
  return shape field for field.

## Styling

Tailwind v4, wired via the `@tailwindcss/vite` plugin (`vite.config.ts:3,7`)
rather than a `tailwind.config.js` + PostCSS pipeline — there is no
`tailwind.config.*` file in this repo. `src/index.css` does three things:
`@import "tailwindcss"` (line 1, pulls in the framework); defines the
entire design system as CSS custom properties on `:root` (lines 3-19) —
`--bg`, `--bg-raised`, `--bg-hover`, `--border`, `--border-strong`,
`--text`, `--text-dim`, `--text-faint`, `--accent`, `--accent-dim`,
`--mono`, `--sans`; and a handful of global element rules (box-sizing reset,
full-height html/body/#root, selection color, scrollbar styling, monospace
on `code`/`pre`). Every component references these tokens through Tailwind
arbitrary-value syntax — `bg-[var(--bg)]`, `text-[var(--text-faint)]`,
`border-[var(--border)]` — rather than Tailwind's built-in color palette, so
"pure black, no gradients, one accent used only for state" is enforced by
there being literally only one color token (`--accent`) that isn't
gray/black/white in the whole stylesheet. There's no dark-mode media query
or `[data-theme]` branching — the app is black-on-black-adjacent
unconditionally, matching the "no light mode" requirement from the design
brief.

Type scale is informal — `text-[10px]` (badges, labels), `text-[11px]`
(most UI chrome), `text-[12px]`/`text-[12.5px]` (table rows, transcript
body), `text-[14px]` (the "riften" wordmark) — declared per-element via
Tailwind arbitrary values rather than a shared scale of named sizes.

## State management

Plain React local state (`useState`) plus `useEffect` for data fetching,
entirely inside `App.tsx`. No Context, no Redux/Zustand/Jotai, no
React Query/SWR — every fetch is a hand-written `useEffect` with a
`cancelled` boolean closure for race-safety and no caching, retries, or
shared query keys. Filter state, the currently selected trace/session/panel,
and every fetched response live as sibling `useState` slots in the single
top-level component; child components are entirely presentational and
receive both data and callbacks as props, with `FilterRail` in particular
being a fully controlled component that owns no state of its own.

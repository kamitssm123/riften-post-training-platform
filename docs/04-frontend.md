# Frontend

All paths relative to `/frontend/src` unless noted.

## Component tree

```
main.tsx
  └── App.tsx                                    (owns all state; see "State management" below)
        ├── <header>                              (inline JSX, not extracted — wordmark + "Exclusion report" nav button)
        ├── FilterRail                            (components/FilterRail.tsx)
        │     ├── FilterSection ×5                 (private, module-local)
        │     ├── ToggleRow ×2                      (private)
        │     └── RangeInputs ×2                    (private)
        ├── <main>
        │     ├── TraceTable                       (components/TraceTable.tsx)
        │     │     └── TraceStatusBadges           (components/StatBadge.tsx, exported alongside StatBadge)
        │     │           └── StatBadge ×N
        │     └── pagination bar                    (inline JSX in App.tsx)
        └── right panel (conditionally one of, based on `panel.kind`):
              ├── TraceDetail                       (components/TraceDetail.tsx)
              │     ├── MessageBubble ×N              (private, module-local)
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
`App.tsx:20-24`) that swaps which component renders in the right-hand
column.

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

Four `useEffect` hooks:
1. `[filters]` → reset `page` to 1 (lines 40-42).
2. `[filters, page]` → `fetchTraces`, sets `traces`/`total`/`tableLoading`
   (lines 44-56).
3. `[filters]` → `fetchStats`, sets `stats` (lines 58-66). Runs in parallel
   with #2 on every filter change (both keyed on `filters`, but this one
   isn't also keyed on `page` — changing page alone does not refetch stats).
4. `[panel]` → branches on `panel.kind`; for `"trace"`/`"session"`/`"exclusions"`
   fires the matching fetch and clears the other two panel state slots; for
   `"none"` clears `traceDetail` and `session` (lines 68-114). Every branch
   uses a local `cancelled` flag closed over the effect's cleanup function
   to avoid setting state after a newer panel selection has superseded an
   in-flight request — standard React fetch-in-effect race guard, not a
   library.

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

The entire HTTP layer — five exported async functions, no class, no
generated client, no caching layer:

| Function | Route | Called from |
|---|---|---|
| `fetchTraces(filters, page, pageSize)` | `GET /api/traces?...` | `App.tsx` effect #2 |
| `fetchTrace(traceId)` | `GET /api/traces/{id}` | `App.tsx` effect #4, `panel.kind === "trace"` |
| `fetchSession(sessionId)` | `GET /api/sessions/{id}` | `App.tsx` effect #4, `panel.kind === "session"` |
| `fetchStats(filters)` | `GET /api/stats?...` | `App.tsx` effect #3 |
| `fetchExclusionReport()` | `GET /api/export/exclusions` | `App.tsx` effect #4, `panel.kind === "exclusions"` |

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

Props: `{trace: TraceDetailT | null, loading: boolean, onOpenSession:
(sessionId: string) => void, onClose: () => void}`. No local state. Three
render branches: `loading` → centered "Loading…" text; `!trace` → centered
"Select a trace to inspect it." (the initial/no-selection state); otherwise
the populated view: a header row with the `trace_id`, computed
`errored`/`truncated` badges plus `feedback`/`is_retrial`/
`continuation_status` badges, and a button reading `session {id} → turn
{turn_index}` that calls `onOpenSession` (this is the only way to reach the
session view from the UI); a 4-column metadata grid (Model, Status, Finish,
Latency, Prompt tok, Completion tok, Cost, Timestamp — 8 cells in a
4-column grid, lines 80-88); the transcript, rendered as one `MessageBubble`
per entry in `trace.messages` plus one more for `trace.response` (labelled
`"assistant (response)"` rather than reusing the `"assistant"` role string,
so it's visually distinguishable from an assistant turn that was already
part of the resent context); and, if `tool_calls` is non-empty, a Tool
calls section listing each call's name, a status badge, and pretty-printed
`args`/`result.output` JSON in `<pre>` blocks.

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

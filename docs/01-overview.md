# Overview

This project turns raw router traffic — the call-by-call traces a router/gateway
product like Riften captures as it sends each request to the cheapest model
likely to complete it correctly — into post-training data: OpenAI-format SFT
conversations and chosen/rejected preference pairs, plus a UI for inspecting
the underlying traces before anything gets exported. All data is synthetic,
generated locally by `backend/generation/generate_corpus.py`; nothing here
talks to a real model provider or real user traffic.

## System diagram

```
                    ┌────────────────────────────────┐
                    │  generation/generate_corpus.py │   random.seed(42)
                    │  (backend/)                    │
                    └────────────────┬───────────────┘
                                 │ writes
                                 ▼
                    /data/traces.json  (intermediate, gitignored)
                                 │
                                 │ python -m db.ingest
                                 ▼
                    /data/traces.db  (SQLite, single `traces` table)
                                 │
                                 │ read by
                                 ▼
                    ┌───────────────────────────────────┐
                    │  api/main.py (FastAPI)            │    uvicorn api.main:app --port 8000
                    │  GET  /traces                     │
                    │  GET  /traces/{id}                │
                    │  GET  /traces/{id}/export-preview │
                    │  GET  /sessions/{id}              │
                    │  GET  /stats                      │
                    │  GET  /stats/model-tradeoff       │
                    │  POST /export/sft                 │───┐
                    │  POST /export/preference          │───┤
                    │  GET  /export/exclusions          │───┤
                    └─────────────────────────────────┬──┘   │
                                                       │ JSON over HTTP       │ also runnable
                                                       │ (CORS: allow_origins=["*"])
                                                       ▼                      ▼
                    ┌─────────────────────────┐   /data/exports/sft.jsonl
                    │  frontend (Vite/React)  │   /data/exports/preference.jsonl
                    │  dev server :5173        │   /data/exports/exclusion_report.md
                    │  proxies /api -> :8000   │
                    └─────────────────────────┘
```

The export scripts (`exports/export_sft.py`, `exports/export_preference.py`,
`exports/exclusion_report.py`) read the same SQLite database as the API and
can be run either as standalone scripts or triggered through the API's
`POST`/`GET` `/export/*` routes — both paths call the same Python functions
(`build_sft_export`, `build_preference_export`, `build_exclusion_report`), so
there is exactly one implementation of the export logic, not two.

## Tech stack

| Piece | Library | Version in use | Why this, for this project |
|---|---|---|---|
| Backend framework | FastAPI | 0.128.8 (installed; unpinned in `backend/requirements.txt`) | Query-param based filtering (`Optional[list[str]]`, range params) maps directly onto FastAPI's function-signature routing with no request-parsing boilerplate, and it ships an interactive `/docs` page for free — useful for a project whose main deliverable is a set of filterable read endpoints. |
| ASGI server | uvicorn (`[standard]` extra) | 0.39.0 | Standard pairing with FastAPI; the `[standard]` extra pulls in `httptools`/`uvloop` for local dev reload, nothing exotic needed here. |
| Backend language runtime | Python | 3.9.6 (venv interpreter) | `from __future__ import annotations` is used throughout specifically so 3.9 accepts the `list[str] \| None`-style type hints written for a newer-Python audience while still running on whatever `python3` resolves to locally. |
| Database | SQLite (stdlib `sqlite3`) | bundled with Python 3.9.6 | The corpus is 381 rows in one table (see `docs/06-dataset.md`); there are no concurrent writers (ingest is a single wipe-and-reload batch job) and no need for a server process — a file at `/data/traces.db` is the entire deployment story. `sqlite3`'s JSON1 functions (`json_each`, `json_extract`) are used directly in `api/main.py`'s `errored` filter to reach into the `tool_calls` JSON column without a second table. |
| Test runner | pytest | 8.4.2 | 42 tests across 6 files (`backend/tests/`) use `monkeypatch` to redirect each module's file-path globals (`DB_PATH`, `OUT_PATH`, `EXPORTS_DIR`) into `tmp_path`, so tests never touch the real `/data` directory. |
| HTTP test client | httpx (via `fastapi.testclient.TestClient`) | 0.28.1 | Required by `TestClient` in this FastAPI version; used only in `tests/test_main.py`. |
| Frontend framework | React | 19.2.8 | Function components + hooks (`useState`/`useEffect`) are the entire state model in `App.tsx` — no global store, no routing library, because the whole UI is one screen with a right-hand panel that swaps content. Navigation is real, shareable URLs via a hand-rolled `pushState`/`popstate` router (`hooks/useRouter.ts`, `routes.ts`), not a client-side routing library. |
| Frontend language | TypeScript | 6.0.3 | Every API response shape is declared once in `frontend/src/types/trace.ts` and `types/exclusion.ts` and imported by both the fetch client and the components that render the data, so a backend field rename fails the build (`tsc -b`) instead of failing silently at render time. |
| Build tool / dev server | Vite | 8.2.1 | `vite.config.ts` proxies `/api/*` to `http://127.0.0.1:8000` and strips the `/api` prefix, so the frontend fetch client never hardcodes a backend origin and the same code works against the dev server or a future same-origin deploy. |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`) | 4.3.3 | v4's CSS-first config means the entire design system — pure-black background, one accent color, the type/spacing scale — lives as CSS custom properties in `frontend/src/index.css` rather than a separate `tailwind.config.js`; utility classes reference those tokens (`bg-[var(--bg)]`, `text-[var(--accent)]`) directly. |
| Linter | oxlint | 1.75.0 | Fast, zero-config linting for the frontend (`npm run lint`); not wired into CI or a pre-commit hook in this repo. |

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
/data       generated traces.json + traces.db + exports/ (gitignored, kept via .gitkeep)
/docs       this documentation set
```

Every subpackage under `/backend` (except `tests/`) has an `__init__.py`
and is imported with its full dotted path (e.g. `from core.schema import
Trace`, `from exports.export_sft import fetch_all_traces`). Run any module
as a script with `python -m <package>.<module>` (e.g. `python -m
generation.generate_corpus`) rather than `python <module>.py`, and cwd must
be `/backend` — both `python -m` and `uvicorn api.main:app` add the current
directory to `sys.path`, which is what makes the dotted imports resolve.

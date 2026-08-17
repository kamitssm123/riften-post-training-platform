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
- **Frontend**: React + TypeScript, Vite, Tailwind.
- **Storage**: SQLite (file-based, zero setup, fine for a few hundred rows).

## Directory layout

```
/backend    FastAPI app, schema, generator, ingest, exports, tests
/frontend   React + TS + Vite + Tailwind inspector UI
/data       generated traces (sqlite db) + exports (gitignored, kept via .gitkeep)
/docs       supporting docs
```

## Setup & run

(To be finalized in Phase 7 — this section will be filled in as each phase
lands.)

```bash
# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Generate + load synthetic corpus
python generate_corpus.py
python ingest.py

# Run API
uvicorn main:app --reload

# Frontend
cd ../frontend
npm install
npm run dev
```

## Design decisions

(Documented in full in Phase 7 — see README section "Design decisions where
the spec was ambiguous".)

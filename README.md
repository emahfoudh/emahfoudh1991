# AI IT Operations — MVP (Phase 1 + Phase 2)

Turns fragmented IT operational data into an executive report. This
is the MVP: synthetic data only, no live connection to any real
company's systems (including Driven Properties — this project is
fully isolated from that production environment).

## What this does right now

```
synthetic CSVs (tickets + network samples)
   -> connectors (normalize into common data model)
   -> KPI engines (SLA, MTTR, aging, recurring problems, bandwidth/latency/uptime)
   -> AI report generator (Claude, or a template fallback with no API key)
   -> PDF + Excel executive report
```

Nothing here calls a real vendor API, and no employer credentials or
data are used anywhere in this repo. Everything runs on generated
synthetic data (`data/generate_synthetic_data.py`).

## Run it locally (no Docker)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# generate synthetic data (only needs to be done once)
.venv/bin/python data/generate_synthetic_data.py

# run the full pipeline
.venv/bin/python main.py
```

Output lands in `output/executive_report.pdf` and `output/executive_report.xlsx`.

### Using a real AI-generated report instead of the template

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. Without a
key, the pipeline still runs end to end — it just uses a plain,
deterministic template instead of Claude's narrative. This is
intentional: the pipeline should never break just because a key isn't
configured yet.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
.venv/bin/python main.py
```

## Run it with Docker

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY if you have one
docker compose up --build
```

## Run the tests

```bash
.venv/bin/python -m pytest tests/ -v
```

## Phase 2: persistence + read-only API

`main.py` now also writes every run's tickets, network samples, KPI
snapshot, and report into a local SQLite file (`ai_it_operations.db`,
gitignored — it's generated data, not source). A minimal read-only
API serves the latest snapshot/report from that database:

```bash
.venv/bin/uvicorn api.app:app --reload
# then in another terminal:
curl http://127.0.0.1:8000/kpi-snapshot/latest
curl http://127.0.0.1:8000/report/latest
```

This has no auth and no write endpoints — there's no real customer
or role system to protect yet, and it's not meant to be exposed
beyond your own machine. It exists to prove the pipeline's output can
be served over HTTP, which is what a future dashboard will build on.

## Project structure

- `connectors/` — one file per data source. `base.py` defines the interface every connector (synthetic or real) must implement: `authenticate()`, `fetch()`, `normalize()`. This is what lets a real Zoho/Sophos/FortiGate connector slot in later without touching anything downstream.
- `engines/` — pure calculation code, no AI, no I/O. `kpi_engine.py` computes ticket SLA/MTTR/aging/recurring problems. `network_engine.py` computes bandwidth under-delivery, latency, packet loss, uptime, and flags problem sites.
- `ai/` — `prompts.py` defines the strict system prompt (only use provided data, say "Insufficient data" rather than invent). `report_generator.py` calls Claude with the engines' *output only* — never raw tickets/logs — and falls back to a deterministic template if no API key is set or the call fails.
- `reporting/` — renders the same report data as PDF (via WeasyPrint, styled HTML/CSS) and Excel (via openpyxl).
- `data/` — synthetic data generator and the generated CSVs.
- `tests/` — unit tests for the KPI engines (the deterministic core — if a number is wrong, it's wrong here and a test should catch it).

## Why it's built this way (for when you explain this to a customer or the COO)

- **Connector interface is the product.** The reason this can eventually support "Customer A on Zoho, Customer B on ServiceNow" without a rewrite is that every connector produces the same normalized shape. Engines/AI/reporting never know which vendor the data came from.
- **The AI never sees raw data.** It receives aggregated KPI numbers and flagged anomalies — small, bounded, and checkable — not thousands of log lines. That's what makes "Insufficient data" possible instead of the model guessing.
- **Every number has a test.** SLA%, MTTR, aging, and network flagging are pure functions with unit tests. This is what makes the eventual "trust me, this dashboard is right" conversation with a COO defensible — the math is auditable, independent of whether the AI wording is good that day.
- **Secrets never touch git.** `.env` is gitignored; `.env.example` shows the shape with no real values. This habit is what makes a future real-customer integration safe to build on top of this codebase without re-architecting security in.

## What's deliberately NOT built yet

Real vendor connectors (Zoho/Sophos/FortiGate/M365), live dashboard, multi-tenancy, auth, cost/contract module, scheduling. See the architecture roadmap discussed with the project owner for phased build-out — each of those is designed for, not built, until this MVP loop is proven.

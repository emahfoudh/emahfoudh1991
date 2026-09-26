# AI IT Operations — MVP (Phase 1 + 2 + 3 + 4 + 5)

Turns fragmented IT operational data into an executive report. Phases
1-2 are synthetic-data only. Phase 3 adds the first real connector —
Zoho Desk — but ONLY against a personal sandbox org, never a real
employer's tenant. This project has no code path that has ever
touched, or is permitted to touch, Driven Properties' systems.

## What this does right now

```
synthetic CSVs (tickets + network samples + vendor contracts)
   -> connectors (normalize into common data model)
   -> KPI engines (SLA, MTTR, aging, recurring problems, bandwidth/latency/uptime,
                    cost/renewal risk, license utilization)
   -> AI report generator (Claude, or a template fallback with no API key)
   -> PDF + Excel executive report + read-only dashboard
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
# then in another terminal, or open the dashboard URL in a browser:
curl http://127.0.0.1:8000/kpi-snapshot/latest
curl http://127.0.0.1:8000/report/latest
```

This has no auth and no write endpoints — there's no real customer
or role system to protect yet, and it's not meant to be exposed
beyond your own machine. It exists to prove the pipeline's output can
be served over HTTP.

## Phase 4: minimal dashboard

Open `http://127.0.0.1:8000/dashboard` in a browser (with the API
server above running) to see the latest report as a readable page —
KPI tiles, executive summary, and every report section — instead of
raw JSON. `api/dashboard.py` holds the plain HTML rendering logic,
covered directly by `tests/test_dashboard.py` (including an
HTML-escaping check, since a period label or ticket title will
eventually come from real, untrusted vendor data).

No JavaScript, no client-side framework, no auto-refresh — this is
the smallest page that proves persisted pipeline output is viewable,
not a production dashboard. Drill-down, history, and live updates are
designed for later.

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

## Phase 3: real connector (Zoho Desk sandbox)

`connectors/zoho_desk.py` is the first connector that calls a real
vendor API instead of reading a CSV. It authenticates via OAuth
refresh token (never a hardcoded credential), fetches tickets with
pagination, and normalizes them onto the exact same Ticket shape the
synthetic connector produces — nothing downstream needed to change.

**This must only ever point at a personal sandbox org**, created and
owned separately from any employer's Zoho tenant. Set these in your
local `.env` (see `.env.example`):

```
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REFRESH_TOKEN=...
ZOHO_API_DOMAIN=https://www.zohoapis.ae   # matches your Zoho data center
ZOHO_ORG_ID=...
```

Run it against your real sandbox tickets:

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python run_zoho_pipeline.py
```

This produces `output/zoho_live_report.pdf` / `.xlsx` from your actual
sandbox tickets, and persists them to the same `ai_it_operations.db`
used by the synthetic pipeline.

`tests/test_zoho_desk_connector.py` covers the connector's parsing
and pagination logic entirely with mocked HTTP responses — it never
makes a real network call, so it runs the same in CI as anywhere else.

## Phase 5: cost/contract module

`connectors/synthetic_contracts.py` reads vendor/service/cost/renewal
data with the same shape a real manual-entry form would eventually
produce (vendor, service, annual cost, renewal date, license count,
licenses in use). `engines/cost_engine.py` turns that into:

- **Total tracked annual spend**, broken down by vendor
- **Contracts renewing within 90 days**, sorted most-urgent first
- **Underutilized licenses** (below 70% usage) — the cost-saving flag
- **Contracts missing cost data**, flagged rather than guessed at

This feeds into the AI report's `cost_observations` section and two
new dashboard tiles (Annual Spend Tracked, Renewals Due Soon). Same
discipline as every other engine: pure functions, no AI, fully unit
tested (`tests/test_cost_engine.py`) — the numbers are right before
the AI layer ever narrates them.

`Vendor` and `Contract` tables (in `models/schema.py`) now store this
data per-customer, same tenant-ready pattern as everything else.

## What's deliberately NOT built yet

Real connectors for Sophos/FortiGate/M365 (Zoho Desk is the only real one so far), multi-tenancy, auth, scheduling, real network/bandwidth data source, a manual-entry UI for contract data (currently CSV only). Each of these is designed for, not built, until proven at the current phase.

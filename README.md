# Atlas Fresh: Daily Apple Export Planner

A decision-support workspace for the daily Production–Commercial committee. It loads and validates the day's workbook on the server and compares each farm's plan with its actual receipts by quality segment. It then runs the fixed allocation policy and shows client service, station use, export value and the local-market residual. A read-only assistant explains the result with IDs you can click through to the evidence.

The workspace **prepares** the committee. It never contacts farms or clients, confirms a plan, or writes to another system. Production and Commercial approve execution.

## Prerequisites

- **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)** (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Node.js 20+** and npm
- Optional: an **Anthropic API key** to enable the AI assistant. Without one the app still works fully and says honestly that no model is configured.

## Clean start

```bash
git clone https://github.com/youcef-s/Atlas-Fresh.git atlas-fresh-planner && cd atlas-fresh-planner
npm install        # also runs `uv sync` for the backend and `npm ci` for the frontend
npm run dev        # API on http://127.0.0.1:8000, workspace on http://localhost:5173
```

Open http://localhost:5173 and click **Load today's workbook**.

### Running the backend and frontend separately

`npm run dev` starts both processes. To run each one in its own terminal instead:

**Backend (API on http://127.0.0.1:8000):**

```bash
cd backend
uv sync --extra dev                                  # first time only
uv run uvicorn app.main:app --port 8000 --reload
```

Check it with `curl http://127.0.0.1:8000/api/health`, which returns `{"status":"ok"}`. Interactive API docs are at http://127.0.0.1:8000/docs.

**Frontend (workspace on http://localhost:5173):**

```bash
cd frontend
npm ci                                               # first time only
npm run dev
```

The frontend forwards `/api` requests to the backend on port 8000. Set `ATLAS_API=http://host:port` to point it elsewhere.

### Enabling the assistant

Start the backend with a key in the environment (either `npm run dev` or the backend command above):

```bash
ANTHROPIC_API_KEY=sk-ant-... npm run dev     # optional: ATLAS_MODEL=claude-opus-5 (default)
```

## Commands

| Command | What it does |
|---|---|
| `npm test` | Backend tests (pytest): baseline, policy, limits, validation, API and assistant boundaries |
| `npm run lint` | `ruff`, `mypy --strict` and `oxlint` |
| `npm run build` | Type-checks and builds the frontend into `frontend/dist` |
| `npm start` | Serves the built frontend (`vite preview`, port 4173) together with the API |

To demo the rejection screen, edit a copy of the workbook (for example, duplicate a `farm_id` or set a demand of 62 t). Load it with **Validate another file…**. The bundled source in `data/` is never modified.

## Architecture

```
data/Atlas_Fresh_Production_Commercial_Data.xlsx   authoritative input (read-only)
backend/  FastAPI · Pydantic · openpyxl
  app/validation.py   workbook → Snapshot; every problem → {sheet, identifier, field, message}
  app/planning.py     Snapshot → PlanResult (pure, deterministic; no I/O)
  app/assistant.py    PlanResult → minimal context → model → validated answer
  app/models.py       source models (Farm, Client, Station) separate from results
  app/main.py         /api/load, /api/load/upload, /api/plan, /api/assistant[/status]
frontend/ Vite · React · TypeScript (no UI kit)
  src/components/     Summary, Production, Commercial, Allocation trace, Local residual, Explain
```

- **The server owns every number.** The frontend only formats and filters the `PlanResult`. The LLM never chooses farms or clients, calculates quantities, or produces KPIs.
- **State** is one in-memory snapshot, which is enough for a single daily committee. Source data (`Snapshot`) and computed results (`PlanResult`) are separate types, and the plan is recalculated from the snapshot on each request.
- **Errors** come back as a typed envelope `{kind, message, issues[]}`: 422 for validation, 409 when nothing is loaded, 500 for a server failure. The UI has loading, empty, validation-error and server-error states, each with a retry or reset path.

### Planning policy (brief §3, implemented exactly)

1. Supply is each farm's **actual** A/B/C/D tonnes. Expected values are only for comparison.
2. Clients are processed by export price descending, with ties broken by `client_id`.
3. For each client, the candidates are compatible farm-segments with a positive balance. `EXACT` means the requested segment only. `MINIMUM` means the requested segment or better.
4. Candidates are sorted by the smallest quality upgrade, then `farm_id`. Tonnes are allocated in 5 t steps until demand, supply or station capacity runs out.
5. Every unexported tonne goes local. Its value is tonnes × local ratio × the reference price of that fruit's segment.
6. A partial or unserved client gets `STATION_CAPACITY_REACHED` if the line is full, otherwise `INSUFFICIENT_COMPATIBLE_SEGMENT`.

The engine checks five invariants on every run and shows them in the UI's data-health badge: export ≤ capacity; client export ≤ demand; farm-segment export ≤ actual; every allocation is compatible; export + local = received.

On the supplied workbook the result matches every public baseline check: 500 t export, 60 t local, 89.3 % export rate, €549,500 export revenue, €4,500 local value, €554,000 total, and 3 clients at risk (C02 and C09 short on segment, C08 short on capacity). The tests check this, and they also check that the outputs change when the inputs change.

### Assistant (read-only)

- It supports three standard questions plus free text. Each question gets only the context it needs: at-risk clients; segment and farm shortfalls; or the local residual.
- The model must return JSON `{status, answer, citations}`. The server **rejects** an answer if it mentions an unknown client or farm ID, or states a number that is not in the context sent to the model. Citations are narrowed to known IDs.
- Every non-answer is reported for what it is: no key, timeout (20 s), provider failure, invalid output, or "not available in today's data". None of these ever shows a made-up AI answer. The three standard questions also show a deterministic summary labelled **"not AI: generated from the plan"**.
- Model: `claude-opus-5` through the Anthropic SDK, with structured JSON output, low effort, and the server-side refusal fallback (`fallbacks: "default"`).

## Assumptions

- **5 t steps:** all actual tonnes, demand and capacity are validated as multiples of 5, so taking whole 5 t steps from one farm-segment produces one allocation row per farm × segment × client.
- **Shortage reason:** "capacity exhausted" means less than 5 t of line was left after the client's turn.
- **Workbook layout:** tables are found by their header name (`farm_id`, `client_id`, `station_id`, `segment`), not by fixed row numbers. A table ends at the first blank row, and any data after that blank row is reported as an error, never dropped.
- **Validation bounds:** station capacity and all prices must be > 0. Expected mix values must sum to 1.0 within 1e-6. Expected capacity may have one decimal.
- **Gap shading:** in the Production grid a cell is shaded only when its gap is ≥ 2.5 t (half a lot), so rounding noise doesn't hide the real gaps. The signed value is always shown.
- **Upload:** loading an edited copy of the workbook is included only so the rejection screen can be demonstrated. It is not a data-management feature.

## Limitations

- One in-memory snapshot per server process. There is no persistence, authentication or multi-user state (all explicitly out of scope).
- **The live Anthropic path was not run against the real API during development** because no key was available. It is covered by tests with a stubbed provider. The no-key path and the UI states were checked in a real browser.
- The assistant's number check is deliberately strict. A correct answer that derives a new figure (for example, a sum) is rejected rather than shown.
- There are no automated frontend tests. The UI was checked by scripted browser runs at 1024 px and 1440 px: every view, the validation and server-error states, and keyboard tab navigation.
- The layout targets desktop widths from 1000 px up. There is no Docker setup and no CI.

## Next three production steps

1. **Decision record:** persist each day's snapshot, plan and the committee's approvals and overrides, so decisions can be audited and compared against what was actually shipped.
2. **Live inputs:** replace the workbook with receipts from the station or ERP and the client program from Commercial. Keep the same validation contract, and add a what-if view for the committee's proposed exceptions.
3. **Operate it:** add authentication with Production and Commercial roles, a container build and CI running tests, lint and a clean-clone check. Add an evaluation set for the assistant so answer quality and the rejection rate are measured, not assumed.

## AI tools used

- **Claude Code** (Anthropic's coding agent, Claude Opus 5.5) wrote most of the code under my direction, in phases: it planned first, wrote the tests for the policy before the engine, and made one commit per phase. It ran the tests, lint, type checks and a browser-driven UI check (Playwright screenshots at 1024 px and 1440 px) after each step. A separate automated code review of the UI commit found three low-severity issues, which are fixed in the assistant commit.
- **What I verified:** I directed the work phase by phase and reviewed every result before moving on. The following checks were run and their output checked:
  - every public baseline number and the C02/C09/C08 statuses against the brief;
  - a valid edit (station capacity 450 t) recalculating every KPI, which proves nothing is hard-coded;
  - an invalid workbook being rejected with the sheet and ID named;
  - the allocation trace summing to all 560 t received;
  - the UI at 1024 px and 1440 px;
  - a fresh clone installing, testing and building with only the README commands.

  I also triaged the automated code review and decided which findings to fix.
- **Approximate time spent:** about 3 hours in total. Roughly 30 min reading the brief and workbook; 45 min on an initial backend skeleton; about 1 h 15 min with Claude Code on planning, the engine and tests, the UI, the assistant and the review fixes; and 30 min checking the result and writing up. The 3–5 minute walkthrough recording comes on top of that.
- **Intentionally omitted:** Docker, CI, persistence, authentication, frontend unit tests, and a live-deployed URL.

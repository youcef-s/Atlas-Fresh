# Atlas Fresh Daily Export Planner

Decision-support workspace for the daily Production–Commercial committee (Qarizmi assessment).

## Layout
- `data/Atlas_Fresh_Production_Commercial_Data.xlsx`: authoritative input. Never modify it.
- `backend/`: FastAPI + Pydantic + openpyxl (uv). `app/validation.py` loads the workbook, `app/planning.py` holds the engine, `app/main.py` holds the routes.
- `frontend/`: Vite + React + TS (planned).

## Commands
- `cd backend && uv sync --extra dev`
- `cd backend && uv run pytest`
- `cd backend && uv run ruff check .`
- `cd backend && uv run uvicorn app.main:app --reload`

## Planning policy (exact order, deterministic)
1. Supply = actual A/B/C/D tonnes per farm. Expected values are for comparison only.
2. Clients are processed by export price descending, then client_id.
3. Compatible supply: EXACT means the same segment; MINIMUM means the same or better (A > B > C > D).
4. Sort supply by smallest quality upgrade, then farm_id. Allocate in 5 t steps until demand, supply or station capacity runs out.
5. Everything unexported goes local: t × local_ratio × segment reference price.
6. Shortage reason: `STATION_CAPACITY_REACHED` if capacity is exhausted, else `INSUFFICIENT_COMPATIBLE_SEGMENT`.

## Public baseline (test oracle, never hard-code)
Expected 600 t, actual 560 t (A/B/C/D 90/160/180/130), capacity 500. Export 500 t, rate 89.3 %, local 60 t.
Export revenue €549,500, local value €4,500, total €554,000. 3 clients at risk: C02 and C09 short on segment, C08 short because of station capacity.

## Rules
- The LLM assistant is read-only. It never computes quantities, chooses allocations or produces KPIs. Every number comes from the engine result, and cited IDs are validated server-side.
- Reject invalid input with `{sheet, identifier, message}`. Never repair it silently.

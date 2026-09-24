"""FastAPI application and routes."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import logging

from app.models import LoadResponse, PlanResponse
from app.validation import load_and_validate_workbook
from app.planning import run_planning_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Atlas Fresh Daily Apple Export Planner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store loaded data in memory (single daily snapshot)
_state = {
    "farms": None,
    "clients": None,
    "station": None,
    "reference_prices": None,
    "load_errors": None,
}


def get_data_path() -> Path:
    return Path(__file__).parent.parent.parent / "Qarizmi_Atlas Fresh_Weekend_Technical_Assessment_Pack" / "Atlas_Fresh_Production_Commercial_Data.xlsx"


@app.post("/api/load", response_model=LoadResponse)
async def load_workbook():
    """Load and validate the workbook."""
    global _state
    file_path = get_data_path()
    logger.info(f"Loading workbook from {file_path}")

    response = load_and_validate_workbook(str(file_path))

    if response.success:
        _state["farms"] = response.farms
        _state["clients"] = response.clients
        _state["station"] = response.station
        _state["reference_prices"] = response.reference_prices
        _state["load_errors"] = None
    else:
        _state["load_errors"] = response.errors

    return response


@app.post("/api/plan", response_model=PlanResponse)
async def generate_plan():
    """Run the deterministic planning engine."""
    if _state["farms"] is None or _state["clients"] is None:
        return PlanResponse(success=False, error="No data loaded. Call /api/load first.")

    try:
        result = run_planning_engine(
            farms=_state["farms"],
            clients=_state["clients"],
            station=_state["station"],
            reference_prices=_state["reference_prices"],
        )
        return PlanResponse(success=True, result=result)
    except Exception as e:
        logger.exception("Planning engine failed")
        return PlanResponse(success=False, error=str(e))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
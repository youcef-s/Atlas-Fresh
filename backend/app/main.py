"""FastAPI routes. State is one in-memory daily snapshot; the source workbook is only read."""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.models import InputIssue, PlanResult, Snapshot
from app.planning import run_plan
from app.validation import WorkbookInvalid, load_snapshot

logger = logging.getLogger("atlas")

DEFAULT_WORKBOOK = (
    Path(__file__).resolve().parents[2] / "data" / "Atlas_Fresh_Production_Commercial_Data.xlsx"
)


def workbook_path() -> Path:
    return Path(os.environ.get("ATLAS_WORKBOOK", DEFAULT_WORKBOOK))


app = FastAPI(title="Atlas Fresh Daily Export Planner")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class LoadResult(BaseModel):
    source: str
    snapshot: Snapshot


class ErrorBody(BaseModel):
    kind: str  # "validation" | "not_loaded" | "server"
    message: str
    issues: list[InputIssue] = []


_state: dict[str, Snapshot | None] = {"snapshot": None}


def _error(status: int, body: ErrorBody) -> JSONResponse:
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/load", response_model=LoadResult, responses={422: {"model": ErrorBody}})
def load() -> LoadResult | JSONResponse:
    """Seed action: load and validate the supplied workbook on the server."""
    path = workbook_path()
    try:
        snapshot = load_snapshot(path)
    except WorkbookInvalid as exc:
        _state["snapshot"] = None
        return _error(
            422,
            ErrorBody(
                kind="validation",
                message="The workbook was rejected. Fix the rows below and reload.",
                issues=exc.issues,
            ),
        )
    _state["snapshot"] = snapshot
    return LoadResult(source=path.name, snapshot=snapshot)


@app.post("/api/plan", response_model=PlanResult, responses={409: {"model": ErrorBody}})
def plan() -> PlanResult | JSONResponse:
    snapshot = _state["snapshot"]
    if snapshot is None:
        return _error(409, ErrorBody(kind="not_loaded", message="Load today's workbook first."))
    return run_plan(snapshot)


@app.exception_handler(Exception)
async def unhandled(_request: object, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error", exc_info=exc)
    return _error(
        500,
        ErrorBody(kind="server", message="Unexpected server error. Retry, or reset the workspace."),
    )

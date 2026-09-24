"""FastAPI routes. State is one in-memory daily snapshot; the source workbook is only read."""

import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.assistant import AssistantAnswer, AssistantRequest, ask, configured_provider
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


MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _load_from(path: Path, source: str) -> LoadResult | JSONResponse:
    try:
        snapshot = load_snapshot(path, display_name=source)
    except WorkbookInvalid as exc:
        _state["snapshot"] = None
        return _error(
            422,
            ErrorBody(
                kind="validation",
                message="Correct the rows below in the workbook, then load it again.",
                issues=exc.issues,
            ),
        )
    _state["snapshot"] = snapshot
    return LoadResult(source=source, snapshot=snapshot)


@app.post("/api/load", response_model=LoadResult, responses={422: {"model": ErrorBody}})
def load() -> LoadResult | JSONResponse:
    """Seed action: load and validate the supplied workbook on the server."""
    path = workbook_path()
    return _load_from(path, path.name)


@app.post("/api/load/upload", response_model=LoadResult, responses={422: {"model": ErrorBody}})
def load_upload(file: UploadFile) -> LoadResult | JSONResponse:
    """Validate an edited copy of the workbook (e.g. to demo rejection). The source is untouched.

    Sync handler on purpose: FastAPI runs it in a worker thread, so parsing never blocks the loop.
    """
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    name = Path(file.filename or "").name or "upload.xlsx"  # display only, never a path
    if len(data) > MAX_UPLOAD_BYTES:
        _state["snapshot"] = None
        return _error(
            422,
            ErrorBody(
                kind="validation",
                message="The file is larger than 5 MB.",
                issues=[InputIssue(sheet="Workbook", identifier=name, message="File too large")],
            ),
        )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "upload.xlsx"
        path.write_bytes(data)
        return _load_from(path, name)


@app.post("/api/plan", response_model=PlanResult, responses={409: {"model": ErrorBody}})
def plan() -> PlanResult | JSONResponse:
    snapshot = _state["snapshot"]
    if snapshot is None:
        return _error(409, ErrorBody(kind="not_loaded", message="Load today's workbook first."))
    return run_plan(snapshot)


class AssistantStatusBody(BaseModel):
    configured: bool
    model: str | None


@app.get("/api/assistant/status", response_model=AssistantStatusBody)
def assistant_status() -> AssistantStatusBody:
    _, model = configured_provider()
    return AssistantStatusBody(configured=model is not None, model=model)


@app.post(
    "/api/assistant",
    response_model=AssistantAnswer,
    responses={409: {"model": ErrorBody}, 422: {"model": ErrorBody}},
)
def assistant(request: AssistantRequest) -> AssistantAnswer | JSONResponse:
    """Explain the calculated plan. Read-only: never changes the snapshot or the plan."""
    snapshot = _state["snapshot"]
    if snapshot is None:
        return _error(409, ErrorBody(kind="not_loaded", message="Load today's workbook first."))
    provider, model = configured_provider()
    try:
        return ask(request, run_plan(snapshot), snapshot, provider, model)
    except ValueError as exc:
        return _error(422, ErrorBody(kind="validation", message=str(exc)))


@app.exception_handler(Exception)
async def unhandled(_request: object, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error", exc_info=exc)
    return _error(
        500,
        ErrorBody(kind="server", message="Unexpected server error. Retry, or reset the workspace."),
    )

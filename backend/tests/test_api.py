from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import DEFAULT_WORKBOOK, app
from app.validation import WorkbookInvalid, load_snapshot

from .conftest import Mutator


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_load_plan_and_source_left_unchanged(client: TestClient) -> None:
    before = DEFAULT_WORKBOOK.read_bytes()
    assert client.post("/api/load").status_code == 200
    plan = client.post("/api/plan").json()
    assert plan["kpis"]["export_t"] == 500
    assert all(check["passed"] for check in plan["invariants"])
    assert DEFAULT_WORKBOOK.read_bytes() == before


def test_upload_with_hostile_name_is_a_validation_error(client: TestClient) -> None:
    res = client.post("/api/load/upload", files={"file": ("..", b"not a workbook")})
    assert res.status_code == 422
    assert res.json()["kind"] == "validation"


def test_rows_after_a_blank_row_are_not_dropped_silently(
    mutated: Callable[[Mutator], Path],
) -> None:
    def blank_mid_table(wb) -> None:  # type: ignore[no-untyped-def]
        ws = wb["Clients"]
        row = next(r[0].row for r in ws.iter_rows() if r[0].value == "C05")
        ws.insert_rows(row)

    with pytest.raises(WorkbookInvalid) as err:
        load_snapshot(mutated(blank_mid_table))
    assert any(i.sheet == "Clients" and i.identifier == "C05" for i in err.value.issues)

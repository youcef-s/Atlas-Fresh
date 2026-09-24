from collections.abc import Callable
from pathlib import Path

import pytest

from app.models import ClientStatus, Segment, ShortageReason, Snapshot
from app.planning import run_plan
from app.validation import WorkbookInvalid, load_snapshot

from .conftest import Mutator, cell


def test_baseline_matches_public_checks(baseline: Snapshot) -> None:
    result = run_plan(baseline)
    k = result.kpis
    assert (k.expected_plan_t, k.actual_received_t, k.station_capacity_t) == (600.0, 560, 500)
    assert {s.segment: s.actual_t for s in result.segments} == {
        "A": 90,
        "B": 160,
        "C": 180,
        "D": 130,
    }
    assert (k.export_t, k.local_t, k.export_rate_pct) == (500, 60, 89.3)
    assert (k.export_revenue_eur, k.local_value_eur, k.total_value_eur) == (549_500, 4_500, 554_000)
    assert k.at_risk_clients == 3
    status = {c.client_id: (c.status, c.shortage_reason) for c in result.clients}
    seg_short = (ClientStatus.PARTIAL, ShortageReason.INSUFFICIENT_COMPATIBLE_SEGMENT)
    assert status["C02"] == seg_short
    assert status["C09"] == seg_short
    assert status["C08"] == (ClientStatus.PARTIAL, ShortageReason.STATION_CAPACITY_REACHED)
    assert run_plan(baseline) == result  # deterministic


def test_ordering_price_desc_then_client_id_and_best_fit_supply(baseline: Snapshot) -> None:
    # Tie C03 with C01 on price: C01 still goes first by client_id.
    c03 = next(c for c in baseline.clients if c.client_id == "C03")
    c03.price_per_t_eur = 1500
    result = run_plan(baseline)
    assert [c.client_id for c in result.clients][:3] == ["C01", "C03", "C02"]
    # MINIMUM B client (C04) takes B before upgrading to A, and farms in ID order.
    c04_rows = [a for a in result.allocations if a.client_id == "C04"]
    assert all(a.segment == Segment.B for a in c04_rows)
    assert [a.farm_id for a in c04_rows] == sorted(a.farm_id for a in c04_rows)


def test_compatibility_exact_never_upgrades_minimum_does(baseline: Snapshot) -> None:
    result = run_plan(baseline)
    by_id = {c.client_id: c for c in baseline.clients}
    for a in result.allocations:
        assert by_id[a.client_id].accepts(a.segment)
        if by_id[a.client_id].acceptance_mode == "EXACT":
            assert a.segment == a.requested_segment and a.upgrade_steps == 0
    # C09 is EXACT B and short even though A supply is left over after C02.
    assert all(a.segment == Segment.B for a in result.allocations if a.client_id == "C09")


def test_hard_limits_hold_when_capacity_and_supply_change(baseline: Snapshot) -> None:
    baseline.station.capacity_t = 245
    result = run_plan(baseline)
    assert result.kpis.export_t <= 245
    assert all(i.passed for i in result.invariants)
    assert all(a.tonnes % 5 == 0 for a in result.allocations)
    reasons = {c.shortage_reason for c in result.clients if c.status != ClientStatus.COMPLETE}
    assert ShortageReason.STATION_CAPACITY_REACHED in reasons
    assert result.kpis.at_risk_clients > 3  # outputs react to input, nothing hard-coded


def test_local_residual_valued_at_segment_reference_price(baseline: Snapshot) -> None:
    result = run_plan(baseline)
    local = [b for b in result.farm_segments if b.local_t > 0]
    assert sum(b.local_t for b in local) == 60
    assert {b.segment for b in local} == {Segment.D}
    assert result.kpis.export_t + result.kpis.local_t == result.kpis.actual_received_t
    baseline.station.reference_price_per_t_eur[Segment.D] = 800
    changed = run_plan(baseline)
    assert changed.kpis.local_value_eur == 60 * 0.1 * 800
    assert changed.kpis.export_revenue_eur == result.kpis.export_revenue_eur  # never affects export


@pytest.mark.parametrize(
    ("edit", "sheet", "identifier"),
    [
        (lambda wb: setattr(cell(wb, "Farms", "F02", "farm_id"), "value", "F01"), "Farms", "F01"),
        (
            lambda wb: setattr(cell(wb, "Farms", "F05", "expected_A_pct"), "value", 0.3),
            "Farms",
            "F05",
        ),
        (lambda wb: setattr(cell(wb, "Farms", "F07", "actual_B_t"), "value", 12), "Farms", "F07"),
        (lambda wb: setattr(cell(wb, "Farms", "F08", "actual_C_t"), "value", -5), "Farms", "F08"),
        (
            lambda wb: setattr(cell(wb, "Clients", "C03", "acceptance_mode"), "value", "AT_LEAST"),
            "Clients",
            "C03",
        ),
        (
            lambda wb: setattr(cell(wb, "Clients", "C04", "requested_segment"), "value", "E"),
            "Clients",
            "C04",
        ),
        (lambda wb: setattr(cell(wb, "Clients", "C05", "demand_t"), "value", 62), "Clients", "C05"),
        (
            lambda wb: setattr(
                cell(wb, "Station", "STATION-01", "export_conditioning_capacity_t"), "value", 0
            ),
            "Station",
            "STATION-01",
        ),
        (
            lambda wb: wb["Station"].delete_rows(
                next(r[0].row for r in wb["Station"].iter_rows() if r[0].value == "C")
            ),
            "Station",
            "C",
        ),
    ],
    ids=[
        "dup-farm",
        "mix-sum",
        "non-5t",
        "negative",
        "mode",
        "segment",
        "demand-5t",
        "capacity",
        "missing-ref-price",
    ],
)
def test_validation_rejects_with_sheet_and_id(
    mutated: Callable[[Mutator], Path], edit: Mutator, sheet: str, identifier: str
) -> None:
    with pytest.raises(WorkbookInvalid) as err:
        load_snapshot(mutated(edit))
    assert any(i.sheet == sheet and i.identifier == identifier for i in err.value.issues), (
        err.value.issues
    )

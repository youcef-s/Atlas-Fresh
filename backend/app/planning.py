"""Deterministic daily allocation engine (reference policy, brief section 3).

No I/O, no randomness: the same Snapshot always yields the same PlanResult.
"""

from app.models import (
    SEGMENTS,
    AllocationRow,
    ClientResult,
    ClientStatus,
    FarmSegmentBalance,
    FarmSummary,
    InvariantCheck,
    Kpis,
    PlanResult,
    Segment,
    SegmentSummary,
    ShortageReason,
    Snapshot,
)

STEP_T = 5


def _r(x: float, nd: int = 2) -> float:
    return round(x + 0.0, nd)


def run_plan(snapshot: Snapshot) -> PlanResult:
    farms = sorted(snapshot.farms, key=lambda f: f.farm_id)
    station = snapshot.station
    farm_by_id = {f.farm_id: f for f in farms}

    # Step 3: available supply = actual tonnes only.
    remaining: dict[tuple[str, Segment], int] = {
        (f.farm_id, s): f.actual_t[s] for f in farms for s in SEGMENTS
    }
    station_left = station.capacity_t

    # Step 4: price descending, tie by client_id.
    ordered = sorted(snapshot.clients, key=lambda c: (-c.price_per_t_eur, c.client_id))

    allocations: list[AllocationRow] = []
    client_results: list[ClientResult] = []
    for priority, client in enumerate(ordered, start=1):
        compatible = client.compatible_segments
        taken_before = sum(a.tonnes for a in allocations if a.segment in compatible)
        station_before = station_left

        # Steps 5-6: compatible positive supply, smallest upgrade then farm_id.
        candidates = sorted(
            (key for key, t in remaining.items() if t > 0 and key[1] in compatible),
            key=lambda k: (client.requested_segment.rank - k[1].rank, k[0]),
        )
        need = client.demand_t
        allocated = 0
        for farm_id, seg in candidates:
            # Step 7: allocate in 5 t steps.
            take = 0
            while (
                need - take >= STEP_T
                and remaining[(farm_id, seg)] - take >= STEP_T
                and station_left - take >= STEP_T
            ):
                take += STEP_T
            if take == 0:
                if need < STEP_T or station_left < STEP_T:
                    break
                continue
            remaining[(farm_id, seg)] -= take
            station_left -= take
            need -= take
            allocated += take
            farm = farm_by_id[farm_id]
            allocations.append(
                AllocationRow(
                    sequence=len(allocations) + 1,
                    farm_id=farm_id,
                    farm_name=farm.farm_name,
                    segment=seg,
                    client_id=client.client_id,
                    client_name=client.client_name,
                    requested_segment=client.requested_segment,
                    upgrade_steps=client.requested_segment.rank - seg.rank,
                    tonnes=take,
                    price_per_t_eur=client.price_per_t_eur,
                    export_revenue_eur=_r(take * client.price_per_t_eur),
                )
            )

        if allocated == client.demand_t:
            status, reason = ClientStatus.COMPLETE, None
        else:
            status = ClientStatus.PARTIAL if allocated > 0 else ClientStatus.UNSERVED
            reason = (
                ShortageReason.STATION_CAPACITY_REACHED
                if station_left < STEP_T
                else ShortageReason.INSUFFICIENT_COMPATIBLE_SEGMENT
            )
        client_rows = [a for a in allocations if a.client_id == client.client_id]
        client_results.append(
            ClientResult(
                priority=priority,
                client_id=client.client_id,
                client_name=client.client_name,
                acceptance_mode=client.acceptance_mode,
                requested_segment=client.requested_segment,
                compatible_segments=compatible,
                price_per_t_eur=client.price_per_t_eur,
                demand_t=client.demand_t,
                allocated_t=allocated,
                remaining_t=client.demand_t - allocated,
                export_revenue_eur=_r(sum(a.export_revenue_eur for a in client_rows)),
                status=status,
                shortage_reason=reason,
                compatible_expected_t=_r(sum(f.expected_t(s) for f in farms for s in compatible)),
                compatible_actual_t=sum(f.actual_t[s] for f in farms for s in compatible),
                compatible_taken_by_higher_priority_t=taken_before,
                station_remaining_before_t=station_before,
                source_farm_ids=sorted({a.farm_id for a in client_rows}),
            )
        )

    # Step 8: every unexported tonne goes local.
    ratio = station.local_market_ratio
    ref = station.reference_price_per_t_eur
    balances: list[FarmSegmentBalance] = []
    for f in farms:
        for s in SEGMENTS:
            exported = sum(
                a.tonnes for a in allocations if a.farm_id == f.farm_id and a.segment == s
            )
            local = f.actual_t[s] - exported
            balances.append(
                FarmSegmentBalance(
                    farm_id=f.farm_id,
                    farm_name=f.farm_name,
                    segment=s,
                    expected_t=_r(f.expected_t(s)),
                    actual_t=f.actual_t[s],
                    variance_t=_r(f.actual_t[s] - f.expected_t(s)),
                    exported_t=exported,
                    local_t=local,
                    local_value_eur=_r(local * ratio * ref[s]),
                    client_ids=sorted(
                        {
                            a.client_id
                            for a in allocations
                            if a.farm_id == f.farm_id and a.segment == s
                        }
                    ),
                )
            )

    farm_summaries = [
        FarmSummary(
            farm_id=f.farm_id,
            farm_name=f.farm_name,
            expected_capacity_t=f.expected_capacity_t,
            actual_t=sum(f.actual_t.values()),
            variance_t=_r(sum(f.actual_t.values()) - f.expected_capacity_t),
            exported_t=sum(b.exported_t for b in rows),
            local_t=sum(b.local_t for b in rows),
            local_value_eur=_r(sum(b.local_value_eur for b in rows)),
        )
        for f in farms
        for rows in [[b for b in balances if b.farm_id == f.farm_id]]
    ]
    segment_summaries = [
        SegmentSummary(
            segment=s,
            expected_t=_r(sum(b.expected_t for b in rows)),
            actual_t=sum(b.actual_t for b in rows),
            variance_t=_r(sum(b.actual_t for b in rows) - sum(f.expected_t(s) for f in farms)),
            exported_t=sum(b.exported_t for b in rows),
            local_t=sum(b.local_t for b in rows),
            reference_price_per_t_eur=ref[s],
            local_value_eur=_r(sum(b.local_t for b in rows) * ratio * ref[s]),
            export_equivalent_value_eur=_r(sum(b.local_t for b in rows) * ref[s]),
        )
        for s in SEGMENTS
        for rows in [[b for b in balances if b.segment == s]]
    ]

    actual_total = sum(sum(f.actual_t.values()) for f in farms)
    export_t = sum(a.tonnes for a in allocations)
    local_t = sum(b.local_t for b in balances)
    export_revenue = _r(sum(a.export_revenue_eur for a in allocations))
    local_value = _r(sum(b.local_value_eur for b in balances))
    kpis = Kpis(
        expected_plan_t=_r(sum(f.expected_capacity_t for f in farms), 1),
        actual_received_t=actual_total,
        station_capacity_t=station.capacity_t,
        export_t=export_t,
        station_utilization_pct=_r(100 * export_t / station.capacity_t, 1),
        export_rate_pct=_r(100 * export_t / actual_total, 1) if actual_total else 0.0,
        local_t=local_t,
        export_revenue_eur=export_revenue,
        local_value_eur=local_value,
        total_value_eur=_r(export_revenue + local_value),
        at_risk_clients=sum(c.status is not ClientStatus.COMPLETE for c in client_results),
    )

    client_by_id = {c.client_id: c for c in snapshot.clients}
    invariants = [
        InvariantCheck(name="Export ≤ station capacity", passed=export_t <= station.capacity_t),
        InvariantCheck(
            name="Client export ≤ demand",
            passed=all(c.allocated_t <= c.demand_t for c in client_results),
        ),
        InvariantCheck(
            name="Farm-segment export ≤ actual",
            passed=all(0 <= b.exported_t <= b.actual_t for b in balances),
        ),
        InvariantCheck(
            name="Every allocation is quality-compatible",
            passed=all(client_by_id[a.client_id].accepts(a.segment) for a in allocations),
        ),
        InvariantCheck(
            name="Export + local = actual received", passed=export_t + local_t == actual_total
        ),
    ]

    return PlanResult(
        kpis=kpis,
        allocations=allocations,
        clients=client_results,
        farm_segments=balances,
        farms=farm_summaries,
        segments=segment_summaries,
        invariants=invariants,
    )

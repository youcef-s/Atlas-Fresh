"""Deterministic planning engine - core allocation logic."""
from app.models import (
    FarmPlan,
    Client,
    StationConfig,
    ReferencePrices,
    PlanningResult,
    AllocationRow,
    ClientResult,
    FarmSegmentBalance,
    KPIGroup,
    Segment,
    AcceptanceMode,
    ClientStatus,
    ShortageReason,
    FarmSegmentSupply,
)
from typing import cast


STEP_SIZE = 5.0
SEGMENTS = [Segment.A, Segment.B, Segment.C, Segment.D]


def create_supply_from_farms(farms: list[FarmPlan]) -> list[FarmSegmentSupply]:
    """Create supply list from actual farm receipts."""
    supply: list[FarmSegmentSupply] = []
    for farm in farms:
        for segment in SEGMENTS:
            actual = farm.get_actual(segment)
            if actual > 0:
                supply.append(FarmSegmentSupply(
                    farm_id=farm.farm_id,
                    farm_name=farm.farm_name,
                    segment=segment,
                    available_t=actual,
                ))
    return supply


def is_compatible(supply_segment: Segment, client: Client) -> bool:
    """Check if a supply segment is compatible with client requirements."""
    return supply_segment.is_compatible_with(client.requested_segment, client.acceptance_mode)


def quality_upgrade_steps(supply_segment: Segment, requested_segment: Segment) -> int:
    """Number of quality steps the supply exceeds the request (0 = exact, 1 = one step better, etc.)."""
    return requested_segment.quality_order - supply_segment.quality_order


def allocate_for_client(
    client: Client,
    supply: list[FarmSegmentSupply],
    remaining_station_capacity: float,
) -> tuple[list[AllocationRow], float, float, ShortageReason | None]:
    """
    Allocate supply to a single client.
    Returns: (allocations, allocated_tonnes, revenue, shortage_reason)
    """
    # Filter compatible supply with remaining balance
    compatible = [
        s for s in supply
        if s.remaining_t > 0 and is_compatible(s.segment, client)
    ]

    # Sort by smallest quality upgrade, then farm_id
    compatible.sort(key=lambda s: (quality_upgrade_steps(s.segment, client.requested_segment), s.farm_id))

    allocations: list[AllocationRow] = []
    allocated = 0.0
    revenue = 0.0
    shortage_reason: ShortageReason | None = None

    demand_remaining = client.demand_t

    for supply_item in compatible:
        if demand_remaining <= 0 or remaining_station_capacity <= 0:
            break

        can_allocate = min(supply_item.remaining_t, demand_remaining, remaining_station_capacity)
        # Round down to nearest 5t step
        can_allocate = (can_allocate // STEP_SIZE) * STEP_SIZE

        if can_allocate <= 0:
            continue

        supply_item.allocated_t += can_allocate
        allocated += can_allocate
        demand_remaining -= can_allocate
        remaining_station_capacity -= can_allocate

        alloc_revenue = can_allocate * client.export_price_per_t_eur
        revenue += alloc_revenue

        quality_upgrade = quality_upgrade_steps(supply_item.segment, client.requested_segment) > 0
        allocations.append(AllocationRow(
            farm_id=supply_item.farm_id,
            farm_name=supply_item.farm_name,
            segment=supply_item.segment,
            client_id=client.client_id,
            client_name=client.client_name,
            tonnes=can_allocate,
            quality_upgrade=quality_upgrade,
            export_revenue_eur=alloc_revenue,
        ))

    # Determine shortage reason
    if allocated < client.demand_t:
        if remaining_station_capacity <= 0:
            shortage_reason = ShortageReason.STATION_CAPACITY_REACHED
        else:
            shortage_reason = ShortageReason.INSUFFICIENT_COMPATIBLE_SEGMENT

    return allocations, allocated, revenue, shortage_reason


def run_planning_engine(
    farms: list[FarmPlan],
    clients: list[Client],
    station: StationConfig,
    reference_prices: ReferencePrices,
) -> PlanningResult:
    """Run the complete deterministic planning policy."""
    # Create supply from actual receipts
    supply = create_supply_from_farms(farms)

    # Sort clients by export price descending, then client_id
    sorted_clients = sorted(clients, key=lambda c: (-c.export_price_per_t_eur, c.client_id))

    all_allocations: list[AllocationRow] = []
    client_results: list[ClientResult] = []
    remaining_station_capacity = station.export_conditioning_capacity_t

    for client in sorted_clients:
        allocations, allocated_t, revenue, shortage_reason = allocate_for_client(
            client, supply, remaining_station_capacity
        )
        all_allocations.extend(allocations)
        remaining_station_capacity -= allocated_t

        remaining = client.demand_t - allocated_t
        if allocated_t >= client.demand_t:
            status = ClientStatus.COMPLETE
        elif allocated_t > 0:
            status = ClientStatus.PARTIAL
        else:
            status = ClientStatus.UNSERVED

        client_results.append(ClientResult(
            client_id=client.client_id,
            client_name=client.client_name,
            acceptance_mode=client.acceptance_mode,
            requested_segment=client.requested_segment,
            demand_t=client.demand_t,
            allocated_t=allocated_t,
            remaining_t=remaining,
            export_revenue_eur=revenue,
            status=status,
            shortage_reason=shortage_reason,
        ))

    # Build farm-segment balances
    farm_segment_balances: list[FarmSegmentBalance] = []
    for farm in farms:
        for segment in SEGMENTS:
            actual = farm.get_actual(segment)
            if actual == 0:
                continue
            allocated = sum(
                a.tonnes for a in all_allocations
                if a.farm_id == farm.farm_id and a.segment == segment
            )
            local = actual - allocated
            farm_segment_balances.append(FarmSegmentBalance(
                farm_id=farm.farm_id,
                farm_name=farm.farm_name,
                segment=segment,
                expected_t=farm.get_expected(segment),
                actual_t=actual,
                allocated_t=allocated,
                local_t=local,
                variance_t=farm.get_variance(segment),
            ))

    # Calculate KPIs
    total_actual = sum(f.actual_total_t for f in farms)
    export_t = sum(a.tonnes for a in all_allocations)
    local_t = total_actual - export_t
    export_revenue = sum(a.export_revenue_eur for a in all_allocations)

    # Local value: residual tonnes × local ratio × reference price of that segment
    local_value = 0.0
    for balance in farm_segment_balances:
        if balance.local_t > 0:
            local_value += balance.local_t * station.local_market_ratio * reference_prices.get_price(balance.segment)

    export_rate = (export_t / total_actual * 100) if total_actual > 0 else 0.0
    at_risk = sum(1 for c in client_results if c.status in (ClientStatus.PARTIAL, ClientStatus.UNSERVED))

    kpis = KPIGroup(
        expected_plan_t=sum(f.expected_daily_capacity_t for f in farms),
        actual_received_t=total_actual,
        station_capacity_t=station.export_conditioning_capacity_t,
        export_t=export_t,
        export_rate_pct=round(export_rate, 1),
        local_t=local_t,
        export_revenue_eur=export_revenue,
        local_value_eur=round(local_value, 2),
        total_value_eur=round(export_revenue + local_value, 2),
        at_risk_clients=at_risk,
    )

    return PlanningResult(
        allocations=all_allocations,
        client_results=client_results,
        farm_segment_balances=farm_segment_balances,
        kpis=kpis,
    )
"""Domain models: validated source data (inputs) and computed plan (outputs) are kept separate."""

from enum import StrEnum

from pydantic import BaseModel


class Segment(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"

    @property
    def rank(self) -> int:
        """0 = best quality (A), 3 = lowest (D)."""
        return SEGMENTS.index(self)


SEGMENTS: tuple[Segment, ...] = (Segment.A, Segment.B, Segment.C, Segment.D)


class AcceptanceMode(StrEnum):
    EXACT = "EXACT"
    MINIMUM = "MINIMUM"


class ClientStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNSERVED = "UNSERVED"


class ShortageReason(StrEnum):
    INSUFFICIENT_COMPATIBLE_SEGMENT = "INSUFFICIENT_COMPATIBLE_SEGMENT"
    STATION_CAPACITY_REACHED = "STATION_CAPACITY_REACHED"


# ---------------------------------------------------------------- source data


class Farm(BaseModel):
    farm_id: str
    farm_name: str
    expected_capacity_t: float
    expected_mix: dict[Segment, float]
    actual_t: dict[Segment, int]

    def expected_t(self, segment: Segment) -> float:
        return self.expected_capacity_t * self.expected_mix[segment]


class Client(BaseModel):
    client_id: str
    client_name: str
    acceptance_mode: AcceptanceMode
    requested_segment: Segment
    demand_t: int
    price_per_t_eur: float

    def accepts(self, segment: Segment) -> bool:
        if self.acceptance_mode is AcceptanceMode.EXACT:
            return segment == self.requested_segment
        return segment.rank <= self.requested_segment.rank

    @property
    def compatible_segments(self) -> list[Segment]:
        return [s for s in SEGMENTS if self.accepts(s)]


class Station(BaseModel):
    station_id: str
    capacity_t: int
    local_market_ratio: float
    reference_price_per_t_eur: dict[Segment, float]


class Snapshot(BaseModel):
    farms: list[Farm]
    clients: list[Client]
    station: Station


class InputIssue(BaseModel):
    sheet: str
    identifier: str
    field: str | None = None
    message: str


# ------------------------------------------------------------------- results


class AllocationRow(BaseModel):
    sequence: int
    farm_id: str
    farm_name: str
    segment: Segment
    client_id: str
    client_name: str
    requested_segment: Segment
    upgrade_steps: int
    tonnes: int
    price_per_t_eur: float
    export_revenue_eur: float


class ClientResult(BaseModel):
    priority: int
    client_id: str
    client_name: str
    acceptance_mode: AcceptanceMode
    requested_segment: Segment
    compatible_segments: list[Segment]
    price_per_t_eur: float
    demand_t: int
    allocated_t: int
    remaining_t: int
    export_revenue_eur: float
    status: ClientStatus
    shortage_reason: ShortageReason | None
    # Deterministic context that links a client shortage back to production.
    compatible_expected_t: float
    compatible_actual_t: int
    compatible_taken_by_higher_priority_t: int
    station_remaining_before_t: int
    source_farm_ids: list[str]


class FarmSegmentBalance(BaseModel):
    farm_id: str
    farm_name: str
    segment: Segment
    expected_t: float
    actual_t: int
    variance_t: float
    exported_t: int
    local_t: int
    local_value_eur: float
    client_ids: list[str]


class FarmSummary(BaseModel):
    farm_id: str
    farm_name: str
    expected_capacity_t: float
    actual_t: int
    variance_t: float
    exported_t: int
    local_t: int
    local_value_eur: float


class SegmentSummary(BaseModel):
    segment: Segment
    expected_t: float
    actual_t: int
    variance_t: float
    exported_t: int
    local_t: int
    reference_price_per_t_eur: float
    local_value_eur: float
    export_equivalent_value_eur: float


class Kpis(BaseModel):
    expected_plan_t: float
    actual_received_t: int
    station_capacity_t: int
    export_t: int
    station_utilization_pct: float
    export_rate_pct: float
    local_t: int
    export_revenue_eur: float
    local_value_eur: float
    total_value_eur: float
    at_risk_clients: int


class InvariantCheck(BaseModel):
    name: str
    passed: bool


class PlanResult(BaseModel):
    kpis: Kpis
    allocations: list[AllocationRow]
    clients: list[ClientResult]
    farm_segments: list[FarmSegmentBalance]
    farms: list[FarmSummary]
    segments: list[SegmentSummary]
    invariants: list[InvariantCheck]

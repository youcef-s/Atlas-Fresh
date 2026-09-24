"""Core domain models for Atlas Fresh planning."""
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import Literal


class Segment(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"

    @property
    def quality_order(self) -> int:
        return {"A": 0, "B": 1, "C": 2, "D": 3}[self.value]

    def is_compatible_with(self, requested: "Segment", mode: "AcceptanceMode") -> bool:
        if mode == AcceptanceMode.EXACT:
            return self == requested
        return self.quality_order <= requested.quality_order


class AcceptanceMode(str, Enum):
    EXACT = "EXACT"
    MINIMUM = "MINIMUM"


class ShortageReason(str, Enum):
    INSUFFICIENT_COMPATIBLE_SEGMENT = "INSUFFICIENT_COMPATIBLE_SEGMENT"
    STATION_CAPACITY_REACHED = "STATION_CAPACITY_REACHED"


class ClientStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNSERVED = "UNSERVED"


class FarmPlan(BaseModel):
    farm_id: str
    farm_name: str
    expected_daily_capacity_t: float
    expected_A_pct: float
    expected_B_pct: float
    expected_C_pct: float
    expected_D_pct: float
    actual_A_t: float
    actual_B_t: float
    actual_C_t: float
    actual_D_t: float

    @field_validator("expected_A_pct", "expected_B_pct", "expected_C_pct", "expected_D_pct")
    @classmethod
    def validate_pct_range(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("Expected mix percentages must be between 0 and 1")
        return v

    @property
    def expected_mix_sum(self) -> float:
        return self.expected_A_pct + self.expected_B_pct + self.expected_C_pct + self.expected_D_pct

    @property
    def expected_A_t(self) -> float:
        return self.expected_daily_capacity_t * self.expected_A_pct

    @property
    def expected_B_t(self) -> float:
        return self.expected_daily_capacity_t * self.expected_B_pct

    @property
    def expected_C_t(self) -> float:
        return self.expected_daily_capacity_t * self.expected_C_pct

    @property
    def expected_D_t(self) -> float:
        return self.expected_daily_capacity_t * self.expected_D_pct

    @property
    def actual_total_t(self) -> float:
        return self.actual_A_t + self.actual_B_t + self.actual_C_t + self.actual_D_t

    def get_actual(self, segment: Segment) -> float:
        return {
            Segment.A: self.actual_A_t,
            Segment.B: self.actual_B_t,
            Segment.C: self.actual_C_t,
            Segment.D: self.actual_D_t,
        }[segment]

    def get_expected(self, segment: Segment) -> float:
        return {
            Segment.A: self.expected_A_t,
            Segment.B: self.expected_B_t,
            Segment.C: self.expected_C_t,
            Segment.D: self.expected_D_t,
        }[segment]

    def get_variance(self, segment: Segment) -> float:
        return self.get_actual(segment) - self.get_expected(segment)


class Client(BaseModel):
    client_id: str
    client_name: str
    acceptance_mode: AcceptanceMode
    requested_segment: Segment
    demand_t: float
    export_price_per_t_eur: float

    @field_validator("demand_t")
    @classmethod
    def validate_demand_multiple_of_5(cls, v: float) -> float:
        if v < 0 or v % 5 != 0:
            raise ValueError("Demand must be non-negative multiple of 5")
        return v


class StationConfig(BaseModel):
    station_id: str
    export_conditioning_capacity_t: float
    local_market_ratio: float


class ReferencePrices(BaseModel):
    prices: dict[Segment, float]

    def get_price(self, segment: Segment) -> float:
        return self.prices[segment]


class FarmSegmentSupply(BaseModel):
    farm_id: str
    farm_name: str
    segment: Segment
    available_t: float
    allocated_t: float = 0.0

    @property
    def remaining_t(self) -> float:
        return self.available_t - self.allocated_t


class AllocationRow(BaseModel):
    farm_id: str
    farm_name: str
    segment: Segment
    client_id: str
    client_name: str
    tonnes: float
    quality_upgrade: bool
    export_revenue_eur: float


class ClientResult(BaseModel):
    client_id: str
    client_name: str
    acceptance_mode: AcceptanceMode
    requested_segment: Segment
    demand_t: float
    allocated_t: float
    remaining_t: float
    export_revenue_eur: float
    status: ClientStatus
    shortage_reason: ShortageReason | None = None


class FarmSegmentBalance(BaseModel):
    farm_id: str
    farm_name: str
    segment: Segment
    expected_t: float
    actual_t: float
    allocated_t: float
    local_t: float
    variance_t: float


class KPIGroup(BaseModel):
    expected_plan_t: float
    actual_received_t: float
    station_capacity_t: float
    export_t: float
    export_rate_pct: float
    local_t: float
    export_revenue_eur: float
    local_value_eur: float
    total_value_eur: float
    at_risk_clients: int


class PlanningResult(BaseModel):
    allocations: list[AllocationRow]
    client_results: list[ClientResult]
    farm_segment_balances: list[FarmSegmentBalance]
    kpis: KPIGroup


class ValidationError(BaseModel):
    sheet: str
    identifier: str
    message: str


class LoadResponse(BaseModel):
    success: bool
    farms: list[FarmPlan] | None = None
    clients: list[Client] | None = None
    station: StationConfig | None = None
    reference_prices: ReferencePrices | None = None
    errors: list[ValidationError] = []


class PlanResponse(BaseModel):
    success: bool
    result: PlanningResult | None = None
    error: str | None = None
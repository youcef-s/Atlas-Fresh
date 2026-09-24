// Mirrors backend/app/models.py (source data vs computed plan).

export type Segment = 'A' | 'B' | 'C' | 'D'
export const SEGMENTS: Segment[] = ['A', 'B', 'C', 'D']
export type AcceptanceMode = 'EXACT' | 'MINIMUM'
export type ClientStatus = 'COMPLETE' | 'PARTIAL' | 'UNSERVED'
export type ShortageReason = 'INSUFFICIENT_COMPATIBLE_SEGMENT' | 'STATION_CAPACITY_REACHED'

export interface Farm {
  farm_id: string
  farm_name: string
  expected_capacity_t: number
  expected_mix: Record<Segment, number>
  actual_t: Record<Segment, number>
}

export interface Client {
  client_id: string
  client_name: string
  acceptance_mode: AcceptanceMode
  requested_segment: Segment
  demand_t: number
  price_per_t_eur: number
}

export interface Station {
  station_id: string
  capacity_t: number
  local_market_ratio: number
  reference_price_per_t_eur: Record<Segment, number>
}

export interface Snapshot {
  farms: Farm[]
  clients: Client[]
  station: Station
}

export interface LoadResult {
  source: string
  snapshot: Snapshot
}

export interface InputIssue {
  sheet: string
  identifier: string
  field: string | null
  message: string
}

export interface ErrorBody {
  kind: 'validation' | 'not_loaded' | 'server' | 'network'
  message: string
  issues: InputIssue[]
}

export interface AllocationRow {
  sequence: number
  farm_id: string
  farm_name: string
  segment: Segment
  client_id: string
  client_name: string
  requested_segment: Segment
  upgrade_steps: number
  tonnes: number
  price_per_t_eur: number
  export_revenue_eur: number
}

export interface ClientResult {
  priority: number
  client_id: string
  client_name: string
  acceptance_mode: AcceptanceMode
  requested_segment: Segment
  compatible_segments: Segment[]
  price_per_t_eur: number
  demand_t: number
  allocated_t: number
  remaining_t: number
  export_revenue_eur: number
  status: ClientStatus
  shortage_reason: ShortageReason | null
  compatible_expected_t: number
  compatible_actual_t: number
  compatible_taken_by_higher_priority_t: number
  station_remaining_before_t: number
  source_farm_ids: string[]
}

export interface FarmSegmentBalance {
  farm_id: string
  farm_name: string
  segment: Segment
  expected_t: number
  actual_t: number
  variance_t: number
  exported_t: number
  local_t: number
  local_value_eur: number
  client_ids: string[]
}

export interface FarmSummary {
  farm_id: string
  farm_name: string
  expected_capacity_t: number
  actual_t: number
  variance_t: number
  exported_t: number
  local_t: number
  local_value_eur: number
}

export interface SegmentSummary {
  segment: Segment
  expected_t: number
  actual_t: number
  variance_t: number
  exported_t: number
  local_t: number
  reference_price_per_t_eur: number
  local_value_eur: number
  export_equivalent_value_eur: number
}

export interface Kpis {
  expected_plan_t: number
  actual_received_t: number
  station_capacity_t: number
  export_t: number
  station_utilization_pct: number
  export_rate_pct: number
  local_t: number
  export_revenue_eur: number
  local_value_eur: number
  total_value_eur: number
  at_risk_clients: number
}

export interface InvariantCheck {
  name: string
  passed: boolean
}

export interface PlanResult {
  kpis: Kpis
  allocations: AllocationRow[]
  clients: ClientResult[]
  farm_segments: FarmSegmentBalance[]
  farms: FarmSummary[]
  segments: SegmentSummary[]
  invariants: InvariantCheck[]
}

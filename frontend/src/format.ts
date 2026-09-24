import type { ClientResult, Segment } from './types'

const tFmt = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1 })
const eurFmt = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

export const t = (v: number) => `${tFmt.format(v)} t`
export const eur = (v: number) => eurFmt.format(v)
export const pct = (v: number) => `${tFmt.format(v)} %`

/** Signed tonnes, e.g. "+5 t" / "−11.7 t" / "0 t". */
export const delta = (v: number) => {
  const r = Math.round(v * 10) / 10
  if (r === 0) return '0 t'
  return `${r > 0 ? '+' : '−'}${tFmt.format(Math.abs(r))} t`
}

export const segList = (segs: Segment[]) =>
  segs.length === 1 ? segs[0] : `${segs.slice(0, -1).join(', ')} or ${segs[segs.length - 1]}`

export const ruleLabel = (c: Pick<ClientResult, 'acceptance_mode' | 'requested_segment'>) =>
  c.acceptance_mode === 'EXACT'
    ? `Exactly ${c.requested_segment}`
    : `${c.requested_segment} or better`

export const statusLabel = { COMPLETE: 'Complete', PARTIAL: 'Partial', UNSERVED: 'Unserved' } as const

export const reasonShort = {
  INSUFFICIENT_COMPATIBLE_SEGMENT: 'Not enough compatible fruit',
  STATION_CAPACITY_REACHED: 'Station capacity reached',
} as const

/** Plain-language explanation built only from server-computed fields. */
export function reasonLong(c: ClientResult, capacity: number): string {
  if (c.shortage_reason === 'STATION_CAPACITY_REACHED') {
    return `The ${t(capacity)} export line was nearly full when this order's turn came (priority #${c.priority}): only ${t(c.station_remaining_before_t)} were left, so ${t(c.remaining_t)} of the ${t(c.demand_t)} order could not be conditioned.`
  }
  if (c.shortage_reason === 'INSUFFICIENT_COMPATIBLE_SEGMENT') {
    const segs = segList(c.compatible_segments)
    return `Only ${t(c.compatible_actual_t)} of Segment ${segs} arrived (plan ${t(c.compatible_expected_t)}). Higher-priced orders took ${t(c.compatible_taken_by_higher_priority_t)} first, leaving ${t(c.allocated_t)} for this order: ${t(c.remaining_t)} short.`
  }
  return `Fully served from ${c.source_farm_ids.length} farm${c.source_farm_ids.length === 1 ? '' : 's'}.`
}

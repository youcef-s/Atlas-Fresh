import { SEGMENTS, type PlanResult, type Segment } from '../types'
import { eur, t } from '../format'
import type { Nav } from './Workspace'

export interface TraceFilter {
  client?: string
  farm?: string
  segment?: Segment
  destination?: 'export' | 'local'
}

interface TraceRow {
  key: string
  ref: string
  farm_id: string
  segment: Segment
  destination: string
  requested: Segment | null
  upgrade: number
  tonnes: number
  price: number | null
  value: number
  local: boolean
}

export function TraceView({
  plan, nav, filter, setFilter,
}: {
  plan: PlanResult
  nav: Nav
  filter: TraceFilter
  setFilter: (f: TraceFilter) => void
}) {
  const all: TraceRow[] = [
    ...plan.allocations.map((a) => ({
      key: `x${a.sequence}`,
      ref: `#${a.sequence}`,
      farm_id: a.farm_id,
      segment: a.segment,
      destination: a.client_id,
      requested: a.requested_segment,
      upgrade: a.upgrade_steps,
      tonnes: a.tonnes,
      price: a.price_per_t_eur,
      value: a.export_revenue_eur,
      local: false,
    })),
    ...plan.farm_segments.filter((b) => b.local_t > 0).map((b) => ({
      key: `l${b.farm_id}${b.segment}`,
      ref: 'L',
      farm_id: b.farm_id,
      segment: b.segment,
      destination: 'LOCAL',
      requested: null,
      upgrade: 0,
      tonnes: b.local_t,
      price: b.local_t ? b.local_value_eur / b.local_t : null,
      value: b.local_value_eur,
      local: true,
    })),
  ]
  const rows = all.filter((r) =>
    (!filter.client || r.destination === filter.client) &&
    (!filter.farm || r.farm_id === filter.farm) &&
    (!filter.segment || r.segment === filter.segment) &&
    (!filter.destination || (filter.destination === 'local') === r.local),
  )
  const totalT = rows.reduce((s, r) => s + r.tonnes, 0)
  const totalV = rows.reduce((s, r) => s + r.value, 0)
  const tracedAll = all.reduce((s, r) => s + r.tonnes, 0)
  const active = Object.values(filter).some(Boolean)
  const farmIds = plan.farms.map((f) => f.farm_id)

  return (
    <section aria-label="Allocation trace">
      <div className="view-head">
        <p>
          Every received tonne appears exactly once: <strong>{t(tracedAll)}</strong> traced of{' '}
          <strong>{t(plan.kpis.actual_received_t)}</strong> received ({t(plan.kpis.export_t)} export + {t(plan.kpis.local_t)} local).
        </p>
        <div className="controls">
          <label>
            Client{' '}
            <select value={filter.client ?? ''} onChange={(e) => setFilter({ ...filter, client: e.target.value || undefined, destination: undefined })}>
              <option value="">All</option>
              {plan.clients.map((c) => <option key={c.client_id} value={c.client_id}>{c.client_id} {c.client_name}</option>)}
            </select>
          </label>
          <label>
            Farm{' '}
            <select value={filter.farm ?? ''} onChange={(e) => setFilter({ ...filter, farm: e.target.value || undefined })}>
              <option value="">All</option>
              {farmIds.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          <label>
            Segment{' '}
            <select value={filter.segment ?? ''} onChange={(e) => setFilter({ ...filter, segment: (e.target.value || undefined) as Segment | undefined })}>
              <option value="">All</option>
              {SEGMENTS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label>
            Destination{' '}
            <select value={filter.destination ?? ''} onChange={(e) => setFilter({ ...filter, destination: (e.target.value || undefined) as TraceFilter['destination'], client: undefined })}>
              <option value="">Export + local</option>
              <option value="export">Export only</option>
              <option value="local">Local only</option>
            </select>
          </label>
          {active && <button type="button" className="btn ghost small" onClick={() => setFilter({})}>Clear filters</button>}
        </div>
      </div>

      <div className="table-wrap">
        <table className="table num-right">
          <caption className="sr-only">Allocation rows from farm and segment to client or local market</caption>
          <thead>
            <tr>
              <th scope="col" className="left">Ref</th>
              <th scope="col" className="left">Farm</th>
              <th scope="col" className="left">Segment</th>
              <th scope="col" className="left">Destination</th>
              <th scope="col" className="left">Quality</th>
              <th scope="col">Tonnes</th>
              <th scope="col">Price / t</th>
              <th scope="col">Value</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={8} className="left muted">No rows match these filters. <button type="button" className="link" onClick={() => setFilter({})}>Clear filters</button></td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.key} className={r.local ? 'local-row' : ''}>
                <td className="left muted"><code>{r.ref}</code></td>
                <td className="left"><button type="button" className="id-chip" onClick={() => nav.farm(r.farm_id)}>{r.farm_id}</button></td>
                <td className="left"><span className={`seg seg-${r.segment}`}>{r.segment}</span></td>
                <td className="left">
                  {r.local
                    ? <span className="chip local">Local market</span>
                    : <button type="button" className="id-chip" onClick={() => nav.client(r.destination)}>{r.destination}</button>}
                </td>
                <td className="left small">
                  {r.local ? <span className="muted">local price for {r.segment}</span>
                    : r.upgrade > 0 ? <span className="upgrade">↑ {r.segment} for {r.requested} order</span>
                    : <span className="muted">as requested</span>}
                </td>
                <td>{t(r.tonnes)}</td>
                <td>{r.price === null ? '—' : eur(r.price)}</td>
                <td className={r.local ? 'alert-text' : ''}>{eur(r.value)}</td>
              </tr>
            ))}
          </tbody>
          {rows.length > 0 && (
            <tfoot>
              <tr>
                <th scope="row" colSpan={5} className="left">{active ? 'Filtered total' : 'Total'} ({rows.length} rows)</th>
                <td className="strong">{t(totalT)}</td>
                <td />
                <td className="strong">{eur(totalV)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </section>
  )
}

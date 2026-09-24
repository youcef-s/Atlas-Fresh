import { Fragment, useEffect, useRef, useState } from 'react'
import type { ClientResult, PlanResult } from '../types'
import { delta, eur, reasonLong, reasonShort, ruleLabel, statusLabel, t } from '../format'
import type { Nav } from './Workspace'

export function CommercialView({
  plan, nav, openClient, setOpenClient,
}: {
  plan: PlanResult
  nav: Nav
  openClient: string | null
  setOpenClient: (id: string | null) => void
}) {
  const [riskOnly, setRiskOnly] = useState(false)
  const openRow = useRef<HTMLTableRowElement>(null)
  useEffect(() => {
    if (openClient) openRow.current?.scrollIntoView({ block: 'center' })
  }, [openClient])

  const clients = riskOnly ? plan.clients.filter((c) => c.status !== 'COMPLETE') : plan.clients
  const counts = { COMPLETE: 0, PARTIAL: 0, UNSERVED: 0 }
  plan.clients.forEach((c) => counts[c.status]++)

  return (
    <section aria-label="Commercial: client service">
      <div className="view-head">
        <p>
          Orders are served in policy order: <strong>highest price first</strong> (ties by client ID), each from
          the closest compatible quality, then farm ID.{' '}
          <span className="chip complete">{counts.COMPLETE} complete</span>{' '}
          <span className="chip partial">{counts.PARTIAL} partial</span>{' '}
          <span className="chip unserved">{counts.UNSERVED} unserved</span>
        </p>
        <div className="controls">
          <label className="check">
            <input type="checkbox" checked={riskOnly} onChange={(e) => setRiskOnly(e.target.checked)} />
            At-risk only
          </label>
        </div>
      </div>

      <div className="table-wrap">
        <table className="table num-right">
          <caption className="sr-only">Clients in processing order with service status</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col" className="left">Client</th>
              <th scope="col" className="left">Quality rule</th>
              <th scope="col">Price</th>
              <th scope="col">Demand</th>
              <th scope="col" className="left">Allocated</th>
              <th scope="col">Remaining</th>
              <th scope="col">Revenue</th>
              <th scope="col" className="left">Status and reason</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((c) => {
              const open = openClient === c.client_id
              return (
                <Fragment key={c.client_id}>
                  <tr className={`${open ? 'open' : ''} ${c.status !== 'COMPLETE' ? 'at-risk' : ''}`} ref={open ? openRow : undefined}>
                    <td className="muted">{c.priority}</td>
                    <th scope="row" className="left">
                      <button type="button" className="row-toggle" aria-expanded={open}
                        onClick={() => setOpenClient(open ? null : c.client_id)}>
                        <span className="caret" aria-hidden="true">▸</span>
                        <code>{c.client_id}</code> <span className="muted">{c.client_name}</span>
                      </button>
                    </th>
                    <td className="left">
                      {ruleLabel(c)}
                      {c.acceptance_mode === 'MINIMUM' && <span className="muted small"> (accepts {c.compatible_segments.join(', ')})</span>}
                    </td>
                    <td>{eur(c.price_per_t_eur)}/t</td>
                    <td>{t(c.demand_t)}</td>
                    <td className="left">
                      <span className="fill" role="img" aria-label={`${c.allocated_t} of ${c.demand_t} tonnes`}>
                        <span style={{ width: `${c.demand_t ? (100 * c.allocated_t) / c.demand_t : 0}%` }} className={c.status.toLowerCase()} />
                      </span>{' '}
                      {t(c.allocated_t)}
                    </td>
                    <td className={c.remaining_t > 0 ? 'neg strong' : 'muted'}>{t(c.remaining_t)}</td>
                    <td>{eur(c.export_revenue_eur)}</td>
                    <td className="left">
                      <span className={`chip ${c.status.toLowerCase()}`}>{statusLabel[c.status]}</span>{' '}
                      {c.shortage_reason && <span className="small">{reasonShort[c.shortage_reason]}</span>}
                    </td>
                  </tr>
                  {open && (
                    <tr className="detail-row">
                      <td colSpan={9}>
                        <ClientDetail plan={plan} client={c} nav={nav} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function ClientDetail({ plan, client: c, nav }: { plan: PlanResult; client: ClientResult; nav: Nav }) {
  const rows = plan.allocations.filter((a) => a.client_id === c.client_id)
  const gaps = plan.farm_segments
    .filter((b) => c.compatible_segments.includes(b.segment) && b.variance_t < -0.05)
    .sort((a, b) => a.variance_t - b.variance_t)
    .slice(0, 6)
  const earlier = plan.clients.filter((o) => o.priority < c.priority)
  const pricier = earlier.filter((o) => o.price_per_t_eur > c.price_per_t_eur).length
  const compatibleLocal = plan.segments
    .filter((s) => c.compatible_segments.includes(s.segment))
    .reduce((sum, s) => sum + s.local_t, 0)
  const higher = plan.clients.filter(
    (o) => o.priority < c.priority && o.compatible_segments.some((s) => c.compatible_segments.includes(s)) && o.allocated_t > 0,
  )

  return (
    <div className="detail">
      <p className={c.shortage_reason ? 'explain warn' : 'explain'}>
        {c.shortage_reason && <code className="reason-code">{c.shortage_reason}</code>}
        {reasonLong(c, plan.kpis.station_capacity_t)}
      </p>
      <div className="detail-grid">
        <div>
          <h4>Supplied by</h4>
          {rows.length === 0 ? <p className="muted">No fruit allocated.</p> : (
            <table className="table compact num-right">
              <thead>
                <tr><th scope="col" className="left">Farm</th><th scope="col" className="left">Segment</th><th scope="col">Tonnes</th><th scope="col">Revenue</th></tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.sequence}>
                    <td className="left">
                      <button type="button" className="id-chip" onClick={() => nav.farm(a.farm_id)}>{a.farm_id}</button>
                    </td>
                    <td className="left">
                      <span className={`seg seg-${a.segment}`}>{a.segment}</span>
                      {a.upgrade_steps > 0 && <span className="upgrade" title="Better quality than requested">↑ upgrade from {a.requested_segment}</span>}
                    </td>
                    <td>{t(a.tonnes)}</td>
                    <td>{eur(a.export_revenue_eur)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <button type="button" className="link small" onClick={() => nav.trace({ client: c.client_id })}>
            Open {c.client_id} in the allocation trace →
          </button>
        </div>
        {c.shortage_reason === 'INSUFFICIENT_COMPATIBLE_SEGMENT' && (
          <div>
            <h4>Farm shortfalls behind this gap</h4>
            {gaps.length === 0 ? <p className="muted">No farm is below plan on these segments.</p> : (
              <ul className="gap-list">
                {gaps.map((g) => (
                  <li key={`${g.farm_id}-${g.segment}`}>
                    <button type="button" className="id-chip" onClick={() => nav.farm(g.farm_id)}>{g.farm_id}</button>
                    <span className={`seg seg-${g.segment}`}>{g.segment}</span>
                    <span className="neg">{delta(g.variance_t)}</span>
                    <span className="muted small">({g.actual_t} of {g.expected_t} t)</span>
                  </li>
                ))}
              </ul>
            )}
            {higher.length > 0 && (
              <p className="small muted">
                Served first:{' '}
                {higher.map((o) => (
                  <button key={o.client_id} type="button" className="id-chip" onClick={() => nav.client(o.client_id)}
                    title={o.price_per_t_eur > c.price_per_t_eur ? 'Higher price' : 'Same price, earlier client ID'}>
                    {o.client_id} {eur(o.price_per_t_eur)}/t{o.price_per_t_eur === c.price_per_t_eur ? ' (tie → ID)' : ''}
                  </button>
                ))}
              </p>
            )}
          </div>
        )}
        {c.shortage_reason === 'STATION_CAPACITY_REACHED' && (
          <div>
            <h4>Why capacity ran out</h4>
            <p className="small">
              {earlier.length} orders ahead of it in the policy order ({pricier} at a higher price
              {earlier.length > pricier ? `, ${earlier.length - pricier} at the same price with an earlier client ID` : ''})
              used {t(plan.kpis.station_capacity_t - c.station_remaining_before_t)} of the {t(plan.kpis.station_capacity_t)} line
              before this order’s turn.{' '}
              {compatibleLocal > 0 ? (
                <>
                  {t(compatibleLocal)} of fruit it accepts is going local instead: see the{' '}
                  <button type="button" className="link" onClick={nav.local}>local residual</button>.
                </>
              ) : 'No fruit it accepts is left over.'}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

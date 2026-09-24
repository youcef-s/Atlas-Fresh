import { SEGMENTS, type LoadResult, type PlanResult } from '../types'
import { delta, eur, pct, reasonShort, t } from '../format'
import type { Nav } from './Workspace'

export function Summary({ load, plan, nav }: { load: LoadResult; plan: PlanResult; nav: Nav }) {
  const k = plan.kpis
  const { snapshot } = load
  const checksOk = plan.invariants.every((c) => c.passed)
  const atRisk = plan.clients.filter((c) => c.status !== 'COMPLETE')
  const localSegments = plan.segments.filter((s) => s.local_t > 0)
  const localRef = plan.segments.reduce((sum, s) => sum + s.export_equivalent_value_eur, 0)
  const receivedGap = k.actual_received_t - k.expected_plan_t
  const unmetValue = atRisk.reduce((sum, c) => sum + c.remaining_t * c.price_per_t_eur, 0)

  return (
    <section aria-labelledby="summary-title" className="summary">
      <div className="summary-head">
        <h2 id="summary-title">Today at a glance</h2>
        <div className={`health ${checksOk ? 'ok' : 'bad'}`}>
          <span aria-hidden="true">{checksOk ? '✓' : '!'}</span>
          <span>
            Data validated: {snapshot.farms.length} farms, {snapshot.clients.length} clients,
            station {snapshot.station.station_id}.{' '}
            Plan checks {plan.invariants.filter((c) => c.passed).length}/{plan.invariants.length} passed
          </span>
          <details className="checks">
            <summary>details</summary>
            <ul>
              {plan.invariants.map((c) => (
                <li key={c.name}>{c.passed ? '✓' : '✗'} {c.name}</li>
              ))}
            </ul>
          </details>
        </div>
      </div>

      <div className="kpis">
        <Kpi label="Received vs plan" value={t(k.actual_received_t)}
          sub={<>plan {t(k.expected_plan_t)} · <span className={receivedGap < 0 ? 'neg' : 'pos'}>{delta(receivedGap)}</span></>} />
        <Kpi label="Station export line" value={`${t(k.export_t)} / ${t(k.station_capacity_t)}`}
          sub={<Meter value={k.station_utilization_pct} label={`${pct(k.station_utilization_pct)} used`} />} />
        <Kpi label="Export rate" value={pct(k.export_rate_pct)} sub={`of received fruit is exported`} />
        <Kpi label="Local market" value={t(k.local_t)} tone={k.local_t > 0 ? 'alert' : undefined}
          sub={<>worth {eur(k.local_value_eur)} <span className="muted">vs {eur(localRef)} at export reference</span></>}
          onClick={nav.local} action="See the residual" />
        <Kpi label="Export revenue" value={eur(k.export_revenue_eur)} sub="Σ tonnes × client price" />
        <Kpi label="Total value" value={eur(k.total_value_eur)} sub="export revenue + local value" />
        <Kpi label="Clients at risk" value={`${k.at_risk_clients} of ${plan.clients.length}`}
          tone={k.at_risk_clients > 0 ? 'warn' : undefined}
          sub={atRisk.length ? `${t(atRisk.reduce((s, c) => s + c.remaining_t, 0))} of demand not served` : 'All orders complete'} />
      </div>

      <div className="decide-grid">
        <div className="card">
          <h3>Needs a committee decision</h3>
          {atRisk.length === 0 && localSegments.length === 0 && (
            <p className="muted">Every order is complete and all fruit is exported.</p>
          )}
          <ul className="attention">
            {atRisk.map((c) => (
              <li key={c.client_id}>
                <span className={`chip ${c.status.toLowerCase()}`}>{c.status === 'PARTIAL' ? 'Partial' : 'Unserved'}</span>
                <div>
                  <button type="button" className="link strong" onClick={() => nav.client(c.client_id)}>
                    {c.client_id} {c.client_name}
                  </button>{' '}
                  is {t(c.remaining_t)} short ({eur(c.remaining_t * c.price_per_t_eur)} of orders).
                  <div className="muted small">
                    {reasonShort[c.shortage_reason!]}
                    {c.shortage_reason === 'INSUFFICIENT_COMPATIBLE_SEGMENT'
                      ? `: Segment ${c.compatible_segments.join('/')} received ${t(c.compatible_actual_t)} vs plan ${t(c.compatible_expected_t)}`
                      : `: ${t(c.station_remaining_before_t)} of line left at its turn (priority #${c.priority})`}
                  </div>
                </div>
              </li>
            ))}
            {localSegments.map((s) => (
              <li key={s.segment}>
                <span className="chip local">Local</span>
                <div>
                  <button type="button" className="link strong" onClick={nav.local}>
                    {t(s.local_t)} of Segment {s.segment}
                  </button>{' '}
                  fall back to the local market for {eur(s.local_value_eur)}
                  <div className="muted small">
                    {eur(s.export_equivalent_value_eur - s.local_value_eur)} below the Segment {s.segment} export reference
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {unmetValue > 0 && (
            <p className="muted small">Unserved orders total {eur(unmetValue)} at client prices.</p>
          )}
        </div>

        <div className="card">
          <h3>From farm receipts to export, by quality segment</h3>
          <div className="table-wrap">
            <table className="table compact num-right">
              <caption className="sr-only">Plan, actual, export and local tonnes per segment</caption>
              <thead>
                <tr>
                  <th scope="col">Segment</th><th scope="col">Plan</th><th scope="col">Actual</th>
                  <th scope="col">Gap</th><th scope="col">Exported</th><th scope="col">Local</th>
                  <th scope="col" className="left">Clients short on it</th>
                </tr>
              </thead>
              <tbody>
                {SEGMENTS.map((seg) => {
                  const s = plan.segments.find((x) => x.segment === seg)!
                  const short = atRisk.filter(
                    (c) => c.shortage_reason === 'INSUFFICIENT_COMPATIBLE_SEGMENT' && c.compatible_segments.includes(seg),
                  )
                  return (
                    <tr key={seg}>
                      <th scope="row">
                        <button type="button" className="link seg-link" onClick={() => nav.segment(seg)}
                          aria-label={`Show farms for Segment ${seg}`}>
                          <span className={`seg seg-${seg}`}>{seg}</span>
                        </button>
                      </th>
                      <td>{t(s.expected_t)}</td>
                      <td>{t(s.actual_t)}</td>
                      <td className={s.variance_t < -0.05 ? 'neg' : s.variance_t > 0.05 ? 'pos' : ''}>{delta(s.variance_t)}</td>
                      <td>{t(s.exported_t)}</td>
                      <td className={s.local_t > 0 ? 'alert-text' : ''}>{t(s.local_t)}</td>
                      <td className="left">
                        {short.length === 0 ? <span className="muted">—</span> : short.map((c) => (
                          <button key={c.client_id} type="button" className="id-chip" onClick={() => nav.client(c.client_id)}>
                            {c.client_id} −{c.remaining_t} t
                          </button>
                        ))}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="muted small">Click a segment to see which farms caused the gap.</p>
        </div>
      </div>
    </section>
  )
}

function Kpi({
  label, value, sub, tone, onClick, action,
}: {
  label: string
  value: string
  sub?: React.ReactNode
  tone?: 'warn' | 'alert'
  onClick?: () => void
  action?: string
}) {
  return (
    <div className={`kpi ${tone ?? ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
      {onClick && <button type="button" className="link small" onClick={onClick}>{action} →</button>}
    </div>
  )
}

function Meter({ value, label }: { value: number; label: string }) {
  return (
    <span className="meter-wrap">
      <span className="meter" role="img" aria-label={label}>
        <span style={{ width: `${Math.min(100, value)}%` }} />
      </span>
      <span>{label}</span>
    </span>
  )
}

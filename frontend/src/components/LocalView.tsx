import type { PlanResult } from '../types'
import { eur, reasonShort, t } from '../format'
import type { Nav } from './Workspace'

export function LocalView({ plan, nav }: { plan: PlanResult; nav: Nav }) {
  const k = plan.kpis
  const rows = plan.farm_segments
    .filter((b) => b.local_t > 0)
    .sort((a, b) => b.local_value_eur - a.local_value_eur || a.farm_id.localeCompare(b.farm_id))
  const segs = plan.segments.filter((s) => s.local_t > 0)
  const refValue = segs.reduce((s, x) => s + x.export_equivalent_value_eur, 0)
  const stationFull = k.station_capacity_t - k.export_t < 5

  if (k.local_t === 0) {
    return (
      <section aria-label="Local residual">
        <p className="state-inline">All {t(k.actual_received_t)} received are exported. Nothing goes to the local market today.</p>
      </section>
    )
  }

  return (
    <section aria-label="Local residual">
      <div className="local-hero">
        <div>
          <div className="kpi-label">Falls back to the local market</div>
          <div className="local-big">{t(k.local_t)}</div>
          <div className="muted">{(100 - k.export_rate_pct).toFixed(1)} % of today’s receipts</div>
        </div>
        <div>
          <div className="kpi-label">Local value</div>
          <div className="local-big alert-text">{eur(k.local_value_eur)}</div>
          <div className="muted">vs {eur(refValue)} at segment export reference prices</div>
        </div>
        <div>
          <div className="kpi-label">Value given up vs reference</div>
          <div className="local-big">{eur(refValue - k.local_value_eur)}</div>
          <div className="muted">reference prices are for valuation only, never for client priority</div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="card">
          <h3>Why this fruit is not exported</h3>
          <ul className="why">
            {segs.map((s) => {
              const open = plan.clients.filter((c) => c.remaining_t > 0 && c.compatible_segments.includes(s.segment))
              return (
                <li key={s.segment}>
                  <span className={`seg seg-${s.segment}`}>{s.segment}</span>{' '}
                  <strong>{t(s.local_t)}</strong> of Segment {s.segment} left after {t(s.exported_t)} were exported.{' '}
                  {open.length === 0 ? (
                    <>No export order that accepts Segment {s.segment} has open demand.</>
                  ) : (
                    <>
                      Open orders that accept it:{' '}
                      {open.map((c) => (
                        <button key={c.client_id} type="button" className="id-chip" onClick={() => nav.client(c.client_id)}>
                          {c.client_id} {t(c.remaining_t)} · {reasonShort[c.shortage_reason!]}
                        </button>
                      ))}
                    </>
                  )}
                </li>
              )
            })}
          </ul>
          {stationFull && (
            <p className="small">
              The export line is full ({t(k.export_t)} of {t(k.station_capacity_t)}), so no additional tonne can
              be exported today without replacing a higher-priced order.
            </p>
          )}
        </div>

        <div className="card">
          <h3>Local tonnes by farm and segment</h3>
          <div className="table-wrap">
            <table className="table compact num-right">
              <caption className="sr-only">Residual local tonnes and values</caption>
              <thead>
                <tr>
                  <th scope="col" className="left">Farm</th><th scope="col" className="left">Segment</th>
                  <th scope="col">Local</th><th scope="col">Local value</th><th scope="col">At export reference</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((b) => {
                  const ref = plan.segments.find((s) => s.segment === b.segment)!.reference_price_per_t_eur
                  return (
                    <tr key={`${b.farm_id}-${b.segment}`}>
                      <td className="left"><button type="button" className="id-chip" onClick={() => nav.farm(b.farm_id)}>{b.farm_id}</button></td>
                      <td className="left"><span className={`seg seg-${b.segment}`}>{b.segment}</span></td>
                      <td className="strong">{t(b.local_t)}</td>
                      <td className="alert-text">{eur(b.local_value_eur)}</td>
                      <td className="muted">{eur(b.local_t * ref)}</td>
                    </tr>
                  )
                })}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row" colSpan={2} className="left">Total</th>
                  <td className="strong">{t(k.local_t)}</td>
                  <td className="strong alert-text">{eur(k.local_value_eur)}</td>
                  <td className="muted">{eur(refValue)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
          <button type="button" className="link small" onClick={() => nav.trace({ destination: 'local' })}>
            Show local rows in the allocation trace →
          </button>
        </div>
      </div>
    </section>
  )
}

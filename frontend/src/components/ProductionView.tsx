import { Fragment, useEffect, useRef, useState } from 'react'
import { SEGMENTS, type PlanResult, type Segment } from '../types'
import { delta, eur, t } from '../format'
import type { Nav } from './Workspace'

type Sort = 'farm' | 'gap' | 'local'

/** Shade a segment cell only when the gap is at least half a 5 t lot. */
const SHADE_T = 2.5

export function ProductionView({
  plan, nav, openFarm, setOpenFarm, segmentFocus, setSegmentFocus,
}: {
  plan: PlanResult
  nav: Nav
  openFarm: string | null
  setOpenFarm: (id: string | null) => void
  segmentFocus: Segment | null
  setSegmentFocus: (s: Segment | null) => void
}) {
  const [sort, setSort] = useState<Sort>('farm')
  const [belowOnly, setBelowOnly] = useState(false)
  const openRow = useRef<HTMLTableRowElement>(null)

  const cellOf = (farmId: string, seg: Segment) =>
    plan.farm_segments.find((b) => b.farm_id === farmId && b.segment === seg)!
  const gapOf = (farmId: string) =>
    segmentFocus ? cellOf(farmId, segmentFocus).variance_t
      : plan.farms.find((f) => f.farm_id === farmId)!.variance_t

  let farms = [...plan.farms]
  if (segmentFocus) {
    farms = farms.filter((f) => {
      const c = cellOf(f.farm_id, segmentFocus)
      return c.expected_t > 0 || c.actual_t > 0
    })
  }
  if (belowOnly) farms = farms.filter((f) => gapOf(f.farm_id) < -0.05)
  if (sort === 'gap') farms.sort((a, b) => gapOf(a.farm_id) - gapOf(b.farm_id))
  if (sort === 'local') farms.sort((a, b) => b.local_t - a.local_t || a.farm_id.localeCompare(b.farm_id))

  useEffect(() => {
    if (openFarm) openRow.current?.scrollIntoView({ block: 'center' })
  }, [openFarm])

  const below = plan.farms.filter((f) => f.variance_t < -0.05).length
  const above = plan.farms.filter((f) => f.variance_t > 0.05).length

  return (
    <section aria-label="Production: plan versus actual by farm">
      <div className="view-head">
        <p>
          <strong>{below}</strong> farms delivered below their expected capacity, <strong>{above}</strong> above.
          Gaps are actual − plan, where plan = expected capacity × expected mix. Shaded cells differ by
          2.5 t or more.
        </p>
        <div className="controls">
          <label>
            Segment{' '}
            <select value={segmentFocus ?? ''} onChange={(e) => setSegmentFocus((e.target.value || null) as Segment | null)}>
              <option value="">All segments</option>
              {SEGMENTS.map((s) => <option key={s} value={s}>Segment {s}</option>)}
            </select>
          </label>
          <label>
            Sort{' '}
            <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              <option value="farm">Farm ID</option>
              <option value="gap">Largest shortfall first</option>
              <option value="local">Most local tonnes first</option>
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={belowOnly} onChange={(e) => setBelowOnly(e.target.checked)} />
            Below plan only
          </label>
        </div>
      </div>
      {segmentFocus && (
        <p className="focus-note">
          Showing Segment {segmentFocus} only.{' '}
          <button type="button" className="link" onClick={() => setSegmentFocus(null)}>Show all segments</button>
        </p>
      )}

      <div className="table-wrap">
        <table className="table num-right production">
          <caption className="sr-only">Farms with expected and actual tonnes per segment</caption>
          <thead>
            <tr>
              <th scope="col" className="left">Farm</th>
              <th scope="col">Plan</th>
              <th scope="col">Actual</th>
              <th scope="col">Gap</th>
              {SEGMENTS.filter((s) => !segmentFocus || s === segmentFocus).map((s) => (
                <th key={s} scope="col"><span className={`seg seg-${s}`}>{s}</span> actual · gap</th>
              ))}
              <th scope="col">Exported</th>
              <th scope="col">Local</th>
            </tr>
          </thead>
          <tbody>
            {farms.length === 0 && (
              <tr><td colSpan={10} className="left muted">No farm matches these filters.</td></tr>
            )}
            {farms.map((f) => {
              const open = openFarm === f.farm_id
              return (
                <Fragment key={f.farm_id}>
                  <tr className={open ? 'open' : ''} ref={open ? openRow : undefined}>
                    <th scope="row" className="left">
                      <button type="button" className="row-toggle" aria-expanded={open}
                        onClick={() => setOpenFarm(open ? null : f.farm_id)}>
                        <span className="caret" aria-hidden="true">▸</span>
                        <code>{f.farm_id}</code> <span className="muted">{f.farm_name}</span>
                      </button>
                    </th>
                    <td>{t(f.expected_capacity_t)}</td>
                    <td>{t(f.actual_t)}</td>
                    <td className={f.variance_t < -0.05 ? 'neg' : f.variance_t > 0.05 ? 'pos' : ''}>{delta(f.variance_t)}</td>
                    {SEGMENTS.filter((s) => !segmentFocus || s === segmentFocus).map((s) => {
                      const c = cellOf(f.farm_id, s)
                      const tone = c.variance_t <= -SHADE_T ? 'neg' : c.variance_t >= SHADE_T ? 'pos' : 'flat'
                      return (
                        <td key={s} className={`segcell ${tone}`}
                          aria-label={`Segment ${s}: actual ${t(c.actual_t)}, plan ${t(c.expected_t)}, gap ${delta(c.variance_t)}`}>
                          <span className="segcell-actual">{c.actual_t === 0 && c.expected_t === 0 ? '·' : c.actual_t}</span>
                          {(c.expected_t > 0 || c.actual_t > 0) && (
                            <span className={`segcell-gap ${c.variance_t < -0.05 ? 'neg' : c.variance_t > 0.05 ? 'pos' : ''}`}>{delta(c.variance_t)}</span>
                          )}
                        </td>
                      )
                    })}
                    <td>{t(f.exported_t)}</td>
                    <td className={f.local_t > 0 ? 'alert-text strong' : 'muted'}>{t(f.local_t)}</td>
                  </tr>
                  {open && (
                    <tr className="detail-row">
                      <td colSpan={10}>
                        <FarmDetail plan={plan} farmId={f.farm_id} nav={nav} />
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

function FarmDetail({ plan, farmId, nav }: { plan: PlanResult; farmId: string; nav: Nav }) {
  const rows = plan.farm_segments.filter((b) => b.farm_id === farmId && (b.expected_t > 0 || b.actual_t > 0))
  const allocs = plan.allocations.filter((a) => a.farm_id === farmId)
  return (
    <div className="detail">
      <h4>Where {farmId}’s fruit went today</h4>
      <table className="table compact num-right">
        <thead>
          <tr>
            <th scope="col" className="left">Segment</th><th scope="col">Plan</th><th scope="col">Actual</th>
            <th scope="col">Gap</th><th scope="col" className="left">Exported to</th>
            <th scope="col">Local</th><th scope="col">Local value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((b) => (
            <tr key={b.segment}>
              <th scope="row" className="left"><span className={`seg seg-${b.segment}`}>{b.segment}</span></th>
              <td>{t(b.expected_t)}</td>
              <td>{t(b.actual_t)}</td>
              <td className={b.variance_t < -0.05 ? 'neg' : b.variance_t > 0.05 ? 'pos' : ''}>{delta(b.variance_t)}</td>
              <td className="left">
                {allocs.filter((a) => a.segment === b.segment).map((a) => (
                  <button key={a.sequence} type="button" className="id-chip" onClick={() => nav.client(a.client_id)}
                    title={`${a.client_name}: ${eur(a.export_revenue_eur)}`}>
                    {a.client_id} · {a.tonnes} t
                  </button>
                ))}
                {b.exported_t === 0 && <span className="muted">—</span>}
              </td>
              <td className={b.local_t > 0 ? 'alert-text strong' : ''}>{t(b.local_t)}</td>
              <td>{eur(b.local_value_eur)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button type="button" className="link small" onClick={() => nav.trace({ farm: farmId })}>
        Open {farmId} in the allocation trace →
      </button>
    </div>
  )
}

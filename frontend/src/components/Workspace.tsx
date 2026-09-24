import { useMemo, useRef, useState } from 'react'
import type { LoadResult, PlanResult, Segment } from '../types'
import { Summary } from './Summary'
import { ProductionView } from './ProductionView'
import { CommercialView } from './CommercialView'
import { TraceView, type TraceFilter } from './TraceView'
import { LocalView } from './LocalView'
import { AssistantView } from './AssistantView'

export type Tab = 'production' | 'commercial' | 'trace' | 'local' | 'assist'

const TABS: { id: Tab; label: string; hint: string }[] = [
  { id: 'production', label: 'Production', hint: 'Plan vs actual by farm' },
  { id: 'commercial', label: 'Commercial', hint: 'Client service' },
  { id: 'trace', label: 'Allocation trace', hint: 'Farm → client' },
  { id: 'local', label: 'Local residual', hint: 'Fruit not exported' },
  { id: 'assist', label: 'Explain', hint: 'Ask the assistant' },
]

/** Cross-view navigation: every ID in the workspace can jump to where it is explained. */
export interface Nav {
  client: (id: string) => void
  farm: (id: string) => void
  trace: (filter: TraceFilter) => void
  local: () => void
  segment: (s: Segment) => void
}

export function Workspace({ load, plan }: { load: LoadResult; plan: PlanResult }) {
  const [tab, setTab] = useState<Tab>('production')
  const [openClient, setOpenClient] = useState<string | null>(null)
  const [openFarm, setOpenFarm] = useState<string | null>(null)
  const [segmentFocus, setSegmentFocus] = useState<Segment | null>(null)
  const [traceFilter, setTraceFilter] = useState<TraceFilter>({})
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({
    production: null, commercial: null, trace: null, local: null, assist: null,
  })
  const panel = useRef<HTMLDivElement>(null)

  const show = (next: Tab) => {
    setTab(next)
    requestAnimationFrame(() => panel.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }))
  }

  const nav: Nav = useMemo(() => ({
    client: (id) => { setOpenClient(id); show('commercial') },
    farm: (id) => { setOpenFarm(id); setSegmentFocus(null); show('production') },
    trace: (f) => { setTraceFilter(f); show('trace') },
    local: () => show('local'),
    segment: (s) => { setSegmentFocus(s); setOpenFarm(null); show('production') },
  }), [])

  const onTabKey = (e: React.KeyboardEvent, i: number) => {
    const delta = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    const target =
      delta !== 0 ? TABS[(i + delta + TABS.length) % TABS.length]
      : e.key === 'Home' ? TABS[0]
      : e.key === 'End' ? TABS[TABS.length - 1]
      : null
    if (!target) return
    e.preventDefault()
    setTab(target.id)
    tabRefs.current[target.id]?.focus()
  }

  return (
    <>
      <Summary load={load} plan={plan} nav={nav} />

      <div className="tabs-shell" ref={panel}>
        <div role="tablist" aria-label="Workspace views" className="tabs">
          {TABS.map((tb, i) => (
            <button
              key={tb.id}
              ref={(el) => { tabRefs.current[tb.id] = el }}
              role="tab"
              id={`tab-${tb.id}`}
              aria-selected={tab === tb.id}
              aria-controls={`panel-${tb.id}`}
              tabIndex={tab === tb.id ? 0 : -1}
              className="tab"
              onClick={() => setTab(tb.id)}
              onKeyDown={(e) => onTabKey(e, i)}
            >
              <span>{tb.label}</span>
              <span className="tab-hint">{tb.hint}</span>
            </button>
          ))}
        </div>
        <div role="tabpanel" id={tab === 'assist' ? undefined : `panel-${tab}`} aria-labelledby={`tab-${tab}`} className="panel" hidden={tab === 'assist'}>
          {tab === 'production' && (
            <ProductionView
              plan={plan}
              nav={nav}
              openFarm={openFarm}
              setOpenFarm={setOpenFarm}
              segmentFocus={segmentFocus}
              setSegmentFocus={setSegmentFocus}
            />
          )}
          {tab === 'commercial' && (
            <CommercialView plan={plan} nav={nav} openClient={openClient} setOpenClient={setOpenClient} />
          )}
          {tab === 'trace' && (
            <TraceView plan={plan} nav={nav} filter={traceFilter} setFilter={setTraceFilter} />
          )}
          {tab === 'local' && <LocalView plan={plan} nav={nav} />}
        </div>
        {/* Kept mounted so an answer survives jumping to its evidence and back. */}
        <div role="tabpanel" id="panel-assist" aria-labelledby="tab-assist" className="panel" hidden={tab !== 'assist'}>
          <AssistantView plan={plan} nav={nav} />
        </div>
      </div>
    </>
  )
}

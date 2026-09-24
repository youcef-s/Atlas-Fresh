import { useRef, useState } from 'react'
import { api, ApiError } from './api'
import { Workspace } from './components/Workspace'
import { EmptyState, ErrorState, LoadingState } from './components/States'
import type { ErrorBody, LoadResult, PlanResult } from './types'

type Phase =
  | { kind: 'empty' }
  | { kind: 'loading'; step: 'load' | 'plan' }
  | { kind: 'error'; error: ErrorBody; retry: () => void; retryLabel: string }
  | { kind: 'ready'; load: LoadResult; plan: PlanResult }

export default function App() {
  const [phase, setPhase] = useState<Phase>({ kind: 'empty' })
  const fileInput = useRef<HTMLInputElement>(null)

  const chooseFile = () => fileInput.current?.click()

  async function run(loader: () => Promise<LoadResult>, fromUpload = false) {
    const retry = () => void run(loader, fromUpload)
    try {
      setPhase({ kind: 'loading', step: 'load' })
      const load = await loader()
      setPhase({ kind: 'loading', step: 'plan' })
      const plan = await api.plan()
      setPhase({ kind: 'ready', load, plan })
    } catch (err) {
      const error: ErrorBody =
        err instanceof ApiError
          ? err.body
          : { kind: 'server', message: 'Something unexpected happened in the browser.', issues: [] }
      // A rejected upload needs a corrected file; anything else can simply be retried.
      const needsNewFile = fromUpload && error.kind === 'validation'
      setPhase({
        kind: 'error',
        error,
        retry: needsNewFile ? chooseFile : retry,
        retryLabel: needsNewFile ? 'Choose a corrected file…' : error.kind === 'validation' ? 'Reload workbook' : 'Retry',
      })
    }
  }

  const loadSeed = () => void run(api.loadSeed)
  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file) void run(() => api.loadFile(file), true)
  }
  const reset = () => setPhase({ kind: 'empty' })

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">AF</span>
          <div>
            <h1>Atlas Fresh · Daily export committee</h1>
            <p className="muted small">
              Decision support only. Production and Commercial approve execution.
            </p>
          </div>
        </div>
        <div className="topbar-actions">
          {phase.kind === 'ready' && (
            <span className="source small muted" title="Source workbook (read-only)">
              {phase.load.source}
            </span>
          )}
          <button type="button" className="btn" onClick={loadSeed} disabled={phase.kind === 'loading'}>
            {phase.kind === 'empty' ? 'Load today’s workbook' : 'Reload workbook'}
          </button>
          <button type="button" className="btn ghost" onClick={chooseFile} disabled={phase.kind === 'loading'}>
            Validate another file…
          </button>
          {phase.kind !== 'empty' && (
            <button type="button" className="btn ghost" onClick={reset} disabled={phase.kind === 'loading'}>
              Reset
            </button>
          )}
          <input
            ref={fileInput}
            type="file"
            accept=".xlsx"
            hidden
            onChange={onFile}
            aria-label="Workbook file to validate"
          />
        </div>
      </header>

      <main id="main" aria-busy={phase.kind === 'loading'}>
        {phase.kind === 'empty' && <EmptyState onLoad={loadSeed} />}
        {phase.kind === 'loading' && <LoadingState step={phase.step} />}
        {phase.kind === 'error' && <ErrorState error={phase.error} onRetry={phase.retry} retryLabel={phase.retryLabel} onReset={reset} />}
        {phase.kind === 'ready' && <Workspace load={phase.load} plan={phase.plan} />}
      </main>
    </div>
  )
}

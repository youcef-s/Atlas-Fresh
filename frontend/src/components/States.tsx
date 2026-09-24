import { useEffect, useRef } from 'react'
import type { ErrorBody } from '../types'

export function EmptyState({ onLoad }: { onLoad: () => void }) {
  return (
    <section className="state-card" aria-labelledby="empty-title">
      <h2 id="empty-title">Prepare today’s committee</h2>
      <ol className="journey">
        <li><strong>Load</strong> the daily workbook. The server validates it and never changes it.</li>
        <li><strong>Compare</strong> farm plans with actual receipts by quality segment.</li>
        <li><strong>Plan</strong> the export allocation with the fixed company policy.</li>
        <li><strong>Decide</strong> on client risks, station use and the local-market residual.</li>
        <li><strong>Explain</strong> any figure with a traceable farm, segment and client.</li>
      </ol>
      <button type="button" className="btn primary" onClick={onLoad} autoFocus>
        Load today’s workbook
      </button>
    </section>
  )
}

export function LoadingState({ step }: { step: 'load' | 'plan' }) {
  return (
    <section className="state-card" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <h2>{step === 'load' ? 'Validating the workbook…' : 'Calculating the export plan…'}</h2>
      <p className="muted">
        {step === 'load'
          ? 'Checking IDs, quality rules, mixes, quantities and the station.'
          : 'Applying the policy: highest price first, closest-quality fruit, 5 t steps.'}
      </p>
      <div className="skeleton" aria-hidden="true">
        <span /><span /><span /><span />
      </div>
    </section>
  )
}

const TITLES: Record<ErrorBody['kind'], string> = {
  validation: 'The workbook was rejected',
  not_loaded: 'No workbook is loaded',
  server: 'The planning server failed',
  network: 'The planning server is unreachable',
}

export function ErrorState({
  error,
  onRetry,
  retryLabel,
  onReset,
}: {
  error: ErrorBody
  onRetry: () => void
  retryLabel: string
  onReset: () => void
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => heading.current?.focus(), [error])
  const isValidation = error.kind === 'validation'

  return (
    <section className={`state-card ${isValidation ? 'warn' : 'danger'}`} role="alert">
      <h2 ref={heading} tabIndex={-1}>{TITLES[error.kind]}</h2>
      <p>{error.message}</p>
      {isValidation && error.issues.length > 0 && (
        <>
          <p className="muted small">
            Nothing was repaired automatically, and no plan was calculated from this file.
            {' '}{error.issues.length} issue{error.issues.length === 1 ? '' : 's'} found:
          </p>
          <div className="table-wrap">
            <table className="table compact">
              <thead>
                <tr><th scope="col">Sheet</th><th scope="col">Farm / client / item</th><th scope="col">Field</th><th scope="col">What to fix</th></tr>
              </thead>
              <tbody>
                {error.issues.map((i, n) => (
                  <tr key={n}>
                    <td>{i.sheet}</td>
                    <td><code>{i.identifier}</code></td>
                    <td>{i.field ? <code>{i.field}</code> : '—'}</td>
                    <td>{i.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div className="row gap">
        <button type="button" className="btn primary" onClick={onRetry}>
          {retryLabel}
        </button>
        <button type="button" className="btn ghost" onClick={onReset}>Reset workspace</button>
      </div>
    </section>
  )
}

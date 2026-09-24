import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import type { AssistantAnswer, AssistantConfig, PlanResult, QuestionId, Segment } from '../types'
import type { Nav } from './Workspace'

const PRESETS: { id: Exclude<QuestionId, 'custom'>; label: string }[] = [
  { id: 'at_risk', label: 'Which clients are at risk and why?' },
  { id: 'gaps', label: 'Which farm/segment gaps matter most today?' },
  { id: 'local', label: 'Why is fruit going local and what is it worth?' },
]

const STATUS_TITLE: Record<AssistantAnswer['status'], string> = {
  answered: 'AI answer',
  unavailable: 'Not available in today’s data',
  no_key: 'No AI model configured',
  timeout: 'The AI model timed out',
  provider_error: 'The AI provider failed',
  invalid_output: 'AI answer rejected',
}

type State =
  | { kind: 'idle' }
  | { kind: 'asking'; question: string }
  | { kind: 'done'; answer: AssistantAnswer }
  | { kind: 'error'; message: string; retry: () => void }

export function AssistantView({ plan, nav }: { plan: PlanResult; nav: Nav }) {
  const clientIds = new Set(plan.clients.map((c) => c.client_id))
  const [config, setConfig] = useState<AssistantConfig | null>(null)
  const [state, setState] = useState<State>({ kind: 'idle' })
  const [text, setText] = useState('')
  const result = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.assistantConfig().then(setConfig).catch(() => setConfig(null))
  }, [])

  async function ask(id: QuestionId, question: string, custom?: string) {
    setState({ kind: 'asking', question })
    try {
      const answer = await api.ask(id, custom)
      setState({ kind: 'done', answer })
    } catch (err) {
      const message = err instanceof ApiError ? err.body.message : 'The assistant request failed.'
      setState({ kind: 'error', message, retry: () => void ask(id, question, custom) })
    }
    requestAnimationFrame(() => result.current?.focus())
  }

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const q = text.trim()
    if (q) void ask('custom', q, q)
  }
  const busy = state.kind === 'asking'

  return (
    <section aria-label="Planning assistant" className="assistant">
      <div className="view-head">
        <p>
          The assistant <strong>explains</strong> the calculated plan. It cannot change allocations,
          confirm execution or contact anyone. The server checks every ID and number in an AI answer
          against the plan before showing it.
        </p>
        <span className={`health ${config?.configured ? 'ok' : 'neutral'}`}>
          {config === null ? 'Checking model…'
            : config.configured ? `Model: ${config.model} (Anthropic API)`
            : 'No AI model configured: deterministic summaries only'}
        </span>
      </div>

      <div className="ask-row" role="group" aria-label="Standard questions">
        {PRESETS.map((p) => (
          <button key={p.id} type="button" className="btn" disabled={busy} onClick={() => void ask(p.id, p.label)}>
            {p.label}
          </button>
        ))}
      </div>
      <form className="ask-form" onSubmit={onSubmit}>
        <label htmlFor="ask-text" className="sr-only">Your question about today’s plan</label>
        <input
          id="ask-text"
          type="text"
          maxLength={300}
          placeholder={config?.configured ? 'Ask about today’s plan…' : 'Free-text questions need an AI model'}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy}
        />
        <button type="submit" className="btn primary" disabled={busy || !text.trim()}>Ask</button>
      </form>

      <div ref={result} tabIndex={-1} aria-live="polite" className="ask-result">
        {state.kind === 'idle' && <p className="muted">Pick a question above.</p>}
        {state.kind === 'asking' && (
          <p className="muted"><span className="spinner inline" aria-hidden="true" /> Asking: “{state.question}”…</p>
        )}
        {state.kind === 'error' && (
          <div className="answer-card danger">
            <h3>The assistant could not answer</h3>
            <p>{state.message}</p>
            <button type="button" className="btn" onClick={state.retry}>Retry</button>
          </div>
        )}
        {state.kind === 'done' && <Answer a={state.answer} nav={nav} clientIds={clientIds} />}
      </div>
    </section>
  )
}

function Answer({ a, nav, clientIds }: { a: AssistantAnswer; nav: Nav; clientIds: Set<string> }) {
  const ai = a.status === 'answered'
  return (
    <>
      <p className="small muted">Question: “{a.question}”</p>
      {(ai || a.status === 'unavailable') && a.answer && (
        <div className={`answer-card ${ai ? 'ai' : 'warn'}`}>
          <h3>{STATUS_TITLE[a.status]} <span className="muted small">{a.model}</span></h3>
          <p>{a.answer}</p>
          {a.citations.length > 0 && <Citations ids={a.citations} nav={nav} clientIds={clientIds} />}
          {ai && <p className="small muted">✓ Server check passed: every ID and number is in the calculated plan.</p>}
          {a.notice && <p className="small">{a.notice}</p>}
        </div>
      )}
      {!ai && a.status !== 'unavailable' && (
        <div className="answer-card warn">
          <h3>{STATUS_TITLE[a.status]}</h3>
          <p>{a.notice}</p>
        </div>
      )}
      {!ai && a.deterministic_summary && (
        <div className="answer-card det">
          <h3>Deterministic summary <span className="tag">not AI: generated from the plan</span></h3>
          <p>{a.deterministic_summary}</p>
          <Citations ids={a.deterministic_citations} nav={nav} clientIds={clientIds} />
        </div>
      )}
    </>
  )
}

function Citations({ ids, nav, clientIds }: { ids: string[]; nav: Nav; clientIds: Set<string> }) {
  return (
    <p className="small">
      Evidence:{' '}
      {ids.map((id) => {
        const seg = /^Segment ([ABCD])$/.exec(id)
        const go = seg ? () => nav.segment(seg[1] as Segment)
          : clientIds.has(id) ? () => nav.client(id)
          : () => nav.farm(id)
        return (
          <button key={id} type="button" className="id-chip" onClick={go}>{id}</button>
        )
      })}
    </p>
  )
}

import type { ErrorBody, LoadResult, PlanResult } from './types'

export class ApiError extends Error {
  readonly body: ErrorBody
  constructor(body: ErrorBody) {
    super(body.message)
    this.body = body
  }
}

const TIMEOUT_MS = 15_000

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { method: 'POST', ...init, signal: AbortSignal.timeout(TIMEOUT_MS) })
  } catch (err) {
    const timedOut = err instanceof DOMException && err.name === 'TimeoutError'
    throw new ApiError({
      kind: 'network',
      message: timedOut
        ? 'The planning server did not answer within 15 s.'
        : 'The planning server cannot be reached. Check that the backend is running.',
      issues: [],
    })
  }
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    const known = body as Partial<ErrorBody> | null
    throw new ApiError({
      kind: known?.kind ?? 'server',
      message: known?.message ?? `Server responded ${res.status}.`,
      issues: known?.issues ?? [],
    })
  }
  if (body === null) {
    throw new ApiError({ kind: 'server', message: 'The server returned an unreadable answer.', issues: [] })
  }
  return body as T
}

export const api = {
  loadSeed: () => request<LoadResult>('/api/load'),
  loadFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<LoadResult>('/api/load/upload', { body: form })
  },
  plan: () => request<PlanResult>('/api/plan'),
}
